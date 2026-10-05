# 26: Remove the old structure

**What to build:** The reorganisation is finished: no legacy directory, path manipulation or duplicated helper is left, and layering is enforced by the build graph alone.

**Blocked by:** 20 (Concept batch: `camera`), 21 (Concept batch: `motion`), 23 (Concept batch: `inspection`), 25 (Studies batch: the 16-scene cohort study)

**Status:** ready-for-agent

- [ ] No `sys.path` insertion remains outside procedure records of closed gates
- [ ] No legacy directory named after a runtime, a file kind or a study stage remains
- [ ] Exactly one file-digest function and one regular-file check exist outside procedure records
- [ ] The import-layering script is removed and Bazel visibility rejects an upward dependency, shown by a deliberately failing example in the ticket
- [ ] The architecture note describes the concept directories and the snapshot model, and uses the glossary's 'pinned' wording
- [ ] The full default run and the full GPU-configuration run pass, and their module counts are recorded against the baseline
