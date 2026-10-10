# What Sureal should take from Milano's conventions

Research note, 2026-10-10. Read-only survey of `~/workspace/milano` at
`diziet/mainline` `5dce94a` and `~/workspace/sureal` at `phi9t/mainline`
`0cfda26`.

Citation form:
- `milano:<path>:<line>` and `sureal:<path>:<line>` are files in each repo.
- Commit ids are Milano commits unless marked otherwise.
- Counts were measured with `git ls-files` plus small scans. They exclude
  `autonomy/research/`, `*/procedure_records/` and
  `studies/architecture/harness/` unless noted.

Context: `.scratch/repo-quality/spec.md` already ported Milano's 2026-10-09
practices: the repo gate, the identifier check, the hooks, the Python and shell
guides, ShellCheck and the import rule. Since then, on 2026-10-09 and
2026-10-10, Milano added the following, which is what this note mainly
evaluates:
- a C++ guide, a pinned clang-format and a C++ lint;
- shfmt and a shell-style lint;
- test tiers and colocation;
- a package restructure;
- ADRs.

## Summary: top recommendations, ranked by value to Sureal

1. **C++: write a short guide, and add a whitespace-only clang-format check for new and touched files (adapt).**
   - Sureal has 17 `.cc` files, no C++ guide and no formatter config.
   - Several files are minified, with whole programs on a handful of lines (`sureal:autonomy/motion/ingestion/native_source_inventory.cc:11-18`).
   - Milano's config can only change whitespace (`milano:.clang-format:8-12`), which suits evidence-bearing sources.
   - The tool must come from a Bazel-pinned archive (Sureal ADR 0002), not uv.
   - Receipt-pinned sources must be excluded the way `scripts/ruff_repo.py` does it.
2. **Python: widen the Ruff format batch and the lint rules (adapt; Sureal's own plan, Milano's sequencing).**
   - Sureal's active Python has 2,812 lines over 120 columns and about 910 lines with `;`-joined statements.
   - Ruff formats only 2 directories (`sureal:scripts/ruff_repo.py:28-31`) and lints only `E9`/`F821` (`sureal:pyproject.toml:114`).
   - Milano's pattern is to land the config and the lint first, then one whitespace-only reformat commit, then enforce (commits `9ee56da` and `12b820e`).
   - Milano itself has no Python formatter or linter. Sureal is already ahead here.
3. **Shell: add a mechanical style lint and a pinned shfmt (adopt the rules, adapt the tooling).**
   - Sureal's guide says `#!/bin/bash` and two-space indentation (`sureal:docs/guides/shell-style.md:9,41`).
   - Today 27 of 28 tracked `.sh` files use `#!/usr/bin/env bash`, only 8 have a header comment, 15 exceed 100 lines, and some use 4-space indentation.
   - Milano enforces these rules mechanically (`milano:harness/workflow/lint/check_shell_style.py:17-74`, `milano:scripts/lint_shell.sh:5`).
4. **Tests: write the tiers down as an ADR and in AGENTS.md, and make the GPU tier fail rather than skip when it runs (adapt).**
   - Milano names a host tier and a GPU tier.
   - Its root `conftest.py` gates collection.
   - Under release, a missing device becomes a failure (`milano:conftest.py:72-90`).
   - Sureal's tiers exist only as Bazel tags and filename suffixes, and are documented nowhere as a rule.
5. **Parallax layout: colocate `parallax/tests/test_*.py` and split `parallax/pipeline/` by concept (adapt).**
   - `parallax/tests/` holds 17 `test_*.py` files with `sys.path` inserts; 14 import-rule baseline entries cover them.
   - `parallax/pipeline/` is the kind of generic directory Sureal ADR 0001 dissolved in `autonomy/`.
   - Milano did both moves recently: commits `ae605a6`, `49396d0` and `4441975`.
6. **Docs: one README per concept plus a docs-staleness test, and no new ticket-numbered directories under `docs/` (adapt).**
   - These are Milano tickets docs/02 and docs/05.
   - Sureal has `docs/ticket27/` and `docs/ticket29/` beside its design docs.
