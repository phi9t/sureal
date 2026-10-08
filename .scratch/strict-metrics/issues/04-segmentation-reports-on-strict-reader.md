# 04: Segmentation metric reports read strictly

**What to build:** Every active reader of a segmentation metric report, starting with the segmentation contract fixtures, uses the strict segmentation reader. A `nan` or `inf` class line now rejects the report instead of being skipped.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The segmentation contract fixtures read through the strict reader; their regex patterns are gone
- [ ] Any other active segmentation report reader found by search is migrated or listed with a reason
- [ ] A test proves that a fixture report holding `nan` is rejected
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
