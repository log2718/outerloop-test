import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from mock_agent.model import TinyMLP, CONFIG  # noqa: E402


def test_forward_shape():
    import torch
    model = TinyMLP(n_features=10, hidden_size=CONFIG["hidden_size"])
    x = torch.randn(4, 10)
    out = model(x)
    assert out.shape == (4, 2)
