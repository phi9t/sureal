# 04: Dataset launches on launch plans

**What to build:** Every dataset script that runs work inside Insula (cohort acquisition, scientific preprocessing, scene and sidecar publishing, archive and native verification, scientific replay, native shape source replay) declares its inputs on a launch plan and loads its runtime lock through the module.

**Blocked by:** 01, blob-store 09 (which rewrites storage in the same dataset scripts)

**Status:** ready-for-agent

- [ ] `dataset/acquire-scientific-cohort.py`, `scientific-preprocess.py`, `publish-scientific-scene.py`, `publish-scientific-sidecars.py`, `publish-scientific-sidecars-bounded.py`, `publish-scientific-sidecars-compressed.py`, `verify-archive-dataset.py`, `verify_native.py`, `verify-scientific-replay.py` and `native_shape_source_replay.py` build launch plans. No hand-parsed lock and no command-line splicing remain
- [ ] Inputs spliced today (`/opt`, `/srv`, `/mnt`, `/tmp/*`) are named inputs with explicit modes
- [ ] Where a script pinned a whole lock against an externally recorded lock, that comparison still happens, on the loaded lock
- [ ] Tests assert on the plans built against fixture locks
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
