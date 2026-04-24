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


def test_extract_goals(isa_repl):
    theory_file = os.path.abspath("python-test/Test.thy")

    ok, msg = split_result(isa_repl._initializeRepl(theory_file))
    assert ok, msg

    ok, msg = split_result(isa_repl._compile())
    assert ok, msg

    isa_repl._step(r"""
      theorem example5: "\<not>(\<forall>(n::nat). f (f n) = n + 1987)"
        proof
          assume A: "\<forall> n. f (f n) = n + 1987"
          have inj_f: "inj f"
          proof (rule inj_onI)
            fix m n
            assume "f m = f n"
            have "f (f m) = f (f n)"
              using \<open>f m = f n\<close> by force
            from A
            have "f (f m) = m + 1987" and "f (f n) = n + 1987"
              by auto
    """)
    print(isa_repl._proof_finished())


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_extract_goals(isa_repl)
        print("test_extract_goals passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
