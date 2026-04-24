package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class ParserTests extends AnyFunSuite {
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
  test("parse the theorem to steps") {
    // 2. create the theorem to be proved
    val theorem_string = """
        lemma 
        fixes x :: int 
        shows "x ^ 3 = x * x * x" 
        proof- 
          have eq1: "x ^ 2 = x * x" by auto
          have eq2: "x ^ 3 = x ^ 2 * x" by auto
          show ?thesis by (simp add: eq1 eq2)
        """
    val result1: String = isa_repl.parse_to_steps(theorem_string)
    val steps: List[String] = result1.split("<\\\\SEP>").toList
    assert(
      steps == List(
        "",
        "lemma fixes x :: int shows \"x ^ 3 = x * x * x\"",
        "proof-",
        "have eq1: \"x ^ 2 = x * x\"",
        "by auto",
        "have eq2: \"x ^ 3 = x ^ 2 * x\"",
        "by auto",
        "show ?thesis",
        "by (simp add: eq1 eq2)"
      )
    )
  }

}
