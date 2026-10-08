# 05: Camera, geometry, segmentation and inspection launches on launch plans

**What to build:** Camera, geometry, segmentation and inspection scripts that run work inside Insula declare their inputs on a launch plan and load their runtime lock through the module.

**Blocked by:** 01, blob-store 10 (which rewrites storage in the same scripts), semantic-layout 29 (which runs the semantic-recovery jobs)

**Status:** ready-for-agent

- [ ] `camera/publish-scientific-camera.py`, `camera/scientific-camera-preprocess.py`, `camera/verify-camera-replay.py`, `geometry/verify_geometry.py`, `geometry/verify_scientific_scene.py`, `geometry/verify_reconstruction.py`, `segmentation/semantic_recovery_job.py`, `segmentation/semantic_recovery_job_aligned.py`, `segmentation/verify-segmentation-export.py`, `segmentation/verify-segmentation-contract.py`, `segmentation/verify-real-semantic-export.py` and `inspection/inspect_scene.py` build launch plans. Scripts that launch through `enter.sh` may keep doing so, because `enter.sh` is the module's command-line face after 01
- [ ] No hand-parsed lock and no command-line splicing remain in these files. Spliced inputs become named inputs
- [ ] Tests assert on the plans built against fixture locks
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
