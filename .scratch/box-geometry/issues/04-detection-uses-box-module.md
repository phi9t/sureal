# 04: Detection uses the box module, including the association baseline files

**What to build:** Detection producers take heading wrap, point counts and BEV rectangles/IoU from the geometry box module, while box coding, both direction-correction rules and suppression stay detection operations with unchanged behaviour. This includes `box_coding.py`, `detector_geometry.py` and `scored_proposals_v3.py`, which the association study lists in its baseline source map; under ADR 0001 their next run records new source pins. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** done

- [x] Parity cases pass against the old copies before each switch and stay in the suite: decoded-heading wrap, v3 canonical wrap, sustained ground-truth wrap, overfit target wrap, prediction-record point counts, and the nearest and enclosing BEV rectangles and IoU
- [x] Box coding, `direction_correct`, `canonical_direction_correct`, `nearest_bev_iou` and `enclosing_bev_nms` keep their names, signatures and results, built on the module
- [x] A test feeds raw yaws inside and outside [-π, π), including 0 and ±π, to both direction-correction rules and records where they agree and where they differ
- [x] Prediction records count points with the module; NLZ overlap still comes from segmentation
- [x] The balanced16 coverage reconciliation script keeps its literal rectangle copy, with a one-line note that the copy is deliberate; any other detection file found with box math is classified as producer (migrated) or independent checker (kept) and the verdicts are listed in this ticket
- [x] Existing detection tests (box coding, detector geometry, scored proposals and direction, detector decode, sustained ground truth, prediction records) pass unchanged; the association contract tests pass
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Done: detection producers now use `geometry.oriented_box` for shared oriented-box math while keeping detection operations and public names in place. `box_coding.py` uses `wrap_heading` for decoded headings and `direction_correct`'s final wrap; `scored_proposals_v3.py` uses `wrap_heading` while preserving the canonical-before-sign rule; `detector_geometry.py` keeps `nearest_bev_iou` and `enclosing_bev_nms` as detection APIs built from geometry rectangles and axis-aligned BEV IoU; `prediction_records.py` counts measured points with `count_points_in_box` while NLZ overlap remains in `segmentation`; `sustained_groundtruth.py` and `overfit_detection_targets_v2.py` use shared heading wrap.

Parity evidence: `//autonomy/geometry:oriented_box_test_support_test` first failed for missing wrap/rectangle parity helpers, then passed after adding them. `//autonomy/detection:box_geometry_parity_test` passed against the old detection copies before the producers were switched, and remains in the suite for decoded-heading wrap, v3 canonical wrap, sustained ground-truth wrap, overfit target wrap, prediction-record point counts, nearest/enclosing BEV rectangles, and IoU.

Direction-rule evidence: `//autonomy/detection:scored_direction_test` documents that `direction_correct` and `canonical_direction_correct` agree for representative raw yaws inside `[-pi, pi)` including `-pi` and `0`, and differ for raw `pi`, `pi + 0.25`, and `-pi - 0.25`.

Detection box-math verdicts: producers migrated are `detection/box_coding.py`, `detection/scored_proposals_v3.py`, `detection/detector_geometry.py`, `detection/prediction_records.py`, `detection/sustained_groundtruth.py`, and `detection/overfit_detection_targets_v2.py`. Producer callers `detection/detector_decode.py` and `detection/scored_proposals_v2.py` already go through detection wrappers. Independent checker kept: `detection/diagnostics/balanced16-coverage-causes.py`, with its deliberate-copy note. Other grep hits were non-box geometry (`detector_loss.py` and `sustained_literal_loss.py` sine heading losses, `native_detection_adapter.py` evaluator log parsing) or tests.

Verification:
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/geometry:oriented_box_test_support_test //autonomy/detection:box_geometry_parity_test //autonomy/detection:box_coding_test //autonomy/detection:detector_geometry_test //autonomy/detection:scored_direction_test //autonomy/detection:detector_decode_test //autonomy/detection:sustained_groundtruth_test //autonomy/detection:prediction_records_test //autonomy/detection:scored_proposals_test` passed 9/9.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/detection:all_tests` passed 25/25.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/association:test_contract //autonomy/association:test_provenance` passed 2/2.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 165/165, up from the ticket baseline 164.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17.
- GPU 1 was free (`nvidia-smi`: GPU 1 had 4 MiB used and no compute process); `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 28/28.

Source-pin check: from `autonomy/`, `python3 -m evidence.pins check --base a4d4751b789385fee3c3fd1c2e6f91e92ab523b2` reported expected changed retained pins for `detection/box_coding.py`, `detection/detector_geometry.py`, `detection/overfit_detection_targets_v2.py`, `detection/prediction_records.py`, `detection/scored_proposals_v3.py`, and `detection/sustained_groundtruth.py`. Per ADR 0001 and this ticket, the next association/balanced run records new source snapshots; no retained evidence was edited.
