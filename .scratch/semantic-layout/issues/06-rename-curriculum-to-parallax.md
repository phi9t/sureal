# 06: Rename the curriculum to `parallax/`

**What to build:** The 3D reconstruction curriculum lives at top-level `parallax/`, with its pipeline, Insula definitions, tests and research directly beneath it. Its runner, tests, CI job and the publication audit all work from the new location.

**Blocked by:** 05 (The curriculum's tests run under Bazel, in place)

**Status:** ready-for-agent

- [x] The move is one commit containing only renames, so history follows every file
- [x] A following commit updates the paths that code, the publication audit and its test, and CI depend on
- [x] The curriculum's Bazel tests pass at the new location and its runner lists and runs a smoke module
- [x] The publication audit and its unit test pass
- [x] Files under the curriculum's `research/` are byte-identical
- [x] The wrapper selects the curriculum rootfs for `//parallax/...` targets, and a target pattern that spans both components (for example `//...`) either runs each component in its own rootfs or is refused with a clear message; it must not silently run curriculum tests in the perception rootfs
- [x] The curriculum runner script's import bootstrap (added in ticket 05 for Bazel's safe-path mode) is simplified to setting the import path, with the Bazel tests still passing

## Comments

Built:

- Moved `experiments/3d-pathway/` to top-level `parallax/` in pure rename commit `7835009`.
- Updated live code, Bazel wrapper routing, publication audit, publication workflow, runner docs, and tests to use `parallax/`.
- Kept the existing shared curriculum rootfs/cache identity under `3d-pathway` to avoid modifying shared external state.
- Simplified `parallax/run.sh` to export `PYTHONPATH="${PIPELINE}${PYTHONPATH:+:${PYTHONPATH}}"` and execute `pipeline/cli.py` directly.
- Added wrapper tests for `//parallax/...` rootfs selection and broad-pattern refusal.
- Updated the Insula Scout environment verifier to import moved parallax pipeline code and refreshed its source-lock digest.
- Fixed final-review finding in `parallax/README.md` link to `../docs/3d-reconstruction-pathway.md` in commit `3401700`.

Verification:

- `git diff --cached --summary` before commit `7835009` -> every moved file reported as a 100% rename.
- `git diff --cached --numstat` before commit `7835009` -> every moved file reported `0	0`.
- `PYTHONPATH=experiments/waymo-perception python3 -m unittest experiments/waymo-perception/tests/test_bazel_wrapper.py -v` -> `Ran 5 tests`, `OK`.
- `python3 -m unittest tests.test_publication_audit -v` -> `Ran 24 tests in 14.371s`, `OK`.
- `python3 -m unittest experiments.insula-scout.tests.test_insula_contract.InsulaContractTest.test_foundation_environment_plan_is_fully_content_addressed experiments.insula-scout.tests.test_insula_contract.InsulaContractTest.test_build_exposes_the_same_locked_plan_without_building -v` -> `Ran 2 tests`, `OK`.
- `python3 scripts/publication_audit.py --root .` -> `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4964}`.
- `./bazelw --emit-plan test //parallax:test_classical` -> selected `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v1` and `--output_base=/outputs/output-base-3d-pathway`.
- `./bazelw --emit-plan test //...` -> refused with `target pattern spans autonomy and parallax; run each component separately so the wrapper can select the correct rootfs`.
- `./bazelw test --nocache_test_results //parallax/...` -> `Executed 17 out of 17 tests: 17 tests pass.`
- `bwrap ... --chdir /experiment -- parallax/run.sh list --json` in the curriculum rootfs -> listed 15 modules, ids `01` through `15`.
- `bwrap ... --setenv SURFLO_PATHWAY_CACHE_ROOT /outputs/runner-smoke --chdir /experiment -- parallax/run.sh run --module 01 --profile smoke --run-id ticket06-smoke` in the curriculum rootfs -> wrote `/outputs/runner-smoke/runs/ticket06-smoke/01`.
- `for path in parallax/research/*; do rel=${path#parallax/}; git show HEAD~2:experiments/3d-pathway/${rel} | cmp -s - "$path" || exit 1; done` -> `PASS: parallax/research files byte-identical to HEAD~2 old paths`.
- `python3 experiments/waymo-perception/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- `PYTHONPATH=parallax/pipeline python3 -m unittest parallax.tests.test_documentation.SurveyContractTest.test_every_module_has_reproduction_structure_sources_and_command parallax.tests.test_documentation.AuditContractTest.test_offline_audit_validates_citations_assets_and_terminology -v` after the final review fix -> `Ran 2 tests`, `OK`.
- `git diff --check` -> exit 0, no output.

Pinned files changed:

- None. No `.py` files under `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` were added, changed, or removed.

Reviewer notes:

- Direct host execution of the moved runner is not a valid gate on this host because host Python lacks the pinned NumPy dependency; runner list and smoke execution were verified inside the curriculum rootfs.
- One read-only final review found a broken moved README relative link; it was fixed and committed separately as `3401700`.
