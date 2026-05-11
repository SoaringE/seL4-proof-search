from pathlib import Path

import pytest
from data.FVELv2Data import FVELv2Data, load_FVELv2
from data.lemma import Lemma
from eval import config
from eval.base_evaluatorV2 import BaseEvaluator, LemmaBuffer
from eval.lib import BaseEvalConfig
from provers.groundtruth_prover import GroundTruthProver, GroundTruthProverConfig


def test_ground_truth_evaluator():
    dataset_path = Path(__file__).parent / "assets/lemma_splits_sample.json"
    dataset: FVELv2Data = load_FVELv2(dataset_path)
    tasks: list[Lemma] = dataset["test"][:1]

    prover_config = GroundTruthProverConfig(
        dataset_path=dataset_path,
    )
    prover = GroundTruthProver(dataset_path=dataset_path)
    evaluator_config = BaseEvalConfig[GroundTruthProverConfig](
        start_port=25533,
        timeout=60,
        prover_config=prover_config,
    )
    print(evaluator_config.model_dump_json(indent=2))

    evaluator = BaseEvaluator[GroundTruthProverConfig](
        args=evaluator_config,
        tasks=tasks,
        prover=prover,
    )

    evaluator.eval()
    assert evaluator.cache[tasks[0].name].success is True


def test_ground_truth_evaluator_all():
    dataset_path = Path(__file__).parent / "assets/lemma_splits_sample.json"
    dataset: FVELv2Data = load_FVELv2(dataset_path)
    tasks: list[Lemma] = dataset["test"]

    prover_config = GroundTruthProverConfig(
        dataset_path=dataset_path,
    )
    prover = GroundTruthProver(dataset_path=dataset_path)
    evaluator_config = BaseEvalConfig[GroundTruthProverConfig](
        start_port=25533,
        timeout=60,
        prover_config=prover_config,
    )

    evaluator = BaseEvaluator[GroundTruthProverConfig](
        args=evaluator_config,
        tasks=tasks,
        prover=prover,
    )

    evaluator.eval()
    for task in tasks:
        assert evaluator.cache[task.name].success is True
    assert len(evaluator.cache) == 3
