# Coherent-scene publication sources

**Scope.** Primary-source audit for `MISSION.md` and the planned
`docs/coherent-scene-hypotheses.md`; historical cutoff: **2026-09-25**.
The papers below establish precedents or interfaces, not that the proposed
synthetic-data + persistent-latent + language + video recipe will work. That
combined causal claim remains an experiment.

## Citation resolution

| MISSION marker | Existing registry coverage | Action |
|---|---|---|
| 0, 8 (synthetic indoor scenes; separate appearance terms) | `yang-dav2-2024` covers only the depth-transfer clause. | Add Hypersim; use it for complete geometry/camera/material/lighting metadata and its diffuse-reflectance/illumination/non-diffuse factorization. |
| 0, 7 (geometry-grounded language) | No SpatialVLM or SpatialRGPT record. | Add both; describe their evidence narrowly as spatial-QA/grounded-reasoning improvement, not proof that language improves a shared generative scene state. |
| 2 (one shared latent before points) | `yang-pointflow-2019` is sufficient. | Retain PointFlow for the probabilistic factorization only. |
| 3 (synthetic episode tools) | No Infinigen, BlenderProc, or Kubric record. | Add the four sources below (including Hypersim). Do not imply that a tool automatically emits every proposed field. |
| 4 (dynamic reconstruction) | `feng-st4rtrack-2025`, `li-nsff-2021`, `luiten-dynamic3dgs-2024`, and related dynamic records suffice for a cutoff-valid precedent. | Cite Kubric plus St4RTrack or Dynamic 3D Gaussians. D4RT is also cutoff-valid (first public 2025-12-09), but is unnecessary unless its query interface is the specific subject. |
| 5 (3D latent rendered as images/pointmaps) | `chan-eg3d-2022`, `dahnert-scene-diffusion-2024`, and `tang-diffuscene-2024` support component precedents. | Add 3DRAE/3DDiT: its 2026-04-13 first-public date is before the 2026-09-25 cutoff. Keep the combined Surflo-derived architecture explicitly proposed. |
| target-view appearance/video path | Existing dynamic records address reconstruction/rendering, but no source directly supports integrating a 3D representation with a video-diffusion prior. | Add Generative Gaussian Splatting; its evidence is a useful directly relevant precedent, not an endorsement of the exact Surflo design. |
| evolving state as observations arrive | No CUT3R record. | Add CUT3R for online state update / common-frame pointmaps; it is deterministic reconstruction, not a sampled posterior scene hypothesis. |

`guedon-surflo-2026` is cutoff-valid (first public 2026-06-11) for the
description of Surflo itself. Its reported method should not be cited as
evidence that Surflo already samples a persistent complete-scene latent; that
is correctly a repository inference in the registry.

**Registry hygiene (not changed here):** `yang-pointflow-2019` spells the
third author **Zhexin Hao**; the ICCV primary paper lists **Zekun Hao**.

## Missing primary sources to register

### Synthetic scenes and annotations

- **Proposed ID:** `roberts-hypersim-2021`
  **Mike Roberts, Jason Ramapuram, Anurag Ranjan, Atulit Kumar, Miguel Angel
  Bautista, Nathan Paczan, Russ Webb, Joshua M. Susskind.** *Hypersim: A
  Photorealistic Synthetic Dataset for Holistic Indoor Scene Understanding.*
  ICCV 2021. First public: **2020-11-04**. Primary:
  <https://arxiv.org/abs/2011.02523>.
  **Supports:** artist-authored synthetic indoor scenes with complete geometry,
  materials, lighting, cameras, dense labels, and a diffuse reflectance /
  diffuse illumination / non-diffuse-residual image factorization.

- **Proposed ID:** `raistrick-infinigen-indoors-2024`
  **Alexander Raistrick, Lingjie Mei, Karhan Kayan, David Yan, Yiming Zuo,
  Beining Han, Hongyu Wen, Meenal Parakh, Stamatis Alexandropoulos, Lahav
  Lipson, Zeyu Ma, Jia Deng.** *Infinigen Indoors: Photorealistic Indoor
  Scenes using Procedural Generation.* CVPR 2024. First public:
  **2024-06-17**. Primary: <https://arxiv.org/abs/2406.11824>.
  **Supports:** controllable, fully procedural indoor variation and rendered
  depth, normals, occlusion boundaries, segmentation, optical flow, and
  albedo. It supports the episode generator, not a claim about semantic or
  physical validity of every generated scene.

