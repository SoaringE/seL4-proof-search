package RunIsar

import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Paths
import RunIsar.IsaREPL
import RunIsar.Exceptions.IsabelleMLException

class TryCloseTests extends AnyFunSuite {
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
  test("try 0 No.1 from Isabelle proof") {
    // create the theorem to be proved
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
    val (ok, result) = isa_repl.try_close()
    val proof_string: String =
      result.replace("Try this:", "").replaceAll("\\(\\d+ ms\\)", "")
    val res: String = isa_repl.step(proof_string)
    assert(res == "")
  }

  // // test 1
  // test("try 0 No.2 from Isabelle proof") {
  //   // create the theorem to be proved
  //   isa_repl.step("""
  //       theorem fixes n k :: nat assumes "n / k < 6" and "5 < n / k" shows "22 \<le> (lcm n k) / (gcd n k)"
  //         proof -
  //           have "k \<noteq> 0"
  //             proof
  //               assume "k = 0"
  //               have "(of_nat n) / (of_nat k) = 0"
  //                 using \<open>k = 0\<close> \<open>5 < real n / real k\<close> \<open>real n / real k < 6\<close> by simp
  //               show False
  //                 using \<open>k = 0\<close> \<open>of_nat n / of_nat k = 0\<close> \<open>5 < real n / real k\<close> \<open>real n / real k < 6\<close> by simp
  //               qed
  //           have k_pos: "k > 0"
  //             using \<open>k \<noteq> 0\<close> by force
  //           have "n \<noteq> 0"
  //             proof
  //               assume "n = 0"
  //               have "(of_nat n) / (of_nat k) = 0"
  //                 using \<open>n = 0\<close> sorry
  //               show False
  //                 sorry
  //               qed
  //           have n_pos: "n > 0"
  //             using \<open>n \<noteq> 0\<close> by force
  //           obtain d a b where d_def: "d = gcd n k" and n_fact: "n = d * a" and k_fact: "k = d * b" and coprime: "gcd a b = 1"
  //             using n_pos k_pos
  //               """)

  //   val result =
  //     try{
  //       isa_repl.try_close(12000000)
  //     } catch {
  //       case e: IsabelleMLException =>
  //         println(e)
  //         ""
  //     }
  //   println(result)
  //   val res: String = isa_repl.step("oops")
  //   assert(res == "")
  // }
}
