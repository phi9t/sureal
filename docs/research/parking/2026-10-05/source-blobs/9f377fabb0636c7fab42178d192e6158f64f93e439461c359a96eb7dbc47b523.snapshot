# Photorealistic paired-scene benchmark

This benchmark asks whether stock Surflo produces a coherent hidden scene from an
ambiguous partial observation. It renders one shared 16-view context and two
complete, mutually exclusive L-room hypotheses: `scene_a` contains Poly Haven's
`Sofa_01`; `scene_b` contains `Shelf_01`. The context is rendered once without
either hidden object and hard-linked into both episodes, so the conditioning
pixels are exactly identical.

The host scripts only build root filesystems, establish mounts, and dispatch
commands. Blender generation, rendering, annotation extraction, validation, and
asset fetching run in the Blender Insula. Inference and checkpoint handling run
in the existing Surflo Insula. Benchmark render and inference stages are offline.

## Reproduce

The default recorded run is `phase-a-v1`.

```bash
# Build both self-contained Insulas. A cold build requires network access.
experiments/photoreal-scenes/run.sh build

# After build, this is the only networked benchmark-execution stage.
experiments/photoreal-scenes/run.sh fetch

# Optional small test. CPU use must be explicit.
experiments/photoreal-scenes/run.sh render-draft \
  --run-id phase-a-draft --device CPU

# Recorded benchmark: 512x384, 256 Cycles samples, OptiX required.
experiments/photoreal-scenes/run.sh render --run-id phase-a-v1
experiments/photoreal-scenes/run.sh validate --run-id phase-a-v1
experiments/photoreal-scenes/run.sh probe --run-id phase-a-v1 \
  --update-tracked-results

# Or execute the complete recipe.
experiments/photoreal-scenes/run.sh all --run-id phase-a-v1
```

Completed runs are immutable by default. Pass `--overwrite` explicitly to replace
one. A standalone probe updates the repository's compact result only when
`--update-tracked-results` is supplied; the `all` recipe supplies it explicitly.
Rendering and probing write to temporary directories and promote atomically only
after validation succeeds. Use `--emit-plan` before any command to inspect its
resolved profile, device, and network mode without executing it.

Large assets and episodes are not stored in Git. Blender data lives below
`~/.cache/surflo/photoreal-scenes`; validated episodes and probe results are
hard-linked or written below `~/.cache/surflo/insula-scout/photoreal-scenes` via
the shared `/exchange` mount.

## Pinned inputs

- Blender 4.5.14 LTS Linux x86-64 archive, SHA-256
  `9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3`.
- The exact Poly Haven files, URLs, byte sizes, SHA-256 values, resolution, and
  CC0 license are in [assets.lock.json](assets.lock.json).
- The Surflo checkpoint and VGGT revision/file hashes have one machine-readable
  source of truth in [model.lock.json](model.lock.json). Fetch, cache verification,
  probing, compact evidence, and strict auditing all consume that lock.
- The executable settings and cache evidence paths are in
  [recipe.json](recipe.json). Because the evidence was produced before these
  changes were committed, it records the base Git revision plus a recomputed
  digest of the explicit executable source overlay and an uncommitted-overlay
  marker; it does not misidentify the base commit as the implementation commit.

No rendering stage can download data. A missing, corrupt, or hash-mismatched
asset fails before scene construction. Benchmark mode rejects CPU and requires an
enabled NVIDIA OptiX device; it never silently falls back.

## Episode contract

`manifest.json` uses schema v2 and preserves the schema-v1 fields consumed by the
existing Surflo ambiguity probe. Every view provides:

- tone-mapped sRGB PNG and linear multilayer OpenEXR;
- camera-axis depth and Euclidean ray distance;
- world-space geometric and shading normals;
- stable integer object IDs, diffuse albedo, and validity mask; and
- metric intrinsics plus OpenCV-style world-to-camera extrinsics (`+x` right,
  `+y` down, `+z` forward).

Each hypothesis also includes evaluated triangulated world-space geometry, an
object table with provenance and support/occlusion relations, and exactly 250,000
stratified surface samples. Every object receives at least 2,048 samples; the
remainder follows surface area. Per-sample annotations include normals, object
IDs, common/hidden role, context visibility, target visibility, and target-only
visibility. Visibility is checked against rendered depth and ID buffers with a
scene-scale tolerance.

The renderer record captures Blender/Cycles versions, exact device and GPU,
profile, resolution, samples, fixed seeds, AgX, denoiser scope, asset-lock hash,
runtime, and peak memory. Only the beauty pass is denoised.

## Recorded evidence

The B200 benchmark completed with Blender 4.5.14 LTS, OptiX, 512×384 pixels, and
256 samples in 769.92 seconds. Validation recorded 444 artifact hashes and a
maximum camera-center recovery error of `2.76e-15` metres. The two shared-context
trees are hard links with byte-identical RGB; every categorical ID pixel belongs
to the corresponding object table and no hidden ID occurs in context. Hidden
target/target-only surface visibility is 73.1% for the sofa and 59.7% for the
shelf, exceeding the 25% threshold.

The four Surflo seeds completed at 100,000 queries and 100 ODE steps. All were
support-classified `unsupported`; this is a valid finding, not a benchmark
failure.
Mean observed-common recall is 0.7657, mean unobserved-common recall is 0.0564,
and mean hidden support is 0 for both hypotheses. Per-seed completion
precision, camera error, runtime, VRAM, and artifact hashes are preserved in
[results.json](results.json), together with the comparison to the tracked analytic
ambiguity baseline.

Reviewable contact-sheet evidence:

- [shared 16-view context](evidence/shared_context.png)
- [hypothesis A target views](evidence/scene_a_target.png)
- [hypothesis B target views](evidence/scene_b_target.png)

Run the strict evidence audit from the Surflo Insula:

```bash
experiments/insula-scout/enter.sh --offline -- \
  python /workspace/surflo/experiments/photoreal-scenes/verify_recipe.py \
  --cache-root /cache/surflo --strict-artifacts --json
```

## Acceptance and scope

Validation requires finite arrays, unit normals, consistent depth/ray distance,
valid IDs and shapes, the exact frame counts, byte-identical context, differing
targets, zero hidden-context visibility, and at least 25% hidden target and
target-only visibility. Probe acceptance requires four complete, valid
measurements; it does not require a predetermined support label. These labels
summarize thresholded relative support for the two benchmark alternatives; they
do not certify object completeness or within-sample scene coherence.

This is the first static diagnostic milestone. It evaluates stock Surflo and does
not train a scene prior. It also does not add language supervision, video
generation, dynamic objects, transparency/refraction, motion blur, or 4D
dynamics. PBRT and Filament are intentionally outside this milestone.
