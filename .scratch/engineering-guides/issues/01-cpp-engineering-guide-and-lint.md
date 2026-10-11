# 01: C++ engineering guide and mechanical C++ lint

**What to build:** A contributor writing new C++ or CUDA in Sureal follows one self-contained guide,
`docs/guides/cpp-engineering.md`, and `//:repo_gate` rejects the guide's mechanical violations.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Source: `~/workspace/milano/docs/guides/cxx-engineering.md` and
`~/workspace/milano/harness/workflow/lint/check_cxx.py` (with its test). Sureal's current
`docs/guides/cpp-style.md` and `.clang-format` are the starting point.

- [ ] **Rename.** `docs/guides/cpp-style.md` becomes `docs/guides/cpp-engineering.md` (`git mv`). It is expanded
  with Milano's sections, adapted to Sureal:
  - suffix table;
  - file layout for `.cc`/`.cu` and for headers (`#pragma once`, include what you use, headers self-contained);
  - naming table;
  - ownership and lifetime (locks via guards, no-throw destructors, return values over out-params);
  - modern C++17 rules (`explicit`, `override`, `final`, `enum class`, `nullptr`, narrow scope, about 40-line
    functions);
  - errors (Sureal's `require` plus `std::runtime_error` model for command-line tools);
  - output (stdout is for results only, diagnostics go to stderr);
  - comments;
  - CUDA launch rules, only where they apply to Sureal;
  - formatting, which points at the pinned clang-format gate;
  - tests (`*_test.cc` beside the source, built by Bazel).
- [ ] **Known deviations.** The guide lists them in their own section, naming files:
  - source-pinned C++ is frozen and exempt;
  - any rule the unpinned files break today.
- [ ] **Lint.** `scripts/check_cxx.py`, a comment- and string-aware line scanner, plus `scripts/check_cxx_test.py`. It
  enforces:
  - forbidden suffixes (`.cpp`, `.h`, `.hpp`, `.hxx`);
  - `#pragma once` in headers;
  - no `using namespace` at file scope or in headers;
  - no `NULL`;
  - no plain `enum`;
  - no C-style casts of the common scalar and pointer types;
  - raw `new`/`delete` only with a nearby `owns`/`ownership` comment;
  - 120 columns.

  Scope is tracked active C++ under `autonomy/` and `parallax/`. It excludes:
  - `submodules/`;
  - research and procedure-record trees;
  - files protected by source pins (reuse `scripts/pinned_sources.py`, as `scripts/clang_format_repo.py` does).
- [ ] **Tests.** Synthetic examples show each rule fails on a violation, and the real tree passes.
- [ ] **Gate.** The check is wired into `//:repo_gate`, and the gate membership test is updated.
- [ ] **References.** `AGENTS.md` names `docs/guides/cpp-engineering.md`.
- [ ] **Gates.** `//:repo_gate`, `//autonomy/...` and `//parallax/...` pass through `./bazelw`.
