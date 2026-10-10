# 02: The plan carries named-input digests and is the only authority for GPU driver pins

**What to build:**

- A launch plan can declare the digest of any named input when it is built, and the public `record_plan` records it.
- The sustained controller's hidden-attribute path and its local `record_plan` are gone.
- For new receipts, GPU driver pins are checked once, from the `gpu-driver:*` mount digests in the plan record.
- Legacy receipts keep their current driver check.

**Blocked by:** 01

**Status:** done

- [x] The plan builder accepts declared named-input digests, and `insula.launch_plan.record_plan` records them. There is no `object.__setattr__` on a `LaunchPlan` anywhere in active code.
- [x] The scientific-root and source-snapshot digests of sustained stages reach the receipt through the public recording path. A test proves that recording through the public `record_plan` keeps them.
- [x] **New-receipt driver pins:**
  - Verification reads only the plan record.
  - Any `driver_hashes` field still written is derived from the plan record when the receipt is written.
  - `resources.dependencies` and `admit_sustained` read pins through one launch-plan function.
- [x] A mismatched driver digest in a new receipt fails with one clear error. A test covers a tampered record.
- [x] **Live acceptance comes first.** Real runs on this ticket's code: the ticket 01 live set, including a GPU live gate on GPU 1 whose fresh receipt carries driver pins only through the plan record. The fresh receipts must verify, and a tampered driver digest must fail. Record the results in Comments.
- [x] The golden argv test from 01 is unchanged and passes.
- [x] The retained-receipt sweep's counts match ticket 01's baseline exactly.
- [x] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

### 2026-10-10 Done

Implemented in `d9091a3` (`Carry plan input and GPU driver digests`). The implementation adds declared named-input digests to `LaunchPlan`, records them through the public `insula.launch_plan.record_plan`, removes the sustained controller's hidden `LaunchPlan` mutation/local record path, and routes new GPU driver verification through plan-record `gpu-driver:*` mounts. Legacy receipts keep their existing driver check.

Code checks:

- `rg -n "object\.__setattr__|driver_hashes_from_plan|record_plan as record_launch_plan|from dataclasses import replace" autonomy -g '*.py'`: no `object.__setattr__` on `LaunchPlan`, no old local `driver_hashes_from_plan`, and no active old `record_plan as record_launch_plan` except the unchanged golden test alias in `autonomy/training_execution/launch_plan_golden_test.py`.
- `git diff --exit-code -- autonomy/training_execution/launch_plan_golden_test.py`: unchanged.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.retained_receipt_sweep_test autonomy.training_execution.run_sustained_test`: 53 tests passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.training_execution.launch_plan_golden_test`: 1 test passed.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/training_execution:sustained_controller_backend_test`: 1/1 passed after the fake-driver fixture covered `check_stage`.

Live run root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z`.

Live commands:

- Non-GPU ticket 01 live set, duration 25.8213s:
  `RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"; LIVE_ROOT="/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-${RUN_ID}"; WORKER_TMP="/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp"; mkdir -p "$LIVE_ROOT"; printf '%s\n' "$RUN_ID" > "$LIVE_ROOT/run-id.txt"; TMPDIR="$(mktemp -d "$WORKER_TMP/motion-cli.XXXXXX")" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py "$LIVE_ROOT/motion-cli"; TMPDIR="$(mktemp -d "$WORKER_TMP/motion-cli-expanded.XXXXXX")" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py "$LIVE_ROOT/motion-cli-expanded"; TMPDIR="$(mktemp -d "$WORKER_TMP/motion-native.XXXXXX")" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py "$LIVE_ROOT/motion-native"; TMPDIR="$(mktemp -d "$WORKER_TMP/motion-foundation.XXXXXX")" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id "foundation-${RUN_ID}" --output-root "$LIVE_ROOT"; printf '%s\n' "$LIVE_ROOT"`.
