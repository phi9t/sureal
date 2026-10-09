# 01: Pin rendered command lines and retained-receipt verification

**What to build:** A safety net for the rest of this feature.

- A golden characterisation test pins the exact rendered argv for every plan shape that runs today.
- A repeatable offline sweep runs every active receipt verifier over the retained receipts it covers and records the pass counts.

No behaviour changes.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Golden argv test.** A test renders representative plans and asserts byte-identical argv: CPU, GPU with driver pins, symlink rootfs entries, `/tmp` tmpfs with mounts under `/tmp/`, resource-wrapped, and a sustained stage.
  - The expected values are generated at the base commit and checked in.
  - The test uses fixtures, not host-specific paths, so it runs on any machine and in the hermetic Bazel sandbox.
- [x] **Retained-receipt sweep.**
  - A script or test (manual or tagged, if it needs host data) runs the active verifiers offline over retained receipts. This includes the plan-record receipts from the balanced16 re-admission (`autonomy/research/balanced16-sustained-bs1220261009T154234Z-*`) and the legacy command-line receipts.
  - It prints per-verifier pass and fail counts.
  - It writes nothing into retained evidence.
- [x] **Baseline counts** from the sweep are recorded in this ticket's comments.
- [x] **Gates pass:** the CPU suite, `//parallax/...`, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

2026-10-09 Done:

- Added `autonomy/training_execution/launch_plan_golden_test.py`, generated from base `6e4eda1540c07acee26a5133802850f748ddbe38`, pinning rendered argv for CPU, GPU with driver pins/minor/uuid, symlink split rootfs, `/tmp` tmpfs with child mounts, resource wrapping through `wrap_resource_plan`, resource wrapping through `with_mounts`, `wrap_rendered_plan_command`, and a sustained stage plan.
- Added `autonomy/retained_receipt_sweep.py` plus `//autonomy:retained_receipt_sweep` and the manual `//autonomy:retained_receipt_sweep_host_test` target. The sweep runs offline, uses `$TMPDIR` for temporary source-snapshot materialization, and does not write retained evidence.
- Host retained-receipt sweep command: `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data`.
- Baseline retained-receipt counts:
  - `launch_plan_receipt_readers`: 2279 passed, 0 failed, 0 skipped.
  - `balanced16_stage_check`: 14 passed, 0 failed, 0 skipped.
  - `resource_stage_proof_validation`: 14 passed, 0 failed, 0 skipped.
  - `resource_checkpoint_validation`: 2 passed, 0 failed, 0 skipped.
  - `legacy_resource_publication_validation`: 9 passed, 0 failed, 0 skipped.
- Focused checks:
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/training_execution/launch_plan_golden_test.py`: pass.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/training_execution:launch_plan_golden_test //autonomy:retained_receipt_sweep_host_test`: pass. The manual host sweep target skips when Bazel's Insula test view does not expose the retained host cache; the host-side `--require-host-data` command above is the authoritative count run.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 187/187 passed. Base was 186; count increased by 1 because `launch_plan_golden_test.py` is included by the existing training execution test glob.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed.
  - GPU 1 was free before CUDA (`GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, no compute process on that UUID). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed.
