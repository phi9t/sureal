# 03: Persist every active rootfs and lock in private GHCR, and restore by lock

**What to build:** Every active Insula rootfs, together with its `.lock.json`, can be pushed to private GHCR as an OCI artifact. It can be pulled back after a cache loss, and is renamed into place only when `load_runtime_lock` accepts the restored tree. The 2026-10-10 cache loss then becomes a routine restore rather than a forensic rebuild.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

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

- [x] **Code.** The `push`, `pull` (restore) and `verify` commands live in an Autonomy module under `autonomy/insula/` (the concept that owns rootfs and locks), with co-located tests. A thin CLI follows `docs/guides/python-style.md`.
- [x] **Tests**, using the dry-run OCI layout and a small fixture rootfs:
  - packing is deterministic, so the same tree gives the same archive sha;
  - a round trip gives the same `rootfs_sha256`;
  - a tampered part fails;
  - an existing target is refused;
  - a lock mismatch leaves the staged copy in place and fails;
  - an existing tag with different content is refused;
  - tokens are redacted from all output.
- [x] **Live dry run, first.** Push all active rootfs to a local OCI layout, outside the repo and outside `~/.cache/waystone`. Pull each one into a scratch cache root and show that `load_runtime_lock` accepts it. Record:
  - sizes;
  - part counts;
  - archive digests;
  - durations.
- [x] **Coordinator-only real push.** The coordinator pushes to `ghcr.io/phi9t`, records the manifest digests in this ticket, and shows each package is private. The coordinator also does one real pull-and-verify of the smallest rootfs into a scratch cache root.
- [x] `docs/agents/` gains a short "persist and restore rootfs" runbook.
- [x] **Gates:** `//:repo_gate`, `//autonomy/...` and `//parallax/...`.

## Comments

### 2026-10-10 worker rr03 implementation and blocked live dry run

Implemented `autonomy/insula/rootfs_oci.py` with `push`, `push-active`,
`pull`, `verify` and `install-oras` CLI commands. The implementation:

- loads every local rootfs through `load_runtime_lock` before packing;
- stages deterministic GNU tar plus zstd archives without writing into the
  rootfs or its lock;
- splits archives into bounded parts and writes a dry-run OCI image layout;
- records the rootfs file inventory, archive digest, rootfs name, lock digest
  and lock `rootfs_sha256` in the embedded rootfs manifest, and mirrors every
  rootfs file path, sha256 and size into `io.sureal.rootfs.entry.*` OCI
  manifest annotations;
- records each artifact file path, sha256 and size in `io.sureal.file.*` OCI
  manifest annotations, and uses ORAS `--annotation-file` for real pushes so
  the coordinator path does not depend on shell argument limits;
- refuses existing restore targets and existing tags with different content;
- restores into `<rootfs>.restore.XXXXXX`, runs `load_runtime_lock`, and renames
  the rootfs and lock into place only after the staged tree is accepted;
- reads `GHCR_TOKEN` or a mode-`600` `SUREAL_GHCR_TOKEN_FILE` only for
  non-dry-run registry operations and redacts token values from command errors.

Added `autonomy/insula/rootfs_oci_test.py` covering the dry-run fixture
acceptance cases:

- deterministic packing: same fixture tree produced the same archive sha;
- round trip: restore preserved the fixture `rootfs_sha256` and was accepted by
  `load_runtime_lock`;
- tampered part: restore failed on digest verification before extraction;
- existing target: restore refused an existing rootfs;
- lock mismatch: staged restore was left in place and failed at
  `load_runtime_lock`;
- tag conflict: an existing tag with different content was refused;
- token redaction: subprocess errors replaced the token value with
  `<redacted>`.
- rootfs entry annotations: the OCI manifest included every fixture regular
  file path, sha256 and size under `io.sureal.rootfs.entry.*`.

Added `docs/agents/rootfs-oci.md` with the dry-run and coordinator-only GHCR
runbook. Host paths in the runbook use `~`.

