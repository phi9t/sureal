# Fixed-batch architecture overfit suite

The reusable fixed-batch catalog and model code lives in `detection/`. The
closed preparation and run scripts that produced retained receipts are preserved
as byte records in `procedure_records/`; they are not active library
entrypoints.

Run the retained-result verifier from the repository worktree:

```bash
PYTHONPATH=autonomy python autonomy/studies/fixed_batch/fixed_batch_verifier.py autonomy/research/tier1-overfit20261002b-results.json
```

Preparation verifies and reuses an existing admitted fixture, or creates its immutable namespace once. It needs the admitted balanced native/physical/annotation cache, not GCS auth or TensorFlow. Training requires the admitted CPU, Torch GPU and official C++ metric Insula runtimes and NVIDIA driver identity. The runner takes the existing exclusive architecture GPU lock and freezes all worker sources.

The selected one-frame batch has73eligible native objects, all four classes, five cyclists and no uncovered targets. Every variant shares the same frame/targets/seed and changes one factor. The `all_pillars` row is an equivalence control: the original cap does not bind on this frame. Planned range/point-attention/ragged/sparse-transformer designs are not presented as executed variants.

Native per-class LEVEL2APH must reach0.8 for **every** class at two consecutive sampled checkpoints including the terminal checkpoint. Stop on an admitted pair within the2000-update primary ceiling; otherwise continue the same Adam trajectory to10000. Scalar losses never replace this gate. Store measured training times and sampled fit intervals; a capped negative is explicitly censored.

Every stage runs live Insula. Admission includes independent literal losses, score-first proposal/NMS and measurement/GT audits, protobuf rereading and official evaluator reruns, and exact replay of every checkpoint head plus terminal model/Adam/RNG. Scientific writes reserve their uncompressed bound before allocating; full replay precedes release of declared new transient heads/checkpoints. Persistent source/input/runtime pins, native records/metrics, complete curves, initial/final heads and terminal Adam state remain. Historical artifacts retain their bytes; only byte-identical duplicates are hardlinked.

Decoderv3 corrects a proven periodic-heading bug in legacyv2: canonicalize the raw angle before applying its direction bin. Keep old scores separate. The paired native diagnostic is recorded in `research/tier1-heading-step2000a-verified.json`. The original baseline optimization was retained and independently rescored/replayed under the corrected verifier.

The active full sweep is `overfit20261002b`, adopting the unchanged4000-update baseline trajectory. Local progress is `research/tier1-overfit20261002b-results.json`; all other variants begin fresh, with verified early stopping. These are fitting diagnostics, not held-out validation or full-dataset training.

The balanced-loss treatment here requires every class to have positive anchors in the fixed batch. Full-cohort use needs a separately specified absent-class/weighting contract.