- **Proposed ID:** `denninger-blenderproc2-2023`
  **Maximilian Denninger, Dominik Winkelbauer, Martin Sundermeyer, Wout
  Boerdijk, Markus Knauer, Klaus H. Strobl, Matthias Humt, Rudolph Triebel.**
  *BlenderProc2: A Procedural Pipeline for Photorealistic Rendering.* Journal
  of Open Source Software 8(82):4901, 2023. Primary:
  <https://doi.org/10.21105/joss.04901>; maintained primary software page:
  <https://www.dlr.de/en/rm/research/publications-and-downloads/software/blenderproc>.
  **Supports:** programmatic scene/camera construction and RGB, depth,
  distance, normal, segmentation, optical-flow, and NOCS passes. Use the
  software page for current pass availability.

- **Proposed ID:** `greff-kubric-2022`
  **Klaus Greff, Francois Belletti, Lucas Beyer, Carl Doersch, Yilun Du,
  Daniel Duckworth, David J. Fleet, Dan Gnanapragasam, Florian Golemo, Charles
  Herrmann, Thomas Kipf, Abhijit Kundu, Dmitry Lagun, Issam Laradji, Hsueh-Ti
  (Derek) Liu, Henning Meyer, Yishu Miao, Derek Nowrouzezahrai, Cengiz
  Oztireli, Etienne Pot, Noha Radwan, Daniel Rebain, Sara Sabour, Mehdi S. M.
  Sajjadi, Matan Sela, Vincent Sitzmann, Austin Stone, Deqing Sun, Suhani
  Vora, Ziyu Wang, Tianhao Wu, Kwang Moo Yi, Fangcheng Zhong, Andrea
  Tagliasacchi.** *Kubric: A Scalable Dataset Generator.* CVPR 2022. First
  public: **2022-03-07**. Primary: <https://arxiv.org/abs/2203.03570>; proceedings:
  <https://openaccess.thecvf.com/content/CVPR2022/html/Greff_Kubric_A_Scalable_Dataset_Generator_CVPR_2022_paper.html>.
  **Supports:** a Python framework joining Blender and PyBullet for
  photorealistic, physics-based synthetic scenes with rich annotations,
  including datasets for optical flow. It is a starting point for dynamic and
  correspondence episodes, not an automatic guarantee of the full proposed
  correspondence contract.

### Geometry-grounded language

- **Proposed ID:** `chen-spatialvlm-2024`
  **Boyuan Chen, Zhuo Xu, Sean Kirmani, Brian Ichter, Danny Driess, Pete
  Florence, Dorsa Sadigh, Leonidas Guibas, Fei Xia.** *SpatialVLM: Endowing
  Vision-Language Models with Spatial Reasoning Capabilities.* CVPR 2024.
  First public: **2024-01-22**. Primary:
  <https://arxiv.org/abs/2401.12168>.
  **Supports:** scalable spatial-QA supervision produced from lifted 3D
  geometry and improved qualitative/quantitative spatial VQA. Its generated
  labels include estimated geometry, so it reinforces the manuscript's choice
  to prefer simulator-defined predicates where available.

- **Proposed ID:** `cheng-spatialrgpt-2024`
  **An-Chieh Cheng, Hongxu Yin, Yang Fu, Qiushan Guo, Ruihan Yang, Jan Kautz,
  Xiaolong Wang, Sifei Liu.** *SpatialRGPT: Grounded Spatial Reasoning in
  Vision-Language Models.* NeurIPS 2024. First public: **2024-06-03**.
  Primary: <https://arxiv.org/abs/2406.01584>; project:
  <https://anjiecheng.me/SpatialRGPT/>.
  **Supports:** 3D-scene-graph-derived regional spatial QA and a depth-input
  connector for spatial reasoning. It does not show that text supervision
  conditions a geometry/video generator through one shared scene state.

### Persistent 3D/4D state and appearance/video generation

- **Proposed ID:** `wang-cut3r-2025`
  **Qianqian Wang, Yifei Zhang, Aleksander Holynski, Alexei A. Efros, Angjoo
  Kanazawa.** *Continuous 3D Perception Model with Persistent State.* CVPR
  2025. First public: **2025-01-21**. Primary:
  <https://arxiv.org/abs/2501.12387>; proceedings:
  <https://openaccess.thecvf.com/content/CVPR2025/html/Wang_Continuous_3D_Perception_Model_with_Persistent_State_CVPR_2025_paper.html>.
  **Supports:** an evolving recurrent state that is updated by new images,
  produces common-frame pointmaps and cameras, and can query unobserved views.
  This is a deterministic perceptual state, not evidence of multimodal
  completion or persistent sampled scene hypotheses.

