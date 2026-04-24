package RunIsar

import java.nio.file.{Path, Paths}
import scala.collection.JavaConverters._
import util.control.Breaks
import scala.collection.mutable.ListBuffer
import scala.concurrent.{
  Await,
  ExecutionContext,
  Future,
  TimeoutException,
  blocking
}
import scala.concurrent.duration.Duration
import scala.util.{Failure, Success}
import sys.process._
import _root_.java.nio.file.{Files, Path}
import _root_.java.io.File

import de.unruh.isabelle.control.{Isabelle, IsabelleMLException}
import de.unruh.isabelle.mlvalue.{
  AdHocConverter,
  MLFunction,
  MLFunction0,
  MLFunction2,
  MLFunction3,
  MLFunction4,
  MLFunction5,
  MLValue,
  MLValueWrapper,
  Version
}
import de.unruh.isabelle.mlvalue.MLValue.{
  compileFunction,
  compileFunction0,
  compileValue
}
import de.unruh.isabelle.pure.{
  Context,
  Position,
  Theory,
  TheoryHeader,
  ToplevelState
}

// import RunIsar.TheoryManager
import RunIsar.TheoryManager.{Ops, Source, Text}
import RunIsar.TempFileManager.{createTempDir, copyResources, cleanupAll}
import RunIsar.RunIsarMLException
// Implicits
import de.unruh.isabelle.mlvalue.Implicits._
import de.unruh.isabelle.pure.Implicits._

object Transition extends AdHocConverter("Toplevel.transition")
object ProofState extends AdHocConverter("Proof.state")
object RuntimeError extends AdHocConverter("Runtime.error")
object Pretty extends AdHocConverter("Pretty.T")
object ProofContext extends AdHocConverter("Proof_Context.T")

/** Main class for the Isabelle REPL (Read-Eval-Print Loop).
  * @param isabelle_home:
  *   path to an Isabelle installation. Normally it equals to the ISABELLE_HOME
  *   env within isabelle's runtime. It is expected to contain 'bin/isabelle'
  * @param path_to_thy:
  *   path to a thy file to be loaded.
  * @param working_directory:
  *   path to a working directory where the underlying 'isabelle build ...'
  *   process will look for ROOT/ROOTS files and .thys.
  * @param session:
  *   the Isabelle session to be built. It will pass to the underlying 'isabelle
  *   build ...' process. Default is "HOL".
  * @param session_roots:
  *   additional directories where the underlying 'isabelle build ...' process
  *   will look for Isabelle sessions.
  */
