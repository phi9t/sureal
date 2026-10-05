# Geometry foundation: conventions before encoders

Primary sources checked 2026-09-29. This is a proposed shared mathematical contract for SUREAL, with implementation cautions rather than a new sensor-data promise.

## Sources and reading order

1. [Ethan Eade’s Lie groups for 2D and 3D transformations](https://www.ethaneade.com/lie.pdf): derive SO(3)/SE(3) action, composition, inverse and exponential maps first. Eade uses translation-first SE(3) tangent coordinates `(u,ω)`; translation in the true exponential is `V(ω)u`, not simply `u`. His [reference page](https://www.ethaneade.com/) also links exponential-map derivatives and Gauss–Newton notes.
2. [Solà, Deray and Atchuthan, A micro Lie theory for state estimation in robotics](https://arxiv.org/pdf/1812.01537): use as the reference for left/right perturbations, adjoints, Jacobians and covariance transport. Its equations are exact only when the chosen tangent order, perturbation side and Jacobian definitions agree with the implementation; “six-vector pose increment” alone is insufficient specification.
3. [Waymo dataset schema](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/dataset.proto) and [official range-image transformations](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/utils/range_image_utils.py): treat these as authoritative adapter conventions, not as a TensorFlow runtime dependency.
4. [SymForce](https://github.com/symforce-org/symforce): assess as optional symbolic derivation/Jacobian/code-generation tooling after the geometry contract is explicit.

## Proposed core contract and equations

Use column vectors and notation `T_A_from_B` meaning **coordinates in B → coordinates in A**. Store frame identity and time alongside every transform; expose composition, inverse and point/vector actions distinctly:

```text
p_A = R_A_from_B p_B + t_A_from_B
T_A_from_C = T_A_from_B T_B_from_C
T_B_from_A = [ Rᵀ  −Rᵀt ; 0  1 ]
v_A = R_A_from_B v_B                    # free vector, no translation
```

A sweep acquired at time `ti` and aligned to ego time `t0` uses `T_ego(t0)_from_world T_world_from_ego(ti) T_ego(ti)_from_sensor(ti)`. For spinning LiDAR, `ti` can be per point/pixel. This compensates ego motion; moving-object motion requires an additional model. Camera exposure/rolling-shutter times should not silently be replaced by the LiDAR frame timestamp.

For a right-handed sensor frame with X forward, Y left and Z up, define azimuth `a=atan2(y,x)`, elevation `e=atan2(z,hypot(x,y))`, radial range `r=norm(p)` and BEV radius `ρ=hypot(x,y)`:

```text
x = r cos(e) cos(a)     y = r cos(e) sin(a)     z = r sin(e)
x = ρ cos(a)           y = ρ sin(a)           z = height
```

Spherical range and cylindrical BEV radius therefore differ whenever elevation is nonzero. Conversion is continuous away from singularities; mapping to rows/columns/voxels is a **separate quantization policy**. Specify angular seam, center/edge convention, calibrated beam lookup, invalid returns, duplicate collisions and first/last-return choice. A polar BEV cell grows in metric area with radius; an XY cell has fixed metric dimensions. Neither is losslessly invertible after pooling/quantization.

Define XY BEV indexing explicitly, for example `ix=floor((x−xmin)/dx)`, `iy=floor((y−ymin)/dy)`, canvas `[iy,ix]`, cell center `(xmin+(ix+0.5)dx, ymin+(iy+0.5)dy)`, and half-open bounds. Tensor layout, display origin and increasing pixel-row direction are distinct from the physical axes. Keep point IDs and occupancy/label masks through scatter/gather.

For a conventional optical camera frame, pinhole projection uses `(u,v)=(fx X/Z+cx, fy Y/Z+cy)` for positive optical depth Z, followed by the specified distortion/image transform. Unprojection from optical depth is `p=Z K⁻¹[u,v,1]`; unprojection from radial range instead normalizes the ray before multiplying by r. Apply an explicit basis conversion when the dataset camera frame differs from the chosen optical convention. Crops/resizes/flips must update intrinsics/projection consistently; label-visible masks are not the same as geometric in-bounds masks.

These formulas define the proposed contract; they are not an assertion that every source uses the same axes or perturbation convention.

## Waymo-specific pitfalls verified in primary code

Waymo’s schema stores transforms row-major and defines camera/LiDAR extrinsics as **sensor-to-vehicle**. Its range rows represent pitch and columns yaw, with nonuniform beam calibration allowed. Raw range-image pixel poses map vehicle-to-global; the second return shares the first return’s pixel pose. The official conversion uses reversed pixel-center azimuth sampling with extrinsic-yaw correction, then sensor-to-vehicle and optional pixel-to-world/reference-vehicle transforms. Do not replace that with a generic uniform spherical image formula. [Schema](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/dataset.proto), [range conversion](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/utils/range_image_utils.py).

The official helper `build_camera_depth_image` returns the **Euclidean norm of camera-frame XYZ**, despite its “depth” name. It is not directly optical-axis depth for camera lifting or R4D. Its collision policy defaults to minimum distance. Camera projection records carry `(x,y)` pixel coordinates while image arrays index `(row=y,column=x)`. Port behavior deliberately, including masks and precision. [Helper implementation](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/utils/range_image_utils.py).

The standard perception schema supplies camera/LiDAR data and calibrations, not a radar measurement stream. Generic radar geometry can belong in the shared math interface; no radar training/evaluation should be promised for this Waymo program without a separately verified dataset adapter.

## SO(3), true SE(3), and SymForce are not interchangeable increments

For the project convention `ξ=(φ,ρ)` with rotation first, the true Lie exponential is

```text
Exp_SE3(ξ) = [ Exp_SO3(φ)  J_left_SO3(φ)ρ ; 0  1 ]
T_new = T Exp_SE3(δξ)       # chosen right/body perturbation
```

A left/spatial perturbation would instead be `Exp_SE3(δξ) T`; the same six numbers then act in a different frame. Use adjoints to relate conventions and covariance blocks, not permutation alone. Adopt stable small-angle series and explicit behavior near π for logs; quaternion sign equivalence and normalization must be handled independently of tangent coordinates. [Eade §3](https://www.ethaneade.com/lie.pdf), [micro Lie theory](https://arxiv.org/pdf/1812.01537).

SymForce’s standard **Pose3** stores quaternion `(x,y,z,w)` followed by translation `(x,y,z)` and uses a **rotation-first** tangent followed by translation in the non-rotated frame. Group composition/inversion are normal rigid transforms, but its manifold retract/local coordinates operate on **SO(3) × R³**: rotation retracts and translation adds separately. Consequently `retract(a,v)` is generally different from `a.compose(from_tangent(v))`; `from_tangent` is not the coupled matrix SE(3) exponential. Its docs identify symbolic `unsupported.pose3_se3.Pose3_SE3` for true-SE(3) behavior and explicitly state there is no runtime equivalent. [Pose3 documentation](https://symforce.org/api/symforce.geo.pose3.html), [source](https://github.com/symforce-org/symforce/blob/main/symforce/geo/pose3.py).

Recommendation: use SymForce to derive/test residuals and Jacobians under its declared retract, or derive explicit true-SE(3) expressions; do not silently substitute Pose3.from_tangent for project Exp_SE3. The project and SymForce both use rotation-first coordinates, but their translation update semantics still differ. Convert tangent ordering **and** update convention when comparing analytical/autodiff Jacobians.

## SymForce role and framework boundary

SymForce provides symbolic Python, generated C++/Python geometry and nonlinear optimization. Current documentation exposes a [PyTorchConfig code-generation backend](https://symforce.org/api/symforce.codegen.backends.pytorch.pytorch_config.html); the repository describes PyTorch/CUDA backends as experimental. This establishes that Torch generation exists, not that every camera/manifold operation, batching pattern or training gradient is production-ready. No documented JAX code-generation backend was verified in this bounded check. NumPy-generated Python is not automatically JAX-JIT/autodiff compatible. [Repository](https://github.com/symforce-org/symforce), [backend index](https://symforce.org/api/symforce.codegen.backends.html).

Keep a small framework-independent reference implementation and native batched Torch/JAX implementations for model training. Make SymForce an optional development dependency for symbolic checking/code generation rather than a required runtime choice. Evaluate a pinned version with a tiny projection/pose residual, generated outputs, tangent Jacobian, finite differences and framework autodiff before adoption. Code-generation success alone does not establish differentiable end-to-end integration.

Generic radar measurements can use `(range,azimuth,elevation)` with the same spherical-to-Cartesian action once axes/units are specified. Doppler supplies line-of-sight **relative radial velocity**, not a full Cartesian velocity vector. Keep measurement sign convention, sensor ego velocity (including angular-motion lever-arm contribution), missing elevation and covariance explicit; missing elevation is not measured zero height. This is generic geometry scope, not evidence of radar samples in Waymo.

## Minimal acceptance evidence before encoder experiments

Verify known-axis rotations; pose inverse/composition; translation-free vector actions; SO(3)/SE(3) exp/log round trips away from branch cuts; analytic-versus-autodiff/finite-difference Jacobians with the same perturbation; continuous polar/Cartesian round trips; calibrated range-grid decoding on recorded fixtures; pixel-center and BEV-boundary cases; camera project/unproject with distortion/crop conventions; and synthetic static-world sweep compensation. Require float64 reference parity before choosing training tolerances/dtypes. Keep quantization/collision losses out of continuous round-trip assertions.
