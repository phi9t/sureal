# 02: Every module and metric declares whether it is synthetic or real

**What to build:** Readers of a Parallax report can tell measured numbers from illustrative ones.

**Blocked by:** 01

**Status:** done

- [x] `curriculum.json` gives each module an `implementation` value of `synthetic`, `real` or `real+baseline`. The schema enforces it. All 15 modules start as `synthetic`.
- [x] **Labelling.** Every hardcoded metric in the synthetic labs is labelled `illustrative`, for example `accuracy_mm` and `f_score_2mm` in the MVS lab and `map_f_score` in the SLAM lab. Metrics computed from data in the lab keep their values but are labelled as computed on synthetic data.
- [x] Reports (JSON and rendered) show the status of each module and of each metric. The validator rejects a module marked `real` whose metrics are not all computed.
- [x] The README states plainly what is real and what is illustrative today.
- [x] **Live check.** `all --profile smoke` runs inside the Parallax Insula, and the report shows the labels. Record the commands.
- [x] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-10

Implemented explicit Parallax honesty status:

- `parallax/curriculum/curriculum.json` now declares `implementation:
  synthetic` for modules `01` through `15`; `parallax/schemas/curriculum.schema.json`
  allows only `synthetic`, `real`, or `real+baseline`.
- `result.json` now carries `module_implementation`, and aggregate
  `report.json` carries `module_implementations` plus per-module
  `metric_provenance`.
- Rendered module and aggregate reports show module implementation status and
  each metric's label.
- The validator rejects `real` module results unless every metric is
  `computed_real`; `real+baseline` permits only `computed_real` or
  `computed_baseline`.
- The README now states that all modules are synthetic today, computed lab
  metrics are `computed_synthetic`, and fixed teaching values are
  `illustrative`.

Live check, run through `autonomy.insula.launch_plan` using the Parallax
curriculum rootfs `~/.cache/waystone/3d-pathway/insula/rootfs-v3`; lock
`~/.cache/waystone/3d-pathway/insula/rootfs-v3.lock.json` SHA-256
`8df13a37ef3adadab73175e3652d9fb8bb20d7c9a481d845cdc86e182a0d7e33`. Writable
output/cache root:
`~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/px02-honest-status-20261010T225042Z/tmp/px02-live-final.kct3vg`.

Commands and results:

- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache python -c 'import numpy, scipy;
  print("numpy", numpy.__version__); print("scipy", scipy.__version__)'`:
  exit 0; `numpy 1.26.4`; `scipy 1.14.1`.
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh all --profile
  smoke --run-id px02-final-20261010`: exit 0; produced 15 module results,
  modules `01` through `15`; stderr included the existing Module 10
  `RuntimeWarning: divide by zero encountered in divide` during SDF
  interpolation.
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh report
  --run-id px02-final-20261010`: exit 0.

Live report evidence:

- `report.json` SHA-256:
  `cc20af75c023ef821cd509fae6534486fdc38892e8de4222770a3f6e3b46169b`.
- `report.md` SHA-256:
  `0b3c32ba94466516156027a4889a91af93aceb7af4d560179dd2c3f8de2e9575`.
- `report.json` records all 15 `module_implementations` as `synthetic`.
- `report.json` records Module 06 geometry labels:
  `accuracy_mm=illustrative`, `completeness=computed_synthetic`,
  `f_score_2mm=illustrative`, `hidden_surface_recall=illustrative`.
- `report.json` records Module 07 geometry labels:
  `ate_before_loop_m=computed_synthetic`,
  `ate_after_loop_m=computed_synthetic`,
  `relative_pose_error_m=computed_synthetic`, `map_f_score=illustrative`.
- Rendered `report.md` contains `implementation=synthetic`, `illustrative`,
  and `computed_synthetic`.

Focused red/green evidence:

- Red run before implementation:
  `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //parallax:test_foundation
  //parallax:test_e2e_completion` failed because modules lacked
  `implementation`, results lacked `module_implementation`, aggregate
  `report.json` lacked `module_implementations`, and rendered reports omitted
  implementation/metric labels.
- Green focused run after implementation:
  `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //parallax:test_foundation
  //parallax:test_e2e_completion`: passed, 2/2 test targets.

Gate evidence gathered before the final ticket closeout edit:

- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:pinned_sources_test`: passed,
  1/1 test target.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //:repo_gate`: passed, 19/19
  test targets.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //autonomy/...`: passed, 189/189
  test targets.
- `./bazelw test --noexperimental_collect_system_network_usage
  --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17
  test targets.
