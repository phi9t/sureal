---
status: accepted
---

# Directories express concepts, and the two research programs are top-level components

The repository follows the [semantic polyglot layout](../repo-structure.md): a directory names a part of the system, never a language, a runtime or a kind of file. Under that rule `experiments/3d-pathway/` becomes the top-level component `parallax/` and `experiments/waymo-perception/` becomes the top-level component `autonomy/`, each moved whole in one rename. We chose this because both had outgrown "experiment" and because their internal directories (`gpu/`, `tests/`, `scripts/`, a 107-module `pipeline/`, and study stages such as `tier1/` and `cohort/`) hid what the code is about.

Inside `autonomy/`, code is reorganised into concept directories (starting from `insula`, `evidence`, `dataset`, `geometry`, `detection`, `segmentation`, `range_view`, `camera`, `motion`, `resources`, `inspection`, `studies`). Study stages dissolve: their library code moves to the concept it implements, and their one-shot procedure scripts go under `studies/<name>/`. Tests sit beside the code they test as `foo_test.py`.

## Considered options

- **Keep both under `experiments/` and let Bazel set the import root.** Rejected: it preserved every recorded path but left the hyphenated, non-importable directory names and the "experiment" framing in place.
- **A staged move that left `pipeline/`, `gpu/`, `tier1/` and `cohort/` at the old path until the balanced16 sweep closed.** Rejected in favour of one rename and a clean tree.
- **Concept directories at the repository root (`detection/`, `geometry/`).** Rejected: geometry in `parallax/` and geometry in `autonomy/` are different code today, and a shared root directory would claim otherwise.

## Consequences

- `surflo/` is the upstream fork's package and does not move or change. `submodules/`, `training/`, `configs/`, `install/`, `scripts/`, `tests/` and the three smaller experiments also stay where they are for now.
- The frozen four-recipe balanced16 sweep must be re-admitted on the new paths and sources before it can resume.
- Receipts written before the move keep their old paths. They remain historical records; see the autonomy ADR on source pins for what they are checked against.
