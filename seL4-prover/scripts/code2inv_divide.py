import os
import re
import time
from py4j.java_gateway import JavaGateway, GatewayParameters


# Ground-truth dataset from
# https://github.com/SoftWiser-group/LaM4Inv/blob/main/Result/GPT4TurboFull.txt
# Override with the GROUND_TRUTH_PATH env var.
ground_truth_path = os.environ.get(
    "GROUND_TRUTH_PATH",
    os.path.join(os.path.dirname(__file__), "..", "datasets", "GPT4TurboFull.txt"),
)

port = 25551

thy_header_template = """
theory {theory_name}
    imports "AutoCorres.AutoCorres"
begin

external_file "{c_file_path}"
install_C_file "{c_file_path}"

autocorres [ts_rules = nondet] "{c_file_path}"

context {context_name} begin

thm main'_def


"""

simple_thy_header_template = """
theory {theory_name}
    imports "AutoCorres.AutoCorres"
begin

"""


c_template = """
int main ({para_list}) {{
    {body}
    {return_block}
}}

"""
lemma_template = """lemma main'_correct: \"\<lbrace> \<lambda>s. {expr} \<rbrace> main' {arg_list} \<lbrace> \<lambda>r s. r = 1 \<rbrace>\""""


decl_line = "// variable declarations"
precond_line = "// pre-conditions"
loop_line = "// loop body"
postcond_line = "// post-condition"

### read ground truths

with open(ground_truth_path, "r") as f:
    ground_truth = f.read()

limit = 133
ground_truth_list = [""]

for line in ground_truth.split("\n"):
    if line.startswith("Bench") or line.startswith("assert"):
        continue
    if len(ground_truth_list) >= 134:
        break
    if line.strip() == "":
        ground_truth_list.append("")
    ground_truth_list[-1] += "\n" + line
    # print(ground_truth_list)

# print(len(ground_truth_list))
ground_truth_list = [block.split("\n")[-1] for block in ground_truth_list]
ground_truths = []
for line in ground_truth_list:
    # print(line)
    ground_truths.append(line.split("\t")[1].strip()[6:-1])
    if len(ground_truths) >= 133:
        break
# cnt = 0
# print("last", ground_truths[-1])


def remove_abundant_paraphases(line: str):
    if line.endswith(";"):
        prefix = line[:-1]
        while prefix.endswith(")") and prefix.startswith("("):
            prefix = prefix[1:-1]
        return prefix + ";"
    else:
        while line.endswith(")") and line.startswith("("):
            line = line[1:-1]
        return line


def build_paralist(lines):
    result = []
    for line in lines:
        vars = re.findall(r"int\s+(\w+)\s*;", line)
        result += vars
    return result


def build_precond(lines):
    result = []
    for line in lines:
        if "assume" in line:
            result.append(remove_abundant_paraphases(line[6:]))
        else:
            result.append(line)
    return "\\<and>".join([line[:-1] for line in result])


def tranlsate_logic(expr):
    c2isabelle = {
        "&&": "\\<and>",
        "||": "\\<or>",
        "%": "mod",
        "!=": "\\<noteq>",
        "!": "\\<not>",
        "==": "=",
        "/": "div",
    }
    for key, value in c2isabelle.items():
        expr = expr.replace(key, value)
    return expr


def build_invariant(entry):
    # print(ground_truths)
    return ground_truths[entry - 1]


def build_postcond(lines):
    # print(lines)
    lines = [line for line in lines if not line.startswith("//")]
    lines = [line for line in lines if line.strip() != ""]
    lines = lines[:-1]
    has_if = False
    for i, line in enumerate(lines):
        if line.startswith("assert"):
            lines[i] = line.replace("assert", "")
        if line.startswith("if"):
            has_if = True
            lines[i] = line.replace("if", "")
    for i, line in enumerate(lines):
        if line.endswith(";"):
            lines[i] = line.replace(";", "")
    for i, line in enumerate(lines):
        lines[i] = line.replace("{", "").replace("}", "")
    # print(lines)
    lines = [remove_abundant_paraphases(line) for line in lines]
    lines = [line for line in lines if line.strip() != ""]
    
    if has_if:
        return "( " + lines[0] + " \\<longrightarrow> (" + "\\<and>".join(lines[1:])  + "))"
    return "\\<and>".join(lines)


### precond ==> inv
def generate_lemma_one(code2inv_path, entry):
    with open(os.path.join(code2inv_path, f"{entry}.c"), "r") as f:
        content = f.read()
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]

    precond = build_precond(
        simple_lines[
            simple_lines.index(precond_line) + 1 : simple_lines.index(loop_line)
        ]
    )
    inv = build_invariant(entry)
    precond = tranlsate_logic(precond)
    inv = tranlsate_logic(inv)
    return f'lemma "{precond} \\<Longrightarrow> {inv}"'


def extract_loop_body(lines):
    content = ("\n".join(lines)).strip()
    if content.startswith("while"):
        left = content.find("{")
        right = content.rfind("}")
        content = content[left : right + 1]

    return content.split("\n")


