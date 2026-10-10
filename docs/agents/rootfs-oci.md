# Persist And Restore Rootfs Artifacts

This is a host publication procedure for Insula root filesystems. Bazel
verification still runs through `./bazelw`; registry publication is host-side
because it needs network access and a docker-free filesystem.

The rootfs publisher lives in `autonomy/insula/rootfs_oci.py`. Dry-run mode
writes an OCI image layout under a caller-provided directory and never contacts
the network. Real GHCR pushes and pulls are coordinator-only for the
rootfs-rebuild workflow.

## Dry Run

Use a scratch root outside the repository and outside `~/.cache/waystone`.
Use this path for the 2026-10-10 closeout dry run:

```bash
dry_root=~/devx/tmp/sureal-refactor-20261007/rootfs-oci-dryrun
```

The dry run can be executed inside the CPU Insula rootfs by mounting
`~/.cache/waystone` as read-only source and the dry-run root as writable output:

```bash
PYTHONPATH=autonomy python3 -m insula.entry \
  --source ~/.cache/waystone \
  --output "$dry_root" \
  -- \
  python -m insula.rootfs_oci --json push-active --dry-run \
    --registry /outputs/registry \
    --work-dir /outputs/work/push-active \
    --waymo-cache /source/waymo-perception \
    --pathway-cache /source/3d-pathway \
    --zstd-bin /outputs/tools/bin/zstd
```

Restore each reported digest into a scratch cache root under the same
`dry_root`, then verify with `load_runtime_lock`:

```bash
PYTHONPATH=autonomy python3 -m insula.entry \
  --source ~/.cache/waystone \
  --output "$dry_root" \
  -- \
  python -m insula.rootfs_oci --json pull --dry-run \
    --registry /outputs/registry \
    --role cpu \
    --digest sha256:<manifest-digest> \
    --target-rootfs /outputs/restore/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z \
    --work-dir /outputs/work/restore-cpu \
    --zstd-bin /outputs/tools/bin/zstd
```

The restore command refuses an existing rootfs or lock. It extracts into
`<rootfs>.restore.XXXXXX` beside the target, copies the lock beside that staged
tree, runs `load_runtime_lock`, and renames the tree and lock into place only
after the lock accepts the restored bytes. If the lock check or artifact digest
check fails, the staged restore is left in place for inspection.

## Real GHCR Push

Real registry operations are coordinator-only. Install the pinned ORAS binary
into a scratch tools directory:

```bash
PYTHONPATH=autonomy python3 -m insula.rootfs_oci --json install-oras \
  --destination ~/devx/tmp/sureal-refactor-20261007/rootfs-oci-dryrun/tools/bin
```

The installer downloads ORAS 1.3.4 linux_amd64 and verifies sha256
`f27adb935022d94df8dc77719c322dda592c78a0d57a6f7dcdd8d900b248c454`.

For a real push, provide `GHCR_TOKEN` or `SUREAL_GHCR_TOKEN_FILE`; a token file
must be mode `600`. The command redacts token values from subprocess errors and
checks the GitHub package API after push so `ghcr.io/phi9t/sureal-rootfs-<role>`
is private.
