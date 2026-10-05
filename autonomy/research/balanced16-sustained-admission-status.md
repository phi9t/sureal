# Native balanced16 execution admission

The baseline0/19/35 engineering pilot now has all21 required stages: GPU training/state/full16head replay; independent literal full0→35 and restart19→35 trajectories at terminal35; independent NumPy losses; full-native-GT V3 export; literal proposal/NMS/point-count/NLZ checks; official native scoring; and independent protobuf-field/native metric replay. Fresh review reconciled809 distinct source/input/output/parent/driver hashes and57 retained payload files.

The original run ended at its600-second score35 subprocess limit. Its failed log/binaries, frozen package and successful19 stage receipts are preserved. A separate source-pinned recovery changes only two native subprocess bounds from600 to1800 seconds. Step35 scoring completes in636.837 seconds; independent native replay agrees exactly. Future scoring/replay now defaults to the user-authorized4hours with4h5m host limits. This recovery retains its original frozen1800-second setting.

| Update | Cumulative synchronized training seconds | Producer peak GPU bytes | Producer peak RSS KiB |
|---|---:|---:|---:|
| 0 | 0.000000 | 661,350,912 | 2,652,964 |
| 19 | 2.381080 | 1,747,883,520 | 3,132,760 |
| 35 | 4.954181 | 1,785,223,680 | 3,141,272 |

Replay peak is1,845,126,144 allocated GPU bytes and3,141,448KiB RSS, within the unchanged8GiB/16GiB gates. Scoring retains all1,279 native GT and8,000 exported predictions. All four native LEVEL2 APH values are0 at these early checkpoints. No native fitting threshold or scientific quality is passed.

Evidence: `balanced16-sustained-admission-native20261003b-recovered.json` (21 stage bindings; external reviewed SHA ecaf72cc586934e40b0fe8235ef771766666f647d211004ccd42d1e9292ab7be), `balanced16-sustained-pilot-timeout.json` (original failed stage), and frozen source/input/output paths in their receipts. The raw command paths preserve exact replay. Checkpoint/head local eviction requires the separately admitted HDFS archive/readback/recovery/global-union lifecycle; none follows solely from this status document.

Decision: adopt this source-frozen execution/restart/evaluation path as an engineering foundation. Sustained balanced16 fitting, extended chunk admission, four matched optimization cases, protocol07 and all held-out studies remain open. A short execution pilot is not an overfit study.
