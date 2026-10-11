# 08: TSDF fusion and marching cubes

**What to build:** Depth maps fused into a voxel TSDF by our code, and a mesh extracted by our marching cubes, scored against the ground-truth surface.

**Blocked by:** 07

**Status:** done

- [x] **Code.** `fusion/tsdf.py`, a volumetric integrator with truncation and weights, and `fusion/marching_cubes.py`.
- [x] **Tests.**
  - Fusing the ground-truth depth of the orbit scene gives a mesh within a stated Chamfer distance and F-score at τ.
  - A sphere SDF meshes to the analytic radius within the voxel tolerance.
- [x] **Live check.** Fuse the ground-truth depth and the depth from ticket 07, and record Chamfer distance, accuracy, completeness, F-score at τ and runtime.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

2026-10-10:

- Live check smoke command: `tmp=$(mktemp -d .bazel-cache/fusion-live-smoke.XXXXXX); ./bazelw run --noexperimental_collect_system_network_usage //parallax:fusion_live_check -- --profile smoke --output "$tmp/artifacts"`
  - Result: pass.
  - Views: 3; truth surface samples: 9216.
  - Settings: voxel size 0.12 m; truncation 0.24 m; tau 0.18 m.
  - Ground-truth depth fusion: Chamfer distance 0.0373517248902196; accuracy 0.03947855956216499; completeness 0.03522489021827421; F-score 0.983569490503467; runtime 0.8590031720232219 seconds.
  - Ground-truth depth counts: volume shape [58, 41, 15]; observed voxels 15340; mesh vertices 40458; mesh triangles 13486.
  - Ticket-07 MVS depth fusion: Chamfer distance 0.07337735735126874; accuracy 0.056600257698967746; completeness 0.09015445700356972; F-score 0.9145597574183665; fusion-and-meshing runtime 0.770408608019352 seconds; MVS depth runtime 1.2819394120015204 seconds.
  - Ticket-07 MVS depth counts: volume shape [47, 38, 26]; observed voxels 11112; mesh vertices 26628; mesh triangles 8876.
  - Digests: scene manifest `818a329131d85be0ffe2ba8b19b3c7a334e53982055991d6eb70980d8f7c2345`; truth surface points `ff5c9b079ef532c684819e13c4a5e5b18011840f72cafdd0d629059398937330`; ticket-07 depth maps `9c8fb38697e871e8fef79e9038f3ffe103616ed76bc051157520eddb5e0883b5`; truth-depth mesh `1df1358c9474e4ff32b8f765fba1c9d27b71b7b7a88580b8010b0d7a2ac64e95`; MVS-depth mesh `8f0e09dafa7e55f9e984e95512b13562de8ab379da45ef7975a46030a107c4cd`; generated artifact tree `f127f6cb01bdb7b4ce37bb449b0a7c2360a4f2bede21b03b3947cdef3446d2a3` across 21 generated artifacts.
- Live check full command: `tmp=$(mktemp -d .bazel-cache/fusion-live-full.XXXXXX); ./bazelw run --noexperimental_collect_system_network_usage //parallax:fusion_live_check -- --profile full --output "$tmp/artifacts"`
  - Result: pass.
  - Views: 7; truth surface samples: 21504.
  - Settings: voxel size 0.08 m; truncation 0.18 m; tau 0.12 m.
  - Ground-truth depth fusion: Chamfer distance 0.024183337120381093; accuracy 0.03036807863171062; completeness 0.017998595609051562; F-score 0.9897915044554026; runtime 3.512797031085938 seconds.
  - Ground-truth depth counts: volume shape [109, 72, 20]; observed voxels 72339; mesh vertices 140124; mesh triangles 46708.
  - Ticket-07 MVS depth fusion: Chamfer distance 0.05419979696014755; accuracy 0.064359742246201; completeness 0.04403985167409411; F-score 0.9056635952666701; fusion-and-meshing runtime 4.29840697417967 seconds; MVS depth runtime 11.80216581793502 seconds.
  - Ticket-07 MVS depth counts: volume shape [95, 66, 37]; observed voxels 65379; mesh vertices 139296; mesh triangles 46432.
  - Digests: scene manifest `e1b6a44204887e914cf107d16a170d37468fcd1f451c6e66483c7c670083ea19`; truth surface points `26d7456fb8de58ee33917b60b89a53f578cb9b7d731ede872993ac6b4466fa2a`; ticket-07 depth maps `b8c38f415bf26d2b2dc7f6f2d0ae2dccde377adc57e1e5c671a7e5142e76641f`; truth-depth mesh `78290a78f53345847e2be97ae6f59b5a6fd7ec37e4928be521cd8c601576b9ca`; MVS-depth mesh `f22fec7843ef5e1fe256c2a43481508863da65555df265dc8a23c21468cb1cdb`; generated artifact tree `24df116c9d860af736ee09938186122609999495d857495f738573530d54b772` across 41 generated artifacts.
- Focused test: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_fusion` passed, 1/1.
- Required gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test` passed, 1/1.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 26/26.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed, 23/23.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 189/189.
- CUDA gate skipped as requested for this no-GPU sandbox.
