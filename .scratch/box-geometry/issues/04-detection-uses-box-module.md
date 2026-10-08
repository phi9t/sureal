# 04: Detection uses the box module, including the association baseline files

**What to build:** Detection producers take heading wrap, point counts and BEV rectangles/IoU from the geometry box module, while box coding, both direction-correction rules and suppression stay detection operations with unchanged behaviour. This includes `box_coding.py`, `detector_geometry.py` and `scored_proposals_v3.py`, which the association study lists in its baseline source map; under ADR 0001 their next run records new source pins. See `.scratch/box-geometry/spec.md`.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Parity cases pass against the old copies before each switch and stay in the suite: decoded-heading wrap, v3 canonical wrap, sustained ground-truth wrap, overfit target wrap, prediction-record point counts, and the nearest and enclosing BEV rectangles and IoU
- [ ] Box coding, `direction_correct`, `canonical_direction_correct`, `nearest_bev_iou` and `enclosing_bev_nms` keep their names, signatures and results, built on the module
- [ ] A test feeds raw yaws inside and outside [-π, π), including 0 and ±π, to both direction-correction rules and records where they agree and where they differ
- [ ] Prediction records count points with the module; NLZ overlap still comes from segmentation
- [ ] The balanced16 coverage reconciliation script keeps its literal rectangle copy, with a one-line note that the copy is deliberate; any other detection file found with box math is classified as producer (migrated) or independent checker (kept) and the verdicts are listed in this ticket
- [ ] Existing detection tests (box coding, detector geometry, scored proposals and direction, detector decode, sustained ground truth, prediction records) pass unchanged; the association contract tests pass
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded
