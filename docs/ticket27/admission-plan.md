# Ticket 27 Admission Plan

Generated: 2026-10-08T01:36:46Z

Worker branch: `worker/t27a-admission-plan`

Bound base: `b5768927fa6679a2793b78d232ea8f7b3e670669`

Coordinator code base: `85633c0`

Prepared comparison base: `b47edbc236e2ef1172a66f436b3f006184f7b711`

Evidence root in the coordinator task: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007`

This is a 27a plan and CPU/read-only binding record. It is not a live
admission, not an HDFS publication, and not a scientific result. 27a did not
use a GPU, run training, write HDFS, publish snapshots, edit research receipts,
or update the ticket status. Phase 27b must run the live gates below in an
authorized environment.

## Phase Split

| Ticket 27 checklist box | 27a disposition | 27b action |
| --- | --- | --- |
| The sweep's recipes, frames and anchor templates are unchanged from the preregistration | Verified read-only in this checkout: four recipes, seed 17, 16 ordered frames, 48 input digests, candidate hash and anchor-template hash match `27-preflight.json`. | Re-run the same read-only digest checks immediately before live admission and retain the output under `t27b-readmission/preregistration.json`. |
| Each recipe's admission pins a source snapshot stored in HDFS and the new rootfs digest | Source closure targets and current `*_sources.py` digests are bound here. Current CPU/GPU/metrics/motion rootfs lock digests were verified read-only. | Publish each source snapshot through `HdfsSnapshotStore`, verify readback, run admission in the locked GPU/CPU roots, and retain per-recipe snapshot and runtime-lock receipts. |
| Every runtime-lock check listed in ticket 01 is re-admitted on the new images | Ticket-01 map was reviewed as a prepared routing table. Current executable targets were re-resolved against this tree; stale pre-26 path placeholders are not treated as executable evidence. | For every active runtime consumer, run the current public CLI/API or explicit successor gate, write a per-consumer readmission receipt, and record source snapshot digest, rootfs digest, command, exit, and independent checker output. |
| A live gate executes the admitted candidate in the new rootfs and its receipt verifies against the snapshot | Not run. The historical `--admission-only` command trains baseline step 0/1000 and is not read-only. This worker also has no `/dev/nvidia1`, `/dev/nvidiactl`, or `/dev/nvidia-uvm`. | Run the live admission command under authorized GPU/HDFS/training access, then verify every receipt against its stored source snapshot and runtime lock. |
| The journal records the re-admission and what changed since the original admission | Draft text and publication sequence are provided below. No journal files were edited. | Append the decision entry after acceptance, verify the local chain, preserve the prior HDFS publication receipt bytes, publish the full current journal/evidence chain, and verify exact readback. |
| The task index states the sweep's new status | Draft issue text is provided below. No task index was edited. | After successful 27b acceptance only, update issue 27 checkboxes/status and add the drafted Comments evidence. |

## 27a Code Binding Fixes

Minimal code changes were made so 27b runs against the final ticket-26 runtime
locks instead of stale rootfs names:

- `autonomy/resources/backend.py` now defines `CURRENT_CPU_ROOTFS_NAME =
  'rootfs-v4'` and `resource_cpu_root_for(owner, cache_root=None)`.
- Resource checkpoint and retention code now use `resource_cpu_root_for` for the
  fallback CPU rootfs binding.
- Native cache, sustained checkpoint, and sustained pilot publishers now use the
  current resource CPU-root helper.
- Balanced16 live controller constants now bind `gpu-rootfs-v6` and
  `insula/rootfs-v4`.
- Legacy standalone sustained admission constants now bind `gpu-rootfs-v6` and
  `insula/rootfs-v4`.
- Focused source guards were added for the changed resource/controller/publisher
  bindings.

These are runtime-binding repairs only. They do not modify research records,
receipts, pins, procedure records, or historical journal entries.

## Checklist Commands

All commands below use repo root
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/final26-closeout-verify-worker-t27a-admission-plan`
as `cwd` unless a command says otherwise.

