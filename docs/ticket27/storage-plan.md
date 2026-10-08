# Ticket 27 Storage Plan

Generated: 2026-10-08T05:15:45Z

Worker branch: `worker/t27d-storage-plan`

Bound start: `8eda504`

Scientific root:
`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing`

Evidence root:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007`

This is a plan-only closeout document. This worker did not upload to HDFS,
release, move, delete, or mutate the Waymo cache. The 15 GiB cap in
`autonomy/resources/scientific_budget.py` and the symlink-refusing accounting
in `autonomy/resources/scientific_payload.py` remain unchanged.

## Required Outcome

Ticket 27 needs live admission space under the existing gate:

| Item | Bytes |
| --- | ---: |
| Scientific cap, `15 * 1024**3` | 16106127360 |
| Target after release, `11 * 1024**3` | 11811160064 |
| Ticket 27 reservation | 2147483648 |
| Current diagnostic accounting, excluding only the symlink audit dir | 15301703072 |
| Bytes to release to meet the 11 GiB target | 3490543008 |

The strict current call to `unique_payload_bytes(W)` raises before returning
bytes because every symlink under `W` is inside
`motion-current-geometry-audit-v3`. Diagnostic accounting therefore used the
same hardlink-aware `(st_dev, st_ino)` regular-file logic with only that
top-level audit directory excluded. That models the value the gate should see
after the audit directory is moved out of `W`, assuming no other cache changes.

Strict failure captured by ticket 27b:

```text
ValueError: scientific payload entries must not be symlinks: /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3/red/mutants/xyz_shift/6-5-1-range.features.bin
```

Symlink inventory:

| Scope | Symlinks |
| --- | ---: |
| All symlinks under `W` | 2970 |
| Symlinks under `motion-current-geometry-audit-v3` | 2970 |
| Symlinks outside that audit dir | 0 |

## Tooling Read

Current first-class publishers are specific, not general:

| Tool | Current supported payload | Release support | Storage-plan disposition |
| --- | --- | --- | --- |
| `autonomy/retention/publish_native_cache.py` | `overfit-native-cache-v1` | Yes, via `--release` and `resource_release_plan.release_plan` | Valid precedent, but not a command for the selected top-level candidates. Existing native-cache HDFS copies are for `overfit-native-cache-v1`, not `native-overfit-v1`. |
| `autonomy/retention/publish_sustained_checkpoint.py` | sustained checkpoint receipts | Yes, via `--release` | Valid precedent for checkpoint outputs, not arbitrary closed directories. |
| `autonomy/retention/publish_sustained_pilot.py` | `balanced16-sustained-admission-*` | Yes, via `--release` | Current sustained pilot path, but ticket 27 protects balanced16 inputs and current sustained state. |
| `autonomy/resources/retention.py` | backend-supplied `shared` and `checkpoint` resource inventories | Releases only new temp and staging bytes | Good HDFS/readback/audit machinery, but deliberately does not release original model/checkpoint payloads. |
| `autonomy/resources/resource_archive.py` | deterministic regular-file tar chunks | No direct HDFS or source release | Useful primitive for regular-file candidates; refuses symlinks. |
| `autonomy/resources/resource_release_plan.py` | complete regular-file source inventory with HDFS/live stages | Returns unlink plan | Refuses source symlinks and requires complete publication checks. |
| `autonomy/studies/*/procedure_records/*` | historical procedure records | Historical only | They import legacy modules and are not current first-class runnable commands. |

Conclusion: the regular-file candidate release is byte-feasible, but this
checkout does not contain a current exact command that archives and releases an
arbitrary top-level `W/<case>` directory. Before any execution, land or
restore a reviewed publisher that wraps the existing `resource_archive`,
HDFS put/get, exact readback, independent live verify/rehydrate, receipt
writing, `resource_release_plan.release_plan`, and release steps. Do not run a
local release for these candidates without that complete publication receipt.

The symlink audit is a separate tooling gap: `resource_archive.py` and
`resource_release_plan.py` both refuse symlinks. A symlink-preserving audit
publisher is required before HDFS upload or move.

## Protected Exclusions

These entries must not be archive-and-release candidates for ticket 27 storage
recovery.

| Entry | Evidence | Reason |
| --- | --- | --- |
| `balanced16-native-v2` | `autonomy/training_execution/sustained_controller_backend.py:149` sets `self.native=W/'balanced16-native-v2'`; line 193 bind-mounts it to `/tmp/native`. `autonomy/training_execution/admit_sustained.py:57,84` does the same. | Current ticket 27 admission reads it. |
| `balanced16-physical-v2` | `autonomy/resources/dependencies.py:36` reads physical inputs; sustained controller line 193 and admit line 84 bind it. | Current resource dependency and admission input. |
| `balanced16-labels-v2` | `autonomy/resources/dependencies.py:37` reads box labels; sustained controller line 193 and admit line 84 bind it. | Current resource dependency and admission input. |
| `cohort16-baseline-balanced20261002a` | `autonomy/training_execution/sustained_controller_backend.py:149` and `autonomy/training_execution/admit_sustained.py:55` read `insula/cohort16-baseline-balanced20261002a/run.json`. | Current frames manifest source. |
| `balanced16-sustained-baseline-controller20261003a` | `autonomy/training_execution/run_sustained.py:88` resumes existing `balanced16-sustained-*` state; user explicitly protected this run. | Current sustained controller state. |
| `resource-retention-balanced16-sustained-baseline-controller20261003a-shared-*` | HDFS read-only listing showed existing `perception-resource-closures/balanced16-sustained-baseline-controller20261003a-shared-*`; user explicitly named these as prior examples, not release candidates. | Prior balanced16 resource retention examples and protected by instruction. |
| Anything referenced by `autonomy/research/balanced16-sustained.candidate.json`, 27a, or 27b | 27a binds the candidate JSON, source closures, and live admission inputs; 27b records the storage failure and current protected top entries. | Preserves preregistration and live readmission contract. |

Bounded inclusion grep for the planned regular-file candidates:

```bash
rg -n 'cohort-v1|cohort16-baseline-fit20261002a|cohort16-residual_bev-balanced20261002b|native-overfit-v1|architecture-window_bev-v1|architecture-coarse_mlp-v1|architecture-deep_pfn-v1|norm-gn_backbone-v1|norm-no_norm-v1' \
  autonomy --glob '!autonomy/research/**' --glob '!autonomy/studies/**' --glob '!**/*_test.py'
