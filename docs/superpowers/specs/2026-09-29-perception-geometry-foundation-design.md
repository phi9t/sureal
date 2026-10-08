# Mathematical foundation for multimodal perception

Date: 2026-09-29. Status: proposed mathematical/verification contract;
implementation and independent numerical verification remain pending.
User priority: settle geometry before representation comparisons. This document
extends R0 and the research charter, rather than launching another detector.

## Scope and anchor references

Use [Ethan Eade's derivations](https://www.ethaneade.com/) and
[Solà, Deray and Atchuthan, micro Lie theory v9](https://arxiv.org/abs/1812.01537v9)
for rotations, rigid motions, local perturbations and Jacobians. Evaluate
[SymForce](https://github.com/symforce-org/symforce) for independent symbolic
derivation, manifold-aware residuals and generated kernels. Dependency adoption
is conditional on convention and runtime verification; citing these sources is
not numerical verification of this project's formulae.

Cover Euclidean/polar coordinates, SO(3)/SE(3), calibrated range/image geometry,
BEV rasterization, sensor timing and covariance. Radar receives a generic
measurement model and synthetic fixtures; the acquired Waymo Perception slice
has no radar measurements. Calibration refinement/optimization is optional
after fixed-calibration replay. Full SLAM is outside this foundation.

## One explicit project convention

Column vectors; right-handed metric frames; meters, seconds and radians.
T^A_B maps coordinates from B into A: p^A=R^A_B p^B+t^A_B.
Composition T^A_C=T^A_B T^B_C; inverse maps in the opposite direction.
Points transform with rotation and translation; directions with rotation only.
Frame identity includes dataset context and reference time; vehicle-at-two-times
are distinct frames even if both have the name vehicle.

The canonical vehicle axes are forward X, left Y, up Z. Every source sensor
adapter declares its actual axis basis, units, calibration direction and
quaternion order. Define a separate conventional optical frame (right X,
down Y, forward Z) for pinhole formulas. Convert dataset camera coordinates
explicitly; do not assume Waymo camera axes equal that optical frame. Storage
quaternion ordering and Euler ordering belong to source adapters, never an
implicit global guess. Rotation matrices are the interchange boundary; any
quaternion representation declares order, sign-equivalence and normalization.

Use a project twist xi=[omega_x,omega_y,omega_z,v_x,v_y,v_z] and
xi-hat=[[omega-cross,v],[0,0]]. Adopt right perturbations:
T'=T Exp(xi-hat). Tangents are local/body-frame quantities. Exp/Log denote the
actual group exponential/logarithm. Third-party retractions may differ; convert
and label their conventions explicitly. Spatial/left perturbations are allowed
only at named boundaries, with conversion via the adjoint.

For this rotation-first ordering:
Ad_T=[[R,0],[t-cross R,R]], xi_left=Ad_T xi_right.
An identity convention test must be supplemented by nonzero translation and
rotation cases; identities hide ordering and adjoint mistakes.

## SO(3), SE(3) and stable local calculus

SO(3) exp uses Rodrigues with series near zero. SE(3) exp has rotation
Exp(omega-cross) and translation J_left_SO3(omega) v; copying v directly is
not the general SE(3) exponential. Implement Log with a documented principal
rotation branch. Near pi, axis/sign selection is ambiguous: compare recovered
rotations/transforms rather than requiring one unique tangent vector. Avoid
Euler interpolation and generic matrix inversion for rigid transforms.

Required primitives: transform compose/inverse/apply; exp/log; adjoint;
left/right SO(3) and SE(3) Jacobians; declared boxplus/boxminus; and unit-tested
conversion to backend tangent/storage conventions. Do not claim all are needed
for the first range reconstruction kernel: supply the tested core first and
add analytic Jacobians as residuals require them.

For fixed p under right perturbation, the point-transform derivative at zero
is d(T Exp(xi-hat)p)/d xi=R[-p-cross, I]. For a left perturbation it is
[-(Rp+t)-cross,I]. Pin both in tests; neither is interchangeable with the other.
Use finite-difference derivatives on the chosen manifold update, not on nine
unconstrained rotation-matrix entries. For generic differentiable functions,
validate chain rules and perturbation-direction conversions independently.

## Polar coordinates and native range view

Define range r>=0, azimuth alpha=atan2(y,x), elevation beta above XY:
x=r cos(beta) cos(alpha), y=r cos(beta) sin(alpha), z=r sin(beta).
Inverse r=norm(p), beta=atan2(z,sqrt(x*x+y*y)). Zero range has no defined angles;
vertical rays have undefined azimuth. Return a validity/singularity mask instead
of manufacturing a zero angle. Distinguish elevation from inclination measured
from +Z and cylindrical radius from spherical range. Angle wrap is periodic;
its numeric representation is discontinuous at the chosen seam.

The spherical-to-Cartesian measurement Jacobian has columns:
[cos(beta)cos(alpha), cos(beta)sin(alpha), sin(beta)],
[-r cos(beta)sin(alpha), r cos(beta)cos(alpha), 0], and
[-r sin(beta)cos(alpha), -r sin(beta)sin(alpha), r cos(beta)].
Use measurement covariance ordered [r,alpha,beta] when applying this Jacobian.

A native range image is a sensor-specific sample lattice, not an RGB image or
uniform spherical grid. Store calibrated beam inclinations, scan column order,
azimuth/extrinsic-yaw corrections, dimensions, acquisition-time support and
return identity. Exact Waymo discretization comes from pinned source utilities,
then independently checked axial/azimuth fixtures. Generic polar equations do
not replace those conventions. Preserve (sensor,return,row,column) through
range→point→projection. The inverse is not generally one-to-one after motion
compensation, quantization or combining returns; define collision/visibility
policy rather than calling rasterization an invertible transform.

Invalid ranges and absent payloads stay separate. NLZ is annotation metadata,
not an observation channel. Full range features remain available to scene
geometry even if an RSN-style detector selects only predicted foreground.

## Sensor transforms, camera projection and time

For a LiDAR ray acquired at tau in sensor L and chosen vehicle reference V_ref:
p^V_ref=(T^W_V_ref)^-1 T^W_V(tau) T^V_L p^L.
When pixel poses are available, use their documented reference and direction;
do not multiply an extrinsic twice. State whether source points are already
vehicle/world compensated. Ego-motion compensation does not freeze actors.

For an optical camera frame, u=f_x X/Z+c_x, v=f_y Y/Z+c_y before distortion.
Require positive depth and explicit validity, distortion model and image
bounds. Unprojection returns a ray without known depth; camera optical-axis
depth Z and Euclidean range norm(p) are different quantities. This distinction
also separates R4D depth from range-view measurements. The upstream Waymo
camera-depth helper computes camera-origin Euclidean norm, not optical-axis Z;
its name alone does not establish compatibility with a depth-training target.

Exposure/per-pixel acquisition time and scan pose are not synonymous with the
frame key. A static camera projection is an approximation when motion/rolling
shutter matters. Supplied Waymo point projections are one reference relation;
new projections must declare camera model, timing and moving-point assumptions.
A source frame timestamp cannot establish online availability by itself.
For pose interpolation, use a declared geodesic/local-motion approximation
T(t)=T0 Exp(s Log(T0^-1 T1)); reject extrapolation unless explicitly requested.
An interpolation does not imply the true trajectory is constant-twist.

## BEV as a lossy representation

Declare BEV frame/time, metric extent, half-open boundaries, resolution, axis
orientation, grid origin, cell centers and integer row/column convention.
For x in [xmin,xmax) use i_x=floor((x-xmin)/dx), similarly for y. Any display
flips/transposes belong to an explicit visualization adapter. Define upper-edge,
negative-coordinate and floating-point-boundary behavior with fixtures.

Point→BEV is aggregation, not a rigid coordinate transform. Declare height bins
or height collapse, feature reduction, count/support masks and collisions.
BEV→point may gather a cell feature but cannot recover geometry discarded by
pooling. Empty cell is unobserved unless a separate ray/free-space derivation
supports a claim. Camera→BEV needs depth or a stated planar hypothesis;
rotating a perspective feature image does not create metric BEV geometry.

## Generic radar and uncertainty

Define a radar measurement z=[range,azimuth,elevation,radial_velocity], allowing
2D sensors to omit elevation. Transform position/ray with calibrated SE(3),
but do not interpret Doppler as full velocity. Radial velocity is a projection
of relative target/sensor velocity; sign, ego motion, lever-arm rotational
velocity, sensor time and absent elevation need explicit contracts. Synthetic
radar tests validate math only, not Waymo radar fusion.

Measurement covariance maps approximately via Sigma_p=J Sigma_z J^T. Pose
covariance is six-dimensional in a declared tangent frame/order, not covariance
of a stored quaternion. Convert left/right covariance via Ad_T Sigma Ad_T^T.
Declare independence when summing point and pose contributions; correlated
calibration/trajectory errors require cross terms. Linearization is local and
can fail near singularities, large uncertainty or multimodal hypotheses.
Keep observation support and learned predictive calibration separate.

## SymForce role and adoption gate

Prefer a small numeric reference implementation plus optional symbolic tooling.
Use SymForce to derive transform/projection/residual Jacobians and generate
fixtures or supported code targets. Verify Pose3 tangent order, retract/local
coordinates, epsilon handling, camera conventions and supported generated
backend against this contract. Do not assume its product-manifold update is
identical to SE(3) Exp or that generated code is automatically Torch/JAX-native
or differentiable through those frameworks.

Prototype one nontrivial transform-point Jacobian and one projection residual.
Compare symbolic/generated output with independent closed-form and manifold
finite differences, then test near-zero rotations and invalid camera depth.
Record version/license/generated-file hashes and generation environment. Adopt
only if the benefit exceeds maintenance/build complexity. Keep symbolic codegen
out of per-frame loading; no optional import may silently change numeric results.
The primary-source audit confirms SymForce's standard Pose3 uses a
rotation/translation product-manifold update; it must not be substituted for
the coupled SE(3) Exp specified above. Its stored quaternion is xyzw, and its
translation tangent convention differs from a body-frame coupled twist.
PyTorch codegen is documented but remains a capability to verify in the chosen
version; JAX output was not established. See the
[source audit](../../../experiments/waymo-perception/research/geometry-foundation-sources.md).
No dependency is installed by this design review.

## Verification ladder and implementation scope

1. Analytic axial rays, noncommuting transform chains, units and direction tests.
2. Group invariants, exp/log roundtrips on the declared branch, near-zero/near-pi
   cases, quaternion sign-equivalence and nonzero-translation adjoints.
3. Jacobian agreement across closed-form, manifold finite differences and
   optional symbolic generation; convergence across multiple step sizes.
4. Native return/pose/projection/semantic identity conservation and hostile
   permutation, boundary, missing-calibration and invalid-payload tests.
5. BEV known-cell/collision/coverage fixtures and roundtrip feature gathering,
   explicitly excluding a false geometric-invertibility claim.
6. Small-noise Monte Carlo covariance agreement, with reproducible seeds and
   declared independence; large-noise failures documented rather than hidden.
7. Existing two-scene dedicated-Insula replay with source/runtime locks,
   quantified projection diagnostics and representative views.

Tolerance follows numerical dtype, coordinate scale and residual units; use
float64 for reference tests and document looser learned-runtime precision.
Symmetric inverse tests alone are insufficient: the same erroneous convention
can cancel in both directions. R0 must pass the relevant gates before model
comparisons. Lie optimization, radar data ingestion and full rolling-shutter
camera reconstruction receive separate implementation scopes if needed.

## Binding live implementation gate — 2026-09-30

Each implemented math/geometry milestone must run its analytic, numerical and
applicable real-data checks in a live dedicated Insula. Host unit tests cannot
close it. Pure mathematical primitives use analytic/synthetic fixtures inside
Insula; dataset adapters additionally use the acquired source slice. Independent
checks must establish conventions and lineage, not merely successful imports.
See [live verification contract](2026-09-30-live-insula-verification-design.md).
Current float64 core: implemented-awaiting-live-verification. Any future
SymForce-generated kernel or Torch/JAX port is a separate candidate requiring
its own live numerical parity and runtime evidence.
