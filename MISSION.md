**Yes. I would make synthetic 3D—and eventually 4D—scenes a major source of pretraining supervision, and use grounded language supervision as an auxiliary objective. But I would change the learning problem, not merely add rendered images to Surflo’s existing training set.**

For our target, the objective should become:

> **Infer a persistent, generative scene representation from incomplete observations; query it geometrically; render it from new cameras; and update or evolve it consistently over time.**

Synthetic scenes are valuable because they let us control **what exists, what was observed, what remains hidden, and what changes**. Language can teach the representation which objects, relationships, and interventions matter. Real imagery and video remain important for transferring those capabilities to real appearance and motion.

There is supporting precedent: Hypersim provides complete synthetic scene geometry and rich rendering annotations; Depth Anything V2 demonstrates a synthetic-supervision-to-real-imagery training bridge; SpatialVLM and SpatialRGPT demonstrate benefits from geometry-grounded language supervision. None of those, individually, establishes that the combined recipe below will improve video generation—that is the experiment we need to run. :chatgpt-content-reference{index="0"}

## 1. First, distinguish the capabilities we want to pretrain

“Geometry extrapolation” contains several different problems.

| Target capability | What the model must learn | Appropriate training episode |
|---|---|---|
| **Novel-view reconstruction** | Recover observed geometry and render it from another camera | Overlapping context and target views |
| **Disocclusion and scene completion** | Infer plausible surfaces or objects never seen in the context | Restricted context; targets reveal hidden regions |
| **Compositional generalization** | Handle unfamiliar object arrangements, structures, and environments | Hold out assets, layouts, or relation combinations |
| **Dynamic video generation** | Preserve identity and geometry while objects, cameras, and lighting evolve | Temporal sequences with independently controlled camera and scene motion |

A model can succeed at the first while remaining weak at the other three. In particular, randomly selecting context and target frames from a dense orbit can make an apparent “extrapolation” task mostly reconstruction from overlapping evidence.

### The most important Surflo-specific change: scene-level uncertainty

Surflo conditions independent point trajectories on a shared encoded state. The paper itself notes that independent decoding can produce inconsistencies in ambiguous, occluded regions; its rendering guidance couples points through agreement with the observed images. :chatgpt-content-reference{index="1"}

For completion, there are **two distinct kinds of randomness**:

**Surface-sampling randomness:** Where should the next point lie on a particular scene?

**Scene-hypothesis randomness:** Which plausible scene exists behind the occluder?

We should not expect the first to substitute for the second.

Suppose the unseen portion of a room could contain either a sofa or a bookshelf. Independently sampling points from a distribution that mixes both possibilities risks producing a hybrid scene. Instead, we want to sample **one coherent hypothesis**, then sample its surface:

\[
h\sim p_\psi(h\mid O,\ell),
\qquad
x_i\sim p_\theta(x_i\mid h,O),
\]

where \(O\) is the observed imagery and \(\ell\) is optional language conditioning. The resulting distribution is

\[
p(X\mid O,\ell)
=
\int p_\psi(h\mid O,\ell)
\prod_i p_\theta(x_i\mid h,O)\,dh.
\]

All points—and all subsequently rendered camera views—share the same \(h\).

This is not a new probabilistic principle: PointFlow explicitly separates a distribution over shapes from a distribution over points conditioned on a shape. I would adapt that distinction to **partial-observation-conditioned scene completion**, retaining Surflo’s scalable point decoder where useful. :chatgpt-content-reference{index="2"}

**The pretraining target should therefore be a distribution over coherent scene completions, not only a better conditional surface-point distribution.**

---

## 2. Build synthetic *scene episodes*, not just RGB–depth pairs

I would define each synthetic example around an underlying scene state:

\[
S_\tau=
\left(
G_\tau,\ M,\ L_\tau,\ \mathcal O,\ A_{0:\tau}
\right),
\]

