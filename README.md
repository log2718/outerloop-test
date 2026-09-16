# outerloop-test

A toy "target repo" for experimenting with outerloop's contract,
scope, and baseline-vs-candidate measurement pattern -- no real
orchestrator, GitHub App, or Slurm involved. Everything runs locally
with plain git.

## Layout

```
.outerloop.yaml           <- the contract: benchmark, budgets, scope, roadmap
benchmarks/
  blob_classify.py         <- the RULER: frozen eval, outside scope.allowed
src/mock_agent/
  model.py                 <- the SOLVER's editable surface (the "hypothesis")
tests/
  test_model.py
docs/
  roadmap.md                <- self-initiated task selection reads this
run_trial.py                <- tiny orchestrator stand-in (measures via git worktrees)
requirements.txt
```

## Setup

```
pip install -r requirements.txt
git init && git add -A && git commit -m "baseline: hidden_size=8"
```

## Try a "hypothesis"

1. Make a branch, as an author session would (`feat/auto/<slug>` in the
   real system):
   ```
   git checkout -b candidate/wider-hidden
   ```
2. Edit `src/mock_agent/model.py` -- e.g. change `"hidden_size": 8` to `32`.
   This is the *only* file a solver is allowed to touch (`scope.allowed`
   in `.outerloop.yaml`); `benchmarks/blob_classify.py` is off-limits.
3. Commit it:
   ```
   git add -A && git commit -m "try: widen hidden layer to 32"
   ```
4. Measure baseline vs candidate, orchestrator-style:
   ```
   git checkout main   # back on main so run_trial.py's own working tree is clean
   python run_trial.py --baseline-ref main --candidate-ref candidate/wider-hidden
   ```

`run_trial.py` never trusts a number either branch "claims" -- it checks
each ref out into its own throwaway git worktree and re-runs
`benchmarks/blob_classify.py` itself, with the *same* freshly-drawn seed
piped to both via `OUTERLOOP_SEED`. That mirrors two rules from
architecture.md:

- "baseline re-run at the merge-base, not a trusted static file"
- "the orchestrator draws ONE fresh seed per measurement pass, pins both
  sides of every comparison to it"

If the delta clears `--min-delta` (default `0.02`), the script prints
"would open a PR" -- standing in for the real system's `metric improved?`
gate. Below that, it's an honest negative result, not a failure.

## What this deliberately leaves out

No GitHub App, no PR automation, no advisory reviewer/verifier, no Slurm,
no notebook, no lease/heartbeat machinery. This is purely the measurement
core (contract -> ruler vs. scope -> paired baseline/candidate) at a scale
you can run in a few seconds on a laptop CPU.
