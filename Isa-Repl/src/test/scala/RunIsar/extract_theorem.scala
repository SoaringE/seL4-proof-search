package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class ExtractTheoremTests extends AnyFunSuite {
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
  test("extract theorem No.1 from Isabelle proof") {
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
    val vars = isa_repl.extract_vars()
    val assms = isa_repl.extract_assms()
    val goal = isa_repl.extract_goal()
    assert(vars == List("x :: int"))
    assert(
      assms == List(
        "x = x",
        "0 < x",
        "x\\<^sup>2 = x * x",
        "x ^ 4 = x\\<^sup>2 * x\\<^sup>2"
      )
    )
    assert(goal == "0 \\<le> x\\<^sup>2 + 2 * x + 1")
    isa_repl.step("""
        sorry
      qed
      """)
  }

  test("extract theorem No.2 from Isabelle proof") {
    isa_repl.step("""
      theorem fixes f :: "nat \<Rightarrow> nat" shows "\<not> (\<forall> n. f (f n) = n + 1987)"
        proof
          assume H: "\<forall> n. f (f n) = n + 1987"
          let ?g = "\<lambda> n. f n - n"
          have g_pos: "\<forall> n. ?g n >= 1"
            proof
              fix n
              {
              assume "f n < n"
              have "f (f n) < f n"
      """)
    val vars = isa_repl.extract_vars()
    val assms = isa_repl.extract_assms()
    val goal = isa_repl.extract_goal()
    assert(vars == List("n :: nat", "f :: nat \\<Rightarrow> nat"))
    assert(assms == List("f n < n", "\\<forall>n. f (f n) = n + 1987"))
    assert(goal == "f (f n) < f n")
    val result = isa_repl.step("""
            sorry
            }
        show "?g n >= 1" sorry
        qed
        show False sorry
        qed""")
    assert(result == "")
  }

}