7. **Shell longer than about 100 lines moves to Python (adopt as an ADR; already implied by Sureal's guide).**
   - This is Milano ADR 0001 (`milano:docs/adr/0001-python-over-shell-for-policy.md:17-21`).

Skip:
- Milano's uv-dev-group tool pinning, pytest/conftest machinery and Bazel-free build. They conflict with Sureal ADR 0002.
- Milano's ADR file format. It is equivalent to Sureal's.

---

## 1. C++

### What Milano does

- **The guide is a full contract.** `milano:docs/guides/cxx-engineering.md` (254 lines) is "adapted from the Ferric Continuum C++ engineering guide … The deliberate Milano deltas are recorded here" (`:7-11`). It covers:
  - **Suffixes:** `.cc`, `.hh`, `.cu`, `.cuh`, and `*_test.cc` for native tests. "Do not add `.cpp`, `.h`, or `.hpp`" (`:15-25`).
  - **Include grouping:** own header, then project, then third-party, then standard library (`:29-58`).
  - **Naming table:** `lower_snake` functions, `kPascalCase` constants, `lower_snake_` members, and `TORCH_ACCEL_` macros. Framework overrides keep their upstream spelling (`:78-95`).
  - **RAII:** "Raw `new` and `delete` are allowed only where an external API takes ownership … Add a nearby comment containing `owns` or `ownership`" (`:118-120`).
  - **Modern C++17 rules:** `explicit`, `override`, `enum class`, `nullptr`, C++ casts and no C-style casts, and functions of about 40 lines (`:129-146`).
  - **Errors at the PyTorch boundary:** `TORCH_CHECK`. "Do not introduce `absl::Status`" (`:150-164`).
  - **Comments** that keep intent, with `// namespace torch_accel` on closing braces (`:178-188`).
  - **Known deviations listed in the guide itself**, not silently tolerated (`:60-71`, `:97-105`).
- **The formatter can only change whitespace.**
  - `milano:.clang-format:1-12` is `BasedOnStyle: Google`, `ColumnLimit: 100`, `PointerAlignment: Left`, with `SortIncludes: Never`, `BreakStringLiterals: false`, `ReflowComments: false` and `SkipMacroDefinitionBody: true`.
  - The guide explains: "the config deliberately leaves four things to the author, so formatting never changes anything but whitespace" (`cxx-engineering.md:232-235`).
  - The formatter is pinned as `clang-format==18.1.8` in the uv dev group (`milano:pyproject.toml:15`).
- **Enforcement.**
  - `milano:scripts/format.sh:21-41` runs `clang-format --dry-run --Werror` over the tracked `.cc`, `.hh`, `.cu` and `.cuh` files.
  - `milano:harness/workflow/lint/check_cxx.py:10-29,139-171` is a comment- and string-aware line scanner. It rejects forbidden suffixes, a missing `#pragma once`, `using namespace`, `NULL`, plain `enum`, C-style casts, and raw `new`/`delete` without an ownership comment.
  - Both run in the repo gate (`milano:scripts/check_repo.sh:13-14`).
  - Each checker has a policy test: `tests/test_check_cxx.py` and `tests/test_format_config.py`.
- **Order of the rollout:**
  1. Guide, config and lint, with nothing reformatted (`9ee56da`).
  2. The rename to `.cc` and `.hh`, pure renames (`dc953bb`).
  3. A whitespace-only reformat of the whole tree, "checked per file by comparing the sources with all whitespace removed" (`12b820e`).
  4. A compile database for editors, `.clangd` plus `scripts/compdb.sh` (`3fb853a`).
  5. Tickets for the parts not done yet: a move to 120 columns (`milano:.scratch/follow-ups/issues/06-cxx-line-limit-120.md`) and clang-tidy, "deferred until the Insula rootfs ships the tool" (`cxx-engineering.md:237-238`).
- **In practice the guide holds.**
  - `milano:torch_accel/csrc/runtime/streams.cc:1-14` shows the own-header / project / third-party / std grouping and `namespace torch_accel { namespace {`.
  - `:18` shows `constexpr std::size_t kStreamsPerPool = 32;`.
  - `:67` shows `std::lock_guard`.
  - `milano:torch_accel/csrc/kernels/pointwise.cu:54-58` shows a `check_launch` helper wrapping `cudaGetLastError` in `TORCH_CHECK`.
  - `milano:torch_accel/csrc/runtime/streams.hh:13-16` documents lifetime on the declaration.
- **Native tests sit beside their source.**
  - `torch_accel/csrc/runtime/runtime_test.cc` is excluded from the extension sources and from the build digest: `milano:setup.py:89-90` and `milano:AGENTS.md:211-214`, commit `2e42b4e`.

### What Sureal does today

- **No C++ guide, no formatter, no C++ lint.**
  - No `.clang-format`, `.clang-tidy` or `.editorconfig` exists in the tree.
  - AGENTS.md names only the Python and shell guides.
- **17 `.cc` files and no headers:**
  - 14 under `autonomy/motion/`;
  - `autonomy/camera/project_camera.cc`;
  - `autonomy/insula/rootfs_compiler_smoke_test.cc`;
  - `parallax/insulas/orb-slam/surflo_rgbd.cc` (359 lines).
- **Dense or minified style.** 124 lines are over 100 columns.
  - `sureal:autonomy/motion/cli/motion_metrics_main.cc:27` puts three declarations on one line: `auto scene=read<wod::Scenario>(argv[1]); auto predictions=...; auto config=...;`.
  - The same file has `:61-66` with multiple statements per line and a one-space indent inside `main` (`:24`).
  - `sureal:autonomy/motion/ingestion/native_source_inventory.cc:11-18` is the whole program in 8 lines, with `int main(...){try{...` on one line.
  - `sureal:autonomy/camera/project_camera.cc:13-15` has `namespace fs=std::filesystem; using namespace waymo::open_dataset;` and a one-line `Require` function.
  - Includes are not grouped: `motion_metrics_main.cc:1-10` and `native_source_inventory.cc:1-10`, where `<set>` comes after `<vector>`.
- **Parallax is the exception.**
  - `sureal:parallax/insulas/orb-slam/surflo_rgbd.cc:1-30` groups includes by library with blank lines, uses an anonymous namespace and indents by 4.
- **Error model in practice.**
  - The code throws `std::runtime_error` from a `require`/`Require` helper, catches it in `main`, prints to stderr and returns 1 (`motion_metrics_main.cc:12-14,69`).
- **Build.**
  - Bazel `cc_binary`/`cc_test` targets: `sureal:autonomy/motion/BUILD.bazel:54-65` and `sureal:autonomy/insula/BUILD.bazel:126-129`.
  - Source filegroups that feed CMake and Dockerfile recipes: `sureal:autonomy/motion/BUILD.bazel:67-99`, `sureal:autonomy/camera/BUILD.bazel:20-23`.
- **Pinning.**
  - Retained receipts pin digests of these sources. Examples: `sureal:autonomy/research/motion-real-pooled-native-truth-verified.json` pins `"motion_metrics_main.cc": "10414722…"`, and `camera-projection-cli-verified.json` pins `project_camera.cc`.
- **The layout standard prefers `.h`.**
  - `sureal:docs/repo-structure.md` uses `.h`, `.cc`, `.cuh`, `.cu` and `foo_test.cc` (§4 at about line 216, §16 at about line 765).

### Gap

- Sureal has no written or mechanical C++ rule at all.
- The Python guide bans "minified one-liners in new or touched code" (`sureal:docs/guides/python-style.md:87-88`). There is no C++ equivalent, and the densest code in the repo is C++.
- Sureal has no compile database for editors.

### Recommendation

- **Adapt the guide.** Write a short `docs/guides/cxx-style.md`. Take from Milano:
  - the naming table;
  - include grouping;
  - RAII and ownership comments;
  - C++ casts only;
  - no `using namespace`;
  - `enum class` and `nullptr`;
  - one statement per line;
  - listing known deviations in the guide.

  Do not take the PyTorch, CUDA-stream and `TORCH_CHECK` sections; they have no Sureal use today. Record Sureal's real error model instead: "validate, throw `std::runtime_error`, catch in `main`, print to stderr and return non-zero".
- **Adopt the whitespace-only clang-format config verbatim, then choose the column limit.**
  - Sureal uses 120 for Python and shell.
  - Milano plans to move C++ to 120 as well (follow-ups/06).
- **Adapt how the tool is pinned.**
  - Pin clang-format as a Bazel-pinned release archive and run it as a `//:repo_gate` test, the way Ruff and ShellCheck already run.
  - Milano's uv dev group conflicts with Sureal ADR 0002, under which Bazel takes every tool from the rootfs or a pinned archive.
- **Adapt the scope.** Check only files that `scripts/pinned_sources.py` does not protect. Start with new and touched files, as the Ruff format batch does.
  - Reformatting a receipt-pinned `.cc` would break the rule in AGENTS.md against reformatting protected sources.
  - It would also change the bytes in the recipe filegroups, and so their source snapshot. By autonomy ADR 0001 the receipts stay historical, but any re-admission would have to be deliberate.
- **Adopt a small `check_cxx`-style lint** for the subset that applies: no `using namespace` at file scope, no C-style casts, no plain `enum`, no `NULL`, and no multiple statements per line. Its self-test goes beside it as `scripts/check_cxx_test.py`, following Sureal's `scripts/*_test.py` pattern.
- **Header suffix: open question.**
  - Milano mandates `.hh`. Sureal's `docs/repo-structure.md` shows `.h`.
  - Sureal has no headers yet, so this costs nothing to settle now. See the open questions.
- **Adopt `*_test.cc` beside its source.** It matches `repo-structure.md` §16 and the existing `rootfs_compiler_smoke_test.cc`.
- **Skip clang-tidy and the compile database for now.**
  - Milano defers clang-tidy too.
  - A compile database only pays off once someone edits Sureal C++ regularly.

---

## 2. Python

### What Milano does

- **No Python style guide, and no formatter or linter.**
  - `pyproject.toml` has no `[tool.ruff]` or black configuration (`milano:pyproject.toml:1-30`). No ruff, black, mypy or pyright appears anywhere in the tree.
  - The gate runs `compileall`, pytest and the import lint (`milano:scripts/check_repo.sh:12-18`).
  - As a result, 210 lines in Milano's Python are over 100 columns, and the longest is 240.
- **Imports.**
  - "The repo root is the root": absolute imports, no relative imports, and no `sys.path` or `PYTHONPATH` edits. The rule is enforced by `harness.workflow.lint.check_imports` (`milano:AGENTS.md:297-304`, commit `8db8ea3`).
  - Milano has 0 relative imports.
- **Module habits in practice:**
  - `from __future__ import annotations` in 127 of 170 files.
  - 36 `@dataclass(frozen=True)` records, for example `milano:harness/cache/cache_layout.py:9-41`.
  - `raise SystemExit(main())` entry points in 25 files.
  - Everything runs as a module (`python -m harness.workflow`). Even `torchrun` turns a path into a module (`milano:AGENTS.md:76-78`).
- **Tests use pytest throughout.**
  - Plain `test_<behavior>()` functions with `assert` and `pytest.raises(..., match=...)` (`milano:harness/cache/cache_layout_test.py:8-30`).
  - 42 files import pytest, and 0 use unittest.
  - Fixtures live in a package-local `conftest.py` (`milano:harness/workflow/conftest.py:37-61`).
  - `pyproject.toml` configures `python_files = ["*_test.py", "test_*.py"]` and `--import-mode=importlib` (`:27-30`).

### What Sureal does today

- **A written guide.**
  - `sureal:docs/guides/python-style.md` is Google style plus deltas: module order, the import root, errors, typing, Ruff ownership, a 120-column limit, and "no minified one-liners".
- **Ruff, pinned by Bazel and limited in scope.**
  - Lint is `select = ["E9", "F821"]` (`sureal:pyproject.toml:111-114`).
  - Formatting covers only `autonomy/association/` and `autonomy/blob_store/` (`sureal:scripts/ruff_repo.py:28-31`).
  - Exclusions come from receipt pins (`scripts/pinned_sources.py`).
- **Measured over 638 active files (263 tests, 375 library modules):**
  - 2,812 lines over 120 columns; the longest is 1,859.
  - About 910 lines with `;`-joined statements.
  - 25 files edit `sys.path`, most of them baselined in `scripts/import_rule_baseline.json`.
  - 77 files use `from __future__ import annotations`.
  - 356 of 375 library modules have a module docstring; Milano has 43 of 86.
- **Tests use unittest.**
  - 261 of 263 test files use unittest, and all of them have a `__main__` block.
  - Each runs as a Bazel `py_test` with `main = test` (`sureal:autonomy/motion/BUILD.bazel:114-138`).
  - Only `autonomy/association/test_contract.py` and `test_provenance.py` use pytest.
- **62 command scripts have hyphenated names** (`*-*.py`), which cannot be imported.
  - Some BUILD files treat them as a separate class, for example `COMMAND_SCRIPTS = glob(["*-*.py"])` in `sureal:autonomy/camera/BUILD.bazel:16`.

### Gap

- Sureal already has the tooling Milano lacks. Its gap is coverage: two formatted directories and two lint rules.
- Its debt is concentrated in long and minified lines.
- Milano's one Python lesson that transfers is sequencing: configure and lint, then a whitespace-only mass format with a check that nothing but whitespace changed, then enforce.

### Recommendation

- **Adapt: widen the Ruff format batch directory by directory.**
  - For each batch, check that the AST is unchanged, the way Milano compared sources with all whitespace removed (`12b820e`).
  - Then add rule families. `E7`, which catches multiple statements on one line, directly targets the ~910 minified lines.
  - This is already the plan in `python-style.md:96-99`. Milano adds only the "prove it is whitespace-only" step.
- **Skip moving to pytest.**
  - Sureal's tests run as `py_test` mains under Bazel, inside the rootfs (ADR 0002).
  - Switching would need pytest in every rootfs, plus a runner shim, and gains no coverage.
  - Adopt only Milano's habit of naming test functions after the behavior, which `python-style.md:50` already asks for.
- **Adopt** `raise SystemExit(main())` and importable `snake_case` modules for *new* command entry points. Leave the existing hyphenated scripts alone: they are referenced by BUILD globs and likely by receipts. See the open questions.
- **Skip Milano's import rule.** Sureal's `scripts/check_imports.py` already covers it, with a deliberate delta allowing `PYTHONPATH=autonomy` in documented commands and receipts (`.scratch/repo-quality/issues/07-import-rule.md`).

---

## 3. Bash

### What Milano does

- **The guide.** `milano:docs/guides/shell-engineering.md` adapts the Google Shell Style Guide.
  - **Shell only for glue.** "A shell script over 100 lines should be rewritten in a structured language unless there is a stated reason" (`:13-16`). This is also an ADR: `milano:docs/adr/0001-python-over-shell-for-policy.md:17-21`.
  - **File shape:** `#!/bin/bash`, then a header comment, then `set -euo pipefail` (`:22-26`).
  - **One recorded exception:** `scripts/rootfs/build_rootfs.sh` keeps `#!/usr/bin/env bash` because "that file is hashed into the Insula rootfs key, so do not edit it for style-only changes" (`:28-32`).
  - **Function comments:** every function has a comment, with Globals, Arguments, Outputs and Returns blocks when useful (`:44-62`).
  - **Naming:** `readonly UPPER_CASE` constants, `local` for function variables, and `${var}` braces in new code (`:66-72`).
  - **Formatting:** 120 columns, using `shfmt -i 2 -ci -bn` (`:92-103`).
  - **ShellCheck disables:** only narrow ones, each with a one-line reason (`:107-110`).
  - **A checklist** closes the guide (`:114-125`).
- **Tooling.** Pinned `shellcheck-py` and `shfmt-py` in the uv dev group (`milano:pyproject.toml:17-18`).
  - `milano:scripts/lint_shell.sh` runs ShellCheck over every `*.sh` plus extensionless hooks (`:21-41`), and shfmt with a named exemption list (`:5-10`).
  - `milano:harness/workflow/lint/check_shell_style.py:17-74` checks the shebang, a header comment on line 2, a comment above every function, 120 columns and no backticks.
  - The gate also runs `bash -n` on every script (`milano:scripts/check_repo.sh:20-22`).
  - Commits: `d5a4dcd` (ShellCheck), `2f65ed9` (shfmt), `16e16b1` (style lint), `357282a` (shebang).
- **Practice.**
  - Sourced libraries live in `scripts/lib/` with function comments (`milano:scripts/lib/gpu_lease.sh:7-14`).
  - Scripts dispatch to `python3 -m harness...` for policy (`milano:scripts/rootfs/run_pipeline.sh:15,42-52`).
- **Milano does not fully meet its own rules.**
  - `scripts/rootfs/run_pipeline.sh` is 415 lines, and `scripts/lint_shell.sh` is 124 lines.
  - Existing unbraced `$var` uses are tolerated "until they are otherwise touched" (`shell-engineering.md:71-72`).
  - Tickets exist to move the pipeline, build and release scripts to Python (`.scratch/follow-ups/issues/02-04`).

### What Sureal does today

- **The guide.** `sureal:docs/guides/shell-style.md` already covers much the same ground:
  - `#!/bin/bash` for new and rewritten files (`:9`);
  - `set -euo pipefail`, `main "$@"` and a header;
  - `readonly` constants and arrays for argv;
  - two-space indentation and 120 columns (`:41-42`);
  - ShellCheck from a Bazel-pinned archive, with pinned files excluded (`:49-55`).
- **The guide does not cover:**
  - shfmt;
  - a mechanical style lint;
  - a limit on script length;
  - function comments;
  - `${var}` braces.
- **Practice over 28 tracked `.sh` files:**
  - 27 use `#!/usr/bin/env bash`; only `autonomy/resources/refresh-hdfs-auth.sh` uses `#!/bin/bash`.
  - 8 have a header comment on line 2.
  - All 28 have `set -euo pipefail`.
  - 15 are longer than 100 lines. The largest are `experiments/insula-scout/run_scout.sh` (258), `install/build_extensions.sh` (234), `autonomy/dataset/setup-gcs.sh` (226) and `autonomy/resources/refresh-hdfs-auth.sh` (222).
  - `sureal:autonomy/insula/build_cpu_rootfs.sh:13-40` uses 4-space indentation, against the guide's 2.
  - It defines functions with no comments.
  - It embeds Python in a heredoc that sets `PYTHONPATH="$PACKAGE"` (`:18-25`), which is policy in shell.
- **Placement.** Shell scripts live inside their concept, for example `autonomy/insula/build_cpu_rootfs.sh` and `parallax/insulas/build.sh`. That is consistent with Sureal ADR 0001.

### Gap

- The rules are written down but not enforced.
- Sureal has no formatter, and no check for shebang, header or function comments.
- It has no length limit or ADR saying that policy moves to Python.
- Its rootfs build scripts may be the same kind of "hashed into the rootfs identity" files as Milano's `build_rootfs.sh`. `autonomy/insula/cpu_rootfs_build_test.py` references `build_cpu_rootfs.sh`, so exemptions have to be derived before anything is formatted.

### Recommendation

- **Adopt a Sureal `check_shell_style.py`**, with its own `_test.py`, run in `//:repo_gate`. It checks:
  - the shebang;
  - a header comment on line 2;
  - a comment above each function;
  - 120 columns;
  - no backticks.

  Like Milano, apply it to new and rewritten files first. One way to scope it is a shrinking baseline file, like `check_identifiers_baseline.json`.
- **Adapt shfmt.**
  - Pin it as a Bazel release archive, not a uv package (Sureal ADR 0002).
  - Use Milano's flags `-i 2 -ci -bn`, which match Sureal's guide.
  - Take exemptions from `pinned_sources.py` plus an explicit list of rootfs-identity inputs, each with a reason, as Milano does at `milano:scripts/lint_shell.sh:6-10`.
- **Adopt the function comment rule and the `${var}` brace rule** into `shell-style.md`.
- **Adopt the 100-line rule as an ADR.** Candidates for moving to Python:
  - `autonomy/dataset/setup-gcs.sh`;
  - `autonomy/resources/refresh-hdfs-auth.sh`;
  - `autonomy/insula/build_cpu_rootfs.sh`, where an inline-Python heredoc runs under `PYTHONPATH`.

  Sureal AGENTS.md already says "keep hooks and shell wrappers thin", and launch-plan ADR 0003 already puts launches in Python. The new ADR would make the rule checkable.
- **Skip Milano's `scripts/lib/` grouping.** Sureal keeps scripts inside their concept, which ADR 0001 requires. Milano's `scripts/` grouping by role (`lib/`, `rootfs/`, `probes/`, `remote/`) is a weaker fit for Sureal.

---

## 4. Layout and test grouping

### 4.1 Directory naming and concept ownership

**Milano.**
- Top-level directories:
  - `torch_accel/`, the extension;
  - `harness/`, the build, release and qualification harness;
  - `modeling/`, models and trainers;
  - `ndtl/`, the tracker;
  - `scripts/`, `tests/`, `docs/`, `targets/`, `spack/` and `packaging/`.
- **Recently restructured by concept:**
  - The package `milano/` was renamed to `harness/` (`3016386`).
  - Models and trainers moved to `modeling/` (`2f3d24c`).
  - The flat `harness/` was split into `insula/`, `build/`, `release/`, `cache/` and `workflow/`. The commit notes that "two modules would have shared their package's name and are renamed" (`4441975`).
  - A boundary test enforces dependency direction: `torch_accel` never imports `modeling` (`milano:tests/test_package_boundaries.py:43-50`).
- **Inside `torch_accel/csrc/`**, directories are named by role: `runtime/`, `ops/`, `kernels/`, `distributed/`.
  - `kernels/` is close to a "file kind" directory. Sureal ADR 0001 would discourage that.

**Sureal.**
- `autonomy/` has 16 concept directories, mapped in `sureal:docs/repo-structure.md:5-26`.
- Boundary tests already exist: `concept_boundary_test`, `storage_boundary_test` and `launch_plan_boundary_test` (`sureal:BUILD.bazel:5-23`).
- **Gaps:**
  - `parallax/pipeline/` (23 modules) and `parallax/tests/` keep the generic names ADR 0001 dissolved in `autonomy/`. ADR 0001 cites "a 107-module `pipeline/`" as hiding "what the code is about" (`sureal:docs/adr/0001-directories-express-concepts.md:7`).
  - `autonomy/` also has loose root files that belong to no concept: `architecture.py`, `retained_receipt_sweep*.py`, `tracer.sh`, `source_snapshot_targets.bzl` and three `tracer-*.schema.json`.

**Recommendation.**
- **Adapt** Milano's `4441975` approach to `parallax/pipeline/`: split it by concept in one rename, and add a boundary test for dependency direction. Possible groups, by module name: reference runners, fetch and assets, reporting and validation, and the generative and dynamic path.
- **Open question:** where `autonomy/`'s loose root files belong.

### 4.2 Where tests live

**Milano.** Two tiers are stated in `milano:AGENTS.md:103-124` and in ADR `milano:docs/adr/0002-tests-beside-their-source.md:58-64`.
- **Host tier.** It needs no GPU and no torch. Tests sit beside the module as `<module>_test.py` under `harness/` and `ndtl/`.
- **Repo-level policy tests** stay in `tests/test_*.py`.
- **GPU tier.**
  - Colocated under `torch_accel/` and `modeling/`.
  - Still in `tests/python` and `tests/negative`, explicitly labelled "not yet moved", with a ticket to move them (`.scratch/restructure/issues/06-colocate-runtime-tier.md`).
- **The rollout was staged** (`cae835b` through `5b40a9d`), and the GPU tier moves only when "collected test ids and runtime Gates stay equivalent".
- **Packaging excludes tests:**
  - `setup.py` drops `*_test`, `*_smoke` and `conftest` modules (`milano:setup.py:20-35`).
  - Native `*_test.cc` files are dropped from extension sources (`:89-90`).

**Sureal.**
- ADR 0001 says "Tests sit beside the code they test as `foo_test.py`" (`:9`), and `python-style.md:12` repeats it.
- `autonomy/` follows this: about 263 colocated `_test.py` files.
- **Exceptions:**
  - `parallax/tests/` has 17 `test_*.py` files that edit `sys.path`, for example `sureal:parallax/tests/test_fetch.py:12-13`, and 14 import-rule baseline entries cover them.
  - `autonomy/association/test_contract.py` and `test_provenance.py` use pytest-style names.
  - A top-level `tests/` holds 48 files under `tests/collab/` plus `tests/test_publication_audit.py`.
- **Repo-gate checkers** are in `scripts/` with tests beside them (`scripts/check_identifiers_test.py`, etc.). Root `BUILD.bazel` wires them as `py_test`s.

**Recommendation.**
- **Adopt** Milano's habit of writing exceptions down. AGENTS.md (or a test ADR, see 4.6) should name `parallax/tests/` and `autonomy/association/test_*.py` as "not yet moved" and point to a ticket.
- **Adapt** the staged move:
  - colocate the Parallax tests as `parallax/<concept>/<module>_test.py`;
  - delete their `sys.path` inserts;
  - shrink the baseline;
  - keep Bazel target names or test counts equivalent.
- **Skip** Milano's `tests/test_*.py` home for policy tests. Sureal already puts each checker's test beside the checker (`scripts/*_test.py`) and boundary tests inside the owning concept, which fits ADR 0001 better.

### 4.3 Test file naming and tier gating

**Milano.**
- Two name patterns are collected: `*_test.py` (colocated) and `test_*.py` (legacy and policy) (`milano:pyproject.toml:28`).
- `*_smoke.py` marks a multi-GPU integration smoke launched as a module, for example `torch_accel/integration/collective_smoke.py`.
- **Gating:**
  - The root `conftest.py` skips runtime-tier collection unless `MILANO_RUNTIME_TEST=1` (`milano:conftest.py:30-68`).
  - The `require_devices` fixture skips a test when too few devices are visible, but *fails* it when `MILANO_REQUIRE_DEVICES` is set by release gates: "so a masked GPU cannot turn coverage into a silent skip" (`milano:conftest.py:71-92`, commit `53418fb`).
  - Markers are used only for `parametrize` (26 uses) and one `skipif`.

**Sureal.**
- Tiers are Bazel tags: `perception_unit`, `requires_gpu`, `requires_live_gate`, `known_failure`, and tool-specific `requires_*` tags (`sureal:autonomy/motion/BUILD.bazel:131-137`).
- They are selected in `sureal:.bazelrc:12-13`. The default excludes `requires_gpu`, `requires_live_gate` and `known_failure`; `test:cuda` selects `requires_gpu`.
- The tier is also encoded in file names: `*_live_test.py`, `*_host_test.py` (`autonomy/retained_receipt_sweep_host_test.py`), and `*_boundary_test.py`.
- Five test files call `skipTest` or `skipUnless` when a resource is missing, for example `sureal:autonomy/dataset/tracer_runtime_test.py:15` and `autonomy/detection/native_detection_breakdowns_live_test.py:11`.
- None of this is written down as a rule.

**Recommendation.**
- **Adapt** the tier documentation. AGENTS.md should list each tag and filename suffix, what it means, and which command runs it.
- **Adapt** "fail, don't skip, when the tier is requested."
  - For example, `test:cuda --test_env=SUREAL_REQUIRE_GPU=1` would make a `requires_gpu` test that cannot find a device fail instead of skipping.
  - This is Milano's `MILANO_REQUIRE_DEVICES` expressed through Bazel instead of conftest. ADR 0002 rules out a pytest-only mechanism.
- **Skip** `*_smoke.py`. Sureal's `_live_test` plus the `requires_live_gate` tag already covers that role.

### 4.4 Fixtures and testdata

**Milano.**
- Test-support code is a package inside the concept, `torch_accel/testing/`. Its JIT test kernels are not shipped.
- Shared fixtures live in `conftest.py` at package scope (`milano:harness/workflow/conftest.py`).
- Test data sits beside its tests (`tests/negative/accel_kernel_allowlist.txt`).

**Sureal** has several patterns at once:
- `testdata/` directories inside a concept: `autonomy/evidence/testdata/`, `autonomy/segmentation/testdata/`.
- `*_fixture.py` and `*_fixture.cc` modules beside code (`autonomy/motion/ingestion/*_fixture.*`, `autonomy/training_execution/full_groundtruth_fixture.py`).
- `*_test_fixtures.py` (`autonomy/geometry/native_range_shape_test_fixtures.py`).
- A hyphenated `segmentation-contract-fixtures.py`.
- Fixtures under `docs/` (`docs/collaboration/fixtures`) and under `tests/collab/audit_support/fixtures`.
- `testonly` fixture libraries in BUILD files (`sureal:autonomy/motion/BUILD.bazel:46-52`).

**Recommendation.**
- **Adapt one convention:**
  - data files go in `<concept>/testdata/`;
  - reusable test code is `<module>_fixture.py`, or `<concept>/testing/` when several modules share it;
  - the code is wired as a `testonly` Bazel target.
- Do not move fixtures that receipts reference. Under autonomy ADR 0001, moves are allowed only once the snapshot is in place, so check pins first.

### 4.5 Script placement

**Milano.**
- `scripts/` holds shell entry points grouped by role (`lib/`, `rootfs/`, `probes/`, `remote/`).
- Repo lints live in a concept, `harness/workflow/lint/`, since `3016386`.
- A ticket groups `scripts/` further (`.scratch/restructure/issues/05-scripts-and-docs-layout.md`).

**Sureal.**
- Concept scripts live in their concept, which is good.
- Root `scripts/` mixes two things:
  - repo-gate checkers (`check_*.py`, `ruff_repo.py`, `shellcheck_repo.py`, `pinned_sources.py`, `publication_audit.py`);
  - upstream Surflo tools (`infer.py`, `evaluate.py`, `preprocess.py`, `download_dl3dv_10k_meshed.py`, `repack_checkpoint.py`).
- ADR 0001 keeps `scripts/` where it is "for now" (`:19`).

**Recommendation.** Open question. Milano's precedent is to give repo tooling its own concept directory, `harness/workflow/lint/`. For Sureal that would mean something like a `repo_gate/` directory. Moving the checkers would touch the root `BUILD.bazel`, the hook (`.githooks/pre-commit:9-10`) and `pinned_sources` imports, so it is not urgent.

### 4.6 Docs, ADRs, CONTEXT.md and tickets

**Milano.**
- **`docs/` layout:**
  - `adr/`;
  - `agents/` (issue tracker, triage labels, domain);
  - `design/`;
  - `guides/` (cxx, shell, build-and-qualify);
  - `ndtl/`;
  - `superpowers/{plans,specs}`.
- **ADRs** are single-context `docs/adr/NNNN-*.md`, with a `Status: accepted` line and Context, Decision, "Rejected alternatives with why" and Consequences sections (`milano:docs/adr/0002-tests-beside-their-source.md`). They were added in `5dce94a`: Python over shell, tests beside their source, and the Insula as the only boundary.
- **Glossary.** `CONTEXT.md` (69 lines) has a "Language" and a "Harness language" glossary.
- **Tickets.**
  - `.scratch/<feature>/issues/NN-<slug>.md`, with `**Blocked by:**`, `**Status:**` and checkbox acceptance criteria that end in "Verified in the Insula: …".
  - Tickets are committed, and the task queue is derived from them (`af2997c`).
- **Queued docs tickets:**
  - `docs/02`: "one README per harness subpackage: ownership, boundaries, entry points".
  - `docs/05`: "a policy test fails when the docs drift from the tree", which requires every top-level directory and subpackage to appear in the repo map.

**Sureal.**
- **ADRs** are in two places: `docs/adr/` (2, system-wide) and `autonomy/docs/adr/` (3). They use YAML `status: accepted` front matter, prose, "Considered options" and Consequences.
- **Glossaries.** `CONTEXT-MAP.md` points to `CONTEXT.md` (Collaboration) and `autonomy/CONTEXT.md`. Parallax has no `CONTEXT.md`; it has `parallax/terminology.json`.
- **Tickets** use the same `.scratch/<feature>/{spec.md,issues/NN-*.md}` scheme (`sureal:docs/agents/issue-tracker.md:7-11`).
- **`docs/` mixes things:**
  - guides and ADRs;
  - ticket-scoped report directories (`docs/ticket27/` with 10 files, `docs/ticket29/`, `docs/refactor-finish/`, `docs/strict-metrics/`, `docs/blob-store/`, `docs/launch-plans/`);
  - `docs/research/` with 791 files.
- **Concept READMEs** exist for only some concepts: `evidence`, `insula`, `resources`, `inspection/*` and three studies. `blob_store`, `camera`, `dataset`, `detection`, `geometry`, `motion`, `range_view`, `retention`, `segmentation` and `training_execution` have none.

**Recommendation.**
- **Skip** reformatting ADRs to Milano's shape. Sureal's "Considered options" format carries the same information.
- **Adapt** Milano ADR 0002 as a Sureal ADR covering:
  - the test tiers and their tags;
  - the filename suffixes;
  - fail-not-skip under a requested tier;
  - the named not-yet-moved exceptions.

  ADR 0001 states only "`foo_test.py` beside code".
- **Adapt** Milano ADR 0001 (Python over shell) as a Sureal ADR. See section 3.
- **Adapt** docs/02 and docs/05:
  - one short README per concept directory: owns, must not do, entry points;
  - a host-side `//:repo_gate` test that each top-level concept directory appears in `docs/repo-structure.md`'s concept map, and that paths named there exist.

  Today the map in `repo-structure.md:5-26` already lists 16 concepts, but nothing checks it.
- **Adopt** the rule that ticket reports go with the ticket. That means `.scratch/<feature>/`, or the receipt store for evidence, not a new `docs/ticketNN/`. Leave the existing directories alone if any receipt or retained record cites them.
- **Parallax context:** per `docs/agents/domain.md`, create `parallax/CONTEXT.md` only when its terms are actually being resolved. Not now.

---

## Where Milano conflicts with Sureal's accepted ADRs

| Milano practice | Conflicts with | Handling |
|---|---|---|
| Tools pinned in the uv dev group: clang-format, shellcheck-py, shfmt-py (`milano:pyproject.toml:13-19`) | Sureal ADR 0002: Bazel takes every tool from the rootfs or a pinned archive | Pin as Bazel release archives, as Ruff and ShellCheck already are |
| No Bazel; a digest-cached `setup.py` build (`milano:AGENTS.md:215`, `1eaaaf0`) | Sureal ADR 0002 | Express tiers and excludes as Bazel tags and targets, not conftest or `setup.py` |
| pytest `conftest.py` tier gating | ADR 0002, since tests run as `py_test` mains in the rootfs | Use tag filters plus `--test_env` |
| `scripts/` grouped by role (`lib/`, `rootfs/`) | Sureal ADR 0001: directories express concepts | Keep scripts inside their concept |
| `csrc/kernels/`, a file-kind directory | Sureal ADR 0001 | Do not copy it. Group CUDA by the operation it implements, as `repo-structure.md` §4 shows |
| Reformat the whole tree in one commit (`12b820e`) | AGENTS.md cache rules; autonomy ADR 0001 (pins refer to snapshots, but retained bytes stay byte-exact) | Format only unpinned files, with exclusions taken from `pinned_sources.py` |

## Open questions for the user

1. **C++ header suffix.** Should Sureal take Milano's `.hh`/`.cuh`, or the `.h`/`.cuh` shown in `docs/repo-structure.md`? Sureal has no headers yet.
2. **C++ column limit.** 100 (Milano today) or 120 (Sureal's Python and shell, and Milano's queued follow-up)?
3. **Reformatting pinned C++.** Should C++ that a receipt pins ever be reformatted, accepting a deliberate re-admission? Or does it stay frozen until it is next changed for logic? The cases are `motion_metrics_main.cc`, `project_camera.cc` and the motion ingestion sources.
4. **Rootfs-identity exemptions.** Which Sureal shell scripts are inputs to a rootfs or recipe identity and so need a named exemption from shfmt and shebang changes, like Milano's `build_rootfs.sh`? Candidates are `autonomy/insula/build_*rootfs*.sh` and `parallax/insulas/build-bazel-rootfs.sh`.
5. **Test framework.** Keep unittest everywhere and turn the two pytest-style `autonomy/association/test_*.py` files into `*_test.py` unittest files? Or allow pytest where the rootfs has it?
6. **Hyphenated command scripts.** Are the 62 hyphenated `*-*.py` command scripts a convention to keep (as `COMMAND_SCRIPTS` in BUILD files suggests), or should new commands be importable `snake_case` modules with `main()`?
7. **Repo-gate checkers.** Should they leave root `scripts/` for a concept directory such as `repo_gate/`, separating them from the upstream Surflo scripts? Or does ADR 0001's "`scripts/` stays for now" still hold?
8. **Ticket-numbered docs.** Are `docs/ticket27/` and `docs/ticket29/` cited by retained records? If not, should they move under `.scratch/`?
9. **GPU-tier fail-not-skip.** Is it wanted under `--config=cuda`? Some `requires_gpu` tests may currently skip on purpose on partially provisioned hosts.
10. **Parallax split.** Should `parallax/pipeline/` and `parallax/tests/` be restructured now, or wait until Parallax work resumes?
