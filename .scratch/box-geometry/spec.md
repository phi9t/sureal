# Box geometry: one home for oriented-box math in the geometry concept

Status: ready-for-agent

Governing decisions: `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md`, `docs/adr/0001-directories-express-concepts.md` and `autonomy/ARCHITECTURE.md`. Vocabulary follows `autonomy/CONTEXT.md` (oriented box, source pin, source snapshot).

## Problem Statement

Every concept that touches an oriented box carries its own copy of the same few formulas, and nothing ties the copies together.

- **The point-in-box test exists seven times.** The viewer export, the NLZ overlap check, foreground support, prediction records, the real-NLZ validator and two proposal audits each rotate points into the box frame and compare against the half-extents. All of them use inclusive `<=` boundaries and the same box convention today, but nothing keeps them that way.
- **Heading wrap is written inline in about nine places.** All active producer copies use `(a + π) % 2π − π`, which gives [-π, π). A fix or a change of convention would have to find every copy.
- **Two direction-correction rules disagree, silently.** `box_coding.direction_correct` tests the sign of the raw yaw, while `scored_proposals_v3.canonical_direction_correct` wraps first and then tests the sign. They give different answers whenever the raw yaw is outside [-π, π). Both are used on purpose (v2 and v3 decoding), but no test says so.
- **BEV rectangle and IoU math is re-implemented.** The detection concept owns the axis-aligned enclosing and nearest-rectangle BEV IoU. Detection diagnostics and the evaluation audits re-implement them inline.
- **The geometry concept cannot be used for any of it.** `geometry/` holds coordinate transforms and range-grid math but nothing about boxes. Its Bazel visibility excludes detection, segmentation and evaluation, and its library depends on `dataset` and `evidence`, so even a visible box helper would drag those in.
- **Behaviour is only tested where each copy happens to be tested.** There is no single suite that pins down boundary inclusion, degenerate-box rejection or heading wrap at ±π.

## Solution

The geometry concept gains one small, dependency-free module for oriented-box math: point-in-box membership, heading wrap, box corners in BEV, and the two BEV rectangle forms with their IoU. Every producer that carries a copy calls the module instead. The migration is strictly behaviour-preserving: before any copy is removed, a parity test runs the old copy and the new module over the same randomized and edge-case inputs and requires exactly equal results.

Concept-specific rules stay in their concepts. Direction correction is a detection rule and stays in detection, built on the module's heading wrap; both v2 and v3 rules keep their behaviour, and a test records where they differ. Non-maximum suppression stays in detection, built on the module's IoU.

Independent checkers keep their own copies on purpose. A proposal audit or a reconciliation script exists to check a producer with a second implementation; if it called the same module, a bug in the module would pass its own audit. These copies are named as deliberate second implementations and left alone.

The three detection files that the association study lists in its baseline source map (`box_coding.py`, `detector_geometry.py`, `scored_proposals_v3.py`) are migrated too. Under ADR 0001 a source pin refers to a source snapshot, and the association contract records the digests it is given rather than comparing them against the working tree. The association study's next run therefore records new source pins, which is expected.

## User Stories

