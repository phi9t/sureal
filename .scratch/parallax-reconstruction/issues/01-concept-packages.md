# 01: Concept packages, with no behaviour change

**What to build:** Parallax reorganised into the approved concept layout (see `../spec.md`). Every command, report and test behaves exactly as before.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] **Moves.**
  - `math3d.py` → `camera/pinhole.py`, `camera/pose.py`, `geometry/triangulate.py` and `geometry/align.py`, with `fuse_tsdf` going to `fusion/tsdf.py`.
  - `reference_scene.py` → `scene/`.
  - `*_reference_runner.py` → `baselines/`.
  - `labs.py` and `curriculum.json` → `curriculum/`.
  - The lock and registry JSON files → `assets/`.
  - `*.schema.json` → `schemas/`.
  - `pipeline/` keeps only the orchestration code.
- [x] Old import paths and file paths that callers, `run.sh`, BUILD targets or docs use keep working through thin re-export shims, or are updated in the same change. Nothing pinned by retained evidence is edited.
- [x] Tests move from `parallax/tests/` to sit beside the code as `*_test.py`, import through the package root, and edit no `sys.path`. The Parallax entries in the import-checker baseline are removed.
- [x] `parallax/BUILD.bazel` (or per-package BUILD files) gives each concept a `py_library`, and each test a `py_test`, so that `//parallax/...` still runs every test that ran before.
- [x] **Live check, run first.** `run.sh list`, `all --profile smoke --fixture-only`, `validate` and `report`, run before and after the change inside the Parallax Insula. The report JSON is byte-identical apart from timestamps and run ids. Record the commands and diffs.
- [x] `parallax/README.md` describes the new layout. `docs/repo-structure.md` is updated if it maps Parallax.
- [x] **Gates:**
  - `//:repo_gate`;
  - `//parallax/...`, where the test count may change only by moves, with no tests lost;
  - `//autonomy/...`.

## Comments

### 2026-10-10

Live check ran before final gate verification using the Parallax curriculum Insula rootfs `rootfs-v2`, lock SHA-256 `598d5cabd4bb47e61e4c0966fa72e6c52e1cbb047b98f9f3ee2b08d29785d6a9`. The before tree was a `git archive HEAD` copy at base commit `e2d1702f0de4eddea8e515ae9abd6a8554f50709`; the after tree was the current worktree. Writable cache/output state was mounted at `/outputs` and backed by `~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/px01-concept-packages-20261010T212842Z/tmp/px01-live.uDW0R4`.

Commands for each tree, executed through `insula.launch_plan`:

- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh list`
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh all --profile smoke --fixture-only --run-id px01-base-20261010`
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh all --profile smoke --fixture-only --run-id px01-current-20261010`
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh validate --module NN --run-id <run-id>` for modules `01` through `15`
- `SURFLO_PATHWAY_CACHE_ROOT=/outputs/cache bash parallax/run.sh report --run-id <run-id>`

Results:

- Base: `list` returned 15 modules; `all --profile smoke --fixture-only` returned 0 and produced 15 module result JSON files; all 15 `validate` commands returned 0; `report` returned 0. `report.json` SHA-256 `94834e07c68cb9ff6ca862d1f29278e4b5df2646b7164d2fdf10d29c20af624e`; `report.md` SHA-256 `0c6ae96a69bd870d4ba10b07fd973480cb36ee97c4184372c1f8c9946479278d`.
- Current: `list` returned 15 modules; `all --profile smoke --fixture-only` returned 0 and produced 15 module result JSON files; all 15 `validate` commands returned 0; `report` returned 0. `report.json` SHA-256 `3afe8505dfc17f2c2a9617d287a6f78f39210cd60411c9975026aae9fd680e58`; `report.md` SHA-256 `e2c960bbdf92c3f4de608b9c54b2118e6d634093d51e9abc9f5d641efd55c0b2`.
- Raw `report.json` top-level differences: `run_id`, `module_resources`, `module_results_sha256`, `report_sha256`. The resource differences are runtime/peak-memory telemetry from the live executions, and the digest differences are derived from run-id/resource/provenance files.
- Normalized comparison, masking run ids, runtime seconds, peak CPU bytes and their derived digest fields: 0 diff lines. Normalized base/current SHA-256 both `af82074b587150086bbd11d777646853a40a13a0dc17e48ef8f02e6d39ba0c1a`; normalized diff SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Gate evidence:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`: passed, 1/1 test.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`: passed, 17/17 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: passed, 189/189 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: passed, 17/17 tests. Bazel found 10 targets and 17 test targets, preserving the pre-move Parallax test count.
