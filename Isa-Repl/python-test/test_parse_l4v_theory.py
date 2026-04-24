import os
import re
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


def replaced_by_sorry(isar_commands):
    keywords = [
        "apply", "supply", "subgoal", "using", "unfolding",
        "proof", "qed", "done",
        "{", "}", "next", "note",
        "let", "write", "fix", "assume", "then",
        "have", "show",
        "from", "with",
        "also", "finally", "moreover", "ultimately",
        "presume", "define", "consider", "obtain", "case",
        "typ", "term", "prop", "thm", "print_statement",
        "apply_end", "defer", "prefer",
        "back", "oops", "hence", "thus", ".", "..", "and",
        "include", "including", "is", "interpret",
        "by",
    ]
    depth = 0
    in_notepad = False
    notepad_depth = -1
    replaced_commands = []
    i, length = 0, len(isar_commands)
    while i < length:
        if isar_commands[i].endswith("begin"):
            depth += 1
        if isar_commands[i].strip() == "end":
            if depth == notepad_depth and in_notepad:
                in_notepad = False
            depth -= 1
        if isar_commands[i].startswith("notepad"):
            in_notepad = not in_notepad
            notepad_depth = depth
        if not in_notepad:
            if any(re.split(r"[ ()]+", isar_commands[i].strip())[0] == kw for kw in keywords):
                while i < length and any(
                    re.split(r"[ ()\n]+", isar_commands[i].strip())[0] == kw for kw in keywords
                ):
                    i += 1
                replaced_commands.append("sorry")
            else:
                replaced_commands.append(isar_commands[i])
                i += 1
        else:
            replaced_commands.append(isar_commands[i])
            i += 1
    return replaced_commands


def is_comment(isar_command):
    stripped = isar_command.strip()
    return stripped.startswith("(*") and stripped.endswith("*)")


def delete_comments(isar_commands):
    return [c for c in isar_commands if not is_comment(c)]


def test_parse_l4v_theory(isa_repl):
    assert L4V_PATH, "L4V_PATH environment variable is not set"

    theory_file = os.path.abspath(
        os.path.join(L4V_PATH, "proof/refine/ARM/CSpace_R.thy")
    )

    ok, msg = split_result(
        isa_repl._initializeRepl(theory_file, L4V_PATH, "Refine", [L4V_PATH])
    )
    assert ok, msg

    with open(theory_file, "r", encoding="utf-8") as f:
        content = f.read()

    steps = isa_repl._parse_to_steps(content).split("<\\SEP>")
    steps = delete_comments(steps)
    steps = replaced_by_sorry(steps)

    plain = False
    if plain:
        for i, step in enumerate(steps):
            print(i, step, "\n", isa_repl._step(steps[i]))
    else:
        i, unprocessed = 1, ""
        while i < len(steps):
            result = isa_repl._step(unprocessed + steps[i])
            if "False<\\SEP>" in result:
                unprocessed += steps[i] + "\n"
            else:
                unprocessed = ""
            i += 1


if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25556
    jvm_process = run_jar_file(jar_path, port)

    try:
        isa_repl = isapy_repl(port)
        test_parse_l4v_theory(isa_repl)
        print("test_parse_l4v_theory passed")
    finally:
        jvm_process.terminate()
        jvm_process.wait()
