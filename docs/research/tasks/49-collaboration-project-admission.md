# 49 — Sureal collaboration project and clean-base admission

Milestone: P0. Implementation home: Sureal. Corenius is a design reference only.

**Goal:** admit one pristine canonical mainline and establish a repository-local controller's durable project records and exclusive lock.

**Dependencies:** current worker integration closeout, written protocol design/implementation-plan review, required live runtime admission. This does not require completion of the scientific program.

**Spec:** [Sureal two-worker collaboration](../../superpowers/specs/2026-10-03-sureal-serial-collaboration-design.md).

## Deliverables

- Inventory/disposition of outstanding owned code, docs, evidence, commits and mutating attempts; no work is discarded to manufacture cleanliness.
- Exact transition base on `refs/heads/phi9t/mainline`, clean tracked/index/untracked state and independently observed publication when required.
- Repository-local project initialization/status through the proposed `scripts/collab.py` entrypoint, external owned runtime-state directory and one exclusive protocol lock.
- One shared Sureal Kata project/daemon binding, stable ticket-to-issue mapping and idempotent import of admitted specs/dependency edges. Commit binding/spec mapping; retain live queue outside Git. No broad unaudited historical closure/import.
- Atomic durable records and source/project identity checks, exercised on real temporary Git fixtures. Status maps stable task IDs and pinned mainline spec/plan revisions to current claim, worker session, attempt, workspace and evidence; runtime ownership stays outside source.

## Verifiers

- Live Insula executes actual project/identity/lock/cleanliness tests and an independent artifact audit.
- Refuse dirty index, tracked/untracked modifications, wrong ref/root, competing lock acquisition, branch-only/unpinned task definitions and corrupted project state.
- Verify actual shared-project resolution, installed Kata capability/version, stable spec-to-issue mapping, blocked-by readiness and project-scoped export/restore; no unrelated project data enters recovery artifacts.
- Admit an additive protocol test runtime with Git/Python/Kata daemon access if needed; do not mutate active scientific runtime roots.

## Acceptance

- Clean-base evidence is real and exact; unique unlanded work and live writers remain explicit blockers.
- A second controller cannot concurrently admit project mutation. Unknown/corrupt identity fails closed.
- Runtime records do not dirty canonical source. The existing Kata daemon supplies the queue; no Corenius dependency or custom daemon is introduced. All worktrees resolve to the same admitted Sureal project.
- Project initialization records intent and state; it does not falsely claim a worker, candidate or integration completed.

## Closure evidence

Retain exact base/ref/root identities, closeout disposition, actual live commands/logs/exits, refusal results, independent receipts and reviewed landed implementation. Documentation checks alone do not close P0.
