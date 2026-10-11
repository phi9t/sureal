# Python Engineering

Sureal Python follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
unless this guide records a deliberate project delta. These rules apply to new
and touched Python under `autonomy/`, `parallax/` and repository maintenance
scripts.

## Project Shape

- Directories name concepts, not languages or runtime tiers. Put new code under
  the concept it implements; see `docs/adr/0001-directories-express-concepts.md`.
- Python under `autonomy/` and `parallax/` is ordinary source and stays
  editable even when older receipts mention its bytes. Historical procedure
  records, retained receipts, source snapshots and the research archives are
  evidence bytes, not cleanup targets.
- Keep live command entry points separate from reusable library code. A live
  command launches nested Insula work, touches host state, reads external assets,
  publishes evidence or otherwise depends on a runtime boundary. Library code
  should expose typed, deterministic functions that tests can call without
  those effects.
- Put repo-policy code in repository tooling and concept policy in the owning
  concept. A policy should have one owner; when two modules both decide the same
  policy, split out an owner and call it from both places.

## Module Layout

Use this order for ordinary modules:

1. Module docstring.
2. `from __future__ import annotations`, when useful.
3. Standard-library imports.
4. Third-party imports.
5. Sureal imports.
6. Constants, small data classes, helper functions, public functions and
   `main()`.

Keep functions small enough to audit in one sitting. About 40 lines is the
target, matching the C++ guide; parsing, validation, computation and rendering
usually deserve separate helpers.

Prefer returning values over mutating arguments. Accept filesystem roots,
clients, clocks and other dependencies from callers instead of constructing
them deep in the function that owns policy. Live command wrappers may assemble
those dependencies at the edge and pass them into library code.

## Imports

- Code under `autonomy/` imports from `autonomy/` as the import root: use
  `from evidence...`, `from insula...`, or `from resources...` as appropriate,
  not relative imports and not `from autonomy...`.
- Code under `parallax/` imports from `parallax/` as the import root.
- Do not edit `sys.path` in active code. Documented live commands and receipts
  may still set `PYTHONPATH=autonomy`.
- Import what you use. Avoid import-time work beyond constants and cheap type
  definitions.

The import checker in `scripts/check_imports.py` scans tracked Python under
`autonomy/` and `parallax/`. It rejects relative imports, local imports that
are not anchored at the concept import root and active `sys.path` edits. It
skips `autonomy/research/**`, `parallax/research/**`, procedure records, the
frozen architecture harness and `submodules/`.

## Tests

Tests sit beside the source they exercise as `foo_test.py`, with a Bazel
`py_test` in the same package. Test external behavior and contracts, not helper
implementation details. Repo-level policy tests may stay at the repository
root or in `scripts/` when the policy itself is repository-wide.

Sureal test tiers are Bazel tags, documented in
`docs/adr/0004-test-tiers-and-gpu-masking.md`:

- `requires_gpu`: runs only in the CUDA gate, which sets
  `SUREAL_REQUIRE_GPU=1`.
- `requires_live_gate`: launches nested live Insula work or depends on live
  host state; excluded from default sweeps unless the command asks for the live
  tier.
- `known_failure`: records unfinished or intentionally failing behavior and is
  excluded from landing gates until its ticket removes the tag.

Use `_live_test.py` for colocated Python tests that touch a live runtime, nested
Insula launch, real external asset or other host state outside pure unit
fixtures. Use `_host_test.py` for host-facing wrappers and repository boundary
behavior that still runs through `./bazelw` unless a documented static hook
says otherwise.

## Naming

- Modules, packages, functions, variables and parameters use `lower_snake_case`.
- Classes and exceptions use `PascalCase`.
- Constants use `UPPER_SNAKE_CASE`.
- Test methods name the behavior they pin.
- Preserve external spellings at boundaries: upstream APIs, metric names,
  receipt field names and file formats keep their recorded names.
- Numeric names include units when the unit is part of the contract, for
  example `timeout_seconds`, `distance_meters` or `iou_tolerance`.

## Numeric Code

- Keep units explicit in variable names, dataclass fields, receipt keys and
  command-line flags.
- Use explicit tolerances for floating-point comparisons. Name whether a
  tolerance is absolute, relative or domain-specific.
- Ground truth is only for scoring and validation. Do not feed target values,
  future observations or evaluator-only annotations into an estimator,
  predictor or planner.

## Receipts And Evidence

Receipts, retained evidence and source snapshots are data. Preserve recorded
field names even when they are awkward Python names, and translate only at the
typed boundary that owns the schema. When emitting JSON, make the schema and
field spelling explicit in tests.

Do not reformat or otherwise edit retained receipts, source snapshots,
`autonomy/research/**`, `parallax/research/**` or procedure records. The
repo-gate wrappers take those archive exclusions from `scripts/pinned_sources.py`.

## Errors

- Raise `ValueError` for invalid data or contract violations in already-opened
  inputs.
- Raise `FileNotFoundError`, `NotADirectoryError` or `OSError` when the file
  system operation itself is the contract being checked.
- Use narrow custom exceptions only when callers branch on the error type.
- Error messages name the violated contract and the relevant path, key, metric
  or runtime-lock field when that is safe to print.

## Typing

- Type public helpers and new dataclasses.
- Prefer concrete return shapes for evidence and checker code: dataclasses for
  internal results, plain dictionaries only at JSON/report boundaries.
- Use `Path` for filesystem paths after argument parsing. Convert to strings at
  subprocess, JSON and receipt boundaries.
- Avoid `Any` unless the input is genuinely untyped JSON. Narrow it before use
  with `isinstance` checks.

## Docstrings And Comments

- Public modules, classes and functions get docstrings when their contract is
  not obvious from the name and signature.
- Comments explain intent, evidence constraints, failure modes or compatibility
  decisions. Do not narrate the next line.
- TODOs need a concrete deferred decision, ticket or follow-up owner.

## Formatting

- Ruff owns Python formatting. Do not hand-align code in a way that fights the
  formatter.
- Keep lines at or below 120 columns where practical.
- Do not add minified one-liners in new or touched code. Prefer one statement
  per line and normal indentation even in scripts.
- Do not reformat retained receipts, source snapshots or historical archives.
  Active Python remains editable even when older receipts mention its bytes.

## Tooling

Bazel is the verification boundary for this repository. Run Python checks
through `./bazelw`; do not install host packages to satisfy a Bazel target.

The repo gate runs Ruff 0.6.9 from a Bazel-pinned release archive declared in
`MODULE.bazel`. `pyproject.toml` sets Python 3.10, a 120-column line length and
the initial lint rule set `E9` and `F821` over active Python in
`autonomy/**/*.py`, `parallax/**/*.py`, `scripts/**/*.py` and `scripts/*.py`.
The format check currently covers the batch under
`autonomy/association/` and `autonomy/blob_store/`. Later batches should expand
the formatted directory list and then widen lint rules based on a fresh live
run.

## Sureal Deltas From Milano

- Milano uses `pyproject.toml` plus `uv.lock` as the Python dependency
  authority and runs checked Python commands with `uv run --frozen`. Sureal does
  not adopt that rule: Bazel through `./bazelw` and the pinned Insula rootfs are
  the dependency and verification authority here.
- Milano gates Python test tiers with pytest collection and `conftest.py`
  environment checks. Sureal does not adopt that rule: test tiers are explicit
  Bazel tags (`requires_gpu`, `requires_live_gate`, `known_failure`) with the
  filename suffixes documented in ADR 0004.
