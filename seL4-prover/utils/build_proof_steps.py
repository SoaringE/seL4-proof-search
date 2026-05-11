import re
import random
from collections import Counter
from typing import List, Tuple

all_tactic_path = "./datasets/tactic_list.txt"
selected_tactic_path = "./datasets/tactic_simplified.txt"


def read_tactics(tactic_path):
    selected_tactics = []
    with open(tactic_path, encoding="utf-8") as f:
        for line in f:
            tactic = " ".join(line.split(" ")[:-1])
            selected_tactics.append(tactic)
    return selected_tactics


def tactic_tokenizer(tactic_list: List[str]):
    token_pattern = re.compile(r"<placeholder>|[A-Za-z0-9_'\?\.]+|[^\s]")
    quoted_pattern = re.compile(r'"[^"]*"')

    counter = Counter()

    for line in tactic_list:
        line = quoted_pattern.sub(" ", line)
        tokens = token_pattern.findall(line.strip())
        # if "s" in tokens:
        #     print(line)
        counter.update(tokens)

    # with open(token_path, "w", encoding="utf-8") as out:
    #     for token, freq in counter.most_common():
    #         out.write(f"{token} {freq}\n")
    return list(counter.keys())


selected_tactics = read_tactics(selected_tactic_path)
known_tokens = tactic_tokenizer(read_tactics(all_tactic_path)[:200])


def proof_line_tokenizer(proof_line: str):
    token_pattern = re.compile(r"<placeholder>|[A-Za-z0-9_'\?\.]+|[^\s]")
    quoted_pattern = re.compile(r'"[^"]*"')

    line = quoted_pattern.sub(" ", proof_line)
    tokens = token_pattern.findall(line.strip())
    return tokens


def extract_premises(proof_line):
    proof_line_tokens = proof_line_tokenizer(proof_line)
    premises = []
    for token in proof_line_tokens:
        if token not in known_tokens:
            premises.append(token)
    return premises


def combine_premises(scored_premises: List[Tuple[str, float]]):
    crafted_proofs = []
    random.shuffle(selected_tactics)
    random_selected_tactics = selected_tactics[:256]
    for premise, logprob in scored_premises:
        for tactic in selected_tactics:
            if tactic.count("<placeholder>") == 0:
                crafted_proofs.append((tactic, logprob))
            if tactic.count("<placeholder>") == 1:
                crafted_proofs.append(
                    (tactic.replace("<placeholder>", premise), logprob)
                )
    return crafted_proofs


def build_crafted_steps(proof_line: str):
    proof_line = proof_line.strip()
    crafted_steps = []
    if proof_line.startswith("by"):
        crafted_steps.append("apply" + proof_line[2:])
    premises = extract_premises(proof_line)
    crafted_steps += combine_premises(premises)
    return crafted_steps


if __name__ == "__main__":
    test_line = [
        (
            "by (simp add: valid_mdb'_def split del: if_split) \
        (rule hoare_pre, wpsimp wp: updateMDB_weak_cte_wp_at updateCap_ctes_of_wp getCTE_wp')+",
            0.7,
        )
    ]
    extracted_premises = extract_premises(test_line[0][0])
    print(extracted_premises)
    crafted_proofs = combine_premises(
        list(zip(extracted_premises, [0.7] * len(extracted_premises)))
    )
    print(len(crafted_proofs))
    print(crafted_proofs[:5])
