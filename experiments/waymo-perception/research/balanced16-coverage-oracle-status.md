# Balanced16 native target-coverage diagnostics

These are annotation-only ideal predictions, never detector outputs or model inputs. All three runs preserve the exact same 1,279 native GT boxes and use the official native evaluator. Independent live audits reread every exported protobuf field and replay each score exactly.

| Ideal prediction set | Vehicle APH | Pedestrian APH | Sign APH | Cyclist APH |
|---|---:|---:|---:|---:|
| Every positive-point native GT | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| Every training-eligible ROI GT | 0.917384 | 0.947955 | 0.868421 | 0.918919 |
| Every anchor-covered training GT | 0.917384 | 0.944238 | 0.759399 | 0.918919 |

Positive-point native counts are 581/269/266/37; training-eligible ROI counts are 533/255/231/34; covered counts are 533/254/202/34 (vehicle/pedestrian/sign/cyclist). The original target NPZ and ordered eligible-ID report independently agree on all covered indices and the exact uncovered list: 29 signs and one pedestrian.

The covered-target sign control misses the 0.8 gate even with exact boxes, headings, classes and score=1. It bypasses detector proposal/NMS errors. This establishes a supervision coverage problem in addition to the previously measured class learning/ranking weakness. Class weighting, normalization and longer training do not create positive supervision for the missing object IDs. The ROI control shows that covering those signs would make the ideal-target threshold attainable under this GT scope; it does not establish that a real model can attain it.

This is not a mathematical ceiling on an unconstrained detector: it may predict objects without a positive training assignment. It is not evidence that a particular replacement assignment, grid or encoder improves learning. The preregistered matched optimization controls and unchanged all-four-class fitting gate remain. Target assignment geometry, maximum-overlap conflicts, grid support and NMS require separate diagnostics/treatments; do not combine a target change silently with weighting or remove difficult GT.

Decision: needs-more-evidence for a model improvement; adopt explicit uncovered-target reporting and this ideal-control diagnostic. No architecture or scientific-training readiness is adopted.

Evidence: balanced16-coverage-oracle-native-verified.json (three native scores and exact source bindings), balanced16-coverage-oracle-audit-verified.json (three independent native protobuf/metric replays). The current baseline0/19/35 GPU admission pilot remains an engineering execution gate and has not established sustained fit.

## Literal assignment cause audit

A separate live CPU Insula audit independently rebuilt all 524,288 anchor labels and target indices for each of the 16 frames and matched the original arrays exactly. Every uncovered object has positive maximum overlap. For 28 objects, another GT wins every maximizing anchor with strictly greater overlap; for two signs, the original ordered argmax resolves equal-IoU ties to another sign. There are 27 sign-to-sign conflicts, two sign-to-vehicle conflicts, and one pedestrian-to-pedestrian conflict. Thus 28 of the 30 conflicts involve the same class; simply restricting matching by class does not resolve those existing same-class collisions. The two tied signs do not have identical nearest-BEV rectangles.

The audit took 74.436 seconds with peak RSS 229,428 KiB. Its source and input hashes, immutable live outputs, per-object winners and height differences are retained in `balanced16-coverage-causes-verified.json`; the literal worker is `../analysis/balanced16-coverage-causes.py`. These are causes of missing assignments under the existing rules, not evidence that a proposed new matcher improves detection. A coverage-preserving matching rule and geometric alternatives require separate frozen one-factor treatments, target verifiers, and native model evaluation. The current training targets and four optimization recipes remain unchanged.
