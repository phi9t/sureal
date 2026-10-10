# 04: Shrink resources.command to the legacy reader and close the seam

**What to build:**

- `resources.command` keeps only what is needed to read and re-check legacy, command-line-only receipts.
- The boundary test catches private launch-plan imports in any formatting.
- The resource-helper allowlist and the "not public" test are deleted.
- The copied Python-worker check and GPU device list exist once.

**Blocked by:** 03

**Status:** done

- [x] **The private-import scan catches parenthesised and multi-line imports.** A self-test proves it catches both forms, and the scan finds no active violations.
- [x] **`RESOURCE_COMMAND_LEGACY_HELPERS` and the test that pins those helpers as not public are deleted.** Any helper that remains is a legacy-receipt reader, and that is documented in the module.
- [x] **One copy of each:** the Python-worker check exists once, and so does the GPU device list.
- [x] **No other check is weakened.** The boundary test's other patterns and exclusions are unchanged, except where they become stricter.
- [x] The `insula` and `autonomy/ARCHITECTURE.md` docs describe the receipt-checking rule: compare plans for new receipts, use the legacy parser only for receipts with no plan record.
- [x] **Live acceptance** is repeated on the final code with the same runs as ticket 03, and the fresh receipts verify. Record the results in Comments.
- [x] The golden argv test is unchanged and passes, and the retained-receipt sweep matches the baseline exactly.
- [x] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

2026-10-10 Done:

- Implemented in `ecf058a` (`Close launch plan resource seam`) and `7a3e595` (`Fix resource worker imports in closure`). `resources.command` is now the documented legacy command-only receipt reader. Resource wrapping, Python-worker command checks, resource wrapper input validation, and the default GPU control device list live in `insula.launch_plan`; `resources.stage` and the sustained controller call those public launch-plan APIs. The second commit fixes the live-found resource-layer import failure with a focused red/green regression test.
- Boundary cleanup: deleted `RESOURCE_COMMAND_LEGACY_HELPERS` and `test_resource_wrapper_helpers_are_not_public_launch_plan_api`; no active `autonomy` or `docs` references remain. The private-import scan now uses the AST and has self-tests for parenthesised imports and backslash multi-line imports. The original sandbox argv and runtime-lock patterns/exclusions remain in force, with the helper allowlist removed.
- Docs: `autonomy/insula/README.md` and `autonomy/ARCHITECTURE.md` state the receipt-checking rule: receipts with `launch_plan` compare the plan record, while receipts without a plan record use the legacy command parser.
- Live root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z`. Worker temp root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa04-close-the-seam-20261010T012012Z/tmp`.
- GPU 1 preflight before the live GPU gate and CUDA gate: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `memory.used` 4 MiB, and no compute process on that UUID. Existing compute processes on other GPU UUIDs were left alone.
- Live commands:
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-cli.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py "$LIVE_ROOT/motion-cli"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-cli-expanded.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py "$LIVE_ROOT/motion-cli-expanded"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-native.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py "$LIVE_ROOT/motion-native"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-foundation.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id foundation-20261010T014108Z --output-root "$LIVE_ROOT"`.
  - `systemd-run --user --scope --same-dir --collect --unit=sureal-sustained-pa04final-20261010T014108Z -p MemoryAccounting=yes -p MemoryMax=17179869184 -p MemorySwapMax=0 env TMPDIR="$RESOURCE_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 "$WORKER_TMP/pa04_resource_stage_live.py" --repo "$PWD" --live-root "$LIVE_ROOT" --label resource-stage-close-seam-final`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/gpu-live.XXXXXX") CUDA_VISIBLE_DEVICES=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/insula/verify_gpu_live.py "$LIVE_ROOT/gpu-live"`.
  - `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY' ...` wrote `$LIVE_ROOT/receipt-manifest.json`.
