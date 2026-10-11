# Shell Engineering

This guide is Sureal's shell contract. It adapts Milano's shell engineering
rules to this repository's Insula launcher, source-pin and receipt model, and
Bazel-pinned repo gate.

## Use Shell Only For Glue

Shell exists to glue together command-line tools: locating the repository root,
checking simple environment preconditions, setting environment variables close
to the command that consumes them, entering Insula through `./bazelw`, invoking
Python modules, and wiring process streams together.

Policy, validation, launch-plan construction, source-pin handling, evidence
parsing, retention decisions and structured state belong in Python modules where
they can be unit-tested through Bazel. This follows
[ADR 0003](../adr/0003-python-over-shell-for-policy.md).

New shell scripts stay below 150 lines. Existing longer scripts are recorded in
`scripts/shell_style_baseline.json`; that baseline may only shrink. When a
grandfathered script changes substantially, move decision-making and data
handling into Python before allowing the shell wrapper to grow.

Do not rewrite receipt-pinned scripts for style alone. Retained receipts and
source-pinned scripts are byte-exact evidence; leave them untouched unless the
owning task explicitly re-admits the evidence.

## File Shape

Start every active Bash script with this shape:

```bash
#!/usr/bin/env bash
# One or more lines saying what the script does and why it exists.
set -euo pipefail
```

The header comment describes the script's role. Avoid filename restatements such
as "Runs this script"; name the boundary, artifact or workflow the wrapper
owns. Generated hooks that intentionally use a different shebang stay under
their own hook tests.

Use `main "$@"` for scripts with more than one top-level action. New and
rewritten scripts should put helper functions above `main`, then call `main` at
the end.

## Function Comments

Every function has a comment immediately above it. Use a short summary when the
signature and behavior are obvious. Add structured detail when a maintainer
needs it to call the function correctly:

```bash
# Builds a temporary runtime tree from the packaged rootfs.
# Globals:
#   SUREAL_CACHE_ROOT
# Arguments:
#   $1: candidate digest
# Outputs:
#   Writes the runtime tree path to stdout.
# Returns:
#   Non-zero if the candidate rootfs is missing.
```

Use the `Globals:` / `Arguments:` / `Outputs:` / `Returns:` block for
non-obvious functions, side-effecting functions and cross-script contracts.
Avoid comments that only repeat the command on the next line.

## Names And Scope

Constants are `readonly UPPER_SNAKE_CASE` near the top of the file. Mutable
variables and functions are `lower_snake_case`.

Prefer `local` for every function variable. Globals should represent true
process state or cross-script configuration, not convenient temporary storage.

Use `${var}` braces in new and rewritten scripts. Existing unbraced `$var`
expansions may stay until the script is otherwise touched for logic.

Keep environment exports near the command that consumes them unless they are
script-wide configuration.

## Commands And Data

Quote expansions: `"${path}"`, `"${items[@]}"`, and `"${name:-default}"`.
Leave intentional word splitting rare and obvious.

Use arrays for command construction and argv:

```bash
command=(./bazelw test --noexperimental_collect_system_network_usage "${targets[@]}")
"${command[@]}"
```

Avoid assembling a command in a string unless the string is evidence or display
text, not something to execute.

Use `[[ ... ]]` for tests and `(( ... ))` for arithmetic. Prefer explicit
conditions over relying on string truthiness. Use `case` for option parsing.

Use `read -r`, `mapfile` and process substitution when reading lines. Use
`$(...)` for command substitution; backticks are not allowed.

## Diagnostics

User-facing normal output goes to stdout. Warnings, usage errors and failure
context go to stderr with `printf ... >&2`:

```bash
printf 'missing launch plan: %s\n' "${plan_path}" >&2
```

Use `echo` only for simple fixed output where escaping does not matter. Never
print secrets. If a tool might echo credentials, disable tracing and redirect
or redact unsafe output.

## Formatting

Use two-space indentation. Keep lines at or below 120 columns.

Put pipeline continuations at the beginning of the continued line when a
pipeline must wrap. Prefer one command per line over dense compound statements.

shfmt is pinned as a Bazel-fetched release archive and checks active, unpinned
shell files with:

```bash
shfmt -i 2 -ci -bn
```

Apply shfmt before changing shell by hand so whitespace changes stay mechanical
and reviewable.

## ShellCheck

ShellCheck runs at its default severity in `//:repo_gate` over every tracked
`*.sh` file plus extensionless versioned hooks, excluding only files whose
current bytes are pinned by retained receipts or current-candidate audits.

ShellCheck comes from a Bazel-pinned release archive, not from host packages.
Fix findings at the source. A disable is allowed only for a narrow rule at the
narrowest practical scope, and each disable needs a one-line reason next to it.
Do not add file-wide or wholesale disables.

## Mechanical Shell Lint

The repo gate runs `scripts/check_shell_style.py` over active shell files under
`autonomy/`, `parallax/` and `scripts/`, excluding source-pinned files. It
enforces the `#!/usr/bin/env bash` shebang, a header comment, function comments,
the 120-column limit, no backticks and the 150-line limit outside the checked-in
baseline.

## Sureal Deltas From Milano

- Active scripts use `#!/usr/bin/env bash`, not `#!/bin/bash`.
- The shell length limit is 150 lines, with a shrinking
  `scripts/shell_style_baseline.json`.
- ShellCheck and shfmt are Bazel-pinned and run through `./bazelw`, never host
  package installs.
- Receipt-pinned, digest-pinned and current-candidate source files are exempt
  from style rewrites until their owning evidence is re-admitted.

## Checklist

- Shell is the right tool, and policy or structured state lives in Python.
- The file starts with `#!/usr/bin/env bash`, a real header comment and
  `set -euo pipefail`.
- Functions have immediate comments, with `Globals:` / `Arguments:` /
  `Outputs:` / `Returns:` when the behavior is not obvious.
- Constants are `readonly UPPER_SNAKE_CASE`; function-local variables are
  `local`.
- Expansions use `${var}` braces in new or rewritten code.
- Commands use arrays, expansions are quoted, and tests use `[[ ... ]]`.
- Option parsing uses `case`.
- Command substitutions use `$(...)`, never backticks.
- Diagnostics go to stderr with `printf ... >&2`.
- Lines stay within 120 columns, and active scripts stay within 150 lines unless
  grandfathered in the shrinking baseline.
- ShellCheck, shfmt and `scripts/check_shell_style.py` pass in `//:repo_gate`.
