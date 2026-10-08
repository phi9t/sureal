# Ticket 26 Closeout Fixes

Base: `916f8c012e403f7f4f3d50ff801b46eaf24745cf`

Worker branch: `worker/t26-closeout-fixes`

## Decisions

- `autonomy/detection/expanded_batch/` was active detector library code, not a
  closed procedure record. I renamed it to
  `autonomy/detection/architecture_adaptations/` because the package implements
  detector architecture adaptation mechanisms: grid resolution controls, ragged
  pillars, point-token interaction, range fusion and sparse BEV attention.
- Active `fixed_batch` module names in `detection/` were also study-stage names.
  I renamed them to detector recipe names:
  `detector_recipe_catalog.py` and `detector_recipe_models.py`.
- `dataset/expanded_batch_observations.py` was an active observation loader, so
  I renamed it to `dataset/detector_observations.py`.
- `autonomy/studies/{balanced16,expanded_batch,fixed_batch}/` are study homes and
  were left unchanged. Procedure records and research evidence were not edited.
- The shared regular-file implementation remains
  `evidence.source_snapshot.require_regular_file`; the new thin boolean predicate
  is `evidence.source_snapshot.is_regular_file`.
- `resources/resource_release_plan.py` no longer duplicates the `path.is_file()`
  check, but still rejects symlinked payload ancestors under the source root.
  `resource_release_plan_test.py` proves that ancestor check is independent of
  `require_regular_file`.

## Rename Map

| Old | New |
| --- | --- |
| `autonomy/detection/expanded_batch/` | `autonomy/detection/architecture_adaptations/` |
| `autonomy/detection/expanded_batch:expanded_batch` | `autonomy/detection/architecture_adaptations:architecture_adaptations` |
| `autonomy/detection/fixed_batch_catalog.py` | `autonomy/detection/detector_recipe_catalog.py` |
| `autonomy/detection/fixed_batch_catalog_test.py` | `autonomy/detection/detector_recipe_catalog_test.py` |
| `autonomy/detection/fixed_batch_models.py` | `autonomy/detection/detector_recipe_models.py` |
| `autonomy/dataset/expanded_batch_observations.py` | `autonomy/dataset/detector_observations.py` |
| `autonomy/dataset/expanded_batch_observations_test.py` | `autonomy/dataset/detector_observations_test.py` |

## Moved File Hashes

Unchanged content after rename:

| Old | New | Before | After |
| --- | --- | --- | --- |
| `detection/fixed_batch_catalog.py` | `detection/detector_recipe_catalog.py` | `4a33cc1719c4a32203ee6574301854c7c2cab8a51fc09b3cdd9cb3fcb90f550f` | `4a33cc1719c4a32203ee6574301854c7c2cab8a51fc09b3cdd9cb3fcb90f550f` |
| `detection/fixed_batch_models.py` | `detection/detector_recipe_models.py` | `d1da1ab694ed4bf08730854c05275fb0a813c18dbd56036e7bdf771be2936c17` | `d1da1ab694ed4bf08730854c05275fb0a813c18dbd56036e7bdf771be2936c17` |
| `detection/expanded_batch/packing.py` | `detection/architecture_adaptations/packing.py` | `7a83c385b2330d4c38afda9a3b9d9066f50b4b9691fe01ce34362ae8b16318e1` | `7a83c385b2330d4c38afda9a3b9d9066f50b4b9691fe01ce34362ae8b16318e1` |
| `detection/expanded_batch/point_modules.py` | `detection/architecture_adaptations/point_modules.py` | `2596eb4c164bff152402ea156a553c3a79cc37f2f5679965da70443e37452606` | `2596eb4c164bff152402ea156a553c3a79cc37f2f5679965da70443e37452606` |
| `detection/expanded_batch/sparse_sets.py` | `detection/architecture_adaptations/sparse_sets.py` | `c27ca6f6894933df75c77ca7195a956990ec2927c6cb5e86a324b8d750d025fe` | `c27ca6f6894933df75c77ca7195a956990ec2927c6cb5e86a324b8d750d025fe` |
| `dataset/expanded_batch_observations.py` | `dataset/detector_observations.py` | `34bad4beccef1436134fafc63c6887d7c9a271f3e3b295f042755f720536e018` | `34bad4beccef1436134fafc63c6887d7c9a271f3e3b295f042755f720536e018` |

Import or BUILD-label-only changes after rename:

