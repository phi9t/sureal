# Blob store: one backend-neutral store for evidence blobs, and one publication module

Status: ready-for-agent

Governing decisions: `autonomy/docs/adr/0002-evidence-blobs-go-through-a-blob-store.md`, `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md`, `docs/adr/0001-directories-express-concepts.md` and `docs/adr/0002-bazel-runs-inside-insula.md`. Vocabulary follows `autonomy/CONTEXT.md` (blob store, blob, blob key, source snapshot, source pin, live implementation gate).

## Problem Statement

Every part of the perception program that keeps a file for later retrieval talks to HDFS directly by shelling out to the Waystone command-line tool, and each one does it differently.

- **About fifteen callers each wrap the tool themselves.** They include the source snapshot store, the research-journal publisher, the scientific-directory publisher, three retention publishers, the resource bundle publisher, and scripts in the dataset, camera, segmentation and geometry concepts. Their timeouts are 90, 300, 30 and 5 seconds. Some kill the tool's process group on a hang and some do not. One checks whether a blob exists before writing it, and the others do not. The block that pins the tool's binaries is copied into seven files.
- **The differences cause real failures.** Ticket 27 failed twice on them: a fetch hung past a fixed 90 s bound with no retry, and a listing's "Found 0 items" line was misread as existence.
- **The repository hard-codes where HDFS keeps its files.** Code, audits and receipts spell out `hdfs://harunava/user/tiger/waystone/sureal/…`. That root is Waystone's configuration. Paths also carry a random UUID per attempt, so a mistaken second publish succeeds silently.
- **Receipts record incidental machine detail.** They hold full command lines, local paths and log paths, in three slightly different shapes, and audit modules depend on each shape.
- **Publication is copied four times.** The native-cache, sustained-checkpoint and sustained-pilot publishers, and the resource bundle, run the same workflow: stage, archive, store, read back, manifest, audit, release. They differ only in payload, inventory and destination. A fix made to one, such as ticket 27's existence check, does not reach the others. Each caller also hand-writes its own disk-reservation estimate.
- **Testing goes past the interface.** Tests inject fake subprocess runners or monkeypatch `subprocess`. When a runner is injected, the real kill path is skipped, so it has never been tested.

## Solution

Sureal asks a **blob store** to store, fetch or check a blob, and nothing more. The blob store is one module with a three-operation interface. HDFS through Waystone is one adapter behind it, alongside a local-file-system adapter and an in-memory adapter. Waystone decides where the project's root lives. Sureal only names **blob keys** relative to that root, such as `runs/perception-resource-closures/<run-id>/checkpoint/archive-000.tar.gz`. Blobs are written once.

On top of the blob store, one **publication module** runs the stage–archive–store–manifest–audit–release workflow for every case, driven by a per-case publication spec. Receipts record only what can be checked again later: blob keys, digests, sizes, a store descriptor and the pinned tool digest.

Callers migrate in two waves, live path first. The old wrappers are deleted at the end, and the balanced16 sweep is re-admitted once because its source snapshot changes.

## User Stories