# exit 1, no current executable-code hits
```

Direct-name retention receipt search found only the source/procedure
directories for these candidates, not exact `hdfs-retention-<name>-*` or
`resource-retention-<name>-*` receipts. Read-only HDFS listings showed
historical namespaces for `perception-overfit`, `perception-resource-closures`,
`perception-motion`, `perception-native-cache`, and
`perception-sustained-checkpoints`, but not exact HDFS publications for the
selected candidate names.

## Candidate Order

The table is ordered by release safety, not by byte size. "Release bytes" are
hardlink-aware bytes that would disappear from `W` if the entry were unlinked
now, using the saved diagnostic inventory. "Unique bytes" are unique regular
bytes within the entry itself.

| Rank | Entry | Unique bytes | Release bytes | Mtime UTC | Producer/procedure evidence | Current consumer | Retention/HDFS status |
| ---: | --- | ---: | ---: | --- | --- | --- | --- |
| 1 | `cohort16-baseline-fit20261002a` | 1803535619 | 1776271853 | 2026-10-02T06:01:44Z | `insula/cohort16-baseline-fit20261002a` contains `run.json`, `train-verified.json`, `loss-verified.json`, `coverage-verified.json`, `checkpoint-verified.json`, and `protocol-verified.json`. | None found by bounded current-code grep; not in 27a/27b protected set. | No exact direct-name local retention receipt or HDFS listing found. Requires general regular-file publisher. |
| 2 | `cohort16-residual_bev-balanced20261002b` | 1367303352 | 1367303352 | 2026-10-02T15:49:12Z | `insula/cohort16-residual_bev-balanced20261002b` contains verified training/loss/coverage/checkpoint evidence plus scoring/audit diagnostics. | None found by bounded current-code grep; not in 27a/27b protected set. | No exact direct-name local retention receipt or HDFS listing found. Requires general regular-file publisher. |
| 3 | `native-overfit-v1` | 494810466 | 494810466 | 2026-10-01T16:11:14Z | `insula/native-overfit-v1/inputs/manifest.json`; older native overfit experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | No exact direct-name local retention receipt or HDFS listing found. Existing `overfit-native-cache-v1` publisher does not cover this name. |
| 4 | `architecture-window_bev-v1` | 361668688 | 361668688 | 2026-10-02T02:20:51Z | `insula/architecture-window_bev-v1/inputs/manifest.json`; closed architecture experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | No exact direct-name local retention receipt or HDFS listing found. Requires general regular-file publisher. |
| 5 | `architecture-coarse_mlp-v1` | 361668652 | 361668652 | 2026-10-02T02:23:59Z | `insula/architecture-coarse_mlp-v1/inputs/manifest.json`; closed architecture experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | No exact direct-name local retention receipt or HDFS listing found. Requires general regular-file publisher. |
| 6 | `architecture-deep_pfn-v1` | 358566392 | 358566392 | 2026-10-02T02:00:17Z | `insula/architecture-deep_pfn-v1/inputs/manifest.json`; closed architecture experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | Fallback only; same tooling gap. |
| 7 | `norm-gn_backbone-v1` | 358512202 | 331248436 | 2026-10-01T22:54:53Z | `insula/norm-gn_backbone-v1/inputs/manifest.json`; closed normalization experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | Fallback only; one shared inode reduces release effect. |
| 8 | `norm-no_norm-v1` | 358387358 | 358387358 | 2026-10-01T22:59:32Z | `insula/norm-no_norm-v1/inputs/manifest.json`; closed normalization experiment output. | None found by bounded current-code grep; not in 27a/27b protected set. | Fallback only; same tooling gap. |
| 9 | `cohort-v1` | 1835747595 | 1835747595 | 2026-10-01T10:55:45Z | Historical cohort generation used by older fixed/overfit procedure records and research receipts. | None found by bounded current-code grep; not in 27a/27b protected set. | High-byte fallback only. It has broader historical references and no direct current producer receipt like the rank 1-2 runs. |

Recommended regular-file release set: ranks 1 through 5. This reaches the
target with about 831 MiB of margin below 11 GiB while avoiding the weaker
`cohort-v1` fallback.

High-cushion alternative if the lead prefers fewer local entries over stronger
per-entry provenance: ranks 1, 2, and 9. That releases 4979322800 bytes and
leaves 10322380272 bytes under `W`, but it depends on accepting the broader
historical `cohort-v1` restoration path.

## Future Commands

No command below was run by this worker. The current checkout lacks an
arbitrary-directory regular-file publisher and a symlink-preserving audit
publisher, so the exact runnable command for the selected candidates does not
exist yet. The following commands are the required reviewed command surfaces
before execution. They must use the same existing retention primitives and
Waystone `--auth-source token-file` HDFS access pattern as the current
publishers.

### Regular-file closed directories

Required wrapper, not present in this checkout:

```bash
PYTHONPATH=autonomy python3 -m retention.publish_scientific_directory \
  --case cohort16-baseline-fit20261002a \
  --root /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/cohort16-baseline-fit20261002a \
  --hdfs-namespace perception-closed-scientific-processing \
  --auth-source token-file \
  --host-source-receipt <admitted-publisher-source-receipt.json> \
  --release
