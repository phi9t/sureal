# 04: Segmentation metric reports read strictly

**What to build:** Every active reader of a segmentation metric report, starting with the segmentation contract fixtures, uses the strict segmentation reader. A `nan` or `inf` class line now rejects the report instead of being skipped.

**Blocked by:** 01

**Status:** done

- [x] The segmentation contract fixtures read through the strict reader; their regex patterns are gone
- [x] Any other active segmentation report reader found by search is migrated or listed with a reason
- [x] A test proves that a fixture report holding `nan` is rejected
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

Done: segmentation contract fixtures now read native metric reports through `segmentation.strict_metric_reader.parse_result`, so unknown, duplicate, missing, non-finite or out-of-range class lines reject the fixture output instead of being skipped by the former regex. The strict reader also exposes `require_perfect_self_score`, and the active self-score report checks in `segmentation/validate-real-semantic-wire.py` and `segmentation/verify-segmentation-export.py` now use it instead of searching for `miou=1`. Search found no other active segmentation metric report readers to migrate; remaining `compute_segmentation_metrics` references are binary/runtime checks or already use `strict_metric_reader`, and export/prototext regexes read wire data rather than metric reports.

Verification:
- Red: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:segmentation_contract_fixtures_test` failed before the fixture producer used the strict reader with `AssertionError: ValueError not raised` for an added `TYPE_POLE:nan` metric line; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:strict_metric_reader_test` failed before the self-score helper existed with `ImportError: cannot import name 'require_perfect_self_score'`.
- Focused green: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:strict_metric_reader_test //autonomy/segmentation:segmentation_contract_fixtures_test` passed, 2/2 tests.
- Segmentation package: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation/...` passed, 16/16 tests.
- CPU gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 168/168 tests.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests.
- CUDA gate: GPU 1 was free (`nvidia-smi`: GPU 1 at 4 MiB used, 0% util, no process on GPU 1); `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests.
