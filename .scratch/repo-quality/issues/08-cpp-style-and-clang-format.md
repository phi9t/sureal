# 08: C++ style guide and pinned clang-format

**What to build:** Sureal's C++ follows a written guide and is checked by a Bazel-pinned clang-format run in `//:repo_gate`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Decisions, from the user on 2026-10-10:
- Headers use `.hh`.
- The column limit is 120.
- C++ pinned by retained evidence, such as `motion_metrics_main.cc` and `project_camera.cc`, stays byte-frozen and is excluded by path.

Source: `../research/milano-conventions.md`, C++ section.

- [ ] **Guide.** `docs/guides/cpp-style.md` covers:
  - naming;
  - include grouping;
  - ownership (RAII, no naked `new`);
  - casts;
  - no `using namespace` in headers or at file scope;
  - the error model (exceptions or status, matching the current code);
  - `.hh` headers;
  - 120 columns.
- [ ] **Format config.** A `.clang-format`, adapted from Milano's whitespace-only configuration, with `ColumnLimit: 120`.
- [ ] **Pinned tool.** clang-format is pinned as a Bazel-fetched release archive with its sha256 (ADR 0002), not taken from host packages.
- [ ] **Repo gate check.** `//:repo_gate` gains a clang-format check over active C++. Files pinned by source pins or retained evidence are excluded by an explicit list, which a test keeps in sync with the pin registry.
- [ ] **Reformat batch.** One batch reformats the unpinned active C++. Behaviour is proven unchanged by rebuilding the affected binaries and rerunning their tests or live checks. Minified files such as `native_source_inventory.cc` are expanded in this batch, unless they are pinned.
- [ ] **Gates:** `//:repo_gate`, `//autonomy/...`, `//parallax/...`, and CUDA on GPU 1 when it is free.
