package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL
import RunIsar.Exceptions.IsabelleMLException

class NitpickTests extends AnyFunSuite {
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
    isa_repl.compile(""" theory test imports Complex_Main begin """)

  // test 1
  test("nitpick No.1 from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
                  lemma "False"
                """)
    val (ok, result) = isa_repl.check_by_nitpick()
    println(result)
    assert(result == "Nitpick found a genuine counterexample")
    val res: String = isa_repl.step("sorry")
    assert(res == "")
  }

  // test 2
  test("nitpick No.2 from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
                  lemma "True"
                """)
    val (ok, result) = isa_repl.check_by_nitpick()
    println(result)
    assert(result == "Nitpick found no counterexample - goal appears valid")
  }

}
