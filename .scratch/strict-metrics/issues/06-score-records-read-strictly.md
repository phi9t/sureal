# 06: Per-class score records in check.json are read through one strict reader

**What to build:** These all read the per-class score record in `check.json` through one strict reader (class key set, finite values in [0, 1]):
- the sustained admission;
- the sustained contract;
- the evidence projection;
- the fixed-batch verifier.

The projection still shows a run with no score yet as running, but a malformed record now raises.

**Blocked by:** 02, 03

The sustained admission is on the balanced16 live path, so this ticket changes balanced16's source snapshot. Blob-store ticket 12's re-admission covers it.

**Status:** done

- [x] One score-record reader exists. The sustained admission's existing strict check becomes it, with no behaviour change on valid records.
- [x] The evidence projection distinguishes "no score yet" from "malformed score", and the latter raises
- [x] The sustained contract and the fixed-batch verifier use the reader instead of key-set-only checks
- [x] Tests cover each rejection rule through the reader's interface
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:
- Added `evidence.score_records.read_level2_per_class` as the single strict reader for `LEVEL2_per_class`: exactly classes `1` through `4`, exactly `AP` and `APH` per row, and numeric finite values in `[0, 1]`.
- Sustained admission now delegates its former inline strict check to the shared reader. Valid records preserve the same APH gate behavior.
- Sustained contract accepts full `LEVEL2_per_class` samples through the shared reader while retaining the existing reduced `APH` sample form used by the controller.
- Evidence projection keeps absent `LEVEL2_per_class` as not scored yet (`running_or_verifying`, empty terminal score, no worst APH), but any present malformed score record raises.
- Fixed-batch verification now reads score receipts, curve points, inherited baseline scores and terminal output through the shared reader instead of checking only the class key set.
- Retained `check.json` compatibility: old mis-keyed range entries under `metrics` are tolerated by these readers because this ticket reads only the four-class `LEVEL2_per_class` score record. Malformed `LEVEL2_per_class` is not tolerated in sustained admission, sustained contract, evidence projection, or fixed-batch verification.
- No balanced16 run happened here; blob-store ticket 12's single re-admission covers the balanced16 source-snapshot change.

Verification:
- Red checks: `//autonomy/evidence:score_records_test` first failed with missing `evidence.score_records`; `//autonomy/evidence:projection_test` first showed malformed present score records were not rejected; `//autonomy/detection:sustained_contract_test` first failed on full `LEVEL2_per_class` samples; `//autonomy/studies:fixed_batch__fixed_batch_verifier_test` first showed missing `AP` was accepted.
- Focused green: `./bazelw test --test_tag_filters= --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evidence:score_records_test //autonomy/evidence:projection_test //autonomy/detection:sustained_contract_test //autonomy/training_execution:sustained_admission_test //autonomy/evaluation:metrics_sustained_v3_test //autonomy/studies:fixed_batch__fixed_batch_verifier_test` passed, 6/6 tests.
- Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 170/170 tests.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- GPU availability: `nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits` showed GPU 1 at `4 MiB` and `0%`; `nvidia-smi pmon -c 1` showed no GPU 1 process.
- CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.