```

Run the same command with `--case` and `--root` changed for:

```text
cohort16-residual_bev-balanced20261002b
native-overfit-v1
architecture-window_bev-v1
architecture-coarse_mlp-v1
```

The wrapper must fail closed unless it records all of these stages in the
receipt for every chunk:

```text
create-live
archive-put
archive-get
manifest-put
manifest-get
verify-live
rehydrate-live
independent
release-plan
release-completed
```

Implementation requirements for that wrapper:

1. Freeze a complete source inventory of regular files under exactly one
   top-level `W/<case>` root, preserving relative names and refusing symlinks.
2. Partition with the current `resources.resource_archive.DEFAULT_LIMIT`
   unless the wrapper records a reviewed bound.
3. Create archives with `resources.resource_archive.create_archive`.
4. Upload archive and manifest to an approved HDFS run namespace with
   `waystone --auth-source token-file put --mkdir-parents`.
5. Download both files with `waystone --auth-source token-file get`.
6. Require exact archive and manifest hash readback.
7. Run live `verify` and `rehydrate` gates in the locked resource CPU rootfs.
8. Write a verified publication receipt under `insula/hdfs-retention-<case>-<uuid>/verified-publication.json`.
9. Call `resources.resource_release_plan.release_plan(root, publication)`.
10. Unlink only paths returned by the release plan, then write
    `release-completed.json`.
11. Re-run `unique_payload_bytes(W)` normally after the audit has been moved
    out of `W`.

Existing current commands that are valid precedents but not commands for these
selected candidates:

```bash
PYTHONPATH=autonomy python3 -m retention.publish_native_cache \
  --host-source-receipt <admitted-publisher-source-receipt.json> \
  --release

