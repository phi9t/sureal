# Experiment tracking and research journal

User requested a mechanism to keep experiments tracked, maintain a research
journal, store results on HDFS and land ready work. Use repository metadata,
not another training framework or external service.

The registry declares each run/recipe, goal, verifier and acceptance criteria.
Evidence-derived projection distinguishes planned, GPU-admitted, running,
execution failure, native-fit pending closure, verified overfit, verified finite
censoring and equivalence controls. Recipes must match immutable run metadata or
GPU admission evidence; registry edits cannot relabel old results. Native loss
reduction cannot promote a run to accepted. Final closure must match the result
hash and successful live checks.

Journal categories are observation, hypothesis, decision and follow-up.
Append under a file lock; hash-chain entries and retain content-addressed evidence
snapshots. Git and HDFS snapshots anchor the head. Automatically record accepted
stage transitions once; keep frequent updates in the dashboard. Never silently
rewrite journal history. Unanchored tail truncation is outside the hash-chain
claim. Live refresh uses the local retained verifier cache; portable Markdown,
JSON and journal snapshots can be viewed from Git/HDFS.

CLI supports refresh, polling, notes and journal verification. An explicit
publisher freezes metadata under locks, uploads a unique HDFS snapshot, downloads
and compares every file, and publishes/reads the manifest last. It uses Waystone's
Sureal namespace, cached token auth and externally bounded processes. No model
or sensor payload is copied into the journal.

Acceptance: live Insula journal/projection contracts and integration prove
history/hash preservation, recipe identity, native threshold/closure gating,
non-training admission/equivalence, evidence snapshots and idempotent refresh.
Actual HDFS upload/readback must pass. Ready work is committed and integrated
separately; pending model/research milestones remain open.
