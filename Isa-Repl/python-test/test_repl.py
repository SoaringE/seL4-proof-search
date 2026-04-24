import os
import subprocess
import time
from py4j.java_gateway import JavaGateway, GatewayParameters


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


def test_repl(isa_repl):
    theory_file = os.path.abspath("python-test/Test.thy")

    ok, msg = split_result(isa_repl._initializeRepl(theory_file))
    assert ok, msg

    ok, msg = split_result(isa_repl._compile())
    assert ok, msg

    theorem = "lemma fixes x :: int shows \"x ^ 3 = x * x * x\" \n proof- \n"
    ok, msg = split_result(isa_repl._step(theorem))
    assert ok, msg
    assert "1. x ^ 3 = x * x * x" in msg

    ok, msg = split_result(isa_repl._step("show ?thesis by (simp add: numeral_eq_Suc)"))
    assert ok, msg
    assert "No subgoals!" in msg


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_repl(isa_repl)
        print("test_repl passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
