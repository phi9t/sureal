# Balanced16 failure-ledger preparation — 58.A

The retained evidence identifies **30 training-eligible frame/object tuples
without positive assignment: 29 signs and one pedestrian**. They remain in the
native evaluation catalog. This preparation records all 30 in
[uncovered-rows.json](uncovered-rows.json), with a deliberately restricted
[row schema](row-schema.json); it does not implement the complete
[42 failure ledger](../../../tasks/42-object-failure-ledger.md).

Source base: `b32307da442598e192a9259d29a8650be1134589`. Worker native thread:
`01a109a1-c007-73f3-b9d1-ebfb2177c571`; actor `sureal/58-a-20261005a`.
The lead acknowledged the exact reservation before work. This is the
[authorized 58.A preparation](../../../tasks/58-mac-happy-path-perception-pilot.md)
under the [October 5 sequencing override](../../../2026-10-05-mac-happy-path-first.md).

## Denominators and original scope

These are the historical 16 training frames from 13 scenes. Native class codes
1/2/3/4 denote vehicle/pedestrian/sign/cyclist. Counts are recomputed from the
retained full native catalog, ordered eligible-ID reports, and original target
arrays. [reconciliation.json](reconciliation.json) includes each frame.

| Population | Vehicle | Pedestrian | Sign | Cyclist | Total |
|---|---:|---:|---:|---:|---:|
| Full native four-class catalog | 639 | 300 | 302 | 38 | 1,279 |
| Native annotation point count > 0 | 581 | 269 | 266 | 37 | 1,153 |
| Training eligible: positive native point count and center in ROI | 533 | 255 | 231 | 34 | 1,053 |
| Eligible targets present in positive target indices | 533 | 254 | 202 | 34 | 1,023 |
| Eligible targets absent from positive target indices | 0 | 1 | 29 | 0 | 30 |

The training ROI is `[-64,64) × [-64,64) × [-4,6)` for box centers.
Thus 126 native boxes have zero annotation points; another 100 positive-point
boxes have centers outside the training ROI. These two distinct exclusions
account for the 226 native-to-training difference. The 30 uncovered targets
are a subset of the 1,053 eligible targets, not a further GT exclusion.

All 1,279 native boxes remain in full-GT evaluation; native evaluator
eligibility is a separate contract. The receipt field `eligible_groundtruth =
1279` is an export count, not a claim that all 1,279 contribute to every native
metric. The earlier historical V2 evaluation used the 1,053 ROI/positive-point
boxes; the later baseline V3 diagnostic retained the full native catalog.
Do not interpret that decoder-plus-GT-scope change as a controlled improvement.

The [initial analysis](../../../../../experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.md),
[analysis values](../../../../../experiments/waymo-perception/research/2026-10-03-initial-experiments-analysis.json),
and [evidence audit](../../../../../experiments/waymo-perception/research/2026-10-03-initial-experiments-evidence-audit.md)
are retained interpretations. An `initial-experiments-evidence-audit.json` file
does not exist at this base; no companion JSON is invented.

## Exact evidence and resolving IDs

[provenance.json](provenance.json) maps 53 actually reopened files to absolute
original paths, bytes, SHA256 values, and live read-only mount paths. These
include the full native `groundtruth.json`, original manifest and anchor
templates, all 16 `report.json`/`targets.npz` pairs, archived literal worker and
cause `check.json`, oracle count `check.json`, receipts, and the cited current
source. Manifest observation/physical/box hashes are retained separately as
references not reopened for per-object lineage; no support measurement is
inferred from those hashes.

The retained scientific roots are
`~/.cache/waystone/waymo-perception/scientific-processing/balanced16-native-v2`
and `~/.cache/waystone/waymo-perception/insula/`. The cause artifact is
`balanced16-coverage-causes-v1/output/check.json`, SHA256
`051948447cafda82cf58e3432ab597a8e0d117c74ba5a7b53d1cad58d2d4f82b`.
The native catalog is
`balanced16-historical-v3-fullgt-export-v1/output/groundtruth.json`, SHA256
`63c3ae4827ae88cd1d77e4ad34017fd1e564e4087c502d7ca255bf5c72f63143`.
Each example resolves in both artifacts and its eligible-ID report; the new
check verifies its absence from positive target indices and resolves its
competing winner in the same native frame.

| Frame identity | Uncovered native ID / class | Archived cause / winning native ID | Native annotation point count |
|---|---|---|---:|
| `13840133134545942567_1060_000_1080_000:1558402354862835` | `Z5kFobm5wzwlYOkEzSfJBA` / sign | Strictly higher overlap / sign `9Fw3mMbBsbk42SFObIUOiw` | 2 |
| `13506499849906169066_120_000_140_000:1552353849872908` | `ntxrTRPDC3sxr1_FfkOlCg` / sign | Equal-IoU ordered tie / sign `EcDOSpsA_7JgzVwVG6bGrQ` | 11 |
| `7921369793217703814_1060_000_1080_000:1557159628222386` | `IgjdGdzZyFvJUL8JG2aAoQ` / sign | Strictly higher overlap / vehicle `ATVCUZjZC4WJ65KtlUsdBA` | 708 |
| `11004685739714500220_2300_000_2320_000:1553640277306703` | `8-7bTNGWUlWqADUHKbnjqg` / pedestrian | Strictly higher overlap / pedestrian `FsNFk3PanpdmdhRZ7ssgKw` | 19 |

