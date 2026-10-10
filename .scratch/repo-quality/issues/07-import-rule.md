# 07: One import rule, checked

**What to build:** An AST checker, adapted from milano's `scripts/check_imports.py`, that enforces three rules in active code:
- absolute imports from each Bazel import root (`autonomy/`, `parallax/`);
- no relative imports;
- no `sys.path` edits.

It runs as a boundary test in the repo gate.
- Unlike milano, `PYTHONPATH=autonomy` in documented commands and receipts stays allowed. Sureal's live runs use it.
- Frozen code (`research/`, `studies/*/procedure_records/`, `studies/architecture/harness/`) and pinned sources are exempt.

**Blocked by:** 02

**Status:** done

- [x] **Live first.** The scan runs over the tree, and the hits are recorded by kind and by directory. The live runs touched by any fix are re-run: the motion verifiers, and a resource stage if one is touched.
- [x] **Hits in active, unpinned code are fixed.** Any others are put in a baseline that may only shrink, with a reason for each.
- [x] **Self-tests:** positive, negative, and the real repo scanning clean.
- [x] **The rule is written** in the Python style guide (ticket 05), or in AGENTS.md if 05 hasn't landed yet.
- [x] **Gates pass**, with counts recorded.

## Comments

2026-10-10 Done:
- Implemented `scripts/check_imports.py` as an AST import-root checker for `autonomy/` and `parallax/`, with frozen-path and retained-source-pin exemptions derived from `autonomy/retained_receipt_sweep.py` plus receipts.
- First live scan found active unpinned hits in `autonomy/inspection`, `parallax/pipeline`, `parallax/insulas/surflo-foundation`, and Parallax test harnesses. Active code was fixed to use import-root-anchored imports; remaining legacy test-harness `sys.path` edits are in `scripts/import_rule_baseline.json` with shrink-only reasons.
- Final live scan: `python3 scripts/check_imports.py --root . --summary-json` passed with `problem_count=78`, `baseline_count=78`, `unexpected_count=0`, `stale_baseline_count=0`, `pinned_source_count=267`; by kind: `sys-path-edit=78`; by directory: `autonomy/training_execution=2`, `parallax/tests=76`.
- Self-tests: `python3 -m unittest scripts.import_rule_behavior_test scripts.repo_gate_import_rule_test scripts.publication_audit_behavior_test` ran 10 tests, OK.
- Repo gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed 9/9 tests.
- CPU autonomy gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 189/189 tests. The recorded base evidence was 188/188; this ticket did not add an `autonomy/...` test target, so the one-test count increase is from the current checkout state rather than a new import-rule autonomy target.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17 tests.
- CUDA eligibility: GPU 1 was UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `memory.used=4 MiB`, and no compute process was listed for that UUID. CUDA gate: `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 30/30 tests.
- Shared-file overlaps: `AGENTS.md` documents the import rule because ticket 05 has not landed; root `BUILD.bazel` adds the import-rule tests to `REPO_GATE_TESTS`.

2026-10-10 Live closeout addendum:
- Entry points whose own file or transitive imports changed: `autonomy/inspection/inspect_scene.py`; `python -m inspection.inspection_views` as launched by `inspect_scene.py`; viewer exporter/verifier modules `python -m inspection.viewer.export.export` and `python -m inspection.viewer.export.verify`; Parallax dispatcher `parallax/run.sh` / `parallax/pipeline/cli.py`; Parallax `run.sh list`, `all --profile smoke --fixture-only`, `validate`, `report`, `fetch`, `reference --adapter ...`; `parallax/pipeline/audit.py --offline`; `scripts/publication_audit.py --root .` because it launches the Parallax audit; `parallax/insulas/build.sh`'s GPU selector import; landed Parallax reference adapters `colmap-sfm`, `colmap-mvs`, `orb-slam`, `depth-anything-v2`, `neus-facto`, `splatfacto`, `nerfacto`, and `foundation-geometry`; Parallax test harnesses under `parallax/tests/*.py`; Autonomy inspection viewer test harnesses under `autonomy/inspection`.
- Base comparison used detached worktree `022e197` under `$TMPDIR`; it was removed after runs. Logs and JSONL summary are under `$TMPDIR/rq07-live-LE7yBG7U/base-head-cpu/summary.jsonl`. No HDFS writes; outputs were under `$TMPDIR`. GPU reference/CUDA work used GPU 1 only after UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` was free.
- Autonomy live comparison:
  - `PYTHONPATH=autonomy python3 autonomy/inspection/inspect_scene.py $OUTDIR/inspect-scene`: base exit 1 in 2.269s; head exit 1 in 2.280s; same pre-existing `ValueError: runtime identity mismatch` before child launch.
  - Direct child stage using real CPU Insula launch plan for `python -m inspection.inspection_views /source /opt/reconstruction /outputs/views`: base exit 0 in 28.658s; head exit 0 in 26.484s; head output `PASS generated 4 inspection frames 131 artifacts`.
  - Viewer CLI import-load probes `PYTHONPATH=autonomy python3 -m inspection.viewer.export.export --help` and `...verify --help`: base/head both exit 1 before argparse because host lacks `PIL`/`pyarrow`; the dedicated Insula/Bazel harness `./bazelw test ... //autonomy/inspection:all_tests` passed base 8/8 in 13.281s and head 8/8 in 13.052s.
- Parallax live comparison:
  - `SURFLO_PATHWAY_CACHE_ROOT=$OUTDIR/pathway-cache ./parallax/run.sh list --json`: base/head exit 0, 15 modules listed.
  - `SURFLO_PATHWAY_CACHE_ROOT=$OUTDIR/pathway-cache ./parallax/run.sh all --profile smoke --fixture-only --run-id rq07-{base,head}-all-smoke`: base exit 0 in 2.478s; head exit 0 in 2.399s.
  - Same-cache `validate --module 01` and `report` after that smoke run: base exits 2/2 with `implementation hash mismatch`; head exits 0/0 (`valid: rq07-head-all-smoke/01`, report path emitted). The earlier fresh-cache validate/report probes were discarded as harness mistakes.
  - `PYTHONPATH=parallax python3 parallax/pipeline/audit.py --offline`: base/head exit 0; `modules=15`, `sources=94`, `assets=9`, no errors.
  - `python3 scripts/publication_audit.py --root .`: base/head exit 0; publication audit status `pass`.
  - `SURFLO_PATHWAY_CACHE_ROOT=$OUTDIR/fetch-cache ./parallax/run.sh fetch --asset middlebury-mvs`: base exit 0 in 1.362s; head exit 0 in 1.502s.
  - Build selector slice matching `parallax/insulas/build.sh` import: base `PYTHONPATH=parallax/pipeline python3 -c 'from contracts import selected_gpu_device; print(selected_gpu_device())'` exit 0; head `PYTHONPATH=parallax python3 -c 'from pipeline.contracts import selected_gpu_device; print(selected_gpu_device())'` exit 0; both printed `0`.
  - `./bazelw test ... //parallax/...`: base exit 0, 17/17 in 392.955s; head exit 0, 17/17 in 408.702s.
- Parallax reference adapter smoke comparison:
  - `colmap-sfm`: base/head `run.sh reference --adapter colmap-sfm --profile smoke` exit 0 in 9.728s/9.193s.
  - `colmap-mvs` with `SURFLO_PATHWAY_GPU_DEVICE=1 CUDA_VISIBLE_DEVICES=1`: base/head exit 0 in 168.957s/180.272s.
  - `orb-slam`: base/head exit 2 with same missing/corrupt locked TUM RGB-D archive.
  - `depth-anything-v2`: base/head exit 2 with same missing Depth Anything checkpoint asset directory.
  - `neus-facto`, `splatfacto`, `nerfacto`: base/head exit 2 with same missing LPIPS checkpoint.
  - `foundation-geometry`: base/head exit 2 with same Surflo foundation environment build-lock mismatch. This reaches the real adapter/environment verification path but not the in-container model script body; no after-only failure was observed.
- Fresh gates after the live comparison:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`: 9/9 passed, elapsed 22.630s.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 189/189 passed, elapsed 88.319s.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 passed, elapsed 389.361s.
  - GPU 1 eligibility at 2026-10-10T04:02:03Z: UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, `memory.used=4 MiB`, no compute process. `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 30/30 passed, elapsed 125.364s.
