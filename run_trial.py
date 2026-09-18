"""
run_trial.py -- a tiny stand-in for the orchestrator's measurement step.

Real outerloop: "baseline re-run at the merge-base, not a trusted static
file" + "the orchestrator draws ONE fresh seed per measurement pass, pins
both sides of every comparison to it" (architecture.md).

This script does the same thing at toy scale, using real git:
  1. Reads the benchmark's `command` and `metric` straight from
     .outerloop.yaml (never hard-coded here -- this driver doesn't know
     or care what the benchmark actually does).
  2. Checks out --baseline-ref and --candidate-ref into throwaway git
     worktrees (like architecture.md's "throwaway worktree of the
     pre-session commit").
  3. Runs the SAME command in each, with the SAME freshly-drawn seed
     injected via OUTERLOOP_SEED (paired, common random numbers).
  4. Parses the last line of stdout as JSON, the same way outerloop's own
     orchestrator.metric_from_output does, and reports whether the delta
     clears --min-delta.

Both refs must be committed (branches or SHAs) -- git worktrees can't
check out a dirty working tree, which is itself a faithful constraint:
the real orchestrator only ever measures pinned SHAs, never in-progress
edits.

Usage (after you've made a candidate branch with a model.py change):
    python run_trial.py --baseline-ref main --candidate-ref candidate/wider-hidden
"""

import argparse
import json
import os
import random
import subprocess
import tempfile

import yaml

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def metric_from_output(stdout: str, metric: str) -> float | None:
    """Same contract as outerloop's own orchestrator.metric_from_output: the
    metric from the LAST single-line JSON object that carries it. No regex
    fallback -- a fuzzy match risks reading the wrong number."""
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and metric in data:
            try:
                return float(data[metric])
            except (TypeError, ValueError):
                return None
        if isinstance(data, dict) and data.get("metric") == metric and "value" in data:
            try:
                return float(data["value"])
            except (TypeError, ValueError):
                return None
    return None


def load_contract():
    with open(os.path.join(REPO_ROOT, ".outerloop.yaml")) as f:
        return yaml.safe_load(f)


def measure(ref: str, seed: int, command: str, role: str, metric: str):
    """Checks out `ref` into a throwaway worktree and runs `command` there.

    wandb's own run dir is pointed at REPO_ROOT (not the worktree), so the
    run survives the worktree's teardown; baseline and candidate share a
    WANDB_RUN_GROUP so they land side by side in the UI for this trial.
    """
    with tempfile.TemporaryDirectory() as tmp:
        worktree = os.path.join(tmp, "wt")
        subprocess.run(
            ["git", "worktree", "add", "--detach", worktree, ref],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        try:
            env = os.environ.copy()
            env["OUTERLOOP_SEED"] = str(seed)
            env.setdefault("WANDB_MODE", "offline")
            env["WANDB_DIR"] = REPO_ROOT
            env["WANDB_RUN_GROUP"] = f"trial-seed{seed}"
            env["WANDB_JOB_TYPE"] = role
            result = subprocess.run(
                command.split(), cwd=worktree, env=env,
                check=True, capture_output=True, text=True,
            )
            value = metric_from_output(result.stdout, metric)
            if value is None:
                raise RuntimeError(
                    f"No readable {metric!r} in output of '{command}' at {ref}.\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                )
            return metric, value
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree],
                cwd=REPO_ROOT, check=False, capture_output=True,
            )


def main():
    parser = argparse.ArgumentParser(description="Baseline vs candidate, measured via git worktrees")
    parser.add_argument("--baseline-ref", default="HEAD", help="Git ref for the baseline (default: HEAD)")
    parser.add_argument("--candidate-ref", required=True, help="Git ref for the candidate (e.g. a branch)")
    parser.add_argument("--seed", type=int, default=None, help="Fix the shared seed instead of drawing fresh")
    parser.add_argument("--min-delta", type=float, default=0.02, help="Noise floor for 'improved'")
    args = parser.parse_args()

    contract = load_contract()
    bench = contract["benchmarks"][0]  # single benchmark for this toy repo
    command, metric_name = bench["command"], bench["metric"]

    seed = args.seed if args.seed is not None else random.randint(0, 2**31 - 1)
    print(f"benchmark: {bench['name']}   command: {command}")
    print(f"shared seed (drawn fresh this measurement pass): {seed}\n")

    _, baseline_value = measure(args.baseline_ref, seed, command, role="baseline", metric=metric_name)
    _, candidate_value = measure(args.candidate_ref, seed, command, role="candidate", metric=metric_name)
    delta = candidate_value - baseline_value
    improved = delta > args.min_delta

    print(f"baseline  ({args.baseline_ref}):  {metric_name}={baseline_value:.4f}")
    print(f"candidate ({args.candidate_ref}): {metric_name}={candidate_value:.4f}")
    print(f"delta: {delta:+.4f}  (min_delta={args.min_delta})")
    print(f"improved? {'YES -> would open a PR' if improved else 'no (does not clear the noise floor)'}")


if __name__ == "__main__":
    main()
