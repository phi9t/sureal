# 10: Real-data tier on Middlebury

**What to build:** The classical chain run on the locked Middlebury MVS asset and compared with the COLMAP MVS baseline, as recorded evidence. It is not a merge gate.

**Blocked by:** 09

**Status:** ready-for-human

- [ ] Refetch `middlebury-mvs` through the Parallax fetch path into the Parallax cache, and verify it against `assets.lock.json`.
- [ ] Run ours and COLMAP on the same views, and record pose and surface metrics against Middlebury ground truth, where available, plus runtime.
- [ ] The report states the gap to COLMAP honestly. No threshold on beating it.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.

## Comments

### 2026-10-11 coordinator

Deferred by the user's decision ("let's focus on the classical chain"). Refetching the Middlebury asset waits until we return to data reruns. Do not start this ticket until the user lifts the deferral.