### 1. Preregistration Read-Only Check

Phase: 27a complete, repeat in 27b before admission.

Needs GPU/HDFS/network/training: no/no/no/no.

Evidence written in 27a: `docs/ticket27/admission-plan.json`
`preregistration` section.

Command:

```bash
sha256sum \
  autonomy/research/balanced16-sustained.candidate.json \
  autonomy/research/training-anchor-templates.candidate.json \
  autonomy/detection/detector_recipe_catalog.py \
  autonomy/detection/detector_recipe_models.py

jq '{
  recipes,
  seed,
  frame_count: (.frames | length),
  input_digest_count: ([.frames[].sha256 | keys | length] | add),
  identities: [.frames[].identity]
}' autonomy/research/balanced16-sustained.candidate.json
```

Expected:

- Candidate SHA-256:
  `d53888395457705e57ba46d2dcbcb7a830f3b1127de1a34a85c7295d3b45ca0a`.
- Anchor-template SHA-256:
  `4bcc69590d664b32ff1ece5e8f00345c76f9564f419b091bf05f6482a5c56d52`.
- Recipes exactly:
  `baseline`, `residual_bev`, `class_balanced`, `prior_bias`.
- Seed: `17`.
- Ordered frame count: `16`.
- Input digest count: `48`.
- Detector recipe files moved in ticket 26 but are byte-identical:
  `detector_recipe_catalog.py` =
  `4a33cc1719c4a32203ee6574301854c7c2cab8a51fc09b3cdd9cb3fcb90f550f`;
  `detector_recipe_models.py` =
  `d1da1ab694ed4bf08730854c05275fb0a813c18dbd56036e7bdf771be2936c17`.

### 2. Current Source Closures

Phase: 27a complete, repeat in 27b and retain full label lists.

Needs GPU/HDFS/network/training: no/no/no/no.

Evidence written in 27a: `docs/ticket27/admission-plan.json`
`source_closures` section.

Command pattern:

```bash
./bazelw query 'kind("source file", filter("^//", labels("srcs", deps(<target>)) union labels("data", deps(<target>))))'
```

Current targets:

| Target | Current source labels | Sorted-label SHA-256 | Role |
| --- | ---: | --- | --- |
| `//autonomy/resources:execute_worker` | 49 | `1c3f5581f84d03d9df55ffdc1e04bfb07ad4f34e5395152d2122b1599a3189d3` | resource worker runtime |
| `//autonomy/training_execution:train_sustained` | 246 | `119bdb1f6b67d06381677e2becb4eca795460e1bc41067255554feb4e3a63f5d` | sustained training worker |
| `//autonomy/training_execution:run_sustained` | 246 | `119bdb1f6b67d06381677e2becb4eca795460e1bc41067255554feb4e3a63f5d` | sustained controller CLI |
| `//autonomy/retention:publish_native_cache` | 64 | `2bcf3b31aaf53873e72acc007c6962b5d4ac040eb54a518f90e5631b6d1b22e7` | native cache publisher |
| `//autonomy/retention:publish_sustained_checkpoint` | 64 | `2bcf3b31aaf53873e72acc007c6962b5d4ac040eb54a518f90e5631b6d1b22e7` | sustained checkpoint publisher |
| `//autonomy/retention:publish_sustained_pilot` | 64 | `2bcf3b31aaf53873e72acc007c6962b5d4ac040eb54a518f90e5631b6d1b22e7` | sustained pilot publisher |
| `//autonomy/studies:architecture_experiment_runner` | 327 | `9387481ba36ae5dbce1afb0e699c65315978993181fffa6674a0870fe0dd688e` | architecture runner |
| `//autonomy/studies:scientific_cohort` | 131 | `9c19c11c1d865766a136be6f9e5811f34ecf08e18c4e4187071162722868dab5` | current successor for moved scientific cohort CLI |

