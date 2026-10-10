# 03: New receipts are checked by comparing plans, and the resource wrapper is plan data

**What to build:**

- **The resource wrapper is plan data:** wrapper mounts with explicit mount roles, plus a command prefix. The resource runner and the resource verifier both build the same expected wrapped plan.
- **The launch-plan module checks new receipts:** every receipt with a `launch_plan` record is checked by comparing that record with the expected plan, by role, target, mode, digest, devices, environment, working directory and command.
- **The rendered command line in a new receipt is checked by rendering the record,** never by parsing the command line.

**Blocked by:** 02

**Status:** done

- [x] The launch-plan module has one public plan-versus-record comparison, and its rejections name the mismatched field.
- [x] **The resource wrapper produces a plan.** `resources.stage` runs and checks resource stages through it, and no active code splices mounts into rendered argv for new launches.
- [x] **No new receipt goes through the legacy parser.** These all use plan comparison when the receipt has a plan record:
  - every active `read_receipt_mounts({'command': …})`-style call in `resources.stage`, `resources.checkpoint` and `training_execution.sustained_controller_backend`;
  - `check_stage`.

  Receipts without one still go through the legacy parser.
- [x] **The ordering rule exists only in the renderer.** The `/tmp`, `/tmp/*` and device mount order is defined only in `render_plan`, and the private index helpers used for splicing are deleted or used only by the legacy path.
- [x] **Tampering tests:** for a new receipt, a record with a changed mount digest, a changed role, or a reordered argv each fails verification.
- [x] **Live acceptance**, run for real on this ticket's code (GPU 1 only, and only when it is free). Record the commands, receipts and durations in Comments, and report failures as found:
  - the three motion verifiers and `replay_motion_foundation.py`;
  - one resource-measured stage through `resources.stage`;
  - the GPU live gate (`insula/verify_gpu_live.py` or its current equivalent) on GPU 1.

  Their fresh receipts must verify through the new plan comparison, and a tampered copy of one must fail.
- [x] The golden argv test is unchanged and passes, and the retained-receipt sweep matches the baseline exactly.
- [x] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.

## Comments

2026-10-10 Done:

