package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class ExtractHammerFactsTests extends AnyFunSuite {
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

  isa_repl.step("lemma fixes x :: int shows \"x ^ 3 = x * x * x\"")

  // test 1
  test("extract notforall goal from Isabelle proof") {
    // create the theorem to be proved
    val result1 = isa_repl.extract_hammer_facts()
    assert(result1.contains("mepo"))

    // extract again
    val result2 = isa_repl.extract_hammer_facts()
    assert(result2.contains("mepo"))

    // close the proof by a step
    val proof_step = "    using power3_eq_cube by auto"
    isa_repl.step(proof_step)

    // start a new lemma
    val theorem = "lemma double_zero: \"2 * a = 0 ==> a = 0\" \n for a :: nat\n"
    isa_repl.step(theorem)

    // extract
    val result3 = isa_repl.extract_hammer_facts()
    assert(result3.contains("mepo"))

    // extract again
    val result4 = isa_repl.extract_hammer_facts()
    assert(result4.contains("mepo"))
  }

}
