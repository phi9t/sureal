# Ticket 27 Phase 27b Readmission Report

Generated: 2026-10-08T02:50:02Z

Status: blocked fail-closed at the phase 3 live-admission storage gate.

Worker branch: `worker/t27b-live-readmission`
Code/evidence HEAD: `98f8dd54f5906de1158033adff421a51c4b00f67`
Accepted code fix commit: `98f8dd54f5906de1158033adff421a51c4b00f67`
Evidence root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission`

## Verdict

Phase 0 preflight passed, phase 1 source snapshot publication/readback passed, and the accepted current GPU runtime-lock/rootfs rebinding fix was committed. The authorized excluded-test readmission recorded 1 pass, 9 prerequisite-missing rows, and 1 failing row; no skipped row is counted as admitted.

The live balanced16 command was run only through `PYTHONPATH=autonomy python3 -m training_execution.run_sustained --run-id <RUN_ID> --admission-only`. The first attempt exposed stale GPU runtime-lock/rootfs binding and led to the accepted fix. The second attempt, after that fix, failed before training during `reserve_write(W, 2 GiB)` because the preserved shared scientific-processing accounting rejects symlinks. No live receipt was emitted, no journal entry was appended, and no scientific result or sweep completion is claimed.

## Box-By-Box Verdicts

| Ticket 27 box | Verdict | Evidence |
| --- | --- | --- |
| The sweep recipes, frames and anchor templates are unchanged from the preregistration | `pass` | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/preflight.json` sha256 `d66bc5ec820fdac1049bd61254d8758684b33be90a3debcf4acd9705bcf316e9` |
| Each recipe admission pins a source snapshot stored in HDFS and the new rootfs digest | `partial` | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots-final-accepted-check/source-closure-final-check.json` sha256 `f8aa6a409a15ec45464e9ac447c6aeb2386d1d108efa79371cde31afdda9d3a1` |
| Every runtime-lock check listed in ticket 01 is re-admitted on the new images | `not_admitted` | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/runtime-consumers-storage-blocker/runtime-consumers-summary.json` sha256 `f2b131c3529eff0133a995ff3f513b60245df80effc14e65045de41bc35aba30` |
| A live gate executes the admitted candidate in the new rootfs and its receipt verifies against the snapshot | `failed_before_training` | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/live-admission/not-admitted-storage-blocker.json` sha256 `a6fe04579f9f35fe2c59a149248f7de96237ed2817a105524899787acf00fc6a` |
| The journal records the re-admission and what changed since the original admission | `not_run` | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/journal/not-run-storage-blocker.json` sha256 `86d896efdc5ed808a487f1172a97908d611c88a3cff387a61adae8150b9427ce` |
| The task index states the sweep new status | `not_changed_by_worker` | `.scratch/semantic-layout/issues/27-readmit-balanced16.md` |

## Phase Evidence

- preflight: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/preflight.json` sha256 `d66bc5ec820fdac1049bd61254d8758684b33be90a3debcf4acd9705bcf316e9`
- source publication: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots-after-fix/publication-summary.json` sha256 `d7fc6ed7df8e75a1a5a8b9ebc72c18047c2608409c44c34d3362d344de6f6f90`
- source final check: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots-final-accepted-check/source-closure-final-check.json` sha256 `f8aa6a409a15ec45464e9ac447c6aeb2386d1d108efa79371cde31afdda9d3a1`
- excluded initial exact: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests/excluded-tests-summary.json` sha256 `46096fe3decd90efc00ecb2c6526291100476a2a266df13e3fd83a66cb5b0c23`
- excluded authorized: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/excluded-tests-summary.json` sha256 `93875f2a43f195d3d7d97d3cabc7d27c45d5f27ce750b3dd84ade1e71d995baa`
- excluded odirect rerun: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/reruns/autonomy_segmentation__staged_derived_archive_aligned_test.rerun.json` sha256 `e42ba8d8cb1138af992fd4de41fc8fea3148b2029800984451be9b7005a9cba4`
- live blocker: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/live-admission/not-admitted-storage-blocker.json` sha256 `a6fe04579f9f35fe2c59a149248f7de96237ed2817a105524899787acf00fc6a`
- storage blocker: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/storage-blocker/storage-blocker-summary.json` sha256 `ba49932a6f01a7485983f1c76d26a9384bc933bbb9a739bf2afc37cc5b1a481e`
- retention coverage: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/storage-blocker/retention-coverage-summary.json` sha256 `4ff3bbacfacbab523b1786cc237c3c1b8da7bebba7b680a70b86e1f07bf51849`
- runtime consumers: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/runtime-consumers-storage-blocker/runtime-consumers-summary.json` sha256 `f2b131c3529eff0133a995ff3f513b60245df80effc14e65045de41bc35aba30`
- journal: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/journal/not-run-storage-blocker.json` sha256 `86d896efdc5ed808a487f1172a97908d611c88a3cff387a61adae8150b9427ce`

## Preflight

- Summary: `pass` with `{"device_ownership": "pass", "disk_floor": "pass", "hdfs_auth_listing": "pass", "preregistration": "pass", "rootfs_locks": "pass"}`.
- GPU 1 `/dev/nvidia1`: compute processes `0` at preflight; GPU 4 observed in use by `1` process.
- `/data02` available before phase 0: `86887133184` bytes; floor `42949672960` bytes.
- HDFS auth/listing: `hdfs://harunava/user/tiger/waystone/sureal/source-snapshots/` passed via token-file auth.
- Rootfs locks: CPU `429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb`, GPU `5a1af6a165eb3d59781eda28fee6acd2672b6a53e3645252eeb6579beb720eb4`, metrics `831a5955ce709cb46b82688ba0f0371c37e1af707ffb870b24c555d53d4f5542`, motion CLI `c471473b944157119d0d6440a9e95515dfda4d4c554d4cfafa4374da40bf9c8e`.

