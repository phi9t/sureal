# Ticket 29 Runtime-Lock Readmission Plan

Generated: 2026-10-08

Worker branch: `worker/t29-runtime-lock-readmission`

Base: `17a864ede75c0b67a54476d870810913673e1832`

Status: phase 1 complete; phase 2 is blocked in this worker because the only
CPU rootfs rebuild path uses `docker build`, and this run forbids container
builds.

## Scope

Ticket 29 finishes the four runtime-lock rows left open by ticket 27:

- `//autonomy/insula:m0_receipt_test`
- `//autonomy/segmentation:semantic_recovery_accounting_test`
- `//autonomy/segmentation:semantic_recovery_receipt_test`
- `//autonomy/segmentation:semantic_recovery_receipt_aligned_test`

No gate may be relaxed, retagged, skipped, or counted from a synthesized
receipt.

## A. M0 Rootfs, Image, And Stale Lock

The checked-in M0 test still points at historical M0 evidence:

- `autonomy/insula/m0_receipt_test.py:10` sets
  `ROOT = ~/.cache/waystone/waymo-perception/insula/rootfs-v2`.
- `autonomy/insula/m0_receipt_test.py:11` sets
  `EVIDENCE = ROOT.parent / "m0-live-20260930-c"`.

That historical path is not the current readmission target. Current CPU Insula
execution is rooted at `rootfs-v4`:

- `autonomy/insula/bazel_launcher.py:14` sets `DEFAULT_ROOTFS` to
  `~/.cache/waystone/waymo-perception/insula/rootfs-v4`.
- `autonomy/resources/backend.py:12` sets
  `CURRENT_CPU_ROOTFS_NAME = "rootfs-v4"`.
- `autonomy/training_execution/admit_sustained.py:20` and
  `autonomy/training_execution/sustained_controller_backend.py:19` set
  `CPU_ROOT = C / "insula/rootfs-v4"`.

The current CPU rootfs is defined by `autonomy/insula/Dockerfile`; the builder is
`autonomy/insula/build_cpu_rootfs.sh`.

Builder facts:

- `autonomy/insula/build_cpu_rootfs.sh:8-11` defaults to cache root
  `~/.cache/waystone/waymo-perception/insula`, previous root `rootfs-v3`,
  destination `rootfs-v4`, and image tag
  `sureal-waymo-cpu:bazel-9.2.0-rootfs-v4`.
- `autonomy/insula/build_cpu_rootfs.sh:126-132` runs
  `docker build`, `docker image inspect`, `docker create`, and `docker export`.
- `autonomy/insula/build_cpu_rootfs.sh:140-153` writes the lock with
  `rootfs_sha256`, `requirements_sha256`,
  `test_tools_requirements_sha256`, `dockerfile_sha256`, Bazel version, and
  Bazel binary digest.
- `autonomy/insula/cpu_rootfs_build_test.py:203-221` verifies that the builder
  creates `rootfs-v4`, preserves the previous rootfs, and records
  `dockerfile_sha256 == sha256(autonomy/insula/Dockerfile)`.

Actual stale-lock check from this worktree:

```text
sha256sum autonomy/insula/Dockerfile
8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6

~/.cache/waystone/waymo-perception/insula/rootfs-v4.lock.json:
dockerfile_sha256 = 61a783f428bfc141ed4d9c2e4cc8360adfb3fea92567f63574900ccdbda9fe30
rootfs_sha256     = 429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb
computed rootfs_identity(rootfs-v4) = 429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb
```

Conclusion: `rootfs-v4` content still matches its lock, but the lock records the
pre-current Dockerfile digest. Ticket 29 must build a new versioned CPU rootfs
from the current `autonomy/insula/Dockerfile`; it must not edit or replace
`rootfs-v4` or retained M0 receipts.

The correct implementation mechanism is to create a new rootfs directory under
`~/.cache/waystone/waymo-perception/insula/`, for example
`rootfs-v5-t29-20261008`, with a matching `.lock.json`. If that rootfs is
promoted as the current CPU Insula, update the active current-root pointers as a
set:

- `autonomy/insula/bazel_launcher.py`
- `autonomy/resources/backend.py`
- `autonomy/training_execution/admit_sustained.py`
- `autonomy/training_execution/sustained_controller_backend.py`
- the M0 live-gate receipt/test pointer

## B. Balanced16 Rootfs Ordering Against Ticket 12

Yes, balanced16 sustained execution uses the same CPU Insula rootfs family as
the current M0 readmission root.

Evidence:

- `autonomy/training_execution/admit_sustained.py:20` sets
  `CPU_ROOT = C / "insula/rootfs-v4"`.
