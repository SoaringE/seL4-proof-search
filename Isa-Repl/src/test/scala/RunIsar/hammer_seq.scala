package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class HammerSeqTests extends AnyFunSuite {
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

  val result0: String =
    isa_repl.compile(""" theory test imports Complex_Main begin""")
  isa_repl.step("""
                theorem aimeII_2001_p3:
                fixes x :: "nat \<Rightarrow> int"
                assumes h0 : "x 1 = 211"
                and h1 : "x 2 = 375"
                and h2 : "x 3 = 420"
                and h3 : "x 4 = 523"
                and h4 : "\<And>(n::nat). ((n\<ge>5) \<Longrightarrow> (x n = x (n-1) - x (n-2) + x (n-3) - x (n-4)))"
                shows "x 531 + x 753 + x 975 = 898"
                proof -
                """)

  // test 1
  test("Hammer Step.1 from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("have step5: \"x 5 = x 4 - x 3 + x 2 - x 1\"")
    val (ok, result) = isa_repl.prove_by_hammer()
    if (ok == true) {
      val proof_string: String = result
        .replace("Try this:", "")
        .replaceAll("\\(\\d+ ms\\)", "")
        .replaceAll("\\(\\d+.\\d+ ms\\)", "")
        .replaceAll("\\(\\d+.\\d+ s\\)", "")
      val res: String = isa_repl.step(proof_string)
      assert(res.contains("x 531 + x 753 + x 975 = 898"))
    }
  }

  // test("Hammer Step.1.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 523 - 420 + 375 - 211\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.1.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 267\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.1.3 from Isabelle proof") {
  //   isa_repl.step("finally have x5: \"x 5 = 267\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.2 from Isabelle proof") {
  //   isa_repl.step("have step6: \"x 6 = x 5 - x 4 + x 3 - x 2\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.2.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 267 - 523 + 420 - 375\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.2.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-211)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.2.3 from Isabelle proof") {
  //   isa_repl.step("finally have x6: \"x 6 = -211\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.3 from Isabelle proof") {
  //   isa_repl.step("have step7: \"x 7 = x 6 - x 5 + x 4 - x 3\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.3.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-211) - 267 + 523 - 420\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.3.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-375)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.3.3 from Isabelle proof") {
  //   isa_repl.step("finally have x7: \"x 7 = -375\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.4 from Isabelle proof") {
  //   isa_repl.step("have step8: \"x 8 = x 7 - x 6 + x 5 - x 4\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.4.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-375) - (-211) + 267 - 523\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.4.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = -420\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.4.3 from Isabelle proof") {
  //   isa_repl.step("finally have x8: \"x 8 = -420\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.5 from Isabelle proof") {
  //   isa_repl.step("have step9: \"x 9 = x 8 - x 7 + x 6 - x 5\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.5.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-420) - (-375) + (-211) - 267\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.5.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-523)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.5.3 from Isabelle proof") {
  //   isa_repl.step("finally have x9: \"x 9 = -523\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.6 from Isabelle proof") {
  //   isa_repl.step("have step10: \"x 10 = x 9 - x 8 + x 7 - x 6\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.6.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-523) - (-420) + (-375) - (-211)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.6.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-267)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.6.3 from Isabelle proof") {
  //   isa_repl.step("finally have x10: \"x 10 = -267\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.7 from Isabelle proof") {
  //   isa_repl.step("have step11: \"x 11 = x 10 - x 9 + x 8 - x 7\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.7.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = (-267) - (-523) + (-420) - (-375)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.7.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 211\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.7.3 from Isabelle proof") {
  //   isa_repl.step("finally have x11: \"x 11 = 211\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.8 from Isabelle proof") {
  //   isa_repl.step("have step12: \"x 12 = x 11 - x 10 + x 9 - x 8\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   println(proof_string)
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.8.1 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 211 - (-267) + (-523) - (-420)\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.8.2 from Isabelle proof") {
  //   isa_repl.step("also have \"... = 375\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  // test("Hammer Step.8.3 from Isabelle proof") {
  //   isa_repl.step("finally have x12: \"x 12 = 375\"")
  //   val (ok, result) = isa_repl.prove_by_hammer(timeout_in_millis=300000)
  //   assert(ok == true)
  //   val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ ms\\)", "").replaceAll("\\(\\d+.\\d+ s\\)", "")
  //   val res: String = isa_repl.step(proof_string)
  //   assert(res.contains("x 531 + x 753 + x 975 = 898"))
  // }

  test("Hammer close proof") {
    isa_repl.step("oops")
  }

}
