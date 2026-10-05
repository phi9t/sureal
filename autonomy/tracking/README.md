# Experiment tracker and research journal

The registry defines expected runs and complete recipes. The dashboard derives
status from native curves and matching final live closure, keeping GPU admission,
training, execution failure, scientific censoring and equivalence distinct.
Every experiment records a goal, verifiers and acceptance criteria.

```bash
python experiments/waymo-perception/tracking/cli.py refresh
python experiments/waymo-perception/tracking/cli.py watch --interval 60
python experiments/waymo-perception/tracking/cli.py note --category hypothesis --experiment expanded20261002a/range_fusion --text 'State a falsifiable hypothesis here' --evidence path/to/receipt.json
python experiments/waymo-perception/tracking/cli.py verify-journal
python experiments/waymo-perception/tracking/publish.py
```

Read `research/experiment-tracker.md` and `research/research-journal.md`.
The machine-readable dashboard is `research/experiments.json`; definitions are
in `research/experiment-registry.json`. The append-only journal is JSONL.
Observations, hypotheses, decisions and follow-up work are separate categories.
Evidence is copied to immutable content-addressed snapshots before automatic
stage-transition notes; entry hashes link the journal history. Git commits and
HDFS snapshots anchor the journal head. The chain detects edited entries;
it cannot prove an unanchored suffix was never truncated.

A refresh records newly verified/admitted stages once. Running checkpoint
updates appear in the dashboard without flooding the journal. The watch command
retries partial result writes and retains the previous dashboard. It fails
explicitly on invalid evidence instead of silently declaring success.

Results and journal snapshots can be retained on HDFS; use verified upload and
readback receipts. TensorFlow is not required. The tracker is metadata-only and
makes no claim of held-out, segmentation or full-dataset success.
