# 01: C++ engineering guide and mechanical C++ lint

**What to build:** A contributor writing new C++ or CUDA in Sureal follows one self-contained guide,
`docs/guides/cpp-engineering.md`, and `//:repo_gate` rejects the guide's mechanical violations.

**Blocked by:** None (can start immediately)

**Status:** done

Source: `~/workspace/milano/docs/guides/cxx-engineering.md` and
`~/workspace/milano/harness/workflow/lint/check_cxx.py` (with its test). Sureal's current
`docs/guides/cpp-style.md` and `.clang-format` are the starting point.

- [x] **Rename.** `docs/guides/cpp-style.md` becomes `docs/guides/cpp-engineering.md` (`git mv`). It is expanded
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
- [x] **Known deviations.** The guide lists them in their own section, naming files:
  - source-pinned C++ is frozen and exempt;
  - any rule the unpinned files break today.
- [x] **Lint.** `scripts/check_cxx.py`, a comment- and string-aware line scanner, plus `scripts/check_cxx_test.py`. It
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
- [x] **Tests.** Synthetic examples show each rule fails on a violation, and the real tree passes.
- [x] **Gate.** The check is wired into `//:repo_gate`, and the gate membership test is updated.
- [x] **References.** `AGENTS.md` names `docs/guides/cpp-engineering.md`.
- [x] **Gates.** `//:repo_gate`, `//autonomy/...` and `//parallax/...` pass through `./bazelw`.

## Comments

2026-10-10:

- Live source-pin check before edits:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`
  passed. Result: 1/1 test passed; invocation `d5dbc0ab-a751-4f06-9278-8062dd7c7624`.
- Implemented and focused live check:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:check_cxx_test //:repo_gate_cxx_test //:repo_gate_membership_test`
  passed. Result: 3/3 tests passed; invocation `dc29f068-9ba1-460f-b488-35f99a457d7a`.
- Live C++ lint summary:
  `./bazelw run --noexperimental_collect_system_network_usage --nocache_test_results //:check_cxx -- --summary-json`
  passed with 0 findings. Counts: `tracked_cxx=17`, `protected_cxx=15`, `frozen_cxx=0`,
  `submodule_cxx=0`, `cxx_lint_scope=2`, `finding_count=0`. Digests:
  `checked_digest=dbce9557fb61ab5ac95d37c4efd198b04c9c8c14c9f133802d34eafda14aabf8`,
  `excluded_digest=f64c54b6309e0553a0286aacfb33230f9cc63faf8e057a1e1272505b0f2b1c62`;
  invocation `089dad84-999a-4502-b9fb-7445a16fe8a7`.
- Required gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed. Result: 25/25 tests passed; invocation `8ee98f5d-cea8-4d9e-946e-bb5d574c4af0`.
- Required gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed. Result: 191/191 tests passed; invocation `d584f323-81e6-45fb-9e35-09ddecd0a11c`.
- Required gate:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed. Result: 32/32 tests passed; invocation `cfc18254-8f1f-4d5e-a1cc-6bfa99b36b89`.
- CUDA gate intentionally not run: sandbox has no GPU devices; coordinator owns CUDA verification.
