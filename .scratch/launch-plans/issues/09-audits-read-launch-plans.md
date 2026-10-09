# 09: Audits read launch plans from receipts, old and new

**What to build:** Stage, retention, checkpoint and semantic-recovery audits read the mounts of a launch from one receipt reader. The reader accepts new plan records and old command-line receipts, so audits stop scanning command lines and old evidence still verifies.

**Blocked by:** 01, blob-store 11 (which rewrites the retention audit)

**Status:** done

- [x] One reader returns mounts by inside path, mode and digest (when known) for both receipt forms. `resources/command.py`'s command-line parser is kept only behind it and renamed for that job
- [x] `resources/stage.py`, `resources/checkpoint.py`, `retention/retention_audit.py`, `segmentation/semantic_recovery_receipt.py` and `segmentation/semantic_recovery_receipt_aligned.py` use the reader. No flag-string checks remain
- [x] Tests feed the reader a retained old receipt and a freshly recorded plan for an equivalent launch, and get the same mounts
- [x] Retained receipts used by existing tests still verify
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Added `insula.launch_plan.read_receipt_mounts(...)`, which returns mount facts by inside path for both receipt forms: new `launch_plan` records and old command-line receipts. For new plan records it reads `mounts` directly, preserving role, kind, mode and digest fields, and enforces the requested cleared-environment and Python-worker audit requirements from the plan record before returning mounts. For old receipts it accepts either top-level `command` or single-check `checks[0].command`, parses the legacy `bwrap` shape with option arity, and returns inside path, mode, kind, role, host path and digest when the read-only host mount is still available. The old receipt parser lives in the launch-plan reader path; `resources.command`'s old parser was renamed to `inspect_legacy_receipt_command(...)` for its resource-wrapper grammar, with a compatibility alias left only so frozen procedure records that import `inspect_command` are not broken.

Moved the active strict checks as follows:

- `resources/stage.py`: the native-output check now asks `read_receipt_mounts(..., require_python_worker=True)` for `/outputs` and still requires exactly a writable bind to `native_output`. The original Python-worker namespace grammar remains strict through the renamed legacy parser used by `wrapped_command(...)`.
- `segmentation/semantic_recovery_receipt.py` and `segmentation/semantic_recovery_receipt_aligned.py`: the old `bwrap`/`--unshare-all`/`--clearenv` flag-string check moved to `read_receipt_mounts(..., require_cleared_environment=True)`. For old command receipts the reader still requires the legacy namespace flags; for new plan records it requires the plan environment marker used by launch plans. Both validators require `/experiment` read-only, `/source` read-only and `/outputs` writable before transfer/accounting checks run.
- `resources/checkpoint.py`: no command or mount flag scan existed on this blob-store-migrated base; the active checkpoint/publication audits remain in `resources/checkpoint.py` plus `retention/publication.py`.
- `retention/retention_audit.py`: this active file no longer exists after the blob-store migration. The retained frozen successor is under `studies/balanced16/procedure_records/legacy_resource_retention_audit.py` and was left untouched. Active retention/publication checking is through `resources/checkpoint.py` and `retention/publication.py`, neither of which scanned launch flag strings on this base.

Retained-evidence handling:

- The reader equivalence test uses the real retained old receipt `autonomy/research/balanced16-sustained-contract-red-verified.json` for the legacy command shape, then rewrites equivalent mounts to sandbox-local fixture paths and compares them with a freshly recorded launch plan.
- The semantic receipt tests gained fallback fixture receipts under `autonomy/segmentation/testdata/semantic_receipts/{exact,aligned}` so retained receipt verification still runs outside `/source`. The copied receipts keep their audit shape, but `candidate_hashes` point at harmless `fixture-source.txt` files to avoid treating copied historical Python snapshots as active code. No retained receipt, frozen procedure record, lock, rootfs or cache outside the allowed worktree paths was edited.
- `//autonomy/blob_store:storage_boundary_test` passed after the fixture repair, confirming the blob-store storage-boundary scanner stays strict.

Tests and scans:

- Red/green reader test: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test.LaunchPlanTests.test_receipt_reader_normalizes_old_command_and_new_plan_mounts` failed first on missing `read_receipt_mounts`, then passed after implementation.
- Focused Python coverage: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.resources.command_test autonomy.resources.stage_test` passed `24/24`.
- Focused reader regression after the final tightening: `PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test.LaunchPlanTests.test_receipt_reader_normalizes_old_command_and_new_plan_mounts` passed `1/1`.
- Focused Bazel coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_test //autonomy/resources:stage_test //autonomy/resources:command_test //autonomy/segmentation:semantic_recovery_receipt_test //autonomy/segmentation:semantic_recovery_receipt_aligned_test` passed the runnable focused targets, `3/3`. The two semantic receipt targets are tagged `requires_live_gate` and are skipped by that focused command.
- Explicit semantic receipt coverage: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors --test_tag_filters=requires_live_gate,-requires_gpu,-known_failure //autonomy/segmentation:semantic_recovery_receipt_test //autonomy/segmentation:semantic_recovery_receipt_aligned_test` passed `2/2`.
- Static scan over the target active audit files found legacy flag parsing only in `insula/launch_plan.py`'s reader and `resources/command.py`'s renamed legacy/wrapper parser, not in `resources/stage.py`, `resources/checkpoint.py`, `retention/*` or the semantic recovery receipt validators.

Required gates:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed `184/184` tests. This worker branch enumerates `184` default `//autonomy/...` tests after analysis; the count stayed `184` after this ticket's data dependencies and reader changes.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed `17/17` tests.
- GPU 1 precheck before CUDA: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`. It was occupied at the first check and still occupied at the first scheduled 10-minute recheck, then freed at `2026-10-09T11:20:18Z` with memory.used `4 MiB` and compute apps listing only GPU 0's UUID.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed on GPU 1, `29/29` tests, including `//autonomy/insula:launch_plan_gpu_live_test`.
