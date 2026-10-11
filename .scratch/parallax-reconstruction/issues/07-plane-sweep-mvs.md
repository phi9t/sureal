# 07: Plane-sweep multi-view stereo depth maps

**What to build:** Per-view depth maps are computed by our plane-sweep MVS from ground-truth poses on the orbit scene, and scored against ground-truth depth.

**Blocked by:** 03, 04

**Status:** done

- [x] **Code.**
  - `stereo/plane_sweep.py`: fronto-parallel sweep over depth hypotheses with neighbour-view selection.
  - `stereo/cost.py`: ZNCC, plus census or an equivalent.
  - `stereo/depth_filter.py`: cross-view geometric consistency.
- [x] **Tests.** A synthetic fronto-parallel plane recovers its depth exactly up to sampling. Depth on the orbit scene beats a stated AbsRel threshold on textured pixels.
- [x] **Live check.** Run inside the Insula on the smoke and full profiles. Record:
  - AbsRel;
  - δ<1.25;
  - the fraction of valid pixels;
  - runtime.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

2026-10-10:

- Live check smoke command: `./bazelw run --noexperimental_collect_system_network_usage //parallax:mvs_live_check -- --profile smoke`
  - Result: pass.
  - Views: 3; depth hypotheses: 96; evaluated pixels: 9183; valid pixels: 7294.
  - AbsRel: 0.013691063413673023.
  - δ<1.25: 0.9968171552291163.
  - Valid-pixel fraction: 0.7942854766531614.
  - Runtime: 1.298744766972959 seconds.
  - Digests: scene manifest `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`; depth maps `9c8fb38697e871e8fef79e9038f3ffe103616ed76bc051157520eddb5e0883b5`; generated artifact tree `8c41c9abe3d2c0bc7e55796bc438dee2cef93f386904cd5998604479a78df180` across 19 generated artifacts.
- Live check full command: `./bazelw run --noexperimental_collect_system_network_usage //parallax:mvs_live_check -- --profile full`
  - Result: pass.
  - Views: 7; depth hypotheses: 160; evaluated pixels: 84568; valid pixels: 76929.
  - AbsRel: 0.015438970355745166.
  - δ<1.25: 0.999391253697782.
  - Valid-pixel fraction: 0.9097128024003179.
  - Runtime: 11.751627481076866 seconds.
  - Digests: scene manifest `e1b6a44204887e914cf107d16a170d37468fcd1f451c6e66483c7c670083ea19`; depth maps `b8c38f415bf26d2b2dc7f6f2d0ae2dccde377adc57e1e5c671a7e5142e76641f`; generated artifact tree `1101f90c71508f49c4cda428e4332c1ea869d8f05b8e5c8c1ed3ae37cde947ef` across 39 generated artifacts.
- Pipeline smoke check: `./bazelw run --noexperimental_collect_system_network_usage //parallax:parallax_cli -- run --module 06 --profile smoke --run-id mvs-smoke-20261010` passed.
- Focused tests: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_stereo_cost //parallax:test_depth_filter //parallax:test_plane_sweep //parallax:test_foundation //parallax:test_e2e_completion` passed, 5/5.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test` passed, 1/1.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 23/23.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed, 19/19.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 189/189.
- CUDA gate skipped as requested for this no-GPU sandbox.
