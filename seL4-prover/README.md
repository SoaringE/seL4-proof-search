# seL4-prover

## Installation
#### 1. Dataset
Download `FVELer.zip` from [FVELER/FVELerExtraction](https://github.com/FVELER/FVELerExtraction/blob/main/FVELer.zip) into `./datasets/` and unzip it:

```shell
cd datasets
# download FVELer.zip from the URL above into this directory, then:
unzip FVELer.zip
```

#### 2. Isabelle REPL
Isa-Repl lives in the sibling directory [../Isa-Repl](../Isa-Repl/). Follow [../Isa-Repl/README.md](../Isa-Repl/README.md) to build the JAR — `sbt assembly` produces `target/IsaREPL.jar`, which must be pointed to by the `ISA_REPL_PATH` environment variable.

#### 3. Build l4v

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
   2. We have bump to sel4-13.0.0, please checkout to `seL4-13.0.0` for the best compability.
   3. For the error `No such file: "/path/to/verification/l4v/Main.thy"`, remove the symbolic link of Isabelle in l4v folder.

## Run in Docker
#### 1. Start the docker
```shell
sudo sudo docker run --shm-size=10.24gb --network host -it lizenan1995/sel4-test:latest
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

