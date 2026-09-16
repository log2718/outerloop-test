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
orchestrator's structured result parsing.
"""

import os
import random
import sys

import numpy as np
import torch

# Solver-editable code lives under src/ -- imported, never copied in here.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mock_agent.model import CONFIG, TinyMLP  # noqa: E402

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_dataset(seed: int, n_train: int = 400, n_test: int = 200, n_features: int = 10):
    """Seeded synthetic two-blob dataset. Ruler-owned: the solver cannot
    see or influence how data is drawn, only how the model is built."""
    rng = np.random.RandomState(seed)
    n = n_train + n_test

    labels = rng.randint(0, 2, size=n)
    means = np.where(labels[:, None] == 1, 1.0, -1.0)
    X = means + rng.randn(n, n_features) * 1.5
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

    X_train, y_train, X_test, y_test = make_dataset(seed)

    model = TinyMLP(n_features=X_train.shape[1], hidden_size=CONFIG["hidden_size"]).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["lr"])
    loss_fn = torch.nn.CrossEntropyLoss()

    model.train()
    for _ in range(CONFIG["epochs"]):
        optimizer.zero_grad()
        loss = loss_fn(model(X_train), y_train)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        preds = model(X_test).argmax(dim=1)
        accuracy = (preds == y_test).float().mean().item()

    print(f"RESULT metric=accuracy value={accuracy:.4f}")


if __name__ == "__main__":
    main()
