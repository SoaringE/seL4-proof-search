import re


def parse_java_object(parse_result) -> tuple[bool, str]:
    """Parse a String to a tuple of (ok, msg)."""
    if "<\\SEP>" in parse_result:
        ok, msg = parse_result.split("<\\SEP>", 1)
        ok = True if ok == "True" else False
        return ok, msg
    else:
        return (
            False,
            f"Failed to parse the result. Got unexpected result: {parse_result}",
        )


def parse_hammer_facts(parse_result):
    if "<\\SEP>" in parse_result:
        ok, msg = parse_result.split("<\\SEP>", 1)
        ok = True if ok == "True" else False
        lst = (":".join(msg.split(":")[1:])).strip().split(" ")
        return ok, lst
    else:
        return False, [
            f"Failed to parse the result. Got unexpected result: {parse_result}"
        ]


def remove_illegal_variables(text):
    # Remove like "Illegal schematic type variable: ?'a1"
    text = re.sub(r"::\?'[a-zA-Z0-9]+", "", text)
    return text.strip()


def parse_tactic(tactic: str) -> str:
    """Parse tactic from a string that may contain timing information.

    Args:
        tactic_str (str): The tactic string to parse, e.g. "Try this: using power2_eq_square by blast (0.5 ms)"

    Returns:
        str: The parsed tactic, e.g. "using power2_eq_square by blast"
    """
    # Remove "Try this: " if present
    if "Try this:" in tactic:
        tactic = tactic.split("Try this:")[1].strip()

    # Remove timing information in parentheses at the end
    if "(" in tactic:
        tactic = tactic.rsplit("(", 1)[0].strip()

    # Remove illegal variables
    tactic = remove_illegal_variables(tactic)

    return tactic


def shorten_text(text, width=30):
    # width is a soft limit
    text = text.replace("\n", " ")
    if len(text) > width:
        text = text.split(" ")[0:width]
        text = " ".join(text) + "..."
    return text


def clean_whitespace(s):
    s = re.sub(r"\s", " ", s)
    s = re.sub(r" +", " ", s)
    return s.strip()
