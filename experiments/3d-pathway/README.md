# Executable 3D reconstruction pathway

This directory backs the survey in
[`docs/3d-reconstruction-pathway.md`](../../docs/3d-reconstruction-pathway.md).
It provides deterministic concept labs for all fifteen modules, machine-readable
source and asset registries, a common controlled scene, two distinct Insula
definitions, provenance-aware run storage, and citation/terminology auditing.

The smoke profile is the numerical and CI contract. The full profile only
increases the deterministic repo-owned fixture workloads. Maintained systems
run through explicit reference adapters, separately from both concept profiles.
`reference-adapters.json` distinguishes landed adapters from future work.
Controlled fixtures are teaching experiments, not reproduced third-party
leaderboard values.

```bash
# No network:
experiments/3d-pathway/run.sh list
experiments/3d-pathway/run.sh run --module 01 --profile smoke --run-id demo-01
experiments/3d-pathway/run.sh validate --module 01 --run-id demo-01
experiments/3d-pathway/run.sh all --profile smoke --run-id demo-all
experiments/3d-pathway/run.sh report --run-id demo-all
experiments/3d-pathway/run.sh reference --adapter colmap-sfm --profile smoke --run-id colmap-demo
python3 experiments/3d-pathway/pipeline/audit.py --offline

# Explicit network boundaries:
experiments/3d-pathway/run.sh build
experiments/3d-pathway/run.sh fetch
experiments/3d-pathway/run.sh fetch --asset tum-rgbd
python3 experiments/3d-pathway/pipeline/audit.py --online
```

The landed COLMAP SfM adapter requires the classical image produced by
`run.sh build`. It renders the shared scene's explicit calibrated, multi-depth
plane-mosaic reference fixture (five smoke or nine full views), runs the exact
Ubuntu package `colmap=3.9.1-2build2` with container networking disabled, and
executes the immutable image ID inspected before launch. It atomically promotes
validated output under `reference-runs/RUN_ID/colmap-sfm/`. Validation checks
the SQLite catalog and required tables, binary and text sparse models, PLY
vertex count, package and Insula manifests, finite metrics, profile thresholds,
input calibration, execution log, report, hashes, and container provenance.

Runs default to `~/.cache/surflo/3d-pathway`. Set
`SURFLO_PATHWAY_CACHE_ROOT` to choose another cache. A module first writes to
`staging/`, validates schema and hashes, then atomically moves into
`runs/RUN_ID/MODULE/`. Existing module runs are never overwritten.

Every completed module contains:

- `result.json`: metrics separated into geometry, rendering, and generative
  families, resource use, environment, and input/config/artifact hashes;
- `report.md`: a short interpretation with assumptions and observed trend;
- `artifacts/failure_sweep.csv`: controlled intervention and response;
- at least one SVG visualization plus any module-specific compact evidence.

Every metric and artifact is labeled `controlled_fixture`, except module 15,
which is labeled `reused_measured_result` and checked against its asset lock.
`all` stages the complete run and promotes it atomically; its `report.json`
manifest records completeness, sources, assumptions, interpretations, and the
Markdown report hash. A report made from a partial run says so explicitly.

`assets.lock.json` records the generated controlled suite, selected canonical
dataset inputs, and the existing paired-scene result. Downloaded datasets and
checkpoints stay outside Git. `sources.json` is the source of truth for title,
authors, year, venue, primary URL, themes, supported claims, and historical
credit caveats.
