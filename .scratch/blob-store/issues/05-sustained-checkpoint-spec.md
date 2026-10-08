# 05: Sustained-checkpoint publication spec

**What to build:** The sustained controller publishes and releases each checkpoint through the publication module, keeping its subprocess entry point and its lock handoff, with release only after a passing audit.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The sustained-checkpoint publication is a spec with checkpoints under the `checkpoints/` area and release enabled
- [ ] Its subprocess entry point and `--lock-fd` lock handoff behave as before for the controller
- [ ] Local files are released only after store, readback and a passing audit; a failing audit releases nothing (tested)
- [ ] The controller backend's readers of publication receipts read the new shape
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
