package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL
import de.unruh.isabelle.control.IsabelleMLException

class ImportsThyTests extends AnyFunSuite {
  // get the value of isabelleHome_str from env variable ISABELLE_HOME. If not set, raise an error
  val isabelleHome_str: String = sys.env.getOrElse(
    "ISABELLE_HOME",
    throw new Exception("ISABELLE_HOME not set")
  )
  val isabelle_home: String = isabelleHome_str

  val path_to_thy: String =
    Paths.get("python-test/Test_Afp.thy").toAbsolutePath.toString
  val working_directory: String =
    Paths.get("python-test").toAbsolutePath.toString
  val isa_repl = new IsaREPL(
    isabelle_home = isabelle_home,
    path_to_thy = path_to_thy,
    working_directory = working_directory,
    debug = false
  )

  // test 1
  test("Compile the theory env") {
    val result0: String = isa_repl.compile(
      """ theory test_afp imports "HOL-Computational_Algebra.Computational_Algebra"
	    "HOL-Number_Theory.Number_Theory"  begin """
    )
    assert(result0 == "")
  }

  test("Create the theorem to be proved") {
    val theorem_string =
      "theorem mathd_numbertheory_303: \"(\\<Sum> k \\<in> {n ::nat. 2 \\<le> n \\<and> [171 = 80] (mod n) \\<and> [468 = 13] (mod n)}. k) = 111\""
    val result1: String = isa_repl.step(theorem_string)
    assert(
      result1.contains("proof (prove)") && result1.contains(
        "\\<Sum> {n. 2 \\<le> n \\<and> [171 = 80] (mod n) \\<and> [468 = 13] (mod n)} = 111"
      )
    )
    isa_repl.step("sorry")
  }

  test("Prove the theorem") {
    val steps = List(
      """ proof - """,
      """have A: "{n :: nat. 2 \<le> n \<and> n dvd 91 \<and> n dvd 455} \<subseteq> {7, 13, 91}"""",
      """proof""",
      """fix x :: nat""",
      """assume H: "x \<in> {n :: nat. 2 \<le> n \<and> n dvd 91 \<and> n dvd 455}""",
      """then have "x dvd 91" by simp""",
      """then obtain k :: nat where "91 = x * k" unfolding dvd_def by blast""",
      """then have "x \<in> {1,7,13,91}" by auto"""
    )
    for (step <- steps) {
      val result2: String = isa_repl.step(step)
      println(result2)
    }
  }

}
