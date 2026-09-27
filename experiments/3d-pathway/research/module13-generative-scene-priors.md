# Module 13: generative 3D and scene priors

**Primary-source synthesis; historical cutoff 2026-09-25.**

## Research conclusion

Module 13 should not teach “generative 3D” as one task.  At least six distinct
objects have appeared under that name: a distribution over point sets, a
distribution over implicit-function parameters, a 3D-aware image generator, a
view-conditioned image generator, an optimizer guided by a frozen image prior,
and an amortized 3D reconstructor.  Their output types, evidence contracts, and
random variables are different, so their metrics are not interchangeable.
PointFlow, for example, is a hierarchical probability model over a global shape
latent and points; DreamFusion optimizes one scene through a frozen 2D score;
Zero-1-to-3 samples camera-conditioned images; and LRM predicts a triplane NeRF
in one feed-forward pass
([PointFlow](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
[DreamFusion](https://arxiv.org/abs/2209.14988),
[Zero-1-to-3](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html),
[LRM](https://arxiv.org/abs/2311.04400)).

The architectural property needed at the Surflo frontier is narrower than
“stochastic output” and stronger than “all points see the same image tokens.”
One sample must first choose a persistent complete-scene hypothesis and then
reuse that choice for every point, output resolution, query batch, camera, and
time.  PointFlow is an important positive historical example because it
already samples one shape latent before sampling points.  More recent
scene-level models go further by jointly denoising object shapes and poses or
whole unordered object sets, thereby allowing inter-object relationships to
participate in one sampling process
([PointFlow, Section 3](https://openaccess.thecvf.com/content_ICCV_2019/papers/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.pdf),
[Coherent 3D Scene Diffusion](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
[DiffuScene](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html)).
Those designs motivate the target, but their published evaluations do not by
themselves prove a calibrated posterior or the cross-call persistence contract
required here.

## Terminology guardrails

| Term | Required meaning in this pathway | Not implied |
|---|---|---|
| **Reconstruction** | Estimate geometry or a renderable representation from observations. | A distribution over all evidence-compatible worlds. |
| **Completion** | Fill content outside observed support using a prior. | That several valid completions are represented, sampled with calibrated probabilities, or kept coherent. |
| **Conditional generation** | Sample from a learned distribution conditioned on text, images, partial geometry, layout, or another signal. | Evidence preservation unless the conditioning mechanism and evaluation test it. |
| **3D-aware image synthesis** | Generate images through a representation or inductive bias that supports camera control and some multi-view consistency. | Metric geometry, a watertight asset, or posterior inference for a particular observation.  GRAF, pi-GAN, and EG3D are canonical examples with radiance-field or hybrid 3D representations ([GRAF](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html), [pi-GAN](https://openaccess.thecvf.com/content/CVPR2021/html/Chan_Pi-GAN_Periodic_Implicit_Generative_Adversarial_Networks_for_3D-Aware_Image_Synthesis_CVPR_2021_paper.html), [EG3D](https://openaccess.thecvf.com/content/CVPR2022/html/Chan_Efficient_Geometry-Aware_3D_Generative_Adversarial_Networks_CVPR_2022_paper.html)). |
| **Novel-view generation** | Generate an image at a requested relative camera pose. | That independently generated views are renderings of one persistent scene.  Zero-1-to-3 explicitly trains a viewpoint-conditioned image diffusion model and uses downstream 3D optimization as a separate application ([paper](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html)). |
| **Large reconstruction model (LRM)** | Amortize image-to-3D prediction across many training assets. | Stochastic generation.  The original LRM maps an image to triplane features and a NeRF decoder in one forward pass ([paper](https://arxiv.org/abs/2311.04400)). |
| **Score distillation** | Back-propagate a frozen diffusion model's image-space score through differentiable renders to optimize 3D parameters. | Direct ancestral sampling of a 3D posterior.  DreamFusion and Magic3D are per-instance optimization pipelines ([DreamFusion](https://arxiv.org/abs/2209.14988), [Magic3D](https://openaccess.thecvf.com/content/CVPR2023/html/Lin_Magic3D_High-Resolution_Text-to-3D_Content_Creation_CVPR_2023_paper.html)). |
| **Scene sample** | One jointly interpretable state containing geometry, appearance, arrangement, and any other variables needed by downstream queries. | An unordered union of marginally plausible points or images. |
| **Arbitrary-resolution sampling** | Draw more samples from the same selected scene state. | A new scene hypothesis every time the requested point count changes. |
| **Posterior scene-hypothesis sampling** | Approximate `p(S \mid O)` so each sampled `S` respects observation `O`, samples differ where `O` is ambiguous, and all outputs from one sample share the same hidden choice. | Mere noise sensitivity, dropout variation, diverse renderings, or high aggregate point coverage. |

“3D-aware” is therefore a representation/training claim, “3D-consistent” is a
relationship among outputs, and “posterior sampling” is a conditional
distributional claim.  They must not be used as synonyms.  Likewise,
feed-forward reconstruction and LRM are historical names for amortized
prediction, not evidence that an LRM samples uncertainty
([LRM](https://arxiv.org/abs/2311.04400)).

## The probabilistic object Module 13 needs

Let `O` be the available observation and `S` a complete scene state.  The
desired target is

\[
p(S\mid O), \qquad S=(G,A,C,R,\ldots),
\]

where `G` is geometry, `A` appearance, and the remaining components can include
camera gauge, object identities/relations, or dynamics.  A practical latent
factorization is

\[
p(S\mid O)=\int p(S\mid z^*,O)\,p(z^*\mid O)\,dz^*.
\]

The critical operational rule is that one `z*` is sampled once per scene
hypothesis and retained.  Points, meshes, images, and later temporal states are
then conditionally generated from that same value:

\[
z^*\sim p(z\mid O),\qquad
X_N\sim p(X_N\mid z^*,O),\qquad
I_c\sim p(I\mid c,z^*,O),\qquad
S_t\sim p(S_t\mid z^*,O).
\]

This is a repository design requirement derived from the task, not a claim
that any one cited model implements the full interface.  Its closest canonical
antecedents are global shape latents in PointFlow, latent scene representations
in 3D-aware generators, and joint object-set diffusion in scene models
([PointFlow](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
[GRAF](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html),
[Coherent 3D Scene Diffusion](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html)).

### Why independent point stochasticity is insufficient

Suppose the observations admit exactly two hidden completions, `A` and `B`,
and let `p_A(x)` and `p_B(x)` be their surface-point distributions.  A sampler
that independently chooses the hidden mode for every point implements

\[
p_{\mathrm{ind}}(X\mid O)
=\prod_{i=1}^{N}\left[\tfrac12p_A(x_i)+\tfrac12p_B(x_i)\right].
\]

It has perfect marginal coverage of both alternatives, yet for moderate `N`
almost every finite point cloud contains points from both mutually exclusive
scenes.  A scene-level mixture instead implements

\[
p_{\mathrm{scene}}(X\mid O)
=\tfrac12\prod_{i=1}^{N}p_A(x_i)
 +\tfrac12\prod_{i=1}^{N}p_B(x_i).
\]

Both distributions can have the same one-point marginal.  Consequently,
pointwise Chamfer distance, marginal occupancy, and pooled coverage cannot
distinguish them; the experiment must inspect correlations within each sample.
This counterexample is an analytic consequence of the two factorizations.

PointFlow must not be placed on the wrong side of this contrast.  It learns a
latent distribution over shapes and a conditional point distribution, with
the joint model factorized as a shape latent followed by points conditioned on
that same latent.  Its two continuous normalizing flows model the shape-level
distribution and the point-level distribution respectively
([paper, Section 3](https://openaccess.thecvf.com/content_ICCV_2019/papers/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.pdf)).
That hierarchy creates dependence among points after marginalizing the shared
shape latent.  It does not automatically solve the present problem: the latent
must actually resolve the hidden alternatives relevant to `O`, the condition
must preserve the visible evidence, and the sampled latent must survive later
calls.  Redrawing the shape latent for each output chunk or camera would break
scene persistence even with a sound PointFlow-style model.

A deterministic global evidence encoding `h(O)` is also not `z*`.  Sharing
`h(O)` across stochastic point transports makes them respond to the same
observation, but it does not force their private noise variables to select the
same unobserved mode.  A shared random scene state, or an equivalent joint
sampling mechanism whose correlations persist across calls, is required.

## Historical pathway

### 1. Set likelihoods and hierarchical point generation

PointFlow replaced voxel-grid generation with continuous normalizing flows.
It first models a latent shape distribution, then transports samples from a
simple prior to a point distribution conditioned on a sampled shape code.  The
construction supports likelihood-based training, point-cloud generation, and
reconstruction while allowing a variable number of sampled points
([ICCV 2019 paper](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
[official repository](https://github.com/stevenygd/PointFlow)).

Diffusion Probabilistic Models for 3D Point Cloud Generation instead treats
points as particles progressively perturbed to noise and learns the reverse
Markov process conditioned on a shape latent.  The authors evaluate generation
and autoencoding and identify completion, upsampling, synthesis, and data
augmentation as applications; the representation remains a finite point cloud
rather than a continuous surface
([CVPR 2021 paper](https://openaccess.thecvf.com/content/CVPR2021/html/Luo_Diffusion_Probabilistic_Models_for_3D_Point_Cloud_Generation_CVPR_2021_paper.html),
[official code](https://github.com/luost26/diffusion-point-cloud)).
LION later combines a global shape latent and a point-structured latent in a
hierarchical VAE, then trains diffusion models in both latent spaces; smooth
meshes require a separate surface-reconstruction stage
([NeurIPS 2022 paper](https://proceedings.neurips.cc/paper_files/paper/2022/hash/40e56dabe12095a5fc44a6e4c3835948-Abstract.html),
[official project](https://nv-tlabs.github.io/LION/)).

The progression is from a likelihood over sampled point sets toward richer
latent structure.  None of “more points,” “latent diffusion,” or “smooth mesh
post-processing” alone establishes that a conditional sample corresponds to
one complete evidence-compatible scene.

### 2. Flow matching

Flow Matching trains a continuous normalizing flow by regressing a vector
field against the conditional vector fields of chosen probability paths:

\[
\mathcal L_{FM}(\theta)
=\mathbb E_{t,x_t}\left[\lVert
v_\theta(x_t,t,O)-u_t(x_t\mid O)
\rVert_2^2\right].
\]

The ICLR paper shows that this simulation-free objective supports a family of
Gaussian paths, including diffusion paths, and introduces optimal-transport
paths as an efficient alternative
([Flow Matching](https://openreview.net/forum?id=PqvMRDCJT9t)).
Flow matching specifies how to learn a transport; it does not specify what one
state represents or how variables are coupled.  A flow over individual 6D
oriented points, a flow over a global scene latent, and a flow over a joint set
of object poses are three different models even if they use the same loss.

Historical credit should remain explicit: PointFlow's continuous normalizing
flows predate the 2023 Flow Matching objective and were trained with change-of-
variables/ODE likelihood machinery.  It is inaccurate to retroactively call
PointFlow a Flow Matching method merely because both use continuous flows
([PointFlow](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
[Flow Matching](https://openreview.net/forum?id=PqvMRDCJT9t)).

### 3. Diffusing 3D representations and implicit parameters

The representation being noised matters:

- Shap-E trains an encoder that maps an asset to parameters of an implicit
  function, then trains text- and image-conditioned latent diffusion models on
  those encoded outputs.  A sampled latent is projected into one implicit
  function that can be rendered as a NeRF or converted to a textured mesh
  ([paper](https://arxiv.org/abs/2305.02463),
  [official model card](https://github.com/openai/shap-e/blob/main/model-card.md)).
- Chou, Bahat, and Heide's Diffusion-SDF represents neural signed-distance
  functions with compact modulations and diffuses those representations for
  unconditional generation, partial-shape completion, single-view
  reconstruction, and real-scan reconstruction
  ([ICCV 2023 paper](https://openaccess.thecvf.com/content/ICCV2023/html/Chou_Diffusion-SDF_Conditional_Generative_Modeling_of_Signed_Distance_Functions_ICCV_2023_paper.html),
  [official code](https://github.com/princeton-computational-imaging/Diffusion-SDF)).
- Direct3D trains a VAE for continuous triplane shape latents and a diffusion
  transformer over those latents, conditioned on image features, thereby
  making the probabilistic 3D stage explicit rather than relying on a
  multi-view image generator or score-distillation optimization
  ([NeurIPS 2024 paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/dc970c91c0a82c6e4cb3c4af7bff5388-Abstract-Conference.html)).

There are two unrelated 2023 papers titled “Diffusion-SDF.”  Chou et al.
(ICCV) diffuse compact representations of neural SDFs for conditional
reconstruction/completion; Li et al. (CVPR) use a patch SDF autoencoder and
voxelized diffusion for text-to-shape.  Citations and registry IDs must include
authors and venue rather than treating the title as unique
([Chou et al.](https://openaccess.thecvf.com/content/ICCV2023/html/Chou_Diffusion-SDF_Conditional_Generative_Modeling_of_Signed_Distance_Functions_ICCV_2023_paper.html),
[Li et al.](https://openaccess.thecvf.com/content/CVPR2023/html/Li_Diffusion-SDF_Text-To-Shape_via_Voxelized_Diffusion_CVPR_2023_paper.html)).

Sampling one implicit function is structurally closer to sampling one asset
than sampling unrelated points, because arbitrary spatial queries reuse one
parameter set.  It is still object-level unless its state includes scene
layout, identities, cameras, and relations, and it is still not posterior
sampling unless observation conditioning and mode coverage are validated.

### 4. 3D-aware and view-conditioned image generation

GRAF conditions a radiance field on shape and appearance latents and renders
it from sampled cameras, learning from unposed 2D images.  pi-GAN uses a
periodic implicit radiance field and volume rendering.  EG3D improves
efficiency and image quality with a hybrid triplane representation, volume
rendering, and a 2D super-resolution path
([GRAF](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html),
[pi-GAN](https://openaccess.thecvf.com/content/CVPR2021/html/Chan_Pi-GAN_Periodic_Implicit_Generative_Adversarial_Networks_for_3D-Aware_Image_Synthesis_CVPR_2021_paper.html),
[EG3D](https://openaccess.thecvf.com/content/CVPR2022/html/Chan_Efficient_Geometry-Aware_3D_Generative_Adversarial_Networks_CVPR_2022_paper.html)).
These models demonstrate the useful pattern “sample one latent representation,
render many cameras,” but their unconditional category-level image synthesis
objective is not the conditional scene posterior required by Module 13.

Zero-1-to-3 fine-tunes an image diffusion model to condition on one input image
and a relative camera transformation.  It samples plausible novel views and
can serve as a prior for a separate single-image 3D optimization, but the
direct model output is an image, not a persistent 3D asset
([ICCV 2023 paper](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html)).
Generative Novel View Synthesis with 3D-Aware Diffusion Models incorporates a
3D feature volume and can autoregressively generate view sequences; the paper
evaluates distributions of possible renderings rather than exporting a
canonical complete scene interface
([ICCV 2023 paper](https://openaccess.thecvf.com/content/ICCV2023/html/Chan_Generative_Novel_View_Synthesis_with_3D-Aware_Diffusion_Models_ICCV_2023_paper.html)).

This distinction matters operationally.  Sampling every requested camera from
private image noise can produce attractive frames whose hidden geometry
changes across views.  Either the image generator must preserve a shared
latent/state across the sequence, or a later optimization must distill the
images into one representation and accept that this is an additional,
typically mode-seeking inference stage.  SparseFusion explicitly describes
its diffusion-to-3D distillation as mode seeking while optimizing one
3D-consistent representation from sparse views
([CVPR 2023 paper](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_SparseFusion_Distilling_View-Conditioned_Diffusion_for_3D_Reconstruction_CVPR_2023_paper.html)).

### 5. Text-to-3D: optimization versus native sampling

DreamFusion introduced Score Distillation Sampling (SDS): render random views
of a parameterized 3D scene, perturb the images, compare the frozen text-to-
image diffusion model's predicted noise with the applied noise, and
back-propagate that difference through the renderer.  Its representation is
optimized per prompt and its image prior is frozen; the method does not train
an ancestral 3D scene sampler
([paper](https://arxiv.org/abs/2209.14988),
[official project](https://dreamfusion3d.github.io/)).
Magic3D retains score distillation but uses a coarse neural stage followed by
high-resolution textured-mesh optimization
([CVPR 2023 paper](https://openaccess.thecvf.com/content/CVPR2023/html/Lin_Magic3D_High-Resolution_Text-to-3D_Content_Creation_CVPR_2023_paper.html),
[official project](https://research.nvidia.com/labs/cosmos-lab/magic3d/)).

Shap-E represents the alternative native-sampling route: its diffusion model
directly samples a latent that decodes to one implicit 3D function
([paper](https://arxiv.org/abs/2305.02463)).  The contrast is not “old versus
new” or “low versus high quality”; it is per-instance score-guided optimization
versus an amortized learned distribution over 3D representations.  Random
initialization can make an optimizer produce varied assets, but variation
alone is not evidence that its outcomes are calibrated samples of
`p(S | text)`.

### 6. Large reconstruction models

LRM uses a transformer to map one input image and camera-ray embeddings to a
triplane NeRF representation, trained at scale on rendered 3D assets.  Its
central contribution is amortized prediction speed and cross-category
generalization, not stochastic inference
([ICLR 2024 paper](https://arxiv.org/abs/2311.04400)).
Calling every large image-to-3D network “generative” would erase the difference
between a deterministic conditional estimator and a model with an explicit
sampled variable.  Direct3D's conditional diffusion transformer is a useful
counterexample: it preserves the amortized pipeline while explicitly modeling
a distribution in 3D latent space
([NeurIPS 2024 paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/dc970c91c0a82c6e4cb3c4af7bff5388-Abstract-Conference.html)).

### 7. Object completion

PCN is the deterministic baseline: an encoder maps a partial point cloud to a
latent feature and a coarse-to-fine decoder predicts one completion under
Chamfer-style reconstruction objectives
([3DV 2018 paper](https://doi.org/10.1109/3DV.2018.00088),
[official code](https://github.com/wentaoyuan/pcn)).
That learned completion prior can hallucinate a plausible hidden side, but it
does not expose alternative completions for the same input.

DiffComplete instead casts completion of partial range scans as conditional
diffusion.  Its spatially aligned conditioning and occupancy-aware fusion
support multiple partial inputs, and the authors explicitly evaluate realism,
fidelity, and multimodality
([NeurIPS 2023 paper](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html),
[official code](https://github.com/dvlab-research/DiffComplete)).
This is closer to conditional hypothesis sampling than PCN, but it remains an
object-shape model.  Object-level plausibility does not determine scene-scale
pose, support, collision, identity, or relation consistency.

Completion benchmarks also often provide one ground-truth complete shape per
partial input.  A one-to-many posterior cannot be validated by distance to
that single target alone: best-of-`K` distance rewards sample count, mean
distance can punish valid alternatives, and pooled coverage ignores whether
one sample is coherent.  Evidence fidelity, within-sample coherence,
between-sample diversity, mode coverage, and calibration must be reported
separately.  DiffComplete's explicit realism/fidelity/multimodality framing
motivates this separation, but the two-hypothesis laboratory below makes it
directly identifiable
([paper](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html)).

### 8. Scene synthesis and conditional scene inference

DiffuScene diffuses an unordered set of object attributes containing position,
size, orientation, semantics, and shape features, then retrieves object
geometry.  Because the whole set is denoised together, the model can learn
arrangement relationships; the paper demonstrates unconditional synthesis,
partial-scene completion, rearrangement, and text-conditioned scene synthesis
on 3D-FRONT
([CVPR 2024 paper](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html)).
It is a distribution over semantic object configurations, not dense
reconstruction of arbitrary observed surfaces.

Coherent 3D Scene Diffusion conditions on a single RGB image and simultaneously
denoises the 3D poses and geometries of all detected objects.  Its scene-prior
transformer allows information exchange across objects during denoising, and a
separate conditional shape diffusion module produces object geometry
([NeurIPS 2024 paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
[official project](https://www.manuel-dahnert.com/research/scene-diffusion/)).
This is the most direct canonical precedent for the Module 13 claim that hidden
object choices and their poses should be sampled jointly rather than inferred
object by object.

MIDI extends an image-to-3D object diffusion model to multiple instances.  It
generates the instances simultaneously and adds multi-instance attention to
model spatial relationships, using partial object images plus global scene
context
([CVPR 2025 paper](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html)).
SceneMaker, published by the cutoff at CVPR 2026, instead decouples image
de-occlusion, object generation, and pose estimation; its unified pose model
uses local and global interactions across objects and predicts rotation,
translation, and scale for open-set scenes
([CVPR 2026 paper](https://openaccess.thecvf.com/content/CVPR2026/html/Shi_SceneMaker_Open-set_3D_Scene_Generation_with_Decoupled_De-occlusion_and_Pose_CVPR_2026_paper.html),
[official project](https://idea-research.github.io/SceneMaker/)).

These scene systems show two viable strategies: jointly sample the full object
set, or decouple specialized generators while adding a joint relational stage.
Neither strategy automatically supplies a reusable opaque `scene_sample_id`
for arbitrary later point/camera/time queries.  That persistence interface and
the paired-observation posterior test remain distinct acceptance requirements
for this repository.

## Failure taxonomy

1. **Evidence violation.**  A sample changes observed geometry, color, or
   camera relations to satisfy its prior.  View-conditioned diffusion and SDS
   can improve plausibility without making observed-pixel agreement automatic
   ([Zero-1-to-3](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html),
   [DreamFusion](https://arxiv.org/abs/2209.14988)).
2. **Conditional mode collapse.**  Every sample chooses the same completion.
   Reconstruction error may remain strong while posterior coverage is zero.
3. **Within-sample hybridization.**  Different points or objects independently
   choose incompatible hidden modes.  Marginal coverage can look perfect.
4. **Cross-query identity drift.**  A second point batch, denser output,
   camera, or time step redraws the hypothesis because no persistent state is
   carried across calls.
5. **View inconsistency.**  A view-conditioned image model produces plausible
   individual frames that cannot be rendered from one geometry.  SparseFusion
   addresses this by distilling a single representation, explicitly as a
   separate mode-seeking stage
   ([paper](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_SparseFusion_Distilling_View-Conditioned_Diffusion_for_3D_Reconstruction_CVPR_2023_paper.html)).
6. **Object-wise composition failure.**  Individually plausible completed
   objects intersect, float, duplicate identities, or violate room relations.
   Joint-set and multi-instance attention are designed to expose these
   dependencies
   ([DiffuScene](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html),
   [MIDI](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html)).
7. **Prior domination.**  Text/category priors replace unusual but observed
   structure with a familiar asset.  Conditional completion must measure the
   input region independently of hidden plausibility
   ([DiffComplete](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html)).
8. **Resolution-as-diversity confusion.**  Sampling more points changes Monte
   Carlo density, not the number of scene hypotheses.  A million mutually
   inconsistent points are not a more certain or more complete scene.
9. **Representation leakage.**  A method is credited with mesh, metric, or
   scene semantics that only appear after an unreported retrieval, meshing,
   optimization, or alignment stage.  LION's mesh reconstruction,
   Zero-1-to-3's downstream 3D optimization, and DiffuScene's geometry
   retrieval are explicit stages and must remain so
   ([LION](https://proceedings.neurips.cc/paper_files/paper/2022/hash/40e56dabe12095a5fc44a6e4c3835948-Abstract.html),
   [Zero-1-to-3](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html),
   [DiffuScene](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html)).

## Controlled two-hypothesis laboratory

The repository concept lab constructs two complete scenes `S_A` and `S_B`
with an identical 48-point observed occluder and one hidden object translated
left or right.  The hidden alternatives are exactly balanced and mutually
exclusive.  It compares:

- **Independent point mixture:** each point independently chooses `A` or `B`,
  then samples from that surface distribution.
- **Shared scene latent:** sample `z* in {A,B}` once, then sample every point
  from `p(x | z*, O)`.

The two samplers deliberately have the same evidence consistency and the same
one-point marginal.  They differ only in joint structure.  The lab persists
the visible predictions, hidden prototypes, point assignments, repeated-query
draws, and scene latents in `ambiguity_samples.npz`; validation recomputes the
metrics from those arrays.  This makes the lab a contract test for the required
factorization rather than a proxy benchmark for any cited model.

### Required metrics

| Metric | Definition | Failure exposed |
|---|---|---|
| Evidence consistency | Fraction of observed constraints satisfied per sample; report mean and worst sample. | Prior domination or corrupt conditioning. |
| Within-sample coherence | `max(n_A,n_B)/N` after assigning hidden points to hypotheses; `1` is coherent. | Hybrid samples. |
| Hybrid-sample fraction | Fraction with both assignments above a tolerance such as 5%. | Hides less readily than average coherence. |
| Hypothesis coverage | Fraction of valid hypotheses represented by at least one coherent sample. | Mode collapse. |
| Frequency calibration | Distance between sampled hypothesis frequency and the known balanced posterior. | Miscalibrated diversity. |
| Between-sample diversity | Diversity of the dominant hypothesis or complete-scene state, never pooled points. | Repeated copies disguised by point noise. |
| Query-batch persistence | Whether several point batches requested under one sample handle retain one hypothesis. | Redrawing `z*` between calls. |
| Resolution persistence | Whether `N={256,1024,4096,...}` changes only density while retaining the sampled hypothesis. | Conflating arbitrary resolution with new scene draws. |
| Camera persistence | Whether renders from several cameras agree with one selected hidden state. | Per-view stochastic drift. |

Report the complete distribution over seeds, not only a favourable example.
The independent sampler should attain hypothesis coverage in aggregate yet
approach a hybrid fraction of one as `N` increases.  The shared sampler should
attain coherence one for every sample while covering both modes across samples.
This expected result follows exactly from the two factorizations above and
does not depend on the quality claims of an external model.

### Failure sweep

The executable sweep varies hidden points per sample from 17 to 16,385 and
records independent-point coherence, hybrid fraction, repeated-query
consistency, shared-latent coherence, shared repeated-query consistency, and
shared-latent identity across resolutions.  Under the fixed seed, changing
resolution never redraws the shared scene latent.  Useful future extensions
are posterior imbalance (`0.5/0.5`, `0.9/0.1`), visible-evidence corruption,
and a negative control that redraws `z*` between cameras.  Keep hypothesis
coverage and coherence separate throughout—one cannot substitute for the
other.

The final smoke fixture (64 samples and 257 hidden points) measures 0.527
independent coherence, 1.0 hybrid fraction, zero coherent-scene coverage,
0.498 repeated-query consistency, and 0.853 m mean best-hypothesis RMSE.  Its
marginal mode entropy is effectively one bit despite zero coherent-scene
entropy.  The shared sampler measures 1.0 coherence, coherent coverage, and
repeat consistency with zero best-hypothesis RMSE.  Both samplers preserve all
observed points and cover both modes in aggregate.  Full uses 4,096 samples
and 4,097 hidden points and sharpens the independent coherence and repeat
consistency toward 0.5.

## Architectural implication for Surflo

A compatible transition can retain the existing observation encoder and
arbitrary-resolution oriented-point decoder while inserting an explicit
scene-posterior module:

\[
h=E(O),\qquad z^*=G_\phi(\epsilon;h),\qquad
\dot x_i=v_\theta(x_i,t;h,z^*).
\]

`G_phi` may be a conditional flow, diffusion model, discrete/continuous latent
model, or another joint sampler.  The choice of generative family is secondary
to four interface requirements:

1. `sample_scene(O, seed)` returns a persistent state or handle, not points.
2. `sample_points(scene, N, point_seed)` reuses that state; `N` controls surface
   sampling resolution only.
3. `render(scene, camera)` and any later mesh/dynamic decoder consume the same
   state.
4. Provenance records the observation hash, scene-latent seed/hash, point seed,
   decoder/checkpoint hash, and every post-processing stage separately.

PointFlow supports the first conceptual separation between shape and points;
3D-aware generators demonstrate rendering many views from one latent field;
Coherent 3D Scene Diffusion and MIDI demonstrate interactions across objects
during joint sampling
([PointFlow](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html),
[GRAF](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html),
[Coherent 3D Scene Diffusion](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
[MIDI](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html)).
The proposed interface combines those structural lessons without claiming
that one of those systems already solves Surflo's observation domain.

Training also needs scene-level supervision or a defensible latent-variable
objective.  Pairing individual target points independently cannot teach which
hidden points co-occur.  Full scenes, multiple partial observations of the same
scene, object-relation annotations, or multi-view rendering constraints can
provide joint information; otherwise the desired correlation is statistically
unidentified.  The scene-level papers obtain such structure from complete
scene configurations, scene images with object annotations, or scene-level 3D
training data rather than from isolated point marginals
([DiffuScene](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html),
[Coherent 3D Scene Diffusion](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
[MIDI](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html)).

## Recommended primary-source reading sequence

1. PointFlow for the shape-latent/point hierarchy
   ([paper](https://openaccess.thecvf.com/content_ICCV_2019/html/Yang_PointFlow_3D_Point_Cloud_Generation_With_Continuous_Normalizing_Flows_ICCV_2019_paper.html)).
2. Flow Matching for the transport objective, while keeping model state and
   factorization separate from the loss
   ([paper](https://openreview.net/forum?id=PqvMRDCJT9t)).
3. Shap-E and Diffusion-SDF for generation of persistent implicit
   representations
   ([Shap-E](https://arxiv.org/abs/2305.02463),
   [Chou et al.](https://openaccess.thecvf.com/content/ICCV2023/html/Chou_Diffusion-SDF_Conditional_Generative_Modeling_of_Signed_Distance_Functions_ICCV_2023_paper.html)).
4. GRAF or EG3D for one latent scene representation rendered from many cameras
   ([GRAF](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html),
   [EG3D](https://openaccess.thecvf.com/content/CVPR2022/html/Chan_Efficient_Geometry-Aware_3D_Generative_Adversarial_Networks_CVPR_2022_paper.html)).
5. Zero-1-to-3 and SparseFusion for the distinction between stochastic view
   synthesis and distillation into one 3D representation
   ([Zero-1-to-3](https://openaccess.thecvf.com/content/ICCV2023/html/Liu_Zero-1-to-3_Zero-shot_One_Image_to_3D_Object_ICCV_2023_paper.html),
   [SparseFusion](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_SparseFusion_Distilling_View-Conditioned_Diffusion_for_3D_Reconstruction_CVPR_2023_paper.html)).
6. DreamFusion and LRM for per-scene optimization versus amortized deterministic
   reconstruction
   ([DreamFusion](https://arxiv.org/abs/2209.14988),
   [LRM](https://arxiv.org/abs/2311.04400)).
7. DiffComplete for probabilistic object completion
   ([paper](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html)).
8. DiffuScene, Coherent 3D Scene Diffusion, MIDI, and SceneMaker for the
   progression from set-level scene synthesis to image-conditioned joint scene
   inference and open-set composition
   ([DiffuScene](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html),
   [Coherent 3D Scene Diffusion](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html),
   [MIDI](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html),
   [SceneMaker](https://openaccess.thecvf.com/content/CVPR2026/html/Shi_SceneMaker_Open-set_3D_Scene_Generation_with_Decoupled_De-occlusion_and_Pose_CVPR_2026_paper.html)).

## Source-registry metadata

The current registry already contains `yang-pointflow-2019`, `lipman-2023`,
`poole-2022`, `hong-lrm-2023`, and `liu-zero123-2023`.  Retain those IDs.  The
following primary sources are suitable additions; titles, author order, years,
and venues follow the official proceedings or first-party release pages.

| Proposed ID | Title; authors | Year / venue | Primary URL | Registry claim |
|---|---|---|---|---|
| `luo-point-diffusion-2021` | **Diffusion Probabilistic Models for 3D Point Cloud Generation**; Shitong Luo, Wei Hu | 2021 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2021/html/Luo_Diffusion_Probabilistic_Models_for_3D_Point_Cloud_Generation_CVPR_2021_paper.html) | A reverse diffusion process conditioned on a shape latent generates finite point clouds. |
| `zeng-lion-2022` | **LION: Latent Point Diffusion Models for 3D Shape Generation**; Xiaohui Zeng, Arash Vahdat, Francis Williams, Zan Gojcic, Or Litany, Sanja Fidler, Karsten Kreis | 2022 / NeurIPS | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2022/hash/40e56dabe12095a5fc44a6e4c3835948-Abstract.html) | Hierarchical diffusion over global and point-structured latents improves point-shape generation; surface reconstruction remains a separate stage. |
| `jun-shap-e-2023` | **Shap-E: Generating Conditional 3D Implicit Functions**; Heewoo Jun, Alex Nichol | 2023 / arXiv and official release | [arXiv](https://arxiv.org/abs/2305.02463) | Conditional latent diffusion generates parameters of implicit functions renderable as NeRFs or textured meshes. |
| `chou-diffusion-sdf-2023` | **Diffusion-SDF: Conditional Generative Modeling of Signed Distance Functions**; Gene Chou, Yuval Bahat, Felix Heide | 2023 / ICCV | [CVF](https://openaccess.thecvf.com/content/ICCV2023/html/Chou_Diffusion-SDF_Conditional_Generative_Modeling_of_Signed_Distance_Functions_ICCV_2023_paper.html) | Diffusion over compact neural-SDF representations supports conditional 3D reconstruction and completion. |
| `schwarz-graf-2020` | **GRAF: Generative Radiance Fields for 3D-Aware Image Synthesis**; Katja Schwarz, Yiyi Liao, Michael Niemeyer, Andreas Geiger | 2020 / NeurIPS | [NeurIPS](https://proceedings.neurips.cc/paper/2020/hash/e92e1b476bb5262d793fd40931e0ed53-Abstract.html) | Shape and appearance latents condition a radiance field rendered under explicit camera control. |
| `chan-pigan-2021` | **pi-GAN: Periodic Implicit Generative Adversarial Networks for 3D-Aware Image Synthesis**; Eric R. Chan, Marco Monteiro, Petr Kellnhofer, Jiajun Wu, Gordon Wetzstein | 2021 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2021/html/Chan_Pi-GAN_Periodic_Implicit_Generative_Adversarial_Networks_for_3D-Aware_Image_Synthesis_CVPR_2021_paper.html) | A periodic implicit radiance field and volume rendering support 3D-aware category-level image synthesis. |
| `chan-eg3d-2022` | **Efficient Geometry-aware 3D Generative Adversarial Networks**; Eric R. Chan, Connor Z. Lin, Matthew A. Chan, Koki Nagano, Boxiao Pan, Shalini De Mello, Orazio Gallo, Leonidas Guibas, Jonathan Tremblay, Sameh Khamis, Tero Karras, Gordon Wetzstein | 2022 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2022/html/Chan_Efficient_Geometry-Aware_3D_Generative_Adversarial_Networks_CVPR_2022_paper.html) | A hybrid triplane renderer improves efficient multi-view-consistent 3D-aware synthesis from 2D collections. |
| `chan-3dim-2023` | **Generative Novel View Synthesis with 3D-Aware Diffusion Models**; Eric R. Chan, Koki Nagano, Matthew A. Chan, Alexander W. Bergman, Jeong Joon Park, Axel Levy, Miika Aittala, Shalini De Mello, Tero Karras, Gordon Wetzstein | 2023 / ICCV | [CVF](https://openaccess.thecvf.com/content/ICCV2023/html/Chan_Generative_Novel_View_Synthesis_with_3D-Aware_Diffusion_Models_ICCV_2023_paper.html) | A 3D feature volume conditions diffusion over plausible novel views and autoregressive view sequences. |
| `zhou-sparsefusion-2023` | **SparseFusion: Distilling View-Conditioned Diffusion for 3D Reconstruction**; Zhizhuo Zhou, Shubham Tulsiani | 2023 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_SparseFusion_Distilling_View-Conditioned_Diffusion_for_3D_Reconstruction_CVPR_2023_paper.html) | View-conditioned image diffusion can be distilled through mode-seeking optimization into one 3D-consistent representation. |
| `lin-magic3d-2023` | **Magic3D: High-Resolution Text-to-3D Content Creation**; Chen-Hsuan Lin, Jun Gao, Luming Tang, Towaki Takikawa, Xiaohui Zeng, Xun Huang, Karsten Kreis, Sanja Fidler, Ming-Yu Liu, Tsung-Yi Lin | 2023 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2023/html/Lin_Magic3D_High-Resolution_Text-to-3D_Content_Creation_CVPR_2023_paper.html) | Coarse neural and fine textured-mesh stages optimize a 3D asset through 2D diffusion guidance. |
| `wu-direct3d-2024` | **Direct3D: Scalable Image-to-3D Generation via 3D Latent Diffusion Transformer**; Shuang Wu, Youtian Lin, Feihu Zhang, Yifei Zeng, Jingxi Xu, Philip Torr, Xun Cao, Yao Yao | 2024 / NeurIPS | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2024/hash/dc970c91c0a82c6e4cb3c4af7bff5388-Abstract-Conference.html) | Image-conditioned diffusion directly models compact triplane 3D latents rather than relying on score distillation or generated views. |
| `chu-diffcomplete-2023` | **DiffComplete: Diffusion-based Generative 3D Shape Completion**; Ruihang Chu, Enze Xie, Shentong Mo, Zhenguo Li, Matthias Nießner, Chi-Wing Fu, Jiaya Jia | 2023 / NeurIPS | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/ef7bd1f9cbf8a5ab7ddcaccd50699c90-Abstract.html) | Conditional 3D diffusion makes object completion multimodal while spatial conditioning preserves partial range evidence. |
| `tang-diffuscene-2024` | **DiffuScene: Denoising Diffusion Models for Generative Indoor Scene Synthesis**; Jiapeng Tang, Yinyu Nie, Lev Markhasin, Angela Dai, Justus Thies, Matthias Nießner | 2024 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2024/html/Tang_DiffuScene_Denoising_Diffusion_Models_for_Generative_Indoor_Scene_Synthesis_CVPR_2024_paper.html) | Joint diffusion over unordered object attributes supports scene synthesis, arrangement, completion, and text conditioning. |
| `dahnert-scene-diffusion-2024` | **Coherent 3D Scene Diffusion From a Single RGB Image**; Manuel Dahnert, Angela Dai, Norman Müller, Matthias Nießner | 2024 / NeurIPS | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2024/hash/29c8c615b3187ee995029284702d3f43-Abstract-Conference.html) | Image-conditioned joint denoising of object poses and shapes models scene context and inter-object relationships. |
| `huang-midi-2025` | **MIDI: Multi-Instance Diffusion for Single Image to 3D Scene Generation**; Zehuan Huang, Yuan-Chen Guo, Xingqiao An, Yunhan Yang, Yangguang Li, Zi-Xin Zou, Ding Liang, Xihui Liu, Yan-Pei Cao, Lu Sheng | 2025 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2025/html/Huang_MIDI_Multi-Instance_Diffusion_for_Single_Image_to_3D_Scene_Generation_CVPR_2025_paper.html) | Multi-instance diffusion and cross-instance attention jointly generate object geometry and spatial relationships from one scene image. |
| `shi-scenemaker-2026` | **SceneMaker: Open-set 3D Scene Generation with Decoupled De-occlusion and Pose Estimation Model**; Yukai Shi, Weiyu Li, Zihao Wang, Hongyang Li, Xingyu Chen, Ping Tan, Lei Zhang | 2026 / CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2026/html/Shi_SceneMaker_Open-set_3D_Scene_Generation_with_Decoupled_De-occlusion_and_Pose_CVPR_2026_paper.html) | Decoupled de-occlusion/object generation plus a relational pose diffusion model extends single-image scene generation to open-set objects. |

If the registry remains deliberately compact, the minimum additions needed to
make Module 13 theme-complete are `jun-shap-e-2023`,
`chu-diffcomplete-2023`, `tang-diffuscene-2024`,
`dahnert-scene-diffusion-2024`, and `shi-scenemaker-2026`.  The others support
the explicit terminology and historical branches and are appropriate when the
survey text retains those claims.

## Acceptance statement for Module 13

The concept lab may pass without training a large external generator.  It must
demonstrate, deterministically and from emitted artifacts, that equal marginal
coverage can coexist with failed within-sample coherence, and that one retained
scene latent fixes the failure across point counts and query batches.  It must
not claim that the toy sampler reproduces PointFlow, a diffusion model, or a
published scene generator.  The scientific result is the factorization test.

A future maintained reference should be selected only after its source,
checkpoint, data licence, output semantics, latent lifetime, and offline B200
path are pinned.  Its acceptance criteria must separately test evidence
consistency, coherent mode choice, coverage/calibration, and cross-query
persistence.  Chamfer distance, F-score, PSNR, or a diverse gallery alone are
insufficient for the module's central claim.