| Old | New | Before | After |
| --- | --- | --- | --- |
| `detection/expanded_batch/BUILD.bazel` | `detection/architecture_adaptations/BUILD.bazel` | `368b6d2864e5f0f7e46bc55a0938671d3068b81603f029c2835c27bf3089d541` | `a4109db430f050be7d872c6bab71685e40fabbf437d7ebe9974b1d1a51f90af6` |
| `detection/expanded_batch/catalog.py` | `detection/architecture_adaptations/catalog.py` | `e014d171ebb4aee240d1334f636b127d5e0295817794467016321d3cbfd0daf3` | `29db03601448d6fd3540d9fbf27b1d8c0d3da62c0e27883cf3c8b5a545e2f12c` |
| `detection/expanded_batch/models.py` | `detection/architecture_adaptations/models.py` | `92249a6d3deb93cf77fe90330d2d7359b23587066279db7a44d7d34947fcb682` | `e380c5094cb54556d8ebf8f3489d2e9417d94546091d382589f256632a844ec2` |
| `detection/expanded_batch/spatial_modules.py` | `detection/architecture_adaptations/spatial_modules.py` | `f22e0cc6b6cee57272e82155399cfb8b9b9cca1e9a42e45aa9231dda3210e03d` | `d075008fc0ab372c9b41488160f4ccd81c9bd5e4fe86ac6f5e1a8dba3a3ab924` |
| `detection/fixed_batch_catalog_test.py` | `detection/detector_recipe_catalog_test.py` | `381436a808db5d4528ff0f994b59d4e925b81751ac6bc255564a717c5a9c6065` | `d1d16439f6aca470364dfa5e365f37487568ec409dcaae9722897dbfde034354` |
| `dataset/expanded_batch_observations_test.py` | `dataset/detector_observations_test.py` | `82994da1979c25bea5769f5923c96392035a55b432c77a8888386daa293afeaf` | `190620edfc02c242c60200ae5f08ed54f53abc04069d39c37b44e06568b6731e` |

The remaining moved tests changed only imports. The package BUILD file changed
only package/target labels and the library target name.

## Audit Results

- Active allowed-path grep for `expanded_batch`, `fixed_batch`,
  `expanded_batch_observations`, `fixed_batch_catalog` and `fixed_batch_models`
  across `autonomy/{BUILD.bazel,detection,dataset,range_view,training_execution}`
  plus source snapshot docs/tests exited 1 with no output.
- Directory audit:
  `find autonomy -maxdepth 3 ... | rg '(^|/)(gpu|tests|scripts|tier1|advanced|cohort|runtime|pipeline|balanced16|expanded_batch|fixed_batch|procedure_records)$'`
  now returns only `autonomy/studies/<study>` homes and
  `procedure_records/`.
- Active allowed file-name audit across detection, dataset, range view,
  resources, retention, training execution and motion for
  `balanced16|expanded_batch|fixed_batch` exited 1 with no output.
- Regular wrapper audit:
  `rg -n '^def (regular|regular_children|regular_files)\\b' autonomy ...`
  exited 1 with no output.
- Generic helper audit:
  `rg -n '^def (require_regular_file|is_regular_file|file_digest|file_sha256)\\b' autonomy/evidence/source_snapshot.py`
  shows only:
  `require_regular_file`, `is_regular_file`, `file_digest`, and `file_sha256`.
  `file_digest` is the single generic file-digest implementation;
  `file_sha256` is the existing SHA-256 convenience wrapper in the same module.
- Non-evidence `hashlib.file_digest` audit finds only
  `autonomy/resources/resource_archive.py`, where it hashes tar-member streams,
  not filesystem paths.

## Verification

Cache seed:

- Command:
  `cp -a /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/final26-review/.bazel-cache .bazel-cache`
- Exit code: 0
- Result: local `.bazel-cache` present, `461M`.

Focused red/green checks:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.evidence.source_snapshot_test.SourceSnapshotTests.test_file_digest_and_regular_file_check_reject_symlinks autonomy.resources.resource_release_plan_test.RetentionTests.test_payload_ancestor_symlink_is_rejected_independently_of_regular_file_helper`
- Exit code: 0
- Result: `Ran 2 tests ... OK`.

Focused Bazel checks:

- Command:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evidence:source_snapshot_test //autonomy/resources:resource_release_plan_test //autonomy/resources:sources_test //autonomy/retention:all_tests //autonomy/motion:all_tests //autonomy/dataset:detector_observations_test //autonomy/detection:detector_recipe_catalog_test //autonomy/detection/architecture_adaptations:packing_test`
- Exit code: 0
- Result: `Executed 15 out of 15 tests: 15 tests pass.`

