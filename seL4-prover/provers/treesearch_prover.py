import os
import re
from collections.abc import Mapping
from enum import Enum, StrEnum, auto
from logging import Logger
from pathlib import Path
from typing import Any, override

import Levenshtein
import requests
from pydantic import BaseModel, NonNegativeInt
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from treelib import Node, Tree  # pyright: ignore[reportPrivateImportUsage]
from urllib3.util.retry import Retry

from data.lemma import LemmaProtocol, ProofStep
from provers.lib import ProverProtocol
from provers.logger import get_proof_logger
from utils.build_proof_steps import combine_premises, extract_premises
from utils.parser import shorten_text
from utils.repl import IsaRepl


class ProofState(BaseModel):
    proof_steps: list[str]
    state: str


class ScoredProofState(ProofState):
    score: float


class ProofStatus(Enum):
    OK = auto()
    NO_MORE_STEPS = auto()
    FAILED = auto()  # failed to apply the tactic
    DUPLICATE_STEP = auto()
    DUPLICATE_PATH = auto()
    DUPLICATE_STATE = auto()
    SUCCESS = auto()


class ProofStateResult(BaseModel):
    status: ProofStatus
    result: ProofState | None = None


class ProofTree(Tree):
    """
    A specialized tree structure to manage the proof search space.

    This class inherits from treelib.Tree and adds mappings to quickly
    access nodes by their corresponding proof state or proof sequence.
    """

    def __init__(self, lemma: LemmaProtocol):
        super().__init__()
        self.proof2id: dict[str, int] = {}
        self.state2id: dict[str, int] = {}
        self.curr_id: int = 0
        self.lemma: LemmaProtocol = lemma

    def save_node(
        self, data: ScoredProofState, parent_node: Node | None, isa_repl: IsaRepl
    ) -> Node:
        """
        Creates, saves, and registers a new node in the proof tree.

        Each node represents a unique proof state. A corresponding thread-local
        state is created in the Isabelle REPL to allow independent exploration.

        Args:
            data: A `ScoredProofState` holding the state, proof steps, and score.
            parent_node: The parent node in the tree. `None` for the root.
            isa_repl: The Isabelle REPL instance.

        Returns:
            The newly created node.
        """
        node = Node(identifier=str(self.curr_id), data=data)
        state = data.state
        proof_steps = data.proof_steps
        proof_key = "\n".join(proof_steps)

        self.add_node(node, parent=parent_node)
        # Create a corresponding state in the Isabelle REPL for this node.
        isa_repl.clone_tls(str(self.curr_id))

        self.proof2id[proof_key] = self.curr_id
        self.state2id[state] = self.curr_id
        self.curr_id += 1
        return node

    def getProof(self, state: str) -> list[ScoredProofState]:
        """
        Trace the path from the root to the node for `state`.

        Returns a list of `ScoredProofState` values ordered from the root
        downward, or an empty list when `state` is not in the tree.
        """
        if state not in self.state2id:
            return []
        res = [self[i].data for i in self.rsearch(str(self.state2id[state]))]
        res.reverse()
        return res


class ResultFlag(StrEnum):
    PROVED_WO_HAMMER = "PROVED_WO_HAMMER"
    HAMMERED = "HAMMERED"
    FAILED_INIT = "FAILED_INIT"
    FAIL = "FAIL"


class TreeNode(ProofStep):
    id: NonNegativeInt
    parent: NonNegativeInt | None
    children: list[NonNegativeInt]
    from_hammer: bool = False
    score: float | None = None
    state_score: float | None = None
    success: bool = False


