# Sureal: from surface reconstruction to coherent scene hypotheses

**Assessment:** Sureal's strongest contribution today is a
reproduction-oriented research framework, not yet a new generative scene model.
It takes Surflo's reconstruction system, makes its execution and failure modes
inspectable, and builds experiments around a consequential question:

> Does a model produce samples from one coherent scene, or merely a collection
> of individually plausible surface points?

The repository has substantial machinery for investigating that distinction.
The learned, persistent scene-hypothesis model described below is the next
scientific step, rather than an established result of the current experiments.

**Scope.** This assessment covers `main` at commit `4ff0ab8`, dated September
27, 2026: model configuration, decoder, scene API, experiment runners,
evaluators, validation code, tests, and tracked results. The numerical values
below are **repository-recorded GPU measurements** and were not independently rerun
for this assessment. The repository's CPU contracts and publication checks are
separate from those recorded B200 runs.

## 1. Three layers, kept distinct

| Layer | Main locations | Contribution |
|---|---|---|
| **Inherited reconstruction system** | [`surflo/`](../surflo/), [`configs/`](../configs/), [`training/`](../training/) | Surflo's image encoding, surface flow, rendering-guided reconstruction, extraction, evaluation, and training machinery. |
| **Sureal experimental infrastructure** | [`experiments/insula-scout/`](../experiments/insula-scout/), [`experiments/photoreal-scenes/`](../experiments/photoreal-scenes/), [`experiments/3d-pathway/`](../experiments/3d-pathway/) | B200 execution records, controlled ambiguity experiments, numerical fixtures, maintained-system adapters, provenance, and validation. |
| **Proposed learned research** | this document and [`MISSION.md`](../MISSION.md) | A progression toward sampled scene-level uncertainty, persistent queries, appearance generation, dynamics, and grounded language. |

