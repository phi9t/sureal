# 03: Persist every active rootfs and lock in private GHCR, and restore by lock

**What to build:** Every active Insula rootfs, together with its `.lock.json`, can be pushed to private GHCR as an OCI artifact. It can be pulled back after a cache loss, and is renamed into place only when `load_runtime_lock` accepts the restored tree. The 2026-10-10 cache loss then becomes a routine restore rather than a forensic rebuild.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Approved by the user on 2026-10-10. Modelled on Vaso's `scripts/publish/artifact_store.py` and `docs/agents/publication.md`.

## Design

- **Scope.** The active rootfs set comes from `autonomy/insula/runtime_roots.py`: CPU, GPU, metrics, motion-metrics, motion-cli and Parallax curriculum, plus any rootfs added there later. There is one package per rootfs, `ghcr.io/phi9t/sureal-rootfs-<role>`, tagged with the first 12 hex characters of the lock sha256. Restores are pinned by manifest digest.
- **Archive.**
  - The tar is deterministic: `--sort=name --mtime=@<fixed epoch> --owner=0 --group=0 --numeric-owner`, keeping only the `security.capability` xattr. It is compressed with `zstd -19`, at the same thread count, so the output bytes are reproducible.
  - The archive is split into parts no larger than a configurable size (default 1 GiB).
  - The lock file travels in the same artifact.
  - Manifest annotations record:
    - every file's path, sha256 and size;
    - the archive sha256;
    - the rootfs name and lock sha256;
    - the `rootfs_sha256` recorded in the lock.
- **Push.**
  - Packing is staged under a temporary directory and never writes into the rootfs or its lock.
  - A push refuses to run if `load_runtime_lock` rejects the local rootfs.
  - A push of a tag that already exists with a different manifest digest is refused. A push of identical content is a no-op.
  - After a real push, the tool calls the GitHub package API and fails unless the package is private.
- **Pull and restore.**
  1. Pull into staging and verify every part's sha256 and the reassembled archive's sha256.
  2. Extract to `<rootfs>.restore.XXXXXX` beside the target, and place the lock beside it.
  3. Run `load_runtime_lock` on the staged tree.
  4. Only then rename the tree and lock into place.

  The target and its lock must be absent; a restore never overwrites. On any mismatch the staged copy is left in place and the command fails.
- **Credentials.** The token is read from `GHCR_TOKEN`, or from the file named by `SUREAL_GHCR_TOKEN_FILE`, which must be mode 600. It is never logged, echoed or committed. Command output passes through redaction.
- **Tooling.** ORAS 1.3.4 is pinned by sha256 (`f27adb935022d94df8dc77719c322dda592c78a0d57a6f7dcdd8d900b248c454`, linux_amd64), and the installer verifies the digest. Push and pull run on the host, because they need network access and the docker-free host filesystem. Document this as a host publication step, as AGENTS.md describes for other host-only checks.
- **Dry run.** `--dry-run --registry <dir>` uses an ORAS OCI layout directory and never contacts the network. All tests use this mode.

## Acceptance

- [ ] **Code.** The `push`, `pull` (restore) and `verify` commands live in an Autonomy module under `autonomy/insula/` (the concept that owns rootfs and locks), with co-located tests. A thin CLI follows `docs/guides/python-style.md`.
- [ ] **Tests**, using the dry-run OCI layout and a small fixture rootfs:
  - packing is deterministic, so the same tree gives the same archive sha;
  - a round trip gives the same `rootfs_sha256`;
  - a tampered part fails;
  - an existing target is refused;
  - a lock mismatch leaves the staged copy in place and fails;
  - an existing tag with different content is refused;
  - tokens are redacted from all output.
- [ ] **Live dry run, first.** Push all active rootfs to a local OCI layout, outside the repo and outside `~/.cache/waystone`. Pull each one into a scratch cache root and show that `load_runtime_lock` accepts it. Record:
  - sizes;
  - part counts;
  - archive digests;
  - durations.
- [ ] **Coordinator-only real push.** The coordinator pushes to `ghcr.io/phi9t`, records the manifest digests in this ticket, and shows each package is private. The coordinator also does one real pull-and-verify of the smallest rootfs into a scratch cache root.
- [ ] `docs/agents/` gains a short "persist and restore rootfs" runbook.
- [ ] **Gates:** `//:repo_gate`, `//autonomy/...` and `//parallax/...`.