- `autonomy/training_execution/admit_sustained.py:64` reads
  `CPU_ROOT.lock.json` and verifies `CPU_ROOT`.
- `autonomy/training_execution/admit_sustained.py:82` runs CPU stages through
  `launch_plan(CPU_ROOT, ...)`.
- `autonomy/training_execution/sustained_controller_backend.py:19` sets
  `CPU_ROOT = C / "insula/rootfs-v4"`.
- `autonomy/training_execution/sustained_controller_backend.py:155-156` reads
  and verifies the CPU rootfs lock.
- `autonomy/training_execution/sustained_controller_backend.py:192` runs
  non-GPU/non-metrics stages through `launch_plan(... CPU_ROOT ...)`.

Ordering decision: land ticket 29 before blob-store ticket 12. A promoted CPU
rootfs version changes the runtime lock that balanced16 CPU stages bind, so
ticket 12 should bind after this readmission settles the current CPU rootfs.

## C. Real Semantic-Recovery Receipt Producer

The three semantic recovery tests do not produce receipts. They verify a
receipt mounted at `/source/receipt.json`.

Test behavior:

- `autonomy/segmentation/semantic_recovery_accounting_test.py:5-7` reads
  `/source/receipt.json` and verifies accounting.
- `autonomy/segmentation/semantic_recovery_receipt_test.py:6-17` copies
  `/source`, reads `receipt.json`, and verifies receipt identity and mutations.
- `autonomy/segmentation/semantic_recovery_receipt_aligned_test.py:15-17` reads
  the receipt fixture path from `SEMANTIC_RECEIPT_FIXTURE` or `/source`.

The producer is the semantic recovery job:

- `autonomy/segmentation/semantic_recovery_job.py:24-80` defines
  `recover_semantic_archive(...)` and writes `output/receipt.json`.
- `autonomy/segmentation/semantic_recovery_job_aligned.py:24-80` defines the
  aligned-write variant and writes `output/receipt.json`.
- Both jobs stage the HDFS archive through
  `segmentation.staged_derived_archive` or
  `segmentation.staged_derived_archive_aligned`, then run the offline worker
  through `insula.entry.launch_plan`.
- `autonomy/segmentation/staged_derived_archive.py:47-49` runs
  `timeout --kill-after=10s 600s /data02/home/philip.yang/workspace/waystone/scripts/waystone get <hdfs-uri> <scene.tar>`
  unless a transfer command is injected.
- `autonomy/segmentation/staged_derived_archive_aligned.py:51-53` does the same
  for the aligned transfer contract.

Inputs:

- Source slice: `~/.cache/waystone/waymo-perception/slices/validation-two-scenes-20260929/slice.json`.
- The slice records contexts
  `5847910688643719375_180_000_200_000` and
  `8137195482049459160_3100_000_3120_000`.
- The recovery job input is not the raw slice JSON alone. It is the point
  publication record created from a scientific scene lifecycle:
  `autonomy/studies/scientific_cohort.py:67-72` preprocesses points, publishes
  the scientific scene through `python3 -m dataset.publish-scientific-scene`,
  and verifies replay.
- The record passed to recovery must include `publication_manifest`,
  `publication_manifest_sha256`, `archive_hdfs_uri`, `archive_sha256`,
  `archive_bytes`, `report_sha256`, `records`, `membership`, and `scene`.

Command shape after the rootfs blocker is cleared:

```bash
E=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007
OUT=$E/t29-execution/semantic-recovery
mkdir -p "$OUT"

PYTHONPATH=autonomy python3 - <<'PY'
import json
from pathlib import Path
from segmentation.semantic_recovery_job import recover_semantic_archive
from segmentation.semantic_recovery_job_aligned import recover_semantic_archive as recover_aligned

cache = Path.home() / ".cache/waystone/waymo-perception"
code_root = Path.cwd() / "autonomy"
out = Path("/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t29-execution/semantic-recovery")

# record must be built from the validation-two-scenes scientific point
# publication receipt, not from ticket 27's synthesized contract fixture.
record = json.loads((out / "selected-point-publication-record.json").read_text())
recover_semantic_archive(record, cache=cache, code_root=code_root, output=out / "current")
recover_aligned(record, cache=cache, code_root=code_root, output=out / "aligned-current")
PY
```

GPU: no GPU is required for these semantic recovery jobs. They run CPU Insula
workers and Waystone/HDFS reads. The ticket still requires GPU 1 polling for any
GPU work; the semantic receipt generation should record `gpu_required: false`.

