# Ticket 29 Final Report

Generated: 2026-10-09T02:37:00Z

Worker branch: `worker/t29c-semantic-recovery`

Status: complete; ticket status flip is kept in the final status-only commit.

## Summary

Ticket 29 now has all four runtime-lock re-admissions recorded and verified.
Part one rebuilt and promoted the CPU Insula rootfs, regenerated the M0 receipt,
and passed `//autonomy/insula:m0_receipt_test`. This worker completed the
remaining semantic recovery work by generating fresh exact and aligned recovery
receipts from a retained scientific point publication, running the three
semantic recovery live gates against those receipts, and appending local journal
entries for all four re-admissions.

No HDFS writes, `evidence.publish`, container builds, retained evidence
mutation, or shared-cache staging were performed in this worker.

## Runtime Rootfs And M0

Current CPU rootfs:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z`

Current CPU lock:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z.lock.json`

The lock records:

- `dockerfile_sha256`: `8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6`
- `rootfs_sha256`: `09b794f6fb2797f9f798bcb09e97478a04044536f87f636eddc85c82361d1962`
- `image_id`: `sha256:e5c598e420ba229020559fcf9878fa54273ec38f7041b2fd6fd987f9fda8275c`

Part-one M0 evidence:

- Build summary:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/rootfs-v5-t29-20261008T230657Z-build-summary.json`
  sha256 `d9b3e933b6b0bbc4da66612fb154899a57ff5a849fa8c009c4216c0f05d59a41`
- M0 summary:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/m0-live-rootfs-v5-t29-20261008T230657Z-summary.json`
  sha256 `96ff8ded08ccefbdd07cdc18f50e590a1c28b0ff8926f211b5a2f020f3910fb8`
- M0 receipt:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/m0-live-rootfs-v5-t29-20261008T230657Z/receipt.json`
  sha256 `e9dd21fb9034fdc8baa2fa522bf2571bbdbeea13aabaab2ae6a841ffee66c652`
- M0 log:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/m0-live-rootfs-v5-t29-20261008T230657Z.log`
  sha256 `14a5ce20083f7459d0c00e45ba2e9f4d0a764a3be1a4ce0763bbf3a71143ee78`

## Semantic Recovery Receipts

Selected retained scientific point publication:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/training-publication-a/receipt.json`
sha256 `248dfa385a5d540e2d7863e22777f5f439d77a4e13c1e74533a7b7682c07407f`.

Selected publication manifest:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/training-publication-a/checked/publication.json`
sha256 `e8dbff0a4e74b003b615dbc1dae508078aec59dad5db5334bf3b9c84eada151e`.

Selected scene:
`1730266523558914470_305_260_325_260`

Archive:
`hdfs://harunava/user/tiger/waystone/sureal/waymo/perception/v2.0.1/derived/scene-records-v1/scientific/1730266523558914470_305_260_325_260/fae12ded2bb31c2e87a5d91811e09f9c45234a249a44f103bf82cf730abd1a6f.tar`

Archive identity:

- sha256 `fae12ded2bb31c2e87a5d91811e09f9c45234a249a44f103bf82cf730abd1a6f`
- bytes `3022008320`
- independent reference records `1970`
- eligible point elements `2720971`

Generated under:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery/run-20261009T022117Z.FC5hCl`

Generation summary:
`generation-summary.json` sha256 `8405e152061e2249dd0c2043565919a98a0a3e88ed2addc3b579e84e647fb914`.

Selected recovery record:
`selected-point-publication-record.json` sha256 `03b8d56a9b73150cb15dc6365e8a3127c4050b74b6c10fa580e16e7da800fe32`.

Selected publication summary:
`selected-point-publication-summary.json` sha256 `61c433ba50e1c5f8d8e5c0fb1f1279a330fcbafcb9c1b0042856c9038774d09c`.

Exact receipt:
`current/receipt.json` sha256 `cd68ca461d8a55f8a80cef4dd6b3eb60b7a6fda45913828b2674ccea03df3264`.

Aligned receipt:
`aligned-current/receipt.json` sha256 `e55aa902be95907973f6e641a94a4707e61309369238fec71b5cc8af66a642c0`.

Generation log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/semantic-recovery-generate-20261009T022117Z.log`
sha256 `65d4f336ab9e80b41be4fe871531499db584ee6433ef20e5bef37f9d77032f83`.

The transfer command used by both recovery receipts was the recovery job's
read-only `get` path with an injected prefix:
`timeout --kill-after=10s 600s /data02/home/philip.yang/workspace/waystone/scripts/waystone --auth-source token-file --command-timeout-secs 600 --progress silent get ...`.

The recovery jobs used run-local staging directories under
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery/`.
The preflight lease was corrected to use the supplied `staging_cache`, matching
the transfer path and avoiding writes to the shared Waystone cache.

## Live Gates

Live gate summary:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery/run-20261009T022117Z.FC5hCl/live-gate-summary.json`
sha256 `b4a1401bf0cd29f1d1e109f45ffb5346710ab1cb6034e55b179583e9f7991423`.

Results:

- `//autonomy/segmentation:semantic_recovery_accounting_test`: pass, `2/2`
  unittests; record sha256
  `42373dc300430f6da4131d7a41edfc554de7185bfa579721811b15996da5ae9b`;
  raw log sha256
  `526bdfff73f3d7db70d6bae844abf0c93c94e1d236165f370a562ea1e159e4ce`