Sureal is a fork of [Surflo](https://github.com/Anttwo/Surflo). Surflo's model,
authors, paper, and implementation remain the inherited reconstruction
baseline; readers seeking Surflo itself should use the upstream repository.
The Python package remains `surflo`, and checkpoint formats, Hydra names, and
core interfaces retain their existing identities. That compatibility boundary
lets Sureal develop a research agenda without presenting the inherited
architecture as an independently invented model. The upstream method is
described by [guedon-surflo-2026](https://arxiv.org/abs/2606.13644).

The maturity boundary is equally important. The photoreal benchmark evaluates
stock Surflo. It does not train a scene prior or implement video generation,
language supervision, or 4D dynamics. Module 13 is an executable construction
showing why shared scene randomness differs from independent point randomness;
it does not learn that distinction from images.

## 2. The inherited architecture

Surflo is a useful starting point because it separates expensive observation
processing from repeated surface queries. The released configuration and
decoder implement this approximate execution structure:

```text
Unposed RGB views
       │
       ▼
VGGT features, cameras, depths, and world points
       │
       ├── Patch features from layers 4, 11, 17, 23
       │        ↓ projection + spatial encoding
       │        ↓ Perceiver-style compression
       │        └── 128 geometry tokens × 512 channels
       │
       └── Camera features
                ↓ separate compression
                └── 1 camera token × 512 channels

Source oriented-point queries + flow time
       │
       ▼
Point decoder conditioned on compressed tokens
       │
       ├── 6 cross-attention blocks
       ├── 6 additional MLP-only blocks
       └── 6-dimensional position/normal flow
       │
       ▼
ODE integration
       │
       ├── Plain: oriented surface points
       └── Guided: rendering-based refinement → extraction
```

The geometry compressor uses 128 latent tokens, the feature width is 512, and
the point decoder has 12 blocks with six cross-attention blocks and 16 attention
heads. The six-dimensional field represents oriented points, not physical
six-dimensional motion. These values are inspectable in
[`configs/model/surflo.yaml`](../configs/model/surflo.yaml) and
[`surflo/nn/decoder.py`](../surflo/nn/decoder.py).

### Points do not self-attend in the plain decoder

In `GatedCrossAttention`, queries come from current point tokens while keys and
values come from the shared latent context. The subsequent MLPs and
normalizations act on individual point tokens. There is no point-to-point
self-attention in this decoder.

For fixed encoded conditioning \(c\), the plain velocity field therefore has
the form

\[
\frac{d x_i(t)}{dt}=v_\theta(x_i(t),t;c).
\]

Each point trajectory depends on that point, time, and shared context, rather
than the evolving positions of the other decoded points. With \(P\) queries and
\(K\) latent tokens, cross-attention scales with \(PK\), rather than \(P^2\).
Pointwise MLP work still scales with \(P\), and the observation encoder has its
own costs. This factorization is why surface sampling density can increase
without all-to-all output-point interaction. It is also the factorization to
examine when observations leave mutually exclusive completions unresolved.

### `SceneState` caches evidence; it is not a sampled world

The public API makes the encode/query separation explicit:

```python
from surflo import Surflo

model = Surflo.from_checkpoint("checkpoints/surflo_v0.pt", device="cuda")
scene = model.encode("media/sample")
result = scene.reconstruct(mode="plain", num_query_points=100_000, seed=0)
```

[`SceneState`](../surflo/api.py) caches normalization statistics, compressed
geometry and camera tokens, VGGT outputs, and lazily computed guidance data.
Its `global_state` property returns compressed geometry tokens. Repeated
reconstruction calls can therefore reuse one observation encoding.

Reusing an encoding is not the same as reusing one sampled hidden scene. The
current state primarily represents observed evidence; the proposed hierarchical
completion model needs a distinct stochastic scene-level variable.

Nor is the \(128\times512\) token tensor the full memory footprint. Stored in
BF16 it occupies 128 KiB, but the current state also retains the input batch,
intermediate scene tokens, world points, and other data. A compact scene-serving
interface would need an explicit export and retention contract.

### Guided inference is a different interaction structure

The plain decoder's factorization should not be generalized to the full guided
pipeline. Rendering-based refinement couples the reconstruction through shared
image agreement; the recorded guided configuration also uses depth priors,
densification, and polishing. The paired-scene ambiguity probes described below
use **plain inference**, not the full guided system.

## 3. Point uncertainty and scene uncertainty

Two kinds of uncertainty should not be conflated:

- **Surface-sampling uncertainty:** where to place points on one selected
  surface.
- **Scene-hypothesis uncertainty:** which mutually exclusive surface or object
  configuration exists outside observed support.

Let \(O\) denote observations and \(z\) a sampled scene-level variable:

\[
z\sim p_\psi(z\mid O),
\qquad
x_i\sim p_\theta(x_i\mid z,O).
\]

The point-set distribution is

\[
p(X\mid O)
=
\int p_\psi(z\mid O)
\prod_i p_\theta(x_i\mid z,O)\,dz.
\]

The order of the mixture and product is the important part. An idealized
independent-point mixture over two alternatives is

\[
p_{\mathrm{point}}(X\mid O)
=
\prod_i\left[\pi p_A(x_i)+(1-\pi)p_B(x_i)\right],
\]

whereas a coherent scene mixture is

\[
p_{\mathrm{scene}}(X\mid O)
=
\pi\prod_i p_A(x_i)
+
(1-\pi)\prod_i p_B(x_i).
\]

If A contains a sofa and B a mutually exclusive bookshelf, the first
distribution can place points on both alternatives inside one sample. The
second selects an alternative before populating its surface. For a deliberately
simplified balanced binary example, independently choosing a mode for every
point gives probability \(2^{1-P}\) that all \(P\) choices agree. This is a
mathematical illustration, not an estimate of Surflo's measured behavior.

Conditional independence does not inherently prevent coherent reconstruction.
A fixed latent can describe one coherent scene, and independent points can
sample it correctly. The concern arises when the latent leaves mutually
exclusive scene uncertainty unresolved and only independent point sampling
expresses the remaining variation. PointFlow provides an earlier shape-then-
points factorization in a different setting
([yang-pointflow-2019](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html)).

Sureal's architectural hypothesis is therefore precise: preserve the scalable
point decoder, but move uncertainty about scene identity into one shared sampled
representation. The repository has not yet shown that a learned implementation
improves completion under a matched controlled comparison.

## 4. What the recorded experiments establish

### B200 scout: working execution paths

The scout records real executions of plain reconstruction, guided
reconstruction, meshing, baseline evaluation, and one optimizer step. For the
16-view garden example it reports about 4.92 seconds for plain ODE
reconstruction versus 29 seconds including startup, and 58.06 seconds for
guided reconstruction versus 92 seconds including startup. The guided run
produced about 1.57 million mesh vertices.

The one-scene Tanks & Temples comparison records:

| Method | Normalized Chamfer ↓ | F1 ↑ |
|---|---:|---:|
| Surflo plain | 0.004679 | 0.9057 |
| Surflo guided, no densification | 0.004610 | 0.8893 |
| VGGT raw | 0.006064 | 0.8565 |
| DA3 raw | 0.006527 | 0.8212 |
| VGGT + TSDF | 0.014753 | 0.7350 |
| DA3 + TSDF | 0.014351 | 0.7051 |

These are one-scene scout results, not a reproduction of a benchmark aggregate.
They show why metric and pipeline distinctions matter: guidance slightly
improves Chamfer while reducing F1 in this case, and the tested TSDF paths are
worse than their raw-point counterparts. Neither additional optimization nor
fusion is automatically an improvement.

The training evidence is narrower still: one optimizer step with 8,192 points,
a recorded gradient norm, and a math-SDPA workaround. It establishes that the
training path can execute in that environment, not convergence or improved
pretraining.

### Analytic ambiguity probe: mixed support

The analytic experiment constructs two rooms with identical context images and
different hidden geometry. It encodes the context once, then reconstructs with
four point-sampling seeds. Three samples cross the probe's hybrid-support
threshold. The fourth favors scene A but retains substantial scene-B support.
Mean observed-common recall is about 82.4%, versus 45.9% for unobserved common
surfaces.

This is evidence that changing point-sampling randomness does not cleanly select
the intended scene alternatives in that controlled example. It does not isolate
decoder factorization as the sole cause.

### Photoreal probe: unsupported hidden alternatives

The photoreal benchmark uses one shared 16-view context and two hidden-object
alternatives: a sofa and a shelf. It records metric cameras, depth and ray
distance, geometric and shading normals, object IDs, geometry, and visibility.
The context is rendered once without either hidden object and hard-linked into
both episodes.

| Quantity | Recorded result |
|---|---:|
| Observed-common recall | **76.57%** |
| Unobserved-common recall | **5.64%** |
| Hidden support for hypothesis A | **0** |
| Hidden support for hypothesis B | **0** |
| Support classification across four seeds | **All unsupported** |

This is not the same failure as the analytic experiment. The photoreal result
shows no support for either benchmark-defined hidden alternative rather than a
supported mixture of both.

The target views are highly extrapolative: about 98% of target-visible surface
samples are new relative to context. Camera-center RMSE after observed-only
alignment is about 0.31 metres, while the support threshold is about 0.127
metres. There are four seeds, and inference is plain. These diagnostics do not
separate representation, camera estimation, domain shift, and completion
training objectives.

“Unsupported” means unsupported relative to this benchmark's alternatives and
thresholds. It is not a universal statement that Surflo can never produce
plausible hidden geometry.

### Support labels are not completeness certificates

The probe first marks a sample unsupported when both alternative supports are
below 0.10. Otherwise it marks the sample hybrid when the smaller support is at
least 60% of the larger; remaining samples receive the alternative with greater
support. Consequently, 11% support for A and zero for B can receive the A
support label while missing most of A.

In the derived schema these values are named `support_label`,
`support_labels`, and `paired_support_labels`. A `scene_a` or `scene_b` value
means only that the named alternative has greater relative support after the
unsupported and hybrid gates; it does not mean that the object has adequate
coverage.

These **support labels do not certify object completeness**, topology, physical
plausibility, or full-scene coherence. They are thresholded relative-support
summaries. The Module 15 curriculum therefore reports support-label fractions
and explicitly says point-level within-sample coherence is unavailable.

## 5. The reproduction framework

The fifteen-module pathway records each method's evidence, observable
quantities, representation, inference procedure, objectives, metrics, and
failure sweeps. It spans observability and classical geometry; acquisition,
fusion, and mapping; learned depth and continuous fields; radiance fields and
splatting; feed-forward geometry; and finally generation, dynamics, and the
Surflo endpoint.

That structure prevents a single undifferentiated “3D quality” ranking from
concealing whether a system estimates cameras, explains observed pixels,
recovers visible surfaces, or samples plausible hidden worlds.

| Maintained adapter | Evaluated output | Boundary retained |
|---|---|---|
| COLMAP SfM | Cameras and sparse structure | Sparse reconstruction is not dense completion. |
| COLMAP MVS | Depths, fused points, and mesh | Visible-surface reconstruction is not a hidden-scene posterior. |
| ORB-SLAM3 | Trajectory and sparse map | Tracking recovery and new-map creation are distinct events. |
| Depth Anything V2 | Per-view metric depth | A depth estimate is not a sampled complete scene. |
| NeuS-Facto | SDF/radiance fit and mesh | Unseen output is not automatically validated completion. |
| Nerfacto | Radiance and density field | Density is not an SDF surface. |
| Splatfacto | Gaussian rendering primitives | A Gaussian PLY is not a triangle mesh or canonical surface. |
| Foundation geometry | Cameras, depths, points, and supported heads | Direct points, unprojected depth, and tracks remain distinct. |

The runner writes into staging, records input and implementation hashes,
persists results and reports, validates them, and only then promotes the run
atomically. Module 15 is explicitly marked `reused_measured_result`; other
concept labs are controlled fixtures. The generative and dynamic validators
recompute metrics from persisted arrays and regenerate failure sweeps rather
than trusting favorable scalar output.

Hash agreement establishes artifact identity; recomputation establishes
consistency with an evaluator. Neither alone proves independent replication,
evaluator validity, or generalization. Binding a fixture to the shared Blender
episode likewise does not turn its teaching metric into a benchmark score.

## 6. Engineering and scientific limits

### CPU and GPU gates answer different questions

At the inspected commit, publication CI covered repository auditing,
distribution metadata, and secret scanning. The repository also contained a
substantial CPU numerical suite, but it was not a required CI job. A separate
required `numerical-contracts` job now runs that complete offline CPU suite,
covering concept fixtures, evaluator contracts, corruption rejection, and
aggregate semantics. This job is not evidence for a fresh GPU measurement.
B200 reference execution remains an explicitly versioned, separately reported
gate.

### The positive shared-latent example is constructed

Module 13 copies visible points into each sample. Independent samples receive
per-point binary choices; shared samples receive one choice reused across all
queries. Its success is built into the construction. It is a valuable evaluator
test and mathematical illustration, but not evidence that an image-conditioned
model learns useful latent modes or generalizes beyond training scenes.

### Identical pixels and physical equivalence are different guarantees

The current photoreal benchmark guarantees identical input bytes by rendering
shared context without either hidden object. A future dataset should also render
the complete alternatives and measure context agreement, or construct scenes in
which hidden alternatives cannot affect observed indirect light or reflections.
That is a proposed consistency check, not a demonstrated bug in the current
benchmark.

### Runtime guarantees require precise names

The CPU lab's offline guard replaces Python socket constructors during
in-process fixture execution. This is not an operating-system network sandbox.
Maintained reference containers use stronger network isolation. Likewise, the
CPU memory statistic is based on a process high-water mark; when modules share a
process it is not an isolated per-module peak. Reports should name both scopes.

### Scene setup is duplicated

`SceneState` and the plain inference runner duplicate normalization and token
setup, as the API documentation acknowledges. Before introducing stochastic
persistent state, that setup should be centralized or protected by strict
equivalence tests so entry points cannot silently diverge. This publication
change does not modify the inherited inference core.

## 7. Research directions

The next result should be one small learned scene-level completion experiment,
not a larger point cloud or another adapter.

### 7.1 Build scene episodes, not only RGB–depth pairs

Synthetic supervision is useful because it controls what exists, what is
observed, what stays hidden, and what changes. A scene episode should retain
geometry, camera conventions, visibility, materials and illumination, object
identity, and—where applicable—correspondence and dynamics.

Relevant primary precedents include complete synthetic indoor supervision in
[roberts-hypersim-2021](https://arxiv.org/abs/2011.02523), procedural indoor
variation in
[raistrick-infinigen-indoors-2024](https://arxiv.org/abs/2406.11824),
programmable rendering in
[denninger-blenderproc2-2023](https://doi.org/10.21105/joss.04901), and dynamic
physics-backed data generation in
[greff-kubric-2022](https://openaccess.thecvf.com/content/CVPR2022/html/Greff_Kubric_A_Scalable_Dataset_Generator_CVPR_2022_paper.html).

“Ground truth” remains relative to the simulated scene and annotation
definition. Camera-axis depth and ray distance, geometric and shading normals,
and first-surface and transparency-aware observations must remain distinct.
Context and target cameras should be sampled jointly, with difficulty measured
by the fraction of target-visible surface not observed in context—not camera
displacement alone.

Ambiguous pairs should share observable geometry while varying hidden
configurations. Complete-hypothesis rerenders should quantify any cue leakage
through shadows, reflections, or indirect illumination.

### 7.2 Separate evidence, hypothesis, and surface queries

The proposed interface has three conceptual objects:

\[
c=E(O),
\qquad
z\sim p_\psi(z\mid c),
\qquad
X,C\mapsto Q_\theta(c,z;X,C).
\]

- **Evidence state** \(c\) records what observations establish.
- **Scene sample** \(z\) selects one completion consistent with evidence.
- **Query result** returns geometry or appearance while reusing that same
  \((c,z)\).

A surface-resampling seed may change point locations without changing the
hidden furniture configuration. A scene seed may change that configuration.
Changing the camera must query the selected scene rather than silently select a
new one.

CUT3R is a useful deterministic precedent for state updated by observations
([wang-cut3r-2025](https://openaccess.thecvf.com/content/CVPR2025/html/Wang_Continuous_3D_Perception_Model_with_Persistent_State_CVPR_2025_paper.html)).
3DRAE/3DDiT is a more direct cutoff-valid precedent for diffusion in a compact
3D-grounded latent decoded along camera trajectories
([wei-3drae-2026](https://arxiv.org/abs/2604.11331)). Neither establishes the
specific partial-observation posterior proposed here.

### 7.3 Use matched data and diagnostic controls

Stock Surflo is a useful starting reference, but stock Surflo versus a newly
trained latent model is not a decisive comparison. The central experiment
should train a deterministic completion model and a shared-latent model on the
same episodes, with comparable decoder capacity and compute. Otherwise an
improvement may come from explicit completion supervision rather than the
latent factorization.

An oracle-hypothesis diagnostic should supply the correct scene code. This
separates a decoder unable to represent each alternative from a conditional
prior unable to select or cover them.

A practical sequence is:

\[
z^\star=E_{\mathrm{complete}}(S),
\qquad
p_\psi(z^\star\mid O).
\]

First learn a complete-scene representation and its geometry/rendering
decoders. Then learn the partial-observation conditional prior. The complete
scene is a training target, never undeclared conditioning available to the
partial-observation model. DiffComplete and coherent single-image scene
diffusion provide relevant, narrower completion precedents
([chu-diffcomplete-2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html),
[dahnert-scene-diffusion-2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html)).

### 7.4 Require four properties together

Acceptance should be conjunctive:

1. **Evidence preservation:** observed surfaces and known free space remain
   consistent.
2. **Within-sample validity:** one completion has adequate support and does not
   combine mutually exclusive configurations.
3. **Across-sample coverage:** the sample set covers intended alternatives
   without counting hybrids as successful diversity.
4. **Cross-query persistence:** geometry resampling, point-count changes, and new
   cameras preserve the selected hypothesis.

Persistence is a scene-level property; independently resampled point clouds
need not contain identical coordinates. Generalization splits should separate
scene layouts, assets, and occluder structures, not merely nearby cameras from
the same scene. Results should be reported across disocclusion severity and
support thresholds.

### 7.5 Add appearance before dynamics and language

The first appearance experiment should use a leave-and-return camera trajectory
with one fixed sampled scene. Explicit depth, normal, and visibility controls
provide an inspectable path; latent conditioning can then be added and ablated.
Changing \(z\) while holding the camera fixed must change appearance in ways
consistent with the selected geometry.

World-coordinate-conditioned video diffusion and explicit Gaussian features in
video diffusion provide component precedents
([zhang-world-consistent-video-diffusion-2025](https://openaccess.thecvf.com/content/CVPR2025/html/Zhang_World-consistent_Video_Diffusion_with_Explicit_3D_Modeling_CVPR_2025_paper.html),
[schwarz-generative-gaussian-splatting-2025](https://arxiv.org/abs/2503.13272)).
They do not prove that a partial-observation scene posterior will be calibrated
or persistent.

Only after the static and appearance results are convincing should physical
dynamics and language enter the model. Physical time must remain distinct from
flow-integration time, and identity through occlusion must be evaluated apart
from camera-motion estimation. St4RTrack provides a feed-forward 4D
reconstruction/tracking reference
([feng-st4rtrack-2025](https://st4rtrack.github.io/)).

Grounded language should express simulator-verified facts, spatial relations,
and interventions while respecting observability. SpatialVLM and SpatialRGPT
show narrower geometry-grounded spatial-reasoning precedents
([chen-spatialvlm-2024](https://arxiv.org/abs/2401.12168),
[cheng-spatialrgpt-2024](https://arxiv.org/abs/2406.01584)). They do not show
that language supervision will improve a shared generative scene state. A model
must not be taught to state privileged hidden labels as if they were visually
established facts.

## Bottom line

Sureal combines an executable reconstruction baseline, controlled negative
results, explicit representation boundaries, and provenance-aware evaluation.
It is strongest where it refuses to equate a rendered image with correct
geometry, a Gaussian file with a mesh, or point-level randomness with a sampled
world.

The inherited non-commercial research-and-evaluation license remains in force;
the fork and compatibility layer do not remove it.

The next defining result is a learned model that selects one plausible hidden
scene, preserves observed evidence, supports repeated queries without changing
that scene, and covers alternative scenes across samples on held-out
configurations. That result would turn Sureal from a well-instrumented
investigation of the problem into evidence for a solution.
