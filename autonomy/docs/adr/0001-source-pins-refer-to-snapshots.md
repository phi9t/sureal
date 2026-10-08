---
status: accepted
---

# A source pin refers to a source snapshot, not to the working tree

Receipts used to pin the digests of files in the working tree, so editing or moving any pinned file left its receipts describing bytes the tree no longer held. That made almost every file immutable in place and produced the `_v2`/`_v3` copies. From now on a source pin refers to a source snapshot: the transitive sources of the gate's Bazel target, archived when the gate runs, stored content-addressed in HDFS, with the receipt recording the archive's digest. The working tree is free to change.

## Considered options

- **Keep requiring the working tree to match.** Rejected: it forbids restructuring and forces every change into a new file.
- **Pin a git commit and recover bytes from history.** Rejected: it does not survive history rewrites and ties evidence to one repository's history.
- **Commit snapshots to git under `research/`.** Rejected: `research/` is already 89 MB.

## Consequences

- Receipts written before this decision are historical records. Their pinned bytes are recoverable from git history but are not expected to match the tree.
- Checks that compared tracked receipts with the working tree are retired in favour of verifying against the snapshot. `architecture.py verify` without `--run-id` is the one such command.
- Verifying an old gate needs HDFS access to fetch its snapshot.
