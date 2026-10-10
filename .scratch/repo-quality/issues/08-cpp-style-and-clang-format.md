# 08: C++ style guide and pinned clang-format

**What to build:** Sureal's C++ follows a written guide and is checked by a Bazel-pinned clang-format run in `//:repo_gate`.

**Blocked by:** None (can start immediately)

**Status:** done

Decisions, from the user on 2026-10-10:
- Headers use `.hh`.
- The column limit is 120.
- C++ pinned by retained evidence, such as `motion_metrics_main.cc` and `project_camera.cc`, stays byte-frozen and is excluded by path.

Source: `../research/milano-conventions.md`, C++ section.

- [x] **Guide.** `docs/guides/cpp-style.md` covers:
  - naming;
  - include grouping;
  - ownership (RAII, no naked `new`);
  - casts;
  - no `using namespace` in headers or at file scope;
  - the error model (exceptions or status, matching the current code);
  - `.hh` headers;
  - 120 columns.
- [x] **Format config.** A `.clang-format`, adapted from Milano's whitespace-only configuration, with `ColumnLimit: 120`.
- [x] **Pinned tool.** clang-format is pinned as a Bazel-fetched release archive with its sha256 (ADR 0002), not taken from host packages.
- [x] **Repo gate check.** `//:repo_gate` gains a clang-format check over active C++. Files pinned by source pins or retained evidence are excluded by an explicit list, which a test keeps in sync with the pin registry.
- [x] **Reformat batch.** One batch reformats the unpinned active C++. Behaviour is proven unchanged by rebuilding the affected binaries and rerunning their tests or live checks. Minified files such as `native_source_inventory.cc` are expanded in this batch, unless they are pinned.
- [x] **Gates:** `//:repo_gate`, `//autonomy/...`, `//parallax/...`, and CUDA on GPU 1 when it is free.

## Comments

- 2026-10-10 Done:
  - Added `docs/guides/cpp-style.md` covering naming, include grouping, ownership and RAII, casts, namespace rules, error handling, `.hh` headers, and the 120-column limit.
  - Added `.clang-format` from the Milano/Google-style whitespace-only baseline with `ColumnLimit: 120`, `PointerAlignment: Left`, `SortIncludes: Never`, and no comment, string, or macro reflow.
  - Pinned clang-format through Bazel as `@clang_format_linux_x86_64`, using PyPI wheel `clang_format-18.1.8-py2.py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`, sha256 `2de122b8aa78ba49e326f974131caab2c79f4ae877c227cd4e3e5d82a98d21e5`. The pinned binary reports `clang-format version 18.1.8`.
  - Live first pass, through Insula: `TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/rq08-cpp-style-20261010T212843Z/tmp ./bazelw run --noexperimental_collect_system_network_usage //:clang_format_repo -- --root=/experiment` exited 1 with `tracked_cpp=17`, `registry_protected_cpp=15`, `explicit_pinned_cpp=15`, `frozen_cpp=0`, `clang_format_scope=2`, and 336 clang-format diagnostics. The only violating file was `parallax/insulas/orb-slam/surflo_rgbd.cc`.
  - The explicit pinned C++ exclusion list covers 15 source-pin-protected files: `autonomy/camera/project_camera.cc`, `autonomy/motion/cli/motion_metrics_main.cc`, the motion ingestion `.cc` files, and `autonomy/motion/pooled/motion_metrics_pooled_main.cc`. `//:repo_gate_clang_format_test` keeps this list in sync with the pin registry.
  - Reformatted the unpinned active C++ batch. `parallax/insulas/orb-slam/surflo_rgbd.cc` was the only file changed; `autonomy/insula/rootfs_compiler_smoke_test.cc` was already clean. The whitespace-stripped SHA256 for `surflo_rgbd.cc` was unchanged before and after formatting: `d2e408ecbca37a62e2ffed4e2e5be9c649f0896578ac64f7c404961c6208c895`.
  - Post-format live check, through Insula: the same `./bazelw run --noexperimental_collect_system_network_usage //:clang_format_repo -- --root=/experiment` command exited 0 with `tracked_cpp=17`, `registry_protected_cpp=15`, `explicit_pinned_cpp=15`, `frozen_cpp=0`, and `clang_format_scope=2`.
  - Focused checks passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:clang_format_repo_test //:repo_gate_clang_format_test //:repo_gate_membership_test //:pinned_sources_test` -> 4/4 tests pass.
  - A mixed Parallax/autonomy target invocation was rejected by `./bazelw` with `target pattern spans autonomy and parallax; run each component separately so the wrapper can select the correct rootfs`; the affected behavior checks were rerun separately.
  - Affected behavior checks passed: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax:test_orb_slam_reference` -> 1/1 test pass, invocation `5e89ca61-6eeb-4e60-8020-3ec6f96f29b5`; `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:rootfs_compiler_smoke_test` -> 1/1 test pass, invocation `f0c3ff01-cd9a-4a9f-86da-46fcbb34d200`.
  - Compile-only ORB-SLAM rebuild used the existing local `surflo-pathway-orb-slam:1` image without network or pull: `docker run --rm --network none --pull=never -v "$PWD/parallax/insulas/orb-slam/surflo_rgbd.cc:/tmp/surflo_rgbd.cc:ro" surflo-pathway-orb-slam:1 bash -lc 'set -euo pipefail; cp /tmp/surflo_rgbd.cc /opt/ORB_SLAM3/Examples/RGB-D/surflo_rgbd.cc; cmake --build /opt/ORB_SLAM3/build --target surflo_rgbd --parallel 2'` exited 0 with `[100%] Built target surflo_rgbd`.
  - Final repo gate passed after ticket closeout edit: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` -> 19/19 tests pass, invocation `a7640c4c-adc3-44a6-81ca-a102348727a9`.
  - Final CPU autonomy gate passed after ticket closeout edit: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` -> 189/189 tests pass, invocation `1ec51251-20b5-4ec4-a3d5-354cb51a2926`.
  - Final Parallax gate passed after ticket closeout edit: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` -> 17/17 tests pass, invocation `cde98b04-970d-41c6-bed7-b65c22822170`.
  - CUDA gate intentionally skipped for this worker run per coordinator instruction: this sandbox has no GPU devices, and the coordinator runs CUDA.
