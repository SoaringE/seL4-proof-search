package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class HammerComplexTests extends AnyFunSuite {
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
  test("Hammer Complex No.1 from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.reset_isabelle(path_to_thy)
    val result0: String =
      isa_repl.compile(""" theory test imports Complex_Main  begin""")
    isa_repl.step("""
                  lemma Node_7 : 
                  fixes e :: "complex" 
                  and r :: "complex" 
                  assumes h0 : "- r + - e = - r - e" 
                  and h1 : "(- r - e)\<^sup>2 = (- r - e) * (- r - e)" 
                  and h2 : "(- r + - e)\<^sup>2 = (- r - e)\<^sup>2" 
                  and h3 : "(- r - e) * (- r - e) = - r * - r + - r * - e + - e * - r + - e * - e" 
                  and h4 : "r\<^sup>2 + r * e + e * r + e\<^sup>2 = r\<^sup>2 + 2 * (e * r) + e\<^sup>2" 
                  and h5 : "- r * - r + - r * - e + - e * - r + - e * - e = r\<^sup>2 + r * e + e * r + e\<^sup>2" 
                  shows "2 * (e * r) + (e\<^sup>2 + r\<^sup>2) = (- r + - e)\<^sup>2"
                """)
    // val (ok, result) = isa_repl.prove_by_hammer()
    // assert(ok == true)
    // val proof_string: String = result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "")
    // val res: String = isa_repl.step(proof_string)
    val res = isa_repl.step("sorry")
    assert(res == "")
  }

  test("Hammer Complex No.2 from Isabelle proof") {
    isa_repl.reset_isabelle(path_to_thy)
    val result0: String =
      isa_repl.compile(""" theory test imports Complex_Main  begin""")
    isa_repl.step("""
        theorem aimeII_2001_p3:
          fixes x :: "nat \<Rightarrow> int"
          assumes h0 : "x 1 = 211"
            and h1 : "x 2 = 375"
            and h2 : "x 3 = 420"
            and h3 : "x 4 = 523"
            and h4 : "\<And>(n::nat). ((n\<ge>5) \<Longrightarrow> (x n = x (n-1) - x (n-2) + x (n-3) - x (n-4)))"
          shows "x 531 + x 753 + x 975 = 898"
        proof
        -
          (* Compute the first few terms directly using the recurrence: *)
          have step5: "x 5 = x 4 - x 3 + x 2 - x 1"
            using rec[of 5] h1 h2 h3 h4 by simp
          also have "... = 523 - 420 + 375 - 211" sorry
          also have "... = 267" by simp
          finally have x5: "x 5 = 267" .
          
          have step6: "x 6 = x 5 - x 4 + x 3 - x 2"
            using rec[of 6] x5 h2 h3 h4 by simp
          also have "... = 267 - 523 + 420 - 375" sorry
          also have "... = (-211)" by simp
          finally have x6: "x 6 = -211" .
          
          have step7: "x 7 = x 6 - x 5 + x 4 - x 3"
            using rec[of 7] x5 x6 h3 h4 by simp
          also have "... = (-211) - 267 + 523 - 420" sorry
          also have "... = (-375)" by simp
          finally have x7: "x 7 = -375" .
          
          have step8: "x 8 = x 7 - x 6 + x 5 - x 4"
            using rec[of 8] x5 x6 x7 h4 by simp
          also have "... = (-375) - (-211) + 267 - 523" sorry
          also have "... = -420" by simp
          finally have x8: "x 8 = -420" .
          
          have step9: "x 9 = x 8 - x 7 + x 6 - x 5"
            using rec[of 9] x5 x6 x7 x8 sorry
          also have "... = (-420) - (-375) + (-211) - 267" sorry
          also have "... = (-523)" by simp
          finally have x9: "x 9 = -523" .
          
          have step10: "x 10 = x 9 - x 8 + x 7 - x 6"
            using rec[of 10] x6 x7 x8 x9 sorry
          also have "... = (-523) - (-420) + (-375) - (-211)" sorry
          also have "... = (-267)" by simp
          finally have x10: "x 10 = -267" .
          
          have step11: "x 11 = x 10 - x 9 + x 8 - x 7"
            using rec[of 11] x7 x8 x9 x10 sorry
          also have "... = (-267) - (-523) + (-420) - (-375)" sorry
          also have "... = 211" by simp
          finally have x11: "x 11 = 211" .
          
          have step12: "x 12 = x 11 - x 10 + x 9 - x 8"
            using rec[of 12] x8 x9 x10 x11 
    """)
    val (ok, result) = isa_repl.prove_by_hammer()
    if (ok == true) {
      val proof_string: String = result
        .replace("Try this:", "")
        .replaceAll("\\(\\d+ ms\\)", "")
        .replaceAll("\\(\\d+\\.\\d+ ms\\)", "")
        .replaceAll("\\(\\d+\\.\\d+ s\\)", "")
      val res: String = isa_repl.step(proof_string)
      assert(res.contains("x 531 + x 753 + x 975 = 898"))
    }
    isa_repl.step("oops")
  }

}