Checks run:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:rootfs_oci_test`
  first failed as expected before the rootfs-entry annotation helper with
  `KeyError: 'io.sureal.rootfs.entry.count'`, then passed after the fix, 1/1
  test.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:all_tests`
  passed, 11/11 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`
  passed, 1/1 test.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed, 19/19 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed, 190/190 tests.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed, 17/17 tests.

ORAS tooling preflight:

- Downloaded `oras_1.3.4_linux_amd64.tar.gz` in this worker's declared temp
  directory and verified the pinned sha256
  `f27adb935022d94df8dc77719c322dda592c78a0d57a6f7dcdd8d900b248c454`.
- Extracted `oras`; `oras version` reported version `1.3.4`, commit
  `db9e29505c3059f2b8fde34ae8cae266c5c765e9`, linux/amd64.

Disk preflight before live packaging:

- `df -B1 /data02` reported `291636883456` bytes available, above the 200 GB
  floor.
- Active rootfs read-only inventory sizes before packing:
  - CPU `~/.cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z`:
    13,768 regular files, `786M`.
  - GPU `~/.cache/waystone/waymo-perception/gpu-rootfs-v7`: 54,628 regular
    files, `13G`.
  - metrics `~/.cache/waystone/waymo-perception/metrics-rootfs`: 14,542 regular
    files, `600M`.
  - motion-metrics `~/.cache/waystone/waymo-perception/motion-metrics-rootfs`:
    14,770 regular files, `640M`.
  - motion-cli `~/.cache/waystone/waymo-perception/motion-cli-rootfs-v2`: 14,799
    regular files, `643M`.
  - Parallax curriculum `~/.cache/waystone/3d-pathway/insula/rootfs-v3`: 14,380
    regular files, `744M`.

Live dry run was not executed in this worker sandbox because the mandated output
root is not writable here:

```bash
mkdir -p ~/devx/tmp/sureal-refactor-20261007/rootfs-oci-dryrun/rr03-<timestamp>/{tools/bin,tools/src,registry,work,restore,logs}
```

Result:

```text
mkdir: cannot create directory '~/devx/tmp/sureal-refactor-20261007/rootfs-oci-dryrun': Read-only file system
```

The live-dry-run acceptance box remains unchecked. No dry-run OCI layout or
restore scratch root was created, so there are no live rootfs package sizes,
part counts, archive digests or durations from this worker. The
coordinator-only real GHCR push/pull box also remains unchecked by design.

### 2026-10-11 coordinator: live dry run

The worker's sandbox could not write the dry-run root, so the coordinator ran the live dry run on the host with ORAS 1.3.4 (sha256-verified) and zstd 1.5.7.

**Push.** `push-active --dry-run` packed all six active rootfs in 4807 s, 61 min of which was the GPU rootfs at `zstd -19`. The registry holds 6.3 GB.

| Role | Archive bytes | Parts | Tag | Manifest digest |
| --- | ---: | ---: | --- | --- |
| cpu | 228022658 | 1 | `318e827c4832` | `sha256:9c0609c6cca7ccf4b115fddeba2e8fe1bd5f30f3fb88c6fd8e725539b75e5f66` |
| gpu | 5834231161 | 6 | `c68df2817045` | `sha256:90061e3c1307217e6f483595bc80f4afdad6e161cc008e315b115a76d921c7fd` |
| metrics | 135877302 | 1 | `bfcf5f5e6e91` | `sha256:732dad7bfb091de0d8b08f4529fce725ae8c6bb7808cb004420d459413febd33` |
| motion-metrics | 139104107 | 1 | `ede873533967` | `sha256:3efede285940305d6123fb7118b8235e52c6e1b846788de23ce07e7b226eab93` |
| motion-cli | 139387898 | 1 | `e165e1a10fa7` | `sha256:457d012328911232b4f7e33e6e0ba2850d9a764044be135b12ef5525ef153ff8` |
| parallax-curriculum | 208429317 | 1 | `8df13a37ef3a` | `sha256:37a845b9c177530e7f87dd2d7c07e8a98f5ee7a162c75dd9fef7927443ab26e5` |

**Bug found and fixed.** The first restore round trip failed 5 of 6 rootfs. The staged tree was named `<name>.restore.XXXX`, and `load_runtime_lock` selects the recipe spec from the rootfs name, so every non-CPU rootfs was checked against the CPU recipe. No restore was promoted, so the refusal rule held. A restore now stages at `<parent>/.<name>.restore.XXXX/<name>`, which keeps the basename and parent path, and the stage directory is removed after promotion. The test was updated to the new layout.

**Restore after the fix.** All six restored into a scratch cache root in 176 s in total (95 s for gpu). Each passes `load_runtime_lock` with its original lock sha and `rootfs_sha256`, and no staged directories were left behind.

### 2026-10-11 coordinator: first real push found two bugs

- **Annotations dropped.** The real `metrics` push succeeded and the package is private (checked through the GitHub API). But the manifest carried no `io.sureal.*` annotations, so the real pull refused it with "manifest artifact kind is not rootfs". Cause: the ORAS `--annotation-file` used the key `manifest`, but ORAS reads manifest annotations only under `$manifest`. The dry run did not catch this because it writes the OCI layout without ORAS. Fixed through `oras_annotation_document`, which has a test.
- **Manifests too large.** Dry-run manifests carried one annotation per rootfs file: 3.4 MB for cpu and 14.6 MB for gpu. That is over GHCR's 4 MiB manifest limit. Per-file entries now live only in the digest-checked `manifest/rootfs-manifest.json` layer, and the manifest keeps `io.sureal.rootfs.entry.count` plus summary annotations.
- **Broken version left behind.** The broken `sureal-rootfs-metrics:bfcf5f5e6e91` version (`sha256:4933ad31…`, created 2026-10-11T01:33:43Z) cannot be deleted with the current token, which returned 403 for lack of `delete:packages`. The tool correctly refuses to overwrite the tag. The user needs to delete that version before `metrics` is pushed again.

### 2026-10-11 coordinator: real GHCR push complete

All six active rootfs are in `ghcr.io/phi9t`. They were pushed from `04db57a`, with `metrics` re-pushed using the code that added `--replace-tag`. Each package was pulled back from GHCR, restored into a scratch cache root, and accepted by `load_runtime_lock` with its original lock sha and `rootfs_sha256`. The GitHub package API reports every package as `private`.

| Package | Tag | Manifest digest | Push | Pull |
| --- | --- | --- | ---: | ---: |
| `sureal-rootfs-cpu` | `318e827c4832` | `sha256:b3ecfa1ca61e4d7a862c496c97d68382071575bab1697fadea919bee3e661830` | 272 s | 11 s |
| `sureal-rootfs-gpu` | `c68df2817045` | `sha256:12251373c19f0c3ed5bb5583d5ff347cf69fa1eb5d62b37b9211366906834d36` | 3490 s | 114 s |
| `sureal-rootfs-metrics` | `bfcf5f5e6e91` | `sha256:1b63d5b06b0be90cbd0dfa8cb4bcc3f268141330dde83fe19b5e78f46543fd44` | 197 s | — |
| `sureal-rootfs-motion-metrics` | `ede873533967` | `sha256:12ede83aab56f75a334be13a5a3acc6a284c292100f6366057f2e064ff9681b0` | 215 s | 10 s |
| `sureal-rootfs-motion-cli` | `e165e1a10fa7` | `sha256:1ba881840802060fc56415e5790728d548a7f26071b5a743d7ec97aec9418563` | 215 s | 9 s |
| `sureal-rootfs-parallax-curriculum` | `8df13a37ef3a` | `sha256:537f6b6720222e09633ac1900fbbc64f6d9e961a326f67701b1f8e905422033c` | 220 s | 11 s |

`metrics` repair: the broken first push (`sha256:4933ad31…`) could not be deleted, because the token lacks `delete:packages`. On the user's instruction ("you can override this time"), the tag was moved with the new explicit `--replace-tag` flag. The default still refuses, and tests cover both cases. The broken manifest remains in the package, untagged. It can be deleted from the GitHub UI later.

Restoring all six from GHCR takes about 3 minutes of pull time.