- Live receipt manifest: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/receipt-manifest.json`, sha256 `dd7d00d8f3d1faa01fef2c8a542188a8cda9a28426cc8b5d2fce0c5e542b14a9`.
- Live receipts:
  - Motion CLI: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/motion-cli/receipt.json`, sha256 `a82a9bb870a63366b0302a37b9b0a281606fd94ee48e1a5534ed09f76e6c0320`, duration `1.3325308329658583` seconds.
  - Motion CLI expanded: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/motion-cli-expanded/receipt.json`, sha256 `c5b63238f708d04c2b35a3b19d771383299d9aeedb64fc6d0494d3c6444157fa`, duration `1.3371723300078884` seconds.
  - Motion native: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/motion-native/receipt.json`, sha256 `2902b75ca3ab1d82a88339fa587a9aba6676c169e1e1e8a8fc0e2db9c1eca5b6`, duration `1.5181901060277596` seconds.
  - Motion foundation replay: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/foundation-20261010T014108Z/receipt.json`, sha256 `859957a2346c44d5fe916aaf6f87f46c758cee2f4fb4020841c7e87a91ca81ab`, duration `10.951267076074146` seconds.
  - GPU live gate: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/gpu-live/receipt.json`, sha256 `5630c6b3dc074a5395530cac15c8a5dd92aeb068b1a572d3523d7d3a1ac71925`, duration `3.021083129919134` seconds.
  - Resource stage native receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/resource-stage-close-seam-final/case/tiny-live-0-verified.json`, sha256 `2b66f9c0e0724d74f9db816d7fa1302c0107e32e17e549f25f5f1df9acf347f8`, duration `0.1247303809504956` seconds.
  - Resource stage proof: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/resource-stage-close-seam-final/case/resource-layer/stages/tiny-live-0/resource-admitted.json`, sha256 `7a90aa66a5aa0e8ff948c142c1eee62744c86336e8c3cc799ab616ba525e8194`, host elapsed `0.1247303809504956` seconds, worker elapsed `0.0006717760115861893` seconds.
  - Resource identity: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/resource-stage-close-seam-final/case/resource-layer/identity.json`, sha256 `9cc300c0c5011873ff33efb5de79fbeb07e7f581ec10b49362fe8654c43ebddf`.
- Retained and fresh sweeps:
  - Default retained sweep command: `TMPDIR="$SWEEP_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data`.
  - Default retained sweep counts matched ticket 01 exactly: `launch_plan_receipt_readers 2279 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 14 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`.
  - PA04 extended fresh sweep command: `TMPDIR="$SWEEP_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/receipt-manifest.json`.
  - PA04 extended fresh sweep counts: `launch_plan_receipt_readers 2340 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 15 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`, `fresh_live_receipt_validation 8 0 0`.
  - PA01-PA03 live receipt sweep command: `TMPDIR="$SWEEP_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/receipt-manifest.json --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa02-20261009T232458Z/receipt-manifest.json --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/receipt-manifest.json`.
  - PA01-PA03 live receipt sweep counts: `launch_plan_receipt_readers 2471 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 17 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`, `fresh_live_receipt_validation 23 0 0`.
  - Tampered proof: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/tampered-resource-proof-copies/resource-admitted-tampered-digest.json`, sha256 `91a3f913fed7df6bab14dfe1a83cd24509b6d45fe575fbbd7ebdbefaadd61ff0`. Command `TMPDIR="$SWEEP_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --extra-receipt /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa04-20261010T014108Z/tampered-resource-proof-copies/resource-admitted-tampered-digest.json` exited 1 with `ValueError: launch plan mount digest differs: resource-layer`.
- Backfill checks:
  - `TMPDIR="$TEST_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.resources.stage_test.ResourceStageTests.test_execute_worker_loads_resource_layer_packages_without_pythonpath`: failed before the fix with `ModuleNotFoundError: No module named 'evidence'`, then passed.
  - `TMPDIR="$TEST_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_boundary_test`: 7 tests passed.
  - `TMPDIR="$TEST_TMP" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.training_execution.launch_plan_golden_test autonomy.insula.launch_plan_boundary_test autonomy.insula.launch_plan_test autonomy.resources.command_test autonomy.resources.stage_test autonomy.retained_receipt_sweep_test autonomy.training_execution.sustained_controller_backend_test autonomy.training_execution.run_sustained_test`: 90 tests passed.
  - `git diff --exit-code -- autonomy/training_execution/launch_plan_golden_test.py`: passed, so the golden argv test file is unchanged.
  - `rg -n "RESOURCE_COMMAND_LEGACY_HELPERS|test_resource_wrapper_helpers_are_not_public_launch_plan_api" autonomy docs`: no matches.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 189/189 passed, elapsed `77.869s`. Count is unchanged from base `6271417`/ticket 03 (`189`).
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed, elapsed `397.779s`.
  - `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed, elapsed `120.612s`.