def construct_new_func(code2inv_path, entry):
    with open(os.path.join(code2inv_path, f"{entry}.c"), "r") as f:
        content = f.read()
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]
    para_list = para_list = " ".join(
        build_paralist(
            simple_lines[
                simple_lines.index(decl_line) + 1 : simple_lines.index(precond_line)
            ]
        )
    )
    loop_body_lines = extract_loop_body(
        simple_lines[
            simple_lines.index(loop_line) + 1 : simple_lines.index(postcond_line)
        ]
    )
    inv = build_invariant(entry)
    new_func = c_template.format(
        para_list=", ".join(["int " + var for var in para_list.split(" ")]),
        body="\n".join(loop_body_lines),
        return_block="\nreturn " + inv + ";",
    )
    if "unknown()" in content:
        new_func = "int unknown();\n" + new_func
    return new_func


### {inv} procedure {inv}
def generate_lemma_two(code2inv_path, entry):
    with open(os.path.join(code2inv_path, f"{entry}.c"), "r") as f:
        content = f.read()
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]
    para_list = " ".join(
        build_paralist(
            simple_lines[
                simple_lines.index(decl_line) + 1 : simple_lines.index(precond_line)
            ]
        )
    )
    inv = tranlsate_logic(build_invariant(entry))
    lemma_decl = lemma_template.format(expr=inv, arg_list=para_list)
    return lemma_decl


### inv ==> postcond
def generate_lemma_three(code2inv_path, entry):
    with open(os.path.join(code2inv_path, f"{entry}.c"), "r") as f:
        content = f.read()
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]

    postcond = build_postcond(simple_lines[simple_lines.index(postcond_line) + 1 :])
    inv = build_invariant(entry)
    postcond = tranlsate_logic(postcond)
    inv = tranlsate_logic(inv)
    return f'lemma "{inv} \\<Longrightarrow> {postcond}"'


def generate_files(code2inv_path, entry: int):
    # if "/1.c" in filepath:
    #     print(simple_lines[:5])
    #     print(simple_lines[simple_lines.index(postcond_line) + 1 :])
    # else:
    #     return "", ""
    with open(os.path.join(code2inv_path, f"{entry}.c"), "r") as f:
        content = f.read()
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]

    if (
        decl_line in simple_lines
        and precond_line in simple_lines
        and loop_line in simple_lines
        and postcond_line in simple_lines
    ):
        # global cnt
        # cnt += 1
        # body = "\n".join(simple_lines[simple_lines.index(loop_line) + 1 : simple_lines.index(postcond_line)])
        # precond = "\\<and>".join(build_precond(simple_lines[simple_lines.index(precond_line) + 1 : simple_lines.index(loop_line)]))
        # return_block = "\n".join(build_postcond(simple_lines[simple_lines.index(postcond_line) + 1 :]))
        # para_list = " ".join(build_paralist(simple_lines[simple_lines.index(decl_line) + 1 : simple_lines.index(precond_line)]))
        # new_c_file_content = c_template.format(
        #     para_list=", ".join(["int " + var for var in para_list.split(" ")]),
        #     body=body,
        #     return_block=return_block,
        # )
        # new_isa_file_content = thy_header_template.format(
        #     theory_name="test" + os.path.basename(filepath).split(".")[0],
        #     c_file_path=os.path.join(newcode2inv_path, os.path.basename(filepath)),
        #     context_name=os.path.basename(filepath).split(".")[0],
        #     lemma_decl=lemma_template.format(expr=precond, arg_list=para_list),
        # )
        # has_unknown = False
        # for line in simple_lines:
        #     if "unknown()" in line:
        #         has_unknown = True
        # if has_unknown:
        #     new_c_file_content = "int unknown();\n" + new_c_file_content
        # return new_c_file_content, new_isa_file_content

        lemma_one = generate_lemma_one(code2inv_path, entry)
        # print("*" * 80 + "\n\n", lemma_one)
        lemma_two = generate_lemma_two(code2inv_path, entry)
        # print("*" * 80 + "\n\n", lemma_two)
        lemma_three = generate_lemma_three(code2inv_path, entry)
        # print("*" * 80 + "\n\n", lemma_three)
        new_c_file_content = construct_new_func(code2inv_path, entry)
        # print("*" * 80 + "\n\n", new_c_file_content)
        return lemma_one, lemma_two, lemma_three, new_c_file_content
    else:
        print(entry)


def translate_all_files(code2inv_path, newcode2inv_path):
    os.makedirs(newcode2inv_path, exist_ok=True)
    for i in range(1, 134):
        # if i != 1:
        #     continue
        a, b, c, d = generate_files(code2inv_path, i)
        a = a.replace("size", "sz")
        b = b.replace("size", "sz")
        c = c.replace("size", "sz")
        d = d.replace("size", "sz")
        new_c_file_path = os.path.join(newcode2inv_path, f"new_{i}.c")
        with open(new_c_file_path, "w") as f:
            f.write(d)
        with open(os.path.join(newcode2inv_path, "test" + f"{i}_pre.thy"), "w") as f:
            f.write(
                simple_thy_header_template.format(theory_name="test" + f"{i}_pre")
                + "\n\n"
                + a,
            )
        with open(os.path.join(newcode2inv_path, "test" + f"{i}_inv.thy"), "w") as f:
            f.write(
                thy_header_template.format(
                    theory_name="test" + f"{i}_inv",
                    c_file_path=new_c_file_path,
                    context_name=f"new_{i}",
                )
                + "\n\n"
                + b,
            )
        with open(os.path.join(newcode2inv_path, "test" + f"{i}_post.thy"), "w") as f:
            f.write(
                simple_thy_header_template.format(theory_name="test" + f"{i}_post")
                + "\n\n"
                + c,
            )

