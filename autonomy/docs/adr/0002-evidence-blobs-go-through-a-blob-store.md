---
status: accepted
---

# Evidence blobs go through a backend-neutral, write-once blob store

Autonomy stores and fetches every file that evidence must be able to retrieve later through one blob store. The store has three operations: put, get and exists. HDFS through Waystone is one adapter behind it, alongside a local file system and an in-memory store. Blobs are written once. A put of identical bytes succeeds without changing anything, a put of different bytes is a conflict, and nothing is ever deleted. Receipts cite a blob key (such as `runs/perception-resource-closures/<run-id>/<kind>/archive-000.tar.gz`), its sha256 and byte count, and a store descriptor such as `{kind: "waystone", project: "sureal"}`. They never cite a storage root. The adapter resolves the root at read time, because where the project's files go is Waystone's configuration, not sureal's. We chose this after eight callers each wrapped the Waystone CLI with their own timeouts, path layouts and output parsing, and ticket 27 failed on two of those differences.

## Considered options

- **Absolute `hdfs://…` URIs in receipts and code.** This is how things were before. Rejected because it hard-codes the cluster and user into code, audits and evidence, and ties the repository to one backend.
- **Unique paths per attempt (a random UUID segment).** Rejected because it lets a mistaken second publish succeed silently. With write-once keys, a repeat publish is refused unless the bytes are identical.

## Consequences

- Receipts written before this decision keep their absolute URIs. The blob store reads them by stripping the storage root, so there is one read path.
- Changing which modules the sustained run executes changes the balanced16 sweep's source snapshot, so the sweep must be re-admitted after the migration.
