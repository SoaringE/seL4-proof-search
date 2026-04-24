import os
import subprocess
import time
from py4j.java_gateway import JavaGateway, GatewayParameters


# Set L4V_PATH to your local l4v directory. See README for details.
L4V_PATH = os.environ.get("L4V_PATH", "")


def run_jar_file(jar_path, port):
    env = os.environ.copy()
    env["ISABELLE_HOME"] = os.path.expanduser("~/verification/isabelle/")
    process = subprocess.Popen(["java", "-jar", jar_path, str(port)], env=env)
    time.sleep(2)
    return process


def isapy_repl(port):
    gateway = JavaGateway(
        gateway_parameters=GatewayParameters(port=port, auto_convert=True)
    )
    return gateway.entry_point


def split_result(result):
    parts = result.split("<\\SEP>", 1)
    if len(parts) != 2:
        raise AssertionError(f"Malformed result: {result}")
    return parts[0] == "True", parts[1]


def test_dependent_thms(isa_repl):
    assert L4V_PATH, "L4V_PATH environment variable is not set"

    theory_file = os.path.abspath("python-test/Test_Dep.thy")

    ok, msg = split_result(
        isa_repl._initializeRepl(theory_file, L4V_PATH, "AInvs", [L4V_PATH])
    )
    assert ok, msg

    ok, msg = split_result(isa_repl._compile())
    assert ok, msg
    print("Compilation result:", msg)

    ok, deps = split_result(isa_repl._extract_thm_deps("get_object_inv"))
    assert ok, deps
    print("Dependent result:", deps)


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_dependent_thms(isa_repl)
        print("test_dependent_thms passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