1. As a researcher, I want one function that says which points lie inside an oriented box, so that every concept counts box points the same way.
2. As a researcher, I want box membership to include points exactly on a box face, so that boundary handling matches what every existing copy already does.
3. As a researcher, I want membership to apply no tolerance or dilation, so that box membership is the mathematical box and nothing else.
4. As a researcher, I want boxes with non-finite values or non-positive dimensions rejected, so that a degenerate box never silently matches no points.
5. As a researcher, I want one heading-wrap function that maps any finite angle into [-π, π), so that every concept agrees on the canonical heading.
6. As a researcher, I want heading wrap at exactly π and -π to have one documented result, so that boundary angles do not depend on which copy ran.
7. As a researcher, I want BEV box corners from one function, so that drawing code and any future polygon code agree on corner order and orientation.
8. As a researcher, I want the nearest-rectangle and enclosing-rectangle BEV forms in one place, so that anchor assignment, suppression and diagnostics use the same rectangles.
9. As a researcher, I want axis-aligned BEV IoU in one place, returning zero when the union is empty, so that suppression and assignment never divide by zero differently.
10. As a researcher, I want the module to state the oriented-box convention (centre z, length along local x, width along local y, metres and radians, vehicle frame), so that no caller has to infer it from code.
11. As a researcher, I want the module to accept both one box and an N×7 array where the existing callers need them, so that callers do not reshape boxes by hand.
12. As a researcher, I want the module to depend only on numpy, so that any concept can use it without pulling in dataset or evidence code.
13. As a researcher, I want detection, segmentation, evaluation and inspection to be allowed to depend on the module, so that the box math has one home those concepts can reach.
14. As a researcher, I want the dependency to point downward from those concepts into geometry, so that the concept graph stays acyclic.
15. As a researcher, I want the v2 direction correction and the v3 canonical direction correction to keep their exact behaviour, so that retained v2 and v3 results stay reproducible.
16. As a researcher, I want a test that shows where the two direction-correction rules differ, so that the difference is a recorded fact rather than a surprise.
17. As a researcher, I want both direction-correction rules built on the shared heading wrap, so that their difference is only the rule, not the wrap.
18. As a researcher, I want suppression to stay a detection operation built on the shared IoU, so that geometry does not learn about scores and limits.
19. As a researcher, I want the NLZ overlap check and foreground support to use the shared membership function, so that segmentation's box membership matches detection's point counts.
20. As a researcher, I want prediction records to count points in a box with the shared function, so that `num_lidar_points_in_box` means the same thing as everywhere else.
21. As a researcher, I want the viewer export and the explorer's BEV drawing to use the shared module, so that what I see in the viewer matches what the pipeline computes.
22. As a researcher, I want ground-truth canonicalization and target building to use the shared heading wrap, so that targets and decoded predictions share one heading branch.
23. As a researcher, I want independent audits and reconciliation scripts to keep their own second implementations, so that an error in the shared module is still caught by an audit.
24. As a researcher, I want each independent checker to say that its copy is deliberate, so that a future cleanup does not "fix" the independence away.
25. As a researcher, I want the module's own tests to compare against an independently written reference (for example an inverse homogeneous transform), so that the module is not only tested against itself.
26. As a test author, I want a parity test that runs each old copy and the new module on the same inputs before the copy is deleted, so that the migration provably changes no result.
27. As a test author, I want parity inputs to include random boxes and points, points exactly on faces, edges and corners, yaw at ±π and multiples of π/2, and very large and very small dimensions, so that edge cases are covered rather than sampled by luck.
28. As a test author, I want parity to mean exact equality (identical booleans, counts and float bits), so that boundary points cannot quietly flip.
29. As a test author, I want degenerate inputs rejected identically by old and new code, so that error behaviour is preserved too.
30. As a test author, I want every existing caller's tests to pass unchanged after migration, so that the migration is proven at the callers' own interfaces.
31. As a researcher, I want the association study's next run to record new source pins for the migrated detection files, so that its evidence is honest about which code ran.
32. As a researcher, I want frozen code (`research/`, `studies/*/procedure_records/`, `studies/architecture/harness/`) left untouched, so that retained procedures stay byte-identical.
33. As a maintainer, I want one place to change if the box convention ever changes, so that the change is local and testable.
34. As an agent reading the code, I want box math to live where the concept map says geometry lives, so that I find it without searching six concepts.

## Implementation Decisions

