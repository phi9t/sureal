# 06: Evaluation verifiers and the training box replay on launch plans

**What to build:** The evaluation verifiers and audits, and the hand-written sandbox in the training box replay, run on launch plans. The replay gains the overlap check and `PYTHONPATH` its hand-written sandbox lacks.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `evaluation/audit-perception-gate.py`, `verify-detection-adapter.py`, `verify-detection-contract.py`, `verify-native-metrics.py` and `verify-real-detection-export.py` build launch plans and load locks (including the metrics image-form lock) through the module. None creates a lock when it is missing
- [ ] `detection/training_box_replay.py` builds a launch plan instead of a hand-written `bwrap` command. Its whole-lock comparison against the pinned lock still happens
- [ ] Tests assert on plans built against fixture locks
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
