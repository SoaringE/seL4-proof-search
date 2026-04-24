import subprocess
import time
import os
from py4j.java_gateway import JavaGateway, GatewayParameters

### subprocess to run the jar file
def run_jar_file(jar_path, port):
    env = os.environ.copy()
    env["ISABELLE_HOME"] = os.path.expanduser("~/verification/isabelle/")
    process = subprocess.Popen([
        "java", "-jar", jar_path, str(port)
    ])
    # Give the server some time to start
    time.sleep(2)
    return process

### test the isapy connection
def isapy_repl(port):
    gateway = JavaGateway(gateway_parameters=GatewayParameters(port=port, auto_convert=True))
    isa_repl = gateway.entry_point
    return isa_repl

def test_proof(isa_repl):
    # Initialize REPL with a theory file
    theory_file = os.path.abspath("python-test/Test.thy")
    isa_repl._initializeRepl(theory_file)
                
    # Compile the theory file
    result = isa_repl._compile()
    print("Compilation result:", result)
            
    # Create and prove a theorem
    # theorem = 'lemma "(x :: rat) >= 0"'
    theorem = 'lemma "(3::nat) <= (4::nat)"'
    # theorem = 'lemma "(3) <= (4)"'
    result = isa_repl._step(theorem)
    print("Theorem declaration result:", result)
            
    # Add a proof step
    # proof_step = "show ?thesis by (simp add: numeral_eq_Suc)"
    # result = isa_repl._step(proof_step)
    # print("Proof step result:", result)
    # proof_step = "show ?thesis by (simp add: numeral_eq_Suc)"
    result = isa_repl._check_by_quickcheck()
    print("QuickCheck result:", result)
    result = isa_repl._extract_hammer_facts()
    print("Extract fact result: ", result)

"""
Test the IsaREPL server with a sub-repl connection
    using subprocess to open the JVM server
    and py4j to connect to the server
"""
if __name__ == "__main__":
    jar_path = "target/IsaREPL.jar"
    port = 25555
    
    # Start the JVM server
    jvm_process = run_jar_file(jar_path, port)
        
    # Connect to the server
    isa_repl = isapy_repl(port)
        
    # Your test code here
    print("Successfully connected to IsaREPL server")

    test_proof(isa_repl)

    jvm_process.terminate()
    jvm_process.wait()  # Wait for process to terminate

# ~/projects/Isa-Repl$ python ./python-test/test_quickcheck.py 
# Server started on port 25555 (Press Ctrl+C to stop)
# Python connection port: 25555
# Successfully connected to IsaREPL server
# Compilation result: True<\SEP>
# Theorem declaration result: True<\SEP>proof (prove)
# goal (1 subgoal):
#  1. 3 \<le> 4
# QuickCheck result: False<\SEP>Quickcheck found no counterexample — goal appears valid.
# Extract fact result:  True<\SEP>Selected 126 mepo facts: semiring_norm(86) semiring_norm(84) semiring_norm(89) semiring_norm(88) semiring_norm(85) semiring_norm(83) numeral_le_iff num.exhaust verit_eq_simplify(9) semiring_norm(90) Let_numeral numeral_eq_iff semiring_norm(87) verit_eq_simplify(8) semiring_norm(71) semiring_norm(68) semiring_norm(73) semiring_norm(69) semiring_norm(72) semiring_norm(70) le_num_One_iff verit_la_disequality verit_comp_simplify1(2) semiring_norm(82) verit_eq_simplify(10) verit_eq_simplify(14) verit_eq_simplify(12) dual_order.refl order_refl dbl_inc_simps(5) dbl_simps(5) sub_num_simps(5) numeral_le_one_iff semiring_norm(74) semiring_norm(79) neg_numeral_le_iff or_num.elims verit_minus_simplify(4) neg_numeral_eq_iff Let_neg_numeral semiring_norm(78) semiring_norm(75) semiring_norm(80) numeral_eq_one_iff one_eq_numeral_iff numeral_less_iff semiring_norm(76) semiring_norm(81) semiring_norm(77) dbl_simps(1) dbl_inc_simps(4) sub_num_simps(6) sub_num_simps(9) neg_one_eq_numeral_iff numeral_eq_neg_one_iff neg_numeral_less_iff sub_num_simps(8) not_neg_one_le_neg_numeral_iff neg_numeral_less_neg_one_iff one_less_numeral_iff dbl_simps(3) dbl_inc_simps(3) sub_num_simps(3) dbl_simps(4) verit_comp_simplify1(1) verit_negate_coefficient(3) verit_negate_coefficient(2) le_minus_one_simps(4) le_minus_one_simps(2) less_minus_one_simps(4) less_minus_one_simps(2) less_numeral_extra(4) one_neq_neg_one numeral_neq_neg_one one_neq_neg_numeral neg_numeral_less_one neg_one_less_numeral neg_numeral_less_numeral not_numeral_less_neg_one not_one_less_neg_numeral not_neg_one_less_neg_numeral not_numeral_less_neg_numeral not_numeral_less_one order_less_imp_not_less order_less_imp_not_eq2 order_less_imp_not_eq linorder_less_linear order_less_imp_triv order_less_not_sym order_less_subst2 order_less_subst1 order_less_irrefl ord_less_eq_subst ord_eq_less_subst order_less_trans order_less_asym' linorder_neq_iff order_less_asym linorder_neqE dual_order.strict_implies_not_eq order.strict_implies_not_eq dual_order.strict_trans not_less_iff_gr_or_eq order.strict_trans linorder_less_wlog exists_least_iff dual_order.irrefl dual_order.asym linorder_cases antisym_conv3 less_induct ord_less_eq_trans ord_eq_less_trans order.asym less_imp_neq dense gt_ex lt_ex leD leI nless_le antisym_conv1 antisym_conv2 dense_ge dense_le less_le_not_le

# Received shutdown signal - terminating gracefully...
# Server shutdown complete
# Server shutdown complete