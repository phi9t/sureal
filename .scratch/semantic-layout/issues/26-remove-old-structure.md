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

## Comments

2026-10-07: Integrated the GPU runtime recipe prerequisite at `cb387ab164eaffca2d667a91d065ef709683c5e9`. Commit `79a23b0` preserves seven exact file moves into Insula; the follow-up wires build context names, dependencies and the colocated test. Both independent reviews accepted the exact candidate hashes. Installed images and caches were preserved.

The worker passed 150 fresh CPU targets, two focused test methods and 30 publication checks. The parent reran `./bazelw test --nocache_test_results --test_output=all //autonomy/insula:build_gpu_bazel_rootfs_v6_test`: two methods executed and passed (invocation `401facbe-ba05-447a-91bb-b105adca956d`). Research records, wrapper and toolchain remain unchanged. This prerequisite does not claim a GPU execution or image rebuild.

The raw supervisor verdict remains DEGRADED: its seven missing allowed outputs are exactly the seven authorized old paths removed by the pure moves; it reported no findings. Separate parent acceptance is retained at `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runtime-recipes-parent-acceptance.json`. The remaining directory cleanup, production source-closure wiring and full ticket acceptance checks are still pending.