with geometry \(G\), materials \(M\), illumination \(L\), object identities and relations \(\mathcal O\), and optional actions or animation controls \(A\). Here, \(\tau\) is **physical time**, not diffusion or flow time.

A camera \(C_\tau\) produces observations:

\[
I_\tau=R(S_\tau,C_\tau).
\]

The training record should retain both the observation and the underlying state needed to generate additional supervision.

### What I would record

| Supervision | What to retain | Why it matters |
|---|---|---|
| **Geometry** | Meshes or procedural geometry, oriented surface samples, appropriate occupancy/distance queries | Train explicit shape and surface understanding |
| **Cameras** | Intrinsics, poses, distortion, coordinate conventions, units | Separate camera motion from scene structure |
| **Visibility** | Context-visible surfaces, target-visible surfaces, occlusion/disocclusion masks | Distinguish reconstruction from completion |
| **Appearance** | RGB, materials, diffuse albedo, geometric and shading normals, lighting metadata | Avoid encoding illumination as geometry |
| **Correspondence and dynamics** | Persistent object/surface IDs, trajectories, deformation or joint states, optical/scene flow | Train identity preservation and motion understanding |
| **Semantics** | Object labels, scene graphs, verified spatial relations and intervention descriptions | Ground language in the same scene state |

Not every renderer supplies all these fields automatically. Some require custom passes or instrumentation.

Also, “ground truth” means **correct for the simulated scene and the chosen annotation definition**. It does not mean the assets have realistic physics, the scene distribution matches reality, or every rendering convention is unambiguous.

For example, I would explicitly distinguish camera-axis depth from ray distance, geometric normals from material-induced shading normals, and first-surface depth from transparency-aware observations. I would not generate signed-distance labels indiscriminately from open or non-manifold meshes.

### A practical source/tool combination

I would combine several sources rather than betting everything on one procedural generator.

| Source or tool | Role I would assign it |
|---|---|
| **Infinigen / Infinigen Indoors** | Procedural variation in geometry, layout, materials, and difficult structures |
| **BlenderProc** | Controlled camera sampling, rendering, imported assets, and annotation production |
| **Kubric** | Dynamic scenes, object interaction, and correspondence-oriented episodes |
| **Artist-authored scenes such as Hypersim’s source distribution** | High-quality composed environments and appearance diversity |

Infinigen exposes geometry and annotations including depth, normals, flow, and occlusion boundaries. BlenderProc supports camera sampling and RGB/depth/normal/segmentation rendering. Kubric couples Blender and physics simulation for richly annotated synthetic datasets. Hypersim supplies complete scene, camera, material, and lighting information. :chatgpt-content-reference{index="3"}

### “Complex” should mean informative, not merely cluttered

My sampling axes would include occlusion, thin structures, repeated patterns, concavities, connected rooms, transparent or reflective materials, articulated objects, and unusual—but valid—spatial arrangements.

The key is **variation in latent causes**. Rendering 500 camera views of one kitchen creates many observations but still only one underlying kitchen configuration.

I would retain procedural seeds and scene programs, sample surface queries during training where economical, and reuse each scene for multiple carefully chosen observation/target episodes. Expensive photorealistic rendering should be allocated to episodes that add meaningful coverage, not simply to more nearby frames.

---

## 3. Sampling policy is central to extrapolation

This is where I would spend substantial effort. A huge synthetic dataset with the wrong context/target distribution could improve ordinary reconstruction without materially improving extrapolation.

### A. Sample contexts and targets jointly

Instead of independently drawing random cameras, sample a **task episode**:

\[
(S,\ C_{\mathrm{context}},\ C_{\mathrm{target}},\ m),
\]

where \(m\) identifies the intended task.

For one kitchen scene, episodes might include a nearby held-out view, movement behind an island, viewing the back of a chair, entering an adjacent room, and leaving then returning to the starting location.

