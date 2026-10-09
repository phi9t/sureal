# 10: Live gates and M0 on launch plans

**What to build:** The live-gate support that semantic-layout ticket 29 adds to `insula`, and the M0 verifier and receipt, are built on launch plans, so live gates are one more caller rather than another launch shape.

**Blocked by:** 01, semantic-layout 29

**Status:** done

- [x] Ticket 29's live-gate support builds launch plans through the module, with no command-line assembly of its own
- [x] `insula/verify_m0.py` and `insula/m0_receipt.py` load locks through the module. M0's whole-lock comparison still happens
- [x] Ticket 29's four live gates still pass when re-run through the rebuilt support, recorded with counts
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Done. Rebuilt `autonomy/insula/live_gate.py` receipts on `record_plan(...)` so the recorded launch data comes from the launch-plan module rather than command-line mount reconstruction; semantic live-gate records now contain `launch_plan` and no `argv` or `mounts` legacy fields. `autonomy/insula/verify_m0.py` now builds checked launch plans through `build_m0_plan(...)` / `render_plan(...)`, and `autonomy/insula/m0_receipt.py` validates by `load_runtime_lock(...)` while retaining the whole `receipt["runtime_lock"] == runtime.data` comparison.

Red/green focused tests:

- `PYTHONPATH=autonomy python3 -m unittest insula.live_gate_test.LiveGateTests.test_plan_uses_structured_mounts_and_records_receipt insula.verify_m0_test.VerifyM0PlanTests.test_m0_execution_builds_a_checked_launch_plan insula.m0_receipt_test.ReceiptTests.test_runtime_lock_is_loaded_through_strict_module_checker`: failed first on legacy `argv`/`mounts`, missing `build_m0_plan`, and direct-lock validation accepting a stale `dockerfile_sha256`; passed after implementation, `3/3`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:live_gate_test //autonomy/insula:verify_m0_test`: passed, `2/2`.

Ticket 29 live gates were re-run with new outputs only under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/lp10/run-20261009T0318iSd94k`. No HDFS writes, evidence publish, container build, journal entry, retained evidence mutation, or shared-cache staging was performed. Summary `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/lp10/run-20261009T0318iSd94k/live-gate-summary.json` sha256 `db23c887b7c6ccb43aed7a2d36b13f5034b450632281bafe9f277682e9bb4421`.

- `//autonomy/insula:m0_receipt_test`: pass, `8/8`; fresh lp10 M0 receipt sha256 `10edac29375194f31793c553335574aa8be60bc9a3e8bdc1ed614b599aaaab62`; receipt-test log sha256 `4eb4b787da29edb175c1f079741136694482deebc0a47783acd0cb8483efe92d`.
- `//autonomy/segmentation:semantic_recovery_accounting_test`: pass, `2/2`; record sha256 `561cbd928818f4ebe66cc72a8fa019d95970511ccf9aab7bb5ec9fefac799c94`; raw log sha256 `526bdfff73f3d7db70d6bae844abf0c93c94e1d236165f370a562ea1e159e4ce`.
- `//autonomy/segmentation:semantic_recovery_receipt_test`: pass, `1/1`; record sha256 `54562f5295656ef68291b0bd6738f21e33c9f770a23e0b3a336553203e8cac1c`; raw log sha256 `f0d4a1130f1e4f73a9d743cdd18454842b192373f7d585ed732c78d1d61a55c2`.
- `//autonomy/segmentation:semantic_recovery_receipt_aligned_test`: pass, `1/1`; record sha256 `f88ff50d5daed03b70e2fa6f86fb9e320299ccc89385a34dfe25c2dd02700176`; raw log sha256 `08796186deff7ea23225b325424d1bba6174ca5d854e27049a74e3311c6986cb`.

The retained semantic recovery receipts are source-pinned to the ticket-29 worker code root, so their live gates mounted `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/final26-closeout-verify-worker-t29c-semantic-recovery/autonomy` as `/experiment`. A probe against this ticket's base showed the retained exact/aligned receipts would otherwise fail only on the later `semantic_recovery_job*.py` source-pin digests. The fresh M0 receipt was generated and checked against this ticket's current code.

Required gates:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, `174/174`.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, `17/17`.
- GPU 1 precheck before CUDA: free at `4 MiB / 183359 MiB`, `0%`, no compute process for `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`; after CUDA it was again `4 MiB / 183359 MiB`, `0%`, with no compute process for GPU 1.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, `29/29`.
