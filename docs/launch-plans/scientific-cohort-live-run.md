# Scientific Cohort Live Run Plan

Run id: `20261009T231155Z-small-uncompressed`

Ticket: `.scratch/launch-plans/issues/03-run-the-broken-verifiers.md`

Coordinator: Claude Code session `5f8f6972`

## Scene

Run exactly one real scene from `autonomy/dataset/scientific-acquisition.candidate.json`:

`5468483805452515080_4540_000_4560_000`

Reason: it has complete local source-audit records, absent write-once
publication keys, and the smallest known current-format uncompressed decoded
sidecar publication footprint from retained `cohort-v1` evidence. The prior
fresh run on `1357883579772440606_2365_000_2385_000` failed before sidecar
publication because its decoded sidecars plus uncompressed bundle reserve
exceeded the 20 GiB aggregate working cap. The selected scene's source audits
sum to `633351907` bytes total and `80716779` bytes across the seven
point-sidecar components; retained `cohort-v1` evidence records a `6133923840`
byte sidecar archive, `6118111164` bytes of sidecar payload, and `12252035004`
bytes evicted for this scene. Its split is `training` with research split
`development`.

## Output Root

Use a fresh cohort output root under the accounted scientific working tree:

`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/lp03-live-20261009T231155Z-small-uncompressed/`

The preflight must fail if this directory already exists or if the scene
checkpoint under it already exists. No historical `cohort-v1` or other retained
checkpoint is reused.

## Exact Command

Run from the repository root:

```bash
systemd-run --user --scope --unit=sureal-cohort-20261009T231155Z-small-uncompressed -p MemoryMax=17179869184 -p MemorySwapMax=0 -p MemoryAccounting=yes env HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf PYTHONPATH=autonomy CUDA_VISIBLE_DEVICES= python3 autonomy/studies/scientific_cohort.py --scene 5468483805452515080_4540_000_4560_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/lp03-live-20261009T231155Z-small-uncompressed
```

The driver already documents and implements this direct Python invocation. It
loads the current CPU runtime lock through `load_runtime_lock`, builds
launch-plan based eviction stages, and delegates live inner stages to module
entrypoints through `PYTHONPATH=autonomy`.

The active scientific working cap is `21474836480` bytes (20 GiB), raised by
user decision on 2026-10-09 after the sanctioned release audit found zero
release-safe bytes. The independent `/data02` free-space gate remains `45` GiB.

## Publication Keys

The run is authorized to write only these new Waystone/HDFS-backed blob keys.
The preflight must check each key with read-only blob-store `exists`/Waystone
`ls` before launch and every key must be absent.

- Point scene archive:
  `datasets/scene-records-v1/5468483805452515080_4540_000_4560_000/scientific/archive.tar`
- Point scene manifest:
  `datasets/scene-records-v1/5468483805452515080_4540_000_4560_000/scientific/publication.json`
- Decoded sidecar archive:
  `datasets/component-bundles-v1/5468483805452515080_4540_000_4560_000/scientific/archive.tar`
- Decoded sidecar manifest:
  `datasets/component-bundles-v1/5468483805452515080_4540_000_4560_000/scientific/publication.json`
- Camera archive:
  `runs/scientific-camera/5468483805452515080_4540_000_4560_000/archive/camera.tar`
- Camera manifest:
  `runs/scientific-camera/5468483805452515080_4540_000_4560_000/manifest/publication.json`

The publishers derive those keys through
`dataset.blob_storage.scene_archive_blob_key`,
`dataset.blob_storage.scene_manifest_blob_key`,
`dataset.blob_storage.sidecar_archive_blob_key`,
`dataset.blob_storage.sidecar_manifest_blob_key`, and
`camera.blob_publication.camera_blob_key`.

## Evidence

Record preflight JSON, live stdout/stderr, command metadata, verification JSON,
and gate logs under:

`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-live/20261009T231155Z-small-uncompressed/`

The ticket comment will cite command lines, receipt paths, sha256 values, and
durations from that evidence directory.