I would quantify difficulty using the **fraction of target-visible geometry that was not visible in any context image**, rather than camera displacement alone:

\[
\rho_{\mathrm{new}}
=
\frac{
\text{target pixels whose surface points were unobserved in context}
}{
\text{valid target pixels}
}.
\]

A large translation can still view the same wall; rotating in place can reveal an entirely unseen room region. Visibility-based difficulty describes the learning problem more directly.

Train across low, moderate, and severe disocclusion, and report each separately.

### B. Deliberately generate ambiguous examples

An especially useful synthetic capability is creating scenes that have **the same observable front region but different hidden configurations**.

For example, render an identical doorway view while varying furniture behind an occluding wall. Ensure that shadows, reflections, or other visible cues do not accidentally reveal the hidden configuration when testing true ambiguity.

These episodes teach the difference between:

> “The observations establish this geometry.”

and

> “This is one plausible completion.”

They also expose a deterministic-completion model’s tendency to commit to an average or dominant training layout.

### C. Separate surface sampling from volumetric supervision

For Surflo-style surface training, I would mix area-uniform samples with additional emphasis on thin structures, boundaries, small objects, and context-unobserved surfaces.

But free-space and near-surface volumetric queries belong to **separate occupancy or distance objectives**, not the surface-target distribution.

That distinction matters. If we oversample chair legs heavily, the learned point density changes. Either that is intentional, or we need weighting/separate objectives to preserve the desired surface-sampling measure.

Free-space supervision is particularly useful as a constraint: generated geometry should not appear along rays known to have passed unobstructed through the scene.

### D. Decouple cameras from physical dynamics

For video pretraining, render the **same physical event from multiple camera trajectories**. Also render camera-only motion through a static scene.

Otherwise, the training distribution may fail to distinguish an object moving from the camera moving around it.

Synthetic episodes should include objects disappearing behind occluders and reappearing, articulated motion, and repeated observations after long gaps. Kubric offers a starting point for dynamic synthetic data; D4RT is a relevant reconstruction reference because it jointly targets depth, spatiotemporal correspondence, and cameras—not just independent frame geometry. :chatgpt-content-reference{index="4"}

---

## 4. Change the representation and objectives together

I would not start by forcing every capability into Surflo’s existing fixed latent and hoping additional losses are sufficient.

### A. Use a geometry-grounded state with appearance and dynamic capacity

My initial architecture would have:

```text
Partial images/video + optional cameras + optional text
                           │
                           ▼
                 Observation encoder
                           │
                           ▼
              Conditional scene-state model
              ├── coarse layout / global state
              ├── spatially indexed local detail
              ├── appearance information
              └── object state / dynamics
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
       Geometry queries   RGB/video    Grounded language
       and rendering      generation   and relation queries
```

This is a proposed factorization, not a claim that the factors will disentangle automatically.

I would compare a single global-token representation against global-plus-local tokens at matched capacity and compute. Increasing output-point count is not equivalent to increasing the information capacity of the scene representation.

The relevant architectural comparison is **3DRAE/3DDiT**: it learns a 3D-grounded latent, models a generative distribution in that latent space, and decodes images and pointmaps for camera trajectories. That is closer to our desired training problem than surface reconstruction alone. :chatgpt-content-reference{index="5"}

### B. Learn a complete-scene representation, then a conditional prior

One practical training arrangement would be:

**Complete-state representation training.** Encode complete synthetic geometry and sufficiently rich views into a latent \(z^\star\); train geometry and rendering decoders to recover the scene.

**Partial-observation prior training.** Given restricted observations, learn

\[
p_\psi(z^\star\mid O,\ell)
\]

using latent diffusion or flow matching.

**Joint refinement.** Gradually allow reconstruction, rendering, and language objectives to shape the shared representation.

The complete scene is a **training target**, not an undeclared input to the partial-observation model. Full-scene metadata, hidden object IDs, or target-only captions must not leak into its conditioning.

