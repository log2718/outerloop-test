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
  4. Parses the ruler's `RESULT metric=... value=...` line and reports
     whether the delta clears --min-delta.

Both refs must be committed (branches or SHAs) -- git worktrees can't
check out a dirty working tree, which is itself a faithful constraint:
the real orchestrator only ever measures pinned SHAs, never in-progress
edits.

Usage (after you've made a candidate branch with a model.py change):
    python run_trial.py --baseline-ref main --candidate-ref candidate/wider-hidden
"""

import argparse
import os
import random
import re
import subprocess
import tempfile

import yaml

RESULT_RE = re.compile(r"RESULT metric=(\S+) value=([\d.]+)")
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_contract():
    with open(os.path.join(REPO_ROOT, ".outerloop.yaml")) as f:
        return yaml.safe_load(f)


def measure(ref: str, seed: int, command: str):
    """Checks out `ref` into a throwaway worktree and runs `command` there."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree = os.path.join(tmp, "wt")
        subprocess.run(
            ["git", "worktree", "add", "--detach", worktree, ref],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True,
        )
        try:
            env = os.environ.copy()
            env["OUTERLOOP_SEED"] = str(seed)
            result = subprocess.run(
                command.split(), cwd=worktree, env=env,
                check=True, capture_output=True, text=True,
            )
            match = RESULT_RE.search(result.stdout)
            if not match:
                raise RuntimeError(
                    f"No RESULT line from '{command}' at {ref}.\n"
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                )
            return match.group(1), float(match.group(2))
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

    _, baseline_value = measure(args.baseline_ref, seed, command)
    _, candidate_value = measure(args.candidate_ref, seed, command)
    delta = candidate_value - baseline_value
    improved = delta > args.min_delta

    print(f"baseline  ({args.baseline_ref}):  {metric_name}={baseline_value:.4f}")
    print(f"candidate ({args.candidate_ref}): {metric_name}={candidate_value:.4f}")
    print(f"delta: {delta:+.4f}  (min_delta={args.min_delta})")
    print(f"improved? {'YES -> would open a PR' if improved else 'no (does not clear the noise floor)'}")


if __name__ == "__main__":
    main()
