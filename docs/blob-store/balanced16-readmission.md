# Balanced16 Blob Store Readmission

Run ID: `bs1220261009T154234Z`

Evidence root:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/bs12-execution/bs1220261009T154234Z`

Worker branch: `worker/bs12-readmit-balanced16-r2`

Base named by the coordinator: `f1566c2`

This is an engineering readmission of the balanced16 admission-only path after
the blob-store and launch-plan migrations. It does not run the full balanced16
sweep and does not claim a scientific result.

## Phase A Plan

The current sustained entry point is unchanged from ticket 27 for this scope:

```bash
systemd-run --user --scope --unit=sureal-sustained-bs1220261009T154234Z \
  -p MemoryMax=17179869184 \
  -p MemorySwapMax=0 \
  -p MemoryAccounting=yes \
  env HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf \
    PYTHONPATH=autonomy \
    python3 -m training_execution.run_sustained \
      --run-id bs1220261009T154234Z \
      --admission-only
```

The run will be launched only after the storage preflight passes and GPU 1 is
clear by both checks: no compute app on GPU 1's UUID in
`nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader`, and
`memory.used < 1024 MiB`.

### What Changed Since Ticket 27

- Blob store: source snapshots, resource publication, checkpoint retention and
  journal publication now use the blob-store interface and receipts cite blob
  keys plus `{kind: "waystone", project: "sureal"}` instead of HDFS roots.
- Store descriptors: new publication receipts carry a backend descriptor and
  normalized Waystone tool digest roles; no command lines, local paths or HDFS
  roots are part of the publication receipt shape.
- Publication module: resource bundle, sustained checkpoint, native cache,
  sustained pilot and research journal publication use publication specs in
  `autonomy/retention/publication.py`.
- Launch plans: sustained admission, controller, training, replay and transition
  audit build current launch plans; GPU stages request GPU 1 by index and record
  GPU driver pins from the launch plan.
- Driver pins: GPU-stage receipts must carry non-empty driver hashes matching
  the launch-plan GPU driver mounts and current driver file digests.
- Strict metrics: scorer, metric audit and sustained admission behavior are from
  the strict-metrics landed base, so the re-admission binds those sources.
- Ticket 29 rootfs/lock: resource CPU work now binds the current t29 CPU runtime
  lock (`rootfs-v5-t29-20261008T230657Z`) through
  `insula.launch_plan.load_default_runtime_lock`; GPU work still binds the
  sustained GPU lock through the launch-plan module.
- Old wrappers: active code outside the blob store and keepalive no longer owns
  the Waystone storage root or copied Waystone tool wrappers.

Prior attempt `bs1220261009T135658Z` was stopped by the coordinator during
Phase A planning only. Its evidence directory is retained as an aborted attempt.
It used no GPU and made no HDFS writes.

### New Blob Keys

All HDFS writes in this run must be new blob keys written by this admission
run's own publication steps or by the journal publication. The planned new key
prefixes are:

- Source snapshots:
  `artifacts/source-snapshots/<source-snapshot-sha256>`
- Resource publication for the baseline admission:
  `runs/perception-resource-closures/balanced16-sustained-baseline-bs1220261009T154234Z/checkpoint/`
- Sustained checkpoint publication for step 0:
  `checkpoints/perception-sustained-checkpoints/balanced16-sustained-baseline-bs1220261009T154234Z-step0/checkpoint/`
- Sustained checkpoint publication for step 1000:
  `checkpoints/perception-sustained-checkpoints/balanced16-sustained-baseline-bs1220261009T154234Z-step1000/checkpoint/`
- Research journal publication:
  `runs/perception-research-journal/bs1220261009T154234Z/snapshot/`

Each archive-mode publication writes `archive-000.tar.gz` and `manifest.json`
under its prefix, adding more `archive-NNN.tar.gz` blobs only if chunking needs
them. The journal publication is direct-files mode and writes each journal file
plus `manifest.json` under its prefix.

### Preflight Commands

Disk gate:

```bash
df -B1 /data02
TMPDIR=/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/bs12-readmit-balanced16-r2-20261009T153852Z/tmp/<fresh-dir> \
PYTHONPATH=autonomy python3 - <<'PY'
from pathlib import Path
from resources.scientific_payload import unique_payload_bytes
W = Path.home() / ".cache/waystone/waymo-perception/scientific-processing"
value = unique_payload_bytes(W)
print(value)
print(value + 2 * 1024**3)
if value + 2 * 1024**3 > 15 * 1024**3:
    raise SystemExit("storage gate failed")
