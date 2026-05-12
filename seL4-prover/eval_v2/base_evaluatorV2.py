import json
import logging
import os
import sys
from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Any, Callable, Generic, Literal

import ray
import yaml

from data.lemma import Lemma, LemmaProtocol
from eval_v2.lib import BaseEvalConfig, LemmaBuffer, LoggingConfig, ProverCfgT
from provers.lib import ProverProtocol
from utils.repl import IsaRepl

__all__ = [
    "BaseEvaluator",
]


class BaseEvaluator(Generic[ProverCfgT]):
    """Base evaluator for proof generation and verification."""

    # !NOTE: Generic is introduced to declare that the prover configs are consistent between evaluation arguments and prover instances.

    @staticmethod
    def create_logger(
        name: str,
        ctx: Literal["EVAL", "PROVER"],
        log_cfg: LoggingConfig,
        prover: ProverProtocol,
    ) -> Logger:
        """
        Setup and configure a logger for the evaluator or prover.
        """
        logger: Logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.setLevel(getattr(logging, log_cfg.level))
        # If a formatter is provided, use it
        formatter: logging.Formatter = logging.Formatter(
            log_cfg.format.replace("%(ctx)s", ctx)
        )

        # File handler
        if log_cfg.to_file:
            log_file: Path
            if log_cfg.log_file is None:
                # Auto-generate log file name: <ProverName>-MMDD-HHMM.log
                timestamp = datetime.now().strftime("%m%d-%H%M")
                log_file = log_cfg.log_dir / f"{type(prover).__name__}-{timestamp}.log"
            else:
                log_file = log_cfg.log_dir / log_cfg.log_file
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Console handler
        if log_cfg.to_stdout:
            console_handler = logging.StreamHandler(stream=sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        return logger

    @staticmethod
    def get_prover_logger(
        parent_logger: Logger, log_cfg: LoggingConfig, prover: ProverProtocol
    ) -> Logger:
        """
        Create a child logger for the prover.
        """
        prover_logger: Logger = BaseEvaluator.create_logger(
            name=parent_logger.name + ".Prover",
            ctx="PROVER",
            log_cfg=log_cfg,
            prover=prover,
        )
        return prover_logger

    @staticmethod
    def load_checkpoint(
        checkpoint_path: Path,
    ) -> tuple[dict[str, LemmaBuffer], BaseEvalConfig[ProverCfgT] | None]:
        """
        Load prior results and config from a checkpoint file, keyed by solution name.
        """
        res_config: BaseEvalConfig[ProverCfgT] | None = None
        res_data: dict[str, LemmaBuffer] = {}
        with open(checkpoint_path, "r") as f:
            data = json.load(f)
            for key, value in data.items():
                if key == "config":
                    res_config = BaseEvalConfig[ProverCfgT](**value)

                if key.endswith("_results") and isinstance(value, list):
                    source = key[:-8]
                    for item in value:
                        solution = LemmaBuffer(**item)
                        solution.source = source
                        res_data[solution.name] = solution
        return res_data, res_config

    @staticmethod
    def default_check(
        lemma: LemmaProtocol,
        proof: list[str],
        config: BaseEvalConfig[ProverCfgT],
        isa_repl: IsaRepl,
        logger: Logger | None = None,
    ) -> tuple[bool, str]:
        assert proof, "No generated proof!"

        _log: Callable[[str], Any] = logger.debug if logger is not None else print
        session_root = config.session_root
        path = lemma.getAbsPath(Path(session_root))
        if path is None or not path.exists():
            return (False, f"Lemma path {path} does not exist.")

        try:
            isa_repl.initialize(
                str(path), str(session_root), lemma.session, [str(session_root)]
            )
            isa_repl.step_to_target(lemma.statement, config.get_abs_excludes())
            _log(f"lemma: {lemma.name}")
            _log(f"statement: {lemma.statement}")
            _log(f"generated_proof: {proof}")

            ok, msg = isa_repl.execute_steps(proof)
            success = ok and msg == ""

            _log(f"result: {success} with message: {msg}")
            return success, msg
        except Exception as e:
            _log(f"result: {False} with message: {str(e)}")
            return False, str(e)

    def __init__(
        self,
        args: BaseEvalConfig[ProverCfgT],
        prover: ProverProtocol[ProverCfgT],
        tasks: Iterable[Lemma] | None = None,
        checker: Callable[
            [LemmaProtocol, list[str], BaseEvalConfig[ProverCfgT], IsaRepl],
            tuple[bool, str],
        ]
        | None = None,
    ) -> None:
        self.config: BaseEvalConfig[ProverCfgT] = args
        self.prover: ProverProtocol[ProverCfgT] = prover

        # Setup evaluator logger first (log_dir created during LoggingConfig validation)
        self.logger: Logger = self.create_logger(
            name=f"{type(self).__name__}@{type(self.prover).__name__}",
            ctx="EVAL",
            log_cfg=self.config.logging_config,
            prover=self.prover,
        )
        # Setup prover logger with distinct formatting and attach to prover
        self.prover.logger = self.get_prover_logger(
            self.logger, self.config.logging_config, self.prover
        )

        # Evaluation buffers
        self.tasks: list[LemmaBuffer] = []
        self.cache: dict[str, LemmaBuffer] = {}  # Cache of evaluated lemmas

        self._proof_checker: Callable[
            [LemmaProtocol, list[str], BaseEvalConfig[ProverCfgT], IsaRepl],
            tuple[bool, str],
        ] = (
            checker
            if checker is not None
            else lambda lemma, proof_steps, config, isa_repl: self.default_check(
                lemma, proof_steps, config, isa_repl, self.logger
            )
        )

        # Load tasks passed in (if any)
        self.init_tasks(tasks=tasks)

        self.logger.info("BaseEvaluator initialized successfully.")

    def should_be_added(self, lemma: LemmaProtocol) -> bool:
        """
        Check if the lemma should be evaluated.
        By default, a lemma should be evaluated if its name is not already in the cache.
        """
        return lemma.name not in self.cache

    def load_prover_config(self, config: ProverCfgT) -> None:
        """
        Pass the prover config to the prover instance.
        """
        self.prover.load_config(config)

    def init_tasks(
        self,
        checkpoint_path: Path | None = None,
        tasks: Iterable[Lemma] | None = None,
    ) -> None:
        """Load optional checkpoint and initialize tasks buffer."""
        if checkpoint_path is None:
            checkpoint_path = self.config.check_point

        old_results: dict[str, LemmaBuffer] = self.cache
        if checkpoint_path is not None:
            self.logger.info(f"Loading checkpoint from {str(checkpoint_path)}")
            self.cache, config = BaseEvaluator.load_checkpoint(checkpoint_path)
            self.logger.info(f"Loaded {len(self.cache)} items from checkpoint.")
            if config is not None:
                self.logger.info(
                    "Loaded checkpoint config:\n"
                    + yaml.dump(config.model_dump(mode="dict"), indent=2)
                )
                self.config = config
        # Fresh tasks from input
        self.tasks = []
        if tasks is not None:
            self.tasks = [
                LemmaBuffer(**t.model_dump()) for t in tasks if self.should_be_added(t)
            ]
            self.logger.info(f"Loaded {len(self.tasks)} tasks from input.")

        # Re-queue previously seen items that are not in cache anymore
        reeval_tasks = [
            res for res in old_results.values() if self.should_be_added(res)
        ]
        if reeval_tasks:
            self.logger.info(f"Re-evaluate {len(reeval_tasks)} tasks.")
            self.tasks.extend(reeval_tasks)

    def eval(self, do_save: bool = False, save_file: Path | None = None) -> None:
        """Execute the complete evaluation pipeline in parallel via Ray.

        Two phases, both Ray-parallel with at most `server_num` in-flight calls:
          1. generate: prover owns its own JAR per task and produces proof steps.
          2. check: a checker owns its own JAR per task and verifies the proof.
        Each task gets a unique port `start_port + idx`; Ray's concurrency is
        bounded by the in-flight window we maintain ourselves.
        """
        n_tasks = len(self.tasks)
        self.logger.info(f"There are {n_tasks} lemmas to evaluate.")
        if n_tasks == 0:
            return

        if not ray.is_initialized():
            ray.init()

        server_num = self.config.server_num
        start_port = self.config.start_port

        # Extract plain values up-front: Ray serializes closure captures with
        # cloudpickle, and pydantic v2's parameterized generics (e.g.
        # BaseEvalConfig[TreeSearchProverConfig]) don't have a stable
        # module-attribute name, so pickling instances of them fails on the
        # worker. Capturing primitives sidesteps that entirely.
        prover = self.prover
        session_root: Path = self.config.session_root
        abs_excludes: list[str] = self.config.get_abs_excludes()
        repl_envs: dict[str, str | None] = dict(self.config.repl_envs)

        @ray.remote
        def _generate_remote(task: LemmaBuffer, port: int) -> LemmaBuffer:
            task.generated_proof = prover.prove(
                task,
                port,
                session_root=session_root,
                exclude_list=abs_excludes,
                repl_envs=repl_envs,
            )
            return task

        @ray.remote
        def _check_remote(task: LemmaBuffer, port: int) -> LemmaBuffer:
            if not task.generated_proof:
                task.success = False
                task.message = "No generated proof!"
                return task
            try:
                with IsaRepl(port=port, envs=repl_envs) as isa_repl:
                    path = task.getAbsPath(Path(session_root))
                    if path is None or not path.exists():
                        task.success = False
                        task.message = f"Lemma path {path} does not exist."
                        return task
                    isa_repl.initialize(
                        str(path),
                        str(session_root),
                        task.session,
                        [str(session_root)],
                    )
                    isa_repl.step_to_target(task.statement, abs_excludes)
                    ok, msg = isa_repl.execute_steps(task.generated_proof)
                    task.success = bool(ok) and msg == ""
                    task.message = msg
            except Exception as e:
                task.success = False
                task.message = str(e)
            return task

        self.logger.info(f"Phase 1: generating proofs ({server_num} workers)…")
        self.tasks = self._submit_with_concurrency(
            _generate_remote, self.tasks, server_num, start_port
        )

        self.logger.info(f"Phase 2: checking proofs ({server_num} workers)…")
        self.tasks = self._submit_with_concurrency(
            _check_remote, self.tasks, server_num, start_port
        )

        for task in self.tasks:
            self.cache[task.name] = task

        self.logger.info("Saving results...")
        if do_save:
            self.save_results(output_path=save_file)

    def _submit_with_concurrency(
        self,
        remote_fn: Any,
        tasks: list[LemmaBuffer],
        server_num: int,
        port_start: int,
    ) -> list[LemmaBuffer]:
        """Submit `remote_fn(task, port)` over `tasks`, keeping at most
        `server_num` calls in flight. Returns results in task order.
        """
        n = len(tasks)
        results: list[LemmaBuffer | None] = [None] * n
        pending: dict[Any, int] = {}
        next_idx = 0

        while next_idx < n or pending:
            while next_idx < n and len(pending) < server_num:
                fut = remote_fn.remote(tasks[next_idx], port_start + next_idx)
                pending[fut] = next_idx
                next_idx += 1
            if not pending:
                break
            done, _ = ray.wait(list(pending.keys()), num_returns=1)
            for fut in done:
                idx = pending.pop(fut)
                results[idx] = ray.get(fut)

        return [r for r in results if r is not None]

    def dispatch_port(self, offset: int) -> int:
        """Return a port number based on offset."""
        return self.config.start_port + offset

    def save_results(
        self,
        output_path: Path | None = None,
        lemma_list: list[LemmaBuffer] | None = None,
    ) -> None:
        """Save evaluation results to JSON file."""
        self.logger.info("Evaluating results:")
        if lemma_list is None:
            lemma_list = list(self.cache.values())

        sources = sorted({s.source for s in lemma_list if s.source})
        # Use OrderedDict to guarantee key order on older Python versions.
        # Order: 1) <source>_pass 2) config 3) <source>_results
        out_buffer: OrderedDict[str, Any] = OrderedDict()
        for s in sources:
            out_buffer[f"{s}_pass"] = 0
        out_buffer["config"] = self.config.model_dump(mode="json")
        for s in sources:
            out_buffer[f"{s}_results"] = []

        for s in lemma_list:
            if s.success:
                out_buffer[f"{s.source}_pass"] += 1
                out_buffer[f"{s.source}_results"].append(s.model_dump(mode="json"))

        for source in sources:
            total = len([x for x in lemma_list if x.source == source])
            self.logger.info(
                f"\t{source}: {out_buffer[f'{source}_pass']} out of {total} success"
            )

        if output_path is None:
            output_path = self.config.save_path
        if output_path is None:
            self.logger.error("No output path specified, skipping saving results.")
            return
        os.makedirs(output_path.parent, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(out_buffer, f, indent=2)
        self.logger.info(f"Results saved to {output_path}")
