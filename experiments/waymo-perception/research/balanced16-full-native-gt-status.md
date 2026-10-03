# Balanced16 full native GT and V3 export

The original balanced16 preparation workers selected positive-point boxes whose centers fall inside the training ROI. Source-data reconciliation found1,279 native four-class boxes across the same16 frames,1,153 with positive point counts and1,053 inside that ROI. The new `cohort/sustained_groundtruth.py` retains every native box, including zero-point and outside-ROI boxes, and reports training eligibility separately. Native difficulty values of `None` remain unspecified. The native evaluator determines metric eligibility from the original metadata.

| Class | Native boxes | Positive-point boxes | Training ROI eligible |
|---|---:|---:|---:|
| Vehicle |639|581|533|
| Pedestrian |300|269|255|
| Sign |302|266|231|
| Cyclist |38|37|34|

`balanced16-full-native-gt-verified.json` records live locked CPU Insula export and independent direct-source field/order/ID/periodic-heading checks for all1,279 boxes. Training eligibility matches the original target reports. The first native fixture refused unspecified difficulty; `balanced16-full-gt-native-difficulty-red-verified.json` preserves the meaningful regression failure and `balanced16-full-gt-preparation-v2-verified.json` records41 passing groups after preserving `None`. Original failed fixture logs remain in `insula/balanced16-full-native-gt-v1/output/live.log`.

`cohort/prepare_sustained_v3.py` checks externally pinned manifest/anchor templates/all16 head files and every native frame/physical/box payload. It uses the existing V3 score-first decoder with unchanged thresholds/NMS and all10 physical LiDAR returns for prediction point counts/NLZ metadata. Training IDs and uncovered target counts are reported without filtering evaluation GT. `balanced16-historical-v3-fullgt-export-verified.json` records its live execution on the unchanged historical baseline2000 heads (45.857s), producing8,000 proposals and full native GT. This validates export execution; independent proposal geometry, native protobuf/metric replay and new sustained training remain open.

Ruling: the new balanced16 V3 scoring path retains all native four-class GT, with no loader-side ROI/point-count exclusion. Historical ROI/V2 metrics remain contextual; changing both scope and decoder is not an architecture effect. No matched improvement or overfit acceptance follows. All-four-class APH>=0.8 and two consecutive scored checkpoints remain required.
