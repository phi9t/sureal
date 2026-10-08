# Expanded fixed-batch architecture suite

This implements the approved fine/coarse-grid, ragged-pillar, point-attention,
range-fusion and sparse-BEV ideas, with matched-parameter point-MLP and
zero-range mechanism controls. These remain **experimental recipes** until
actual-frame CUDA admission and native overfit closure pass.

The reusable code lives in its concepts: the architecture-adaptation catalog,
models, packing and point/sparse/spatial modules are in
`detection/architecture_adaptations/`, while observation loading is in
`dataset/detector_observations.py`. The closed
CUDA and HDFS gate scripts that produced retained receipts are preserved as
byte records in `procedure_records/`; they are not active library entrypoints.

Inspect the current catalog from the isolated worktree:

```bash
PYTHONPATH=autonomy python -c "from detection.architecture_adaptations.catalog import catalog; print('\n'.join(catalog()))"
PYTHONPATH=autonomy python autonomy/studies/expanded_batch/expanded_verifier.py autonomy/research/advanced-SAMEID-results.json
```

Preparation reuses hash-checked receipts. Range preparation needs the pinned
original native LiDAR shard in `scientific-processing-staging/advanced-range-source-v1`;
it includes range/intensity/elongation and measurement validity, excluding
annotation fields and the no-label-zone channel. Point-to-pixel identity stays
aligned with the original packed points. Ragged inputs keep every eligible
point in selected pillars. Grid treatments keep the physical output anchor
lattice but change point/pillar retention; report those effects together.

Admission uses the shared exclusive GPU lock and the existing locked Torch
Insula runtime. Every recipe executes the actual all-class frame, verifies
finite gradients for every parameter, and repeats a three-update Adam
trajectory exactly, including model, optimizer and RNG. Range initial heads
must equal the original baseline. The optional `admit.py --wait` defers CUDA
work until the original sweep's live final closure receipt exists.

Training freezes sources and refuses a mismatch with admitted architecture
sources or observations. The fixed frame has all73 native objects. Objective,
seed, anchors, decoder and native evaluation stay fixed. Each chunk requires
literal loss checks, independent proposal and native evaluator audits, and
full trajectory replay before transient heads are released. Acceptance is
LEVEL2 APH >=0.8 for all four classes at two consecutive sampled checkpoints,
including terminal. Otherwise continue unchanged to10,000 updates; execution
or resource failures are open failures, never scientific negatives.

Keep scientific payload within15 GiB, raw data within2 GiB, allocated CUDA
memory within8 GiB and worker RSS within16 GiB. The expanded training matrix
must have sufficient admitted headroom; verified HDFS upload, independent
readback/member checks and retention lineage must precede release of any
new-run local artifact. Human HDFS authentication is performed with
`../scripts/refresh-hdfs-auth.sh`. Historical evidence is retained. After an
entire new-run matrix has live closure, the retained expanded publication
procedure record describes the bounded publisher run; active reusable archive
helpers now live under `resources/`.

The publisher partitions a complete case inventory into bounded archives,
resolves the Sureal runs prefix through Waystone, pins the native tools, and
bounds transfers externally. Each archive and manifest is downloaded again;
separate CPU Insula workers verify every member and perform bounded recovery.
It publishes the complete inventory last, rereads it, then plans release.
Failed transfers retain local artifacts. The publication receipt maps every
released path/hash to its HDFS archive member. Its offline worker smoke test
is not evidence of successful HDFS publication.

These are one-batch fitting diagnostics. They do not close16-frame,
segmentation, held-out evaluation or full-dataset training goals.
