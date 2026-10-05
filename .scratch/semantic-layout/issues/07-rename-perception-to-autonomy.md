# 07: Rename the perception program to `autonomy/`

**What to build:** The perception research program lives at top-level `autonomy/`, moved whole. Everything that ran before the move runs after it: the Bazel tests, the architecture experiment catalog, the tracker and journal, the publication audit and CI. The internal structure is not changed in this ticket.

**Blocked by:** 03 (Every perception CPU test runs under Bazel, in place), 04 (Torch tests run under Bazel in the GPU rootfs)

**Status:** ready-for-agent

- [x] The move is one commit containing only renames
- [x] A following commit updates every hard-coded occurrence of the old path in code: the architecture harness drivers, the gate scripts still in use, the rootfs build script, the publication audit and its test, the collaboration tests and CI
- [x] Sandbox mount points inside the rootfs are unchanged
- [x] The default Bazel run passes the same modules as before the move, and the GPU configuration runs the same torch modules
- [x] The architecture runner lists and shows experiments from the new location; the journal's hash chain verifies
- [x] The context map points at the glossary's new location and the perception ADR has moved with the tree
- [x] Files under `research/` are byte-identical, and the pin report for the content-editing commit is attached to the ticket

## Comments

Built:

- Pure move commit: `93e64a0b1edebd48a39d1ae4ab382ff07668ad5f`.
- Content-editing commit: `e91e9b4`, updating active `autonomy/` labels and path literals in the Bazel wrapper, architecture harness and snapshot runner, active cohort snapshot gates, tracker command output, rootfs build helper, publication audit/test, collaboration tests, and viewer generated-path literals.
- Rootfs sandbox conventions remain `/experiment`, `/source`, and `/outputs`. The Bazel wrapper still provides legacy in-rootfs child mounts such as `/experiment/cohort` and `/experiment/gpu`; it also exposes the moved package at `/experiment/autonomy` for `//autonomy/...` Bazel labels.

Verification:

- `git show --numstat 93e64a0b1edebd48a39d1ae4ab382ff07668ad5f` showed all rename entries with `0 0`.
- `rg -n "experiments/waymo-perception|//experiments/waymo-perception" .github bazelw MODULE.bazel autonomy tests parallax scripts --glob '!autonomy/research/**' --glob '!**/research/**' --glob '!*.md' --glob '!*.lock' --glob '!*.snapshot' --glob '!*.txt'` returned no active code/config matches.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 autonomy/architecture/test_experiment_runner.py -v` passed: 13 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 autonomy/tests/test_bazel_wrapper.py -v` passed: 6 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 tests/test_publication_audit.py -v` passed: 25 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/tests/collab python3 tests/collab/test_runtime.py -v` passed: 2 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/tests/collab python3 tests/collab/test_cli.py -v` passed: 11 tests. The suite still emits existing sqlite ResourceWarnings.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/tests/collab python3 tests/collab/test_live.py -v` passed: 15 tests. The suite still emits existing sqlite ResourceWarnings.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/tracking/test_journal.py -v` passed: 5 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/tracking/test_projection.py -v` passed: 4 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/tracking/test_publish.py -v` passed: 1 test.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/architecture.py list && TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/architecture.py show residual_bev && TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy python3 autonomy/tracking/cli.py verify-journal` listed the moved catalog, showed `residual_bev`, and printed `VERIFIED journal entries 129`.
- `./bazelw query 'kind(py_test, //autonomy/...)'` and the saved pre-move inventory both found 179 Python test targets after normalizing labels.
- `./bazelw query 'attr("tags", "requires_gpu", kind(py_test, //autonomy/...))'` and the saved pre-move inventory both found 24 GPU-tagged Python test targets after normalizing labels.
- `TMPDIR=$PWD/.bazel-cache/tmp ./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` passed: `Executed 138 out of 138 tests: 138 tests pass`.
- `TMPDIR=$PWD/.bazel-cache/tmp ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` passed: `Executed 24 out of 24 tests: 24 tests pass`.
- Research byte identity check against `work/semantic-layout/integration:experiments/waymo-perception/research` passed: 2,276 old files, 2,276 new files, 0 missing, 0 extra, 0 changed.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 scripts/publication_audit.py --root .` passed with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4969}`.
- `git diff --check` passed before the content commit.

Pin and protected-file record:

- Pin guard before content commit: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- Pinned files changed: none.
- Protected active `.py` files changed under the moved path: `autonomy/cohort/re_admit_physical.py`, `autonomy/cohort/run.py`, `autonomy/cohort/run_balanced.py`, `autonomy/cohort/score.py`, `autonomy/cohort/score_balanced.py`, `autonomy/cohort/score_parallel.py`, and `autonomy/cohort/score_v2.py`. Reason: their frozen source-package lookup changed from `source/experiments/waymo-perception` to `source/autonomy` after the whole-directory move.
- No protected `.py` files changed under `autonomy/pipeline`, `autonomy/gpu`, `autonomy/tier1`, or `autonomy/resources`.

Post-review fix:

- Clean-context review found that `autonomy/architecture/experiment_runner.py` still resolved relative `worker_hashes` from `package.parents[1]/.scratch`, which is stale after moved snapshots use `source/autonomy`. Commit `9d4695c` changes that lookup to `package.parent/.scratch` and adds a regression test for `source/autonomy` plus `source/.scratch/worker.py`.
- The same commit updates active agent domain wayfinding from `experiments/waymo-perception/docs/adr/` to `autonomy/docs/adr/`.
- `TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 autonomy/architecture/test_experiment_runner.py -v` passed: 14 tests.
- `TMPDIR=$PWD/.bazel-cache/tmp ./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` passed: `Executed 138 out of 138 tests: 138 tests pass`.
- `TMPDIR=$PWD/.bazel-cache/tmp ./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` first rerun had one flaky failure in `//autonomy:cohort__test_sustained_worker_guard` because the test compared all of `/outputs` while Bazel wrote repository-cache files there concurrently. The failed target passed alone, and a second full GPU rerun passed: `Executed 24 out of 24 tests: 24 tests pass`.
- Final guard before this record: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration && TMPDIR=$PWD/.bazel-cache/tmp PYTHONPATH=$PWD:$PWD/autonomy:$PWD/tests/collab python3 scripts/publication_audit.py --root . && git diff --check` passed with pin guard `PASS: 0 changed file(s) cited by retained receipts` and publication audit `status: pass`.
