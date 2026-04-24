import os
import subprocess
import tempfile
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


THEORY_TEMPLATE = """
theory Test
    imports {session}.{theory_name}
begin
"""


def test_extract_parent_thms(isa_repl):
    assert L4V_PATH, "L4V_PATH environment variable is not set"

    session = "AInvs"
    theory_name = "KHeap_AI"

    with tempfile.TemporaryDirectory(dir=".") as tmpdir:
        thy_path = os.path.join(tmpdir, "Test.thy")
        with open(thy_path, "w") as f:
            f.write(THEORY_TEMPLATE.format(session=session, theory_name=theory_name))

        ok, msg = split_result(
            isa_repl._initializeRepl(thy_path, L4V_PATH, session, [L4V_PATH])
        )
        assert ok, msg

        ok, msg = split_result(isa_repl._compile())
        assert ok, msg
        print("Compilation result:", msg)

        ok, thms = split_result(isa_repl._extract_thms_defined_in_parent())
        assert ok, thms
        result_lst = thms.split("<\\SEP>")
        print(result_lst[:10])
        print("length of thms:", len(result_lst))

        isa_repl._exit()


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_extract_parent_thms(isa_repl)
        print("test_extract_parent_thms passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
