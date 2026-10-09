# 02: Detection scoring and audits read reports strictly

**What to build:** These now read their detection metric report through the strict reader and record the diagnostic counts:
- the plain detection scorer;
- its metric audit;
- the real-export check.

`check.json` gains correctly keyed range breakdowns. The plain scorer states its mean scope and raises on an empty populated set. It also gains tests, which it has never had.

**Blocked by:** 01

**Status:** done

- [x] The plain scorer reads through the strict reader with the committed breakdown set, records the accepted diagnostic counts, records `mean_scope`, and raises when no class is populated
- [x] The metric audit re-reads the report strictly and compares it with a same-generation `check.json`; the lenient pattern is gone
- [x] The real-export check reads the whole report strictly instead of searching for one line
- [x] New tests cover the plain scorer's wiring, mean rule and empty-scope error through its interface
- [x] No lenient detection-report pattern remains in active code outside the sustained path (ticket 03) and frozen code
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:
- Plain scorer, metric audit and real-export check now read the native detection metric report through `detection.native_detection_adapter.parse_result`.
- `check.json` output now records strict-reader diagnostics; the plain scorer records `mean_scope: populated classes`, preserves LEVEL_2 populated-class values, records full range breakdown keys, and raises `ValueError` for an empty populated class set.
- New command-interface tests in `autonomy/evaluation/metrics_test.py` covered strict-reader wiring, the populated-class mean rule, empty-scope rejection, audit same-generation comparison, and whole-report rejection in the real-export check.
- Lenient-pattern scan: `rg -n "mAP|mAPH|compute_detection_metrics|parse_result\\(" autonomy -g '*.py'` shows the old `re.findall(r'(\\S+): ...')` parser remains only in the sustained scorer/audit owned by ticket 03 and in frozen `studies/architecture/harness/` code.
- Focused gates: `//autonomy/evaluation:metrics_test` passed; `//autonomy/evaluation:all_tests` passed with 2 executed tests.
- Required gates: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed with 165/165 tests; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed with 17/17 tests; GPU 1 was free by `nvidia-smi`/`nvidia-smi pmon`, and `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed with 28/28 tests.
