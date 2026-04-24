import re
from typing import List


def is_comment(isar_command: str):
    stripped = isar_command.strip()
    return stripped.startswith("(*") and stripped.endswith("*)")


def delete_comments(isar_commands: list[str]):
    result = []
    for command in isar_commands:
        if is_comment(command):
            continue
        if is_unclosed_comment(command):
            result.append(delete_unclosed_comments(command))
            continue
        result.append(command)
    return result


def is_unclosed_comment(isar_command: str):
    stripped = isar_command.strip()
    return "(*" in stripped and "*)" not in stripped


def delete_unclosed_comments(isar_command: str):
    return isar_command[: isar_command.find("(*")]


def delete_texts(isar_commands: list[str]):
    result = []
    for command in isar_commands:
        command = command.strip()
        if re.split(r"[ \\]+", command)[0] == "text":
            continue
        result.append(command)
    return result


def replaced_by_sorry(isar_commands: list[str]):
    keywords = [
        "apply",
        "supply",
        "subgoal",
        "using",
        "unfolding",
        "proof",
        "qed",
        "done",
        "{",
        "}",
        "next",
        "note",
        "let",
        "write",
        "fix",
        "assume",
        "then",
        "have",
        "show",
        "from",
        "with",
        "also",
        "finally",
        "moreover",
        "ultimately",
        "presume",
        "define",
        "consider",
        "obtain",
        "case",
        "typ",
        "term",
        "prop",
        "print_statement",
        "thm",
        "apply_end",
        "defer",
        "prefer",
        "back",
        "oops",
        "hence",
        "thus",
        ".",
        "..",
        "and",
        "include",
        "including",
        "is",
        "interpret",
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
            if any(
                [
                    re.split(r'[ ()\-\'"\n]+', isar_commands[i].strip())[0] == keyword
                    for keyword in keywords
                ]
            ):
                while i < length and any(
                    [
                        re.split(r'[ ()\-\'"\n]+', isar_commands[i].strip())[0]
                        == keyword
                        for keyword in keywords
                    ]
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


def extract_theorem_names(command):
    pattern = re.compile(
        r"^\s*(lemma|theorem|corollary)\s+"
        r"([^\s\[\]:]+)"
        r"(?:\s*\[.*?\])?"
        r"\s*:"
    )

    match = pattern.match(command)
    if match:
        return match.group(2)
    return ""


def extract_sledgehammer_proof(output):
    match = re.match(r'^Try this:\s*(.*?)\s*\(([^()]*)\)$', output)
    if match:
        return match.group(1)
    return None

def extract_proof_step(text):
    # This regex looks for an Isabelle code block and captures its content
    match = re.search(r"```isabelle\s+(.*?)\s+```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def filter_explicit_premises(premises, theorem_proof_string):
    premises = [premise.strip() for premise in premises]
    # print(premises)
    # print("premises raw", premises)
    # print(f"Returned premises: {'||'.join(premises)}")

    # Function to break down the proof string
    def further_break(chunks, separator=None):
        new_chunks = []
        for chunk in chunks:
            new_chunks.extend(chunk.split(separator))
        return new_chunks

    # Break down the proof string into chunks which might be premises
    possible_premise_chunks = further_break([theorem_proof_string])
    # print("First filter", possible_premise_chunks)
    legit_separators = [",", "(", ")", "[", "]", "{", "}", ":", '"', "<", ">", "\\"]
    for separtor in legit_separators:
        possible_premise_chunks = further_break(possible_premise_chunks, separtor)
    # print("Second filter", possible_premise_chunks)
    possible_premise_chunks = set(chunk.strip() for chunk in possible_premise_chunks)
    # print("Third filter", possible_premise_chunks)
    
    
    # Only include theorems that are in the proof string
    explicit_premises = {}

    for premise in premises:
        premise_divisions = premise.split(".")
        for i in range(len(premise_divisions)):
            possible_way_to_refer_to_premise = ".".join(premise_divisions[i:])
            # print("possible_way", possible_way_to_refer_to_premise)
            if possible_way_to_refer_to_premise in possible_premise_chunks:
                if premise.strip():
                    explicit_premises[premise] = possible_way_to_refer_to_premise
                    break

    # explicit_premises = [premise for premise in explicit_premises if premise.strip()]
    # print(theorem_name, theorem_proof_string, explicit_premises)
    # print("*"*100)
    return explicit_premises

def extract_subgoals(proof_state: str) -> List[str]:
    """
    Extracts subgoals from an Isabelle proof state string.
    
    Args:
        proof_state (str): The raw proof state string from Isabelle.
    
    Returns:
        List[str]: A list of subgoals as strings.
    """
    # Normalize line endings and strip prefixes
    lines = proof_state.splitlines()
    goal_start = False
    subgoal_lines = []

    for line in lines:
        if re.match(r"\s*goal\s+\(\d+\s+subgoal", line):
            goal_start = True
            continue
        if goal_start:
            if re.match(r"\s*\d+\.\s", line):
                subgoal_lines.append(line.strip())
            elif subgoal_lines and line.strip() != "":
                # Append continuation of subgoal (multi-line goal)
                subgoal_lines[-1] += " " + line.strip()

    # Remove numbering prefix (e.g., "1. ")
    return [re.sub(r"^\d+\.\s*", "", g) for g in subgoal_lines]

def extract_proof_state_type(proof_state: str):
    """
    Extracts the proof state type from a raw Isabelle proof state string.
    
    Args:
        proof_state (str): The raw proof state string starting with 'proof (...)'
    
    Returns:
        Optional[str]: The proof state type inside parentheses, or None if not found.
    """
    match = re.match(r"\s*proof\s*\(([^)]+)\)", proof_state)
    if match:
        return match.group(1).strip()
    return None