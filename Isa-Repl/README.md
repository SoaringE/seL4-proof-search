## Main process
Isa-Repl wraps a Python REPL for Isabelle based on the [py4j] and [scala-isabelle]

## Installation
#### 1. Clone the repository
```
git clone https://github.com/Lizn-zn/Isa-Repl
```

#### 2. Path configuration
```
export ISABELLE_HOME=/path/to/Isabelle2024/
export ISA_REPL_PATH=/path/to/Isa-Repl/target/IsaREPL.jar
```

## Usage

```python
import os
import subprocess
import time
from py4j.java_gateway import JavaGateway, GatewayParameters

# Start the JVM server
process = subprocess.Popen(["java", "-jar", os.getenv("ISA_REPL_PATH"), "25556"])
time.sleep(2)

# Connect to the JVM
gateway = JavaGateway(
    gateway_parameters=GatewayParameters(port=25556, auto_convert=True)
)
isa_repl = gateway.entry_point

# Initialize the REPL with a theory file
theory_file = os.path.abspath("python-test/Test.thy")
isa_repl._initializeRepl(theory_file)

# Compile the theory environment
isa_repl._compile()

# Step through a lemma and its proof
isa_repl._step('lemma fixes x :: int shows "x ^ 3 = x * x * x" \n proof- \n')
isa_repl._step("show ?thesis by (simp add: numeral_eq_Suc) qed")

# Call sledgehammer on the current goal
isa_repl._step('lemma fixes x :: int shows "x ^ 2 = x * x" \n proof- \n')
isa_repl._prove_by_hammer()

# Apply the SMT translation
isa_repl._translate_to_smt()

# Clean up
isa_repl._exit()
process.terminate()
process.wait()
```


## JAR Compilation
The `scala-isabelle` library is fetched from Maven via `build.sbt`, so no local publishing is required.

#### 1. Install [Isabelle], and set the environment variable `ISABELLE_HOME` to indicate the Isabelle installation.
```shell
export ISABELLE_HOME=/path/to/Isabelle2024/
```

#### 2. Install [Scala](https://www.scala-sbt.org/1.x/docs/zh-cn/Installing-sbt-on-Linux.html). Run the following command to check whether the installation is successful.
```shell
./src/test/test.sh
```

#### 3. Compile and create a JAR file at `target/IsaREPL.jar` with all the dependencies included.
```
sbt assembly
```

## Running the Python tests

Each test script in `python-test/` spawns its own JVM (via `subprocess`), runs the test, and terminates the JVM on exit. Run an individual test from the repo root after building the JAR:

```shell
sbt assembly
python python-test/test_repl.py
```

### Tests that require seL4 l4v

The following tests exercise Isabelle sessions from a local [seL4/l4v](https://github.com/seL4/l4v) checkout. Set `L4V_PATH` before running them:

```shell
export L4V_PATH=/path/to/verification/l4v
```

Tests needing `L4V_PATH`:

- `test_dependent_thms.py`
- `test_dependent_thm_with_thy.py`
- `test_extract_parent_thms.py`
- `test_hammer_facts_with_thy.py`
- `test_parse_l4v_theory.py`

If `L4V_PATH` is unset, these tests fail fast with an assertion.
