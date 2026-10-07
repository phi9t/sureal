# Architecture experiments

A persistent catalog of tested directions and planned follow-ups. The runner uses host Python standard library only; model training and native evaluation run inside the existing locked Insula roots. Torch is inside the GPU root, not required on the host. No TensorFlow.

Prediction–target association is a separately specified experiment axis:
[study handbook](../../research/prediction-target-association-study.md),
[ticket 41](../../../docs/research/tasks/41-prediction-target-association.md).
Its A0–A3 matrix separates legacy ownership, global coverage, 3D geometry and
prediction-dependent matching while keeping the baseline architecture/loss/decoder
fixed. These treatments are planned and are not supported by this architecture
runner. Existing results retain their original target contract; coverage, live
implementation admission, actual native fitting and held-out benefit remain
separate gates.

| ID | Status | Goal |
| --- | --- | --- |
| [deep_pfn](ideas/deep_pfn.md) | runnable | Pointwise nonlinear depth may improve geometry encoding without spatial interactions. |
| [context_pfn](ideas/context_pfn.md) | runnable | A point may benefit from its pillar-wide geometric context before pooling. |
| [residual_bev](ideas/residual_bev.md) | runnable | Identity paths may improve spatial optimization without adding parameters. |
| [retain64](ideas/retain64.md) | runnable | The32-point cap may discard useful measurements. |
| [masked_pfn](ideas/masked_pfn.md) | runnable | Padded slots may distort the pooled representation. |
| [window_bev](ideas/window_bev.md) | runnable | Learned spatial interactions may improve the coarsest BEV features. |
| [coarse_mlp](ideas/coarse_mlp.md) | runnable | Added coarse-stage capacity may explain an apparent attention gain. |
| [all_pillars](ideas/all_pillars.md) | runnable | Pillar truncation may remove all measurements from small objects. |
| [ragged_pillars](ideas/ragged_pillars.md) | planned | Removing the per-pillar point cutoff may improve support and avoid padding artifacts. |
| [grid_fine](ideas/grid_fine.md) | planned | Finer XY cells may preserve small-object geometry. |
| [grid_coarse](ideas/grid_coarse.md) | planned | Coarser cells may reduce computation without sacrificing useful geometry. |
| [point_attention](ideas/point_attention.md) | planned | Relative point-to-point interactions may improve summaries of local shape. |
| [range_fusion](ideas/range_fusion.md) | planned | Sensor-neighborhood context may complement metric pillar geometry. |
| [sparse_bev_transformer](ideas/sparse_bev_transformer.md) | planned | Occupied spatial tokens may support broader context at controlled cost. |

From this worktree, use:

```bash
python autonomy/architecture.py list
python autonomy/architecture.py show residual_bev
python autonomy/architecture.py run residual_bev --run-id residual-trial01 --dry-run
python autonomy/architecture.py run residual_bev --run-id residual-trial01
python autonomy/architecture.py verify residual_bev --run-id residual-trial01
```

An absolute path to architecture.py works from any current directory. A run ID is globally unique in the selected cache. Omit it to generate a UTC timestamp plus random suffix. Existing runs are preserved; reusing an ID requires `--resume`. Completed stages are skipped only after their evidence hashes are verified. If an incomplete stage already has outputs, resume stops and preserves them; select a new run ID. This runner does not erase/retry partial artifacts.

```bash
python autonomy/architecture.py run residual_bev --run-id residual-trial01 --resume
```

Verification now always names a run ID. The old read-only mode
`python autonomy/architecture.py verify <experiment>` compared historical
receipts with the working tree and has been retired; historical receipts remain
records, but they are not reverified against edited source paths.

Prerequisites: the acquired native caches and their admission receipts, bubblewrap, locked GPU/CPU/native-metric roots, and matching NVIDIA driver files. Default cache: `~/.cache/waystone/waymo-perception`; `--cache-root PATH` precedes the subcommand to select an already prepared cache. This runner does not download data, authenticate, build root filesystems or silently replace missing fixtures. Retention candidates additionally require their independently admitted64-point/all-pillar caches. Missing prerequisites fail with an explicit path.

Each run takes a content-addressed source snapshot of
`//autonomy:architecture_experiment_runner_snapshot` through the evidence
module (maximum64MiB), records the snapshot digest and Bazel target in
`run.json`, and adds the same source-snapshot fields to new stage receipts. The
runnable private workspace is materialized from that snapshot, so later
unrelated source edits do not change resume or verification. The dated study
spec remains linked below and its SHA-256 is pinned by the runner source. Logs,
run metadata and a final summary are written under:

```text
<cache>/insula/architecture-runs/<run-id>/
  run.json            # frozen experiment, source pins, stage plan
  logs/               # contract/train/replay/score/audit logs
  summary.json        # exists after every required admission passes
  failure.json        # retained stage failure when applicable
  source/             # frozen source plus new stage receipts
  ../source-snapshots-v1/<sha256>
```

Large model/scoring outputs remain under `<cache>/scientific-processing/architecture-<experiment>--<run-id>-...`. They retain the15GiB scientific and768MiB per-training-run caps. A nonblocking shared flock serializes runs through this entry point. Existing direct legacy invocations are outside that lock; use this entry point for new work. Dataset/runtime inputs are shared read-only, not copied; historical results are untouched.

The public bundled harness lives in `harness/`. New executions do not depend on the checkout’s temporary `.scratch` scripts. Its frozen private run workspace uses the old internal worker filenames to preserve the verified implementation; users need only the entry point. Historical verification still uses the paths pinned in historical receipts.

A completed run means the implementation and evaluation are admitted. It does not mean the architecture passed quality thresholds. Summaries report scores and first crossing brackets; full-class Tier1 and heldout promotion remain separate. The fixed recipe is deliberately not an unrestricted hyperparameter sweep. Additional seeds/configurations require a separately specified experiment.

[First-cohort results](../../research/architecture-first-cohort-results.md) · [Study spec](../../../docs/superpowers/specs/2026-10-02-perception-architecture-study-design.md) · [Execution plan](../../../docs/superpowers/plans/2026-10-02-perception-architecture-study.md)

## Verified runner evidence (2026-10-02)

Fresh run `runner-live-20261002` completed all seven live Insula stages for `residual_bev`, including independent checkpoint replay, loss reconstruction, and native scoring audits at all 11 checkpoints. Training took 130.83 seconds for 2,000 updates; final mean populated-class LEVEL2 APH was 0.907812. The sign-class gate did not pass, and the fixture contains no cyclists: this is an implementation admission, not full-class or heldout acceptance.

The public runner's 12 contract tests passed inside the CPU Insula root. Review-driven checks cover manifest tampering, missing required contracts, reserved run labels, and descendant-process cleanup on timeout. Completed-run resume verified and skipped all seven stages.

Historical follow-up contract verification currently refuses a stale source hash in `gpu/architecture-followup-contract.py`. Preserve that evidence; use a fresh run to obtain contracts pinned to its frozen source. Original cohort scores remain recorded in the results document.
