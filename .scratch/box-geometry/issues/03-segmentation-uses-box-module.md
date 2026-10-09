# 03: Segmentation uses the box module

**What to build:** The NLZ overlap check and foreground support decide box membership through the geometry box module, so segmentation and detection count box points the same way. The real-NLZ validator keeps its independent homogeneous-transform copy on purpose. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** done

- [x] Parity cases for NLZ overlap and foreground support membership pass against the old copies before the switch, and stay in the suite afterwards
- [x] NLZ overlap and foreground support call the module; their own validation messages and contracts (all sensor returns, ±1 flags, native classes) are unchanged
- [x] The real-NLZ validator is unchanged apart from a one-line note that its copy is a deliberate independent implementation
- [x] The NLZ overlap and foreground support tests pass unchanged
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Done: `autonomy/segmentation/oriented_box_parity_test.py` keeps old-copy parity fixtures for foreground support and NLZ overlap. Pre-switch parity passed with `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:oriented_box_parity_test` (1/1). After switching producers to `geometry.oriented_box`, focused tests passed with `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:oriented_box_parity_test //autonomy/segmentation:foreground_support_test //autonomy/segmentation:nlz_overlap_test` (3/3). Full gates passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` (164/164), `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` (17/17), and `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` (28/28) after `nvidia-smi` showed GPU 1 idle.