At generation time, sample one scene state and reuse it across cameras. When new *real observations* arrive, update the hypothesis while preserving already established evidence.

### C. Include target-view appearance during pretraining

Geometry supervision alone does not tell the representation how much appearance information the video model needs.

I would include both an explicit geometric path and an appearance-generation path:

\[
\hat B_\tau
=
R_{\mathrm{geom}}(z,C_\tau),
\qquad
I_{1:T}
\sim
p_\theta(I_{1:T}\mid z,C_{1:T},\ell).
\]

Here, \(\hat B\) contains depth, normals, and visibility controls. The video model could consume those controls, scene tokens, or both.

The important test is whether geometry actually constrains generation. A geometry auxiliary head can improve while the RGB generator learns to ignore the shared state.

My initial preference is to retain explicit rendered controls as an inspectable interface, then test whether direct latent conditioning adds value.

### D. Train with the inputs we will actually have

Perfect synthetic cameras and depth are excellent targets, but potentially misleading conditioning.

I would train distinct, explicitly identified modes: known cameras, estimated cameras, noisy cameras, and no provided cameras. Similarly, the video model should see predicted/degraded geometry controls as well as clean ground-truth controls.

For a Surflo-based implementation, there is a concrete engineering consequence: the current training path uses cached features from frozen VGGT. Improving the backbone itself requires a different gradient path; simply adding labels to the cached dataset cannot accomplish that.

Also, metric supervision does not remove monocular scale ambiguity. Scaling the scene and camera translations together can preserve the image projection. We should separate calibrated metric tasks from tasks where scale is inferred from a prior or remains unidentifiable.

---

## 5. Yes to language co-training—but make it grounded and causally useful

I see three useful roles for a language model, with different risks.

### Role 1: Express simulator-verified facts and tasks

The simulator should determine geometric truth. The language model can turn that truth into varied questions, descriptions, or instructions:

```text
Scene geometry + camera + visibility
                 │
                 ▼
       Deterministic geometric queries
                 │
                 ▼
      Verified relations / measurements
                 │
                 ▼
      Language realization and paraphrase
```

Examples include relative position in a specified camera frame, object ordering by distance, support relations, visible object counts, and descriptions of a camera move or object intervention.

SpatialVLM demonstrates scalable spatial-question supervision derived by lifting imagery into 3D; SpatialRGPT uses 3D scene graphs and depth-aware features for grounded spatial reasoning. A synthetic scene engine gives us an opportunity to obtain cleaner geometric targets than an image-derived labeling pipeline—within the simulator’s definitions. :chatgpt-content-reference{index="7"}

**I would not use an LLM’s guessed depth, pose, or distance as ground truth when the renderer already provides it.**

For left/right, front/behind, clearance, or containment, define the coordinate frame and computational predicate. Otherwise, apparently correct language can supervise contradictory concepts.

### Role 2: Make language losses supervise the scene state

The language head should answer from the same state used by geometry and generation:

\[
\mathcal L_{\mathrm{lang}}
=
-\log p_\eta
\left(
a_{\mathrm{verified}}
\mid q,\ A(z)
\right),
\]

where \(A\) is an adapter from scene state to the language model.

This creates a gradient path that can encourage the scene representation to retain object identity and relations. A separate captioner operating on source images would not necessarily improve the scene state at all.

I would initially keep the language backbone frozen, train the adapter, then selectively allow gradients into semantic/global scene components. Fine geometric detail should not be forced through a purely semantic bottleneck.

A critical control is **caption-only co-training versus grounded relational co-training**. “A kitchen with chairs” can remain true despite a badly reconstructed layout; a verified question about which chair is behind the island cannot.

### Partial-view language must respect observability

This is an easy place to accidentally train false certainty.

A simulator knows how many chairs are behind a wall. A model receiving only a doorway image may not.

For partial-view QA, I would distinguish observable answers, uncertain inferences, and genuinely unanswerable questions. Full-state queries can receive exact answers when the model actually has full-state input.

