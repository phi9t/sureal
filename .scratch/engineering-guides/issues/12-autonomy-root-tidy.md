# 12: The autonomy root holds only its front door

**What to build:** `autonomy/` at its top level holds only its front-door files (`README.md`, `CONTEXT.md`,
`BUILD.bazel`) and concept directories. Each loose module joins the concept that owns it.

**Blocked by:** 07, 08

**Status:** ready-for-agent

Mapping (coordinator, 2026-10-11). The worker confirms each row against the code's actual dependencies and
records any deviation:

| From `autonomy/` | To | Why |
|---|---|---|
| `retained_receipt_sweep*.py` | `evidence/` | sweeps retained receipts |
| `source_snapshot_targets.bzl`, `source_snapshot_targets_test.py` | `evidence/` | source snapshot binding |
| `tracer.sh`, `tracer-*.schema.json`, `requirements-tracer.{in,lock}` | `dataset/tracer/` | the concept map puts tracer contracts in `dataset` |
| `architecture.py`, `ARCHITECTURE.md` | `studies/architecture/` | architecture study driver |
| `enter.sh` | `harness/insula/` (or delete if 08 made it redundant) | Insula entry |
| `roadmap.md`, `research-task-index.md` | `autonomy/docs/` | program docs |

- [ ] `git mv`, then references are fixed: Bazel labels and loads, `bazelw` and the launcher, docs, and constants
  naming these paths.
- [ ] The `docs/repo-structure.md` concept map and `autonomy/README.md` reflect the result.
- [ ] Live first: `./bazelw test //:repo_gate`, `//autonomy/...`, and CUDA on GPU 1 when it is free.
