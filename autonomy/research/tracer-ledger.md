# Real-data tracer ledger

Worktree: `.worktrees/waymo-tracer`, branch `work/waymo-tracer`.

User requested acquire-first investigation, not full production-plan execution.
Ruling: build the minimal tested tracer over the actual 17-component local slice;
leave the production runtime/schema and reduced-pilot gates separate.

Ruling: use an isolated Python 3.12 environment with the same PyArrow 25.0.1
observed in Waystone; no SDK or TensorFlow. This supersedes the proposed Python
3.10 choice for this tracer only and does not change Surflo dependencies.

Access verified; validation split inventoried: 3,434 Parquet files across 17
components and 202 contexts, 128,583,245,118 bytes. Selected two scenes with
nonempty sparse camera/LiDAR keypoint and segmentation files rather than the
smallest scenes whose auxiliary files were empty. Local acquisition complete:
34 files, 1,200,154,353 bytes, generation-pinned copies with provider MD5 and
content SHA-256. Full dataset acquisition is not authorized by this tracer and
was not launched. HDFS storage uses Waystone-resolved Sureal child namespace.

Completed: all 34 objects uploaded through Waystone and downloaded again;
full SHA-256 and byte-size roundtrip matched. Receipt uploaded to HDFS.
The offline tracer processes every row in all 17 families, validates native
key lineage, payload dimensions and transforms, and reports unresolved
associations as unknown. Review's independent-validator lineage gap was
reproduced with three failing cases and fixed; all 16 tests pass.
See `tracer-bullet-e2e.md` and `tracer-reproducibility.json` for final real-run
coverage and manifest repeatability evidence. Production roadmap gates remain.
