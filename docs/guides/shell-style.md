# Shell Style

Sureal shell exists to glue together tools. Keep policy, validation, launch-plan
construction and evidence parsing in Python modules where they can be tested.
Shell wrappers should be thin, explicit entry points.

## Language And Startup

- Use Bash only. New and rewritten shell files start with `#!/bin/bash`.
- Start executable scripts with `set -euo pipefail`.
- Prefer `main "$@"` for scripts with more than one helper function.
- Put a short file header after the shebang that says what the script does.
- Do not rewrite receipt-pinned scripts for style alone. Retained receipts are
  byte-exact evidence; leave them untouched unless the owning task explicitly
  re-admits the evidence.

## Data And Names

- Constants are `readonly UPPER_SNAKE_CASE`.
- Variables and functions are `lower_snake_case`.
- Use arrays for argv, not strings that are later split.
- Keep environment exports near the command that consumes them unless they are
  script-wide configuration.

## Tests And Expansion

- Use `[[ ... ]]` for tests and `(( ... ))` for arithmetic.
- Quote expansions: `"$path"`, `"${items[@]}"`, and `"${name:-default}"`.
- Use `read -r`, `mapfile`, and process substitution when reading lines.
- Avoid backticks; use `$(...)`.

## Output And Errors

- User-facing status goes to stdout.
- Warnings, usage errors and failure context go to stderr.
- Print secrets never. If a tool might echo credentials, disable tracing and
  redirect or redact the unsafe output.

## Formatting

- Use two-space indentation.
- Keep lines at or below 120 columns where practical.
- Put pipeline continuations at the beginning of the continued line when a
  pipeline must wrap.
- Prefer one command per line over dense compound statements.

## Tooling

The repo gate runs ShellCheck at its default severity over every tracked
`*.sh` file plus extensionless versioned hooks, excluding only files whose
current bytes are pinned by retained receipts or current-candidate audits.

ShellCheck comes from a Bazel-pinned release archive, not from host packages.
Rules may be disabled only in `.shellcheckrc` or an inline directive, and each
disable needs a one-line reason next to it.
