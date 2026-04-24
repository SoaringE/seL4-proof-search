package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class SmtTranslateTests extends AnyFunSuite {
  // get the value of isabelleHome_str from env variable ISABELLE_HOME. If not set, raise an error
  val isabelleHome_str: String = sys.env.getOrElse(
    "ISABELLE_HOME",
    throw new Exception("ISABELLE_HOME not set")
  )
  val isabelle_home: String = isabelleHome_str

  val path_to_thy: String =
    Paths.get("python-test/Test.thy").toAbsolutePath.toString
  val working_directory: String =
    Paths.get("python-test").toAbsolutePath.toString
  val isa_repl = new IsaREPL(
    isabelle_home = isabelle_home,
    path_to_thy = path_to_thy,
    working_directory = working_directory,
    debug = false
  )

  // 1. compile the theory env
  val result0: String =
    isa_repl.compile(""" theory Test imports Main HOL.HOL HOL.Real begin""")

  // test 1
  test("translate the goal to SMT") {
    // create the theorem to be proved
    isa_repl.step("""
                lemma 
                  fixes x :: int 
                  assumes "x > 0"
                  shows "x ^ 2 + 2 * x + 1 >= 0" 
                  proof-
                    have "x = x" by simp
                    have "x ^ 2 = x * x"
                    proof- 
                        have "x ^ 2 = x * x" by (simp add: power2_eq_square)
                        show ?thesis by (simp add: power2_eq_square)
                    qed
                    have "x ^ 4 = x ^ 2 * x ^ 2" by simp
                    show ?thesis 
                """)
    val smt = isa_repl.translate_to_smt()
    val expected = """
      ; smt.random_seed=1 smt.refine_inj_axioms=false -smt2
      (set-logic AUFLIA)
      (declare-sort Nat$ 0)
      (declare-sort Num$ 0)
      (declare-fun x$ () Int)
      (declare-fun one$ () Num$)
      (declare-fun bit0$ (Num$) Num$)
      (declare-fun power$ (Int Nat$) Int)
      (declare-fun times$ (Int Int) Int)
      (declare-fun numeral$ (Num$) Nat$)
      (assert (! (= x$ x$) :named a0))
      (assert (! (< 0 x$) :named a1))
      (assert (! (= (power$ x$ (numeral$ (bit0$ one$))) (times$ x$ x$)) :named a2))
      (assert (! (= (power$ x$ (numeral$ (bit0$ (bit0$ one$)))) (times$ (power$ x$ (numeral$ (bit0$ one$))) (power$ x$ (numeral$ (bit0$ one$))))) :named a3))
      (assert (! (not (<= 0 (+ (+ (power$ x$ (numeral$ (bit0$ one$))) (* 2 x$)) 1))) :named conjecture4))
      (check-sat)
      (get-proof)
      """
    assert(
      smt.trim.replaceAll("\\s+", " ") == expected.trim.replaceAll("\\s+", " ")
    )
    isa_repl.step("""
        sorry
      qed
      """)
  }

}