class TreeSearchProverConfig(BaseModel):
    max_attempts: int = int(
        os.getenv("TREE_SEARCH_MAX_ATTEMPTS", "128")
    )  # max attempts to find a proof
    selected_states_num: int = int(
        os.getenv("TREE_SEARCH_SELECTED_STATES_NUM", "5")
    )  # at each iteration, select 5 states
    selected_hammer_num: int = int(
        os.getenv("TREE_SEARCH_SELECTED_HAMMER_NUM", "128")
    )  # finally, select 128 hammer steps
    width: int = int(
        os.getenv("TREE_SEARCH_WIDTH", "128")
    )  # at each iteration, generate 128 steps
    max_depth: int = int(
        os.getenv("TREE_SEARCH_MAX_DEPTH", "128")
    )  # max depth of the tree
    crafted_step_limit: int = int(os.getenv("CRAFTED_STEP_LIMIT", "16"))
    premise_limit: int = 5
    use_crafted_steps: bool = False
    use_quickcheck: bool = False
    llm_address: str
    log_dir: str = "logs"


class TreeSearchProver(ProverProtocol[TreeSearchProverConfig]):
    """Tree-search prover compatible with `ProverProtocol`."""

    def __init__(
        self,
        config: TreeSearchProverConfig = TreeSearchProverConfig(llm_address="http://localhost:8000/api/v1/llm/inference"),
    ):
        self.config: TreeSearchProverConfig = config
        self.logger: Logger = get_proof_logger(self.config.log_dir, "TreeSearchProver")
        self.tree: ProofTree
        self.state2step: dict[str, list[str]] = {}
        self.state2allSuggestedSteps: dict[str, list[str]] = {}
        # Track all scores
        self.state2score: dict[str, float] = {}
        self.selected_states: list[str] = []
        self.total_attempts: int = 0

        self.generate_request_body: dict[str, Any] = {
            "items": [],
            "sampling_params": {
                "temperature": 1.0,
                "max_tokens": 2048,
                "top_p": 0.95,
                "n": self.config.width,
                "logprobs": 1,
            },
            "use_tqdm": True,
        }
        self.logprob_request_body: dict[str, Any] = {
            "state": "",
            "possible_steps": [],
            "limit": self.config.crafted_step_limit,
            "sampling_params": {
                "temperature": 0.0,
                "max_tokens": 1,
                "top_p": 0.95,
                "n": 1,
                "logprobs": 1,
                "prompt_logprobs": 0,
            },
            "use_tqdm": True,
        }
        self.session: requests.Session = requests.Session()
        retry_strategy = Retry(
            total=5,
            read=5,
            connect=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False,
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retry_strategy))

        self.focus_id: int = -1
        self.focus_node: Node | None = None
        self.focus_state: str = ""
        self.focus_proof: list[str] = []

    def _llm_url(self, path: str) -> str:
        """Return a fully-qualified URL for the LLM endpoint.

        Accepts `llm_address` as either `host:port` or `scheme://host:port[/prefix]`.
        """
        addr = self.config.llm_address.rstrip("/")
        if not addr.startswith(("http://", "https://")):
            addr = "http://" + addr
        return f"{addr}/{path.lstrip('/')}"

    @override
    def load_config(self, config: TreeSearchProverConfig) -> None:
        """Replace the current prover configuration and sync dependent values."""
        self.config = config
        self.generate_request_body["sampling_params"]["n"] = config.width
        self.logprob_request_body["limit"] = config.crafted_step_limit

    @override
    def prove(
        self,
        lemma: LemmaProtocol,
        isa_port: int,
        session_root: Path,
        exclude_list: list[str] = [],
        repl_envs: Mapping[str, str | None] = {},
    ) -> list[str]:
        """
        Attempts to find a proof for `lemma` using tree search.

        Owns the Isabelle REPL JAR on `isa_port` for the duration of the call:
        starts the JAR, initializes the theory and steps to the lemma, runs
        tree search, then shuts the JAR down.
        """
        self.logger.info(
            f"{lemma.name} with isa_port {isa_port}: Applying tree search to generate proof..."
        )
        self.tree = ProofTree(lemma)
        self.state2step = {}
        self.state2allSuggestedSteps = {}
        self.state2score = {}
        self.selected_states = []
        self.total_attempts = 0

        path = lemma.getAbsPath(Path(session_root))
        if path is None or not path.exists():
            self.logger.error(
                f"{lemma.name}: Lemma path {path} does not exist (session_root={session_root})."
            )
            return []

        try:
            with IsaRepl(port=isa_port, envs=repl_envs) as isa_repl:
                isa_repl.initialize(
                    str(path), str(session_root), lemma.session, [str(session_root)]
                )
                isa_repl.step_to_target(lemma.statement, exclude_list)

                return self._search(lemma, isa_port, isa_repl)
        except Exception as e:
            self.logger.exception(f"{lemma.name}: prove failed: {e}")
            return []

    def _search(
        self, lemma: LemmaProtocol, isa_port: int, isa_repl: IsaRepl
    ) -> list[str]:
        """Run the tree-search loop against an already-initialized REPL."""
        if not self.start_state(isa_repl):
            self.logger.error(f"{lemma.name}: Failed to initialize the start state.")
            return []
        self.logger.info("Initialized the start state.")

        for current_attempt in tqdm(
            range(self.config.max_attempts),
            desc=f"Tree Search {lemma.name} with port {isa_port}",
        ):
            self.logger.info(
                f"====== Round {current_attempt + 1} / {self.config.max_attempts} ======"
            )
            self.logger.info("Start selecting states...")
            states = self.select_state()
            if len(states) == 0:
                break
            self.generate_request_body["items"] = states
            response = None
            try:
                response = self.session.post(
                    self._llm_url("generate_batch"),
                    json=self.generate_request_body,
                    timeout=(30, 1200),
                )
                response.raise_for_status()
                results = response.json()["outputs"]
            except Exception as e:
                self.logger.exception(f"Failed to get results from prover: {e}")
                if response is not None:
                    self.logger.error(response.text)
                else:
                    self.logger.error("Empty response")
                self.logger.info(f"input: {self.generate_request_body}")
                return []
            self.logger.info(f"Generated {len(results)} states")
            for current_state_idx, (try_res, state) in enumerate(zip(results, states)):
                try:
                    self.focus(state, isa_repl)
                except Exception as e:
                    self.logger.exception(f"Failed to focus state in repl: {e}")
                    self.logger.error(f"The current proof:\n\t{self.focus_proof}")
                    return []
                # `try_res` here is the list of generated step candidates for the current state
                # log the focused state id
                total_tactics = float(len(try_res))
                self.logger.info(
                    f"State Number: {current_state_idx + 1} / {len(states)}"
                )
                self.logger.info(f"Total candidate steps: {int(total_tactics)}")
                self.logger.info(
                    f"The focused state:\n\t{shorten_text(self.focus_state)}"
                )
                self.logger.info(f"The current proof:\n\t{self.focus_proof}")

                hammer_fact_ok, hammer_facts = False, []

                if self.config.use_crafted_steps:
                    hammer_fact_ok, hammer_facts = isa_repl.hammer_facts()
                # self.logger.info(hammer_fact_ok, hammer_facts)
                if self.config.use_quickcheck:
                    try:
                        quickcheck_success, quickcheck_state = (
                            isa_repl.check_by_quickcheck()
                        )
                    except Exception as e:
                        self.logger.exception(f"Failed to check by quickcheck: {e}")
                        self.logger.error(f"The current proof:\n\t{self.focus_proof}")
                        return []
                    if quickcheck_success:
                        self.logger.info(
                            f"⏸️ Quickcheck: Proof State contains a counterexample: {quickcheck_state}"
                        )
                        continue
                    else:
                        self.logger.info(
                            f"▶️ Quickcheck: Proof State Pass the check! {quickcheck_state}"
                        )

                (
                    failed_tactics,
                    duped_path,
                    duped_tactics,
                    duped_states,
                    passed_tactics,
                ) = (0.0, 0.0, 0.0, 0.0, 0.0)

                failed_steps = []
                for step_num, (step, logprob) in enumerate(try_res, start=1):
                    msg = f"Step {step_num:2d} | "
                    msg += f"Tactic : {shorten_text(step, 35):<40} | "
                    try:
                        result = self.get_next_state(step, logprob, isa_repl)
                    except Exception as e:
                        self.logger.exception(f"Failed to apply step: {e}")
                        self.logger.error(f"The current proof:\n\t{self.focus_proof}")
                        return []
                    status, result = result.status, result.result

                    if status == ProofStatus.OK and result and result.state == "":
                        msg += "Result : ✅ success → proof complete"
                        msg += f"\n{lemma.name}: Successfully found a proof:\n"
                        msg += " " + "\n ".join(result.proof_steps)
                        self.logger.info(msg)
                        return result.proof_steps
                    if status in [ProofStatus.FAILED, ProofStatus.NO_MORE_STEPS]:
                        failed_tactics += 1
                        if self.config.use_crafted_steps:
                            failed_steps.append(
                                (step, logprob, result.state if result else "")
                            )
                        msg += f"Result : ❌ Error: {shorten_text(result.state, 40) if result else 'Unknown error':<40}"
                    elif status == ProofStatus.DUPLICATE_STEP:
                        duped_tactics += 1
                        msg += "Result : ⚠️ duplicate tactic"
                    elif status == ProofStatus.DUPLICATE_STATE:
                        duped_states += 1
                        msg += "Result : ⚠️ duplicate state"
                    elif status == ProofStatus.DUPLICATE_PATH:
                        duped_path += 1
                        msg += "Result : ⚠️ duplicate path"
                    else:
                        passed_tactics += 1
                        # Extract subgoal count from state if possible
                        state_text = result.state if result else ""
                        subgoal_match = ""
                        if "subgoal" in state_text.lower():
                            if "1 subgoal" in state_text:
                                subgoal_match = "1 subgoal"
                            else:
                                match = re.search(r"(\d+) subgoals?", state_text)
                                if match:
                                    subgoal_match = f"{match.group(1)} subgoals"
                        msg += f"Result : ✅ success -> {subgoal_match}"
                    # log here
                    self.logger.info(msg)

                summary_msg = (
                    f"Generated steps Results: Passed {passed_tactics}/{total_tactics} tactics; "
                    f"Step Duped {duped_tactics}/{total_tactics} tactics; "
                    f"State Duped {duped_states}/{total_tactics} tactics; "
                    f"Path Duped {duped_path}/{total_tactics} tactics; "
                    f"Failed {failed_tactics}/{total_tactics} tactics "
                )
                self.logger.info(summary_msg)

                if self.config.use_crafted_steps:
                    self.logger.info("Trying crafted steps...")
                    scored_premises = {}
                    for failed_step, logprob, _ in failed_steps:
                        for premise in extract_premises(failed_step):
                            scored_premises.setdefault(premise, []).append(logprob)
                    for premise, logprobs in scored_premises.items():
                        scored_premises[premise] = sum(logprobs) / len(logprobs)
                    scored_premises = list(scored_premises.items())
                    scored_premises.sort(key=lambda x: x[1], reverse=True)
                    selected_premises = scored_premises[: self.config.premise_limit]

                    crafted_steps_for_state: dict[str, float] = {}
                    for failed_step, logprob, _ in failed_steps:
                        if failed_step.startswith("by"):
                            crafted_steps_for_state["apply" + failed_step[2:]] = logprob

                    for combined_step, log_prob in combine_premises(selected_premises):
                        if combined_step not in crafted_steps_for_state:
                            crafted_steps_for_state[combined_step] = log_prob
                        elif crafted_steps_for_state[combined_step] < log_prob:
                            crafted_steps_for_state[combined_step] = log_prob

                    undefined_fact_steps = [
                        t for t in failed_steps if "Undefined fact" in t[2]
                    ]
                    undefined_fact_steps.sort(key=lambda x: x[1], reverse=True)
                    undefined_fact_steps = undefined_fact_steps[
                        : self.config.premise_limit
                    ]

                    for failed_step, logprob, fail_msg in undefined_fact_steps:
                        fact = (fail_msg.split("Undefined fact: ")[1].split(" ")[0])[
                            1:-1
                        ]
                        if hammer_fact_ok:
                            # self.logger.info(fact, failed_step)
                            similarities = [
                                (
                                    hammer_fact,
                                    Levenshtein.distance(fact, hammer_fact),
                                )
                                for hammer_fact in hammer_facts
                            ]
                            similarities.sort(key=lambda x: x[1])
                            similarities = similarities[:7]
                            # self.logger.info(similarities)
                            for hammer_fact, _ in similarities:
                                replaced_step = failed_step.replace(fact, hammer_fact)
                                if (
                                    replaced_step not in crafted_steps_for_state
                                    or crafted_steps_for_state[replaced_step] < logprob
                                ):
                                    crafted_steps_for_state[replaced_step] = logprob
                    # self.logger.info(crafted_steps_for_state)
                    total_crafted_steps = len(crafted_steps_for_state)

                    (
                        failed_tactics,
                        duped_path,
                        duped_tactics,
                        duped_states,
                        passed_tactics,
                    ) = (0.0, 0.0, 0.0, 0.0, 0.0)
                    for step_num, (step, logprob) in enumerate(
                        crafted_steps_for_state.items(), 1
                    ):
                        try:
                            isa_repl.focus_tls(str(self.focus_id))
                        except Exception as e:
                            self.logger.exception(f"Failed to focus state in repl: {e}")
                            self.logger.error(
                                f"The current proof:\n\t{self.focus_proof}"
                            )
                            return []

                        msg = f"Step {step_num:2d} | "
                        msg += f"Tactic : {shorten_text(step, 60):<60} | "
                        try:
                            result = self.get_next_state(step, logprob, isa_repl)
                        except Exception as e:
                            self.logger.exception(f"Failed to apply step: {e}")
                            self.logger.error(
                                f"The current proof:\n\t{self.focus_proof}"
                            )
                            return []
                        status, result = result.status, result.result

                        if status == ProofStatus.OK and result and result.state == "":
                            msg += "Result : ✅ success -> proof complete"
                            self.logger.info(msg)
                            self.logger.info(
                                f"{lemma.name}: Successfully found a proof:"
                            )
                            self.logger.info(
                                " " + "\n ".join([step for step in result.proof_steps])
                            )
                            return result.proof_steps
                        elif status in [
                            ProofStatus.FAILED,
                            ProofStatus.NO_MORE_STEPS,
                        ]:
                            failed_tactics += 1
                            msg += f"Result : ❌ Error: {shorten_text(result.state, 40) if result else 'Unknown error':<40}"
                            continue
                        elif status == ProofStatus.DUPLICATE_STEP:
                            duped_tactics += 1
                            msg += "Result : ⚠️ duplicate tactic"
                            continue
                        elif status == ProofStatus.DUPLICATE_STATE:
                            duped_states += 1
                            msg += "Result : ⚠️ duplicate state"
                            continue
                        elif status == ProofStatus.DUPLICATE_PATH:
                            duped_path += 1
                            msg += "Result : ⚠️ duplicate path"
                            continue
                        else:
                            passed_tactics += 1
                            # Extract subgoal count from state if possible
                            state_text = result.state if result else ""
                            subgoal_match = ""
                            if "subgoal" in state_text.lower():
                                if "1 subgoal" in state_text:
                                    subgoal_match = "1 subgoal"
                                else:
                                    match = re.search(r"(\d+) subgoals?", state_text)
                                    if match:
                                        subgoal_match = f"{match.group(1)} subgoals"
                            msg += f"Result : ✅ success -> {subgoal_match}"

                        self.logger.info(msg)

                    summary_msg = (
                        f"Crafted steps results: Passed {passed_tactics}/{total_crafted_steps} tactics; "
                        f"Step Duped {duped_tactics}/{total_crafted_steps} tactics; "
                        f"State Duped {duped_states}/{total_crafted_steps} tactics; "
                        f"Path Duped {duped_path}/{total_crafted_steps} tactics; "
                        f"Failed {failed_tactics}/{total_crafted_steps} tactics "
                    )
                    self.logger.info(summary_msg)

        # try hammer
        self.logger.info("Trying to hammer each leaf node:")
        leaf_nodes = [node for node in self.tree.all_nodes() if node.is_leaf()]
        nodes_with_score = [(node, node.data.score) for node in leaf_nodes]
        nodes_with_score.sort(key=lambda x: x[1], reverse=True)
        for node, score in tqdm(
            nodes_with_score[: self.config.selected_hammer_num],
            desc=f"Hammering {lemma.name} with port {isa_port}",
        ):
            if node.is_leaf():
                msg = f"Leaf node with score: {score}: \n{node.data.state}"
                msg += f"\nCurrent leaf node: {node.data.proof_steps}"
                self.logger.info(msg)
                try:
                    self.focus(node.data.state, isa_repl)
                    steps, res = isa_repl.auto_prove()
                except Exception as e:
                    self.logger.exception(f"Failed to hammer: {e}")
                    self.logger.error(f"The current proof:\n\t{self.focus_proof}")
                    return []
                if steps != []:
                    self.logger.info(f"Successfully hammered: {res}")
                    new_proof = self.focus_proof + steps
                    self.logger.info(f"{lemma.name}: Successfully found a proof:")
                    self.logger.info(" " + "\n ".join([step for step in new_proof]))
                    return new_proof
                else:
                    self.logger.info(f"Failed to hammer: {res}")
        self.logger.info(
            f"Failed to find a proof after {self.config.max_attempts} attempts with hammer."
        )
        return []

    def start_state(
        self,
        isa_repl: IsaRepl,
    ) -> bool:
        """
        Read the current goal from the REPL and set up the root state.

        The evaluator has already initialised the session and stepped to
        just after the lemma statement; this method reads the goal and
        registers it as the root node of the proof tree.

        Args:
            lemma: The lemma being proved.
            isa_repl: The Isabelle REPL instance (already connected).

        Returns:
            `True` if the goal was read successfully, `False` otherwise.
        """
        state: str = isa_repl.get_msg()
        self.tree.save_node(
            ScoredProofState(proof_steps=[], state=state, score=0.0),
            parent_node=None,
            isa_repl=isa_repl,
        )
        self.state2score[state] = 0.0
        return True

    def select_state(self) -> list[str]:
        """
        Selects the next proof states to explore, based on their scores.

        States that have already been selected in a previous round are
        excluded.

        Returns:
            The list of selected state strings.
        """
        selected = [
            tp[0]
            for tp in sorted(
                [
                    (s, score)
                    for s, score in self.state2score.items()
                    if s not in self.selected_states
                ],
                key=lambda t: t[1],
                reverse=True,
            )[: self.config.selected_states_num]
        ]
        self.selected_states.extend(selected)
        return selected

    def focus(self, state: str, isa_repl: IsaRepl | None = None) -> None:
        """
        Set the current focus state, id, node, and proof.

        When `isa_repl` is provided the REPL TLS is switched to the
        cloned state matching this node's identifier.

        Args:
            state: The state text to focus on.
            isa_repl: If given, `focus_tls` is called on this REPL.
        """
        self.focus_state = state
        self.focus_id = self.tree.state2id[self.focus_state]
        self.focus_node = self.tree[str(self.focus_id)]
        self.focus_proof = self.focus_node.data.proof_steps
        if isa_repl is not None:
            isa_repl.focus_tls(str(self.focus_id))

    def get_next_state(
        self, next_step: str, score_step: float, isa_repl: IsaRepl
    ) -> ProofStateResult:
        """
        Apply a step to the current focused state and record the result.

        Guards against empty/cheating steps, duplicate tactics, duplicate
        proof paths, and duplicate resulting states.  On success the new
        state is scored and saved as a node in the proof tree.

        Args:
            next_step (str): The step string to apply.
            score_step (float): The score of the next step.
            isa_repl (IsaRepl): The Isabelle REPL instance.

        Returns:
            A `ProofStateResult`.
        """
        if not next_step:
            return ProofStateResult(
                status=ProofStatus.FAILED,
                result=ProofState(proof_steps=self.focus_proof, state="empty step"),
            )
        if next_step == "oops" or next_step == "sorry":
            return ProofStateResult(
                status=ProofStatus.FAILED,
                result=ProofState(proof_steps=self.focus_proof, state="cheating"),
            )
        if self.focus_state not in self.state2allSuggestedSteps:
            self.state2allSuggestedSteps[self.focus_state] = []
        else:
            if next_step in self.state2allSuggestedSteps[self.focus_state]:
                return ProofStateResult(status=ProofStatus.DUPLICATE_STEP, result=None)
            self.state2allSuggestedSteps[self.focus_state].append(next_step)

        # 2. Check if this proof path has been explored before.
        new_proof = self.focus_proof + [next_step]
        if "\n".join(new_proof) in self.tree.proof2id:
            return ProofStateResult(status=ProofStatus.DUPLICATE_PATH, result=None)

        # 3. Apply the step in the REPL.
        isa_repl.focus_tls(str(self.focus_id))
        success, new_state = isa_repl.step(next_step)

        if not success:
            return ProofStateResult(
                status=ProofStatus.FAILED,
                result=ProofState(proof_steps=new_proof, state=new_state),
            )

        # 4. Check if the resulting state is a new, unique state.
        if new_state in self.tree.state2id:
            return ProofStateResult(
                status=ProofStatus.DUPLICATE_STATE,
                result=ProofState(proof_steps=new_proof, state=new_state),
            )

        # 5. Save the new state as a new node in the proof tree.
        curr_depth = self.tree.depth(self.focus_node)
        score = (curr_depth * self.state2score[self.focus_state] + score_step) / (
            curr_depth + 1
        )
        if (
            curr_depth < self.config.max_depth
        ):  # only update the score if the depth is less than the max depth
            self.state2score[new_state] = score
        self.tree.save_node(
            ScoredProofState(proof_steps=new_proof, state=new_state, score=score),
            parent_node=self.focus_node,
            isa_repl=isa_repl,
        )

        return ProofStateResult(
            status=ProofStatus.OK,
            result=ProofState(proof_steps=new_proof, state=new_state),
        )

    def rank_steps(self, steps: list[str]):
        """
        Re-rank candidate steps by log-probability via the LLM server.

        Args:
            lemma: The lemma being proved (used for logger context).
            steps: The candidate step strings to rank.

        Returns:
            A list of `(step, logprob)` pairs ordered by the server
            response, or an empty list on failure.
        """
        self.logprob_request_body["state"] = self.focus_state
        self.logprob_request_body["possible_steps"] = steps
        response = None
        try:
            response = self.session.post(
                self._llm_url("compute_logprob"),
                json=self.logprob_request_body,
                timeout=(30, 1200),
            )
            response.raise_for_status()
            results = response.json()["outputs"]
        except Exception as e:
            self.logger.exception(f"Failed to get logprobs: {e}")
            if response is not None:
                self.logger.info(response.text)
            else:
                self.logger.info("Empty response")
            self.logger.info(
                "input: ",
                {
                    "state": shorten_text(self.logprob_request_body["state"]),
                    "possible_steps": self.logprob_request_body["possible_steps"][:10],
                },
            )
            return []
        # self.logger.info(results)
        return results
