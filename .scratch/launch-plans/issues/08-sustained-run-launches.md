# 08: The sustained run launches from fresh launch plans

**What to build:** The balanced16 sustained run's admission, controller, training, replay and transition audit build fresh launch plans (GPU plans for GPU stages, CPU and metrics plans otherwise) instead of replaying the command from an old receipt (`detector-gpu-live-a`) and rewriting it by mount target.

**Blocked by:** 02, blob-store 11 (the blob-store migration rewrites the sustained run's storage)

**Status:** ready-for-agent

- [ ] `training_execution/admit_sustained.py`, `sustained_controller_backend.py`, `train_sustained.py`, `replay_sustained.py` and `audit_sustained_transition.py` build launch plans and load the GPU, CPU and metrics locks through the module. No code reads a command or a runtime lock out of an old receipt, and `rebind_rootfs_mount` is deleted
- [ ] Every input spliced today (`/tmp/inputs`, `/tmp/native`, `/tmp/physical`, `/tmp/boxes`, `/tmp/runtime-lock.json`, `/tmp/scientific` and the snapshot store) is a named input. `CUBLAS_WORKSPACE_CONFIG` is declared environment
- [ ] GPU stages request GPU 1 by index from the run's own configuration
- [ ] Offline tests assert on each stage's plan. A `requires_gpu` smoke test runs one trivial stage through the controller's GPU plan on GPU 1
- [ ] The sustained run is not re-admitted here. Blob-store 12 does that once, after this ticket
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
