# 17: Concept batch: `detection` variants and GPU workers

**What to build:** Model variants and their GPU workers live with the detector they vary, not in a directory named after the runtime.

**Blocked by:** 16 (Concept batch: `detection` core)

**Status:** ready-for-agent

- [x] Scope: normalisation and architecture variants and follow-ups, weight and decoder contracts, scored-proposal code, checkpoint value comparison, and the learning-curve, overfit and probe workers still in use
- [x] Workers that only a closed gate used are left for the studies batches and listed in the ticket's comments
- [x] The directory named after the GPU runtime no longer contains library code
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Implementation:

- Moved the active detection-variant modules and workers from `autonomy/gpu` into `autonomy/detection`: architecture contracts, architecture follow-ups, weight contract support, checkpoint value comparison, normalisation variants, scored proposal decoders, detector probe, architecture/follow-up/retain64 learning-curve workers, checkpoint audit workers, and the scored-decoder contract.
- Rewired active callers in `advanced`, `architecture`, `association`, `cohort`, and `tier1` to import `detection.*` by package path and to pin `detection/*` source paths in active harness/source-closure code.
- Added colocated Bazel tests beside the moved modules: `architecture_variants_test.py`, `architecture_followups_test.py`, `checkpoint_values_test.py`, `norm_variants_test.py`, and `scored_proposals_test.py`.
- Kept historical retained receipts and research files unchanged. The association provenance test fixture remaps retained manifest source identities into the new `detection/*` names for live contract validation without rewriting the retained manifest.
- `rg -n "sys\\.path|PYTHONPATH|from gpu|import gpu|gpu/|def sha|def _sha|hashlib\\.sha256|\\.is_file\\("` over the moved detection-variant files and their new tests produced no output. Existing non-ticket detection core tests still contain local test-only hash helpers.

Deferred closed-gate / procedure records left in `autonomy/gpu` for later studies batches:

- Rootfs/runtime files: `Dockerfile`, `Dockerfile.bazel-rootfs-v6`, `build.sh`, `build_bazel_rootfs_v6.sh`, `requirements.in`, `requirements.lock`, `verify-isolation.py`, `verify-live.py`.
- Procedure and legacy worker records: `audit-norm-checkpoint.py`, `audit-one-batch-bn-counterfactual.py`, `detector-optimizer-resource-probe.py`, `native-detector-probe.py`, `native-norm-learning-curve.py`, `native-one-batch-learning-curve.py`, `native-one-batch-overfit.py`, `native-optimizer-pilot.py`, `native-overfit.py`, `norm-variant-contract.py`, `one-batch-bn-counterfactual.py`, `pillar-probe.py`, `probe.py`, `range-frontend-native-probe.py`, `range-pillar-native-probe.py`, `sam-native-image-all-probe.py`, `sam-native-image-probe.py`, `sparse-window-native-probe.py`, and `validate-probe.py`.

Focused verification:

- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy/detection:scored_proposals_test --test_output=errors --cache_test_results=no` exited 0; 1/1 test passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test --config=cuda --test_tag_filters=requires_gpu //autonomy/detection:architecture_variants_test //autonomy/detection:architecture_followups_test //autonomy/detection:checkpoint_values_test //autonomy/detection:norm_variants_test --test_output=errors --cache_test_results=no` exited 0; 4/4 tests passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy:architecture__test_experiment_runner //autonomy:source_snapshot_targets_test --test_output=errors --cache_test_results=no` exited 0; 2/2 tests passed.
- A full `//autonomy/...` run initially found a stale association test fixture: `//autonomy:association__test_contract` failed 2 tests with `ValueError: incomplete baseline sources`. After remapping the moved `gpu/{architecture_followups,architecture_variants,norm_variants,scored_proposals_v3}.py` source identities to `detection/*` in the fixture, `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy:association__test_contract //autonomy:association__test_provenance --test_output=errors --cache_test_results=no` exited 0; 2/2 tests passed.

Final verification from candidate source head:

- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy/detection:scored_proposals_test --test_output=errors --cache_test_results=no` exited 0; 1/1 test passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test --config=cuda --test_tag_filters=requires_gpu //autonomy/detection:architecture_variants_test //autonomy/detection:architecture_followups_test //autonomy/detection:checkpoint_values_test //autonomy/detection:norm_variants_test --test_output=errors --cache_test_results=no` exited 0; 4/4 tests passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy:architecture__test_experiment_runner //autonomy:source_snapshot_targets_test --test_output=errors --cache_test_results=no` exited 0; 2/2 tests passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //autonomy/... --test_output=errors --cache_test_results=no` exited 0; 149/149 tests passed. Count delta versus ticket16 baseline is +1 CPU test from the new colocated `//autonomy/detection:scored_proposals_test`; no coverage was removed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test --config=cuda --test_tag_filters=requires_gpu //autonomy/... --test_output=errors --cache_test_results=no` exited 0; 28/28 tests passed. Count delta versus ticket16 baseline is +4 GPU-tagged tests from the new colocated architecture variants, architecture follow-ups, checkpoint values, and normalisation variants tests.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s ./bazelw --cache .bazel-cache test //parallax/... --test_output=errors --cache_test_results=no` exited 0; 17/17 tests passed.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s python3 -m unittest tests.test_publication_audit` exited 0; `Ran 30 tests ... OK`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s python3 scripts/publication_audit.py --root .` exited 0 with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4991}`.
- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s python3 autonomy/tools/layers.py` exited 0 with `PASS: 0 layering problem(s) across 16 layers`.
- `git diff --check` exited 0.
- `git diff --name-only 5ba7237 -- autonomy/research docs/research` exited 0 and produced no output; retained research files are unchanged.

Pin impact:

- `TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/runs/workers/sureal-semantic-17-20261007T085844Z/tmp timeout 900s python3 autonomy/tools/pins.py check --base 5ba7237` exited 1, as the required impact report. It reported 8 changed pinned source paths: `advanced/train.py`; `gpu/architecture_followups.py -> detection/architecture_followups.py`; `gpu/architecture_weight_contract.py -> detection/architecture_weight_contract.py`; `gpu/checkpoint_values.py -> detection/checkpoint_values.py`; `gpu/norm_variants.py -> detection/norm_variants.py`; `tier1/test_direction.py`; `tier1/train.py`; and `tier1/treatment_contract.py`.
- The moved-source pin failures are expected for this concept batch because retained receipts pin old source paths/bytes. The non-move entries are import-only updates needed so active callers use the concept package. This is not recorded as a green verification.

Diagnostic command notes:

- `./bazelw --output_user_root="$PWD/.bazel-cache" test ...` exited 2 because `bazelw` rejected raw `--output_user_root`; subsequent wrapper runs used `--cache .bazel-cache`.
- `./bazelw --cache .bazel-cache query 'tests(//autonomy/architecture:*)'` exited 7 because `autonomy/architecture` has no package BUILD file; the root-generated `//autonomy:*` targets are the correct entry points.
- An early focused CUDA run before tagging new torch-dependent tests exited 4 with all named targets excluded by filters; running the same tests outside CUDA then failed on missing `torch`. The final targets are tagged `requires_gpu` and pass under `--config=cuda`.

Unresolved limitations:

- No live scientific training/gate was launched, and no retained receipts or research artifacts were rewritten. Historical receipts remain historical records and still explain the pin impact above.