1. As a researcher, I want to store a file as a blob by naming a blob key, so that I never have to know which storage system or cluster holds it.
2. As a researcher, I want storing a blob to return its key, sha256 and byte count, so that I can cite it in a receipt without computing those myself.
3. As a researcher, I want every stored blob read back and compared before `put` returns, so that a successful store means the bytes are really there.
4. As a researcher, I want storing identical bytes under an existing key to succeed without changing anything, so that a retried or resumed step is harmless.
5. As a researcher, I want storing different bytes under an existing key to fail as a conflict, so that a blob a receipt cites can never change underneath it.
6. As a researcher, I want no operation that deletes or replaces a blob, so that every receipt's citations stay true.
7. As a researcher, I want to fetch a blob to a local path and have its sha256 checked against the value I expect, so that corrupted or substituted bytes are caught at the point of use.
8. As a researcher, I want to ask whether a blob exists without listing a directory, so that existence is never inferred from parsing listing text.
9. As a researcher, I want the blob store to choose its own deadline for each transfer, scaled by size, so that large archives are not killed by a bound meant for small files and small files do not hang for minutes.
10. As a researcher, I want a hung transfer's whole process group killed when its deadline passes, so that no orphaned tool process holds files or credentials.
11. As a researcher, I want transient failures and timeouts retried inside the blob store, up to three attempts with backoff, so that one slow request does not fail a two-hour run.
12. As a researcher, I want five distinct failure kinds (Missing, Conflict, Corrupt, Unauthenticated, Unavailable), so that my code can react correctly to each.
13. As a researcher, I want an Unauthenticated failure to name the refresh script, so that I know the exact action that fixes it.
14. As a researcher, I want no tool exit codes or stderr text leaking out of the blob store, so that callers do not parse backend output.
15. As a researcher, I want the Waystone adapter to resolve the project root from Waystone itself, so that moving the cluster or root is a Waystone configuration change, not a repository change.
16. As a researcher, I want the Waystone tool's pinned digest checked before each operation and recorded once per receipt, so that a changed tool cannot slip into an admitted run.
17. As a researcher, I want a local-file-system adapter rooted at a directory, so that I can run publications and snapshots offline or on a machine without HDFS.
18. As a test author, I want an in-memory adapter, so that tests of anything that stores blobs run fast and without network or credentials.
19. As a test author, I want one set of contract tests that runs against every adapter, so that every backend is proven to behave identically at the interface.
20. As a test author, I want the Waystone adapter's contract tests opt-in under a `requires_hdfs` tag, so that the default test run stays offline while the real kill and timeout path is still provable on demand.
21. As a researcher, I want blob keys to begin with an area chosen by meaning, so that the store's retention and quota policy can tell kinds of data apart: checkpoints under `checkpoints/`, source snapshots under `artifacts/`, cohort data under `datasets/`, run closures under `runs/`.
22. As a researcher, I want blob keys below the area to read `<child>/<run-id>/<kind>/<name>`, with no UUID or digest segment, so that a key says what the blob is.
23. As a researcher, I want a second publication of the same run and kind refused unless the bytes are identical, so that double publication is caught, not hidden.
24. As a researcher, I want receipts to carry a store descriptor naming the adapter and project but no storage root, so that receipts stay valid if the root moves.
25. As a researcher, I want receipts to record, for each blob, only its key, sha256 and byte count, plus one readback flag, so that every recorded fact can be checked again from the blob itself.
26. As a researcher, I want receipts to leave out command lines, local paths and log paths, so that evidence describes the data, not the machine that moved it.
27. As a researcher, I want receipts written before this change, with their absolute `hdfs://` URIs, to remain readable, so that historical evidence can still be fetched and verified.
28. As a researcher, I want old URIs read by stripping the storage root to get a blob key, so that there is a single read path for old and new receipts.
29. As a researcher, I want source snapshots stored and fetched through the blob store, content-addressed under `artifacts/`, so that the most critical evidence path gets the blob store's deadlines, retries and typed failures.
30. As a researcher, I want one publication module driven by a publication spec, so that publishing a new kind of payload means writing a spec, not copying a publisher.
31. As a researcher, I want a publication spec to declare payload, inventory, area, kind, staging style (hardlink or copy) and release flag, so that the four existing publication workflows and the journal are expressed as data.
32. As a researcher, I want each publication to consist of chunk archives plus one manifest blob listing every chunk and the file inventory, so that there is one manifest to cite and verify.
33. As a researcher, I want the publication module to compute its own disk reservation from what it stages, so that no caller hand-writes a byte estimate.
34. As a researcher, I want local files released only after the publication is stored, read back and independently audited, so that release never loses the only copy.
35. As a researcher, I want one audit that reads the new receipt shape and rejects a tampered or incomplete receipt, so that every publication is verified the same way.
36. As an operator of the sustained controller, I want the sustained-checkpoint publication to keep its subprocess entry point and its `--lock-fd` lock handoff, so that the controller's process model does not change.
37. As a researcher, I want the research journal published as a publication spec, with files stored directly and no archive or release, so that journal publication gets the same retries and failure kinds.
38. As a maintainer, I want the evidence concept to own the journal but not its publication, so that dependencies point downward: retention depends on blob store, evidence and resources.
39. As a maintainer, I want the HDFS login keepalive left as it is, so that authentication renewal stays independent of blob transfers.
40. As a maintainer, I want the live path migrated first (source snapshots, resource bundle, sustained checkpoint, journal), so that the riskiest callers are proven early.
41. As a maintainer, I want the remaining callers (scientific-directory and symlink-audit publishers, native-cache and pilot publishers, and the dataset, camera, segmentation and geometry scripts) migrated in a second wave, one ticket per caller group, so that each change is small and gated.
42. As a maintainer, I want the old wrappers deleted once nothing imports them, and old-shape audit modules moved to procedure records, so that the working tree holds one way to store a blob.
43. As a maintainer, I want no blob key, store root or Waystone path hard-coded outside the blob store, so that a grep for the cluster name in active code finds nothing.
44. As a researcher, I want the balanced16 sweep re-admitted once after the migration, with a live admission and a journal entry, so that the sweep's source snapshot binds the code it will actually run.
45. As a reviewer, I want every migration ticket to keep the default CPU suite, the `--config=cuda` suite and `//parallax/...` green, so that the refactor never trades one regression for another.

