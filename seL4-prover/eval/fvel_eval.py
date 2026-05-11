from __future__ import annotations

from typing import Any, Dict, List

import ray

from eval.base_evaluator import BaseEvaluator
from eval.config import parse_args


class FvelEvaluator(BaseEvaluator):
    def __init__(self, args: Any) -> None:
        super().__init__(args)

    def build_generate_method(self) -> None:
        @ray.remote
        def _generate_single_proof(lemma: Dict[str, Any], port: int) -> List[str]:
            """
            Generate a proof for a single lemma using the specified proof type.

            Args:
                lemma (dict): The lemma information.
                port (int): The port for the Isabelle REPL.

            Returns:
                list[str]: The generated proof steps.
            """
            print("warning: FvelEvaluator is not implemented")
            return [c for c in lemma["proof"] if c not in lemma["statement"]]

        self._generate_single_proof = _generate_single_proof


if __name__ == "__main__":
    args = parse_args()
    evaluator = FvelEvaluator(args)
    evaluator.build_generate_method()
    evaluator.build_check_method()
    evaluator.eval()
