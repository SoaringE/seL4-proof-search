import os
import re
from py4j.java_gateway import JavaGateway, GatewayParameters
from utils.repl import IsaRepl


code2inv_path = "./datasets/examples/code2inv"
newcode2inv_path = "./datasets/examples/newcode2inv"
# Set L4V_PATH to your local l4v directory. See README for details.
l4v_path = os.environ.get("L4V_PATH", "")
assert l4v_path, "L4V_PATH environment variable is not set"

code2inv_path = os.path.abspath(code2inv_path)
newcode2inv_path = os.path.abspath(newcode2inv_path)

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

{lemma_decl}

"""

c_template = """
int main ({para_list}) {{
    {body}
    {return_block}

"""
lemma_template = """lemma main'_correct: \"\<lbrace> \<lambda>s. {expr} \<rbrace> main' {arg_list} \<lbrace> \<lambda>r s. r = 1 \<rbrace>\""""


decl_line = "// variable declarations"
precond_line = "// pre-conditions"
loop_line = "// loop body"
postcond_line = "// post-condition"

# cnt = 0


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


def build_postcond(lines):
    # print(lines)
    for i, line in enumerate(lines):
        lines[i] = line.replace("assert", "return")
    # print(lines)
    have_if = any(["if" in line for line in lines])
    if have_if:
        right_bracket_index = 0
        for i in range(len(lines)):
            if lines[i] == "}":
                right_bracket_index = i
        lines.insert(right_bracket_index, "return 1;")
    return lines


def build_precond(lines):
    result = []
    for line in lines:
        if "assume" in line:
            result.append(remove_abundant_paraphases(line[6:]))
        else:
            result.append(line)
    return [line[:-1] for line in result]


def generate_files(filepath: str, content: str):
    lines = content.splitlines()
    simple_lines = [remove_abundant_paraphases(line.strip()) for line in lines]
    # if "/1.c" in filepath:
    #     print(simple_lines[:5])
    #     print(simple_lines[simple_lines.index(postcond_line) + 1 :])
    # else:
    #     return "", ""
    if (
        decl_line in simple_lines
        and precond_line in simple_lines
        and loop_line in simple_lines
        and postcond_line in simple_lines
    ):
        # global cnt
        # cnt += 1
        body = "\n".join(
            simple_lines[
                simple_lines.index(loop_line) + 1 : simple_lines.index(postcond_line)
            ]
        )
        precond = "\\<and>".join(
            build_precond(
                simple_lines[
                    simple_lines.index(precond_line) + 1 : simple_lines.index(loop_line)
                ]
            )
        )
        return_block = "\n".join(
            build_postcond(simple_lines[simple_lines.index(postcond_line) + 1 :])
        )
        para_list = " ".join(
            build_paralist(
                simple_lines[
                    simple_lines.index(decl_line) + 1 : simple_lines.index(precond_line)
                ]
            )
        )
        new_c_file_content = c_template.format(
            para_list=", ".join(["int " + var for var in para_list.split(" ")]),
            body=body,
            return_block=return_block,
        )
        new_isa_file_content = thy_header_template.format(
            theory_name="test" + os.path.basename(filepath).split(".")[0],
            c_file_path=os.path.join(newcode2inv_path, os.path.basename(filepath)),
            context_name=os.path.basename(filepath).split(".")[0],
            lemma_decl=lemma_template.format(expr=precond, arg_list=para_list),
        )
        has_unknown = False
        for line in simple_lines:
            if "unknown()" in line:
                has_unknown = True
        if has_unknown:
            new_c_file_content = "int unknown();\n" + new_c_file_content
        return new_c_file_content, new_isa_file_content
    else:
        return "", ""


def translate_all_files():
    os.makedirs(newcode2inv_path, exist_ok=True)
    for entry in os.listdir(code2inv_path):
        filepath = os.path.join(code2inv_path, entry)
        if os.path.isfile(filepath):
            # print(filepath)
            with open(filepath, "r") as f:
                content = f.read()
            a, b = generate_files(filepath, content)
            with open(os.path.join(newcode2inv_path, entry), "w") as f:
                f.write(a)
            with open(
                os.path.join(newcode2inv_path, "test" + entry.replace(".c", ".thy")),
                "w",
            ) as f:
                f.write(b)


# print(cnt)


## test
def test1():
    logic = "AutoCorres"

    thy_path = os.path.join(newcode2inv_path, "test1.thy")

    with open(thy_path, "r") as f:
        content = f.read()

    with IsaRepl(port=port) as isa_repl:
        # Initialize REPL with a theory file
        isa_repl.initialize(thy_path, l4v_path, logic, [l4v_path])
        # Compile the theory file
        _, steps = isa_repl.parse(content)

        step_count = 0

        for step in steps:
            if step.strip() != "":
                print(step_count, step)
                step_count += 1
                ok, msg = isa_repl.step(step)
                print(ok, msg)

        proof = """
            apply (unfold main'_def)
            apply wp
            apply simp
            apply (subst whileLoop_add_inv[where I = "\<lambda>(x, y) s.(x = (1 + y * (y - 1) div 2))"
                    and M = "\<lambda>((x, y), s) . (100000 - nat y)"] )
            apply wp
                apply auto
            apply (simp add: algebra_simps)


            proof -
                fix b::int
                assume Nb: "\<not> b < 100000"
                hence b_ge_100000: "b \<ge> 100000" by simp
                hence "b \<ge> 2" by simp
                hence "(b - 1) * 2 \<le> b * (b - 1)"
                    by (metis diff_ge_0_iff_ge dual_order.trans mult.commute mult_right_mono one_le_numeral)
                moreover have "0 < (2::nat)" by simp
                ultimately have "b - 1 \<le> (b * (b - 1)) div 2"
                    by simp
                hence "b \<le> 1 + (b * (b - 1)) div 2"
                    by (simp add: le_add1)
                thus "b \<le> 1 + b * (b - 1) div 2" by simp
            qed

        """
        _, proof_steps = isa_repl.parse(proof)
        for proof_step in proof_steps:
            if proof_step.strip() != "":
                print(step_count, proof_step)
                step_count += 1
                ok, msg = isa_repl.step(proof_step)
                print(ok, msg)


### check_all
def test2():
    malform = []

    with IsaRepl(port=port) as isa_repl:
        for entry in os.listdir(newcode2inv_path):
            # print(entry)
            filepath = os.path.join(newcode2inv_path, entry)
            if os.path.isfile(filepath) and filepath.endswith(".thy"):
                # print("ok")
                logic = "AutoCorres"
                thy_path = filepath

                with open(thy_path, "r") as f:
                    content = f.read()
                if content.strip() == "":
                    continue
                # Initialize REPL with a theory file
                isa_repl.initialize(thy_path, l4v_path, logic, [l4v_path])

                # print("initialization: ", init_res)
                # Compile the theory file
                _, steps = isa_repl.parse(content)

                for i, step in enumerate(steps):
                    if step.strip() != "":
                        print(i, step)
                        success, msg = isa_repl.step(steps[i])
                        if not success:
                            print("Error: ", msg)
                            malform.append(entry)
                            break
                        else:
                            print("State: ", msg)

    print(malform)


if __name__ == "__main__":
    translate_all_files()
    test1()