## Implementation Decisions

- **New concept: the blob store.** A new top-level concept directory, `blob_store`, under the perception program, named for the concept, not the backend.
- **Blob store interface.** Three operations:
  - `put(key, file)` returns a record `{key, sha256, bytes}`.
  - `get(key, dest, sha256)` writes to `dest` and fails as Corrupt if the digest differs.
  - `exists(key)` returns a boolean.

  `put` reads the blob back before returning. A put of identical bytes under an existing key succeeds without changing anything; different bytes raise Conflict. There is no list, delete or overwrite.
- **Failure kinds.** Missing, Conflict, Corrupt, Unauthenticated and Unavailable. Unauthenticated names the refresh script. Unavailable means retries are exhausted. Nothing else escapes the interface.
- **Owned inside the blob store:**
  - **Deadlines:** a base time plus bytes divided by a minimum throughput.
  - **Hangs:** the process group is killed when a deadline passes.
  - **Retries:** up to three attempts with backoff, for every operation, which is safe because blobs are write-once.
  - **Authentication:** the token-file auth source.
  - **Tool pins:** checked before each operation.
  - **Output classification:** recognising missing and authentication markers.
- **Adapters.**
  - **Waystone:** production. Resolves the project root through Waystone's layout profile.
  - **Local file system:** a root directory. It absorbs today's local snapshot store.
  - **In-memory:** for tests.
- **Store descriptor.** Written once per receipt, as `{kind, project}` for Waystone and `{kind, root}` for local. A factory builds an adapter from a descriptor, replacing today's store-from-receipt logic. Old descriptors that carry an absolute prefix are accepted and mapped to the Waystone adapter.
- **Blob keys.**
  - Areas by meaning: `checkpoints`, `artifacts`, `datasets`, `runs`.
  - Below the area: `<child>/<run-id>/<kind>/<name>`. Source snapshots are content-addressed, as `artifacts/source-snapshots/<sha256>`.
  - No UUID segments.
  - Old absolute URIs are read by stripping Waystone's storage root.
- **Receipt shape for transfers.** Per blob: `{key, sha256, bytes}`. Per receipt: the store descriptor, the pinned Waystone tool digest, and a `verified_by_readback` flag. No command lines, local paths or log paths. Transfer logs may stay in the run's evidence directory without being cited.
- **Publication module.**
  - Lives in the retention concept.
  - Interface: publish a publication spec to get a publication receipt, and audit a publication receipt.
  - A publication spec declares payload, inventory function, area, child, kind, staging style (hardlink or copy), archive or direct mode, and release flag.
  - A publication is chunk archives plus one manifest blob listing every chunk's `{key, sha256, bytes}` and the file inventory. Per-chunk manifests are dropped.
  - The module computes its own disk reservation through the existing scientific budget.
  - Release happens only after store, readback and audit.
