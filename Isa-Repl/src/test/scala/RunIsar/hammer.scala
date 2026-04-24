package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL

class HammerTests extends AnyFunSuite {
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
  test("Hammer No.1 from Isabelle proof") {
    // create the theorem to be proved
    isa_repl.step("""
                lemma test: fixes a b :: real
                assumes ha : "a > 0" and hb : "b > 0"
                shows   "a + b > 0"
                proof-
                  show ?thesis
                """)
    val (ok, result) = isa_repl.prove_by_hammer()
    assert(ok == true)
    val proof_string: String =
      result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "")
    val res: String = isa_repl.step(proof_string)
    assert(res.contains("No subgoals!"))
    isa_repl.step("qed")
  }

  test("Hammer No.2 from Isabelle proof") {
    isa_repl.step("""
        lemma Node_71 : 
        fixes d :: "nat" 
        and k :: "nat" 
        and n :: "nat" 
        and b :: "nat" 
        and a :: "nat" 
        and thesis :: "bool" 
        assumes h0 : "0 < d" 
        and h1 : "0 < k" 
        and h2 : "0 < n" 
        and h3 : "k \<noteq> 0" 
        and h4 : "n \<noteq> 0" 
        and h5 : "d = gcd n k" 
        and h6 : "k = d * b" 
        and h7 : "n = d * a" 
        and h8 : "gcd a b = 1" 
        and h9 : "2 \<le> b" 
        and h10 : "3 \<le> b" 
        and h11 : "b \<noteq> 2" 
        and h12 : "lcm n k = d * a * b" 
        and h13 : "5 < real n / real k" 
        and h14 : "real n / real k < 6" 
        and h15 : "5 * b + 1 \<le> a" 
        and h16 : "of_nat n / of_nat k = of_nat a / of_nat b" 
        and h17 : "lcm n k div gcd n k = a * b" 
        and h18 : "48 \<le> a * b" 
        and h19 : "(5 * b + 1) * b \<le> a * b" 
        and h20 : "16 \<le> 5 * b + 1" 
        and h21 : "48 \<le> (5 * b + 1) * b" 
        and h22 : "5 * 3 + 1 \<le> 5 * b + 1" 
        and h23 : "(5) < of_nat a / of_nat b \<and> of_nat a / of_nat b < (6)" 
        and h24 : "(5) * of_nat b < of_nat a \<and> of_nat a < (6) * of_nat b" 
        and h25 : "16 * 3 \<le> (5 * b + 1) * b" 
        and h26 : "(\<And>d a b. \<lbrakk>d = gcd n k; n = d * a; k = d * b; gcd a b = 1\<rbrakk> \<Longrightarrow> thesis) \<Longrightarrow> thesis" 
        shows "22 \<le> a * b"
        """)
    val (ok, result) = isa_repl.prove_by_hammer()
    if (ok == true) {
      val proof_string: String =
        result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "")
      val res: String = isa_repl.step(proof_string)
      assert(res == "")
    }
  }
}
