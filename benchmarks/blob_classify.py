"""
benchmarks/blob_classify.py -- the RULER for the "blob-classify" benchmark.

This file lives OUTSIDE scope.allowed in .outerloop.yaml, so a solver
session is never permitted to edit it (mirrors roles.md: "touch the ruler
(frozen evals/tests)" is something the author session "may never" do).

Contract's `command` runs this file verbatim, unmodified, whether the
checkout is the pre-session baseline or the solver's candidate diff --
same command, same data draw, only the imported model code differs.

Seed handling: a real orchestrator draws ONE fresh seed per measurement
PASS and pins both sides of the comparison to it (architecture.md,
"Measurement on resampled pools"). Here that's simulated via the
OUTERLOOP_SEED environment variable, which a driver script sets before
invoking this command -- the contract's command text itself stays fixed,
exactly as the real system requires ("contract: benchmarks, scope,
budgets (verbatim)").

Output contract: prints exactly one line of the form
    RESULT metric=<name> value=<float>
A driver simply greps stdout for that line -- standing in for the real
orchestrator's structured result parsing. wandb is a side channel for
humans inspecting a run's curves after the fact; the RESULT line remains
the one thing the orchestrator itself trusts.

wandb: every run logs config + the loss curve + final accuracy. Defaults
to WANDB_MODE=offline (no network, no login needed) so it never blocks an
automated measurement pass; run_trial.py points WANDB_DIR at the main
repo so runs survive their throwaway worktree, and groups baseline vs
candidate together so they land side by side in the UI.
"""

import os
import random
import subprocess
import sys

import numpy as np
import torch
import wandb

# Solver-editable code lives under src/ -- imported, never copied in here.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mock_agent.model import CONFIG, TinyMLP  # noqa: E402

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _git_short_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_dataset(seed: int, n_train: int = 400, n_test: int = 200, n_features: int = 20,
                  n_blobs: int = 4, mean_sep: float = 0.5,
                  n_informative: int = 6, n_redundant: int = 4):
    """Seeded synthetic multi-blob dataset. Ruler-owned: the solver cannot
    see or influence how data is drawn, only how the model is built.

    Of the n_features columns, only n_informative actually carry the class
    signal. n_redundant more are random linear combinations of those
    informative columns (correlated, but no new information). The rest are
    pure noise, independent of the label."""
    rng = np.random.RandomState(seed)
    n = n_train + n_test
    n_noise = n_features - n_informative - n_redundant
    if n_noise < 0:
        raise ValueError("n_informative + n_redundant exceeds n_features")

    labels = rng.randint(0, n_blobs, size=n)
    centers = (np.arange(n_blobs) - (n_blobs - 1) / 2) * mean_sep
    means = centers[labels][:, None]

    X_informative = means + rng.randn(n, n_informative) * 1.5
    combo_weights = rng.randn(n_informative, n_redundant)
    X_redundant = X_informative @ combo_weights + rng.randn(n, n_redundant) * 0.5
    X_noise = rng.randn(n, n_noise) * 1.5

    X = np.concatenate([X_informative, X_redundant, X_noise], axis=1)
    y = labels

    X_train, X_test = X[:n_train], X[n_train:]
    y_train, y_test = y[:n_train], y[n_train:]

    to_t = lambda a, dt: torch.tensor(a, dtype=dt, device=DEVICE)
    return (
        to_t(X_train, torch.float32), to_t(y_train, torch.long),
        to_t(X_test, torch.float32), to_t(y_test, torch.long),
    )


def main() -> None:
    seed = int(os.environ.get("OUTERLOOP_SEED", "0"))
    set_all_seeds(seed)

    os.environ.setdefault("WANDB_MODE", "offline")
    os.environ.setdefault("WANDB_PROJECT", "outerloop-test")
    run = wandb.init(
        name=f"{_git_short_sha()}-seed{seed}",
        config={**CONFIG, "seed": seed, "commit": _git_short_sha()},
    )

    X_train, y_train, X_test, y_test = make_dataset(seed)

    n_classes = int(y_train.max().item()) + 1
    model = TinyMLP(n_features=X_train.shape[1], hidden_size=CONFIG["hidden_size"], n_classes=n_classes).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"])
    loss_fn = torch.nn.CrossEntropyLoss()

    model.train()
    for epoch in range(CONFIG["epochs"]):
        optimizer.zero_grad()
        loss = loss_fn(model(X_train), y_train)
        loss.backward()
        optimizer.step()
        run.log({"train/loss": loss.item()}, step=epoch)

    model.eval()
    with torch.no_grad():
        preds = model(X_test).argmax(dim=1)
        accuracy = (preds == y_test).float().mean().item()

    run.summary["accuracy"] = accuracy
    run.finish()

    print(f"RESULT metric=accuracy value={accuracy:.4f}")


if __name__ == "__main__":
    main()
