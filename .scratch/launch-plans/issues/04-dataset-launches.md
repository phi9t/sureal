# 04: Dataset launches on launch plans

**What to build:** Every dataset script that runs work inside Insula (cohort acquisition, scientific preprocessing, scene and sidecar publishing, archive and native verification, scientific replay, native shape source replay) declares its inputs on a launch plan and loads its runtime lock through the module.

**Blocked by:** 01, blob-store 09 (which rewrites storage in the same dataset scripts)

**Status:** done

- [x] `dataset/acquire-scientific-cohort.py`, `scientific-preprocess.py`, `publish-scientific-scene.py`, `publish-scientific-sidecars.py`, `publish-scientific-sidecars-bounded.py`, `publish-scientific-sidecars-compressed.py`, `verify-archive-dataset.py`, `verify_native.py`, `verify-scientific-replay.py` and `native_shape_source_replay.py` build launch plans. No hand-parsed lock and no command-line splicing remain
- [x] Inputs spliced today (`/opt`, `/srv`, `/mnt`, `/tmp/*`) are named inputs with explicit modes
- [x] Where a script pinned a whole lock against an externally recorded lock, that comparison still happens, on the loaded lock
- [x] Tests assert on the plans built against fixture locks
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Added `autonomy/dataset/launches.py` as the dataset launch-plan facade over `load_runtime_lock`, `build_plan`, `render_plan` and `record_plan`, with `load_pinned_dataset_runtime(...)` preserving whole-lock comparisons after strict module loading. Migrated the named dataset scripts to build structured launch plans and render them only at `subprocess.run(...)`; old `/opt`, `/srv`, `/mnt` and `/tmp/*` command-line splices are now `named_inputs`/`writable_inputs` with explicit modes. Existing receipt `runtime_lock` fields remain whole-lock data, and launch-plan receipt records are added beside the rendered command evidence.

Focused red/green:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.dataset.launches_test`: failed first because `dataset.launches` did not exist, then passed `2/2` after implementation.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/dataset:launches_test`: passed `1/1`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/dataset/...`: passed `24/24`.

Required gates after final cleanup:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed `178/178`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed `17/17`.
- GPU 1 precheck at `2026-10-09T04:46:13Z`: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `4 MiB` used, `0%` utilization, and no compute app for that UUID. Earlier check found GPU 1 occupied, so CUDA waited until it was free.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed `29/29`.
- GPU 1 postcheck at `2026-10-09T04:48:37Z`: same UUID, `4 MiB` used, `0%` utilization, and no compute app for that UUID.
