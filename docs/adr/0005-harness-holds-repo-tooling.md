---
status: accepted
---

# Harness holds repository tooling

Sureal's repo-gate lint tools live in `harness/lint/`. The top-level
`harness/` directory is a concept directory for development and verification
tooling, not a language bucket and not part of the Autonomy or Parallax runtime
surface.

## Decision

Move repo-wide mechanical checks, their baselines and their tests out of
`scripts/` into `harness/lint/`. Keep `scripts/` for Surflo-compatible user
entry points such as inference, preprocessing, evaluation and checkpoint
repacking.

`harness/` is its own Python import root, matching `autonomy/` and `parallax/`.
Code under `harness/lint/` imports sibling modules with `from lint...`; it does
not import through `harness`, `scripts` or relative module names.

The root `//:repo_gate` suite remains the front-door verification target, but
its lint targets are owned by `//harness/lint:*`.

## Considered Options

- **Keep the repo-gate tools in `scripts/`.** Rejected: the directory also
  carries Surflo's inherited user commands, so repo policy was hidden among
  end-user entry points.
- **Create one root-level tool directory per linter.** Rejected: that would make
  file kind and tool choice more prominent than the repository-policy concept.
- **Import moved code as `harness.lint`.** Rejected: concept roots in Sureal are
  import roots. Using `lint` inside `harness/` keeps the rule consistent with
  `autonomy/` and `parallax/`.

## Consequences

- New repo-policy checks belong in `harness/lint/` with colocated tests and a
  Bazel target in `harness/lint/BUILD.bazel`.
- Static hooks may call the moved standalone files with `PYTHONPATH=harness`,
  but the Insula-backed `./bazelw` gates remain authoritative.
- Documentation and workflows must refer to the moved lint paths; historical
  receipts and `.scratch/` records keep their original paths.