Current `*_sources.py` identities versus the b47edbc prepared values:

| File | b47edbc SHA-256 | Current SHA-256 | Reason |
| --- | --- | --- | --- |
| `autonomy/resources/sources.py` | `cb4529c772faa1dd24284272202939adce8f2b67e7b42407aa8c462f8499f767` | `981dbe7d7a980e974994ee59919d6bd6a31fe7ab30abb5fb28a21fc1c40b402a` | Local regular-file wrapper replaced by `evidence.source_snapshot.is_regular_file`. |
| `autonomy/training_execution/sustained_sources.py` | `9f877302429e46f865e970c247a26d7adc3c655dc015963cb6fb30714bce3ff9` | `35771fa0baec83f66b32d84eb1becaca73442d96ee989d30fc03dd5e11aacbf3` | Detector recipe files renamed from `detection/fixed_batch_{catalog,models}.py` to `detection/detector_recipe_{catalog,models}.py`. |
| `autonomy/training_execution/sustained_controller_sources.py` | `e0bf7d581d188ba940cc97d3a102137f26ec0ed258837da8a6c497eba2547cfa` | `1acfc3b499b4037615a53e86cccc711848d5c5214e40ca6f3d52a65aac015f9e` | Local regular-file wrapper replaced by `evidence.source_snapshot.is_regular_file`. |
| `autonomy/retention/retention_sources.py` | `aaae6a8d48f51dda1c91428698f4b134b26d94fa6e9eef2a82f82bb63d9f8d9f` | `46a2734b48f3b70f308e6739f9a6f2d31f5bf4da8a89d3623e11a49205375b36` | Local regular-file wrapper replaced by `evidence.source_snapshot.is_regular_file`. |
| `autonomy/retention/checkpoint_retention_sources.py` | `0581c5ecac96a02f2d01f9b0807c41cf0d9f00fda7fe80435a86cee1a684453e` | `64ed630855599f3280b1aef5c4d82d9e4607fd19f0aa7e4bce4daf31bf01b696` | Local regular-file wrapper replaced by `evidence.source_snapshot.is_regular_file`. |
| `autonomy/retention/pilot_retention_sources.py` | `d91b85017b48abe91d33f34ace8807cf6e95d93d96dbb45dca5a557e4d53f1b6` | `1d292ccd29c5e45cbd80857e1105e06733e0577c85596485c0224f5bfa681a56` | Local regular-file wrapper replaced by `evidence.source_snapshot.is_regular_file`. |

### 3. Rootfs Lock Verification

Phase: 27a complete, repeat in 27b immediately before live gates.

Needs GPU/HDFS/network/training: no/no/no/no for digest verification. Live GPU
execution later needs GPU device access.

Evidence written in 27a: `docs/ticket27/admission-plan.json`
`rootfs_locks` section.

Command:

```bash
PYTHONPATH=autonomy python3 - <<'PY'
import json
from pathlib import Path
from insula.runtime_identity import rootfs_identity, verify_rootfs

roots = [
    ("cpu", Path.home()/".cache/waystone/waymo-perception/insula/rootfs-v4"),
    ("gpu", Path.home()/".cache/waystone/waymo-perception/gpu-rootfs-v6"),
    ("metrics", Path.home()/".cache/waystone/waymo-perception/metrics-rootfs"),
    ("motion_cli", Path.home()/".cache/waystone/waymo-perception/motion-cli-rootfs-v2"),
]
for name, root in roots:
    lock = json.loads(Path(str(root) + ".lock.json").read_text())
    verify_rootfs(root, lock["rootfs_sha256"])
    print(name, root, rootfs_identity(root), lock["rootfs_sha256"], "PASS")
PY
```

Current results:

