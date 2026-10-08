---
status: accepted
---

# Executions inside Insula are described by launch plans, checked against a full runtime lock

Every execution inside a dedicated Insula is described by a launch plan: the runtime lock, mounts by role, devices, environment, working directory and command. One module builds launch plans, checks the runtime lock in full (content digest and recipe digests, for both the CPU recipe form and the image form), and renders a plan to a sandbox command line only when it launches. Callers never splice command-line arguments, never copy GPU device handling, and never rebuild a launch from an old receipt's command. New receipts record the launch plan by mount role and digest, not by host path or command line. We chose this after finding about 40 hand-built launches in seven different shapes. Most checked only the content digest, which is how a lock built from an old Dockerfile went unnoticed until ticket 27, and three of them could not run at all because they mounted the same directory twice.

## Considered options

- **Keep `launch_plan` returning a command line and fix the callers one by one.** Rejected: splicing arguments is the pattern that produced seven shapes, and tests can only check strings.
- **Check only the content digest for speed.** Rejected: the recipe check is what catches a stale lock. If the content digest is slow on large root filesystems, it is cached per process, not skipped.
- **Record host paths in receipts, as before.** Rejected for the same reason as storage roots in ADR 0002: they describe the machine, not the evidence, and cannot be checked again elsewhere.

## Consequences

- Receipts written before this decision keep their command lines. The existing command-line parser stays, only to read them.
- Changing which code the sustained run launches changes its source snapshot, so balanced16 is re-admitted once after the migration. Blob-store ticket 12 is that re-admission and should land after this migration's live-path ticket where possible.
- Frozen code under `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/` keeps its own launches.
