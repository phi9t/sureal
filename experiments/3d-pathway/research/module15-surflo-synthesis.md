# Module 15 research note: Surflo and the persistent-state boundary

Cutoff: 2026-09-25. This note distinguishes claims made by the Surflo method,
properties visible in the repository implementation, measurements already
tracked by this repository, and the proposed research transition. It does not
treat the pathway wrapper as a new Surflo evaluation.

## Primary-source sequence

1. [VGGT](https://arxiv.org/abs/2503.11651) supplies the feed-forward visual
   geometry backbone: camera, depth, pointmap, and track evidence from one or
   more views.
2. [Flow Matching for Generative
   Modeling](https://openreview.net/forum?id=PqvMRDCJT9t) defines the
   simulation-free conditional vector-field objective used to learn a
   continuous transport.
3. [Surflo](https://arxiv.org/abs/2606.13644) combines a frozen VGGT encoder,
   a fixed-size Perceiver state, and a conditional flow over oriented surface
   points, with optional rendering guidance and mesh extraction.

The repository implementation exposes the same boundary directly:

- [`surflo/model/ffm.py`](../../../surflo/model/ffm.py) freezes VGGT, samples
  the point-source distribution, solves the flow, and converts the transported
  6D values into positions and normals;
- [`surflo/model/surface_net.py`](../../../surflo/model/surface_net.py)
  compresses visual tokens and evaluates the per-query velocity/target field;
- [`surflo/nn/compressor.py`](../../../surflo/nn/compressor.py) implements the
  fixed-size Perceiver token state;
- [`surflo/inference/engine.py`](../../../surflo/inference/engine.py) separates
  plain pointwise flow from the optional rendering-guidance loop.

## Exact sample space

Let $O$ be the input images and let the frozen evidence pipeline plus
Perceiver produce $h(O)$. Plain Surflo draws a source value for each query
point and transports it through a shared conditional velocity field:

\[
x_i(0)\sim p_0(\cdot\mid O),\qquad
\frac{d x_i(t)}{dt}=v_\theta(x_i(t),t,h(O)),\qquad
x_i(1)=(p_i,p_i+\epsilon n_i).
\]

The last equality is the repository's 6D oriented-point representation; the
normal is recovered from the normalized difference of the two 3D components.
The convention follows standard flow matching and the released plain-inference
path: the source is $x_0$, the surface target is $x_1$, and the ODE time grid
moves from 0 to 1. Only the optional mean-flow branch reverses its integration
grid.

The deterministic state $h(O)$ is shared, and all queries share the learned
field parameters. Those facts provide cross-view conditioning. They do not
introduce a sampled random variable whose value denotes one complete scene.
In plain inference, changing the point seed or extending the query set draws
new point-source variables. Rendering guidance can couple point updates through
a shared image-space loss, but coupling an optimization trajectory is not the
same contract as conditioning every future query on one sampled scene identity.

This yields four distinct notions that must not be collapsed:

| Property | Surflo endpoint status |
|---|---|
| Variable output density | Supported: the number of oriented-point queries is selected at inference. |
| Shared deterministic evidence state | Supported: all point transports attend to the same compressed visual tokens. |
| Coupled point refinement | Optional: rendering guidance introduces shared image-space gradients. |
| Sampled persistent complete-scene state | Not defined by the current interface or established by the measured evidence. |

## What Surflo inherits

Surflo inherits feed-forward multi-view geometry and camera evidence from
VGGT, conditional continuous transport from flow matching, oriented points as
a surface-bearing representation, differentiable rendering as an optional
inverse-graphics signal, and Gaussian-wrapping-style mesh extraction. The
frozen evidence encoder also inherits VGGT's visible-support bias and gauge
behavior; a later decoder cannot create observations that the inputs do not
contain.

## What it improves

The core representation improvement is decoupling output point count from an
image-grid pointmap. A fixed-size cross-view state can be decoded into a point
cloud at a chosen density, and normals support direct surface extraction. The
locked B200 scout gives one measured, deliberately narrow comparison on Tanks
& Temples Ignatius:

| Method | Normalized Chamfer ↓ | Surface F1 ↑ |
|---|---:|---:|
| VGGT pointmap | 0.006064 | 0.8565 |
| Surflo plain | 0.004679 | 0.9057 |
| Surflo guided, no densification | 0.004610 | 0.8893 |

This is one scene, not a full benchmark aggregate. It supports the executable
claim that the Surflo decoder can improve measured visible-surface geometry
over its inherited pointmap on this scene. It also shows why Chamfer and F1
must remain separate: guidance slightly improved Chamfer while reducing F1.

## What the paired scene establishes

The photoreal benchmark renders the same 16 context images for two mutually
exclusive complete L-room hypotheses. Scene A contains a hidden sofa; scene B
contains a hidden shelf. Target views reveal the difference, but target images
are withheld from reconstruction. Therefore neither hidden completion is
uniquely recoverable from $O$, while both are valid conditional hypotheses.

Four stock plain-Surflo runs use seeds 0–3, 100,000 queries, and 100 ODE steps.
The result wrapper recomputes these quantities from the per-seed records:

| Quantity | Recorded result |
|---|---:|
| Mean observed-common recall | 0.7657 |
| Mean unobserved-common recall | 0.0564 |
| Mean exclusive hidden support, scene A | 0 |
| Mean exclusive hidden support, scene B | 0 |
| Single-hypothesis support-label fraction | 0 |
| Unsupported seed fraction | 1 |

The result is accepted because the experiment requires valid measurements, not
a favorable completion. It does not show that Surflo always fails to complete
hidden geometry, nor does it estimate a calibrated posterior from four seeds.
It shows that this locked ambiguous episode provides no evidence that point
stochasticity sampled either complete hidden hypothesis.

The compact result does not retain point assignments, candidate counts, or
candidate numerators. It therefore cannot support a within-sample coherence
metric, and the recorded completion-candidate precision of zero is ambiguous
between an empty candidate set and an all-incorrect set. The pathway archives
that published per-seed field for provenance but excludes it from aggregate
metrics and claims.

The analytic paired-room scout is a different diagnostic. It produced hybrid
support for most seeds, whereas the photoreal probe supported neither hidden
alternative. Hybrid and unsupported are different failure modes, but both
reject the stronger claim that an arbitrary-resolution point draw is already a
coherent sample from the conditional distribution over complete scenes.

## Required architectural transition

The missing state is explicit:

\[
z^*\sim p_\phi(z\mid O),\qquad
X_Q\sim p_\theta(X_Q\mid z^*,O,Q),\qquad
I_C\sim p_\psi(I_C\mid z^*,O,C),\qquad
S_T\sim p_\omega(S_T\mid z^*,O,T).
\]

One draw (z^*) must be retained while point set (Q), camera set (C), and
time set (T) change. Repeating a query with the same (z^*) should preserve
scene identity; drawing a new (z^*) may select another evidence-consistent
hypothesis. The state needs an explicit lifecycle—sample, serialize, extend,
render, advance in time—not merely a tensor that happens to be global.

An acceptance suite for that transition should test:

1. observation consistency for every sample;
2. within-sample geometric and semantic coherence;
3. coverage of both paired conditional alternatives over scene-state draws;
4. persistence when query density or spatial extent changes;
5. persistence across cameras and return trajectories;
6. calibrated diversity without rewarding unsupported geometry; and
7. temporal identity after occlusion when the state is extended to 4D.

The proposed state can reuse Surflo's frozen-or-fine-tuned evidence backbone,
Perceiver interface, oriented-point decoder, rendering objectives, and mesh
path. The research change is the stochastic factorization and persistence
contract, not a rejection of the existing surface reconstruction system.
