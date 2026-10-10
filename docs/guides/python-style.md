# Python Style

Sureal Python follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
unless this guide records a deliberate project delta. These rules apply to new
and touched Python under `autonomy/`, `parallax/` and repository maintenance
scripts.

## Project Shape

- Directories name concepts, not languages or runtime tiers. Put new code under
  the concept it implements.
- Tests live next to the code they test as `foo_test.py`, unless the surrounding
  package already uses a more specific colocated pattern.
- Keep live one-shot procedures separate from reusable library code. Historical
  procedure records and retained receipts are evidence bytes, not cleanup
  targets.

## Module Layout

Use this order for ordinary modules:

1. Module docstring.
2. `from __future__ import annotations`, when useful.
3. Standard-library imports.
4. Third-party imports.
5. Sureal imports.
6. Constants, small data classes, helper functions, public functions and
   `main()`.

Prefer small modules with one clear owner. A module that needs comments to
explain which half owns which policy should probably split along the concept
boundary.

## Imports

- Code under `autonomy/` imports from `autonomy/` as the import root: use
  `from evidence...`, `from pipeline...`, or `from resources...` as appropriate,
  not relative imports and not `from autonomy...`.
- Code under `parallax/` imports from `parallax/` as the import root.
- Do not edit `sys.path` in active code. Documented live commands and receipts
  may still set `PYTHONPATH=autonomy`.
- Import what you use. Avoid import-time work beyond constants and cheap type
  definitions.

## Naming

- Modules, packages, functions, variables and parameters use `lower_snake_case`.
- Classes and exceptions use `PascalCase`.
- Constants use `UPPER_SNAKE_CASE`.
- Test methods name the behavior they pin.
- Preserve external spellings at boundaries: upstream APIs, metric names,
  receipt field names and file formats keep their recorded names.

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
- Do not reformat files whose bytes are protected by retained receipts,
  current-candidate source declarations or source snapshots. The Ruff wrapper
  derives those exclusions from repository evidence.

## Tooling

The repo gate runs Ruff from a Bazel-pinned release archive, not from host
packages. The initial lint gate enforces syntax and undefined-name failures
(`E9`, `F821`) over active unpinned Python, and the format gate covers only the
current batch of concept directories. Later batches should expand the formatted
directory list and then widen lint rules based on a fresh live run.
