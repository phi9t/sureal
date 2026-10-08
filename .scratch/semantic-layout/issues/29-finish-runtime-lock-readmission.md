# 29: Finish the runtime-lock re-admission left open by ticket 27

**What to build:** Every runtime-lock check listed in ticket 01 passes for real on the new images. Ticket 27 re-admitted seven of them with live-gate passes; four remain. This ticket finishes them without relaxing any gate.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] `//autonomy/insula:m0_receipt_test` passes in a rebuilt rootfs whose lock records the current Dockerfile digest (ticket 27 found the lock at `61a783f4…` against the committed Dockerfile's `8e6c2a38…`)
- [ ] `//autonomy/segmentation:semantic_recovery_accounting_test`, `semantic_recovery_receipt_test` and `semantic_recovery_receipt_aligned_test` run on real semantic-recovery receipts, not the synthesized receipts ticket 27 used for its contract-only check
- [ ] The journal records these four re-admissions

## Comments

Split from ticket 27's third box. See `docs/ticket27/readmission-report.md` (rows marked `prerequisite_missing`) and `docs/ticket27/execution-report.md` ("Ticket 27 Box Verdicts").

Triaged 2026-10-08: ready-for-agent. Land this before blob-store ticket 12, because a rootfs rebuild here may change the lock that ticket 12's balanced16 re-admission binds; first establish whether the M0 image and the balanced16 image share a rootfs. The unmerged branch `worker/t27c-live-gate-harness` (7720795) shows how these live gates mount their fixtures; use it as reference only. Do not land a ticket-named module such as `autonomy/ticket27/`; live-gate support belongs in a concept module. GPU 1 only, and only when free.

2026-10-08 worker/t29b: Rebuilt CPU Insula as `rootfs-v5-t29-20261008T230657Z`; lock records Dockerfile digest `8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6`. M0 live receipt and `insula.m0_receipt_test` passed against the rebuilt rootfs. The semantic recovery receipts remain blocked: retained point publication `training-publication-a` was selected, but read-only HDFS staging timed out during `hdfs test -e` after 300 seconds, and bounded `waystone ls` probes without and with `--auth-source token-file` also timed out. See `docs/ticket29/report.md` and `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery-blocker-summary.json`.
