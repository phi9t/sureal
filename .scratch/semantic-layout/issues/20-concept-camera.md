# 20: Concept batch: `camera`

**What to build:** Camera data handling and the camera evaluator live together under `camera`, Python and C++ side by side.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`), 28 (The perception rootfs carries the tools its tests need)

**Status:** done

- [x] Scope: the camera dataset, sidecars and their validation, camera eviction, replay checks, camera semantic scoring, and the C++ camera projection tool
- [x] The C++ projection tool is a Bazel target if it builds from sources in this repository; otherwise its existing build is kept and the reason recorded
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Implementation notes before integration merge:

- Built the `autonomy/camera` concept package and moved camera dataset, sidecar materialization/validation, camera eviction, replay checking, camera semantic scoring, camera publication/preprocess/replay scripts, camera coverage candidate JSON, and the C++ projection tool into it.
- Kept `project_camera.cc` on its existing CMake build instead of adding a Bazel C++ target because it still builds against external/generated inputs outside this repository: `/tmp/camera-source/camera_model.cc`, `/tmp/camera-source/include`, `/generated`, `/upstream/src`, and `/motion-build/libwod_motion_proto.a`.
- Updated in-repo callers, Bazel runfiles/test suites, and the layer declaration so camera imports use package paths such as `camera.camera_dataset`; `rg -n "sys\\.path" autonomy/camera` returned no matches.
- Moved tests beside their modules as `camera_dataset_test.py`, `camera_sidecars_test.py`, `camera_eviction_test.py`, `camera_semantic_scoring_test.py`, and `project_camera_test.py`; `project_camera_test.py` remains tagged `requires_live_gate`.
- Updated non-research Markdown references that pointed at the old camera paths. Files under `research/` were not modified.

Verification before first commit:

- `./bazelw test //autonomy/camera:all_tests --test_output=errors --cache_test_results=no` -> passed; 4 of 4 CPU camera tests passed.
- `./bazelw query 'kind(py_test, //autonomy/camera:*)'` -> listed `camera_dataset_test`, `camera_eviction_test`, `camera_semantic_scoring_test`, `camera_sidecars_test`, and `project_camera_test`.
- `./bazelw query 'attr(tags, requires_live_gate, //autonomy/camera:*)'` -> listed `//autonomy/camera:project_camera_test`.
- `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 16 layers`.
- `rg -n "pipeline\\.camera|segmentation\\.camera_semantic|camera-evaluation|test_camera_(dataset|sidecars|eviction|projection_cli)" --glob '!**/research/**'` -> no stale old camera package/test/evaluation references outside retained research evidence.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> expected failure for this concept move: `FAIL: 11 changed file(s) pinned by retained receipts`.

Pinned files changed and why:

- `camera-coverage-audit.candidate.json -> camera/camera-coverage-audit.candidate.json`: moved into the camera concept with the candidate metadata it describes.
- `camera-evaluation/CMakeLists.txt -> camera/CMakeLists.txt`: kept the existing projection-tool build beside the camera C++ source.
- `camera-evaluation/project_camera.cc -> camera/project_camera.cc`: moved the C++ camera projection tool into the camera concept.
- `evaluation/validate-real-camera-source.py -> camera/validate-real-camera-source.py`: moved the camera source checker into the camera concept.
- `pipeline/camera_replay_check.py -> camera/camera_replay_check.py`: moved camera replay validation into the camera concept.
- `pipeline/camera_sidecar_validate.py -> camera/camera_sidecar_validate.py`: moved camera sidecar validation into the camera concept.
- `pipeline/camera_sidecars.py -> camera/camera_sidecars.py`: moved camera sidecar materialization into the camera concept.
- `segmentation/camera_semantic_scoring.py -> camera/camera_semantic_scoring.py`: moved camera semantic scoring into the camera concept.
- `tests/test_camera_eviction.py -> camera/camera_eviction_test.py`: moved the camera eviction test beside its module and renamed to package test style.
- `tests/test_camera_projection_cli.py -> camera/project_camera_test.py`: moved the camera projection CLI test beside the C++ tool and kept it as the live-gate test.
- `tests/test_camera_sidecars.py -> camera/camera_sidecars_test.py`: moved the camera sidecar test beside its modules and renamed to package test style.

Pre-merge update after ticket 16 landed in `work/semantic-layout/integration`:

- Re-ran `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` immediately before the first commit. It still reports the camera moves above, and now also reports 16 pinned `detection/* -> pipeline/*` paths because this branch has not yet merged ticket 16's integration changes. Those detection paths were not changed by ticket 20.

Post-merge update:

- Merged `work/semantic-layout/integration` after ticket 16 landed. The only conflict was `autonomy/dataset/BUILD.bazel`; resolution kept both `//autonomy/camera:__pkg__` and `//autonomy/detection:__pkg__` in `DATASET_VISIBILITY`.
- `./bazelw test //autonomy/camera:all_tests --test_output=errors --cache_test_results=no` -> passed; 4 of 4 CPU camera tests passed after merge.
- `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 17 layers`.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> expected failure for this camera concept move only: `FAIL: 11 changed file(s) pinned by retained receipts`.

Integration review and repair, 2026-10-07:

- Independent camera review found that the scientific cohort orchestrator launched moved scripts by filename, losing sibling-package imports. Changed its camera and dataset stages to package-module invocation with the autonomy package root as cwd. Eight real CLI `--help` invocations passed with `PYTHONPATH` unset; inputs remain absolute and stage arguments and receipt checks are unchanged.
- Merged inspection integration `c86283b`. The full CPU gate then passed 147 of 148 tests; the source snapshot inventory test caught 16 camera Python sources missing from the Python freezer despite their inclusion in the Bazel snapshot target. Added the camera directory to the freezer inventory. The existing snapshot-target equality and sustained-source tests both passed uncached after the fix. Independent follow-up review found no remaining blocker.
- Camera tests: 4/4 passed uncached. Full GPU gate: 24/24 passed. Publication unit tests: 30 passed; publication audit and layer audit passed. Parallax and build-wrapper/toolchain files are byte-identical to `c86283b`, whose 17 Parallax tests passed, so that result is reused.
- Raw command logs and outcomes, including the original failing CPU gate, are retained at `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/camera-verification/`. `9-snapshot-fix.log` records the two passing regression checks.
- Legacy tree-pin check still reports expected camera migration impact (see `6.log`); retained research files remain byte-identical. This is not a successful legacy pin validation or a live camera gate run.
- The reviewed landing history uses a separate 19-file, byte-identical pure-move commit, followed by wiring with the same complete tree as this verified recovery candidate. The original branch remains preserved.
