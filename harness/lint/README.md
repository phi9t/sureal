# `lint`

`harness/lint/` owns Sureal's mechanical repository-policy checks. These checks
are small, deterministic and useful both in the versioned git hook and in
`//:repo_gate`.

## Owns

- Python import-root checks for tracked active Python under `autonomy/`,
  `parallax/` and `harness/`.
- Identifier checks that reject machine names, user home paths, host absolute
  paths and unapproved e-mail addresses.
- Mechanical C++ and CUDA style checks that do not need clang tooling.
- Shell style, ShellCheck, shfmt, Ruff and clang-format repository wrappers.
- Publication audit checks and the repo-gate membership check.

## Boundaries

- `harness/` is the Python import root. Modules in this directory import
  siblings with `from lint...`, never `from harness...`, `from scripts...` or
  relative imports.
- These modules enforce mechanical policy only; design judgment stays in
  review and documentation.
- Historical archives, retained receipts, source snapshots and submodules stay
  byte-exact and are excluded by `pinned_sources.py` where the policy calls for
  it.
- Surflo user entry points stay in `scripts/`; this package may lint them but
  does not own their compatibility contract.

## Entry Points

- `//harness/lint:check_imports` rejects imports that bypass concept import
  roots.
- `//harness/lint:check_identifiers` rejects tracked machine-local identifiers.
- `//harness/lint:check_cxx` enforces mechanical C++ and CUDA rules.
- `//harness/lint:check_shell_style` enforces Sureal shell style.
- `//harness/lint:pinned_sources_test` verifies the active archive exclusion
  rules used by repo-gate wrappers.

## Tests

The package's `*_test.py` targets live beside the modules they test. The root
`//:repo_gate` suite names the repo-gate subset explicitly so membership drift
is reviewed with the policy change that caused it.
