import os

from dotenv import load_dotenv

from utils.repl import IsaRepl, SafeIsaRepl

load_dotenv()
# Set L4V_PATH to your local l4v directory. See README for details.
L4V_PATH = os.environ.get("L4V_PATH", "")
assert L4V_PATH, "L4V_PATH environment variable is not set"

working_dir = L4V_PATH
session_roots = [L4V_PATH]
exclude_list = []

# lemma = {
#     "name": "",
#     "statement": "",
#     "path": "",
#     "session": "",
# }

lemma = {
    "session": "AInvs",
    "context": 'lemma list_eq_after_in_list:\n  "\\<lbrakk>valid_list_2 t m; m x = Some p\\<rbrakk>\n    \\<Longrightarrow> \\<exists>list. t p = list @ x # after_in_list_list (t p) x" apply(simp only:valid_list_2_def) apply (erule conjE) apply (drule_tac x = p in spec)+ apply (subgoal_tac "x \\<in> set (t p)") apply (drule_tac in_set_conv_nth[THEN iffD1], erule exE) apply (auto simp: in_set_conv_nth list_eq_after_in_list\') done',
    "statement": 'lemma list_eq_after_in_list:\n  "\\<lbrakk>valid_list_2 t m; m x = Some p\\<rbrakk>\n    \\<Longrightarrow> \\<exists>list. t p = list @ x # after_in_list_list (t p) x"',
    "name": "unnamed_thy_11534",
    "theory_name": "Deterministic_AI",
    "path": os.path.join(L4V_PATH, "proof/invariant-abstract/Deterministic_AI.thy"),
}

with IsaRepl(port=25555) as isa_repl:
    isa_repl = SafeIsaRepl(isa_repl)
    isa_repl.initialize(lemma["path"], working_dir, lemma["session"], session_roots)
    step_success, msg = isa_repl.step_to_target(
        lemma["statement"], exclude_list
    )
    if not step_success:
        print(f"{lemma['name']}: Failed to step to target lemma: {msg}")
    else:
        print(f"{lemma['name']}: Successfully step to target lemma:\n {msg}")
        # unnamed_thy_11534: Successfully step to target lemma:
        # proof (prove)
        # goal (1 subgoal):
        # 1. \<lbrakk>valid_list_2 t m; m x = Some p\<rbrakk> \<Longrightarrow> \<exists>list. t p = list @ x # after_in_list_list (t p) x

    isa_repl.clone_tls("initial_state")  # tls is toplevel state

    ok, msg = isa_repl.step("apply(simp only:valid_list_2_def)")
    print(msg)
    # proof (prove)
    # goal (1 subgoal):
    # 1. \<lbrakk>(\<forall>p. set (t p) = {c. m c = Some p}) \<and> (\<forall>p. distinct (t p)); m x = Some p\<rbrakk> \<Longrightarrow> \<exists>list. t p = list @ x # after_in_list_list (t p) x

    isa_repl.focus_tls("initial_state")

    isa_repl.remove_tls("initial_state")

    ok, msg = isa_repl.execute_steps(
        [
            "apply(simp only:valid_list_2_def)",
            "apply (erule conjE)",
            "apply (drule_tac x = p in spec)+",
            'apply (subgoal_tac "x \\<in> set (t p)")',
            "apply (drule_tac in_set_conv_nth[THEN iffD1], erule exE)",
        ]
    )
    # print(msg)
    #     proof (prove)
    # goal (2 subgoals):
    # 1. \<And>i. \<lbrakk>m x = Some p; set (t p) = {c. m c = Some p}; distinct (t p); i < length (t p) \<and> t p ! i = x\<rbrakk> \<Longrightarrow> \<exists>list. t p = list @ x # after_in_list_list (t p) x
    # 2. \<lbrakk>m x = Some p; set (t p) = {c. m c = Some p}; distinct (t p)\<rbrakk> \<Longrightarrow> x \<in> set (t p)

    ok, msg = isa_repl.check_by_quickcheck()
    print(msg)
    # failed for check the goal by quickcheck. Get msg: Wellsortedness error:
    # Type 32 word \<times> bool list not of sort enum
    # No type arity list :: enum

    isa_repl.relearn_isar()
    steps, msg = isa_repl.hammer()
    if steps != []:
        print(f"Find proof:\n {msg}")
    else:
        print("Failed to find a proof automatically")
    # Find proof:
    # Try this: apply (meson list_eq_after_in_list') (5 ms)
    ok, msg = isa_repl.step('find_theorems "obj_at _ _" "set_thread_state"')
    print("*" * 40)
    print(msg)
    ok, msg = isa_repl.step("apply (meson list_eq_after_in_list')")

    steps, msg = isa_repl.hammer()
    if steps != []:
        print(f"Find proof:\n {msg}")
    else:
        print("Failed to find a proof automatically")
    # Find proof:
    # Try this: by blast (0.4 ms)
    ok, msg = isa_repl.step("by blast")
    print(msg)
    #
