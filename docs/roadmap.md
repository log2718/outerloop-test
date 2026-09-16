# Roadmap

Benchmark gaps for the "blob-classify" benchmark. A real outerloop
orchestrator's self-initiated lane would read this file, plus notebook
lessons/recent reports, to pick a task when no requested issue is
pending (architecture.md, "Intake").

- [ ] Beat baseline accuracy (hidden_size=8) by more than the noise floor
      (min_delta=0.02) without increasing epochs above 60.
- [ ] Try a deeper network (2 hidden layers) instead of just widening.
- [ ] Investigate whether a different optimizer (SGD+momentum vs Adam)
      changes the result at fixed hidden_size.
