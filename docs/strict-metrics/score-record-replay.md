# Strict score-record replay report

Read-only roots:
- `<cache>`
- `autonomy/research`

## Inventory

- JSON files mentioning `LEVEL2_per_class`: 1433
- Parsed JSON files containing `LEVEL2_per_class` records: 1371
- `LEVEL2_per_class` records: 6404

### Shapes

- 4672: `classes=1,2,3; rows=AP/APH x3`
- 1727: `classes=1,2,3,4; rows=AP/APH x4`
- 4: `classes=1,2,3,4; rows=APH x4`
- 1: `classes=CYCLIST,PEDESTRIAN,SIGN,VEHICLE; rows=AP/APH x4`

## Consumer Replay

### sustained_admission

- Class rule: all four native LEVEL_2 classes: 1, 2, 3, 4
- Records replayed: 4
- Accepted: 4
- Rejected: 0

### sustained_contract

- Class rule: all four native LEVEL_2 classes: 1, 2, 3, 4; reduced APH samples are wrapped as AP=APH before reading
- Records replayed: 4
- Accepted: 4
- Rejected: 0

### evidence_projection

- Class rule: classes with positive groundtruth_by_class when present; otherwise all points require native LEVEL_2 classes 1, 2, 3, 4
- Records replayed: 214
- Accepted: 214
- Rejected: 0

### fixed_batch_verifier

- Class rule: all four native LEVEL_2 classes: 1, 2, 3, 4
- Records replayed: 435
- Accepted: 435
- Rejected: 0

## Populated-Class Producer Compatibility

- These are retained score records whose containing object has `groundtruth_by_class`; they are replayed with classes whose counts are greater than zero.
- Records replayed: 4672
- Accepted: 4672
- Rejected: 0

## Consumed Rejections

- None

## Unconsumed Odd Records

- Unconsumed `LEVEL2_per_class` records: 5972
- Unconsumed odd-shaped records: 5

- `<cache>/insula/association-runs/oracle20261003a/check.json` `LEVEL2_per_class`: classes=CYCLIST,PEDESTRIAN,SIGN,VEHICLE; rows=AP/APH x4; producer: association oracle coverage control; consumed by migrated reader: no
- `<cache>/insula/research-tracker-live-v1/fixture/results.json` `cases/baseline/curve/0/LEVEL2_per_class`: classes=1,2,3,4; rows=APH x4; producer: research tracker live fixture; consumed by migrated reader: no
- `<cache>/insula/research-tracker-live-v1/fixture/results.json` `cases/baseline/curve/1/LEVEL2_per_class`: classes=1,2,3,4; rows=APH x4; producer: research tracker live fixture; consumed by migrated reader: no
- `<cache>/insula/research-tracker-live-v2/fixture/results.json` `cases/baseline/curve/0/LEVEL2_per_class`: classes=1,2,3,4; rows=APH x4; producer: research tracker live fixture; consumed by migrated reader: no
- `<cache>/insula/research-tracker-live-v2/fixture/results.json` `cases/baseline/curve/1/LEVEL2_per_class`: classes=1,2,3,4; rows=APH x4; producer: research tracker live fixture; consumed by migrated reader: no

## Compatibility Decision

- Sustained admission, sustained contract and fixed-batch verifier require all four native LEVEL_2 classes because their retained inputs are all-class gates.
- Evidence projection accepts populated-class records only when the consumer context names that populated set via `groundtruth_by_class`; otherwise records require all four classes.
- Projection quality remains the all-four acceptance rule: populated-class records can populate display fields, but cannot satisfy overfit quality.
- Old mis-keyed range entries under `metrics` are tolerated here only because these migrated readers read `LEVEL2_per_class`, not the historical range rows.
- The odd retained records above are not consumed by any migrated reader, so the score-record reader was not loosened for them.
