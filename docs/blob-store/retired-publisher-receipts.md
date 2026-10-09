# Retired publisher receipt source-snapshot check

Date: 2026-10-09

Verifier:

```bash
RUN_TMP=$(mktemp -d /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/bs07-native-cache-pilot-20261009T060944Z/tmp/retired-receipts.XXXXXX)
TMPDIR="$RUN_TMP" PYTHONPATH=autonomy python3 autonomy/retention/retired_publisher_receipts.py \
  --root /data02/home/philip.yang/.cache/waystone/waymo-perception \
  --root autonomy/research
```

The verifier discovers final retired publisher receipts by JSON shape and requires
`independent_admission`, so independent-audit input copies and in-progress
manifests are not counted. When a receipt contains an embedded source-snapshot
receipt, the verifier builds the recorded store with `store_from_receipt()` and
materializes the recorded snapshot into a fresh temporary directory with
`verify_or_materialize_receipt_sources()`. It never compares against the working
tree.

## Results

| Receipt kind | Found | Verified through source snapshot | Missing source-snapshot receipt | Failed |
| --- | ---: | ---: | ---: | ---: |
| native-cache retention | 2 | 0 | 2 | 0 |
| sustained-checkpoint retention | 2 | 0 | 2 | 0 |
| sustained-pilot retention | 2 | 0 | 2 | 0 |
| resource retention | 25 | 0 | 25 | 0 |

Unique receipt digests found:

| Receipt kind | Unique SHA-256 digests | Root distribution |
| --- | ---: | --- |
| native-cache retention | 1 | 1 under `~/.cache/waystone/waymo-perception`, 1 under `autonomy/research` |
| sustained-checkpoint retention | 1 | 1 under `~/.cache/waystone/waymo-perception`, 1 under `autonomy/research` |
| sustained-pilot retention | 1 | 1 under `~/.cache/waystone/waymo-perception`, 1 under `autonomy/research` |
| resource retention | 12 | 25 under `~/.cache/waystone/waymo-perception` |

## Interpretation

The retained final receipt files on this host do not embed full source-snapshot
receipts. They contain legacy digest maps such as `host_source_pins`,
`resource_source_pins` or `source_pins`, but those maps do not include
`source_snapshot_sha256`, `source_snapshot_store` and a snapshot receipt
`source_pins` map together. They therefore are not counted as verified through a
source snapshot.

No receipt with an embedded source-snapshot receipt failed verification. No HDFS
writes, cache writes, receipt edits or snapshot edits were performed.