The sign `IgjdGdzZyFvJUL8JG2aAoQ` also occurs at timestamp
`1557159618222385`, with 721 annotation points. An object ID alone is not a
unique row key; use `(context_name, frame_timestamp_micros, object_id)`.

The [archived literal cause audit](../../../../../experiments/waymo-perception/research/balanced16-coverage-causes-verified.json)
reconstructed every frame's 524,288 labels and target indices. All 30 missing
targets had positive maximum nearest-BEV anchor IoU: 28 lost to strictly higher
overlap and two signs lost equal-IoU ordered argmax ties. The conflicts are 27
sign-to-sign, two sign-to-vehicle, and one pedestrian-to-pedestrian; 28 involve
the same class. Restricting competition by class alone leaves those same-class
conflicts unresolved. These causes are archived measurements; the new check
reopens them and reconciles coverage, without rerunning the geometric audit.

The [archived annotation-only native controls](../../../../../experiments/waymo-perception/research/balanced16-coverage-oracle-status.md)
give sign APH .868421 for all training-eligible targets and .759399 for covered
targets against the same full native GT. Those are ideal annotation
predictions, not learned predictions or a universal detector ceiling.

## Machine-readable missingness

Each row has native identity/class/annotation point count, the exact archived
assignment record, zero positive-anchor count, and provenance keys. Zero is
justified here by the original positive target indices. The schema requires
explicit `null` for raw/retained per-object point counts and originating
measurement IDs; best decoded 3D IoU/geometry/heading; predicted class/score/rank;
score-floor, pre-top-k, NMS and post-top-k survival/rejection; official native
match and heading; checkpoint/head/decoder identity; and reproducible views.

Native `num_lidar_points_in_box` is annotation metadata, not a measured count
of the retained detector input or an original sensor/return/pixel lineage.
The native export's `difficulty` is also null for these examples. Assignment
`maximum_iou` is nearest-BEV anchor overlap, not decoded 3D candidate IoU.
Missing assignment does not establish that the detector failed to predict the
object. No diagnostic geometric association is called an official native match.

## Fresh preparation check and operational limits

[verify_preparation.py](verify_preparation.py) runs in live CPU Insula using
the existing `pipeline.insula_entry.launch_plan` and retained `rootfs-v2`.
[live-receipt.json](live-receipt.json) retains actual argv/exits, fresh rootfs
digest verification, input/source/artifact hashes, kernel resource facts,
and observed child cleanup. The receipt is excluded from its own document
hash list to avoid a recursive digest; all preparation content is pinned.
The independent integration lead must reopen those identities and recheck
current-base content before landing.

New execution validates 53 pinned files, all native frame/object identities,
16 eligible-ID reports and target arrays, the 30-row schema and missingness,
and document links. The unique systemd scope imposes exactly 2 GiB RAM and
zero swap; no GPU device bindings are added, `/dev/nvidia*` and `/dev/dri` are
absent, TensorFlow is absent, and optimizer updates are zero. The checker
refuses a changed digest or mismatch. It is a bounded preparation verifier;
full 42 decoder traces, physical lineage, native match extraction, visualization,
and the comprehensive fault matrix remain outstanding.

All external artifacts stay owned at
`/data02/home/philip.yang/workspace/.sureal-collab/pilot58-20261005a/worker-a`.
The first check (`live-v1`) failed before execution because its extra mount
targets `/retained` and `/repository` did not exist in the read-only rootfs.
Its failure/argv/source are retained. Binding originals under the existing
`/tmp` tmpfs fixed the pilot staging choice; `live-v2` passed (1.531 seconds
including rootfs verification; largest waited-child RSS 50,164 KiB).
The final receipt records the subsequent completed-document check.
This does not add a daemon or alter the launch pipeline. No scientific source,
input, target, GT, model or checkpoint is written or released; no GPU, training,
native metric replay or HDFS action is performed.

## Smallest next 42 slice

Produce the complete 1,279-row **native eligibility/coverage prefix** from the
same frozen native catalog and original targets, with tuple keys, exact source
pins, explicit exclusion reasons, and positive-anchor counts. Keep the 226
training-ineligible native boxes and all 30 uncovered eligible objects. Use the
four examples above as hand-reopenable joins; preserve all downstream fields
as null. Then implement a separately pinned per-object raw/retained support
join to originating measurements and retention indices for one selected frame,
before expanding to full16 or adding decoded candidate traces. Admission of
that new join needs literal CPU Insula validation of physical point identity;
this preparation supplies no such proof and does not close 42, 50, or 53.
