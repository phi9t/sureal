---
status: accepted
---

# Python owns policy; shell only orchestrates

Shell in Sureal is for short entry points that glue together command-line
programs, set environment variables close to the commands that use them, and
dispatch into the repository's Python modules. Decisions, validation,
state inspection, data transformations and evidence parsing belong in Python,
where they can be unit-tested and run through Bazel inside Insula.

We chose this because the repository's scientific workflows rely on auditable
runtime locks, receipt parsing and source-pin handling. Those are easier to
test and review in importable Python modules than in long shell scripts. The
rule also keeps rootfs and launcher scripts readable: shell may assemble a
container or call `bwrap`, but policy about what is valid and why lives in
Python.

## Considered options

- **Keep policy in shell where it is already written.** Rejected: existing
  scripts have grown beyond orchestration, and shell has weak test boundaries
  for parsing JSON, validating source pins and handling complex state.
- **Ban shell entirely.** Rejected: short wrappers are still the clearest place
  to launch system tools, enter rootfses and preserve command-line compatibility.
- **Allow long shell with comments only.** Rejected: comments make the current
  code easier to read, but do not give policy logic the importable tests that
  repo-quality gates require.

## Consequences

- New shell scripts are thin wrappers and stay below 150 lines.
- Existing scripts over 150 lines are grandfathered in
  `harness/lint/shell_style_baseline.json`, which may only shrink.
- When a grandfathered script is changed substantially, its decision-making and
  data handling move into Python before the shell wrapper grows.
- Shell style and formatting are enforced in `//:repo_gate` for active,
  unpinned shell files. Source-pinned files remain byte-exact evidence and are
  not rewritten for style alone.
