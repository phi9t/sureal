# 03: The balanced16 sustained scorer and metric audit read reports strictly

**What to build:** The sustained scorer and its metric audit, which both run on the balanced16 live path, read the detection metric report through the strict reader. The sustained scorer keeps requiring all four classes. This changes balanced16's source snapshot, so blob-store ticket 12 re-admits it once, covering this ticket together with the blob store migration.

**Blocked by:** 01

**Status:** done

- [x] The sustained scorer reads through the strict reader, records diagnostic counts, and still requires all four classes finite and in [0, 1]
- [x] The sustained metric audit re-reads strictly and compares with the same-generation `check.json`
- [x] The existing sustained scorer test still passes, extended for diagnostic counts and a rejected malformed report
- [x] The ticket notes that blob-store ticket 12's re-admission covers this source-snapshot change; no balanced16 run happens here
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done: the sustained scorer now reads its detection metric report through `detection.native_detection_adapter.parse_result`, writes strict-reader diagnostic counts to `check.json`, and keeps the four-class LEVEL_2 requirement unchanged. The sustained metric audit re-runs `compute_detection_metrics`, re-reads the metric report through the same strict reader, compares both strict `metrics` and `diagnostics` with the same-generation scorer `check.json`, and writes its replayed `metrics.stderr`.

Blob-store ticket 12's single balanced16 source-snapshot re-admission covers this source change. No balanced16 run happened in this ticket.

Verification:
- Red check: `./bazelw test --test_tag_filters= --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evaluation:metrics_sustained_v3_test` failed before implementation because diagnostics were absent, malformed reports were accepted, and the audit still used the lenient regex.
- Focused green: `./bazelw test --test_tag_filters= --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evaluation:metrics_sustained_v3_test //autonomy/detection:native_detection_adapter_test` passed, 2/2 tests.
- Default CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 167/167 tests.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- GPU availability: `nvidia-smi` showed GPU 1 at 4 MiB used and 0 percent utilization, with no listed compute process on GPU 1.
- CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.
- Source-pin check: `cd autonomy && python3 -m evidence.pins check --base 7cd1ace50e819d6cffec5dc7815cb17bea0c9fd1` reported `evaluation/metrics_sustained_v3.py` and `evaluation/audit_metrics_sustained_v3.py` as pinned by retained receipts. This is the expected balanced16 source-snapshot change covered by blob-store ticket 12's re-admission.
