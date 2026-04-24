package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class ExtractGoalTests extends AnyFunSuite {
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
  test("extract notforall goal from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
      theorem example1: "\<not>(\<forall>n::nat. f (f n) \<noteq> n + 1987)"
        proof 
          assume H: "\<forall>n::nat. f (f n) \<noteq> n + 1987"
      """)
    val result = isa_repl.extract_goal()
    assert(result == "False")
    isa_repl.step("""
      show False 
        sorry
      qed
      """)
  }

  // test 2
  test("extract forall goal from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
      theorem example2: "\<forall>n::nat. f (f n) = n + 1987"
        proof 
          fix n::nat
      """)
    val result = isa_repl.extract_goal()
    assert(result == "f (f n) = n + 1987")
    isa_repl.step("""
      show "f (f n) = n + 1987" 
        sorry
      qed
      """)
  }

  // test 3
  test("extract ccontr goal from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
      theorem example3: "(\<exists>n::nat. f (f n) = n + 1987)"
        proof (rule ccontr)
          assume "\<not>(\<exists>n::nat. f (f n) = n + 1987)"
      """)
    val result = isa_repl.extract_goal()
    assert(result == "False")
    isa_repl.step("""
      show False 
        sorry
      qed
      """)
  }

  // test 4
  test("check no_subgoals No.1") {
    isa_repl.step("""
      theorem example4: "False"
        proof-
           show ?thesis
      """)
    val result1 = isa_repl.check_no_subgoals()
    assert(result1 == false)
    isa_repl.step("sorry")
    val result2 = isa_repl.check_no_subgoals()
    assert(result2 == true)
    isa_repl.step("qed")
  }

  // test 5
  test("check no_subgoals No.2") {
    isa_repl.step("""
      theorem example5: "\<not>(\<forall>(n::nat). f (f n) = n + 1987)"
        proof
          assume A: "\<forall> n. f (f n) = n + 1987"
          have inj_f: "inj f"
          proof (rule inj_onI)
            fix m n
            assume "f m = f n"
            have "f (f m) = f (f n)"
              using \<open>f m = f n\<close> by force
            from A
            have "f (f m) = m + 1987" and "f (f n) = n + 1987"
              by auto
      """)
    val result = isa_repl.check_no_subgoals()
    assert(result == true)
    isa_repl.step("""
        show "m = n" 
          sorry
      qed
      show False
        sorry
      qed
      """)
  }

  test("extract extential goal from Isabelle proof") {
    isa_repl.step("""
    lemma 
    assumes "\<exists>x y. P x \<and> Q y \<and> R x y"
    shows "\<exists>u v. P u \<and> Q v"
      proof -
        from assms obtain x y where "P x" "Q y" "R x y"
      """)
    val result = isa_repl.extract_goal()
    assert(result == "thesis")
    isa_repl.step("""
      by auto
      thus ?thesis by blast
      qed
      """)
  }
}
