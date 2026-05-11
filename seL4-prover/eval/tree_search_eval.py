from __future__ import annotations
from typing import Any, Dict, List
from eval.base_evaluator import BaseEvaluator
from eval.tree_searcher import TreeSearcher
from eval.config import parse_args
import ray


class TreeSearchEvaluator(BaseEvaluator):
    """
    A theorem prover that uses a random tree search strategy.

    This prover explores different proof paths by randomly selecting proof states
    and applying random tactics. It is designed as a baseline and can be extended
    to use a learned model for smarter tactic selection.
    """

    def __init__(self, args: Any) -> None:
        super().__init__(args)
        ray.init()
        print(ray.cluster_resources())
        self.max_repl_memory = (
            ray.cluster_resources()["memory"] * 0.95 / self.server_num
        )
        print(f"max_repl_memory: {self.max_repl_memory}")

    def build_generate_method(self) -> None:
        @ray.remote(memory=self.max_repl_memory)
        def _generate_single_proof(
            lemma: Dict[str, Any],
            port: int,
            address: str = self.llm_address,
            session_root: str = self.session_root,
            exclude_list: List[str] = self.exclude_list,
        ) -> List[str]:
            searcher = TreeSearcher(
                self.use_crafted_steps, self.use_nitpick, self.log_dir
            )
            proof = searcher.search(lemma, port, address, session_root, exclude_list)
            return proof

        self._generate_single_proof = _generate_single_proof


if __name__ == "__main__":
    args = parse_args()
    evaluator = TreeSearchEvaluator(args)
    evaluator.build_generate_method()
    evaluator.build_check_method()
    evaluator.eval()
