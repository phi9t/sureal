# A49 raw evidence contract

This independent authority never imports `scripts/_collab`. It reads the pinned
coverage document, retained raw Git objects, actual source bytes, filesystem
snapshots, native logs/resource receipts and isolated Kata databases. A producer
`passed` field, an expected reason or a case name never supplies an assertion.

Every artifact reference is `{ "path": "/absolute/regular/file", "sha256": "…" }`.
The auditor rejects missing/changed references and records every reopened digest.
JSON records have `schema_version: 1`; canonical records reject duplicate keys,
floats and unknown schemas. Raw resource measurements may contain finite floats.

`actual-command.json` records literal `argv`, absolute `cwd`, integer
`started_ms`, `ended_ms`, `exit_code`, optional `timeout_ms`, and `stdout`/`stderr`
artifact references. Refusal probes supply one actual CLI result in stdout;
the exit and result envelope must agree. Aggregate stage exit0 is only harness
completion. Each case's `execution.log` is retained actual command stdout.

`context.json` (or `candidate-role-context.json`) binds `ticket`, `phase`,
`candidate_role`, `candidate`, `parent`, `tree`, `materialization_sha256` and
`gate_admission_sha256`. `independent-oracle.json` only locates a `raw_root` and
`fixture_manifest` reference. Case-specific facts are derived as follows.

* Clean refusals: required scenarios are dirty-tracked, dirty-index, untracked,
  wrong-ref, wrong-root, alias, unpinned-task and branch-only-spec. Each has
  `fixture_root`, `pre_git_facts_path`, `post_git_facts_path`, and
  `actual_command_path` artifact references. Git facts include canonical root,
  common directory, symbolic ref, HEAD/tree, index SHA256, all refs, raw
  porcelain/ignored bytes as hexadecimal and raw recursive submodule status.
  Post facts are reopened from Git and compared with pre facts to prove no ref
  or source mutation. Wrong-root/alias supply consumed `admission_input`;
  unpinned-task/branch-only-spec supply consumed `authority_input`. Actual
  entrypoint/argv, reopened authority and literal Git ancestry prove each cause.
  Optional runtime state snapshots must contain no launch.
* Durability: required scenarios are prepared-event, immutable-record,
  projection, event-fsync, record-fsync, parent-fsync, disk-full and result-fsync. Each has
  `before_state`, `interrupted_state`, `after_state` snapshot references,
  `actual_command_path`, `reconcile_command_path`, and `fault_log` reference.
  A snapshot is a schema1 manifest with `root`, `files` mapping relative paths
  to SHA256 and `device`. Its actual file union must match. The live fixture
  runs on the admitted configured filesystem device. Fault logs are raw
  ordered JSONL call/raise records with consecutive `sequence`, `boundary`,
  `operation_id`, `relative_path`, and errno
  for I/O failures. Recovery derives the event chain, immutable records and
  `current.json`; it cannot infer success from a surviving prepared intent.
  Each probe's `operation_id` must match actual `--operation-id` argv and trace.
  Prepared-event/event-fsync/record-fsync leave one new prepared event without
  an immutable record; immutable-record/parent-fsync publish that record;
  projection publishes its exact derived projection. Result-fsync starts with
  an unresolved durable Effect and adds exactly one success-asserting result
  event without its immutable result record or a new current projection.
  That effect remains unresolved; reconciliation must be unknown/refused.
  The fixture also supplies `lock_holder_command`, `lock_contender_command`
  and `lock_events` artifacts. Acquired/released events bind lock path,
  device/inode, PID and times; the second command must overlap the held lock
  and refuse. Fixture processes must be quiescent before stage completion.
  Holder/contender invoke candidate CLI or `collab_live.py probe lock-holder`
  and `probe lock-contender`, with retained literal argv.
* Journal corruption: torn-tail, earlier-corruption, input-digest-reuse and
  fsync-failure have the same snapshot/command fields. Raw earlier corruption
  must remain refused; torn bytes are retained in `incidents/<sha>.tail`.
  The fsync-failure corruption probe is specifically a failed result-event
  fsync; intent-only reconstruction is allowed to retain unresolved intent.
* Source/runtime: oracle locates `resource_proof`, `pre_source_manifest`,
  `post_source_manifest` and `build_manifest` artifacts. The proof is the
  existing complete resource-admitted receipt; actual original and wrapped
  bwrap argv, host/worker/cgroup/lifecycle measurements and native/retained log
  hashes are independently checked. Build manifest locates actual build and
  export command records, pinned `base_image` digest, `package_artifacts`,
  `image_id`, `image_id_file` written by actual build `--iidfile`,
  `build_context` directory snapshot, `base_inspect_command`, `inspect_command`,
  `create_command`, `container_id`, `container_inspect_command`,
  `rootfs_archive`, `rootfs_inventory` (rootfs_sha256/member_count), and
  `capability_commands`. Actual offline context/recipe/base/package union,
  inspected image, created container, exported tar bytes/types/modes and actual
  rootfs union must agree. Original bwrap admits only exact rootfs/source/
  reference/output/tmp mounts plus optional /proc and /dev; shadow mounts
  refuse. Only the independently reconstructed resource wrapper adds mounts.
  Runtime admission includes
  `reference_path`, rootfs path/digest, lock reference, complete resource source
  map, cap bytes and timeout seconds. No scientific rootfs is modified.
