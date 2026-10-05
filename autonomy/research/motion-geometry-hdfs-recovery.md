# Motion pilot derivative recovery

[Verified publication](motion-geometry-hdfs-retention-verified.json) records21 bounded32MiB chunks with1396 members /653,550,907 uncompressed bytes. Every archive and chunk manifest was uploaded and downloaded through the Waystone token-file authentication path. Locked live Insula verified exact member hashes and rehydrated every chunk. A [separate live admission](motion-geometry-retention-admission-verified.json) reconciled the complete union with native/producer artifacts and refused5 damaged retention copies.

[Local release](motion-geometry-local-release-verified.json) records every permitted deleted derivative path and hash. Native observation/truth protobufs, raw extension slice and camera codebook remain local. Original geometry/delta receipts now describe historical paths: rehydrate before replaying them. No historical Perception/training case was removed. The resulting global scientific working set was15,033,876,120 bytes under the unchanged15GiB cap.

Recovery: use `~/workspace/waystone/scripts/waystone --auth-source token-file get` for the publication manifest and each recorded chunk archive/manifest URI. Match their SHA256 values against the verified publication. Run the existing `advanced/archive_worker.py rehydrate` inside the locked CPU Insula with a job containing `manifest_sha256` and `max_bytes:33554432`, mounting the downloaded chunk read-only at`/source`. Its live invocation is recorded per chunk in the publication receipt. Admit exact member hashes before materializing the original relative paths under the scientific working root. Recover one chunk at a time; retain bounded staging and refuse overwriting existing nonmatching files.

The immutable global manifest is at:

`hdfs://harunava/user/tiger/waystone/sureal/runs/perception-motion/motion-geometry-hdfs-93e9cdd956d0489394b17c17977a7b8b/publication-manifest.json`

The global manifest was sealed before its own upload/readback; the separate publication/admission receipts establish readback and recovery success. These are engineering-pilot storage and geometry proofs, not forecasting-model results.
