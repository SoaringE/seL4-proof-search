(*  Title:      Auto_Isabelle.ML
    Author:     Zenan Li and Baoding He
    Description: Try a combination of proof methods. Tweak from the try0.ML.
                 In Scala env, timeout mechanism is not working.
*)

structure Auto_Isabelle : sig
  val clean_theorem_text : string -> string
  type result = {name: string, command: string, time: int, state: Proof.state}
  val try_close : Time.time -> Proof.state -> bool * string * string
  val try_nitpick: Time.time -> Toplevel.state -> theory -> bool * string
  val try_quickcheck: Time.time -> Toplevel.state -> theory -> bool * string
  val find_theorems: Toplevel.state -> string list -> int option -> bool -> string
  val retrieve_facts : Proof.state -> theory -> string -> string list -> string list -> string 
  val retrieve_facts_with_theory_names : Proof.state -> theory -> string -> string list -> string list -> string
  val mash_relearn : Proof.state -> theory -> unit
end = struct

(* ============================================================================
   Utility functions
   ============================================================================ *)

fun clean_theorem_text thm_text = 
  XML.content_of (YXML.parse_body thm_text);

val num_goals = Thm.nprems_of o #goal o Proof.goal;

(* List of proof methods to try *)
val named_methods =
  ["simp", "auto", "blast", "argo", "linarith", "presburger",
   "algebra", "fast", "fastforce", "force", "meson", "satx", "order"];

