# Balanced16 independent replay preparation

The independent `cohort/replay_sustained.py` worker checks an externally hashed checkpoint against the frozen manifest/source inventory/runtime identity, restores model/Adam/Python/NumPy/Torch/CUDA RNG/cursor values, and recomputes all 16 frame heads from externally hashed observations. It compares every output channel literally, then restores and compares the entire state again. It uses the same admitted deterministic backend flags as the producer. It refuses a CPU runtime before opening inputs or writing outputs.

The recursive comparator rejects missing state/head keys, changed model or Adam/RNG values, shape/dtype differences, container-type differences and nonfinite values. Independent training wall time may be excluded explicitly at the top level; inference restoration checks exclude nothing.

Live frozen Insula CPU evidence: `balanced16-replay-values-red-verified.json` records the missing comparator failure; `balanced16-replay-values-green-verified.json` records four passing literal comparator test groups. `balanced16-replay-preparation-suite-v3-verified.json` records the final 29 passing preparation groups, including refusal of both GPU workers on CPU. Frozen sources and full logs remain in the receipt's Insula paths. The runtime identity is inherited from the existing admitted CPU preparation root; this increment does not independently re-admit a new runtime image.

**Acceptance boundary:** CPU preparation only. The new GPU worker has not run on a native device. Native all16 head replay, 19-to-35 restart trajectory equality, independent literal losses, pooled native V3 metrics, bounded controller execution and verified HDFS checkpoint lifecycle remain required. No balanced16 sustained-fit or scientific improvement claim follows from these tests. The shared GPU remains owned by the expanded sweep; no competing job was launched.

Review found that resetting CUDA peak statistics after checkpoint/model/Adam loading would erase an earlier resource peak. The reset now occurs before all audit allocations; the final cap covers the whole worker. Native device evidence remains pending.
