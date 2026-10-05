# 09: Evidence module: snapshot, fetch and verify

**What to build:** A researcher can take a source snapshot of a build target, get its digest, and later verify a receipt's source pins against that snapshot without the working tree. One module owns this, together with the shared file-digest and regular-file helpers that are currently copied across the codebase.

**Blocked by:** 07 (Rename the perception program to `autonomy/`)

**Status:** ready-for-agent

- [x] Taking a snapshot of a Bazel target archives exactly that target's transitive sources and returns the archive's digest
- [x] The archive is deterministic: the same sources produce the same digest regardless of timestamps, ownership or file order
- [x] Changing, adding or removing any source in the target's closure changes the digest
- [x] Storage is behind an interface; a local-directory adapter stores and fetches snapshots keyed by digest
- [x] Verification passes for a receipt and its snapshot, fails for an altered snapshot, and fails explicitly for a missing one
- [x] Verification never reads the working tree; a test proves this by verifying after the sources are deleted
- [x] The module exposes one file-digest function and one regular-file check, with tests covering symlinks
