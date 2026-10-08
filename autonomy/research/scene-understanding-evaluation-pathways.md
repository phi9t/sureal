# Scene-understanding evaluation pathways

Research checked 2026-09-30. Recommendations below are proposals for the user's
Q2 investigation, not settled definitions or approved model implementations.
This note distinguishes upstream task contracts from untested local hypotheses.
Source revision: `99a4cb3ff07e2fe06c2ce73da001f850f628e45a` for Waymo Open Dataset.

## What each evaluation can establish

| Path | Native measurements and inputs | What a successful result establishes; remaining boundary |
| --- | --- | --- |
| Perception detection / tracking | Official detection AP/APH and tracking MOTA/MOTP under class, difficulty, matcher and geometry configuration; native sensor labels and IDs. Camera-only 3D has LET geometry. | Label/track quality on the selected benchmark; not evidence of improved behavior prediction or safer driving. [Metric configuration][metrics], [native tools][tools] |
| LiDAR semantic segmentation | Class IoU/mIoU on annotated TOP points, preserving unlabeled masks. | Semantic geometry quality on labeled support; sparse labels do not measure all sensors or frames. [Metric implementation][segmetrics], [source contract](program-source-audit.md) |
| Camera video panoptic segmentation | wSTQ, wAQ and mIoU with sequence identity, cross-camera mappings and camera coverage weights. | Semantic and temporal association quality; ordinary image IoU alone omits identity consistency. [Official metric interface][panoptic] |
| Motion forecasting | Scenario historical tracks/maps; optional supported historical LiDAR/camera tokens. minADE/minFDE, miss rate, overlap rate, mAP/soft mAP with fixed horizon, K and class breakdowns. | Added representation value for forecasting under controlled inputs; oracle-track results do not measure recovery from detector errors. [Motion schema][scenario], [Motion metrics][motion] |
| Occupancy and flow | Motion-derived grids; observed/occluded occupancy AUC and soft IoU, flow EPE, flow-warped occupancy scores. | Dense future occupancy/motion quality under the chosen raster/visibility protocol; does not directly establish a planner's response. [Official implementation][occupancy] |
| Sim Agents | Joint scenario rollouts evaluated through kinematic, interaction and map-based distributional likelihoods and a configured aggregate; collision/offroad diagnostics also reported. | Multi-agent simulation realism under that protocol. Its score is not an ego planner's safety score. [Official evaluator][sim] |
| E2E driving | Separate E2EDFrame images, ego history and intent; five-second ego trajectories and sparse preference labels. Official schema reports cluster rater scores and ADE at 3/5 seconds against the highest-rated reference. | Offline imitation/preference agreement. Neither ADE nor rater agreement demonstrates interactive closed-loop safety. [E2E schema][e2e], [metric schema][e2emetrics] |
| Closed-loop planning | Requires specified simulator, observation interface, dynamics, reactive-agent policy and rollout metrics. Waymax provides a JAX simulator for WOMD. | Policy behavior only under those declared simulation assumptions; integration and evaluation have not been audited here. [Waymax][waymax] |

Geometry diagnostics (reprojection residuals, motion-compensation consistency,
coordinate/time checks) are useful engineering measurements. Treat them as local
diagnostics unless tied to an official benchmark definition. The existing
[two-scene tracer](tracer-bullet-e2e.md) establishes structural/payload plumbing;
it has not established any of the model-quality outcomes above.

## Three paper anchors and their implications