The goal is not to teach the model to confidently repeat privileged labels unavailable from its observations.

### Role 3: Propose scenes, counterfactuals, and curricula

An LLM can propose structured scene programs:

> Create a room with two visually similar chairs, only one of which is initially visible. Reveal the second during a camera turn.

Or counterfactual edits:

> Keep geometry fixed and change materials.

> Keep the camera path fixed and change which object moves.

> Exchange two objects while preserving lighting.

I would translate proposals into a constrained scene specification, then validate geometry, visibility, and intended task properties programmatically. The language model proposes; execution and measurement establish what actually happened.

This is potentially more valuable than generating elaborate textual explanations: it expands the distribution of controlled experiments.

For reward signals, I would use language models primarily for semantic or instruction-following judgments. Geometry, camera adherence, collision constraints, and visibility should use explicit measurements wherever possible. The same model should not be the sole generator of training labels and the sole judge of whether they were learned.

---

## 6. Use a staged hybrid training recipe

I would not train everything jointly from random initialization. Starting from existing visual/video representations, I would use staged training followed by mixed-task co-training.

### Stage A: Establish geometric competence

Train the scene representation and geometric decoders on synthetic scenes plus available real multiview data.

Start with reliable overlap and controlled cameras, then increase viewpoint difficulty and introduce estimated/noisy cameras. Include surface, depth, normal, visibility, free-space, and correspondence supervision where valid.

This stage establishes a measurable geometric baseline before introducing generative ambiguity.

### Stage B: Train partial-to-complete scene generation

Introduce restricted contexts and target regions with substantial unseen content.

Train the scene-level conditional prior, not only the per-point decoder. Use multiple observation subsets per scene and deliberately ambiguous scene families.

Keep observed-region reconstruction stringent while learning a distribution over hidden-region completions.

### Stage C: Connect the state to image/video generation

Attach a pretrained image/video generator through rendered controls and/or latent adapters. Initially limit changes to the generative backbone; then unfreeze selected components only when the conditioning path is demonstrably useful.

Train target views and trajectories, not just source-view reconstruction.

Do not apply indiscriminate RGB warping losses across specular surfaces or changing illumination. Geometric correspondence and identity consistency are different requirements from identical pixel colors. Hypersim’s separation of reflectance, illumination, and non-diffuse effects is useful precedent for maintaining this distinction. :chatgpt-content-reference{index="8"}

### Stage D: Mix real-video adaptation, grounded language, and dynamics

Synthetic data supplies controlled supervision. Real footage tests whether the representation handles real materials, sensors, motion, and scene distributions.

A useful bridge is the pattern demonstrated by Depth Anything V2: train with strong synthetic labels, generate labels on real imagery, and transfer through real-image training. Its results support investigating that strategy, not assuming that the same mixture will be optimal for our larger joint model. :chatgpt-content-reference{index="9"}

For real data, I would retain pseudo-label confidence, mask unreliable geometry, and avoid treating reconstructed meshes as complete truth about unseen regions.

A schematic joint objective is

\[
\mathcal L
=
\lambda_g\mathcal L_{\mathrm{geometry}}
+
\lambda_s\mathcal L_{\mathrm{scene\ prior}}
+
\lambda_v\mathcal L_{\mathrm{video}}
+
\lambda_c\mathcal L_{\mathrm{correspondence}}
+
\lambda_l\mathcal L_{\mathrm{grounded\ language}}.
\]

Not every example supports every term. Losses should be normalized over valid supervision and routed by task.

I would monitor gradient interactions and actual downstream trade-offs rather than assume a fixed weighted sum produces beneficial transfer. There is no evidence here for a universally correct synthetic/real ratio or language-loss weight.

---

## 7. The ablations should test *why* this helps

Before scaling the rendering pipeline, I would run a controlled progression.

