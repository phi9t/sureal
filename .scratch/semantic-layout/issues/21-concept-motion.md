# 21: Concept batch: `motion`

**What to build:** Motion ingestion and evaluation live together under `motion`, Python and C++ side by side.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`), 28 (The perception rootfs carries the tools its tests need)

**Status:** done

- [x] Scope: motion ingestion, the causal projection, and the native, pooled and joint motion metric tools with their Python drivers and verifiers
- [x] C++ that needs the upstream Waymo sources keeps its existing build inside its dedicated rootfs; C++ that builds from this repository gets Bazel targets
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Candidate branch: `worker/sureal-semantic-21`.

Candidate commits so far:

- `c1c7e31` pure move: `motion-evaluation/`, root motion tests, and motion verifier scripts moved under `autonomy/motion/` with no content edits.
- `fe7458f` content/build wiring: `autonomy/motion/BUILD.bazel`, package imports, evidence digest helpers, root aggregation, layering, and visibility.

Changed concept:

- `autonomy/motion` now owns motion ingestion fixtures, causal projection sources, native/single CLI, pooled CLI, joint/native/pooled/causal test modules, and motion verifier/replay drivers.
- Root `autonomy/BUILD.bazel` excludes `motion/**` from the legacy test glob and includes `//autonomy/motion:all_tests`.
- Lower concept visibility was opened only where motion imports it: `evidence`, `geometry`, and `insula`.

Closed-gate procedure records and deferred/native build notes:

- Dedicated-rootfs Motion recipes stayed as records/tools under `autonomy/motion`: `CMakeLists.txt`, `Dockerfile`, `cli/{CMakeLists.txt,Dockerfile,motion_metrics_main.cc}`, `pooled/{CMakeLists.txt,motion_metrics_pooled_main.cc}`, and Waymo-proto native ingestion sources.
- C++ requiring upstream Waymo sources, generated protos, or `/motion-build` remains built by the dedicated rootfs/CMake procedures; no container/rootfs rebuild was launched.
- The pure repository C++ helper `ingestion/fnv_bytes_fixture.cc` has Bazel target `//autonomy/motion:fnv_bytes_fixture`.
- Deferred moves outside this ticket: none. Retained `research/` evidence keeps historical paths and was not edited.

Verification:

- `timeout 900 ./bazelw test //autonomy/motion:all_tests --test_output=errors` -> exit 0; 1 default-filtered motion test target passed (`//autonomy/motion:ingestion__delta_components_test`). Live/native motion tests remain tagged out by default.
- `PYTHONPATH=autonomy python3 -m unittest autonomy.motion.ingestion.delta_components_test -v` -> exit 0; 4 tests passed.
- `timeout 900 ./bazelw build //autonomy/motion:fnv_bytes_fixture //autonomy/motion:native_ingestion_sources //autonomy/motion:motion_cli_recipe //autonomy/motion:motion_pooled_recipe` -> exit 0; 4 targets analyzed, build completed successfully.
- `python3 autonomy/tools/layers.py` -> exit 0; `PASS: 0 layering problem(s) across 17 layers`.
- `timeout 900 ./bazelw test //autonomy/...` -> exit 0; 148 test targets passed. Bazel reported `Executed 147 out of 148 tests: 148 tests pass` because one target was cached.
- `timeout 900 ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` -> exit 0; 24 of 24 GPU-tagged tests passed.
- `timeout 900 ./bazelw test //parallax/...` -> exit 0; 17 of 17 tests passed.
- `python3 -m unittest tests.test_publication_audit` -> exit 0; 30 tests passed.
- `python3 scripts/publication_audit.py --root .` -> exit 0; `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4987}`.
- `git diff --check` -> exit 0.
- `git diff --quiet 5ba7237 -- autonomy/research && echo 'research unchanged from 5ba7237'` -> exit 0; `research unchanged from 5ba7237`.

Pin impact:

- `python3 autonomy/tools/pins.py check --base 5ba7237` -> exit 1, expected measurement for intentional concept moves. Report: `FAIL: 32 changed file(s) pinned by retained receipts`.
- Pinned paths moved from old motion locations to the concept package, including native Motion root recipe files, CLI recipe files, ingestion fixtures/helpers, pooled recipe files, and the four motion test modules. Representative report entries:
  - `motion-evaluation/CMakeLists.txt -> motion/CMakeLists.txt`
  - `motion-evaluation/Dockerfile -> motion/Dockerfile`
  - `motion-evaluation/cli/CMakeLists.txt -> motion/cli/CMakeLists.txt`
  - `motion-evaluation/cli/Dockerfile -> motion/cli/Dockerfile`
  - `motion-evaluation/cli/motion_metrics_main.cc -> motion/cli/motion_metrics_main.cc`
  - `motion-evaluation/ingestion/delta_components.py -> motion/ingestion/delta_components.py`
  - `motion-evaluation/ingestion/fnv_bytes_fixture.cc -> motion/ingestion/fnv_bytes_fixture.cc`
  - `motion-evaluation/ingestion/motion_causal_project.cc -> motion/ingestion/motion_causal_project.cc`
  - `motion-evaluation/ingestion/native_source_inventory.cc -> motion/ingestion/native_source_inventory.cc`
  - `motion-evaluation/pooled/motion_metrics_pooled_main.cc -> motion/pooled/motion_metrics_pooled_main.cc`
  - `tests/test_motion_causal_projection.py -> motion/ingestion/motion_causal_projection_test.py`
  - `tests/test_motion_joint_cli.py -> motion/cli/motion_joint_cli_test.py`
  - `tests/test_motion_native_cli.py -> motion/cli/motion_native_cli_test.py`
  - `tests/test_motion_pooled_cli.py -> motion/pooled/motion_pooled_cli_test.py`

Limitations:

- No integration merge was performed: the run rules prohibit merge/rebase/reset, the workspace started at the recorded integration commit `5ba7237`, and no local `refs/heads/work/semantic-layout/integration` ref exists in this private checkout.
- Live Motion rootfs/native replay commands were not launched; this ticket only moved and rewired their preserved procedure records and Bazel-visible source/recipe targets.
