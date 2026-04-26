import traceback
from dataclasses import dataclass
from enum import Enum, auto
from typing import List
from collections import defaultdict
from utils.build_proof_steps import extract_premises, combine_premises
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from treelib import Node, Tree  # pyright: ignore[reportPrivateImportUsage]
from urllib3.util.retry import Retry

import eval.config as config
from eval.logger import get_proof_logger
from utils.parser import shorten_text
from utils.repl import IsaRepl

import Levenshtein

@dataclass(frozen=True)
class ProofState:
    proof_steps: List[str]
    state: str


class ProofStatus(Enum):
    OK = auto()
    NO_MORE_STEPS = auto()
    FAILED = auto()  # failed to apply the tactic
    DUPLICATE_TACTIC = auto()
    DUPLICATE_PATH = auto()
    DUPLICATE_STATE = auto()
    SUCCESS = auto()


@dataclass
class ProofStateResult:
    status: ProofStatus
    result: ProofState | None = None


class ProofTree(Tree):
    """
    A specialized tree structure to manage the proof search space.

    This class inherits from treelib.Tree and adds mappings to quickly
    access nodes by their corresponding proof state or proof sequence.
    """

    def __init__(self):
        super().__init__()
        self.proof2id: dict[str, int] = {}
        self.state2id: dict[str, int] = {}
        self.id2node: dict[int, Node] = {}
        self.curr_id: int = 0

    def save_node(
        self, data: dict, parent_node: Node | None, isa_repl: IsaRepl
    ) -> Node:
        """
        Creates, saves, and registers a new node in the proof tree.

        Each node represents a unique proof state. A corresponding thread-local
        state is created in the Isabelle REPL to allow independent exploration.

        Args:
            data: A dictionary containing the 'state' and 'proof' for the new node.
            parent_node: The parent node in the tree. None for the root.
            isa_repl: The Isabelle REPL instance.

        Returns:
            The newly created node.
        """
        node = Node(identifier=str(self.curr_id), data=data)
        state = data.get("state", "")
        proof_steps = data.get("proof", [])
        proof_key = "\n".join(proof_steps)

        self.add_node(node, parent=parent_node)
        # Create a corresponding state in the Isabelle REPL for this node.
        isa_repl.clone_tls(str(self.curr_id))

        self.proof2id[proof_key] = self.curr_id
        self.state2id[state] = self.curr_id
        self.id2node[self.curr_id] = node
        self.curr_id += 1
        return node


