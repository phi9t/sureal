# 29: Finish the runtime-lock re-admission left open by ticket 27

**What to build:** Every runtime-lock check listed in ticket 01 passes for real on the new images. Ticket 27 re-admitted seven of them with live-gate passes; four remain. This ticket finishes them without relaxing any gate.

**Blocked by:** None (can start immediately)

**Status:** needs-triage

- [ ] `//autonomy/insula:m0_receipt_test` passes in a rebuilt rootfs whose lock records the current Dockerfile digest (ticket 27 found the lock at `61a783f4…` against the committed Dockerfile's `8e6c2a38…`)
- [ ] `//autonomy/segmentation:semantic_recovery_accounting_test`, `semantic_recovery_receipt_test` and `semantic_recovery_receipt_aligned_test` run on real semantic-recovery receipts, not the synthesized receipts ticket 27 used for its contract-only check
- [ ] The journal records these four re-admissions

## Comments

Split from ticket 27's third box. See `docs/ticket27/readmission-report.md` (rows marked `prerequisite_missing`) and `docs/ticket27/execution-report.md` ("Ticket 27 Box Verdicts").
