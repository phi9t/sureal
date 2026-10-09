# 05: Camera, geometry, segmentation and inspection launches on launch plans

**What to build:** Camera, geometry, segmentation and inspection scripts that run work inside Insula declare their inputs on a launch plan and load their runtime lock through the module.

**Blocked by:** 01, blob-store 10 (which rewrites storage in the same scripts), semantic-layout 29 (which runs the semantic-recovery jobs)

**Status:** done

- [x] `camera/publish-scientific-camera.py`, `camera/scientific-camera-preprocess.py`, `camera/verify-camera-replay.py`, `geometry/verify_geometry.py`, `geometry/verify_scientific_scene.py`, `geometry/verify_reconstruction.py`, `segmentation/semantic_recovery_job.py`, `segmentation/semantic_recovery_job_aligned.py`, `segmentation/verify-segmentation-export.py`, `segmentation/verify-segmentation-contract.py`, `segmentation/verify-real-semantic-export.py` and `inspection/inspect_scene.py` build launch plans. Scripts that launch through `enter.sh` may keep doing so, because `enter.sh` is the module's command-line face after 01
- [x] No hand-parsed lock and no command-line splicing remain in these files. Spliced inputs become named inputs
- [x] Tests assert on the plans built against fixture locks
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Added concept-local launch helpers for camera, geometry, segmentation and inspection, then moved the twelve ticket scripts onto checked `load_runtime_lock` / `build_plan` / `render_plan` / `record_plan` paths. The previous inserted `--ro-bind` inputs are now named inputs (`/mnt`, `/opt`, `/srv` as applicable). Runtime receipts written by the migrated scripts record `launch_plan` data for the plan they execute; whole runtime-lock data comparisons remain on the loaded runtime. Semantic recovery keeps the two-lock preflight for both the shared cache and staging cache cohort queue locks.

Red/green and focused verification:

- New fixture-lock tests: `PYTHONPATH=autonomy python3 -m unittest camera.launches_test geometry.launches_test segmentation.launches_test inspection.launches_test segmentation.semantic_recovery_job_test` failed first on the missing `camera.launches` module, then passed after the helpers and migration, `9/9`.
- Focused Bazel: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/camera:launches_test //autonomy/geometry:launches_test //autonomy/segmentation:launches_test //autonomy/inspection:launches_test //autonomy/segmentation:semantic_recovery_job_test`: passed, `5/5` targets.
- Static scan over the twelve ticket files for `insula.entry.launch_plan`, `verify_rootfs`, runtime `.lock.json`, `index('--')`, `--ro-bind` splicing and direct `subprocess.run` launch calls found only dataset metadata lock reads, not runtime-lock parsing or command-line splicing.

Required gates:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, `182/182` tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, `17/17` tests.
- GPU 1 precheck before CUDA: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` was absent from `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`, with memory `4 MiB` and utilization `0%`.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed on GPU 1, `29/29` tests.
- GPU 1 postcheck after CUDA: the same UUID was absent from compute apps, with memory `4 MiB` and utilization `0%`.
