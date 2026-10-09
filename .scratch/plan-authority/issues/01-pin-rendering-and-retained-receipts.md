# 01: Pin rendered command lines and retained-receipt verification

**What to build:** A safety net for the rest of this feature.

- A golden characterisation test pins the exact rendered argv for every plan shape that runs today.
- A repeatable offline sweep runs every active receipt verifier over the retained receipts it covers and records the pass counts.

No behaviour changes.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Live baseline on the base code, run first.** Real runs of the three motion verifiers and `replay_motion_foundation.py`, one resource-measured stage, and the GPU live gate. Run on GPU 1 only, when it is free. Record the commands, receipts, sha256 values and durations. These fresh receipts join the sweep, and they are the before picture that tickets 02-04 must reproduce.
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

2026-10-09 Live baseline addendum:

- Live root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z`.
- GPU 1 preflight before live GPU gate: `nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader,nounits` reported GPU 1 as `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used; `nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader,nounits` showed no compute process on that UUID.
- Live commands:
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/motion-cli.8KQiIW PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-cli`
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/motion-cli-expanded.ks25mG PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-cli-expanded`
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/motion-native.5JNJ3Z PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-native`
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/motion-foundation.QYCe21 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id foundation-20261009T223117Z --output-root /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z`
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/gpu-live.bQ6JWX CUDA_VISIBLE_DEVICES=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/insula/verify_gpu_live.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/gpu-live`
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/resource-stage.hOyfYD systemd-run --user --scope --same-dir --collect --unit=sureal-sustained-pa01e-20261009T223117Z -p MemoryAccounting=yes -p MemoryMax=17179869184 -p MemorySwapMax=0 env TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/resource-stage.hOyfYD PA01_LIVE_ROOT=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z PA01_REPO=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/final26-closeout-verify-worker-pa01-pin-rendering PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/resource-stage.hOyfYD/resource_baseline.py`
- Live receipt manifest: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/receipt-manifest.json`, sha256 `e614ecb4fe35222f3909c436e36efff1051c50a510afe6f7def28726d4854d3d`.
- Live receipts:
  - Motion CLI: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-cli/receipt.json`, sha256 `4b47c511c3e64a9c774bbcc33ee13a4f69b6ecf758b8fc14f7e93ae8d98cfdb6`, duration `1.530223832000047` seconds.
  - Motion CLI expanded: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-cli-expanded/receipt.json`, sha256 `cfc0036af8fd71fe22942fccf42cad5860dc54b957941a454e682f48e73fc960`, duration `1.515594781958498` seconds.
  - Motion native: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/motion-native/receipt.json`, sha256 `afc77ee4b87198e2b479c868225a6ff536f76c81d504941a0128c5cde0c843d6`, duration `1.7702654140302911` seconds.
  - Motion foundation replay: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/foundation-20261009T223117Z/receipt.json`, sha256 `fb6939b223d6c8e4f1caeafcfe00d6cb74dfb54de38b22346428deb1115a6444`, duration `10.648953314987011` seconds.
  - GPU live gate: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/gpu-live/receipt.json`, sha256 `f03baba1d068643aec3d2a46b210789106f1da66670f824f0d665b009566dd6e`, duration `3.0611766369547695` seconds.
  - Resource stage native receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/resource-stage-file-blob/case/tiny-live-0-verified.json`, sha256 `eafbf118988a4a5722cb734f0b700829b63e93bab1d8bee914ca4f5393738abf`.
  - Resource stage proof: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/resource-stage-file-blob/case/resource-layer/stages/tiny-live-0/resource-admitted.json`, sha256 `95c1294ea27cea2c318ec6f5e059dd71ca9a9b7f5eb1ab7a9c7ddbf0c0122f18`, duration `0.12582077004481107` seconds.
  - Resource identity: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/resource-stage-file-blob/case/resource-layer/identity.json`, sha256 `9fc85e9a32b53cc6b6092d6f098b1c8d468ca349159005bc99589da91ff9f6ba`.
- Resource stage wrote only new files under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/resource-stage-file-blob/` and its local source snapshot store; it did not touch HDFS.
- Extended sweep command: `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/receipt-manifest.json`.
- Extended sweep counts:
  - `launch_plan_receipt_readers`: 2343 passed, 0 failed, 0 skipped.
  - `balanced16_stage_check`: 14 passed, 0 failed, 0 skipped.
  - `resource_stage_proof_validation`: 15 passed, 0 failed, 0 skipped.
  - `resource_checkpoint_validation`: 2 passed, 0 failed, 0 skipped.
  - `legacy_resource_publication_validation`: 9 passed, 0 failed, 0 skipped.
  - `fresh_live_receipt_validation`: 7 passed, 0 failed, 0 skipped.
- Default retained sweep without live extras still matches the prior baseline counts: `launch_plan_receipt_readers` 2279, `balanced16_stage_check` 14, `resource_stage_proof_validation` 14, `resource_checkpoint_validation` 2, `legacy_resource_publication_validation` 9; all failed/skipped counts were 0.
- Tampered-copy proof: copied the fresh resource proof to `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/tamper-final.5asa9A/resource-admitted-tampered.json`, changed only the `/tmp/resource-layer` mount digest, and ran `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --extra-receipt /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp/tamper-final.5asa9A/resource-admitted-tampered.json`; it exited 1 with `ValueError: recorded launch plan mount digest differs: /tmp/resource-layer`.
- Focused checks after adding fresh-receipt sweep coverage:
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep_test.py`: 3 tests passed.
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa01-pin-rendering-20261009T212759Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/training_execution/launch_plan_golden_test.py`: 1 test passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy:retained_receipt_sweep_test //autonomy:retained_receipt_sweep_host_test`: 2/2 tests passed.
- Required gates after the live-baseline sweep changes:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 188/188 passed. The count is now +2 from base 186: `launch_plan_golden_test.py` plus `retained_receipt_sweep_test.py`.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed.
  - GPU 1 was free before CUDA (`GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, no compute process on that UUID). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed.
