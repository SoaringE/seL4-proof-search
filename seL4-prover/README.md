# seL4-prover

## Environment Setup

### System Requirements
- Python >=3.12
- [Isabelle2024](https://isabelle.in.tum.de/website-Isabelle2024/index.html)
- Java >= 17 (for IsaREPL)

### 1. Dataset

The dataset is FVELer, available in two compatible variants depending on which evaluation workflow you use:

**Original FVELer** — for the V1 workflow (`eval/tree_search_eval.py`)

Three separate JSON files (`small_test.json`, `medium_test.json`, `medium_train.json`). Download `FVELer.zip` from [FVELER/FVELerExtraction](https://github.com/FVELER/FVELerExtraction/blob/main/FVELer.zip) into `./datasets/` and unzip it:

```shell
cd datasets
# download FVELer.zip from the URL above into this directory, then:
unzip FVELer.zip
```

**Enhanced FVELer** — for the V2 workflow (`eval_v2/main.py`)

A single JSON file (`dataset_lemma_split.json`) that includes each lemma's path and its split classification (train / test / other). All data needed for evaluation lives in one file instead of three. Download `FVELer_EX.zip` from the [v1.0.0 release](https://github.com/SoaringE/seL4-proof-search/releases/tag/v1.0.0) and extract `dataset_lemma_split.json` from it.

The script that produces the enhanced dataset from the original is [utils/retrofitFVEL.py](utils/retrofitFVEL.py). For example, it fills the `path` field of each lemma so that the evaluator can locate the theory file directly.

### 2. Isabelle REPL

You have two options:

**Option A — use the pre-compiled JAR.** Download `IsaREPL.jar` from the [v1.0.0 release](https://github.com/SoaringE/seL4-proof-search/releases/tag/v1.0.0) and point `ISA_REPL_PATH` at it in your `.env` file:

```env
ISA_REPL_PATH=/path/to/IsaREPL.jar
```

**Option B — build from source.** Isa-Repl lives in the sibling directory [../Isa-Repl](../Isa-Repl/). Follow [../Isa-Repl/README.md](../Isa-Repl/README.md) — `sbt assembly` produces `target/IsaREPL.jar`. Then set `ISA_REPL_PATH` to its absolute path.

### 3. l4v

Follow the instructions in the [seL4 l4v repository](https://github.com/seL4/l4v) to install the required packages.

- Install pip package
   ```
   pip install --user sel4-deps
   ```

- Install l4v
   ```shell
   mkdir verification
   cd verification
   repo init -u https://git@github.com/seL4/verification-manifest.git
   repo sync
   ```

- Compile Isabelle
   ```shell
   cd l4v
   mkdir -p ~/.isabelle/etc
   cp -i misc/etc/settings ~/.isabelle/etc/settings
   ./isabelle/bin/isabelle components -a
   ./isabelle/bin/isabelle jedit -bf
   ./isabelle/bin/isabelle build -bv HOL
   ```

- Compile l4v
   ```
   L4V_ARCH=ARM ./run_tests
   ```

**Note**:
   1. The `repo` package is not available in the Ubuntu apt-get repository. To install it manually, run the following commands:
      ```shell
      curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
      chmod a+x ~/bin/repo
      export PATH=~/bin:$PATH
      ```
   2. We have bumped to sel4-13.0.0, please checkout to `seL4-13.0.0` for the best compatibility.
   3. For the error `No such file: "/path/to/verification/l4v/Main.thy"`, remove the symbolic link of Isabelle in the l4v folder.

### 4. Python Environment

Set up the Python environment as specified in [pyproject.toml](pyproject.toml).

## Evaluation

The repository ships two evaluation workflows: a V1 path driven by command-line arguments, and a V2 path driven by Pydantic-typed config classes.

### V1 Workflow — `eval/tree_search_eval.py`

Run on the small test set:

```shell
python -u eval/tree_search_eval.py \
    --test \
    --test_path datasets/small_test.json \
    --server_num 9 \
    --save_path output/tree_search_eval/small_test.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080 \
    --log_dir logs/temp
```

Drop `--test` to evaluate the full dataset (`datasets/medium_test.json`).

Common arguments:
- `--server_num`: number of Isabelle server instances
- `--start_port`: starting port for servers (default: 25555)
- `--llm_address`: LLM server address (`host:port`)
- `--timeout`: per-proof timeout in seconds (default: 600)
- `--crafted_steps`, `--nitpick`: optional features

Run `python eval/tree_search_eval.py --help` for the full argument list.

### V2 Workflow — `eval_v2/main.py`

V2 runs on Ray, so start a Ray head first (same as V1):

```shell
ray start --head --port=6379 --dashboard-host='0.0.0.0'
```

Update the configuration section in [eval_v2/main.py](eval_v2/main.py) for parameters like dataset and output file paths. Critical configurations to pay attention to:
- `DATASET_PATH`: path to the enhanced FVELer dataset (file shipped as `dataset_lemma_split_EX.json` in `FVELer_EX.zip`; rename or point `DATASET_PATH` at the `_EX` file directly)
- `PROVER_CONFIG.llm_address`: LLM inference server address. Accepts either `host:port` or `scheme://host:port[/prefix]`.
- `EVALUATION_CONFIG.session_root`: absolute path to the l4v code base
- `EVALUATION_CONFIG.server_num`: number of parallel Ray workers (each owns one Isabelle JAR on a port starting at `start_port`). Default `1`.

Then run from the repo root:

```shell
python -m eval_v2.main
```

For details on the parameters, see:
- [`eval_v2.lib.BaseEvalConfig`](eval_v2/lib.py) for the evaluator configuration
- [`provers.treesearch_prover.TreeSearchProverConfig`](provers/treesearch_prover.py) for the prover configuration

## Run in Docker
#### 1. Start the docker
```shell
sudo docker run --shm-size=10.24gb --network host -it soaringe/sel4-test:latest
```
#### 2. Start Ray in docker
```shell
source activate test && ray start --head --port=6379 --dashboard-host='0.0.0.0' # in head node
source activate test && ray start --address='head_node:6379' # in worker node
```
#### 3. Start the proving
```shell
python -u eval/tree_search_eval.py \
    --test \
    --test_path datasets/small_test.json \
    --server_num 64 \
    --save_path output/tree_search_eval/medium_test_res.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080 \
    > output/output.txt 2>&1
```