- **Proposed ID:** `schwarz-generative-gaussian-splatting-2025`
  **Katja Schwarz, Norman Mueller, Peter Kontschieder.** *Generative Gaussian
  Splatting: Generating 3D Scenes with Video Diffusion Priors.* arXiv 2025.
  First public: **2025-03-17**. Primary:
  <https://arxiv.org/abs/2503.13272>; project:
  <https://katjaschwarz.github.io/ggs/>.
  **Supports:** integrating an explicit 3D Gaussian feature field into a
  pretrained latent video-diffusion pipeline, rendering feature maps into
  multi-view images, and using depth supervision. It is the most direct
  cutoff-valid appearance/video precedent, but still does not implement
  partial-observation posterior sampling.

- **Proposed ID:** `zhang-world-consistent-video-diffusion-2025`
  **Qihang Zhang, Shuangfei Zhai, Miguel Angel Bautista Martin, Kevin Miao,
  Alexander Toshev, Joshua M. Susskind, Jiatao Gu.** *World-consistent Video
  Diffusion with Explicit 3D Modeling.* CVPR 2025. First public:
  **2024-12-02**. Primary: <https://arxiv.org/abs/2412.01821>; proceedings:
  <https://openaccess.thecvf.com/content/CVPR2025/html/Zhang_World-consistent_Video_Diffusion_with_Explicit_3D_Modeling_CVPR_2025_paper.html>.
  **Supports:** jointly modelling RGB and per-pixel world XYZ in a diffusion
  transformer; conditioning on XYZ projections for specified camera
  trajectories to generate RGB video. This is the preferred citation for a
  geometry-conditioned video path; it does not establish an explicit complete
  scene latent or posterior calibration.

## Additional cutoff-valid 2026 references currently named in MISSION.md

- **D4RT** — Chuhan Zhang *et al.*, *Efficiently Reconstructing Dynamic Scenes
  One D4RT at a Time*, CVPR 2026; first public **2025-12-09**,
  <https://arxiv.org/abs/2512.08924>. It is before the cutoff, but existing
  `feng-st4rtrack-2025` already supports the narrower reconstruction/tracking
  point without expanding the minimal citation set.
- **3DRAE/3DDiT** — Dongxu Wei, Qi Xu, Zhiqi Li, Hangning Zhou, Cong Qiu,
  Hailong Qin, Mu Yang, Zhaopeng Cui, Peidong Liu, *Any 3D Scene is Worth 1K
  Tokens: 3D-Grounded Representation for Scene Generation at Scale*, arXiv
  2026; first public **2026-04-13**, <https://arxiv.org/abs/2604.11331>.
  It is before the cutoff and is the most direct source for the fixed-complexity
  3D latent plus image/pointmap decoding claim. Register it with narrow wording.

## Recommended minimal citation set

For the publication-facing hypothesis document, cite only these primary
sources unless a sentence makes a narrower tool-specific claim:

1. **Synthetic controllable supervision:** Hypersim, Infinigen Indoors,
   BlenderProc, and Kubric.
2. **One sampled scene before many outputs:** existing `yang-pointflow-2019`,
   `dahnert-scene-diffusion-2024`, and `chan-eg3d-2022` (add
   `tang-diffuscene-2024` only when discussing object-set scene synthesis).
3. **Grounded language:** SpatialVLM and SpatialRGPT.
4. **Dynamic/evolving scene evidence:** existing `feng-st4rtrack-2025` plus
   CUT3R; use existing `luiten-dynamic3dgs-2024` only when persistent dynamic
   primitive identity is the specific point.
5. **Appearance/video path:** World-consistent Video Diffusion (preferred for
   geometry-conditioned video) and Generative Gaussian Splatting (preferred
   for explicit 3D representation within a video-diffusion prior); retain
   Hypersim for separating reflectance, illumination, and view-dependent
   residuals.
6. **Synthetic-to-real bridge:** existing `yang-dav2-2024`.

This set deliberately omits claims of a proven end-to-end gain, calibrated
posterior uncertainty, cross-camera persistence of a sampled hypothesis, or a
universally correct loss/data mixture: none is established by these sources.
