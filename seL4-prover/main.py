from pathlib import Path

from data.FVELv2Data import FVELv2Data, load_FVELv2
from data.lemma import Lemma
from eval.base_evaluatorV2 import BaseEvaluator
from eval.lib import BaseEvalConfig
from provers.treesearch_prover import TreeSearchProver, TreeSearchProverConfig

###########################################################################
# Configurations for evaluation - adjust these as needed

## Step 1: Set path to your dataset.
DATASET_PATH = Path("datasets/dataset_lemma_split.json")

## Step 2: Configure the prover settings.
PROVER_CONFIG = TreeSearchProverConfig(
    max_attempts = 128,
    selected_states_num = 5,
    selected_hammer_num = 128,
    width = 128,
    max_depth = 128,
    crafted_step_limit = 16,
    premise_limit = 5,
    use_crafted_steps = True,
    use_quickcheck = True,
    llm_address = "http://localhost:8000/api/v1/llm/inference", #!NOTE: Update this with the actual address of your LLM inference server.
    log_dir = "logs"
)

## Step 3: Configure the evaluation settings and pass the previously defined prover config.
EVALUATION_CONFIG = BaseEvalConfig[TreeSearchProverConfig](
    start_port=25533,
    timeout=120,
    session_root=Path("l4v"),  #!NOTE: Update this to your actual l4v path.
    exclude_list=[
        "spec/take-grant/Example2.thy",
        "lib/EVTutorial/EquivValidTutorial.thy",
        "lib/test/Apply_Debug_Test.thy",
        "lib/test/FastMap_Test.thy",
        "lib/test/RangeMap_Test.thy",
        "lib/test/FP_Eval_Tests.thy",
        "lib/test/CorresK_Test.thy",
    ],
    repl_envs={"L4V_ARCH": "ARM"},
    check_point=None,
    save_path=Path("output/eval_results.json"),
    prover_config=PROVER_CONFIG,  #!NOTE: Make sure to pass the prover config here.
    # logging_config can be customized as needed.
)

# Configurations end here
###########################################################################


if __name__ == "__main__":
    dataset: FVELv2Data = load_FVELv2(DATASET_PATH)
    tasks: list[Lemma] = dataset["test"]

    prover = TreeSearchProver(config=PROVER_CONFIG)
    print(EVALUATION_CONFIG.model_dump_json(indent=2))

    evaluator = BaseEvaluator[TreeSearchProverConfig](
        args=EVALUATION_CONFIG,
        tasks=tasks,
        prover=prover,
    )
    evaluator.eval(do_save=True)