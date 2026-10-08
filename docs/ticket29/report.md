# Ticket 29 Phase 2 Report

Generated: 2026-10-08T23:35:00Z

Worker branch: `worker/t29b-runtime-lock-readmission`

Status: partial, blocked on HDFS readback for real semantic-recovery receipts.

## Summary

Ticket 29 rebuilt the current CPU Insula rootfs and promoted the active CPU
rootfs pointers to the new version. The M0 receipt was regenerated and the
M0 receipt test passed against the rebuilt rootfs.

The three semantic-recovery rows were not re-admitted. A retained point
publication record was selected, but the authorized HDFS read path timed out
before the archive could be staged. No HDFS write and no new publication was
attempted. Because the three semantic receipts were not generated, their live
gates and the four-row journal readmission entry were not run.

## CPU Rootfs

New rootfs:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z`

New lock:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z.lock.json`

The lock records:

- `dockerfile_sha256`: `8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6`
- `rootfs_sha256`: `09b794f6fb2797f9f798bcb09e97478a04044536f87f636eddc85c82361d1962`
- `image_id`: `sha256:e5c598e420ba229020559fcf9878fa54273ec38f7041b2fd6fd987f9fda8275c`

Build evidence:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/rootfs-v5-t29-20261008T230657Z-build-summary.json`
sha256 `d9b3e933b6b0bbc4da66612fb154899a57ff5a849fa8c009c4216c0f05d59a41`.

Promoted current CPU pointers:

- `autonomy/insula/bazel_launcher.py`
- `autonomy/resources/backend.py`
- `autonomy/training_execution/admit_sustained.py`
- `autonomy/training_execution/sustained_controller_backend.py`
- `autonomy/insula/m0_receipt.py` / `autonomy/insula/m0_receipt_test.py`

## M0 Readmission

M0 output:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/m0-live-rootfs-v5-t29-20261008T230657Z`

Default retained M0 receipt pointer:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/m0-live-rootfs-v5-t29-20261008T230657Z`

M0 summary:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/m0-live-rootfs-v5-t29-20261008T230657Z-summary.json`
sha256 `96ff8ded08ccefbdd07cdc18f50e590a1c28b0ff8926f211b5a2f020f3910fb8`.

Command evidence:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/m0-live-rootfs-v5-t29-20261008T230657Z.log`
sha256 `14a5ce20083f7459d0c00e45ba2e9f4d0a764a3be1a4ce0763bbf3a71143ee78`.

Result:

- `python3 -m insula.verify_m0` emitted `PASS M0 live checks`.
- `python3 -m unittest insula.m0_receipt_test -v` ran `7` tests and passed.
- After copying the receipt to the default retained pointer above,
  `PYTHONPATH=autonomy python3 -m unittest insula.m0_receipt_test -v` again ran
  `7` tests and passed without environment overrides.

## Semantic Recovery Blocker

Selected retained point publication:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/training-publication-a/receipt.json`
sha256 `248dfa385a5d540e2d7863e22777f5f439d77a4e13c1e74533a7b7682c07407f`.

Selected record summary:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery/selected-point-publication-summary.json`
sha256 `89bfa1ad56be9de157825fe3549d16ebf5c0a2fd02f04e390c95c515961e45aa`.

Archive URI:
`hdfs://harunava/user/tiger/waystone/sureal/waymo/perception/v2.0.1/derived/scene-records-v1/scientific/1730266523558914470_305_260_325_260/fae12ded2bb31c2e87a5d91811e09f9c45234a249a44f103bf82cf730abd1a6f.tar`

The recovery attempt failed before any receipt was emitted:

- Recovery log:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/semantic-recovery-20261008T231327Z.log`
  sha256 `740b8c6820f3c3a36aec6a8abd02831282df66176a5061eac6b774e885ef888c`
- Blocker summary:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery-blocker-summary.json`
  sha256 `22cb7d3e6c2da96da70b84be70f1d8d5388542b1f4c303f65629069b3e19f434`
- Bounded read audit without explicit token auth:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/hdfs-read-audit-20261008T231856Z.log`
  sha256 `6a88edc1b799accc15bd175e5665ddd312989745e227b2a5cacb56da452ae4ff`
- Bounded read audit with `--auth-source token-file`:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/hdfs-token-read-audit-20261008T232045Z.log`
  sha256 `78ab2c07179d2b036ee72c320d2385896deae0342121ee6ef2f147b1c9c6320b`

The exact failure from the recovery log:
`hdfs test -e ... timed out after 300 seconds`.

Local retained `.tar` archive fallback was checked with `find` under
`scientific-processing`; no local archive copy was present.

No HDFS writes were attempted. No new publication was attempted.

## Verification

Focused code verification:
`./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:live_gate_test //autonomy/insula:bazel_wrapper_test //autonomy/segmentation:semantic_recovery_job_test //autonomy/resources:backend_test //autonomy/training_execution:sustained_controller_backend_test`

Result: `5/5` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/focused-bazel-20261008T232247Z.log`
sha256 `fb41efa9e882d9ec0cbb340d7800b9ca32e939e3f5f49c133a067c62ad46f5ff`.

Baseline autonomy gate:
`./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`

Result: `156/156` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/autonomy-baseline-20261008T232321Z.log`
sha256 `c89e36fd76c03d9d64432abd6253ea84a0667a53cd3a86c51418bbfdfff4f6e8`.

Parallax gate:
`./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`

Result: `17/17` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/parallax-baseline-20261008T232431Z.log`
sha256 `b72186e8e4f6bb6efc6d54bd4511db950c852199953c8a44f8ed4557fe1a9ca2`.

CUDA autonomy gate:
`CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`

GPU 1 precheck: no compute process on GPU 1; memory used `4` MiB of `183359` MiB.

Result: `28/28` tests passed.

Log:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/logs/autonomy-cuda-20261008T233124Z.log`
sha256 `72b9bc8a4ab94780f21d79c6db05656d41589ec7425ee7bc4f35d7f70859e80d`.

## Not Run

- The three semantic-recovery live gates were not run because the required real
  exact/aligned semantic recovery receipts were not generated.
- The four-row journal readmission entry was not appended because the four
  re-admissions did not happen.
- `evidence.publish` was not run because HDFS writes are forbidden for this
  worker.
- Balanced16 was not run, per coordinator instruction.

## Box Verdicts

| Ticket 29 box | Verdict | Evidence |
| --- | --- | --- |
| `//autonomy/insula:m0_receipt_test` passes in a rebuilt rootfs whose lock records the current Dockerfile digest | `pass` | New rootfs lock records Dockerfile `8e6c2a38...`; M0 live receipt and 7-test unittest pass in `m0-live-rootfs-v5-t29-20261008T230657Z-summary.json` |
| Three semantic recovery tests run on real semantic-recovery receipts | `blocked` | Retained point publication selected, but HDFS read timed out before archive staging; see `semantic-recovery-blocker-summary.json` |
| The journal records these four re-admissions | `not_run` | Four-row readmission did not occur; no local journal entry or HDFS publication attempted |