PYTHONPATH=autonomy python3 -m retention.publish_sustained_checkpoint \
  --receipt <final-receipt.json> \
  --receipt-sha256 <sha256> \
  --host-source-receipt <admitted-publisher-source-receipt.json> \
  --release \
  --lock-fd <fd>

PYTHONPATH=autonomy python3 -m retention.publish_sustained_pilot \
  --receipt <receipt.json> \
  --receipt-sha256 <sha256> \
  --host-source-receipt <admitted-publisher-source-receipt.json> \
  --release
```

### `motion-current-geometry-audit-v3`

Required wrapper, not present in this checkout:

```bash
PYTHONPATH=autonomy python3 -m retention.publish_symlink_audit \
  --case motion-current-geometry-audit-v3 \
  --root /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3 \
  --hdfs-namespace perception-motion \
  --auth-source token-file \
  --host-source-receipt <admitted-publisher-source-receipt.json> \
  --preserve-symlinks \
  --readback \
  --receipt
```

The wrapper must not dereference links. It must inventory regular files by
bytes and sha256 and symlinks by link text, type, and relative path. The
readback gate must prove that restored symlink entries are symlinks with the
same link text and that restored regular files match bytes and sha256.

Only after that verified receipt exists, move the audit out of `W`:

```bash
mkdir -p /data02/home/philip.yang/.cache/waystone/waymo-perception/retired-audits
mv /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3 \
  /data02/home/philip.yang/.cache/waystone/waymo-perception/retired-audits/motion-current-geometry-audit-v3
```

The symlink targets sampled in ticket 27b are absolute `/source/...` targets,
for example `/source/training/6-5-1-range.features.bin`. Moving the directory
does not change symlink text and therefore does not make relative links stale.
Those links remain meaningful only in a namespace that binds the same `/source`
tree. On the host, the move is for gate hygiene and audit retirement, not for
making the links independently host-resolvable.

## Dry Run After Planned Actions

Planned regular-file releases: ranks 1 through 5.

| Entry | Release bytes |
| --- | ---: |
| `cohort16-baseline-fit20261002a` | 1776271853 |
| `cohort16-residual_bev-balanced20261002b` | 1367303352 |
| `native-overfit-v1` | 494810466 |
| `architecture-window_bev-v1` | 361668688 |
| `architecture-coarse_mlp-v1` | 361668652 |
| Total regular-file release effect | 4361723011 |

Projected hardlink-aware regular payload under `W` after those releases and
after moving `motion-current-geometry-audit-v3` out of `W`:

```text
15301703072 - 4361723011 = 10939980061 bytes
```

That is below the 11 GiB target by 871180003 bytes and below the 15 GiB cap by
5166147299 bytes. A 2 GiB reservation would leave 3018663651 bytes of remaining
cap headroom.

Validation command to run after the archive, release, and audit move steps:

```bash
PYTHONPATH=autonomy python3 - <<'PY'
from pathlib import Path
from resources.scientific_payload import unique_payload_bytes

