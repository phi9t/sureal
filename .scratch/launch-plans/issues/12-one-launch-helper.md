# 12: One launch helper instead of five per-concept copies

**What to build:** Scripts in every concept build, run and record launch plans by calling the launch-plan module directly. The near-identical per-concept helper modules added by tickets 04 and 05 (dataset, camera, geometry, inspection, segmentation) are gone, so a change to how plans are loaded or run is made once.

**Blocked by:** 04, 05

**Status:** ready-for-agent

- [ ] The launch-plan module offers the two things every helper copy added: loading a root filesystem's runtime lock from its default lock path, and running a rendered plan as a subprocess. Path coercion of named and writable inputs happens inside `build_plan`
- [ ] The per-concept `launches.py` helpers in dataset, camera, geometry, inspection and segmentation are deleted, and their callers use the launch-plan module. Any concept-specific behaviour they held (for example the segmentation helper's metrics root) moves to its caller or to the root registry
- [ ] Their plan-against-fixture-lock tests are kept, retargeted at the callers or the module, not deleted
- [ ] Source pins and code-hash lists that named a deleted helper name the launch-plan module instead
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Found while landing tickets 04 and 05: the five helper modules differ only in the name of their build/run functions (the deletion test: deleting them moves nothing but four pass-throughs).
