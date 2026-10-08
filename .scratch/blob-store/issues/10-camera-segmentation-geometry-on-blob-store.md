# 10: Camera, segmentation and geometry scripts on the blob store

**What to build:** The remaining direct Waystone callers in the camera, segmentation and geometry concepts store and fetch through the blob store.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] No camera, segmentation or geometry module builds a Waystone command line or wraps one in an external `timeout`
- [ ] Fetches of previously published data resolve old URIs through the descriptor factory
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
