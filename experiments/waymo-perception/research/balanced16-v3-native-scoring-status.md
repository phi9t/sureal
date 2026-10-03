# Balanced16 V3 native scoring preparation

This increment scores the historical baseline's 2,000-update heads. It does not train a new model, establish sustained fit, or provide held-out scientific evidence.

The V3 export retains all 1,279 native four-class ground-truth boxes, including zero-point and out-of-ROI boxes; native evaluation determines eligibility. The original training targets contain 1,053 eligible boxes. Decoder and evaluation scope differ from historical V2/ROI reports, so the numbers are not a controlled architecture comparison.

Native LEVEL_2 APH is 0.281619 vehicle, 0.242956 pedestrian, 0.0236408 sign, and 0.00190988 cyclist. The all-class 0.8 gate fails. A mean cannot substitute for this gate, and sustained fitting additionally requires consecutive confirming checkpoints.

Live evidence includes literal full16 proposal decoding/NMS, physical point counts and NLZ metadata; all native protobuf fields; and exact independent replay of native metrics. Review found that the proposal auditor initially accepted records from unknown frames. The corrected verifier validates the entire catalog before per-frame checks, requires ordered frame reports and per-frame counts, and rejects duplicate object IDs. Empty frames remain valid. Four regression groups cover foreign-frame records in both catalogs, duplicate IDs even when counts are re-pinned, count/order/manifest errors, and valid empty frames. The live CPU suite contains 49 passing groups.

The pilot launcher now freezes every stage's receipt aliases, exports/scorers/auditors after each 0/19/35-update chunk, and checks both GPU and native-metric runtime identities. This is wiring preparation: actual GPU pilot admission and the four-recipe sustained controller remain pending, including verified HDFS retention to make room for the local working set.

Evidence: balanced16-historical-v3-fullgt-metrics-verified.json; balanced16-historical-v3-native-metric-audit-verified.json; balanced16-historical-v3-proposal-audit-verified.json; balanced16-catalog-red-v1-verified.json; balanced16-catalog-green-v1-verified.json.