Expected duration: the transfer path has a 600 second timeout per archive
download. The retained v4 examples recover multi-GB scene archives, so plan for
minutes per exact/aligned receipt rather than seconds. Record wall time in the
ticket evidence.

Important stale evidence note: the retained local
`semantic-recovery-admission-v4-*` directories are real historical recovery
outputs, but the sampled receipt binds `pipeline/*` code paths and
`rootfs-v2`. Ticket 29 must generate current semantic-layout receipts, not copy
or rehash those retained outputs into a contract fixture.

## D. Live-Gate Execution Without A Ticket-Named Module

Use concept-owned live-gate support in `autonomy/insula`, not
`autonomy/ticket29` or `autonomy/ticket27`.

Implementation plan:

1. Add reusable live-gate support under `autonomy/insula`, for example
   `autonomy/insula/live_gate.py`, backed by
   `insula.sandbox_plan.compose_bwrap_plan`.
2. Add focused tests for the live-gate plan construction and receipt writer
   under `autonomy/insula/live_gate_test.py`.
3. The live-gate helper records JSON evidence under `$E/t29-execution`:
   label, rootfs path, lock path, rootfs lock digest, command argv, raw log path,
   raw log SHA-256, expected/executed unittest count, fixture path, duration,
   and verdict.
4. The helper mounts current code read-only at `/experiment`, the real receipt
   fixture at `/source`, and an execution-local output directory under
   `$E/t29-execution` at `/outputs`.

Gate mapping:

| Row | Live command inside CPU Insula | Fixture |
| --- | --- | --- |
| `//autonomy/insula:m0_receipt_test` | Generate fresh M0 receipt with `WAYMO_INSULA_ROOT=<new-rootfs> PYTHONPATH=autonomy python3 -m insula.verify_m0 $E/t29-execution/m0-current`, then run the M0 receipt unittest/validator against that receipt and rootfs. | `$E/t29-execution/m0-current` |
| `//autonomy/segmentation:semantic_recovery_accounting_test` | `python3 -m unittest segmentation.semantic_recovery_accounting_test -v` | `$E/t29-execution/semantic-recovery/current` mounted at `/source` |
| `//autonomy/segmentation:semantic_recovery_receipt_test` | `python3 -m unittest segmentation.semantic_recovery_receipt_test -v` | `$E/t29-execution/semantic-recovery/current` mounted at `/source` |
| `//autonomy/segmentation:semantic_recovery_receipt_aligned_test` | `SEMANTIC_RECEIPT_FIXTURE=/source SEMANTIC_RECEIPT_CODE=/experiment python3 -m unittest segmentation.semantic_recovery_receipt_aligned_test -v` | `$E/t29-execution/semantic-recovery/aligned-current` mounted at `/source` |

For M0, the current test source is historical. The reviewed mechanism is to
parameterize the M0 receipt/rootfs paths through environment variables or an
equivalent concept-owned live-gate adapter, then run the same receipt assertions
against the fresh current-code receipt. Do not mutate retained
`m0-live-20260930-*` evidence.

## Phase 2 Blocker In This Worker

The next required ticket action is to rebuild the CPU rootfs as a new versioned
directory. The only active builder is `autonomy/insula/build_cpu_rootfs.sh`, and
it invokes Docker at `autonomy/insula/build_cpu_rootfs.sh:126-132`. This worker
run explicitly says container builds are not allowed.

Because of that rule, this worker must stop after the phase 1 plan commit. It
must not fake the rebuild by copying `rootfs-v4` and changing the lock, because
that would record the current Dockerfile digest without proving those bytes were
built from it.

When rerun with container-build authorization, execute phase 2 in this order:

1. Build a new CPU rootfs under a fresh versioned path using
   `WAYMO_INSULA_PREVIOUS_ROOT=<existing-rootfs-v4>` and
   `WAYMO_INSULA_ROOT=<new-rootfs>`.
2. Verify the new lock records Dockerfile digest
   `8e6c2a38868c8ff8e01e205697955a2d2837d740bb1539d81b3825141c273ac6`.
3. Promote active CPU rootfs pointers consistently if the new root becomes the
   current runtime.
4. Generate a fresh M0 receipt in `$E/t29-execution`.
5. Generate exact and aligned current semantic recovery receipts in
   `$E/t29-execution` from the validation-two-scenes scientific point
   publication record.
6. Run the four live gates with concept-owned `autonomy/insula` support.
7. Append local journal entries through `python3 -m evidence.tracker note`.
   Do not run `autonomy/evidence/publish.py` in this worker because HDFS writes
   are forbidden.
8. Run the required gates:
   `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`,
   `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`, and
   `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
   when GPU 1 is free.
