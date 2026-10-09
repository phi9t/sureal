# 12: One launch helper instead of five per-concept copies

**What to build:** Scripts in every concept build, run and record launch plans by calling the launch-plan module directly. The near-identical per-concept helper modules added by tickets 04 and 05 (dataset, camera, geometry, inspection, segmentation) are gone, so a change to how plans are loaded or run is made once.

**Blocked by:** 04, 05

**Status:** done

- [x] The launch-plan module offers the two things every helper copy added: loading a root filesystem's runtime lock from its default lock path, and running a rendered plan as a subprocess. Path coercion of named and writable inputs happens inside `build_plan`
- [x] The per-concept `launches.py` helpers in dataset, camera, geometry, inspection and segmentation are deleted, and their callers use the launch-plan module. Any concept-specific behaviour they held (for example the segmentation helper's metrics root) moves to its caller or to the root registry
- [x] Their plan-against-fixture-lock tests are kept, retargeted at the callers or the module, not deleted
- [x] Source pins and code-hash lists that named a deleted helper name the launch-plan module instead
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Found while landing tickets 04 and 05: the five helper modules differ only in the name of their build/run functions (the deletion test: deleting them moves nothing but four pass-throughs).

### 2026-10-09 worker evidence

Done. Added `load_default_runtime_lock(...)` and `run_plan(...)` to `autonomy/insula/launch_plan.py`, moved named and writable input path coercion into `build_plan(...)`, and deleted the dataset, camera, geometry, inspection and segmentation `launches.py` helper modules. The migrated callers now import `build_plan`, `load_default_runtime_lock`, `render_plan`, `record_plan` and `run_plan` from `insula.launch_plan`, and use `runtime_roots` directly for CPU or metrics root selection. Whole-lock comparisons in pinned dataset callers remain explicit after loading the checked runtime lock.

Retargeted the fixture-lock plan tests for dataset, camera, geometry, inspection and segmentation to the shared launch-plan module; no plan-against-fixture-lock coverage was deleted. Source pin and code-hash lists that named a deleted helper now name `insula/launch_plan.py` and `insula/runtime_roots.py` instead.

Verification:

- Red/green focused module test: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test` failed first on missing `load_default_runtime_lock`, then passed `15/15`.
- Focused Python coverage after caller migration: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.dataset.launches_test autonomy.camera.launches_test autonomy.geometry.launches_test autonomy.inspection.launches_test autonomy.segmentation.launches_test autonomy.segmentation.semantic_recovery_job_test`: passed `26/26`.
- Focused Bazel coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/dataset:launches_test //autonomy/camera:launches_test //autonomy/geometry:launches_test //autonomy/inspection:launches_test //autonomy/segmentation:launches_test //autonomy/segmentation:semantic_recovery_job_test`: passed `7/7`.
- Default CPU suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed `185/185`.
- Parallax suite: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed `17/17`.
- GPU 1 precheck before CUDA: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` was absent from `nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`, and GPU 1 memory was `4 MiB`.
- CUDA suite on GPU 1 only: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed `29/29`, including `//autonomy/insula:launch_plan_gpu_live_test`.
- GPU 1 postcheck after CUDA: the same UUID was absent from compute apps, and GPU 1 memory was `4 MiB`.