- `//autonomy/segmentation:semantic_recovery_receipt_test`: pass, `1/1`
  unittest; record sha256
  `652cbf5104803a77e7d80e9d9268a4e00568285b42dca218ce9b5da20df14266`;
  raw log sha256
  `f0d4a1130f1e4f73a9d743cdd18454842b192373f7d585ed732c78d1d61a55c2`
- `//autonomy/segmentation:semantic_recovery_receipt_aligned_test`: pass,
  `1/1` unittest; record sha256
  `63af3bcc72d1b23ee7d39c343ea23377f5d83b61723c638118a6a08b41bc0693`;
  raw log sha256
  `08796186deff7ea23225b325424d1bba6174ca5d854e27049a74e3311c6986cb`

## Journal

`PYTHONPATH=autonomy python3 -m evidence.tracker note` appended four local
journal entries and refreshed the local dashboard:

- Sequence 131: `ticket29-m0-receipt-readmission`, entry sha256
  `259b2371cc94d41e9de9d7b5e217059c9b3be27c136bc9a1857dbbea6e19c59d`
- Sequence 132: `ticket29-semantic-recovery-accounting-readmission`, entry
  sha256 `0617223a64f37f099851fc37955b8cfbe46cb94c455838be42034c9ebdd5298b`
- Sequence 133: `ticket29-semantic-recovery-receipt-readmission`, entry
  sha256 `d0a0157f25a3adbf783a552aa00eb719ba8dcc1063e427265646ae42397fa777`
- Sequence 134: `ticket29-semantic-recovery-receipt-aligned-readmission`, entry
  sha256 `94f9a8969318d60b54f4f554416e9e9d2e0492b619865fb98e6c45c68861ca78`

Journal command log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/journal-notes-20261009T023704Z.log`
sha256 `82046418430ac99ecde6339c08e92c365821e4a0f5eb699abecc981006d21679`.

## Verification

Focused recovery test after the staging-cache fix:

`TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/t29c-semantic-recovery-20261009T021420Z/tmp ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:semantic_recovery_job_test`

Result: `1/1` test passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/semantic-recovery-job-test-20261009T021803Z.log`
sha256 `f35c9ab7cf877ba77e323026cf14be85d1ad9885f5dd279b608d16fad021db0d`.

Baseline autonomy gate:

`TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/t29c-semantic-recovery-20261009T021420Z/tmp SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`

Result: `173/173` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/autonomy-baseline-20261009T022428Z.log`
sha256 `acb2cbba3019447253782eb161c1f0a27c49eee8bc04cff9a050cb2d8266c099`.

Parallax gate:

`TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/t29c-semantic-recovery-20261009T021420Z/tmp SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`

Result: `17/17` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/parallax-baseline-20261009T022548Z.log`
sha256 `323932e450a85452e73767e1688836f79b3b3ddd4fa66bfe551e417cc19682c5`.

GPU 1 precheck:

- Busy at 2026-10-09T02:32:48Z; log sha256
  `6c99be66063aef971b12c3b9673bbaebbe82f5f80ea2adbf39b5c9eabc7928ca`
- Clear at 2026-10-09T02:33:41Z; GPU 1 reported `4` MiB used and no compute
  process for `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`; log sha256
  `839cc162942131091cf3a2882aa0dbb9747860cf0ceb460e9137a6d22c3a320f`

CUDA autonomy gate:

`TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/t29c-semantic-recovery-20261009T021420Z/tmp SUREAL_BAZEL_CACHE=$PWD/.bazel-cache CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`

Result: `29/29` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/autonomy-cuda-20261009T023350Z.log`
sha256 `4733f1d49ac04372440b45ee3d3b1bb90b73a15e84fd0c6fb9128a7613c568ef`.

Pre-commit source-pin report:

`cd autonomy && PYTHONPATH=. python3 -m evidence.pins check --base 647c458`

Result: exit `1`, reporting the expected local journal/dashboard updates
`research/experiments.json`, `research/research-journal.jsonl`, and
`research/research-journal.md` as pinned by
`research/research-journal-hdfs-verified.json`. No semantic recovery source file
was reported by the pin check.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/pins-precommit-base647c458-20261009T024001Z.log`
sha256 `1dd5080fe37182c6f6030eb733764318d73cdfde5ede5789d3dca6fdd9bedcca`.

## Box Verdicts

| Ticket 29 box | Verdict | Evidence |
| --- | --- | --- |
| `//autonomy/insula:m0_receipt_test` passes in a rebuilt rootfs whose lock records the current Dockerfile digest | `pass` | New rootfs lock records Dockerfile `8e6c2a38...`; M0 live receipt and `7/7` unittest pass in `m0-live-rootfs-v5-t29-20261008T230657Z-summary.json`; journal sequence 131 |
| Three semantic recovery tests run on real semantic-recovery receipts | `pass` | Fresh exact and aligned receipts generated from retained `training-publication-a`; live gates passed `2/2`, `1/1`, `1/1`; journal sequences 132-134 |
| The journal records these four re-admissions | `pass` | Local journal sequences 131-134 appended by `python3 -m evidence.tracker note` |

## Not Run

- `evidence.publish` was not run because HDFS writes are forbidden.
- No new HDFS publication was attempted.
- No container build was run in this worker.
- Balanced16 was not run, per ticket scope and coordinator instruction.
