# seL4 Theorem Prover

This is the official repository for our OSDI'26 paper [*Neuro-Symbolic Proof Generation for Scaling Systems Software Verification*](https://arxiv.org/abs/2603.19715).

A theorem proving system for seL4 verification built on top of Isa-Repl, providing automated proof generation and verification capabilities for seL4 lemmas.

## Overview

This repository contains two main components:

1. **Isa-Repl**: A Python REPL wrapper for Isabelle theorem prover, enabling programmatic interaction with Isabelle through Py4J and scala-isabelle.
2. **seL4-prover**: A theorem prover specifically designed for seL4 verification, featuring tree search algorithms and LLM-assisted proof generation.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Isa-Repl Installation](#isa-repl-installation)
- [Isa-Repl Usage](#isa-repl-usage)
- [seL4-prover Installation](#sel4-prover-installation)
- [seL4-prover Configuration](#sel4-prover-configuration)
- [Running seL4-prover](#running-sel4-prover)
- [Docker Setup](#docker-setup)
- [Project Structure](#project-structure)

---

## Prerequisites

Before installation, ensure you have the following:

- **Isabelle 2024**: Download and install from [Isabelle website](https://isabelle.in.tum.de/)
- **Scala and sbt**: Required for building Isa-Repl
- **Python 3.10+**: Required for seL4-prover
- **Java**: Required for running the JAR file
- **seL4 l4v**: The seL4 verification framework

---

## Isa-Repl Installation

Isa-Repl provides a Python interface to Isabelle theorem prover.


### Step 1: Set Environment Variables

```bash
export ISABELLE_HOME=/path/to/Isabelle2024/
export ISA_REPL_PATH=/path/to/Isa-Repl/target/IsaREPL.jar
```

### Step 2: Build the JAR File

```bash
sbt assembly
```

This creates `target/IsaREPL.jar` with all dependencies included.

### Step 3: Test the Installation

Each test script under `Isa-Repl/python-test/` spawns its own JVM and cleans up on exit. Run from the `Isa-Repl/` directory so the relative paths to `Test.thy` and the JAR resolve:

```bash
cd Isa-Repl
python python-test/test_repl.py
```

---


For detailed API documentation, see [API_Documentation.md](Isa-Repl/API_Documentation.md).

---

## seL4-prover Installation

### Step 1: Install Python Dependencies

```bash
cd seL4-prover
pip install -e .
```

### Step 2: Prepare the Dataset

Download `FVELer.zip` from [FVELER/FVELerExtraction](https://github.com/FVELER/FVELerExtraction/blob/main/FVELer.zip) into `seL4-prover/datasets/` and unzip it there:

```bash
cd seL4-prover/datasets
# download FVELer.zip from the URL above into this directory, then:
unzip FVELer.zip
```

### Step 3: Install Isa-Repl

The seL4-prover requires Isa-Repl to be installed. Follow the [Isa-Repl Installation](#isa-repl-installation) steps above.

**Important**: Ensure the `IsaREPL.jar` file is built and the `ISA_REPL_PATH` environment variable is set.

### Step 4: Build seL4 l4v

Follow the instructions in the [seL4 l4v repository](https://github.com/seL4/l4v) to install the required packages.

#### Install seL4 Dependencies

```bash
pip install --user sel4-deps
```

#### Install l4v

```bash
mkdir verification
cd verification
repo init -u https://git@github.com/seL4/verification-manifest.git
repo sync
```

**Note**: The `repo` package is not available in Ubuntu apt-get. Install it manually:

```bash
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
chmod a+x ~/bin/repo
export PATH=~/bin:$PATH
```

#### Compile Isabelle

```bash
cd l4v
mkdir -p ~/.isabelle/etc
cp -i misc/etc/settings ~/.isabelle/etc/settings
./isabelle/bin/isabelle components -a
./isabelle/bin/isabelle jedit -bf
./isabelle/bin/isabelle build -bv HOL
```

#### Compile l4v

```bash
export L4V_ARCH=ARM
./run_tests
```

**Important Notes**:

1. We recommend using `seL4-13.0.0` for best compatibility.
2. If you encounter the error `No such file: "/path/to/verification/l4v/Main.thy"`, remove the symbolic link of Isabelle in the l4v folder.

---

## seL4-prover Configuration

### Environment Variables

Set the following environment variables:

```bash
export L4V_PATH=/path/to/verification/l4v
export ISA_REPL_PATH=/path/to/Isa-Repl/target/IsaREPL.jar
export SESSION_ROOT=$L4V_PATH
```


### Configuration File

Reference .env.template to create a .env file, check and modify it and `eval/config.py` if needed to adjust:

- Server configuration
- Timeout settings
- Path configurations
- Search parameters

---

## Running seL4-prover

### Basic Evaluation

```bash
cd seL4-prover
python -u eval/tree_search_eval.py \
    --test \
    --test_path datasets/small_test.json \
    --server_num 9 \
    --save_path output/tree_search_eval/small_test.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080 \
    --log_dir logs/temp
```

### Command Line Arguments

- `--test`: Run on test dataset only
- `--test_path`: Path to test JSON file
- `--server_num`: Number of Isabelle server instances
- `--start_port`: Starting port for servers (default: 25555)
- `--save_path`: Path to save results
- `--llm_address`: Address of LLM server (format: `host:port`)
- `--timeout`: Timeout for each proof check in seconds (default: 600)
- `--log_dir`: Directory for log files
- `--crafted_steps`: Use crafted proof steps
- `--nitpick`: Enable nitpick and quickcheck checking

### Full Dataset Evaluation

Remove the `--test` flag to run on the full dataset:

```bash
python -u eval/tree_search_eval.py \
    --test_path datasets/medium_test.json \
    --server_num 64 \
    --save_path output/tree_search_eval/medium_test_res.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080
```

---

## Docker Setup

### Step 1: Start Docker Container

```bash
docker run --shm-size=10.24gb --network host -it [DOCKER_IMAGE]:latest
```

### Step 2: Start Ray Cluster

**On head node:**

```bash
source activate test
ray start --head --port=6379 --dashboard-host='0.0.0.0'
```

**On worker nodes:**

```bash
source activate test
ray start --address='head_node:6379'
```

### Step 3: Run Evaluation

```bash
python -u eval/tree_search_eval.py \
    --test \
    --test_path datasets/small_test.json \
    --server_num 64 \
    --save_path output/tree_search_eval/medium_test_res.json \
    --llm_address [LLM_SERVER_ADDRESS]:8080 \
    > output/output.txt 2>&1
```

---

## Project Structure

```
.
├── Isa-Repl/                    # Isabelle REPL wrapper
│   ├── src/
│   │   ├── main/
│   │   │   ├── scala/          # Scala source code
│   │   │   └── resources/      # Isabelle ML files
│   ├── build.sbt               # Build configuration
│   └── API_Documentation.md    # API reference
│
├── seL4-prover/                 # seL4 theorem prover
│   ├── eval/                   # Evaluation scripts
│   │   ├── tree_search_eval.py # Main evaluation script
│   │   ├── tree_searcher.py    # Tree search implementation
│   │   └── config.py           # Configuration
│   ├── datasets/               # Dataset files
│   ├── provers/                # Prover implementations
│   ├── utils/                  # Utility functions
│   └── run.sh                  # Example run script
│
└── README.md                    # This file
```

---

## Implementation Details

### Base Evaluator

The `BaseEvaluator` class in `eval/base_evaluator.py` provides core functionality:

- Starting and shutting down Isabelle servers
- Loading datasets
- Dispatching worker functions
- Error handling and recovery
- Saving results

### Tree Search Prover

The `TreeSearcher` class implements a tree search algorithm for proof generation:

- Explores multiple proof paths
- Uses LLM for tactic generation
- Supports crafted proof steps
- Integrates with Isabelle REPL

### Extending the System

To implement custom proof strategies, extend the `BaseEvaluator` class and override the `evaluate_single_lemma` method. See `eval/tree_search_eval.py` for an example implementation.

---

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 25555+ are available for Isabelle servers or modify it to a suitable value by --start_port arg
2. **Memory issues**: Increase JVM heap size or reduce `server_num`
3. **Isabelle errors**: Verify `ISABELLE_HOME` and `L4V_PATH` are correctly set
4. **LLM connection**: Check `--llm_address` format and network connectivity

### Getting Help

For issues related to:

- **Isa-Repl**: Check [API_Documentation.md](Isa-Repl/API_Documentation.md)
- **seL4 l4v**: Refer to [seL4 documentation](https://docs.sel4.systems/)
- **Isabelle**: See [Isabelle documentation](https://isabelle.in.tum.de/documentation.html)

---

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for the full text.

Copyright (c) 2025-2026 Baoding He, Zenan Li, Wei Sun.

## Citation

[Neuro-Symbolic Proof Generation for Scaling Systems Software Verification](https://arxiv.org/abs/2603.19715)
USENIX Symposium on Operating Systems Design and Implementation (OSDI), 2026
Baoding He\*, Zenan Li\*, Wei Sun, Yuan Yao†, Taolue Chen, Xiaoxing Ma†, Zhendong Su
(\* equal contribution; † equal advising)

```bibtex
@inproceedings{he2026neurosymbolic,
  title={Neuro-Symbolic Proof Generation for Scaling Systems Software Verification},
  author={He, Baoding and Li, Zenan and Sun, Wei and Yao, Yuan and Chen, Taolue and Ma, Xiaoxing and Su, Zhendong},
  booktitle={USENIX Symposium on Operating Systems Design and Implementation (OSDI)},
  year={2026}
}
```