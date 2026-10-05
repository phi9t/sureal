# 09: Evidence module: snapshot, fetch and verify

**What to build:** A researcher can take a source snapshot of a build target, get its digest, and later verify a receipt's source pins against that snapshot without the working tree. One module owns this, together with the shared file-digest and regular-file helpers that are currently copied across the codebase.

**Blocked by:** 07 (Rename the perception program to `autonomy/`)

**Status:** done

- [x] Taking a snapshot of a Bazel target archives exactly that target's transitive sources and returns the archive's digest
- [x] The archive is deterministic: the same sources produce the same digest regardless of timestamps, ownership or file order
- [x] Changing, adding or removing any source in the target's closure changes the digest
- [x] Storage is behind an interface; a local-directory adapter stores and fetches snapshots keyed by digest
- [x] Verification passes for a receipt and its snapshot, fails for an altered snapshot, and fails explicitly for a missing one
- [x] Verification never reads the working tree; a test proves this by verifying after the sources are deleted
- [x] The module exposes one file-digest function and one regular-file check, with tests covering symlinks

## Comments

Built `autonomy/evidence/source_snapshot.py` as the shared evidence module. It snapshots explicit repository-local Bazel source-file inputs reached through target `srcs` and `data` closures, writes deterministic uncompressed tar archives, returns source pins and one snapshot digest, verifies receipts against fetched snapshots without consulting the working tree, and exposes the shared SHA-256 file digest plus regular non-symlink file guard.

Added `autonomy/evidence/source_snapshot_test.py` with tests for target snapshots, filegroup-style rule labels in data closures, deterministic archive metadata/order, a golden raw-tar digest fixture, changed/added/removed source digests, local digest-keyed storage with unique same-directory temp files, missing/corrupt snapshots, receipt verification from the stored snapshot after deleting sources, current-only receipt schema, and symlink rejection on source files, store reads, and store writes. Updated `autonomy/BUILD.bazel` so concept-local sibling `*_test.py` files are discovered as Bazel tests.

Verification:
- `./bazelw test //autonomy:evidence__source_snapshot_test --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes.`
- Host digest smoke with `python3 - <<'PY' ... archive_sources(fixed fixture) ... PY` -> `host_source_snapshot_sha256=26d7ae75a8a99ed88f3e5350159faf024a632dd3deb70f403fa664b959c6fd18`, `host_archive_bytes=10240`.
- CPU rootfs golden digest check with `./bazelw test //autonomy:evidence__source_snapshot_test --test_filter=SourceSnapshotTests.test_source_snapshot_digest_matches_uncompressed_tar_golden --test_output=errors --cache_test_results=no` -> `Executed 1 out of 1 test: 1 test passes`; the test asserts the same literal digest `26d7ae75a8a99ed88f3e5350159faf024a632dd3deb70f403fa664b959c6fd18`.
- `./bazelw query --output=label 'kind("source file", filter("^//", labels("srcs", deps(//autonomy:evidence__source_snapshot_test)) union labels("data", deps(//autonomy:evidence__source_snapshot_test))))' | rg '^//autonomy:(BUILD.bazel|evidence/source_snapshot.py|evidence/source_snapshot_test.py)$'` -> printed `//autonomy:BUILD.bazel`, `//autonomy:evidence/source_snapshot.py`, and `//autonomy:evidence/source_snapshot_test.py`.
- `./bazelw test //autonomy/... --cache_test_results=no` -> `Executed 139 out of 139 tests: 139 tests pass.`
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- `python3 - <<'PY' ... snapshot_bazel_target('//autonomy:anchor_grid_test') and snapshot_bazel_target('//autonomy:tracking__test_journal') ... PY` -> both snapshots currently have `source_files=714`, `digest=19b2167a5dec1329ad9a08c333d6a6ea660749c2a4a36998ec83764a1bb87d5a`, and `archive_bytes=3553280`.

Reviewer notes:
- HDFS storage is intentionally not included; ticket 10 owns that adapter.
- Architecture runner and sustained-run consumers are intentionally not rewritten here; tickets 11 and 12 own those integrations.
- Known limitation: `//autonomy:anchor_grid_test` and `//autonomy:tracking__test_journal` currently snapshot the same 714 files with the same digest because the bridge runner still gives each test the whole package as data. Snapshots become narrower once later tickets give concept batches real target-specific dependencies.
- The requested legacy pin command under `experiments/waymo-perception/tools/pins.py` is unavailable after the rename, so the renamed `autonomy/tools/pins.py` guard was used.
- Pinned files changed: none under the protected legacy `experiments/waymo-perception/{pipeline,gpu,tier1,cohort,resources}` inventory; the renamed pin guard reports no retained receipt-cited file changes.
