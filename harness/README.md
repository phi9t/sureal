# `harness`

`harness/` owns repository tooling: checks, wrappers and support code that make
Sureal's development and verification process reproducible. It is a top-level
component and a Python import root. Code under this tree imports from
subpackage names such as `lint`, never from `harness`.

## Owns

- Repo-gate lint and audit tooling.
- Thin host-side hook checks that are safe outside Insula.
- Future build, workflow or release harnesses that are about the repository
  process rather than Autonomy or Parallax behavior.

## Boundaries

- Bazel remains the authoritative verification boundary through `./bazelw`.
- Host hooks stay cheap and static; they do not import Autonomy or Parallax
  runtime code.
- `scripts/` remains the Surflo-compatible user-entry boundary until a ticket
  moves a specific command.

## Subpackages

- [`lint/`](lint/README.md): repo-gate static policy checks, baselines and
  their tests.
