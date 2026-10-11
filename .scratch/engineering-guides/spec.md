# Engineering guides from Milano

**Status:** ready-for-agent

## Problem Statement

Sureal took Milano's first round of conventions on 2026-10-10. That round gave Sureal short style
documents (`docs/guides/{cpp,python,shell}-style.md`), Ruff, a pinned clang-format, ShellCheck, shfmt and
a shell-style lint. Since then Milano has turned its style notes into full engineering guides
(`~/workspace/milano/docs/guides/`). It has also added a mechanical C++ lint, a guide that walks the build and
qualify flows, and a repo-gate check that fails when the docs drift from the tree. Sureal has none of these.
Contributors and agents therefore still have to guess the rules for file layout, ownership, function size,
shell function contracts, and how a change travels from an edit to a gate.

## Solution

Adopt Milano's guides as Sureal engineering guides. Keep Sureal's recorded deltas: Bazel through `./bazelw`
(ADR 0002), the `#!/usr/bin/env bash` shebang, the 150-line shell limit with its shrinking baseline,
concept import roots, and source pins that keep retained evidence byte-frozen. Back each guide's
mechanical rules with a lint in `//:repo_gate`. Make the front-door docs checkable.

## Decisions

- Guides are renamed `*-engineering.md`. AGENTS.md and the lints point at the new names. Historical
  `.scratch` tickets keep their old wording; they are records, not front-door docs.
- Each guide is self-contained and lists its known deviations rather than tolerating them silently,
  as Milano's guides do.
- Tooling stays Bazel-pinned, never uv or host packages (ADR 0002).
- Nothing protected by a source pin or retained receipt is edited or reformatted.
- Milano rules that conflict with Sureal are recorded as deltas, not adopted. Examples: the Milano commit
  trailer policy, uv as the dependency authority, `#!/bin/bash`, and the 100-line shell limit.
- No feature work (Parallax, autonomy) lands while this feature is open.
- Repo tooling is grouped by concept: a top-level `harness/` component (its own import root) takes the
  repo-gate lints from `scripts/` (ticket 06), following Milano's `harness/` package layout.

## Out of Scope

- Widening the Ruff format batch or the lint rule set. That is a separate, already-offered follow-up.
- Moving source-pinned code (`autonomy/insula/` core, `autonomy/evidence/`, `scripts/_collab/`) into `harness/`;
  that waits until the deferred reruns can re-pin. Splitting `parallax/sfm/incremental.py`.
- clang-tidy, GoogleTest and Google Benchmark. These are deferred in Milano too.
