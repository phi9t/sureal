# 16: The formerly pinned C++ meets the guide, and the C++ baseline is gone

**What to build:** Every active C++ file follows `docs/guides/cpp-engineering.md`, and clang-format checks all
active C++ rather than a prefix batch. These are the 15 autonomy native tools and fixtures that were frozen until
ticket 07. Today they carry 89 recorded findings in `scripts/cxx_lint_baseline.json`: 85 over-long lines, 3
C-style casts and one `using namespace`. Several are minified whole programs on a handful of lines, such as
`autonomy/motion/ingestion/native_source_inventory.cc`.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] **Whitespace pass.** One commit runs the pinned clang-format over the 15 files. Prove it is
  whitespace-only by comparing each file's whitespace-stripped sha256 before and after, as ticket repo-quality/08
  did for `surflo_rgbd.cc`.
- [ ] **Code pass.** A second commit fixes what clang-format cannot:
  - expand dense one-line statements into one statement per line;
  - C-style casts become C++ casts;
  - `using namespace` moves into function scope or becomes qualified names;
  - include groups follow the guide.

  No behaviour change.
- [ ] **Gates widen.** `CLANG_FORMAT_BATCH_PREFIXES` is removed, so clang-format covers all active C++.
  `scripts/cxx_lint_baseline.json` is deleted along with its loading code. If any entry truly cannot be fixed,
  the baseline stays shrink-only with a reason per entry, and the guide's Known Deviations names it.
- [ ] **Behaviour proven.**
  - The affected Bazel binaries and their tests pass in `//autonomy/...`: motion ingestion fixtures and
    references, motion metrics, pooled metrics and camera projection.
  - CUDA on GPU 1 when it is free (no compute process, memory.used < 1024 MiB).
  - Where a native tool has a recorded fixture output, it is byte-identical before and after.
- [ ] **Guide.** The Known Deviations section in `docs/guides/cpp-engineering.md` is updated.
- [ ] **Gates.** `//:repo_gate`, `//autonomy/...` and `//parallax/...` pass through `./bazelw`.