* Fixture import: `selected_project_uid`, first_db, second_db, revised_db,
  definitions, old_brief_before/after, status_before_db/status_after_db and
  command artifacts. DBs are actual isolated schema25 backups without omitted
  WAL; independent SQLite reads compare UIDs, source pins, metadata/dependencies
  and unchanged old brief. `sureal_task` and `sureal_definition` are literal
  metadata keys. Definition revision is its canonical digest without revision.
  A genuine changed spec uses `definition_repository`,
  `definition_retention`, `definition_pre_git_facts` and
  `definition_post_git_facts`. Reopen the owned clean fixture mainline and
  fresh retained pack; first/revised source pins belong to corresponding
  landed before/after history. This authority is separate from frozen X code.
* Restore: source_db, restored_db, export, actual_export_command,
  actual_import_command and selected_project_uid. Source contains a foreign
  project; restored project/issues/links contain only selected UIDs, with fresh
  instance identity. Actual export is project-scoped; import targets fresh DB
  with `--new-instance` and no `--force`.
  All live DB schemas must equal the pinned installed native baseline's raw
  sqlite_master, not merely a schema25 metadata flag. The exact empty native
  .kata-system sentinel row is preserved; no arbitrary foreign rows or
  unbound auxiliary payload/credential rows are allowed.
  Only its native fresh numeric row ID and created_at/updated_at UTC timestamps
  may differ from baseline; all other identity/payload fields remain exact.
  Native FTS5 search closure is checked separately from segment layout. Reopen
  every exact known FTS table, retaining BLOB values as explicit hexadecimal;
  refuse unknown search tables. Independently rebuild expected indexed title,
  body and id-ordered comments using the declared native tokenizer. Actual
  fts5vocab instance postings, document row IDs, document sizes and config must
  match, including empty-text documents. Check internal FTS integrity solely
  in an owned memory copy. Selected source/restored search facts normalize
  numeric document IDs to stable issue UIDs and must agree. Read-only status
  compares actual raw search-table facts too. Never execute index repair or
  integrity writes on the observed database.
* Map gate: raw canonical M/parent Git diff, map and binding blobs, source
  definition pins and real-project SQLite snapshot. Only `.kata.toml`, the
  `.kata.local.toml` ignore line and `docs/research/kata-task-map.json` may change;
  map contains project/binding/source/tasks pins, never owner/status.
  Existing ignore bytes/order are preserved after removing exactly one added
  authorized line; only a missing final newline may be completed. Metadata
  changed paths must remain ordinary mode100644 blobs.
* Post landing: actual canonical Git/ref/tree/index/status, accepted exact gate
  audit, prepared landing and actual configured remote readback. A prior gate
  never supplies the post fact.
* Closure: actual real-project SQLite close/readback, manual bootstrap/import,
  exact X/M retained objects and complete accepted gate/post references for
  both roles. Closure follows the actual close operation.
  Reopen M's retained pack/materialization for X→M ancestry; X's immutable
  earlier pack need not contain M. Project/49 issue UID/definition/spec/plan
  pins must match raw M map/binding. `kata_context` references actual health
  response and binds home/db_path/project_uid/workspace. Close command pins
  admitted Kata executable, `environment.KATA_HOME` and canonical cwd.

GateAdmission is kind `GateAdmission`, not ProjectAdmission. It pins `source`,
coverage reference, auditor commit/materialization/reviewer references, runtime
and state_filesystem. The auditor invocation must be from its immutable admitted
source; both auditor and producer materializations are reopened before/after.
Source pins additionally locate `source.retention`; every retained raw pack is
freshly indexed/read back in an independent bare repository. `authors` contains
distinct producer/auditor/reviewer identities, and the admitted reviewer receipt
pins exact A49. `kata.native_baseline_db` binds the installed schema. Later
admissions list exact accepted prior receipt references in
`prior_acceptances[implementation|metadata][gate|post-landing]`; prior flags,
empty/incomplete coverage or unadmitted digests never authorize a transition.

The report has kind `independent-collaboration-audit`, ticket/phase/role,
candidate/parent/tree and exact source/admission/coverage/auditor/review digests,
reopened artifact references and derived facts. Only every matching authoritative
case can yield `status: pass`, `accepted: true`, `phase_complete: true`. A case-only
probe yields `partial`, false/false even if the probe exits0. Missing facts yield
a retained failing report and exit2, keeping the gate open.