| Experiment | Change | Main question |
|---|---|---|
| **A** | Continued training on the existing real-data recipe | What does additional training compute alone buy? |
| **B** | Add synthetic scenes, retaining reconstruction objectives | Does clean geometry supervision transfer? |
| **C** | Add visibility-aware completion episodes and a scene-level prior | Does it improve genuinely unseen regions? |
| **D** | Add target-view/video generation objectives | Does geometric improvement translate into better generation? |
| **E** | Add generic captions to D | Is ordinary semantic supervision sufficient? |
| **F** | Add verified spatial language instead of generic captions | Does grounded co-training add more value? |

Then ablate whether language gradients reach the shared state, and whether video generation uses explicit controls, scene tokens, or both.

Comparisons should track training FLOPs, unique scene count, rendered-frame count, and target-task exposure. Otherwise, a “language benefit” may simply be additional compute, or a “synthetic benefit” may be extra scene diversity.

### Evaluate the intended extrapolation, not only reconstruction

**Geometry:** Report observed versus unobserved surface quality separately, stratified by disocclusion. Include free-space violations and small/thin structures, not just an aggregate surface distance.

**Uncertainty:** Compare several sampled scene hypotheses for consistency, diversity, and coverage. Report ordinary sample quality alongside best-of-\(K\); best-of-\(K\) alone can hide poor distributions.

**Video:** Test camera adherence, persistent layout, identity after occlusion, and revisiting previous locations. Use one consistent alignment for a sequence; independent per-frame alignment can conceal drift.

**Language:** Use changed-camera and counterfactual-object tests. A relation answer should change when the relevant geometry changes, and remain stable when irrelevant texture changes.

**Generalization:** Split by underlying scene, asset family, layout template, and procedural family—not merely by rendered frames. Include real held-out captures evaluated independently of the models that supplied training pseudo-labels.

For completely unseen regions or unconstrained future motion, a single observed target is only one possible valid outcome. Evaluation must distinguish **fidelity to known evidence** from **plausibility and consistency of a sampled completion**.

### The first end-to-end benchmark I would prioritize

Use a small number of input views of a furnished environment. Request a camera trajectory that moves behind a major occluder, reveals new geometry, leaves the area, and returns.

That one protocol tests nearly everything we care about: geometry completion, camera control, consistent appearance, persistent scene hypotheses, and memory across views.

Repeat it with controlled object motion only after the static version works.

---

## My recommendation

**Build a hybrid geometry-and-generation pretraining system, rather than a larger surface-only Surflo dataset.**

The highest-priority changes are:

1. **Visibility-aware synthetic episodes** that explicitly train disocclusion and completion.
2. **A shared stochastic scene hypothesis**, separate from point-sampling noise.
3. **Target-view image/video objectives** attached to the geometric representation.
4. **Simulator-grounded language co-training**, with uncertainty-aware labels and a real gradient path into the shared state.

The conceptual division is:

> **Synthetic scenes provide controlled geometric and causal supervision. Real imagery/video provides real-world appearance and behavioral coverage. Language provides semantic structure and intent. The shared scene representation must make those signals useful to the same generator.**

That is the direction I would pursue. The decisive result would not be a cleaner reconstructed mesh or better spatial QA in isolation—it would be **more reliable geometric extrapolation and more consistent generated video at matched training and inference cost**.

---

## Phase A implementation: photorealistic paired static scenes

The first static milestone is now implemented as a reproducible paired-scene
benchmark in [experiments/photoreal-scenes](experiments/photoreal-scenes/README.md).
It measures whether stock Surflo expresses a coherent hidden completion when two
different complete scenes produce the same partial observation.

### Renderer and isolation

The renderer is a repository-owned `bpy` generator running under Cycles in a
dedicated Blender Insula. Blender 4.5.14 LTS is pinned to the official Linux
archive and SHA-256. The existing Surflo Insula remains separate. Asset fetching,
scene generation, rendering, annotation extraction, validation, tests, and
inference all run inside one of those Insulas; host scripts only build root
filesystems, establish mounts, and dispatch commands.