W = Path('/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing')
value = unique_payload_bytes(W)
cap = 15 * 1024**3
reservation = 2 * 1024**3
target = 11 * 1024**3
print({'unique_payload_bytes': value, 'target': target, 'cap': cap, 'reservation': reservation})
assert value <= target
assert value + reservation <= cap
PY
```

## Rollback

Do not release any local candidate unless its verified publication receipt has
already passed an empty-target restoration test. The restore command should be
part of the same reviewed wrapper family; it is not present in this checkout.

Required regular-file restore surface:

```bash
PYTHONPATH=autonomy python3 -m retention.restore_scientific_directory \
  --receipt /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/hdfs-retention-<case>-<uuid>/verified-publication.json \
  --destination /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/<case> \
  --auth-source token-file \
  --require-empty-destination \
  --verify
```

Rollback sequence for each regular-file release:

1. Confirm `W/<case>` is absent or empty enough for a fresh restore.
2. Download every archive and manifest named by the verified receipt from HDFS.
3. Verify archive bytes, archive sha256, manifest sha256, member names, member
   sizes, and member sha256 values.
4. Rehydrate into a fresh temporary directory under an allowed run temp.
5. Atomically install the restored directory at `W/<case>`.
6. Run a second full inventory comparison against the receipt.

Required symlink-audit restore surface:

```bash
PYTHONPATH=autonomy python3 -m retention.restore_symlink_audit \
  --receipt /data02/home/philip.yang/.cache/waystone/waymo-perception/insula/hdfs-retention-motion-current-geometry-audit-v3-<uuid>/verified-publication.json \
  --destination /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/motion-current-geometry-audit-v3 \
  --auth-source token-file \
  --require-empty-destination \
  --verify-symlinks
```

Rollback for the audit move:

1. If the retired local directory still exists and no new `W/motion-current-geometry-audit-v3`
   exists, move it back from `retired-audits/`.
2. Otherwise restore from the HDFS symlink-audit receipt with the command above.
3. Verify all 2970 symlink entries and every regular file entry against the
   receipt.

## Estimated HDFS And Local Effects

Recommended ranks 1 through 5:

| Metric | Bytes |
| --- | ---: |
| Estimated HDFS regular payload upper bound before compression | 4388986777 |
| Local `W` release effect | 4361723011 |
| Motion audit regular payload upper bound | 27577424 |
| Motion audit local `W` regular-byte effect in the diagnostic count | 0 |

The motion audit also removes all 2970 symlink entries from `W`; that is the
operation that lets the unchanged strict accounting function run. HDFS archive
bytes will include tar, gzip, manifests, logs, and symlink metadata, so the
safe budget estimate is "regular payload bytes plus receipt overhead" rather
than a compression claim.

## Acceptance Gates Before Ticket 27 Admission Retry

1. Reviewed regular-file publisher or approved restored legacy procedure exists.
2. Every selected regular-file candidate has a verified HDFS publication
   receipt with exact readback and live rehydrate proof.
3. `resource_release_plan.release_plan` has approved every local file planned
   for unlink.
4. Local release has unlinked only release-plan paths and written
   `release-completed.json`.
5. Reviewed symlink-audit publisher has archived `motion-current-geometry-audit-v3`
   with symlinks preserved and exact readback verified.
6. The audit directory has been moved, not deleted, to
   `~/.cache/waystone/waymo-perception/retired-audits/`.
7. Fresh `unique_payload_bytes(W)` succeeds with no symlink exception.
8. Fresh accounting is `<= 11811160064` and `value + 2147483648 <= 16106127360`.