PY
```

Rootfs lock verification:

```bash
PYTHONPATH=autonomy python3 - <<'PY'
from pathlib import Path
from insula.launch_plan import load_default_runtime_lock

roots = {
    "cpu": Path.home() / ".cache/waystone/waymo-perception/insula/rootfs-v5-t29-20261008T230657Z",
    "gpu": Path.home() / ".cache/waystone/waymo-perception/gpu-rootfs-v6",
    "metrics": Path.home() / ".cache/waystone/waymo-perception/metrics-rootfs",
    "motion": Path.home() / ".cache/waystone/waymo-perception/motion-cli-rootfs-v2",
}
for name, root in roots.items():
    lock = load_default_runtime_lock(root)
    print(name, lock.rootfs, lock.lock_path, lock.lock_sha256, lock.data["rootfs_sha256"])
PY
```

HDFS read-only listing through the blob store:

```bash
HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf PYTHONPATH=autonomy python3 - <<'PY'
from blob_store.core import BlobStore, blob_adapter_from_descriptor
from retention.publication import WAYSTONE_DESCRIPTOR

store = BlobStore(blob_adapter_from_descriptor(WAYSTONE_DESCRIPTOR))
for key in [
    "artifacts/source-snapshots/does-not-exist-for-bs12-readonly-preflight",
    "runs/perception-research-journal/does-not-exist-for-bs12-readonly-preflight/snapshot/manifest.json",
]:
    print(key, store.exists(key))
PY
```

Waystone tool pins:

```bash
PYTHONPATH=autonomy python3 - <<'PY'
from blob_store.core import waystone_tool_pins
print(waystone_tool_pins())
PY
```

### GPU Guard And Occupancy Commands

Wait up to six hours, polling every 60 seconds, for GPU 1 to be free by UUID and
memory. Immediately before the launch, repeat the same guard. During the scoped
run, sample every 30 seconds into:

`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/bs12-execution/bs1220261009T154234Z/gpu1-occupancy.jsonl`

The sampler records UTC time, GPU 1 UUID, memory used, compute-app rows, PIDs
and owners where available. If a foreign process shares GPU 1 mid-run, the run
is allowed to finish and the sharing is reported with counts, owners and
durations.

### Receipt Verification

Every emitted receipt will be verified from durable evidence, not from the
current working tree alone:

- Source snapshots: build the recorded store with `store_from_receipt()` and run
  `verify_receipt_sources()` or `verify_or_materialize_receipt_sources()` on
  each source-snapshot receipt emitted by the run.
- Runtime locks: load each recorded CPU, GPU and metrics lock through
  `insula.launch_plan.load_default_runtime_lock()` and require full lock data
  equality for the stage receipt's recorded runtime lock.
- GPU driver pins: for GPU stages, require non-empty `driver_hashes`, compare
  them with the launch-plan GPU driver mount digests by filename, and sha256 the
  recorded driver files again before acceptance.
- Resource and checkpoint blob publications: call
  `retention.publication.audit(receipt)` on each blob publication receipt and
  independently fetch every cited blob through the blob store, checking sha256
  and byte count against the receipt.
- Stage receipts: replay `NativeBackend.check_stage()` and the backend resume
  validation for records 0 and 1000, then verify each checkpoint's `check.json`,
  all 16 head files, admitted checkpoint receipt, report digest and stage
  coverage.
- Journal publication: append the re-admission note only after the live
  admission verifies; run `PYTHONPATH=autonomy python3 -m evidence.tracker
  verify-journal`, publish with
  `PYTHONPATH=autonomy python3 -m retention.publish_research_journal --run-id
  bs1220261009T154234Z --staging-root <fresh-dir> --legacy-receipt <preserved
  prior receipt>`, and audit the resulting receipt with readback before and
  after publication.

### Gates

After live verification and journal publication, run and record counts:

```bash
TMPDIR=<fresh-dir> SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test \
  --noexperimental_collect_system_network_usage \
  --nocache_test_results \
  --test_output=errors \
  //autonomy/...

TMPDIR=<fresh-dir> SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test \
  --noexperimental_collect_system_network_usage \
  --nocache_test_results \
  --test_output=errors \
  //parallax/...

CUDA_VISIBLE_DEVICES=1 TMPDIR=<fresh-dir> SUREAL_BAZEL_CACHE=$PWD/.bazel-cache ./bazelw test \
  --config=cuda \
  --noexperimental_collect_system_network_usage \
  --nocache_test_results \
  --test_output=errors \
  //autonomy/...
```

The CUDA gate runs only after the same GPU 1 free check passes. No gate will be
weakened.

## Results

Phase A: planned, committed before heavy work.

Phases B-E: pending.
