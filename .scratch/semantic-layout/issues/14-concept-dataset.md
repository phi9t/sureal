# 14: Concept batch: `dataset`

**What to build:** Everything about reading and storing Waymo data lives under `dataset`: readers, records, the scientific cohort's components and sidecars, archives and eviction.

**Blocked by:** 13 (Concept batch: `insula` and `evidence`)

**Status:** ready-for-agent

- [x] Scope: the TFRecord reader, sensor records, shard inventory, source integrity, staged sources, scientific dataset, components, sidecars and their readers and validators, scene and component archives, eviction policies, cohort selection, checkpoint and resume, and the cloud-storage setup commands
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Implemented ticket 14 by moving the dataset-owned sources into `autonomy/dataset/`, adding the concept Bazel package, moving tests beside their modules as `foo_test.py`, and updating live callers to import moved modules as `dataset.*`. The moved command scripts now resolve component-root files through `Path(__file__).resolve().parents[1]` and use `dataset/...` paths for dataset-owned manifests, locks and GCS commands. File SHA-256 helpers and regular-file checks in moved library code now come from `evidence.source_snapshot`.

Verification before the concept repair commit:

- `./bazelw test //autonomy/dataset:concept_import_test --test_output=errors --cache_test_results=no` -> PASS, 1/1 test.
- `./bazelw test //autonomy/dataset:all_tests --test_output=errors --cache_test_results=no --keep_going` -> PASS, 22/22 tests.
- `python3 autonomy/tools/layers.py` -> `PASS: 0 layering problem(s) across 13 layers`.
- `rg -n "sys\\.path" autonomy/dataset || true` -> no matches.
- `git status --short | rg '(^|/)research/'` -> no matches.
- `git diff --check` -> no output.

Pin report before commit:

- Command: `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration`
- Result: `FAIL: 68 changed file(s) pinned by retained receipts`
- Reason this is expected for this batch: the semantic-layout spec says the pin report is a migration measurement, and this ticket deliberately moves pinned dataset files after source pins were changed to refer to snapshots rather than the working tree.
- Dataset concept moves: `dataset.lock.json -> dataset/dataset.lock.json`, `gcs.sh -> dataset/gcs.sh`, `setup-gcs.sh -> dataset/setup-gcs.sh`, `scientific-acquisition.candidate.json -> dataset/scientific-acquisition.candidate.json`, `scientific-cohort.candidate.json -> dataset/scientific-cohort.candidate.json`, `pipeline/bounded_sidecar_eviction.py -> dataset/bounded_sidecar_eviction.py`, `pipeline/cohort_checkpoint.py -> dataset/cohort_checkpoint.py`, `pipeline/cohort_resume.py -> dataset/cohort_resume.py`, `pipeline/cohort_selection.py -> dataset/cohort_selection.py`, `pipeline/component_archive.py -> dataset/component_archive.py`, `pipeline/component_archive_validate.py -> dataset/component_archive_validate.py`, `pipeline/compressed_component_archive.py -> dataset/compressed_component_archive.py`, `pipeline/compressed_component_archive_validate.py -> dataset/compressed_component_archive_validate.py`, `pipeline/compressed_sidecar_eviction.py -> dataset/compressed_sidecar_eviction.py`, `pipeline/scene_archive.py -> dataset/scene_archive.py`, `pipeline/scene_archive_validate.py -> dataset/scene_archive_validate.py`, `pipeline/scientific_admission.py -> dataset/scientific_admission.py`, `pipeline/scientific_component.py -> dataset/scientific_component.py`, `pipeline/scientific_dataset.py -> dataset/scientific_dataset.py`, `pipeline/scientific_preparation.py -> dataset/scientific_preparation.py`, `pipeline/scientific_publication.py -> dataset/scientific_publication.py`, `pipeline/scientific_sidecar_reader.py -> dataset/scientific_sidecar_reader.py`, `pipeline/scientific_sidecar_validate.py -> dataset/scientific_sidecar_validate.py`, `pipeline/scientific_sidecars.py -> dataset/scientific_sidecars.py`, `pipeline/sensor_records.py -> dataset/sensor_records.py`, `pipeline/shard_inventory.py -> dataset/shard_inventory.py`, `pipeline/sidecar_eviction.py -> dataset/sidecar_eviction.py`, `pipeline/tfrecord_reader.py -> dataset/tfrecord_reader.py`, `pipeline/verified_eviction.py -> dataset/verified_eviction.py`. Reason: these files implement the ticket's dataset concept scope.
- Dataset test moves: `tests/test_cohort_checkpoint.py -> dataset/cohort_checkpoint_test.py`, `tests/test_cohort_selection.py -> dataset/cohort_selection_test.py`, `tests/test_component_archive.py -> dataset/component_archive_test.py`, `tests/test_gcs_bootstrap.py -> dataset/gcs_bootstrap_test.py`, `tests/test_scene_archive.py -> dataset/scene_archive_test.py`, `tests/test_scene_archive_validation.py -> dataset/scene_archive_validate_test.py`, `tests/test_scientific_admission.py -> dataset/scientific_admission_test.py`, `tests/test_scientific_component.py -> dataset/scientific_component_test.py`, `tests/test_scientific_dataset.py -> dataset/scientific_dataset_test.py`, `tests/test_scientific_preparation.py -> dataset/scientific_preparation_test.py`, `tests/test_scientific_publication.py -> dataset/scientific_publication_test.py`, `tests/test_scientific_sidecar_reader.py -> dataset/scientific_sidecar_reader_test.py`, `tests/test_scientific_sidecar_validation.py -> dataset/scientific_sidecar_validate_test.py`, `tests/test_scientific_sidecars.py -> dataset/scientific_sidecars_test.py`, `tests/test_sensor_records.py -> dataset/sensor_records_test.py`, `tests/test_shard_inventory.py -> dataset/shard_inventory_test.py`, `tests/test_sidecar_eviction.py -> dataset/sidecar_eviction_test.py`, `tests/test_staged_source.py -> dataset/staged_source_test.py`, `tests/test_tfrecord_reader.py -> dataset/tfrecord_reader_test.py`, `tests/test_verified_eviction.py -> dataset/verified_eviction_test.py`. Reason: the spec requires moved tests to sit beside moved modules as Bazel `py_test` targets.
- Pinned compatibility edits outside `dataset/`: `advanced/range_cache_contract.py`, `cohort/gcs_metadata_get.py`, `cohort/overfit-point-worker.py`, `cohort/raw_reconstruct.py`, `cohort/raw_reconstruct_v3.py`, `explorer/joint_render.py`, `pipeline/camera_dataset.py`, `pipeline/camera_eviction.py`, `pipeline/inspection_validate.py`, `pipeline/inspection_views.py`, `pipeline/reconstruction_probe.py`, `pipeline/reconstruction_validate.py`, `pipeline/scientific_reconstruction.py`, `pipeline/scientific_scene_validate.py`, `pipeline/semantic_archive_support.py`, `pipeline/training_box_job.py`, `tests/test_camera_dataset.py`, `tests/test_scientific_reconstruction.py`, `tests/test_scientific_scene_validate.py`. Reason: these live callers or tests import dataset-owned modules or use the moved `dataset/gcs.sh` / `dataset/dataset.lock.json` paths, and keeping them stale would break the moved concept package.