- **Module.** A new module in the geometry concept for oriented-box math, built as its own Bazel library with no dependencies beyond numpy. It is visible to detection, segmentation, evaluation and inspection (inspection already sees geometry). The existing geometry library is unchanged and does not need to depend on it.
- **Interface.** Small and array-first:
  - point membership for one box (mask or count) and for many boxes;
  - heading wrap to [-π, π) using the exact expression the producers use today, so results are bit-identical;
  - BEV corners for a box, in a documented order;
  - nearest and enclosing BEV rectangles, and axis-aligned BEV IoU between rectangle sets.
  Validation (finite values, positive dimensions, shape) happens inside, with one error message family.
- **Boundary semantics.** Inclusive `<=` on all three half-extents, no tolerance. Rotation into the box frame uses the same cos/sin projection and operation order as the current copies, so parity can be exact.
- **What stays in detection.** Box encoding and decoding, both direction-correction rules, and enclosing-BEV suppression. They call the module for wrap and IoU. Their public names and signatures are unchanged.
- **Producers migrated.**
  - Inspection: viewer export point counting and the explorer's BEV corners.
  - Segmentation: NLZ overlap and foreground support.
  - Detection: prediction records' point counts, box coding's decoded-heading wrap, the BEV rectangles and IoU, v3 canonical direction correction's wrap, sustained ground-truth canonicalization, and overfit target building.
- **Independent checkers keep their copies.** A file whose stated purpose is to check a producer independently keeps its own implementation: the proposal audits in evaluation, the real-NLZ validator, the balanced16 coverage reconciliation in detection diagnostics, and the full ground-truth fixture's atan2 comparison. Each gets a one-line note that the copy is deliberate. Any other file found during migration is classified by the same rule and the verdict is listed in the ticket.
- **Association baseline.** `box_coding.py`, `detector_geometry.py` and `scored_proposals_v3.py` are migrated with the rest. Their behaviour is unchanged; their bytes change, so the association study's next run records new source pins. No retained evidence is edited.
- **Frozen code** is not touched.

## Testing Decisions

- **Good tests use the interface only.** Tests call the module's public functions and the callers' existing public functions; they do not reach into private helpers.
- **Module tests.** Boundary inclusion on faces, edges and corners; degenerate and non-finite rejection; wrap at ±π and at large multiples of 2π; corner order; IoU symmetry, identity and empty union. Membership is also checked against an independently written inverse-homogeneous-transform reference away from exact boundaries.
- **Parity harness.** A test-only helper that runs a given old copy and the new module over a fixed seed of random inputs plus a fixed edge-case set, and asserts exact equality of outputs and identical rejection of invalid inputs. Each migration ticket adds the parity cases for the copies it removes, runs them green against the old copy first, then switches the caller and deletes the copy. The old copy lives only inside the parity test after that, so the evidence of parity stays in the suite.
- **Direction-correction test.** One test feeds raw yaws inside and outside [-π, π), including exactly 0 and ±π, into both rules and asserts both their agreement inside the range and their documented disagreement outside it.
- **Prior art.** `detection/detector_geometry_test.py`, `detection/box_coding_test.py`, `segmentation/nlz_overlap_test.py`, `segmentation/foreground_support_test.py`, `detection/prediction_records_test.py` and `inspection/viewer/export/manifest_test.py`; all keep passing unchanged.
- **Gates per ticket.** The default CPU suite, the `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded.

## Out of Scope

- Rotated (polygon) BEV IoU or 3D IoU. The detection concept deliberately uses axis-aligned reference geometry and never native rotated metrics.
- Unifying the two direction-correction rules.
- Changing any independent audit, validator, reconciliation script or fixture comparison.
- Frozen code under `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/`.
- Metric parsing in the same evaluation and studies files, which belongs to the strict-metrics work.
- The torch sine-difference heading loss, which is a loss term, not a wrap.

## Further Notes

- Evaluation audit scripts and the studies harness are also touched by the strict-metrics work. Box tickets change only box math, and only in producers, so the two sets of tickets do not overlap in practice.
- If a parity test ever fails, the copy is not migrated; the difference is reported in the ticket as a finding, because it means two concepts were already computing different answers.