class TreeSearcher:

    MAX_ATTEMPTS = config.TREE_SEARCH_MAX_ATTEMPTS
    SELECTED_STATES_NUM = config.TREE_SEARCH_SELECTED_STATES_NUM
    SELECTED_HAMMER_NUM = config.TREE_SEARCH_SELECTED_HAMMER_NUM
    WIDTH = config.TREE_SEARCH_WIDTH
    MAX_DEPTH = config.TREE_SEARCH_MAX_DEPTH
    CRAFTED_STEP_LIMIT = config.CRAFTED_STEP_LIMIT

    def __init__(self, use_crafted_steps=False, use_nitpick=False, log_dir="logs"):
        # Tracks the available tactics for each state to avoid re-trying failures.
        self.state2step: dict[str, list[str]] = {}
        self.state2allSuggestedSteps: dict[str, list[str]] = {}
        # Track all scores
        self.state2score: dict[str, float] = {}
        self.selected_states: list[str] = []  # the states that have been selected
        self.use_crafted_steps = use_crafted_steps
        self.use_nitpick = use_nitpick
        self.log_dir = log_dir

        self.generate_request_body = {
            "items": [],
            "sampling_params": {
                "temperature": 1.0,
                "max_tokens": 2048,
                "top_p": 0.95,
                "n": self.WIDTH,
                "logprobs": 1,
            },
            "use_tqdm": True,
        }
        self.logprob_request_body = {
            "state": "",
            "possible_steps": [],
            "limit": self.CRAFTED_STEP_LIMIT,
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
        self.session = requests.Session()
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

    def search(
        self,
        lemma: dict,
        isa_port: int,
        llm_address: str,
        session_root: str,
        exclude_list: list[str],
    ) -> list[str]:
        """
        Attempts to find a proof for a single lemma using tree search.

        Args:
            lemma: A dictionary with lemma details, including 'name', 'path',
                'session', and 'statement'.
            port: The network port for the Isabelle REPL server.

        Returns:
            A list of tactic strings representing the found proof, or an
            empty list if no proof was found within the attempt limit.
        """
        logger = get_proof_logger(self.log_dir, lemma["name"])
        logger.info(
            f"{lemma['name']} with isa_port {isa_port}: Applying tree search to generate proof..."
        )
        self.tree = ProofTree()
        with IsaRepl(port=isa_port, create_port=True) as isa_repl:
            if not self.start_state(lemma, isa_repl, session_root, exclude_list):
                logger.error(f"{lemma['name']}: Failed to initialize the start state.")
                return []
            logger.info("Initialized the start state.")

            for current_attempt in tqdm(
                range(self.MAX_ATTEMPTS),
                desc=f"Tree Search {lemma['name']} with port {isa_port}",
            ):
                logger.info(
                        f"====== Round {current_attempt + 1} / {self.MAX_ATTEMPTS} ======"
                    )
                logger.info("Start selecting states...")
                states = self.select_state()
                if len(states) == 0:
                    break
                self.generate_request_body["items"] = states
                response = None
                try:
                    response = self.session.post(
                        f"http://{llm_address}/generate_batch",
                        json=self.generate_request_body,
                        timeout=(30, 1200),
                    )
                    response.raise_for_status()
                    results = response.json()["outputs"]
                except Exception as e:
                    traceback.print_exc()
                    if response is not None:
                        print(response.text)
                    else:
                        print("Empty response")
                    print("input: ", self.generate_request_body)
                    logger.error(f"Failed to get the results from the prover: {e}")
                    return []
                logger.info(f"Generated {len(results)} states")
                for current_state, (try_res, state) in enumerate(zip(results, states)):
                    # set the state
                    self.set_state(state)
                    # focus the state
                    try:
                        isa_repl.focus_tls(str(self.focus_id))
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(f"Failed to get the results from the repl: {e}")
                        logger.error(f"The current proof:\n\t{self.focus_proof}")
                        return []
                    # log the focused state id
                    total_tactics = float(len(try_res))
                    logger.info(f"State Number: {current_state + 1} / {len(states)}")
                    logger.info(f"Total candidate tactics: {int(total_tactics)}")
                    logger.info(
                        f"The focused state:\n\t{shorten_text(self.focus_state)}"
                    )
                    logger.info(f"The current proof:\n\t{self.focus_proof}")

                    hammer_fact_ok, hammer_facts = False, []
                    
                    if self.use_crafted_steps:
                        hammer_fact_ok, hammer_facts = isa_repl.hammer_facts()
                    # print(hammer_fact_ok, hammer_facts)
                    if self.use_nitpick:
                        try:
                            nitpick_success, nitpick_state = isa_repl.check_by_quickcheck()
                        except Exception as e:
                            traceback.print_exc()
                            logger.error(f"Failed to get the results from the repl: {e}")
                            logger.error(f"The current proof:\n\t{self.focus_proof}")
                            return []
                        if nitpick_success:
                            logger.info(
                                f"⏸️ Quickcheck: Proof State contains a counterexample: {nitpick_state}"
                            )
                            continue
                        else:
                            logger.info(
                                f"▶️ Quickcheck: Proof State Pass the check! {nitpick_state}"
                            )

                    failed_tactics, duped_path, duped_tactics, duped_states, passed_tactics = (
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    )

                    failed_steps = []
                    for step_num, (tactic, logprob) in enumerate(try_res, 1):
                        msg = f"Step {step_num:2d} | "
                        msg += f"Tactic : {shorten_text(tactic, 35):<40} | "
                        try:
                            result = self.get_next_state(tactic, logprob, isa_repl)
                        except Exception as e:
                            traceback.print_exc()
                            logger.error(f"Failed to get the results from the repl: {e}")
                            logger.error(f"The current proof:\n\t{self.focus_proof}")
                            return []
                        status, result = result.status, result.result

                        if status == ProofStatus.OK and result.state == "":
                            msg += f"Result : ✅ success → proof complete"
                            msg += f"\n{lemma['name']}: Successfully found a proof:\n"
                            msg += " " + "\n ".join(
                                [step for step in result.proof_steps]
                            )
                            logger.info(msg)
                            return result.proof_steps
                        if status in [ProofStatus.FAILED, ProofStatus.NO_MORE_STEPS]:
                            failed_tactics += 1
                            if self.use_crafted_steps:
                                failed_steps.append((tactic, logprob, result.state))
                            msg += f"Result : ❌ Error: {shorten_text(result.state, 40) if result else 'Unknown error':<40}"
                        elif status == ProofStatus.DUPLICATE_TACTIC:
                            duped_tactics += 1
                            msg += f"Result : ⚠️ duplicate tactic"
                        elif status == ProofStatus.DUPLICATE_STATE:
                            duped_states += 1
                            msg += f"Result : ⚠️ duplicate state"
                        elif status == ProofStatus.DUPLICATE_PATH:
                            duped_path += 1
                            msg += f"Result : ⚠️ duplicate path"
                        else:
                            passed_tactics += 1
                            # Extract subgoal count from state if possible
                            state_text = result.state if result else ""
                            subgoal_match = ""
                            if "subgoal" in state_text.lower():
                                if "1 subgoal" in state_text:
                                    subgoal_match = "1 subgoal"
                                else:
                                    import re

                                    match = re.search(r"(\d+) subgoals?", state_text)
                                    if match:
                                        subgoal_match = f"{match.group(1)} subgoals"
                            msg += f"Result : ✅ success → {subgoal_match}"
                        # logger here
                        logger.info(msg)

                    summary_msg = (
                        f"Generated steps Results: Passed {passed_tactics}/{total_tactics} tactics; "
                        f"Tactic Duped {duped_tactics}/{total_tactics} tactics; "
                        f"State Duped {duped_states}/{total_tactics} tactics; "
                        f"Path Duped {duped_path}/{total_tactics} tactics; "
                        f"Failed {failed_tactics}/{total_tactics} tactics "
                    )
                    logger.info(summary_msg)

                    if self.use_crafted_steps:
                        logger.info("Trying crafted steps...")
                        scored_premises = {}
                        for failed_step, logprob, _ in failed_steps:
                            for premise in extract_premises(failed_step):
                                scored_premises.setdefault(premise, []).append(logprob)
                        for premise, logprobs in scored_premises.items():
                            scored_premises[premise] = sum(logprobs) / len(logprobs)
                        scored_premises = list(scored_premises.items())
                        scored_premises.sort(key=lambda x: x[1], reverse=True)
                        selected_premises = scored_premises[: config.PREMISE_LIMIT]
                        
                        crafted_steps_for_state = {}
                        
                        for failed_step, logprob, _ in failed_steps:
                            if failed_step.startswith("by"):
                                crafted_steps_for_state["apply" + failed_step[2:]] = logprob
                        
                        for combined_step, log_prob in combine_premises(selected_premises):
                            if combined_step not in crafted_steps_for_state:
                                crafted_steps_for_state[combined_step] = log_prob
                            elif crafted_steps_for_state[combined_step] < log_prob:
                                crafted_steps_for_state[combined_step] = log_prob
                        
                        undefined_fact_steps = [t for t in failed_steps if "Undefined fact" in t[2]]
                        undefined_fact_steps.sort(key=lambda x: x[1], reverse=True)
                        undefined_fact_steps = undefined_fact_steps[: config.PREMISE_LIMIT]
                        
                        for failed_step, logprob, fail_msg in undefined_fact_steps:
                            fact = (fail_msg.split("Undefined fact: ")[1].split(" ")[0])[1: -1]
                            if hammer_fact_ok:
                                # print(fact, failed_step)
                                similarities = [(hammer_fact, Levenshtein.distance(fact, hammer_fact)) for hammer_fact in hammer_facts]
                                similarities.sort(key=lambda x: x[1])
                                similarities = similarities[: 7]
                                # print(similarities)
                                for hammer_fact, _ in similarities:
                                    replaced_step = failed_step.replace(fact, hammer_fact)
                                    if replaced_step not in crafted_steps_for_state or crafted_steps_for_state[replaced_step] < logprob:
                                        crafted_steps_for_state[replaced_step] = logprob
                        # print(crafted_steps_for_state)
                        total_crafted_steps = len(crafted_steps_for_state)
                        crafted_steps_for_state = list(crafted_steps_for_state.items())

                        failed_tactics, duped_path, duped_tactics, duped_states, passed_tactics = (
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                        )
                        for step_num, (tactic, logprob) in enumerate(
                            crafted_steps_for_state, 1
                        ):
                            # focus the state
                            try:
                                isa_repl.focus_tls(str(self.focus_id))
                            except Exception as e:
                                traceback.print_exc()
                                logger.error(f"Failed to get the results from the repl: {e}")
                                logger.error(f"The current proof:\n\t{self.focus_proof}")
                                return []
                            # log the focused state id
                            msg = f"Step {step_num:2d} | "
                            msg += f"Tactic : {shorten_text(tactic, 60):<60} | "
                            try:
                                result = self.get_next_state(tactic, logprob, isa_repl)
                            except Exception as e:
                                traceback.print_exc()
                                logger.error(f"Failed to get the results from the repl: {e}")
                                logger.error(f"The current proof:\n\t{self.focus_proof}")
                                return []
                            status, result = result.status, result.result

                            if status == ProofStatus.OK and result.state == "":
                                msg += f"Result : ✅ success → proof complete"
                                logger.info(msg)
                                logger.info(
                                    f"{lemma['name']}: Successfully found a proof:"
                                )
                                logger.info(
                                    " "
                                    + "\n ".join([step for step in result.proof_steps])
                                )
                                return result.proof_steps
                            elif status in [
                                ProofStatus.FAILED,
                                ProofStatus.NO_MORE_STEPS,
                            ]:
                                failed_tactics += 1
                                msg += f"Result : ❌ Error: {shorten_text(result.state, 40) if result else 'Unknown error':<40}"
                                continue
                            elif status == ProofStatus.DUPLICATE_TACTIC:
                                duped_tactics += 1
                                msg += f"Result : ⚠️ duplicate tactic"
                                continue
                            elif status == ProofStatus.DUPLICATE_STATE:
                                duped_states += 1
                                msg += f"Result : ⚠️ duplicate state"
                                continue
                            elif status == ProofStatus.DUPLICATE_PATH:
                                duped_path += 1
                                msg += f"Result : ⚠️ duplicate path"
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
                                        import re

                                        match = re.search(
                                            r"(\d+) subgoals?", state_text
                                        )
                                        if match:
                                            subgoal_match = f"{match.group(1)} subgoals"
                                msg += f"Result : ✅ success → {subgoal_match}"

                            logger.info(msg)

                        summary_msg = (
                            f"Crafted steps results: Passed {passed_tactics}/{total_crafted_steps} tactics; "
                            f"Tactic Duped {duped_tactics}/{total_crafted_steps} tactics; "
                            f"State Duped {duped_states}/{total_crafted_steps} tactics; "
                            f"Path Duped {duped_path}/{total_crafted_steps} tactics; "
                            f"Failed {failed_tactics}/{total_crafted_steps} tactics "
                        )
                        logger.info(summary_msg)

            # try hammer
            logger.info("Trying to hammer each leaf node:")
            leaf_nodes = [node for node in self.tree.all_nodes() if node.is_leaf()]
            nodes_with_score = [(node, node.data["score"]) for node in leaf_nodes]
            nodes_with_score.sort(key=lambda x: x[1], reverse=True)
            for node, score in tqdm(
                nodes_with_score[: self.SELECTED_HAMMER_NUM],
                desc=f"Hammering {lemma['name']} with port {isa_port}",
            ):
                if node.is_leaf():
                    msg = f"Leaf node with score: {score}: \n{node.data['state']}"
                    msg += f"\nCurrent leaf node: {node.data['proof']}"
                    logger.info(msg)
                    self.set_state(node.data["state"])
                    try:
                        isa_repl.focus_tls(str(self.focus_id))
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(f"Failed to get the results from the repl: {e}")
                        logger.error(f"The current proof:\n\t{self.focus_proof}")
                        return []
                    try:
                        steps, res = isa_repl.auto_prove()
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(f"Failed to get the results from the repl: {e}")
                        logger.error(f"The current proof:\n\t{self.focus_proof}")
                        return []
                    msg = ""
                    if steps != []:
                        msg += f"Successfully hammered: {res}"
                        logger.info(msg)
                        new_proof = self.focus_proof + steps
                        logger.info(f"{lemma['name']}: Successfully found a proof:")
                        logger.info(" " + "\n ".join([step for step in new_proof]))
                        return new_proof
                    else:
                        msg += f"Failed to hammer: {res}"
                        logger.info(msg)
            logger.info(
                f"Failed to find a proof after {self.MAX_ATTEMPTS} attempts with hammer."
            )
            return []

    def start_state(
        self, lemma: dict, isa_repl: IsaRepl, session_root: str, exclude_list: list[str]
    ) -> bool:
        """
        Initializes the Isabelle REPL to the starting state of a lemma.

        Args:
            lemma: A dictionary containing lemma information.
            isa_repl: The Isabelle REPL instance.

        Returns:
            True if initialization was successful, False otherwise.
        """
        path = lemma["path"]
        try:
            isa_repl.initialize(path, session_root, lemma["session"], [session_root])
            step_success, msg = isa_repl.step_to_target(
                lemma["path"], lemma["statement"], exclude_list
            )
            if not step_success:
                print(f"{lemma['name']}: Failed to step to target lemma: {msg}")
                return False
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"{lemma['name']}: An error occurred during initialization: {e}")
            return False

        # initialize the score of the start state
        data = {"state": msg, "proof": [], "score": 0.0}
        self.tree.save_node(data, parent_node=None, isa_repl=isa_repl)
        self.state2score[msg] = 0.0
        return True

    def select_state(self) -> List[str]:
        """
        Selects the next proof states to explore, based on their scores.
        Returns:
            List[str]: The list of selected states.
        """
        # Sort states by score in descending order, excluding already selected states
        sorted_results = sorted(
            self.state2score.items(), key=lambda x: x[1], reverse=True
        )
        sorted_states = [
            s[0] for s in sorted_results if s[0] not in self.selected_states
        ]
        selected = sorted_states[: self.SELECTED_STATES_NUM]
        self.selected_states.extend(selected)
        return selected

    def set_state(self, state: str) -> None:
        """
        Sets the current focus state, id, node, and proof.
        Args:
            state (str): The state to focus on.
        """
        self.focus_state = state
        self.focus_id = self.tree.state2id[self.focus_state]
        self.focus_node = self.tree.id2node[self.focus_id]
        self.focus_proof = self.focus_node.data["proof"]

    def get_next_state(
        self, next_step: str, score_step: float, isa_repl: IsaRepl
    ) -> ProofStateResult:
        """
        Applies a tactic to the current state and generates a new state.
        Args:
            next_step (str): The tactic to apply.
            score_step (float): The score of the next step.
            isa_repl (IsaRepl): The Isabelle REPL instance.
        Returns:
            ProofStateResult: The result of the tactic application.
        """
        if not next_step or next_step == "":
            return ProofStateResult(
                ProofStatus.FAILED, ProofState(self.focus_proof, "empty step")
            )
        if next_step == "oops" or next_step == "sorry":
            return ProofStateResult(
                ProofStatus.FAILED, ProofState(self.focus_proof, "cheating")
            )
        if self.focus_state not in self.state2allSuggestedSteps:
            self.state2allSuggestedSteps[self.focus_state] = []
        else:
            if next_step in self.state2allSuggestedSteps[self.focus_state]:
                return ProofStateResult(ProofStatus.DUPLICATE_TACTIC, None)
            self.state2allSuggestedSteps[self.focus_state].append(next_step)

        # 2. Check if this proof path has been explored before.
        new_proof = self.focus_proof + [next_step]
        if "\n".join(new_proof) in self.tree.proof2id:
            return ProofStateResult(ProofStatus.DUPLICATE_PATH, None)

        # 3. Apply the tactic in the REPL.
        isa_repl.focus_tls(str(self.focus_id))
        success, new_state = isa_repl.step(next_step)

        if not success:
            return ProofStateResult(
                ProofStatus.FAILED, ProofState(self.focus_proof, new_state)
            )  # "new_state" is an error message here

        # 4. Check if the resulting state is a new, unique state.
        if new_state in self.tree.state2id:
            return ProofStateResult(
                ProofStatus.DUPLICATE_STATE, ProofState(self.focus_proof, new_state)
            )

        # 5. Save the new state as a new node in the proof tree.
        curr_depth = self.tree.depth(self.focus_node)
        score = (curr_depth * self.state2score[self.focus_state] + score_step) / (
            curr_depth + 1
        )
        if (
            curr_depth < self.MAX_DEPTH
        ):  # only update the score if the depth is less than the max depth
            self.state2score[new_state] = score
        data = {"state": new_state, "proof": new_proof, "score": score}
        self.tree.save_node(data, parent_node=self.focus_node, isa_repl=isa_repl)

        return ProofStateResult(ProofStatus.OK, ProofState(new_proof, new_state))

    def rank_steps(self, lemma, llm_address, steps: List[str]):
        logger = get_proof_logger(self.log_dir, lemma["name"])
        self.logprob_request_body["state"] = self.focus_state
        self.logprob_request_body["possible_steps"] = steps
        response = None
        try:
            response = self.session.post(
                f"http://{llm_address}/compute_logprob",
                json=self.logprob_request_body,
                timeout=(30, 1200),
            )
            response.raise_for_status()
            results = response.json()["outputs"]
        except Exception as e:
            import traceback

            traceback.print_exc()
            if response is not None:
                print(response.text)
            else:
                print("Empty response")
            print(
                "input: ",
                {
                    "state": shorten_text(self.logprob_request_body["state"]),
                    "possible_steps": self.logprob_request_body["possible_steps"][:10],
                },
            )
            logger.error(f"Failed to get the results from the prover: {e}")
            return []
        # print(results)
        return results
