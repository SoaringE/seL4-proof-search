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


def test_find_theorems(isa_repl):
    theory_file = os.path.abspath("python-test/Test.thy")

    ok, msg = split_result(isa_repl._initializeRepl(theory_file))
    assert ok, msg

    ok, msg = split_result(isa_repl._compile())
    assert ok, msg

    # Similar to: find_theorems "obj_at _ _" "set_thread_state"
    # Here we use a HOL query that should reliably return matches.
    query_patterns = ["(_::nat) <= _"]
    raw = isa_repl._find_theorems(query_patterns)
    ok, output = split_result(raw)

    print("find_theorems raw output:\n", output)
    assert ok, output
    assert "find_theorems" in output
    assert "theorem(s)" in output


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_find_theorems(isa_repl)
        print("test_find_theorems passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
