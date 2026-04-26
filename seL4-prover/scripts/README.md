# scripts/

One-off dataset preparation scripts. Not part of the main proof-search
pipeline and not invoked by `run.sh`.

- `code2inv.py` — converts the original code2inv benchmark into Isabelle/HOL
  theorems via AutoCorres.
- `code2inv_divide.py` — variant that ingests the LaM4Inv GPT-4 ground-truth
  output. Set `GROUND_TRUTH_PATH` to the `GPT4TurboFull.txt` file before
  running.

Both scripts assume `L4V_PATH` is set and an Isa-Repl gateway is reachable
on `port = 25551`.
