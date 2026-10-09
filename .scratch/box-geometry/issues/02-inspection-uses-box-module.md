# 02: Inspection uses the box module

**What to build:** The viewer export counts points in a box, and the explorer draws BEV box outlines, through the geometry box module, with parity proven before the inline copies are removed. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** done

- [x] Parity cases for the viewer's point count and the explorer's corner computation pass against the old copies before the switch, and stay in the suite afterwards
- [x] The viewer export and the explorer call the module; their inline box math is gone
- [x] The viewer manifest tests and any explorer tests pass unchanged
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Done: inspection producers now use `geometry.oriented_box` for shared oriented-box math. `viewer/export/boxes.py` adapts the viewer signature into one oriented box and calls `count_points_in_box`; `explorer/joint_render.py` draws BEV outlines from `bev_corners`. The old viewer point-count and explorer corner formulas live only in `autonomy/inspection/oriented_box_parity_test.py`, and the shared parity harness now includes `assert_bev_corners_parity`.

Parity evidence: `//autonomy/geometry:oriented_box_test_support_test //autonomy/inspection:oriented_box_parity_test` first failed before implementation because the BEV-corner parity helper was missing; the inspection parity target also exposed that the old viewer copy did not reject invalid oriented-box inputs. The viewer wrapper was tightened to the module's finite-positive oriented-box contract, then the same targets passed against the old inline point-count and corner copies before the switch, and remain in the suite afterwards.

Focused evidence: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/inspection:oriented_box_parity_test //autonomy/inspection:viewer__export__manifest_test` passed 2/2 after the switch, and `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/inspection:all_tests` passed 7/7.

Gate evidence: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 168/168. `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17. `nvidia-smi` showed GPU 1 idle at 4 MiB used, 0% util and no compute app listed on GPU 1, so `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` ran and passed 28/28.
