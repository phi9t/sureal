# Sustained checkpoint retention preparation

`cohort/sustained_checkpoint_inventory.py` verifies byte lineage for one externally admitted checkpoint at any actual update0..32,000. Seven successful stage receipts and every original stage artifact must match the pinned final receipt and manifest. Producer manifest, actual/requested updates, stop reason, resource admission, checkpoint and all16 heads must match. The payload union is exactly19 files; extra/missing/changed/symlink paths refuse. Honest time-censored terminal samples are supported without declaring fitting success.

Live CPU evidence: missing-module RED, initial79-test GREEN, meaningful re-pinned producer-manifest mismatch RED, then fixed79-test GREEN. Fresh independent review reconciled279 source pins and separately reran all79 tests. The report manifest binding finding is resolved.

This helper checks retained bytes and lineage only. Underlying GPU state transition, literal loss, export, proposals and native metric mathematics need their separate live admissions. Generic arbitrary-checkpoint HDFS publication/readback/live recovery/whole-union release and the sustained four-case controller are still required. No new GPU training or generic checkpoint deletion has run.

Evidence: `sustained-checkpoint-inventory-{red,green}-v1-verified.json`, `sustained-checkpoint-manifest-{red,green}-v1-verified.json`.