## Source Snapshots

Publication/readback status: `pass` for `8` of `8` targets. Final accepted-tree check: `True`.

| Target | Files | Source snapshot digest | Matches after-fix HDFS publication |
| --- | ---: | --- | --- |
| `//autonomy/resources:execute_worker` | 49 | `00945a61700098679d7cd368d7cb346d9df3b0516f396368734986dd3a51db69` | `True` |
| `//autonomy/training_execution:train_sustained` | 246 | `524ffe24704ce9fabd05db95aed7244d7bb7a2434220523093eabcd498de4407` | `True` |
| `//autonomy/training_execution:run_sustained` | 246 | `524ffe24704ce9fabd05db95aed7244d7bb7a2434220523093eabcd498de4407` | `True` |
| `//autonomy/retention:publish_native_cache` | 64 | `90a619d88d476e965e8f5fe96e5e5a18455b472bd6a3834b528438132c6f4b55` | `True` |
| `//autonomy/retention:publish_sustained_checkpoint` | 64 | `90a619d88d476e965e8f5fe96e5e5a18455b472bd6a3834b528438132c6f4b55` | `True` |
| `//autonomy/retention:publish_sustained_pilot` | 64 | `90a619d88d476e965e8f5fe96e5e5a18455b472bd6a3834b528438132c6f4b55` | `True` |
| `//autonomy/studies:architecture_experiment_runner` | 327 | `59bce6964ef2f3674277e597e9ce04d2b8aa55319f2a73dff3231556852a9758` | `True` |
| `//autonomy/studies:scientific_cohort` | 131 | `66cba6d2d777ef9d0a5fb67174a5b53bf39676fc025d2bb1a4693631f2571f78` | `True` |

## Excluded Tests

Initial exact row commands without an override selected zero test bodies due the repository default tag filters; they are preserved in the JSON ledger and not counted as admissions. Initial summary: `11` skipped-not-admitted of `11` rows.

Authorized command-line `--test_tag_filters=` override summary: `1` pass, `9` prerequisite missing, `1` fail, `0` skipped-not-admitted.

| Label | Status | Exit | Wall seconds | Evidence |
| --- | --- | ---: | ---: | --- |
| `//a/evaluation:metrics_sustained_v3_test` | `pass` | 0 | 6.134 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_evaluation__metrics_sustained_v3_test.json` |
| `//a/camera:project_camera_test` | `prerequisite_missing` | 3 | 6.06 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_camera__project_camera_test.json` |
| `//a/insula:m0_receipt_test` | `prerequisite_missing` | 3 | 6.416 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_insula__m0_receipt_test.json` |
| `//a/motion:ingestion__motion_causal_projection_test` | `prerequisite_missing` | 3 | 6.034 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_motion__ingestion__motion_causal_projection_test.json` |
| `//a/motion:cli__motion_joint_cli_test` | `prerequisite_missing` | 3 | 6.021 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_motion__cli__motion_joint_cli_test.json` |
| `//a/motion:cli__motion_native_cli_test` | `prerequisite_missing` | 3 | 6.083 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_motion__cli__motion_native_cli_test.json` |
| `//a/motion:pooled__motion_pooled_cli_test` | `prerequisite_missing` | 3 | 6.872 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_motion__pooled__motion_pooled_cli_test.json` |
| `//a/segmentation:semantic_recovery_accounting_test` | `prerequisite_missing` | 3 | 5.914 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_segmentation__semantic_recovery_accounting_test.json` |
| `//a/segmentation:semantic_recovery_receipt_test` | `prerequisite_missing` | 3 | 5.934 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_segmentation__semantic_recovery_receipt_test.json` |
| `//a/segmentation:semantic_recovery_receipt_aligned_test` | `prerequisite_missing` | 3 | 6.213 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_segmentation__semantic_recovery_receipt_aligned_test.json` |
| `//a/segmentation:staged_derived_archive_aligned_test` | `fail` | 3 | 6.087 | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests-authorized-override/autonomy_segmentation__staged_derived_archive_aligned_test.json` |

The staged derived archive aligned row was rerun with disk-backed TMPDIR under `E/t27b-readmission/odirect-tmp`; it still exited 3 with `OSError: [Errno 22] Invalid argument` from the `O_DIRECT` open path. That row is a fail, not an admission.

## Live Admission

| Run ID | Exit | Wall seconds | Result | Evidence |
| --- | ---: | ---: | --- | --- |
| `t27b20261008T021233Z` | 1 | 27.102 | stale GPU runtime lock/rootfs mismatch; fixed by accepted rebinding patch | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/live-admission/t27b20261008T021233Z/admission-command.json` |
| `t27b20261008T022321Z` | 1 | 32 | failed before training at preserved scientific-processing gate | `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/live-admission/t27b20261008T022321Z/admission-command.json` |