//noinspection TypeAnnotation,ScalaUnusedSymbol
class IsaREPL(
    var isabelle_home: String,
    var path_to_thy: String,
    var working_directory: String,
    var session: String = "HOL",
    var session_roots: List[String] = Nil,
    var debug: Boolean = false
) {
  if (debug) println("Checkpoint 1: Isabelle setup")
  // Prepare setup config and the implicit Isabelle context
  var currentTheoryName: String =
    path_to_thy.split("/").last.replace(".thy", "")
  val isabelleHome: Path = Paths.get(isabelle_home)
  val setup: Isabelle.Setup = Isabelle.Setup(
    isabelleHome = isabelleHome,
    workingDirectory = Path.of(working_directory),
    logic = session,
    sessionRoots = session_roots.map(s => Path.of(s))
  )
  implicit val isabelle: Isabelle = new Isabelle(setup)
  implicit val ec: ExecutionContext = ExecutionContext.global
  if (debug) println("Checkpoint 2: Compile ML functions")
  // Load Auto_Isabelle theory from the correct path
  val tempDir = createTempDir("isar_temp")
  copyResources("RunIsar/isabelle/AutoIsar", tempDir)
  val autoIsaPath_tmp = new File(tempDir, "Auto_Isabelle.thy").getAbsolutePath
  val autoIsaPath = Paths.get(autoIsaPath_tmp)
  val thy0 = Theory(autoIsaPath)
  val Auto_Isabelle: String = thy0.importMLStructureNow("Auto_Isabelle")
  // Compile useful ML functions
  val num_of_processors: MLFunction0[Int] =
    compileFunction0[Int]("fn _ => Multithreading.num_processors ()")
  val num_of_threads: MLFunction0[Int] =
    compileFunction0[Int]("fn _ => Multithreading.max_threads ()")
  // Compile useful ML functions
  val script_thy: MLFunction2[String, Theory, Theory] =
    compileFunction[String, Theory, Theory](
      "fn (str,thy) => Thy_Info.script_thy Position.none str thy"
    )
  val init_toplevel: MLFunction0[ToplevelState] =
    if (Version.from2023)
      compileFunction0[ToplevelState]("fn _ => Toplevel.make_state NONE")
    else
      compileFunction0[ToplevelState]("Toplevel.init_toplevel")
  val is_proof: MLFunction[ToplevelState, Boolean] =
    compileFunction[ToplevelState, Boolean]("Toplevel.is_proof")
  val is_skipped_proof: MLFunction[ToplevelState, Boolean] =
    compileFunction[ToplevelState, Boolean]("Toplevel.is_skipped_proof")
  val proof_level: MLFunction[ToplevelState, Int] =
    compileFunction[ToplevelState, Int]("Toplevel.level")
  val proof_of: MLFunction[ToplevelState, ProofState.T] =
    compileFunction[ToplevelState, ProofState.T]("Toplevel.proof_of")
  val command_exception
      : MLFunction3[Boolean, Transition.T, ToplevelState, ToplevelState] =
    compileFunction[Boolean, Transition.T, ToplevelState, ToplevelState](
      "fn (int, tr, st) => Toplevel.command_exception int tr st"
    )
  val command_exception_with_10s_timeout
      : MLFunction3[Boolean, Transition.T, ToplevelState, ToplevelState] =
    compileFunction[Boolean, Transition.T, ToplevelState, ToplevelState](
      """fn (int, tr, st) => let
        |  fun go_run (a, b, c) = Toplevel.command_exception a b c
        |  in Timeout.apply (Time.fromSeconds 10) go_run (int, tr, st) end""".stripMargin
    )
  val command_exception_with_30s_timeout
      : MLFunction3[Boolean, Transition.T, ToplevelState, ToplevelState] =
    compileFunction[Boolean, Transition.T, ToplevelState, ToplevelState](
      """fn (int, tr, st) => let
        |  fun go_run (a, b, c) = Toplevel.command_exception a b c
        |  in Timeout.apply (Time.fromSeconds 30) go_run (int, tr, st) end""".stripMargin
    )
  val command_errors: MLFunction3[
    Boolean,
    Transition.T,
    ToplevelState,
    (List[RuntimeError.T], Option[ToplevelState])
  ] = compileFunction[
    Boolean,
    Transition.T,
    ToplevelState,
    (List[RuntimeError.T], Option[ToplevelState])
  ]("fn (int, tr, st) => Toplevel.command_errors int tr st")
  val toplevel_end_theory: MLFunction[ToplevelState, Theory] =
    compileFunction[ToplevelState, Theory]("Toplevel.end_theory Position.none")
  val theory_of_state: MLFunction[_, _] =
    if (Version.from2023)
      compileFunction[Theory, ToplevelState]("Toplevel.make_state o SOME")
    else
      compileFunction[ToplevelState, Theory]("Toplevel.theory_of")
  val context_of_state: MLFunction[ToplevelState, Context] =
    compileFunction[ToplevelState, Context]("Toplevel.context_of")
  val name_of_transition: MLFunction[Transition.T, String] =
    compileFunction[Transition.T, String]("Toplevel.name_of")
  val parse_text: MLFunction2[Theory, String, List[(Transition.T, String)]] =
    compileFunction[Theory, String, List[(Transition.T, String)]]("""fn (thy, text) => let
        |  val transitions = Outer_Syntax.parse_text thy (K thy) Position.start text
        |  fun addtext symbols [tr] =
        |        [(tr, implode symbols)]
        |    | addtext _ [] = []
        |    | addtext symbols (tr::nextTr::trs) = let
        |        val (this,rest) = Library.chop (Position.distance_of (Toplevel.pos_of tr, Toplevel.pos_of nextTr) |> Option.valOf) symbols
        |        in (tr, implode this) :: addtext rest (nextTr::trs) end
        |  in addtext (Symbol.explode text) transitions end""".stripMargin)
  val toplevel_string_of_state: MLFunction[ToplevelState, String] =
    compileFunction[ToplevelState, String](
      "fn (s) => XML.content_of (YXML.parse_body (Toplevel.string_of_state s))"
    )
  val pretty_local_facts: MLFunction2[ToplevelState, Boolean, List[Pretty.T]] =
    compileFunction[ToplevelState, Boolean, List[Pretty.T]](
      "fn (tls, b) => Proof_Context.pretty_local_facts b (Toplevel.context_of tls)"
    )
  val make_pretty_list_string_list: MLFunction[List[Pretty.T], List[String]] =
    compileFunction[List[Pretty.T], List[String]](
      "fn (pretty_list) => map Pretty.unformatted_string_of pretty_list"
    )

  val local_facts_and_defs: MLFunction[ToplevelState, List[(String, String)]] =
    compileFunction[ToplevelState, List[(String, String)]](
      """fn tls =>
        |  let val ctxt = Toplevel.context_of tls;
        |      val facts = Proof_Context.facts_of ctxt;
        |      val props = map #1 (Facts.props facts);
        |      val local_facts =
        |        (if null props then [] else [("unnamed", props)]) @
        |        Facts.dest_static true [Global_Theory.facts_of (Proof_Context.theory_of ctxt)] facts;
        |      val thms = (
        |           if null local_facts then []
        |           else
        |           (map (fn e => #2 (#2 e)) (sort_by (#1 o #2) (map (`(Proof_Context.pretty_fact ctxt)) local_facts))));
        |      val condensed_thms = fold (fn x => fn y => (x @ y)) thms [];
        |  in 
        |      map (fn thm => (
        |            Thm.get_name_hint thm,
        |            Pretty.unformatted_string_of
        |          (Element.pretty_statement ctxt "" thm)
        |         ))
        |         condensed_thms
        |  end""".stripMargin
    )
  val global_facts_and_defs: MLFunction[ToplevelState, List[(String, String)]] =
    compileFunction[ToplevelState, List[(String, String)]](
      """fn tls =>
          | map (fn tup => (#1 tup, Pretty.unformatted_string_of (Element.pretty_statement (Toplevel.context_of tls) "test" (#2 tup))))
          | (Global_Theory.all_thms_of (Proof_Context.theory_of (Toplevel.context_of tls)) false)
          """.stripMargin
    )
  val fact_definition: MLFunction2[ToplevelState, String, String] =
    compileFunction[ToplevelState, String, String](
      """fn (tls, name) =>
        | let val ctxt = Toplevel.context_of tls;
        |     val thm = Global_Theory.get_thms (Proof_Context.theory_of ctxt) name;
        | in
        |     YXML.content_of (Pretty.unformatted_string_of (Element.pretty_statement ctxt "" (hd thm)))
        | end""".stripMargin
    )
  def fact_definition(tls_name: String, theorem_name: String): String = {
    val toplevel_state = retrieve_tls(tls_name)
    fact_definition(toplevel_state, theorem_name).force.retrieveNow
  }

  val get_dependent_thms: MLFunction2[ToplevelState, String, List[String]] =
    compileFunction[ToplevelState, String, List[String]](
      """fn (tls, name) =>
        | let val thy = Toplevel.theory_of tls;
        |     val thm = Global_Theory.get_thms thy name;
        | in
        |     map (fn x => (#1 (#2 x))) (Thm_Deps.thm_deps thy thm)
        | end""".stripMargin
    )
  val get_dependent_thms_with_thy_names
      : MLFunction2[ToplevelState, String, List[String]] =
    compileFunction[ToplevelState, String, List[String]](
      """fn (tls, name) =>
        | let val thy = Toplevel.theory_of tls;
        |     val thm = Global_Theory.get_thms thy name;
        | in
        |     map (fn x => String.concat [#theory_name (#1 x), "<\\INNER_SEP>", (#1 (#2 x))]) (Thm_Deps.thm_deps thy thm)
        | end""".stripMargin
    )
  def get_dependent_theorems(
      tls_name: String,
      theorem_name: String
  ): List[String] = {
    val toplevel_state = retrieve_tls(tls_name)
    // println("Retrieved top level")
    try {
      val dependent_thms =
        get_dependent_thms(toplevel_state, theorem_name).force.retrieveNow
      return dependent_thms
    } catch {
      case e: IsabelleMLException =>
        println("Name not found. Trying locales.")
        throw e
      case o: Throwable => println(o); throw o
    }
    val relevant_locales = locales_defined_in_file(toplevel_state)
    // println(relevant_locales)

    var dep_thms: List[String] = List()

    Breaks.breakable {
      for (relevant_locale <- relevant_locales) {
        println("Trying locale: " + relevant_locale)
        val full_name = relevant_locale.trim + '.' + theorem_name
        // println(s"Trying out full name: ${full_name}")
        try {
          val dependent_thms =
            get_dependent_thms(toplevel_state, full_name).force.retrieveNow
          dep_thms = dependent_thms
          println("This locale works: " + relevant_locale)
          Breaks.break()
        } catch {
          case e: Throwable => println(e)
        }
      }
    }

    dep_thms
  }

  def get_dependent_theorems_with_theory_names(
      tls_name: String,
      theorem_name: String
  ): List[String] = {
    val toplevel_state = retrieve_tls(tls_name)
    // println("Retrieved top level")
    try {
      val dependent_thms =
        get_dependent_thms_with_thy_names(
          toplevel_state,
          theorem_name
        ).force.retrieveNow
      return dependent_thms
    } catch {
      case e: IsabelleMLException =>
        println("Name not found. Trying locales.")
        throw new RunIsarMLException(e)
      case o: Throwable =>
        println(o);
        throw o
    }
  }

  val get_used_consts: MLFunction2[ToplevelState, String, List[String]] =
    compileFunction[ToplevelState, String, List[String]](
      """fn(tls, inner_syntax) =>
        |let
        |  val term_to_list = fn te =>
        |  let
        |     fun leaves (left $ right) = (leaves left) @ (leaves right)
        |     |   leaves t = [t];
        |     fun filter_out (Const ("_type_constraint_", _)) = false
        |     | filter_out (Const _) = true
        |     | filter_out _ = false;
        |     val all_leaves = leaves te;
        |     val filtered_leaves = filter filter_out all_leaves;
        |     fun remove(_, []) = []
        |       | remove(x, y::l) =
        |         if x = y then
        |           remove(x, l)
        |         else
        |           y::remove(x, l);
        |      fun removeDup [] = []
        |        | removeDup(x::l) = x::removeDup(remove(x, l));
        |      fun string_of_term (Const (s, _)) = s
        |        | string_of_term _ = "";
        |  in
        |      removeDup (map string_of_term filtered_leaves)
        |  end;
        |
        |  val type_to_list = fn ty =>
        |  let
        |    fun type_t (Type ty) = [#1 ty] @ (flat (map type_t (#2 ty)))
        |    | type_t (TFree _) = []
        |    | type_t (TVar _) = [];
        |    fun filter_out_universal_type_symbols symbol =
        |  case symbol of
        |    "fun" => false
        |    | "prop" => false
        |    | "itself" => false
        |    | "dummy" => false
        |    | "proof" => false
        |    | "Pure.proof" => false
        |    | _ => true;
        |  in
        |    filter filter_out_universal_type_symbols (type_t ty)
        |  end;
        |  val ctxt = Toplevel.context_of tls;
        |  val flex = fn str =>
        |   (type_to_list (Syntax.parse_typ ctxt str))
        |   handle _ => (term_to_list (Syntax.parse_term ctxt str));
        |in
        |  flex inner_syntax
        |end""".stripMargin
    )
  def get_all_definitions(
      tls_name: String,
      theorem_string: String
  ): List[String] = {
    val toplevel_state = retrieve_tls(tls_name)
    val quotation_split: List[String] = theorem_string.split('"').toList
    val all_inner_syntax = quotation_split.indices
      .collect { case i if i % 2 == 1 => quotation_split(i) }
      .filter(x => x.nonEmpty)
      .toList
    val all_defs = all_inner_syntax.map(x =>
      get_used_consts(toplevel_state, x).force.retrieveNow
    )
    val deduplicated_all_defs: List[String] = all_defs.flatten
    deduplicated_all_defs.distinct
  }
  // Nasty locales
  val locales_opened_for_state: MLFunction[ToplevelState, List[String]] =
    compileFunction[ToplevelState, List[String]](
      """fn (tls) => Locale.get_locales (Toplevel.theory_of tls)""".stripMargin
    )

  def locales_defined_in_file(tls: ToplevelState): List[String] = {
    val locales_opened: List[String] = locales_opened_for_state(
      tls
    ).force.retrieveNow
    locales_opened.filter(_.startsWith(currentTheoryName))
  }

  def local_facts_and_defs_string(tls: ToplevelState): String =
    local_facts_and_defs(tls).force.retrieveNow.distinct
      .map(x => x._1 + "<DEF>" + x._2)
      .mkString("<SEP>")
  def local_facts_and_defs_string(tls_name: String): String = {
    val tls = retrieve_tls(tls_name)
    try {
      local_facts_and_defs_string(tls)
    } catch {
      case e: Throwable => e.toString
    }
  }
  def global_facts_and_defs_string(tls: ToplevelState): String =
    global_facts_and_defs(tls).force.retrieveNow.distinct
      .map(x => x._1 + "<DEF>" + x._2)
      .mkString("<SEP>")
  def global_facts_and_defs_string(tls_name: String): String = {
    val tls = retrieve_tls(tls_name)
    try {
      global_facts_and_defs_string(tls)
    } catch {
      case e: Throwable => e.toString
    }
  }
  def total_facts_and_defs_string(tls: ToplevelState): String = {
    val local_facts = local_facts_and_defs(tls).force.retrieveNow
    val global_facts = global_facts_and_defs(tls).force.retrieveNow
    (local_facts ++ global_facts).distinct
      .map(x => x._1 + "<DEF>" + x._2)
      .mkString("<SEP>")
  }
  def total_facts_and_defs_string(tls_name: String): String = {
    val tls = retrieve_tls(tls_name)
    total_facts_and_defs_string(tls)
  }

  /** Extracts the current variables, assumptions and conclusion from the proof
    * state.
    *
    * This function takes a ToplevelState and returns a tuple containing:
    *   - A list of strings representing the current assumptions (local facts)
    *   - A string representing the current proof goal (conclusion)
    *
    * The output is formatted as human-readable text, with XML markup removed.
    */
  val parse_vars: MLFunction[ToplevelState, List[String]] =
    compileFunction[ToplevelState, List[String]](
      s"""fn (toplevel_state) =>
        |  let
        |    val p_state = Toplevel.proof_of toplevel_state;
        |    val ctxt = Proof.context_of p_state;
        |    val {context = _, facts, goal} = Proof.goal p_state;
        |  
        |  (* Get all assumptions from the context *)
        |  val assumptions = Facts.props (Proof_Context.facts_of ctxt) |> map #1;
        |  val props = map Thm.prop_of assumptions;
        |  
        |  (* Helper functions for variable processing *)
        |  fun sort_idxs vs = map (apsnd (sort (prod_ord string_ord int_ord))) vs;
        |  
        |  fun ins_entry (x, y) = 
        |    AList.default (op =) (x, []) #> AList.map_entry (op =) x (insert (op =) y);
        |  
        |  (* Collect variables from terms *)
        |  val add_vars = Term.fold_aterms 
        |    (fn Free (x, T) => ins_entry (T, (x, ~1))
        |     | Var (xi, T) => ins_entry (T, xi)
        |     | _ => I);
        |  
        |  fun vars_of t = sort_idxs (add_vars t []);
        |  
        |  (* Pretty-printing functions *)
        |  val prt_term = singleton (Syntax.uncheck_terms ctxt) 
        |    #> Type_Annotation.ignore_free_types 
        |    #> Syntax.string_of_term ctxt;
        |  
        |  fun prt_var (x, ~1) = prt_term (Syntax.free x)
        |    | prt_var xi = prt_term (Syntax.var xi);
        |  
        |  val prt_typ = Syntax.string_of_typ ctxt;
        |  
        |  (* Format variable declarations *)
        |  fun prt_all (ty, vars) = 
        |    let
        |      val ty_str = prt_typ ty;
        |      fun print_var (name, idx) = prt_var (name, idx) ^ " :: " ^ ty_str
        |    in 
        |      map print_var vars 
        |    end;
        |  
        |  (* Process all propositions to extract variables *)
        |  val all_vars = maps vars_of props;
        |  val var_decls = maps prt_all all_vars;
        |  
        |  (* Final result with duplicates removed *)
        |  val res = var_decls 
        |    |> map $Auto_Isabelle.clean_theorem_text
        |    |> distinct (op =);
        |  in
        |    res
        |  end""".stripMargin
    )

  val parse_assms: MLFunction[ToplevelState, List[String]] =
    compileFunction[ToplevelState, List[String]](
      s"""fn (toplevel_state) =>
        | let
        |     (* Extract proof state and context *)
        |     val proof_state = Toplevel.proof_of toplevel_state;
        |     val proof_context = Proof.context_of proof_state;
        |
        |     (* Extract and format assumptions *)
        |     val assumptions = 
        |         Facts.props (Proof_Context.facts_of proof_context)
        |         |> map #1
        |         |> map (Thm.string_of_thm proof_context);
        | in
        |     map $Auto_Isabelle.clean_theorem_text assumptions
        | end""".stripMargin
    )

  val parse_goal: MLFunction[ToplevelState, String] =
    compileFunction[ToplevelState, String](
      s"""fn (toplevel_state) =>
        | let
        |     (* Extract proof state and context *)
        |     val proof_state = Toplevel.proof_of toplevel_state;
        |     val proof_context = Proof.context_of proof_state;
        |     val {context = _, facts = _, goal} = Proof.goal proof_state;
        |
        |     (* Extract and format conclusion *)
        |     val conclusion = 
        |       if not (Proof.goal_finished proof_state) then
        |         let
        |           val ({context = ctxt, prems = _, concl, ...}, _) = Subgoal.focus proof_context 1 NONE goal
        |       in
        |         Variable.revert_fixed ctxt (Syntax.string_of_term ctxt (Thm.term_of concl))
        |       end
        |       else
        |         ""
        | in
        |     $Auto_Isabelle.clean_theorem_text conclusion
        | end""".stripMargin
    )

  // check if the sub-proof is finished; if it is, then we can successfully retrieve it by `this`, and thus return true; otherwise, return false
  val parse_no_subgoals: MLFunction[ToplevelState, Boolean] =
    compileFunction[ToplevelState, Boolean](
      """fn (toplevel_state) =>
        | let
        |   val proof_state = Toplevel.proof_of toplevel_state;
        |   val {context = ctxt, facts = facts, goal = goal} = Proof.goal proof_state;
        |   val result = Thm.no_prems goal;
        | in
        |   result
        | end""".stripMargin
    )

  val parse_num_subgoals: MLFunction[ToplevelState, Int] =
    compileFunction[ToplevelState, Int](
      """fn (toplevel_state) =>
        | let
        |   val proof_state = Toplevel.proof_of toplevel_state;
        |   val {context = ctxt, facts = facts, goal = goal} = Proof.goal proof_state;
        |   val result = Thm.nprems_of goal;
        | in
        |   result
        | end""".stripMargin
    )

  // Find out about the starter string
  // filecontent is the content of thy file to be proved
  private var fileContent: String = Files.readString(Path.of(path_to_thy))
  var fileContentCopy: String = fileContent
  if (debug) println("File content: " + fileContent)

  var top_level_state_map: Map[String, MLValue[ToplevelState]] = Map()
  if (debug) println("Checkpoint 9: func begintheory")
  // Load the theory manager
  val theoryManager: TheoryManager = new TheoryManager(
    isabelle_home = isabelle_home,
    path_to_thy = path_to_thy,
    working_directory = working_directory,
    logic = session,
    sessionRoots = session_roots,
    isabelle = isabelle,
    debug = debug
  )

  var thy1: Theory = theoryManager.beginTheory()
  if (debug) println("Checkpoint 9_6: Loading theory")
  thy1.await
  if (debug) println("Checkpoint 10: Loading theory finished")

  // setting up SMT_translate
  val Skip_Proof: String = thy1.importMLStructureNow("Skip_Proof")
  val SMT_Config: String = thy1.importMLStructureNow("SMT_Config")
  val SMT_Normalize: String = thy1.importMLStructureNow("SMT_Normalize")
  val SMT_Util: String = thy1.importMLStructureNow("SMT_Util")
  val SMT_Translate: String = thy1.importMLStructureNow("SMT_Translate")
  val parse_to_smt: MLFunction[ToplevelState, String] =
    compileFunction[ToplevelState, String](
      s""" fn (state) =>  
            |    let  
            |       val p_state = Toplevel.proof_of state;
            |       val ctxt = Proof.context_of p_state;
            |       val {context = _, facts, goal} = Proof.goal p_state;
            |       val ({context = ctxt, prems, concl, ...}, _) = Subgoal.focus ctxt 1 NONE goal
            |
            |       val facts = Proof_Context.facts_of ctxt;
            |       val local_facts = map #1 (Facts.props facts);
            |       
            |       val not_const = Syntax.read_term ctxt "Not";
            |       val not_ct = Thm.cterm_of ctxt not_const;
            |       fun negate ct = Thm.dest_comb ct ||> Thm.apply not_ct |-> Thm.apply;
            |       val cprop = negate (Thm.rhs_of ($SMT_Normalize.atomize_conv ctxt concl));
            |       val conjecture = Thm.assume cprop;
            |
            |       val options = $SMT_Config.solver_options_of ctxt;
            |       val comments = [space_implode " " options];
            |       val has_topsort = Term.exists_type (Term.exists_subtype (fn
            |                             TFree (_, []) => true
            |                           | TVar  (_, []) => true
            |                           | _ => false));
            |       val TrueI = Proof_Context.get_thm ctxt "TrueI";
            |       fun check_topsort ctxt thm = 
            |         if has_topsort (Thm.prop_of thm) then ($SMT_Normalize.drop_fact_warning ctxt thm; TrueI) else thm;
            |
            |       val thms0 = prems @ local_facts;
            |       val thms = map (pair $SMT_Util.Axiom o check_topsort ctxt) thms0;
            |       val assms_thms = ($SMT_Normalize.normalize ctxt thms);
            |
            |       val thms0 = [conjecture];
            |       val thms = map (pair $SMT_Util.Conjecture o check_topsort ctxt) thms0;
            |       val conc_thms = ($SMT_Normalize.normalize ctxt thms);
            |
            |       val ithms = assms_thms @ conc_thms;
            |
            |       fun go_run () = 
            |         let 
            |           val (str_result, _) = $SMT_Translate.translate ctxt "z3" [] comments ithms
            |         in 
            |           str_result  end  
            |    in  
            |       Timeout.apply (Time.fromSeconds 180) go_run () end 
          |""".stripMargin
    )

  // setting up Sledgehammer
  // val thy_for_sledgehammer: Theory = Theory("HOL.List")
  val thy_for_sledgehammer = thy1
  val Sledgehammer: String =
    thy_for_sledgehammer.importMLStructureNow("Sledgehammer")
  val Sledgehammer_Commands: String =
    thy_for_sledgehammer.importMLStructureNow("Sledgehammer_Commands")
  val Sledgehammer_Prover: String =
    thy_for_sledgehammer.importMLStructureNow("Sledgehammer_Prover")
  // prove_with_Sledgehammer is mostly identical to check_with_Sledgehammer except for that when the returned Boolean is true, it will
  // also return a non-empty list of Strings, each of which contains executable commands to close the top subgoal. We might need to chop part of
  // the string to get the actual tactic. For example, one of the string may look like "Try this: by blast (0.5 ms)".
  if (debug) println("Checkpoint 11")
  val normal_with_Sledgehammer: MLFunction4[ToplevelState, Theory, List[
    String
  ], List[String], (Boolean, (String, List[String]))] =
    compileFunction[ToplevelState, Theory, List[String], List[
      String
    ], (Boolean, (String, List[String]))](
      s""" fn (state, thy, adds, dels) =>
            |    let
            |       fun get_refs_and_token_lists (name) = (Facts.named name, []);
            |       val adds_refs_and_token_lists = map get_refs_and_token_lists adds;
            |       val dels_refs_and_token_lists = map get_refs_and_token_lists dels;
            |       val override = {add=adds_refs_and_token_lists,del=dels_refs_and_token_lists,only=false};
            |       fun go_run (state, thy) =
            |          let
            |             val p_state = Toplevel.proof_of state;
            |             val ctxt = Proof.context_of p_state;
            |             val params = $Sledgehammer_Commands.default_params thy
            |                [("provers", "cvc5 vampire verit e spass z3 zipperposition"),
            |                 ("timeout","30"),
            |                 ("verbose","false")];
            |             val results = $Sledgehammer.run_sledgehammer params $Sledgehammer_Prover.Normal NONE 1 override p_state;
            |             val (result, (outcome, step)) = results;
            |           in
            |             (result, ($Sledgehammer.short_string_of_sledgehammer_outcome outcome, [YXML.content_of step]))
            |           end;
            |    in
            |      go_run (state, thy) end
            |""".stripMargin
    )

  val parse_hammer_facts: MLFunction5[ToplevelState, Theory, String, List[
    String
  ], List[String], String] =
    compileFunction[ToplevelState, Theory, String, List[String], List[
      String
    ], String](
      s"""fn (state, thy, filter, adds, dels) =>
        |    let
        |      val proof_state = Toplevel.proof_of state;
        |      val facts = $Auto_Isabelle.retrieve_facts proof_state thy filter adds dels;
        |    in
        |      facts
        |    end
        |""".stripMargin
    )

  val parse_hammer_facts_with_theory_names
      : MLFunction5[ToplevelState, Theory, String, List[String], List[
        String
      ], String] =
    compileFunction[ToplevelState, Theory, String, List[String], List[
      String
    ], String](
      s"""fn (state, thy, filter, adds, dels) =>
         |    let
         |      val proof_state = Toplevel.proof_of state;
         |      val facts = $Auto_Isabelle.retrieve_facts_with_theory_names proof_state thy filter adds dels;
         |    in
         |      facts
         |    end
         |""".stripMargin
    )

    val mash_relearn: MLFunction2[ToplevelState, Theory, Unit] =
    compileFunction[ToplevelState, Theory, Unit](
      s"""fn (state, thy) =>
         |    let
         |      val proof_state = Toplevel.proof_of state;
         |      val _ = $Auto_Isabelle.mash_relearn proof_state thy;
         |    in
         |      ()
         |    end
         |""".stripMargin
    )

  val normal_with_try0: MLFunction[ToplevelState, (Boolean, String, String)] =
    compileFunction[ToplevelState, (Boolean, String, String)](
      s""" fn (state) =>
        |        let
        |          val proof_state = Toplevel.proof_of state;
        |          val (success, method, step) = $Auto_Isabelle.try_close (Time.fromSeconds 10) proof_state;
        |        in
        |          (success, method, $Auto_Isabelle.clean_theorem_text step)
        |        end
        |""".stripMargin
    )

  val thy_for_nitpick = thy1
  val Nitpick: String =
    thy_for_nitpick.importMLStructureNow("Nitpick")
  val Nitpick_Commands: String =
    thy_for_nitpick.importMLStructureNow("Nitpick_Commands")
  val normal_with_NitPick: MLFunction2[ToplevelState, Theory, String] =
    compileFunction[ToplevelState, Theory, String](
      s"""fn (state, thy) =>
         |    let
         |      val (ok, str_result) = $Auto_Isabelle.try_nitpick (Time.fromSeconds 60) state thy;
         |    in
         |      str_result
         |    end
         |""".stripMargin
    )

  val thy_for_quickcheck = thy1
  val QuickCheck: String =
    thy_for_quickcheck.importMLStructureNow("Quickcheck")
  // val QuickCheck_Commands: String =
  //   thy_for_quickcheck.importMLStructureNow("Quickcheck_Commands")
  val normal_with_QuickCheck: MLFunction2[ToplevelState, Theory, String] =
    compileFunction[ToplevelState, Theory, String](
      s"""fn (state, thy) =>
         |    let
         |      val (ok, str_result) = $Auto_Isabelle.try_quickcheck (Time.fromSeconds 60) state thy;
         |    in
         |      str_result
         |    end
         |""".stripMargin
    )

  val parse_find_theorems: MLFunction4[ToplevelState, List[String], Int, Boolean, String] =
    compileFunction[ToplevelState, List[String], Int, Boolean, String](
      s"""fn (state, query_patterns, limit, rem_dups) =>
         |    let
         |      val opt_limit = if limit < 0 then NONE else SOME limit;
         |      val output = $Auto_Isabelle.find_theorems state query_patterns opt_limit rem_dups;
         |    in
         |      output
         |    end
         |""".stripMargin
    )

  var toplevel: ToplevelState = init_toplevel().force.retrieveNow
  if (debug) println("Checkpoint 12")
  def reset_map(): Unit = {
    top_level_state_map = Map()
  }

  def reset_problem(): Unit = {
    thy1 = theoryManager.beginTheory()
    toplevel = init_toplevel().force.retrieveNow
    reset_map()
  }

  def getFacts(stateString: String): String = {
    var facts: String = ""
    if (stateString.trim.nonEmpty) {
      // Limit the maximum number of local facts to be 5
      for (
        fact <- make_pretty_list_string_list(
          pretty_local_facts(toplevel, false)
        ).retrieveNow.takeRight(5)
      ) {
        facts = facts + fact + "<\\SEP>"
      }
    }
    facts
  }

  def getStateString(top_level_state: ToplevelState): String =
    toplevel_string_of_state(top_level_state).force.retrieveNow

  def getStateString: String = getStateString(toplevel)

  def is_done(top_level_state: ToplevelState): Boolean = {
    getProofLevel(top_level_state) == 0
  }

  def getProofLevel(top_level_state: ToplevelState): Int =
    proof_level(top_level_state).retrieveNow

  def getProofLevel: Int = getProofLevel(toplevel)

  def singleTransitionWith10sTimeout(
      single_transition: Transition.T,
      top_level_state: ToplevelState
  ): ToplevelState = {
    command_exception_with_10s_timeout(
      true,
      single_transition,
      top_level_state
    ).retrieveNow.force
  }

  def singleTransitionWith30sTimeout(
      single_transition: Transition.T,
      top_level_state: ToplevelState
  ): ToplevelState = {
    command_exception_with_30s_timeout(
      true,
      single_transition,
      top_level_state
    ).retrieveNow.force
  }

  def singleTransitionWithoutTimeout(
      single_transition: Transition.T,
      top_level_state: ToplevelState
  ): ToplevelState = {
    command_exception(
      true,
      single_transition,
      top_level_state
    ).retrieveNow.force
  }

  def singleTransition(
      single_transition: Transition.T,
      top_level_state: ToplevelState
  ): ToplevelState = {
    command_exception(
      true,
      single_transition,
      top_level_state
    ).retrieveNow.force
  }

  def singleTransition(singTransition: Transition.T): String = {
    //    TODO: include global facts
    toplevel = singleTransition(singTransition, toplevel)
    getStateString
  }

  def parseStateAction(isarString: String): String = {
    // Here we directly apply transitions to the theory repeatedly
    // to get the (last_observation, action, observation, reward, done) tuple
    var stateActionTotal: String = ""
    val continue = new Breaks
    // Initialising the state string
    var stateString = getStateString
    var proof_level_number = getProofLevel
    Breaks.breakable {
      for ((transition, text) <- parse_text(thy1, isarString).force.retrieveNow)
        continue.breakable {
          if (text.trim.isEmpty) continue.break()
          else if (
            text.trim
              .startsWith("text \\<open>") && text.trim.endsWith("\\<close>")
          ) continue.break()
          else if (text.trim.startsWith("(*") && text.trim.endsWith("*)"))
            continue.break()
          else {
            stateActionTotal =
              stateActionTotal + (stateString + "<\\STATESEP>" + text.trim + "<\\STATESEP>" + s"$getProofLevel" + "<\\TRANSEP>")
            stateString = singleTransition(transition)
          }
        }
    }
    stateActionTotal
  }

  def parse: String = parseStateAction(fileContent)

  @throws(classOf[IsabelleMLException])
  @throws(classOf[TimeoutException])
  def step(
      isar_string: String,
      top_level_state: ToplevelState,
      timeout_in_millis: Int = 30001
  ): ToplevelState = {
    if (debug) println("Begin step")
    // Normal isabelle business
    var tls_to_return: ToplevelState = clone_tls_scala(top_level_state)
    var stateString: String = ""
    val continue = new Breaks
    if (debug) println("Starting to step")
    val f_st = Future.apply {
      blocking {
        Breaks.breakable {
          if (debug) println("start parsing " + isar_string)
          for (
            (transition, text) <- parse_text(
              thy1,
              isar_string
            ).force.retrieveNow
          ) {
            if (debug) println("Transition: " + text)
            continue.breakable {
              if (text.trim.isEmpty) continue.break()
              // println("Small step : " + text)
              if (debug)
                println("singleTransition with timeout " + timeout_in_millis)
              tls_to_return = if (timeout_in_millis > 100000) {
                singleTransitionWithoutTimeout(transition, tls_to_return)
              } else {
                if (timeout_in_millis > 30000) {
                  singleTransitionWith30sTimeout(transition, tls_to_return)
                } else {
                  singleTransitionWith10sTimeout(transition, tls_to_return)
                }
              }
              // println("Applied transition successfully")
            }
          }
        }
      }
      "success"
    }

    // Await for infinite amount of time
    Await.result(f_st, Duration.Inf)
    if (debug)
      println(
        "Finish step, the current state is " + getStateString(tls_to_return)
      )
    tls_to_return
  }

  def normal_with_hammer(
      top_level_state: ToplevelState,
      added_names: List[String],
      deleted_names: List[String],
      timeout_in_millis: Int = 60000 // 60 seconds
  ): (Boolean, List[String]) = {
    if (debug) println("Checkpoint Hammer1: Begin normal_with_hammer")
    val f_res: Future[(Boolean, List[String])] = Future.apply {
      val first_result = normal_with_Sledgehammer(
        top_level_state,
        thy1,
        added_names,
        deleted_names
      ).force.retrieveNow
      (first_result._1, first_result._2._2)
    }
    if (debug) println("Checkpoint Hammer2: Finish & Await result")
    Await.result(f_res, Duration(timeout_in_millis, "millis"))
  }

  def normal_with_try0(
      top_level_state: ToplevelState,
      timeout_in_millis: Int = 12000 // 12 seconds
  ): (Boolean, String) = {
    val f_res: Future[(Boolean, String)] = Future.apply {
      val first_result = normal_with_try0(top_level_state).force.retrieveNow
      (first_result._1, first_result._3)
    }
    if (debug) println("Checkpoint Try0: Finish & Await result")
    Await.result(f_res, Duration(timeout_in_millis, "millis"))
  }

  def normal_with_nitpick(
      top_level_state: ToplevelState,
      timeout_in_millis: Int = 65000 // 65 seconds
  ): String = {
    val f_res: Future[String] = Future.apply {
      val first_result = normal_with_NitPick(top_level_state, thy1).force.retrieveNow
      first_result
    }
    if (debug) println("Checkpoint Nitpick: Finish & Await result")
    Await.result(f_res, Duration(timeout_in_millis, "millis"))
  }

  def normal_with_quickcheck(
      top_level_state: ToplevelState,
      timeout_in_millis: Int = 65000 // 65 seconds
  ): String = {
    val f_res: Future[String] = Future.apply {
      val first_result = normal_with_QuickCheck(top_level_state, thy1).force.retrieveNow
      first_result
    }
    if (debug) println("Checkpoint QuickCheck: Finish & Await result")
    Await.result(f_res, Duration(timeout_in_millis, "millis"))
  }

  if (debug) println("Checkpoint 13: Parse text")
  // return the list of (transition and current step text)
  val transitions_and_texts = parse_text(thy1, fileContent).force.retrieveNow
  var frontier_proceeding_index = 0

  if (debug) println("Checkpoint 14")

  /** Executes Isabelle proof steps until reaching a specific target step. This
    * function accumulates proof states by executing transitions one by one
    * until it finds the target proof step specified by isar_string.
    *
    * @param isar_string
    *   The target proof step to reach (as a string)
    * @return
    *   The proof state string before the target step
    *
    * The function works recursively by:
    *   1. Normalizing input strings (removing extra spaces and newlines) 2.
    *      Checking current transition against target 3. Either returning
    *      current state (if target found) or executing more steps
    */
  def accumulative_step_to_before_transition_starting(
      isar_string: String
  ): String = {
    // Normalize the target string by removing extra whitespace and newlines
    val sanitised_isar_string =
      isar_string.trim.replaceAll("\n", " ").replaceAll(" +", " ")
    // Get current transition and its text from the stored transitions
    val (transition, text) = transitions_and_texts(frontier_proceeding_index)
    val sanitised_text = text.trim.replaceAll("\n", " ").replaceAll(" +", " ")
    if (sanitised_text.trim.isEmpty) {
      // Skip empty transitions and continue recursively
      frontier_proceeding_index += 1
      accumulative_step_to_before_transition_starting(sanitised_isar_string)
    } else if (sanitised_text.trim == sanitised_isar_string) {
      // Found the target step - return current proof state
      val top_level_proceeding_state = retrieve_tls("default")
      getStateString(top_level_proceeding_state)
    } else {
      // Haven't found target yet - execute current transition and continue recursively
      frontier_proceeding_index += 1
      val top_level_proceeding_state = retrieve_tls("default")
      val resulting_state: ToplevelState =
        singleTransition(transition, top_level_proceeding_state)
      register_tls("default", resulting_state)
      accumulative_step_to_before_transition_starting(sanitised_isar_string)
    }
  }

  var accumulative_index: Int = 0
  def accumulative_step_before_theorem_starts(theorem_name: String): Unit = {
    val sanitised_theorem_name =
      theorem_name.trim.replaceAll("\n", " ").replaceAll(" +", " ")
    var found_theorem: Boolean = false
    while (!found_theorem) {
      val (transition, text) = transitions_and_texts(accumulative_index)
      val sanitised_text = text.trim.replaceAll("\n", " ").replaceAll(" +", " ")
      if (sanitised_text == sanitised_theorem_name) {
        found_theorem = true
      } else {
        // println("Before theorem" + sanitised_text)
        if (sanitised_text.nonEmpty) singleTransition(transition)
        accumulative_index += 1
      }
    }
  }
  def accumulative_step_through_a_theorem(): Unit = {
    var proof_finished: Boolean = false
    while (!proof_finished) {
      val (transition, text) = transitions_and_texts(accumulative_index)
      val sanitised_text = text.trim.replaceAll("\n", " ").replaceAll(" +", " ")
      if (sanitised_text.isEmpty) {
        accumulative_index += 1
      } else {
        // println("During theorem" + sanitised_text)
        // println("Stepping to: " + sanitised_text)
        singleTransition(transition)
        val proof_level = getProofLevel
        if (proof_level == 0) proof_finished = true
        accumulative_index += 1
      }
    }
  }
  def accumulative_step_to_theorem_end(theorem_name: String): Unit = {
    accumulative_step_before_theorem_starts(theorem_name)
    accumulative_step_through_a_theorem()
  }

  /* ==================================================================================
  The following functions are prepared interfaces for Isa-REPL
  1. compile(): None or String. If None, the original thy file is compiled. If String, the string is compiled.
  2. step(): String. Apply a single transition to the current state.
  3. step_with_30s(): String. Apply a single transition to the current state with 30s timeout.
  4. step_without_timeout(): String. Apply a single transition to the current state without timeout.
  5. translate_to_smt(): String. Translate the current state to SMT.
  6. prove_by_hammer(): (Boolean, String). Apply sledgehammer to the current state.
  7. parse_to_steps(): String. Parse the current state to a list of steps.
  8. tls pending...
  ================================================================================== */

  /*
  This function is used to compile the original thy file.
   */
  def compile(): String = {
    var stateString: String = ""
    val context_length: Int = fileContent.split("\n").length
    if (context_length > 5) {
      throw new Exception("Compilation context is too complex")
    }
    for (
      (transition, text) <- parse_text(thy1, fileContent).force.retrieveNow
    ) {
      // Avoid too complex context if \n >> 5
      if (text.trim.nonEmpty) {
        if (debug) println("Compilation Context: " + text)
        stateString = singleTransition(transition)
      }
    }
    stateString
  }

  // compile the isar string
  def compile(isar_string: String): String = {
    var stateString: String = ""
    val context_length: Int = isar_string.split("\n").length
    if (context_length > 5) {
      throw new Exception("Compilation context is too complex")
    }
    for (
      (transition, text) <- parse_text(thy1, isar_string).force.retrieveNow
    ) {
      // Avoid too complex context if \n >> 5
      if (text.trim.nonEmpty) {
        if (debug) println("Compilation Context: " + text)
        stateString = singleTransition(transition)
      }
    }
    stateString
  }

  def step(isar_string: String): String = {
    toplevel = step(isar_string, toplevel)
    getStateString
  }

  def step_with_30s(isar_string: String): String = {
    toplevel = step(isar_string, toplevel, 30000)
    getStateString
  }

  def step_without_timeout(isar_string: String): String = {
    toplevel = step(isar_string, toplevel, 180000)
    getStateString
  }

  def prove_by_hammer(timeout_in_millis: Int = 300000): (Boolean, String) = {
    val (ok, tactic) = normal_with_hammer(
      toplevel,
      List[String](),
      List[String](),
      timeout_in_millis
    )
    val results: String = tactic.mkString("<\\SEP>")
    (ok, results)
  }

  def try_close(timeout_in_millis: Int = 12000): (Boolean, String) = {
    val (ok, result) = normal_with_try0(toplevel, timeout_in_millis)
    (ok, result)
  }

  def check_by_nitpick(timeout_in_millis: Int = 65000): (Boolean, String) = {
  // Specifies the expected outcome, which must be one of the following:
  // • genuine: Nitpick found a genuine counterexample.
  // • quasi_genuine: Nitpick found a "quasi genuine" counterexample
  //      (i.e., a counterexample that is genuine unless it contradicts a missing axiom or a dangerous option was used inappropriately).
  // • potential: Nitpick found a potentially spurious counterexample.
  // • none: Nitpick found no counterexample.
  // • unknown: Nitpick encountered some problem (e.g., Kodkod ran out of memory).
    val result = normal_with_nitpick(toplevel, timeout_in_millis)
    val hasCounterexample = result match {
      case "genuine" | "quasi_genuine" | "potential" => true
      case "none" | "unknown" => false
      case _ => false // Default case for unexpected results
    }
    
    val message = result match {
      case "genuine" => "Nitpick found a genuine counterexample"
      case "quasi_genuine" => "Nitpick found a quasi-genuine counterexample (may contradict missing axioms)"
      case "potential" => "Nitpick found a potentially spurious counterexample"
      case "none" => "Nitpick found no counterexample - goal appears valid"
      case "unknown" => "Nitpick encountered a problem (e.g., out of memory)"
      case _ => s"Unexpected nitpick result: $result"
    }
    
    (hasCounterexample, message)
  }


  def check_by_quickcheck(timeout_in_millis: Int = 65000): (Boolean, String) = {
  // Specifies the expected outcome, which must be one of the following:
  // • genuine: QuickCheck found a genuine counterexample.
  // • none: QuickCheck found no counterexample.
  // • unknown: QuickCheck encountered some problem (e.g., Kodkod ran out of memory).
  val result = normal_with_quickcheck(toplevel, timeout_in_millis)
  val norm = Option(result).getOrElse("").trim.toLowerCase
  val hasCounterexample: Boolean =
    if (norm.contains("no counterexample")) false
    else if (norm.contains("found a")) true
    else false


  val message: String =
    norm match {
      case s if s.contains("no counterexample") =>
        "Quickcheck found no counterexample — goal appears valid."
      case s if s.contains("potentially spurious") || s.contains("underspecified") =>
        "Quickcheck found a potentially spurious counterexample (may be caused by underspecified functions)."
      case s if s.contains("found a counterexample") =>
        "Quickcheck found a genuine counterexample."
      case _ =>
        s"Unexpected Quickcheck result: $result"
    }
    (hasCounterexample, message)
  }

  def find_theorems(
      query_patterns: List[String],
      limit: Int = -1,
      remove_duplicates: Boolean = true
  ): String = {
    val output =
      parse_find_theorems(toplevel, query_patterns, limit, remove_duplicates).force.retrieveNow
    output
  }

  def translate_to_smt(): String = {
    val result = parse_to_smt(toplevel).force.retrieveNow
    result
  }

  def extract_vars(): List[String] = {
    val vars = parse_vars(toplevel).force.retrieveNow
    vars
  }

  def extract_assms(): List[String] = {
    val assms = parse_assms(toplevel).force.retrieveNow
    assms
  }

  def extract_goal(): String = {
    val goal = parse_goal(toplevel).force.retrieveNow
    goal
  }

  def check_no_subgoals(): Boolean = {
    val no_subgoals = parse_no_subgoals(toplevel).force.retrieveNow
    no_subgoals
  }

  def check_num_subgoals(): Int = {
    val num_subgoals = parse_num_subgoals(toplevel).force.retrieveNow
    num_subgoals
  }

  /*
  parse a string into a list of executable commands
  it will not execute the commands, just parse them
   */
  def parse_to_steps(isar_string: String): String = {
    val isar_string_trim =
      isar_string.trim.replaceAll("\n", " ").replaceAll(" +", " ")
    var steps: String = ""
    var stateString: String = ""
    for (
      (transition, text) <- parse_text(thy1, isar_string_trim).force.retrieveNow
    ) {
      if (text.trim.nonEmpty) {
        steps = steps + "<\\SEP>" + text
      }
    }
    steps
  }

  def extract_thm_deps(theorem_name: String): List[String] = {
    get_dependent_thms(toplevel, theorem_name).force.retrieveNow
  }

  def extract_hammer_facts(
      filter: String = "mepo",
      adds: List[String] = List[String](),
      dels: List[String] = List[String]()
  ): String = {
    val output =
      parse_hammer_facts(toplevel, thy1, filter, adds, dels).force.retrieveNow
    output
  }

  def extract_thm_deps_with_thy_names(theorem_name: String): List[String] = {
    get_dependent_thms_with_thy_names(toplevel, theorem_name).force.retrieveNow
  }

  def extract_hammer_facts_with_thy_names(
      filter: String = "mesh",
      adds: List[String] = List[String](),
      dels: List[String] = List[String]()
  ): String = {
    val output = parse_hammer_facts_with_theory_names(
      toplevel,
      thy1,
      filter,
      adds,
      dels
    ).force.retrieveNow
    output
  }

  def mash_state_relearn(): Unit = {
    val output = mash_relearn(
      toplevel,
      thy1,
    ).force.retrieveNow
    output
  }

  def extract_thm_defined_in_parent(): List[String] = {
    val get_parent_thy_thm_pairs: MLFunction[Theory, List[String]] =
      compileFunction[Theory, List[String]](
        s""" fn (thy) =>
          | let
          |   val parents_of_thy = Theory.parents_of thy;
          |   val first_parent = List.nth (parents_of_thy, 0);
          |   val thms = Global_Theory.dest_thm_names first_parent;
          | in
          |    map (fst o snd) thms
          | end
          |""".stripMargin
      )
    get_parent_thy_thm_pairs(thy1).force.retrieveNow
  }

  // reset isabelle and thy to be proved
  def reset_isabelle(path: String): String = {
    path_to_thy = path
    currentTheoryName = path_to_thy.split("/").last.replace(".thy", "")
    fileContent = Files.readString(Path.of(path_to_thy))
    fileContentCopy = fileContent
    thy1 = theoryManager.beginTheory()
    toplevel = init_toplevel().force.retrieveNow
    reset_map()
    "Reset"
  }

  def exit_isabelle(): String = {
    // remove temp directory
    cleanupAll()
    // exit isabelle
    isabelle.destroy()
    "Destroyed"
  }

  if (debug) println("Checkpoint 15")

  // Manage top level states with the internal map
  def copy_tls: MLValue[ToplevelState] = toplevel.mlValue

  def _clone_tls_scala(tls_scala: ToplevelState): Future[ToplevelState] =
    ToplevelState.converter.retrieve(tls_scala.mlValue)

  def clone_tls_scala(tls_scala: ToplevelState): ToplevelState =
    Await.result(_clone_tls_scala(tls_scala), Duration.Inf)

  def register_tls(name: String, tls: ToplevelState): Unit =
    top_level_state_map += (name -> tls.mlValue)

  def _retrieve_tls(tls_name: String): Future[ToplevelState] =
    ToplevelState.converter.retrieve(top_level_state_map(tls_name))

  def retrieve_tls(tls_name: String): ToplevelState =
    Await.result(_retrieve_tls(tls_name), Duration.Inf)

  def clone_tls(tls_name: String): Unit = {
    top_level_state_map += (tls_name -> copy_tls)
  }

  def clone_tls(old_name: String, new_name: String): Unit =
    top_level_state_map += (new_name -> top_level_state_map(old_name))

  def focus_tls(tls_name: String): Unit = {
    toplevel = retrieve_tls(tls_name)
  }

  def remove_tls(tls_name: String): Unit = {
    if (top_level_state_map.contains(tls_name)) {
      top_level_state_map -= tls_name
      // wait for 100ms to ensure the tls is removed
      Thread.sleep(100)
    }
  }

  def parse_entire_thy: List[String] =
    parse_text(thy1, fileContent).force.retrieveNow.map(_._2)

  def get_num_of_processors: Int =
    num_of_processors().force.retrieveNow

  def get_num_of_threads: Int =
    num_of_threads().force.retrieveNow
}