- Implemented `insula.launch_plan.assert_plan_matches_record(...)` as the public structured plan-versus-record comparison, with field-specific errors for runtime, mount role/digest/mode/target, devices, environment, working directory and command. Added `assert_record_matches_rendered_command(...)` for new receipts that still store a rendered command; it renders from the recorded plan data and treats the environment mapping as data, not JSON key order.
- Resource wrapper is now plan data through `resources.command.wrap_resource_plan_record(...)` and `wrap_resource_plan(...)`, with stable roles `resource-layer`, `resource-experiment-resources`, `resource-experiment-evidence` and `resource-output`. `resources.stage.validate_proof(...)` and `training_execution.sustained_controller_backend.check_stage(...)` branch on `launch_plan` before legacy command parsing. The remaining private index-helper uses in `resources.command` are for legacy rendered-command wrapping only; `render_plan` owns the new launch ordering rule.
- `resources.checkpoint` still has `read_receipt_mounts({'command': ...})` calls only in retained legacy publication/archive/audit validators. No `launch_plan`-bearing receipt path reaches those calls in this ticket's active checks; new resource-stage and sustained-stage receipts use plan comparison.
- Live root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z`. Worker temp root: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa03-plan-comparison-20261010T002436Z/tmp`.
- GPU 1 preflight before live GPU gate and CUDA gate: GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `memory.used` 4 MiB, and no compute process on that UUID. Other users' GPU processes on other UUIDs were left alone.
- Live commands:
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-cli.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py "$LIVE_ROOT/motion-cli"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-cli-expanded.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py "$LIVE_ROOT/motion-cli-expanded"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-native.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py "$LIVE_ROOT/motion-native"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/motion-foundation.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id foundation-20261010T003448Z --output-root "$LIVE_ROOT"`.
  - `TMPDIR=$(mktemp -d "$WORKER_TMP/gpu-live.XXXXXX") CUDA_VISIBLE_DEVICES=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/insula/verify_gpu_live.py "$LIVE_ROOT/gpu-live"`.
  - `PA03_REPO="$PWD" PA03_LIVE_ROOT="$LIVE_ROOT" PA03_RESOURCE_LABEL=resource-stage-plan-data-r4 TMPDIR=$(mktemp -d "$WORKER_TMP/resource-stage.XXXXXX") PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 "$WORKER_TMP/pa03_resource_stage_live.py"`.
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 "$WORKER_TMP/pa03_manifest_and_tamper.py"`.
- Live receipt manifest: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/receipt-manifest.json`, sha256 `e7fef87a26ff83e8499ca32e275fa2ac488f2f492dc02cfe9d45315851df4fd1`.
- Live receipts:
  - Motion CLI: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/motion-cli/receipt.json`, sha256 `477fda8f44049cfcb9d1a08027dd86ba3e4cf67768b73b3e76e0d40fbfa50d69`, duration `1.3361080680042505` seconds.
  - Motion CLI expanded: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/motion-cli-expanded/receipt.json`, sha256 `05a258ef4628889fb68adbbb4c217eaa28e9a18b7156da96b492e4e9b0d705f8`, duration `1.3413383980514482` seconds.
  - Motion native: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/motion-native/receipt.json`, sha256 `31e6ad1e829e111a40696ae3715ea1868e5104e6df76ccc5558bd7860bbc8a98`, duration `1.543574535055086` seconds.
  - Motion foundation replay: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/foundation-20261010T003448Z/receipt.json`, sha256 `820621fa35deaec737ef05bb977e80c1dd5740d10ae85e2deb9b8e9dc87636e2`, duration `10.494631926063448` seconds.
  - GPU live gate: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/gpu-live/receipt.json`, sha256 `eb55d352eed35f5e43cd219c5238a65a75332f314020390d9d0282cce10e66ac`, duration `2.9858225269708782` seconds.
  - Resource stage native receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/resource-stage-plan-data-r4/case/tiny-live-0-verified.json`, sha256 `857d4519044a3afad9fcaa3ceca6651af11854e95b8c385dc6fc5afe93086122`, duration `0.2181053680833429` seconds.
  - Resource stage proof: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/resource-stage-plan-data-r4/case/resource-layer/stages/tiny-live-0/resource-admitted.json`, sha256 `5861d4107df7219b042f126820c34bfcccd27f32031a768da95dc29e94928953`, host elapsed `0.12806890695355833` seconds, worker elapsed `0.00065741001162678` seconds.
  - Resource identity: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/resource-stage-plan-data-r4/case/resource-layer/identity.json`, sha256 `89213df77d76aa3c0ebdc41ad139fd1333f1b3c080e6f7b8f80b8870577fcf41`.
- Retained and fresh sweeps:
  - Default retained sweep command: `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa03-plan-comparison-20261010T002436Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data`.
  - Default retained sweep counts matched ticket 01 exactly: `launch_plan_receipt_readers 2279 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 14 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`.
  - Extended fresh sweep command: `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa03-plan-comparison-20261010T002436Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data --extra-receipt-manifest /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/receipt-manifest.json`.
  - Extended fresh sweep counts: `launch_plan_receipt_readers 2343 0 0`, `balanced16_stage_check 14 0 0`, `resource_stage_proof_validation 15 0 0`, `resource_checkpoint_validation 2 0 0`, `legacy_resource_publication_validation 9 0 0`, `fresh_live_receipt_validation 8 0 0`.
- Tampered resource proof copies:
  - Digest copy: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/tampered-resource-proof-copies/resource-admitted-tampered-digest.json`, sha256 `a939219c884f2db8e69aba85e24c434510bb198f179d93c0aa5bb86df39faefd`; sweep exited 1 and named `ValueError: launch plan mount digest differs: resource-layer`.
  - Role copy: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/tampered-resource-proof-copies/resource-admitted-tampered-role.json`, sha256 `10d4175d3c9cdfa12f26e5ff236632519809b517957375b2f41267e8349bca98`; sweep exited 1 and named `ValueError: launch plan mount role differs: missing resource-layer; unexpected resource-layer-renamed`.
  - Argv copy: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa03-20261010T003448Z/tampered-resource-proof-copies/resource-admitted-tampered-argv.json`, sha256 `0d559fbffe700d029aedfcfaac0f1304c8c7ee12c66240453f4b2e15f432a23a`; sweep exited 1 and named `ValueError: launch plan command differs`.
- Regression checks:
  - `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/pa03-plan-comparison-20261010T002436Z/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=autonomy python3 -m unittest autonomy.insula.launch_plan_test autonomy.resources.command_test autonomy.resources.stage_test autonomy.retained_receipt_sweep_test autonomy.training_execution.run_sustained_test autonomy.training_execution.sustained_controller_backend_test`: 81 tests passed.
  - `git diff --exit-code -- autonomy/training_execution/launch_plan_golden_test.py`: passed, so the golden argv test file is unchanged. The CPU Bazel gate also ran `//autonomy/training_execution:launch_plan_golden_test`.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 189/189 passed, elapsed `74.345s`. Count is +1 from ticket 02's 188 because `//autonomy/resources:command_test` is now included.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed, elapsed `399.504s`.
  - `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed, elapsed `123.952s`.
