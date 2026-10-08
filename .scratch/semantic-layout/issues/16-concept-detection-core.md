# 16: Concept batch: `detection` core

**What to build:** The detector and everything it needs lives under `detection`: anchors, box coding, the pillar encoder, the detector, its loss and decoder, and the export and adapter for native scoring.

**Blocked by:** 14 (Concept batch: `dataset`), 15 (Concept batch: `geometry`)

**Status:** done

- [x] Scope: anchor grid and assignment, box coding, pillar packing and encoder, packed point features, the pillar detector, detector geometry, loss and decoding, prediction records, detection export, the native detection adapter, and the training-box pipeline
- [x] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [x] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [x] Bazel visibility lets only the concepts above this one depend on it
- [x] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [x] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [x] Files under `research/` are unchanged

## Comments

Interim implementation and verification before the first ticket commit:

- Built `autonomy/detection` as the concept package for the detection core: anchors, box coding, pillar packing and encoder, packed point features, detector geometry, detector decode/loss/model, prediction records, native detection adapter/export, and the training-box pipeline.
- Moved the matching tests next to their modules as `*_test.py` and exposed them through `//autonomy/detection:all_tests`.
- Rewired active callers to import `detection.*` by package path. `rg -n "sys\\.path|PYTHONPATH" autonomy/detection || true` produced no output after removing the old replay sandbox `PYTHONPATH` setting.
- `git diff --name-only -- ':(glob)**/research/**' ':(glob)research/**' ':(glob)docs/research/**' ':(glob)autonomy/research/**' ':(glob)parallax/research/**'` produced no output; retained research evidence was not modified.
- `./bazelw test //autonomy/detection:all_tests --test_output=errors --cache_test_results=no --keep_going` passed 17/17 detection tests.
- `./bazelw test --config=cuda //autonomy/detection:detector_loss_test //autonomy/detection:packed_point_features_test //autonomy/detection:pillar_detector_test //autonomy/detection:pillar_encoder_test --test_output=errors --cache_test_results=no --keep_going` passed 4/4 GPU-tagged detection tests.
- `./bazelw test //autonomy:source_snapshot_targets_test //autonomy:tools__test_layers --test_output=errors --cache_test_results=no` passed 2/2.
- `python3 autonomy/tools/layers.py` passed with `PASS: 0 layering problem(s) across 15 layers`.
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no --keep_going` passed 148/148.
- `git diff --check` passed.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` reported `FAIL: 100 changed file(s) pinned by retained receipts`. This is expected for this concept batch because retained receipts pin the old source bytes while this ticket moves the detection core and import rewrites active callers. Pinned changes are: moved detection sources from `pipeline/{anchor_assignment,anchor_grid,box_coding,detection_export,detector_decode,detector_geometry,detector_loss,native_detection_adapter,packed_point_features,pillar_detector,pillar_encoder,pillar_packing,prediction_records,training_box_process,training_box_reference,training_box_replay_audit,training_box_resources,training_box_sender,training_box_sources,training_box_statistics,training_box_wire}.py` to `detection/`; moved matching tests from `tests/test_*.py` to `detection/*_test.py`; active import-only rewrites in `advanced`, `analysis`, `architecture/harness`, `association`, `cohort`, `evaluation`, `gpu`, `pipeline/range_pillar_hybrid.py`, `tests/test_range_pillar_hybrid.py`, and `tier1`; and the association provenance fixture remap needed to keep historical retained manifests untouched while the runtime contract uses `detection/*` keys.

Final post-merge verification:

- `git merge work/semantic-layout/integration` reported `Already up to date.`
- `./bazelw test //autonomy/...` passed: 148/148 tests pass.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` passed: 24/24 tests pass.
- `./bazelw test //parallax/...` passed: 17/17 tests pass.
- `python3 -m unittest tests.test_publication_audit` passed: `Ran 30 tests ... OK`.
- `python3 scripts/publication_audit.py --root .` passed with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4985}`.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` still reported `FAIL: 100 changed file(s) pinned by retained receipts`; the pinned files changed for the batch reasons recorded above.
- `git diff --name-only -- ':(glob)**/research/**' ':(glob)research/**' ':(glob)docs/research/**' ':(glob)autonomy/research/**' ':(glob)parallax/research/**'` produced no output.
- `git diff --check` passed.

Post-ticket-18 integration merge and review update:

- `git merge work/semantic-layout/integration` merged ticket 18. Conflicts were resolved by keeping `detection` and the newly merged `segmentation` as separate concept packages, placing `segmentation` below `detection` in `autonomy/tools/layers.py`, and wiring detection to depend on `//autonomy/segmentation:segmentation` for protobuf encoding and NLZ overlap.
- `autonomy/detection/training_box_replay.py` and `autonomy/detection/training_box_replay_audit.py` now call `evidence.source_snapshot.file_sha256` directly for file digests; the local production `sha`/`_sha` wrappers were removed.
- `./bazelw test //autonomy/detection:all_tests //autonomy/segmentation:all_tests --test_output=errors --cache_test_results=no --keep_going` passed: 31/31 tests pass.
- `python3 autonomy/tools/layers.py` passed with `PASS: 0 layering problem(s) across 16 layers`.
- `./bazelw test //autonomy/...` passed: 148/148 tests pass.
- `./bazelw test --config=cuda --test_tag_filters=requires_gpu //autonomy/...` passed: 24/24 tests pass.
- `./bazelw test //parallax/...` passed: 17/17 tests pass.
- `python3 -m unittest tests.test_publication_audit` passed: `Ran 30 tests ... OK`.
- `python3 scripts/publication_audit.py --root .` passed with `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4986}`.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` reported `FAIL: 98 changed file(s) pinned by retained receipts`; this remains expected for the detection move and import rewrites, with ticket 18 now present in the integration base.
- `git diff --cached --name-only -- ':(glob)**/research/**' ':(glob)research/**' ':(glob)docs/research/**' ':(glob)autonomy/research/**' ':(glob)parallax/research/**'` and `git diff --name-only -- ':(glob)**/research/**' ':(glob)research/**' ':(glob)docs/research/**' ':(glob)autonomy/research/**' ':(glob)parallax/research/**'` produced no output.
- `git diff --cached --check` and `git diff --check` passed.