Final live status: `failed_before_training`. Receipts verified: `0`.

## Storage Gate

Strict `unique_payload_bytes(W)` exit code: `1`.
First offending symlink from the strict error: `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/red/mutants/xyz_shift/6-5-1-range.features.bin`.
Bounded symlink count: `2970`.
Diagnostic unique regular-file bytes excluding symlinks: `15329280496`. This diagnostic is not an admission pass.
`du -x -B1 -d 1 W` total: `15555276800` bytes for `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing`.

Bounded symlink sample from `find W -xdev -type l` (first lines of the recorded log):

- `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/green-corruptions/mutants/feature_range/0-1-1-range.pixels.bin -> /source/training/0-1-1-range.pixels.bin`
- `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/green-corruptions/mutants/feature_range/0-1-1-range.xyz.bin -> /source/training/0-1-1-range.xyz.bin`
- `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/green-corruptions/mutants/feature_range/0-1-2-range.features.bin -> /source/training/0-1-2-range.features.bin`
- `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/green-corruptions/mutants/feature_range/0-1-2-range.pixels.bin -> /source/training/0-1-2-range.pixels.bin`
- `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/green-corruptions/mutants/feature_range/0-1-2-range.xyz.bin -> /source/training/0-1-2-range.xyz.bin`

Largest top-level `scientific-processing` entries from the bounded `du` evidence:

| Bytes | Path |
| ---: | --- |
| 15555276800 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing` |
| 2025304064 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort-v1` |
| 1776508928 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort16-baseline-fit20261002a` |
| 1668546560 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/balanced16-sustained-baseline-controller20261003a` |
| 1382256640 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/resource-retention-balanced16-sustained-baseline-controller20261003a-shared-5a74e356862244deb88a264e48f82908` |
| 1367490560 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort16-baseline-balanced20261002a` |
| 1367490560 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort16-residual_bev-balanced20261002b` |
| 494874624 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/native-overfit-v1` |
| 361762816 | `/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/architecture-window_bev-v1` |

HDFS retention coverage found verified release-plan coverage for these top-level entries. This worker did not delete, move, or release anything.

| Top level | Covered bytes | Covered entries | Existing bytes | Release-completed receipts |
| --- | ---: | ---: | ---: | ---: |
| `balanced16-sustained-admission-native20261003a` | 1653672723 | 76 | 0 | 2 |
| `overfit-native-cache-v1` | 1040757892 | 128 | 0 | 1 |

## Runtime And Journal

Runtime consumers: `78` rows, admitted count `0`, dispositions `{'not_run_due_phase3_storage_gate': 78}`.
Journal: `not_run`. Reason: Journal append and evidence.publish are authorized only after live acceptance; live admission failed before training on the preserved scientific-processing admission gate.

## Verification Recorded

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors --test_tag_filters= //autonomy/training_execution:sustained_controller_backend_test //autonomy/training_execution:run_sustained_test` -> exit `0`, result `2/2 passed`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` -> exit `0`, result `152/152 passed`.

## Command Ledger

The structured JSON report contains `78` command records with command, cwd, exit code, wall clock where recorded, evidence path, evidence digest, and stdout/stderr log paths where available.

## Not Checked

- No scientific result is claimed.
- No full balanced16 sweep was run.
- No live admission receipt was emitted or verified after the phase 3 storage gate stopped the run.
- No journal entry was appended and evidence.publish was not run.
- No runtime-consumer row was counted as admitted after the storage gate stopped live admission.
- No file was deleted, moved, released, or normalized under scientific-processing.
- The ticket file and task index were not edited by this worker.
- autonomy/tools/pins.py check was not completed because that file is absent in this worktree.