(* Parse a method string into a method *)
fun parse_method ctxt s =
  enclose "(" ")" s
  |> Token.explode (Thy_Header.get_keywords' ctxt) Position.start
  |> filter Token.is_proper
  |> Scan.read Token.stopper Method.parse
  |> (fn SOME (Method.Source src, _) => src | _ => raise Fail "expected Source");

(* Apply a tactic and return timing information *)
fun simple_apply tac st =
  let
    val result = try (fn () => Seq.pull (tac st)) ()
  in
    case Option.join result of
      SOME (st', _) => (Time.zeroTime, st')
    | NONE => (Time.zeroTime, st)
  end;

(* Create antiquotation markup *)
fun antiquot s = "\\" ^ "<open>" ^ s ^ "\\" ^ "<close>";

(* ============================================================================
   Result type definition
   ============================================================================ *)

type result = {name: string, command: string, time: int, state: Proof.state};

(* ============================================================================
   Method application
   ============================================================================ *)

(* Apply a named method to the current proof state *)
fun apply_named_method name _ st =
  let
    val ctxt = Proof.context_of st;
    val local_facts = Facts.props (Proof_Context.facts_of ctxt) |> map #1 |> take 10; 
    val text =
      name
      |> parse_method ctxt
      |> Method.method_cmd ctxt
      |> Method.Basic
      |> (fn m => Method.Combinator (Method.no_combinator_info, Method.Select_Goals 1, [m]));
    val apply =
      Proof.using [local_facts |> map (rpair [] o single)]
      #> Proof.refine text #> Seq.filter_results;
    val (time, st') = simple_apply apply st;
    val num_after = num_goals st';
    val command =
      (if null local_facts then "" 
       else "using " ^ space_implode " " 
            (map (fn thm => antiquot (Thm.string_of_thm ctxt thm)) local_facts) ^ " ") ^
      (if num_after = 0 then "by " else "") ^ name
  in
    if num_after = 0 then
      SOME {name = name, command = command, time = Time.toMilliseconds time, state = st'}
    else
      NONE
  end;

(* ============================================================================
   Asynchronous proof attempts
   ============================================================================ *)

(* Try to close the proof asynchronously using multiple methods *)
fun try_close_async st =
  Future.fork (fn () =>
    let
      val apply_methods = map apply_named_method named_methods;
      val results =
        map (fn method =>
          case method (SOME (seconds 0.0)) st of
            SOME r => SOME r
          | NONE => NONE
        ) apply_methods
        |> List.mapPartial I
    in
      case results of
        [] => (false, "All Failed", "")
      | {name, command, ...} :: _ =>
          (true, name, "Try this: " ^ Active.sendback_markup_command command)
    end);

(* Try to close the proof with timeout *)
fun try_close timeout st =
  let
    val future = try_close_async st;
    val start_time = Time.now ();
    fun check_timeout () = Time.now () - start_time > timeout;
    fun poll interval =
      if Future.is_finished future then
        Future.join future
      else if check_timeout () then
        (Future.cancel future; (false, "All tactics timed out", ""))
      else
        (OS.Process.sleep (seconds interval); poll (Real.min ((interval * 2.0), 1.0)))
  in
    poll 0.1
  end;

(* Try to refuse the proof asynchronously using nitpick *)
fun try_nitpick_async st thy =
  Future.fork (fn () =>
    let
    val proof_state = Toplevel.proof_of st;
    val step = Toplevel.proof_position_of st;

    (* val {context = _, facts, goal} = Proof.goal proof_state; *)

    val params = Nitpick_Commands.default_params thy
                   [("show_all", "true"), ("timeout", "60")];

    val (str_result, _) = Nitpick.pick_nits_in_subgoal
                            proof_state params Nitpick.Normal 1 step;
    in
      (true, str_result)
    end);

(* Try to nitpick the proof with timeout *)
fun try_nitpick timeout st thy =
  let
    val future = try_nitpick_async st thy;
    val start_time = Time.now ();
    fun check_timeout () = Time.now () - start_time > timeout;
    fun poll interval =
      if Future.is_finished future then
        Future.join future
      else if check_timeout () then
        (Future.cancel future; (false, "Nitpick timed out"))
      else
        (OS.Process.sleep (seconds interval); poll (Real.min ((interval * 2.0), 1.0)))
  in
    poll 0.1
  end;

(* Run Quickcheck asynchronously on subgoal 1.
   timeout: Time.time — internal timeout passed to Quickcheck, also used for external watchdog
   st: Toplevel.state
   thy: theory (kept for compatibility with the Nitpick version, but not used)
   Returns: (bool * string) — (success flag, formatted Quickcheck output)
 *)
fun try_quickcheck_async timeout st _ =
  Future.fork (fn () =>
    let
      val state = Toplevel.proof_of st

      (* Configure Quickcheck parameters inside the proof context:
         - disable report output
         - enable quiet mode
         - set desired number of iterations
         - set Quickcheck’s internal timeout (expects seconds as real)
       *)
      val state' =
        state
        |> Proof.map_context
            (Config.put Quickcheck.report false
             #> Config.put Quickcheck.quiet  true
             #> Config.put Quickcheck.iterations 1000
             #> Config.put Quickcheck.timeout (Time.toReal timeout))

      (* Run Quickcheck on subgoal 1; result is:
         (bool * (string * term) list) option
         Some counterexample  → found
         None                 → no counterexample
       *)
      val cex_opt = (Quickcheck.quickcheck [] 1 state')

      fun simple_pretty_counterex ctxt auto result =
  case result of
      NONE =>
        Pretty.str "Quickcheck found no counterexample."
    | SOME ((genuine, _), _) =>
        Pretty.str ("Quickcheck found a " ^
          (if genuine then "counterexample."
           else "potentially spurious counterexample due to underspecified functions."))



      (* Format the result using Quickcheck’s pretty printer.
         Quickcheck.pretty_counterex expects:
           SOME ((bool * (string * term) list), (term * term) list)
         We give an empty evaluation-term list.
       *)
      val ctxt = Proof.context_of state'
      val msg =
        Pretty.string_of
          (simple_pretty_counterex ctxt true
             (Option.map (fn cex => (cex, [])) cex_opt))
    in
      (true, msg)
    end)


(* Run Quickcheck with an external watchdog timeout.
   If the asynchronous Quickcheck task does not finish within the
   given timeout, cancel the Future and return a timeout message.
 *)
fun try_quickcheck timeout st thy =
  let
    val future = try_quickcheck_async timeout st thy
    val start_time = Time.now ()

    fun timeout_exceeded () = Time.now () - start_time > timeout

    (* Poll the Future until:
         - it finishes
         - or the timeout expires
       Poll interval doubles up to 1 second to reduce overhead.
     *)
    fun poll interval =
      if Future.is_finished future then
        Future.join future
      else if timeout_exceeded () then
        (Future.cancel future; (false, "Quickcheck timed out"))
      else
        (OS.Process.sleep (seconds interval);
         poll (Real.min (interval * 2.0, 1.0)))
  in
    poll 0.1
  end

(* Find theorems that match a list of term-pattern criteria.
   query_patterns: each string corresponds to one positive pattern criterion,
                   e.g. "obj_at _ _" or "set_thread_state"
   opt_limit: NONE means Isabelle default limit; SOME n limits display to n
   rem_dups: true removes duplicate theorem bodies from results
 *)
fun find_theorems st query_patterns opt_limit rem_dups =
  let
    val state = Find_Theorems.proof_state st;
    val criteria = map (fn pat => (true, Find_Theorems.Pattern pat)) query_patterns;
    val pretty = Find_Theorems.pretty_theorems state opt_limit rem_dups criteria;
  in
    clean_theorem_text (Pretty.string_of pretty)
  end;

(* ============================================================================
   Fact retrieval utilities
   ============================================================================ *)

(* Create fact references and token lists *)
fun get_refs_and_token_lists name = (Facts.named name, []);

(* Common parameters for fact retrieval *)
fun make_override adds dels =
  let
    val adds_refs_and_token_lists = map get_refs_and_token_lists adds;
    val dels_refs_and_token_lists = map get_refs_and_token_lists dels;
  in
    {add = adds_refs_and_token_lists, del = dels_refs_and_token_lists, only = false}
  end;

(* Get facts from proof state with common logic *)
fun get_facts_from_state state thy filter adds dels =
  let
    val ctxt = Proof.context_of state;
    val {facts = chained_thms, goal, ...} = Proof.goal state;
    val (_, hyp_ts, concl_t) = ATP_Util.strip_subgoal goal 1 ctxt;
    val override = make_override adds dels;
    val params = Sledgehammer_Commands.default_params thy [("fact_filter", filter)];
    val {induction_rules, max_facts, ...} = params;
    val all_facts = Sledgehammer_Fact.nearly_all_facts_of_context ctxt false override chained_thms hyp_ts concl_t;
    val max_num_facts = the_default 128 max_facts;
    val fact_lst = Sledgehammer_MaSh.relevant_facts ctxt params "" max_num_facts override hyp_ts concl_t all_facts;
    val induction_rules = the_default Sledgehammer_Prover.Exclude induction_rules;
    val factss = map (apsnd (Sledgehammer_Prover.maybe_filter_out_induction_rules induction_rules)) fact_lst;
  in
    (factss, ctxt)
  end;

(* ============================================================================
   Fact retrieval functions
   ============================================================================ *)

(* Retrieve facts from the proof state
   @param state - current proof state
   @param thy - theory
   @param filter - fact filter to use
   @param adds - facts to add
   @param dels - facts to delete
   @return formatted fact string
*)
fun retrieve_facts state thy filter adds dels = 
  let
    val (factss, _) = get_facts_from_state state thy filter adds dels;
  in
    Sledgehammer.string_of_factss factss
  end;

(* Format facts with theory names *)
fun string_of_facts_with_theory_names filter facts =
  string_of_int (length facts) ^ "<\\SEP>" ^ 
  (if filter = "" then "" else filter) ^ "<\\SEP>" ^ 
  (space_implode "<\\SEP>" 
    (map (fn x => String.concat [
      Thm.theory_long_name (#2 x), "<\\INNER_SEP>",
      (* New version should be as follows *)
      (* Thm_Name.print (Thm.derivation_name (#2 x)), "<\\INNER_SEP>", *)
      Thm.derivation_name (#2 x), "<\\INNER_SEP>", 
      #1 (#1 x)
    ]) facts));

(* Format fact lists with theory names *)
fun string_of_factss_with_theory_names factss =
  if forall (null o snd) factss then
    "Found no relevant facts"
  else
    cat_lines (map (fn (filter, facts) => string_of_facts_with_theory_names filter facts) factss);

(* Retrieve facts with theory names *)
fun retrieve_facts_with_theory_names state thy filter adds dels =
  let
    val (factss, _) = get_facts_from_state state thy filter adds dels;
  in
    string_of_factss_with_theory_names factss
  end;

(* ============================================================================
   MaSh learning
   ============================================================================ *)

(* Relearn MaSh with current proof state *)
fun mash_relearn state thy =
  let
    val ctxt = Proof.context_of state;
    val override = make_override [] [];
    val params = Sledgehammer_Commands.default_params thy
      [("timeout", string_of_real 2.0), ("slice", "false"), ("preplay_timeout", "0")];
    val _ = Sledgehammer_MaSh.mash_unlearn ctxt;
    val _ = Sledgehammer_MaSh.mash_learn ctxt params override (#facts (Proof.goal state)) false;
  in
    ()
  end;

end