from pathlib import Path

import pytest
from data.FVELv2Data import FVELv2Data, load_FVELv2
from data.lemma import Lemma
from eval.base_evaluatorV2 import BaseEvaluator
from eval.lib import BaseEvalConfig
from provers.treesearch_prover import TreeSearchProver, TreeSearchProverConfig


def test_treesearch_evaluator():
    dataset_path = Path(__file__).parent / "assets/lemma_splits_sample.json"
    dataset: FVELv2Data = load_FVELv2(dataset_path)
    tasks: list[Lemma] = dataset["test"][:1]

    prover_config = TreeSearchProverConfig(
        max_attempts=3,
        selected_states_num=3,
        width=3,
        max_depth=3,
        llm_address="http://localhost:8000/api/v1/llm/inference",
    )
    prover = TreeSearchProver(config=prover_config)
    evaluator_config = BaseEvalConfig[TreeSearchProverConfig](
        start_port=25533,
        timeout=120,
        prover_config=prover_config,
    )
    print(evaluator_config.model_dump_json(indent=2))

    evaluator = BaseEvaluator[TreeSearchProverConfig](
        args=evaluator_config,
        tasks=tasks,
        prover=prover,
    )

    evaluator.eval()
    assert evaluator.cache[tasks[0].name].success is not None


def test_treesearch_evaluator_all():
    dataset_path = Path(__file__).parent / "assets/lemma_splits_sample.json"
    dataset: FVELv2Data = load_FVELv2(dataset_path)
    tasks: list[Lemma] = dataset["test"]

    prover_config = TreeSearchProverConfig(
        max_attempts=3,
        selected_states_num=3,
        width=3,
        max_depth=3,
        llm_address="http://localhost:8000/api/v1/llm/inference",
    )
    prover = TreeSearchProver(config=prover_config)
    evaluator_config = BaseEvalConfig[TreeSearchProverConfig](
        start_port=25533,
        timeout=120,
        prover_config=prover_config,
    )

    evaluator = BaseEvaluator[TreeSearchProverConfig](
        args=evaluator_config,
        tasks=tasks,
        prover=prover,
    )

    evaluator.eval()
    assert len(evaluator.cache) == 3
    assert all(evaluator.cache[task.name].success is not None for task in tasks)
