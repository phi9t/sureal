# 29: Finish the runtime-lock re-admission left open by ticket 27

**What to build:** Every runtime-lock check listed in ticket 01 passes for real on the new images. Ticket 27 re-admitted seven of them with live-gate passes; four remain. This ticket finishes them without relaxing any gate.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `//autonomy/insula:m0_receipt_test` passes in a rebuilt rootfs whose lock records the current Dockerfile digest (ticket 27 found the lock at `61a783f4…` against the committed Dockerfile's `8e6c2a38…`)
- [x] `//autonomy/segmentation:semantic_recovery_accounting_test`, `semantic_recovery_receipt_test` and `semantic_recovery_receipt_aligned_test` run on real semantic-recovery receipts, not the synthesized receipts ticket 27 used for its contract-only check
- [x] The journal records these four re-admissions

## Comments

Split from ticket 27's third box. See `docs/ticket27/readmission-report.md` (rows marked `prerequisite_missing`) and `docs/ticket27/execution-report.md` ("Ticket 27 Box Verdicts").

Triaged 2026-10-08: ready-for-agent. Land this before blob-store ticket 12, because a rootfs rebuild here may change the lock that ticket 12's balanced16 re-admission binds; first establish whether the M0 image and the balanced16 image share a rootfs. The unmerged branch `worker/t27c-live-gate-harness` (7720795) shows how these live gates mount their fixtures; use it as reference only. Do not land a ticket-named module such as `autonomy/ticket27/`; live-gate support belongs in a concept module. GPU 1 only, and only when free.

2026-10-08 worker/t29b: Rebuilt CPU Insula as `rootfs-v5-t29-20261008T230657Z`; lock records Dockerfile digest `8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6`. M0 live receipt and `insula.m0_receipt_test` passed against the rebuilt rootfs. The semantic recovery receipts remain blocked: retained point publication `training-publication-a` was selected, but read-only HDFS staging timed out during `hdfs test -e` after 300 seconds, and bounded `waystone ls` probes without and with `--auth-source token-file` also timed out. See `docs/ticket29/report.md` and `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery-blocker-summary.json`.

2026-10-09 worker/t29c: HDFS token auth was fresh. Generated fresh exact and aligned semantic recovery receipts from retained `training-publication-a` under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery/run-20261009T022117Z.FC5hCl` with `waystone --auth-source token-file` readback only. Exact receipt `cd68ca461d8a55f8a80cef4dd6b3eb60b7a6fda45913828b2674ccea03df3264`; aligned receipt `e55aa902be95907973f6e641a94a4707e61309369238fec71b5cc8af66a642c0`. Live gates passed: accounting `2/2`, receipt `1/1`, aligned receipt `1/1`; summary `b4a1401bf0cd29f1d1e109f45ffb5346710ab1cb6034e55b179583e9f7991423`. Journal entries 131-134 record the M0 plus three semantic recovery readmissions. Required gates passed: `//autonomy/...` `173/173` (`acb2cbba3019447253782eb161c1f0a27c49eee8bc04cff9a050cb2d8266c099`), `//parallax/...` `17/17` (`323932e450a85452e73767e1688836f79b3b3ddd4fa66bfe551e417cc19682c5`), and GPU 1 CUDA `//autonomy/...` `29/29` (`4733f1d49ac04372440b45ee3d3b1bb90b73a15e84fd0c6fb9128a7613c568ef`). Pin report against recorded base `647c458` exited 1 only for the three local research tracker/journal files pinned by `research/research-journal-hdfs-verified.json`; no semantic recovery source file was reported. No HDFS writes, evidence publish, container build, retained evidence mutation, or shared-cache staging was performed.
