# 10: Source snapshots are stored in HDFS

**What to build:** A researcher's source snapshots are stored content-addressed in HDFS, so they outlive the local cache and can be fetched on another machine. Upload uses exact readback, as the journal's publication already does.

**Blocked by:** 09 (Evidence module: snapshot, fetch and verify)

**Status:** done

- [x] An HDFS adapter implements the same storage interface as the local-directory adapter
- [x] Upload reads the object back and compares bytes before reporting success
- [x] Uploading a digest that already exists verifies the existing bytes and does not overwrite
- [x] A snapshot uploaded in one session is fetched and verified in a fresh session with an empty local cache; the live check is recorded
- [x] Authentication failure and a missing object are reported as distinct, explicit errors

## Comments

Built:

- Added `HdfsSnapshotStore` to the evidence snapshot module. It implements the existing `SnapshotStore` interface, uses Waystone with `--error-format json --auth-source token-file`, stores objects under the Sureal `source-snapshots/` child prefix, verifies existing objects instead of overwriting them, and performs exact readback after upload.
- Added explicit `SnapshotAuthenticationError` and `SnapshotMissingError` paths. Unit tests cover the adapter through a fake Waystone command; unit tests do not require HDFS.
- Pinned files changed: none. The requested old guard path has moved on this branch with the rename; the equivalent guard run was `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration`.
- Live HDFS writes were limited to the new `hdfs://harunava/user/tiger/waystone/sureal/source-snapshots/` child. Two small immutable test snapshots now exist there: `293fc6fefadc28a5addc00ad62c6ff61955feff8d506acf9a5b4dad158a16fa4` from the diagnostic attempt that exposed Waystone's local-destination rule, and `e236ccc29f7ab4bb06c7db9b50e1e83f28d61299a77fbe4db6515a5640726990` from the final verified live check. I did not overwrite, move, or delete either object.

Verification:

- `./bazelw test //autonomy:evidence__source_snapshot_test` -> red before implementation: `ImportError: cannot import name 'HdfsSnapshotStore'`.
- `./bazelw test //autonomy:evidence__source_snapshot_test --test_output=errors --cache_test_results=no` -> red after adding the auth-source expectation: fake Waystone reported `{"error":"unexpected command"}` until the adapter passed `--auth-source token-file`.
- `./bazelw test //autonomy:evidence__source_snapshot_test --test_output=errors --cache_test_results=no` -> red after modeling live Waystone `get`: fake Waystone reported `{"error":"Local destination already exists"}` until `_download` used a not-yet-existing path inside a temporary directory.
- `export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-/opt/tiger/yarn_deploy/hadoop/conf}"; W=/data02/home/philip.yang/workspace/waystone/scripts/waystone; "$W" --error-format json --auth-source token-file ls "$($W --error-format json --auth-source token-file storage-prefix --child sureal)"` -> exit 0; listed existing Sureal children `datasets/`, `runs/`, and `waymo/`.
- Live upload/fresh-fetch check, using two separate `python3` processes with `HdfsSnapshotStore('/data02/home/philip.yang/workspace/waystone/scripts/waystone')` and an archive of `autonomy/evidence/source_snapshot.py` plus `autonomy/evidence/source_snapshot_test.py` -> exit 0. Upload result: `source_snapshot_sha256=e236ccc29f7ab4bb06c7db9b50e1e83f28d61299a77fbe4db6515a5640726990`, `source_snapshot_bytes=40960`, `hdfs_uri=hdfs://harunava/user/tiger/waystone/sureal/source-snapshots/e236ccc29f7ab4bb06c7db9b50e1e83f28d61299a77fbe4db6515a5640726990`. Fresh fetch result: `matches_upload=true`, `uri_matches_upload=true`, `source_snapshot_bytes=40960`.
- `export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-/opt/tiger/yarn_deploy/hadoop/conf}"; W=/data02/home/philip.yang/workspace/waystone/scripts/waystone; PREFIX="$($W --error-format json --auth-source token-file storage-prefix --child sureal)"; "$W" --error-format json --auth-source token-file ls "$PREFIX/source-snapshots"` -> exit 0; found the two 40KB files listed above.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` -> `PASS: 0 changed file(s) cited by retained receipts`.
- `./bazelw test //autonomy:evidence__source_snapshot_test //autonomy:tracking__test_publish --test_output=errors --cache_test_results=no` -> 2 of 2 tests passed.
- `./bazelw test //autonomy/... --test_output=errors --cache_test_results=no` -> 139 of 139 tests passed.