- **Five publication specs:**
  - native cache
  - sustained checkpoint
  - sustained pilot
  - resource bundle (staging by hardlink, no release)
  - research journal (direct files, no archive, no release)
- **Entry points kept.** The sustained-checkpoint publication keeps its subprocess entry point and `--lock-fd` lock handoff. The sustained controller's readers of publication receipts are updated to the new shape.
- **Dependencies.** retention → blob_store, evidence, resources. The evidence concept keeps the journal (append, verify) and stops publishing it. The blob store depends on nothing above it.
- **Old audits.** The three retention audits and the resource retention audit that read old receipt shapes move to procedure records; one new audit reads the new shape.
- **Keepalive.** The HDFS login keepalive is unchanged. It may read the pinned tool path from the blob store's Waystone adapter.
- **Migration order.**
  1. The blob store and its three adapters.
  2. Source snapshots.
  3. The publication module with the resource-bundle and sustained-checkpoint specs.
  4. The research journal spec.
  5. Wave 2 caller groups: the scientific-directory and symlink-audit publishers; the native-cache and pilot specs; dataset scripts; camera; segmentation; geometry.
  6. Delete the old wrappers.
  7. Re-admit balanced16.
- **Source pins.** Changing these modules changes the source snapshots of every gate that runs them. Per autonomy ADR 0001, pinned bytes stay in their source snapshots, so modules may be edited and deleted in the working tree.

## Testing Decisions

- **Good tests use the interface only.** Tests exercise the blob store interface and the publication module interface. They do not monkeypatch `subprocess`, inject command runners, or patch private names. Where a caller's existing tests inject a fake runner or patch functions, they instead pass an in-memory blob store.
- **Blob store contract tests.** One suite, written once against the interface and run against all three adapters. It covers:
  - put and readback
  - identical repeat put
  - conflicting put
  - a get whose digest does not match
  - a missing key
  - exists
  - deadline expiry
  - retry then success
  - retry exhaustion as Unavailable
  - Unauthenticated naming the refresh script

  The in-memory and local adapters run in the default suite. The Waystone adapter runs under the opt-in `requires_hdfs` tag against a scratch area, which is the only place the real kill path is exercised. The in-memory adapter supports injected faults (delay, transient failure, auth failure) so that the deadline and retry behaviour is testable without HDFS.
- **Publication module tests.** Drive each of the five specs through publish and audit with an in-memory blob store. They cover:
  - chunking
  - the single manifest
  - readback
  - disk reservation
  - release only after a passing audit
  - refusal of a repeat publication with different bytes
  - the audit rejecting a tampered key, digest, size or missing chunk
- **Prior art:**
  - the runner-injected tests of the source snapshot store, which become contract-suite cases
  - the fake Waystone in the scientific-directory publisher tests, which becomes the in-memory adapter
  - the existing retention audit tests, which are reworked against the new shape
- **Gates per ticket.** The default CPU suite, the `--config=cuda` suite and `//parallax/...` pass with counts recorded. Wave 1 tickets also run the `requires_hdfs` contract suite once.
- **End-to-end check.** The balanced16 live re-admission: a live implementation gate whose receipts verify against the new store descriptor and blob keys.

## Out of Scope

- Changing Waystone itself, its layout profile, or the HDFS login keepalive.
- Copying or moving blobs already stored under the old layout.
- Running the balanced16 sweep. Only its re-admission is in scope.
- Ticket 29 (the M0 rootfs rebuild and the semantic-recovery rows).
- The other architecture-review candidates: runtime-lock launch plans, box geometry, metric parsing, the path layout module, retiring variant copies, receipt canonical JSON, Waymo record decoding, and the sustained controller.
- Parallax, which does not use Waystone.

## Further Notes

- The architecture review that produced this spec ranked the blob store as its top candidate and the publication module as third. They are designed together because the publication module is built on the blob store.
- Delegate implementation to TraeCLI worker sessions, one ticket each, with the coordinator re-running the gates before accepting a ticket. This is the same model used for semantic-layout tickets 26 and 27.