- GPU 1 preflight: uuid `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, memory.used 4 MiB, no compute process on that UUID.
- GPU live gate:
  `TMPDIR=$(mktemp -d /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp/gpu-live.XXXXXX) CUDA_VISIBLE_DEVICES=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/insula/verify_gpu_live.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/gpu-live`; output included `PASS GPU analytic and convolution fixtures`.
- Small resource stage:
  `PA02_REPO="$PWD" PA02_LIVE_ROOT="/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z" PA02_RESOURCE_LABEL=resource-stage-file-blob-r5 TMPDIR="$(mktemp -d /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp/resource-stage.XXXXXX)" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp/resource-stage.DoauVj/resource_baseline.py`.

Fresh receipt manifest:

- `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/receipt-manifest.json`
- sha256 `b61af33725ba4751d1ba30dfe123e435474e23c7f0072a538841cb5e83efff78`

Fresh receipt sha256 values and durations:

- `motion-cli/receipt.json`: sha256 `42711b4f0d7bc68f78d5be2329ebe32e2bc0df67e18541c5c8868c46db229364`; duration `1.3119487379444763`.
- `motion-cli-expanded/receipt.json`: sha256 `0f35a1d44a5019107c34ae0683c7d91287cd96348db336b4a9077993d217fb01`; duration `1.3175941839581355`.
- `motion-native/receipt.json`: sha256 `c7f247f66da029ec4b5f0c9e8a4aa3703a57946e6735b9b4102c8a4b3f0506f9`; duration `1.5189302400685847`.
- `foundation-20261009T232458Z/receipt.json`: sha256 `2545bfd5708f3649f249b44e0874ed45adcae99c4c1b464735218738d95bd0ca`; duration `10.735600739018992`.
- `gpu-live/receipt.json`: sha256 `002f2f6c04f596d4d1ffc5129ea9003934116c9608574d800da09692f96d745f`; duration `3.169861322036013`; no top-level `driver_hashes`; 9 `gpu-driver:*` launch-plan roles.
- `resource-stage-file-blob-r5/case/tiny-live-0-verified.json`: sha256 `cc3c7f2bd9ca7fe096f242c62efd9482546b6db29a51e0833f0060d94bc7d68a`; stage `tiny-0`; exit_code 0; duration `0.17672878596931696`.
- `resource-stage-file-blob-r5/case/resource-layer/stages/tiny-live-0/resource-admitted.json`: sha256 `fa7c11a573ac4345cf6a544aab0ba207892b2426d4ccf7b53a2767aeddb380fa`; admitted true; timeout 30; host_elapsed `0.13890629494562745`; worker_elapsed `0.000766703044064343`.
- `resource-stage-file-blob-r5/case/resource-layer/identity.json`: sha256 `1bc480632dbb6bc62c663e0f6f198af740a71b5601fc2f5f77674c51600ff25b`.

Retained and fresh receipt sweeps:

- Default retained sweep command:
  `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data`.
- Default retained sweep counts matched ticket 01 exactly: `launch_plan_receipt_readers 2279 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 14 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`.
- Extended fresh sweep command:
  `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/receipt-manifest.json`.
- Extended fresh sweep counts: `launch_plan_receipt_readers 2343 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 15 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`, `fresh_live_receipt_validation 8 0 0`.
- Tampered GPU copy:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/gpu-tamper-full.YTBmto/receipt.json`; sha256 `56ab72426727577d830bdc0da2bf4813ee6d2ca1bf45f7940180cd8befd63ee2`.
- Tamper sweep command:
  `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa02-digests-and-driver-pins-20261009T231634Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/gpu-tamper-full.YTBmto/receipt.json`.
- Tamper result: exit code 1, `fresh_live_receipt_validation 0 1 0`, one clear error `ValueError: gpu-driver:libcuda.so: GPU driver digest differs`. Other retained counts in that run remained green: `launch_plan_receipt_readers 2281 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 14 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`.

Gates:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 188/188 passed; elapsed 75.469s. Count unchanged from base 188.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed; elapsed 396.160s.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed; elapsed 124.813s.
