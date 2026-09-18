"""
src/mock_agent/model.py -- the SOLVER's editable surface.

This file is inside scope.allowed in .outerloop.yaml, so a solver session
is free to change it: architecture, hyperparameters, whatever it thinks
will move `accuracy` on benchmarks/blob_classify.py. That's the entire
"hypothesis" in outerloop terms -- one PR, one change here, evaluated by
the frozen ruler above.

Try it yourself: bump hidden_size, or the number of layers, or the
learning rate, and see whether benchmarks/blob_classify.py reports a real
improvement (see run_trial.py's --min-delta noise floor).
"""

import torch.nn as nn

CONFIG = {
    "hidden_size": 8,
    "lr": 0.01,
    "epochs": 30,
}


class TinyMLP(nn.Module):
    def __init__(self, n_features: int, hidden_size: int, n_classes: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, n_classes),
        )

    def forward(self, x):
        return self.net(x)