| Runtime | Root | Digest | Result |
| --- | --- | --- | --- |
| CPU | `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v4` | `429e7c76ff605dc634e21836e72c40f2ee9d756b0269b031f4e6ec222b057cbb` | PASS |
| GPU | `/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6` | `5a1af6a165eb3d59781eda28fee6acd2672b6a53e3645252eeb6579beb720eb4` | PASS |
| Metrics | `/data02/home/philip.yang/.cache/waystone/waymo-perception/metrics-rootfs` | `831a5955ce709cb46b82688ba0f0371c37e1af707ffb870b24c555d53d4f5542` | PASS |
| Motion CLI | `/data02/home/philip.yang/.cache/waystone/waymo-perception/motion-cli-rootfs-v2` | `c471473b944157119d0d6440a9e95515dfda4d4c554d4cfafa4374da40bf9c8e` | PASS |

### 4. Source Snapshot Publication To HDFS

Phase: 27b only.

Needs GPU/HDFS/network/training: no/yes/yes/no.

Evidence to write in 27b:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots/*.json`
and the materialized source roots named in those receipts.

Authentication: `HdfsSnapshotStore` invokes Waystone with
`--error-format json --auth-source token-file` and sets
`HADOOP_CONF_DIR` to `/opt/tiger/yarn_deploy/hadoop/conf` if unset. It stores
under `hdfs://harunava/user/tiger/waystone/sureal/source-snapshots/` and
verifies exact readback after upload.

Command:

```bash
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-/opt/tiger/yarn_deploy/hadoop/conf}"
mkdir -p /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots
PYTHONPATH=autonomy python3 - <<'PY'
import json
from pathlib import Path
from evidence.source_snapshot import (
    HdfsSnapshotStore,
    snapshot_target_and_materialize,
    verify_receipt_sources,
)

out = Path("/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/source-snapshots")
store = HdfsSnapshotStore()
targets = [
    "//autonomy/resources:execute_worker",
    "//autonomy/training_execution:train_sustained",
    "//autonomy/training_execution:run_sustained",
    "//autonomy/retention:publish_native_cache",
    "//autonomy/retention:publish_sustained_checkpoint",
    "//autonomy/retention:publish_sustained_pilot",
    "//autonomy/studies:architecture_experiment_runner",
    "//autonomy/studies:scientific_cohort",
]
for target in targets:
    name = target.replace("//", "").replace("/", "_").replace(":", "__")
    materialized = out / (name + ".materialized")
    receipt = snapshot_target_and_materialize(target, materialized, store=store, repo_root=Path.cwd())
    verified = verify_receipt_sources(receipt, store)
    (out / (name + ".json")).write_text(json.dumps({
        "target": target,
        "receipt": receipt,
        "verified": verified,
    }, indent=2) + "\n")
PY
```

Expected:

- Each receipt has `source_snapshot_store.kind = "hdfs"`.
- Each `source_snapshot_sha256` is a 64-hex digest.
- `verify_receipt_sources` reports the same digest and source pins as the
  receipt.
- Re-running the command for an existing digest verifies the existing bytes and
  does not overwrite.

This command was not run in 27a because HDFS writes and network changes are
outside this worker's authorization.

### 5. Runtime-Consumer Readmission

Phase: 27b only for live consumers; 27a prepared the binding.

Needs GPU/HDFS/network/training: depends on row. Every row must write a
successor artifact before being counted as admitted.

Evidence to write in 27b:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/runtime-consumers/<id>.json`.

Required receipt fields for each active consumer:

- current label or current CLI/API;
- exact command, cwd, env without secrets, and exit code;
- source snapshot target and digest;
- rootfs path, lock path, and verified digest;
- input receipt/dataset/procedure identity if any;
- output artifacts and SHA-256 digests;
- independent checker command and result;
- explicit disposition for closed historical records that are not rerun.

Prepared map caveat: `27-runtime-checklist.json` has 78 ticket-01 routing rows
from an earlier commit. Rows with placeholder final paths are not current-tree
evidence. The current executable source closures are the targets listed in
section 2, plus the excluded-test labels listed below.

Current disposition of stale prepared paths observed in 27a:

| Prepared row | Prepared final path | Current disposition for 27b |
| --- | --- | --- |
| `R19` | `autonomy/build.sh` | Removed active rootfs build script. Use the current Insula recipe targets and tests under `autonomy/insula`, especially `//autonomy/insula:cpu_rootfs_build_test` and the CPU rootfs-v4 lock verification in section 3. Do not recreate `autonomy/build.sh`. |
| `R44` | `autonomy/dataset/process-scientific-cohort.py` | Moved to the executable closure `//autonomy/studies:scientific_cohort`, already listed in section 2. This is acquisition/publication workflow evidence, not balanced16 training. |
| `R54` | `autonomy/tests/test_cpu_rootfs_build.py` | Moved under `autonomy/insula:cpu_rootfs_build_test`; this passed in the full default 27a run. |
| `R61` | `autonomy/verify-geometry.py` | Removed as an old active root verifier by ticket 26. Use the current geometry concept tests and any concrete successor receipt, not the deleted root script. |
| `R62` | `autonomy/verify-m0.py` | Removed as an old active root verifier by ticket 26. Current M0 admission/replay evidence is `autonomy/insula:m0_receipt_test`, listed in the excluded-test map. |
| `R64` | `autonomy/verify-native.py` | Removed as an old active root verifier by ticket 26. Current native metric verification is routed through evaluation/training execution receipts and `autonomy/evaluation` commands. |
| `R65` | `autonomy/verify-reconstruction.py` | Removed as an old active root verifier by ticket 26. Current reconstruction checks live under `autonomy/geometry` and `autonomy/segmentation`; retain concrete successor receipts. |
| `R67` | `autonomy/verify-scientific-scene.py` | Removed as an old active root verifier by ticket 26. Current scene publication/replay evidence is through dataset/geometry command filegroups and `//autonomy/studies:scientific_cohort`. |
| `R70` | `autonomy/pipeline/r0_compare.py` | Current implementation is `autonomy/geometry/r0_compare.py`; ticket 27 should bind any new receipt to the geometry concept path. |

All other prepared rows marked `active_consumer`, `unit_test_only`, or
`build_tool` either resolve to current files in this checkout or are covered by
the current executable closures and excluded-test labels above. For every row,
27b should write an explicit disposition receipt rather than relying on the
prepared JSON alone.

### 6. Excluded-Test Readmission Map

Phase: 27b only.

Evidence to write in 27b:
`/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/excluded-tests/<label>.json`.

For rows tagged `requires_live_gate`, use the normal Bazel target only after
the needed fixture/rootfs/device is available. For rows tagged `known_failure`,
do not count the row as passing until the stated prerequisite is satisfied and
the target exits 0 without weakening tags or assertions.

| Current label | Current tags | Needs | Exact 27b command |
| --- | --- | --- | --- |
| `//autonomy/evaluation:metrics_sustained_v3_test` | `requires_live_gate` | CPU rootfs-v4, current autonomy mounted as `/experiment`, TensorFlow absent, mocked evaluator/export fixture. Replaces stale prepared row `//autonomy:cohort__test_sustained_native_metric_gate`. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/evaluation:metrics_sustained_v3_test` |
| `//autonomy/camera:project_camera_test` | `requires_live_gate` | Motion CLI rootfs-v2, pinned camera source/Eigen, native build in fresh writable output. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/camera:project_camera_test` |
| `//autonomy/insula:m0_receipt_test` | `requires_live_gate` | Historical rootfs-v2 receipt replay or a separately named current M0 fixture; do not rewrite retained receipts. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:m0_receipt_test` |
| `//autonomy/motion:ingestion__motion_causal_projection_test` | `known_failure`, `requires_motion_causal_project_binary`, `requires_upstream_protoc` | Motion CLI rootfs-v2, upstream proto/protoc mount, current causal projection binary. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:ingestion__motion_causal_projection_test` |
| `//autonomy/motion:cli__motion_joint_cli_test` | `requires_live_gate` | Motion native CLI fixture and rootfs-v2. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:cli__motion_joint_cli_test` |
| `//autonomy/motion:cli__motion_native_cli_test` | `requires_live_gate` | Motion CLI rootfs-v2 and cached `compute_motion_metrics` binary. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:cli__motion_native_cli_test` |
| `//autonomy/motion:pooled__motion_pooled_cli_test` | `requires_live_gate` | Motion CLI rootfs-v2, native metric/proto libraries, fresh pooled CLI build. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:pooled__motion_pooled_cli_test` |
| `//autonomy/segmentation:semantic_recovery_accounting_test` | `requires_live_gate` | Consistent generated receipt fixture at `/source`, current code at `/experiment`. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:semantic_recovery_accounting_test` |
| `//autonomy/segmentation:semantic_recovery_receipt_test` | `requires_live_gate` | Consistent fixture files under `/source`, matching code pins under `/experiment`. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:semantic_recovery_receipt_test` |
| `//autonomy/segmentation:semantic_recovery_receipt_aligned_test` | `requires_live_gate` | Aligned generated receipt fixture and matching code root. | `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:semantic_recovery_receipt_aligned_test` |
| `//autonomy/segmentation:staged_derived_archive_aligned_test` | `known_failure` | CPU rootfs-v4 and dedicated disk-backed `TMPDIR` that supports `O_DIRECT`; generic `/tmp`/tmpfs is not enough. | `TMPDIR=<disk-backed-scratch> ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/segmentation:staged_derived_archive_aligned_test` |

### 7. Live Balanced16 Admission

Phase: 27b only.

Needs GPU/HDFS/network/training: yes/yes/yes/yes.

This command is not read-only. The historical/current `--admission-only` path
trains baseline step 0/1000. Run it only after exclusive GPU and HDFS
authorization are confirmed.

GPU/device requirements:

- `/dev/nvidia1`, `/dev/nvidiactl`, and `/dev/nvidia-uvm` visible inside the
  wrapper environment;
- configured device is `/dev/nvidia1`;
- GPU 4 was reported in use by another process in the prepared task; 27b must
  re-check device ownership and not run if exclusive access is unavailable;
- do not change tags, device paths, rootfs image pins, or sandbox policy to
  bypass missing devices.

Command:

```bash
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-/opt/tiger/yarn_deploy/hadoop/conf}"
RUN_ID="t27b$(date -u +%Y%m%dT%H%M%SZ)"
PYTHONPATH=autonomy python3 -m training_execution.run_sustained \
  --run-id "${RUN_ID}" \
  --admission-only
```

Expected receipts and verification:

- Run root:
  `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/balanced16-sustained-baseline-${RUN_ID}`.
- Source snapshot receipts for sustained execution, controller host sources,
  resource layer, and retention publishers. Verify each with
  `verify_receipt_sources` or `verify_or_materialize_receipt_sources` against
  its recorded store.
- Runtime locks in receipts must match the verified rootfs digests in section 3.
- Stage receipts must bind train/log/output artifacts, all 16 head files,
  literal loss/checkpoint/report identities, native metrics/evaluator receipts,
  resource proof receipts, and retention publisher host-source receipts.
- No skipped test, missing receipt, producer-only pass field, or current-tree
  digest should be counted as acceptance.

Receipt verification helper:

```bash
PYTHONPATH=autonomy python3 - <<'PY'
import json
from pathlib import Path
from evidence.source_snapshot import store_from_receipt, verify_receipt_sources

receipt_paths = [
    # Fill with source receipt paths emitted by the live run.
]
for path in map(Path, receipt_paths):
    receipt = json.loads(path.read_text())
    store = store_from_receipt(receipt, env_var="SUREAL_SOURCE_SNAPSHOT_STORE")
    verified = verify_receipt_sources(receipt, store)
    print(path, verified["source_snapshot_sha256"], verified["source_files"])
PY
```

### 8. Journal Audit And Publication

Phase: 27b only after live acceptance.

Needs GPU/HDFS/network/training: no/yes/yes/no.

Prepared audit facts:

- At commit `247ae52`, the fresh journal audit had 129 entries and 381
  immutable files, all valid.
- The recorded HDFS publication matched exactly the first 101 entries.
- The remaining 28-entry suffix must be published as part of 27b; historical
  publication lag is not corruption.

Local verification command:

```bash
PYTHONPATH=autonomy python3 -m evidence.tracker verify-journal
```

Draft journal note command after acceptance:

```bash
PYTHONPATH=autonomy python3 -m evidence.tracker note \
  --category decision \
  --experiment "balanced16-readmission-${RUN_ID}" \
  --text "Ticket 27 re-admitted the preregistered balanced16 four-recipe candidate on semantic-layout base b576892 / code 85633c0 successor. Recipes, seed, ordered frames and anchors matched preregistration; source snapshots were republished through HDFS with exact readback; runtime locks changed to CPU rootfs-v4 and GPU rootfs-v6; detector recipe paths changed only by ticket-26 byte-identical rename; live admission receipts verified against stored source snapshots and rootfs locks. This is an engineering readmission, not a scientific outcome or completion of the full sweep." \
  --evidence "/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/t27b-readmission/live-admission/${RUN_ID}/admission-summary.json"
```

Publication command:

```bash
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-/opt/tiger/yarn_deploy/hadoop/conf}"
PYTHONPATH=autonomy python3 -m evidence.publish
PYTHONPATH=autonomy python3 -m evidence.tracker verify-journal
```

Before running `evidence.publish`, 27b must preserve the current
`autonomy/research/research-journal-hdfs-verified.json` bytes in a new
append-only/versioned evidence location, because the publisher updates that
receipt path.

### 9. Task Index Draft

Phase: 27b only after acceptance. Do not apply in 27a.

Draft update for `.scratch/semantic-layout/issues/27-readmit-balanced16.md`:

```markdown
**Status:** done

- [x] The sweep's recipes, frames and anchor templates are unchanged from the preregistration
- [x] Each recipe's admission pins a source snapshot stored in HDFS and the new rootfs digest
- [x] Every runtime-lock check listed in ticket 01 is re-admitted on the new images
- [x] A live gate executes the admitted candidate in the new rootfs and its receipt verifies against the snapshot
- [x] The journal records the re-admission and what changed since the original admission
- [x] The task index states the sweep's new status

## Comments

2026-10-08: Re-admitted the preregistered balanced16 candidate on the
semantic-layout successor to base b576892 / code 85633c0. Recipes
`baseline`, `residual_bev`, `class_balanced`, and `prior_bias`, seed 17,
the 16 ordered frames, the 48 input digests, and the anchor templates matched
the preregistered hashes. Current source closures were snapped and uploaded to
HDFS with exact readback through `HdfsSnapshotStore`; receipt verification used
the stored snapshots rather than the working tree. Runtime locks were verified
for CPU rootfs-v4, GPU rootfs-v6, metrics-rootfs, and motion-cli-rootfs-v2.
The live admission gate executed under authorized GPU/HDFS/training access and
all retained receipts verified against their source snapshots and rootfs locks.

This closes engineering readmission only. It does not claim the full four-recipe
32k sweep completed and does not claim a scientific result.
```

## What 27a Did Not Check

- No live HDFS listing or publication was attempted.
- No GPU wrapper command was run; this worker has no visible `/dev/nvidia1`,
  `/dev/nvidiactl`, or `/dev/nvidia-uvm`.
- No training or admission-only command was run.
- No excluded live/known-failure test was run as passing.
- No journal publication or issue-status edit was performed.