Source-closure genquery check:

- Command:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy:source_snapshot_targets_test`
- Exit code: 0
- Result: `Executed 1 out of 1 test: 1 test passes.`

Full default run:

- Command:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
- Final exit code: 0
- Final result: `Executed 152 out of 152 tests: 152 tests pass.`
- Baseline comparison: baseline was 152; delta is 0. The renames changed labels
  but did not change the number of default test targets.

GPU target inventory:

- Command:
  `./bazelw query 'attr(tags, requires_gpu, tests(//autonomy/...))'`
- Exit code: 0
- Count: 28 targets.
- Renamed labels include
  `//autonomy/dataset:detector_observations_test` and
  `//autonomy/detection/architecture_adaptations:{models_test,point_modules_test,sparse_sets_test}`.

CUDA build:

- Command: `./bazelw build --config=cuda //autonomy/...`
- Exit code: 1
- Result: pre-Bazel wrapper failure,
  `ValueError: GPU device not found: /dev/nvidia1`.
- Coordinator reply at `2026-10-08T00:58:27Z`: this is expected in this worker;
  do not retry or work around it; coordinator will run CUDA build/test on the
  final commit. The 28-target `requires_gpu` query is sufficient from this
  worker.

Repo hygiene/publication audit:

- I found no dedicated publication-audit Bazel target in the checked
  `autonomy/BUILD.bazel`, `autonomy/insula/BUILD.bazel`,
  `autonomy/inspection/BUILD.bazel`, `autonomy/evidence/BUILD.bazel`,
  `autonomy/resources/BUILD.bazel` or `autonomy/dataset/BUILD.bazel` files.
- `//autonomy/inspection:viewer__repo_hygiene_test` exists and passed as part of
  the full `//autonomy/...` run.
- `git diff --check` exit code: 0.

Pin impact:

- Command:
  `(cd autonomy && python3 -m evidence.pins check --base work/semantic-layout/integration)`
- Exit code: 1
- Result: failed before producing pin impact because this private workspace has
  no `work/semantic-layout/integration` revision:
  `fatal: Needed a single revision`, from
  `git diff --name-status -M20% -z work/semantic-layout/integration`.
- No pins, receipts, research records or procedure records were edited.

## Not Checked Here

- CUDA build/test did not run on this CPU-only worker because `/dev/nvidia1` is
  unavailable and the coordinator explicitly said not to retry or bypass it.
- Pin-impact reporting against `work/semantic-layout/integration` could not run
  because that ref is absent in this private workspace.

## Follow-up

Worker branch: `worker/t26-closeout-followup`

Base: `38bdd76f09262e611ea27b7a4daf53d8d7b6efe3`

Changes:

- Updated the association contract's active baseline source requirements from
  `detection/fixed_batch_catalog.py` and `detection/fixed_batch_models.py` to
  `detection/detector_recipe_catalog.py` and
  `detection/detector_recipe_models.py`.
- Updated the provenance test's historical manifest reconciliation map so
  `tier1/catalog.py` and `tier1/models.py` now map directly to the current
  detector recipe paths. The frozen research manifest was not edited.
- Updated the expanded-batch study README's active library prose and catalog
  import example to reference `detection/architecture_adaptations/` and
  `dataset/detector_observations.py`.

Residual-reference audit:

- Command:
  `rg -n "(detection/(fixed_batch_(models|catalog)\\.py|expanded_batch)|dataset/expanded_batch_observations\\.py|//autonomy/detection/expanded_batch|fixed_batch_catalog|fixed_batch_models|expanded_batch_observations|detection\\.expanded_batch)" . -g '!autonomy/research/**' -g '!autonomy/studies/*/procedure_records/**' -g '!docs/research/**' -g '!docs/refactor-finish/**' -g '!.scratch/**' -g '!.bazel-cache/**'`
- Exit code: 1.
- Result: no active-tree references to the old detector/dataset paths or the
  old `//autonomy/detection/expanded_batch` label.

Verification:

- Cache seed:
  `cp -a /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/final26-review/.bazel-cache .bazel-cache`
  was already present for this follow-up workspace as a single local cache copy.
- Focused command:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/association/... //autonomy:source_snapshot_targets_test`
- Focused exit code: 0.
- Focused result: `Executed 3 out of 3 tests: 3 tests pass.`
- Full default command:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
- Full default exit code: 0.
- Full default result: `Executed 152 out of 152 tests: 152 tests pass.`
- Baseline comparison: baseline was 152; delta is 0.