The benchmark profile is fixed at 512×384, 256 samples, AgX, fixed seeds, and
OptiX on an NVIDIA GPU. CPU is allowed only when explicitly selected for the
small draft profile. A cold Insula build requires network access; after build,
fetching is the only networked benchmark-execution stage. Recorded rendering and
inference run offline and never fall back to another device. Exact CC0 asset
files and hashes are recorded in
[assets.lock.json](experiments/photoreal-scenes/assets.lock.json).

### Episode contract

The scene family is a metric L-shaped furnished room with an opaque
floor-to-ceiling partition. Sixteen shared context views are rendered once with
no privileged hidden geometry and hard-linked into both hypotheses. Eight target
views reveal `Sofa_01` in hypothesis A or `Shelf_01` in hypothesis B. Common
furniture, architecture, materials, lighting, and all camera parameters are held
fixed.

Episode schema v2 retains all v1 fields needed by the stock Surflo probe. Per-view
supervision includes sRGB PNG, linear multilayer OpenEXR, camera-axis depth, ray
distance, geometric and shading normals in world space, stable object IDs,
diffuse albedo, validity, intrinsics, and OpenCV world-to-camera extrinsics. Each
hypothesis adds evaluated triangulated geometry, a provenance-bearing object
table, and 250,000 stratified surface samples with common/hidden roles and
context/target/target-only visibility.

The executable contract is [recipe.json](experiments/photoreal-scenes/recipe.json),
the checkpoint/VGGT pins are centralized in
[model.lock.json](experiments/photoreal-scenes/model.lock.json),
and the compact measured outcome is
[results.json](experiments/photoreal-scenes/results.json). Reviewable render
evidence is tracked as the [shared context](experiments/photoreal-scenes/evidence/shared_context.png),
[sofa targets](experiments/photoreal-scenes/evidence/scene_a_target.png), and
[shelf targets](experiments/photoreal-scenes/evidence/scene_b_target.png).

### Commands

```bash
experiments/photoreal-scenes/run.sh build
experiments/photoreal-scenes/run.sh fetch
experiments/photoreal-scenes/run.sh render --run-id phase-a-v1
experiments/photoreal-scenes/run.sh validate --run-id phase-a-v1
experiments/photoreal-scenes/run.sh probe --run-id phase-a-v1 \
  --update-tracked-results

# Equivalent full recipe:
experiments/photoreal-scenes/run.sh all --run-id phase-a-v1
```

Runs are staged and validated before atomic promotion. Completed run IDs are not
overwritten unless `--overwrite` is supplied.

### Acceptance and observed result

Acceptance requires byte-identical contexts, no hidden ID or hidden-surface
visibility in context, different target RGB, more than 25% hidden target and
target-only visibility for both hypotheses, valid geometry/annotations, accurate
camera conversion, and an OptiX B200 render at the recorded benchmark settings.
It also requires Surflo seeds 0–3 to finish at 100,000 queries and 100 ODE steps
with recall, hidden support, completion precision, camera error, label, runtime,
VRAM, and artifact hashes captured. It does not require a favorable coherence
classification.

The recorded episode passed every renderer invariant. Stock Surflo classified all
four seeds as `unsupported`, with mean observed-common recall 0.7657,
unobserved-common recall 0.0564, and no hidden-hypothesis support.
That differs from the tracked analytic ambiguity baseline, which produces at
least one hybrid completion, and is retained as a diagnostic finding rather than
being hidden by an outcome gate.

### Phase boundary

This milestone does **not** implement scene-prior training, language supervision,
video generation, or 4D dynamics. It also excludes dynamic objects,
transparency/refraction, and motion blur. Its purpose is to establish a strict,
auditable static benchmark before any of those capabilities are introduced.
