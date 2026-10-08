# 02: Inspection uses the box module

**What to build:** The viewer export counts points in a box, and the explorer draws BEV box outlines, through the geometry box module, with parity proven before the inline copies are removed. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Parity cases for the viewer's point count and the explorer's corner computation pass against the old copies before the switch, and stay in the suite afterwards
- [ ] The viewer export and the explorer call the module; their inline box math is gone
- [ ] The viewer manifest tests and any explorer tests pass unchanged
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded
