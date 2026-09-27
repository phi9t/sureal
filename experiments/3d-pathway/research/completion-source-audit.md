# Completion source audit

Audit date: 2026-09-27. Historical cutoff: 2026-09-25. Scope: the source
registry, external-asset locks, survey, and executable canonical-sample
consumers. Primary evidence is restricted to author/project pages, official
proceedings and DOI records, and upstream source repositories.

## Final verdict

The source and canonical-input acceptance gaps found in the initial audit are
closed in this branch:

- `sources.json` contains 84 claim-bearing records. Every cutoff-year record
  has a day-level `first_public_date`, and the audit rejects dates after
  2026-09-25.
- The citation parser covers dotted identifiers such as `gsplat-1.4.0`, and
  every material HTTPS link in the survey must be registered.
- Depth Anything 3 now consistently describes the 2025 eight-author arXiv
  edition; gsplat 1.4.0 is dated 2024; Surflo's persistent-scene conclusion is
  labeled as a repository inference rather than a paper claim.
- The COLMAP 4.0.3 release and the pinned 2026 installation source are
  first-class registry entries supporting the Blackwell PatchMatch and CUDA
  build claims.
- The official 16-view Middlebury `TempleSparseRing` archive is byte- and
  tree-locked and consumed by the full COLMAP MVS adapter. Because the archive
  does not distribute its laser ground truth, this canonical run reports
  calibrated-view consumption, fused-point support, and mesh support—not
  accuracy or completeness.
- The verified NeRF example archive is tree-locked. Full Nerfacto runs consume
  16 fixed Lego training views and score four held-out views; canonical
  rendering measurements remain separate from the analytic shared-scene
  geometry measurements.
- Full concept modules bind the existing validated Blender/Cycles
  `phase-a-v1` episode. Its recipe, manifest, validation record, and all 444
  cached artifacts are checked before use.

## Locked canonical inputs

| Input | Byte/tree evidence | Executable consumer | Claim boundary |
|---|---|---|---|
| Middlebury `TempleSparseRing` | 4,004,383-byte archive; 19-file extracted tree | `colmap-mvs-reference` full | Structural execution/support only; no distributed laser truth |
| NeRF example Lego | 370,385,516-byte archive; 873-file extracted tree | `nerfstudio-nerfacto-reference` full | Held-out novel-view PSNR/SSIM, separate from surface geometry |
| TUM RGB-D `freiburg1_xyz` | Hash-verified tar extraction | `orb-slam-reference` | Metric RGB-D trajectory and visible landmark map, not hidden completion |
| Blender `phase-a-v1` | Locked recipe plus 444-artifact validation inventory | All 15 full concept modules; Surflo endpoint | Shared evidence binding; per-module teaching metrics remain distinct |

## Historical-credit result

The registry and survey explicitly state that bundle adjustment predates the
Triggs et al. modern synthesis, splatting predates 3D Gaussian Splatting, and
non-rigid factorization and scene flow predate neural canonical/dynamic fields.
Splatfacto is identified as a maintained family implementation, not a
paper-exact Kerbl reproduction.

## Reproduction evidence

Run from `experiments/3d-pathway`:

```bash
python pipeline/audit.py --offline
run.sh fetch --asset middlebury-mvs
run.sh fetch --asset nerf-synthetic
run.sh all --profile full --run-id pathway-full-e2e
```

The offline audit currently reports 15 modules, 84 sources, 9 assets, and zero
errors. Full acceptance additionally requires all fifteen full-profile lab
results and every landed maintained reference result in the atomic cross-era
report; the source audit alone does not substitute for that execution gate.
