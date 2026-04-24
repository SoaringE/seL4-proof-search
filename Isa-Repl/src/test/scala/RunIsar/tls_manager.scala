package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL
import de.unruh.isabelle.control.IsabelleMLException

class TlsManagerTests extends AnyFunSuite {
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

  // test 1
  val result0: String =
    isa_repl.compile(""" theory Test imports Main HOL.HOL HOL.Real begin""")

  test("Clone the TLS") {
    isa_repl.step("lemma fixes x :: int shows \"x ^ 3 = x * x * x\" proof- \n")
    val goal = isa_repl.extract_goal()
    isa_repl.clone_tls("test")
    isa_repl.step("show ?thesis by (simp add: numeral_eq_Suc)")
    val goal1 = isa_repl.extract_goal()
    assert(goal1 == "")
    isa_repl.focus_tls("test")
    val goal2 = isa_repl.extract_goal()
    assert(goal == goal2)
  }

//   test("Create the theorem to be proved") {
//     val theorem_string = "lemma fixes x :: int shows \"x ^ 3 = x * x * x\" \n proof- \n"
//     val result1: String = isa_repl.step(theorem_string)
//     assert (result1.contains("proof (state)") && result1.contains("x ^ 3 = x * x * x"))
//   }

//   test("Declare a new subgoal") {
//     val proof_string1 = "have eq1: \"x ^ 2 = x * x\""
//     val result2: String = isa_repl.step(proof_string1)
//     assert (result2.contains("x\\<^sup>2 = x * x"))
//   }

//   test("Prove the subgoal") {
//     val proof_string2 = "by auto"
//     var result3: String = ""
//     try{
//       result3 = isa_repl.step(proof_string2)
//       println(result3)
//     } catch {
//       case _: IsabelleMLException =>
//         result3 = "failed for prove eq1 using `by auto`"
//     }
//     assert (result3 == "failed for prove eq1 using `by auto`")
//   }

//   test("Use `sorry` to skip the proof") {
//     val proof_string3 = "sorry"
//     val result4: String = isa_repl.step(proof_string3)
//     assert (result4.contains("x ^ 3 = x * x * x"))
//   }

//   test("Declare the lemma again") {
//     val proof_string4 = "have eq2: \"x ^ 2 = x * x\""
//     val result5: String = isa_repl.step(proof_string4)
//     assert (result5.contains("x\\<^sup>2 = x * x"))
//   }

//   test("Prove the lemma again") {
//     val proof_string5 = "by (simp add: power2_eq_square)"
//     val result6: String = isa_repl.step(proof_string5)
//     assert (result6.contains("x ^ 3 = x * x * x"))
//   }

//   test("Close the proof") {
//     val proof_string6 = "show ?thesis by (simp add: numeral_eq_Suc)"
//     val result7: String = isa_repl.step(proof_string6)
//     assert (result7.contains("No subgoals!"))
//     isa_repl.step("qed")
//   }

}