1. **Wayformer — Nigamaa Nayakanti, Rami Al-Rfou, Aurick Zhou, Kratarth Goel,
   Khaled S. Refaat and Benjamin Sapp.** Its attention encoder studies early,
   late and hierarchical fusion of heterogeneous scene inputs. This motivates
   a controlled feature-fusion probe: hold oracle tracks/maps and the predictor
   protocol fixed, then compare additional causal scene features. The paper's
   benchmark results do not establish the value of our proposed features.
   [Author paper](https://arxiv.org/abs/2207.05844),
   [Waymo research page](https://waymo.com/research/wayformer/).
2. **MTR — Shaoshuai Shi, Li Jiang, Dengxin Dai and Bernt Schiele.** Global
   intention localization and local movement refinement use motion queries to
   represent multimodal futures. This is a useful forecasting anchor for asking
   whether scene cues change mode probabilities or refinement accuracy. Keep K,
   target selection and confidence handling fixed; changing those changes the
   comparison. Adoption and reproduced performance remain unaudited.
   [NeurIPS primary paper](https://papers.neurips.cc/paper_files/paper/2022/hash/2ab47c960bfee4f86dfc362f26ad066a-Abstract-Conference.html).
3. **UniAD — Yihan Hu, Jiazhi Yang, Li Chen, Keyu Li and coauthors.** Its
   planning-oriented network coordinates tracking, mapping, motion/occupancy
   prediction and planning through query interfaces. It motivates testing
   representation utility downstream instead of equating perception quality
   with planning value. It was instantiated on nuScenes; transfer to Waymo and
   closed-loop improvements are not established by its reported results.
   [CVPR primary paper](https://openaccess.thecvf.com/content/CVPR2023/html/Hu_Planning-Oriented_Autonomous_Driving_CVPR_2023_paper.html).

## Recommended investigation, before defining the representation

Start with a frozen Motion forecasting experiment using native Scenario oracle
tracks/maps. Compare tracks+maps against the same inputs plus one specified
scene representation. Use only version-supported sensor extensions, restrict
all features to `current_time_index`, and stratify by extension availability.
Do not manufacture Perception-to-Motion joins from similar timestamps or names.
The schema provides historical sensor extensions; it does not provide a general
cross-dataset join contract. [Scenario schema][scenario]

Predeclare cohort, feature interface, missing-feature handling, predictor
capacity/training budget, metric configuration and paired per-scenario analysis.
A frozen-head probe tests immediate usability; a matched retraining probe tests
learnable value. Report these separately. First measure effect on official
forecasting metrics plus calibration/mode diagnostics, not a guessed planning
benefit. Then test predicted-track input degradation separately from the oracle
experiment so error propagation is measurable.

A later E2E offline probe can test ego prediction and preference agreement using
its own native inputs. Closed-loop planning should remain a separate gate until
reactive-agent assumptions, rollout observations and simulator compatibility are
specified. Neither a Perception semantic model nor a Motion forecaster should
be called a validated planner from offline scores alone.

## TensorFlow-free compatibility audit

The user's no-TensorFlow constraint applies to acquisition, processing, training
and evaluation. Do not install a TF evaluator in an isolated environment as a
fallback.

- Detection/tracking/LiDAR segmentation native C++ executables and Motion C++
  library are candidates: declared direct dependencies omit TF. Transitive
  build/runtime closure and benchmark-config parity still need verification.
  [Prior audit](program-source-audit.md), [native tools][tools].
- The official E2E rater-feedback helper imports typing and NumPy, making it a
  promising TF-free path. Package-free loading, upstream fixtures and exact
  threshold/aggregation parity are still untested. This narrows the prior E2E
  compatibility gap; it does not claim a working local evaluator. [Helper][rfs].
- Camera-panoptic code imports DeepLab2 STQ; its transitive import/dependency
  closure needs inspection before claiming TF-free compatibility. [Code][panoptic].
- Occupancy-flow and Sim Agents official Python metric modules explicitly import
  TF. A TF-free implementation would need parity tests against pinned reference
  fixtures/configuration; official equivalence is currently blocked/unverified
  under the constraint. [Occupancy code][occupancy], [Sim Agents code][sim].
- Waymax's simulator is JAX-based, but its setup requirements include TensorFlow
  and its WOMD loader imports it. A validated TF-free ingestion/runtime path is
  a separate prerequisite, not something established by the simulator's name.
  [Setup][waymaxsetup], [loader][waymaxloader].

No code, datasets or models were downloaded or executed for this investigation;
only primary source text was inspected. No model performance, statistical
significance, TF-free runtime or closed-loop equivalence claim is established.

[metrics]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/metrics.proto
[tools]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/metrics/tools/BUILD
[segmetrics]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/metrics/segmentation_metrics.cc
[panoptic]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/wdl_limited/camera_segmentation/camera_segmentation_metrics.py
[scenario]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/scenario.proto
[motion]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/motion_metrics.proto
[occupancy]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/utils/occupancy_flow_metrics.py
[sim]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/wdl_limited/sim_agents_metrics/metrics.py
[e2e]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/end_to_end_driving_data.proto
[e2emetrics]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/protos/end_to_end_driving_metrics.proto
[rfs]: https://github.com/waymo-research/waymo-open-dataset/blob/99a4cb3ff07e2fe06c2ce73da001f850f628e45a/src/waymo_open_dataset/metrics/python/rater_feedback_utils.py
[waymax]: https://github.com/waymo-research/waymax
[waymaxsetup]: https://github.com/waymo-research/waymax/blob/main/setup.py
[waymaxloader]: https://github.com/waymo-research/waymax/blob/main/waymax/dataloader/womd_dataloader.py
