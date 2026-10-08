# Strict metrics: every metric report is read through its strict reader

Status: ready-for-agent

Governing decisions: `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md` and `docs/adr/0001-directories-express-concepts.md`. Vocabulary follows `autonomy/CONTEXT.md`: metric report, live implementation gate, source snapshot, source pin.

## Problem Statement

Every quality claim in the perception program comes from a native evaluator's metric report. A strict reader for the detection report already exists, `parse_result` in the detection concept. It requires:
- a zero exit code and an example-count header;
- every line fully matched, every breakdown expected and seen exactly once, and the breakdown set complete;
- every value finite and within [0, 1].

Only two contract verifiers use it. Everything that produces or audits a score reads the report with its own lenient pattern instead.

- **The detection readers mis-read the report today.** The pattern is `(\S+): [mAP …] [mAPH …]`. The native report's range breakdown names contain a space (`RANGE_TYPE_VEHICLE_[0, 30)_LEVEL_1`), so the pattern captures only the suffix, such as `30)_LEVEL_1`. Each class's range rows then collide under one key, and the last one wins.
  - The four-class LEVEL_2 values the gates use are unaffected, because those names have no spaces.
  - The `metrics` dictionary written into every `check.json` holds mis-keyed and silently overwritten range entries.
- **Lenient readers hide bad reports.**
  - The plain detection scorer has no tests. It ignores stderr, the example count and unknown or duplicate lines. It drops classes whose ground-truth count is zero, and divides by zero when no class is populated.
  - The audit scripts re-parse with the same pattern and compare with `==`, so both sides share the same blind spots.
  - The real-export check uses an unanchored search.
  - The segmentation fixture reader's number pattern cannot match `nan` or `inf`, so such a line is silently skipped.
  - Motion CLI tests pick a class bundle with `next(…)` and never notice duplicates.
- **Downstream readers of score records are lenient too.**
  - The evidence projection reads per-class scores with `.get(…, {})` and a default.
  - The fixed-batch verifier checks only the key set.
  - Only the sustained admission reader checks keys, finiteness and bounds.
- **The strict detection reader cannot accept real reports as written.**
  - 49 of the 195 retained `metrics.stderr` files on this host are non-empty.
  - The content is only the evaluator's known glog diagnostics: `Tiny box dim seen` and `Huge box dim seen` from `iou.cc`, plus `WARNING: Logging before InitGoogleLogging()`.
  - The reader rejects any stderr, so switching producers over without a rule for these diagnostics would fail real runs.
- **The expected breakdown set is not a committed fact.**
  - The detection contract verifier derives the 32 expected names at run time from comments in the evaluator's C++ source.
  - Nothing else knows the set, so nothing else can pass it to the strict reader.

## Solution

Each kind of metric report has exactly one strict reader. It lives in the concept that owns the evaluator and fails loudly. Every active producer, audit and test reads reports only through it.

| Report | Reader | Owner |
|---|---|---|
| Detection | `parse_result`, extended as described below | detection |
| Segmentation | New strict reader | segmentation |
| Motion | New strict reader, grown from the strict pooled handoff check | motion |

Downstream code that reads the per-class score record written into `check.json` also goes through one strict reader. Before any producer changes, a read-only replay runs every retained metric report on this host through the strict readers and reports what they would reject. Any rejection stops the work for a coordinator decision; a reader is never loosened to make evidence pass.

## User Stories

1. As a researcher, I want every detection metric report read through one strict reader, so that a gate passes only on a report that is complete and well-formed.
2. As a researcher, I want range breakdown names with spaces read correctly, so that `check.json` records the true range breakdowns instead of overwritten suffixes.
3. As a researcher, I want an unexpected, missing or duplicated breakdown to reject the report, so that a changed evaluator configuration cannot pass unnoticed.
4. As a researcher, I want a non-finite or out-of-range AP or APH to reject the report, so that no quality claim rests on `nan` or a value above 1.
5. As a researcher, I want a missing example-count header to reject the report, so that a truncated report cannot be scored.
6. As a researcher, I want a non-zero evaluator exit code to reject the report, so that a crashed evaluator never yields a score.
7. As a researcher, I want the evaluator's known benign diagnostics accepted and counted, so that real runs with degenerate predicted boxes still score while every diagnostic stays visible.
8. As a researcher, I want any stderr line outside that known set to reject the report, so that new evaluator errors are never swallowed.
9. As a researcher, I want the known diagnostics listed by exact glog file, line and message, so that accepting them is a reviewed fact rather than a pattern that can drift.
10. As a researcher, I want the expected detection breakdown set committed in the detection concept, so that every caller passes the same frozen configuration to the reader.
11. As a researcher, I want a test that the committed breakdown set equals the one the evaluator source documents, wherever that source is available, so that the constant cannot drift from the evaluator.
12. As a researcher, I want the plain detection scorer to fail loudly when no class is populated, so that an empty scope is an error, not a divide-by-zero.
13. As a researcher, I want classes with zero ground truth handled by an explicit, documented rule, so that which classes a mean covers is never an accident of a dictionary lookup.
14. As a researcher, I want metric audits to re-read the report with the same strict reader as the producer, so that an audit cannot agree with a producer's mistake.
15. As a researcher, I want the real-export check to read the report strictly instead of searching for one line, so that it checks the whole report.
16. As a researcher, I want every segmentation metric report read through a strict segmentation reader, so that per-class IoU and mIoU are complete and finite.
17. As a researcher, I want a segmentation report line holding `nan` or `inf` to reject the report, so that an undefined IoU can never be silently skipped.
18. As a researcher, I want the segmentation reader to know the evaluator's preamble lines, such as the frame counts and progress lines, so that every other line is either a class score or an error.
19. As a researcher, I want the segmentation reader to require each expected class exactly once and the mIoU line exactly once, so that a partial report is rejected.
20. As a researcher, I want every motion metric report read through a strict motion reader, so that per-class minADE and minFDE come from exactly one bundle per class.
21. As a researcher, I want a duplicated or unknown `objectFilter` bundle to reject a motion report, so that the reader never silently picks the first match.
22. As a researcher, I want the motion reader to apply proto3 JSON's omission of zero-valued fields explicitly, from a declared list of such fields, so that a legitimately zero minADE is read as 0.0 and a missing structural field is still an error.
23. As a researcher, I want the measurement step and per-class counts checked by the motion reader, so that the handoff checks no longer each repeat those checks.
24. As a researcher, I want one strict reader for the per-class score record in `check.json`, so that the evidence projection, the fixed-batch verifier and the sustained contract agree on what a valid score record is.
25. As a researcher, I want the evidence projection to keep showing a run with no score yet as running, but to reject a malformed score record, so that "no score yet" and "bad score" are different states.
26. As a researcher, I want a read-only replay of every retained metric report on this host through the strict readers, so that I know before migrating whether any retained evidence would be rejected.
27. As a researcher, I want the replay to list each rejected report with its path and the reader's reason, so that every rejection becomes a decision rather than a surprise.
28. As a researcher, I want the replay to count retained `check.json` files whose `metrics` dictionary holds mis-keyed range entries, so that the extent of the historical mis-read is recorded.
29. As a researcher, I want work to stop for a coordinator decision when any retained report is rejected, so that strictness is never traded away to make old evidence pass.
30. As a researcher, I want retained `check.json` files left unchanged, so that historical receipts stay as they were written (ADR 0001).
31. As a researcher, I want the balanced16 sustained scorer and its metric audit moved to the strict reader in their own ticket, so that the change to balanced16's source snapshot is isolated and re-admitted once by blob-store ticket 12.
32. As a test author, I want each strict reader tested with real retained reports as fixtures alongside synthetic malformed ones, so that a reader is proven on real evaluator output and on every rejection path.
33. As a test author, I want reader tests to go through the reader's interface only, so that the readers can change internally without rewriting tests.
34. As a maintainer, I want no lenient pattern parsing a metric report left in active code, so that the next reader added has nothing lenient to copy.
35. As a maintainer, I want frozen code under `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/` left untouched, so that retained procedures keep running exactly as recorded.

## Implementation Decisions

- **One strict reader per report kind, in the concept that owns the evaluator.**
  - **Detection** keeps `parse_result` as its reader. It is extended with:
    - a committed breakdown-set constant, the 32 names the evaluator documents;
    - a known-diagnostics rule.
  - **Segmentation** gets a new strict reader beside the segmentation evaluator code.
  - **Motion** gets a new strict reader in the motion ingestion area, extracted from the strict pooled handoff check, which then uses it.
- **Known diagnostics.** The detection reader accepts stderr made only of:
  - the glog preamble line `WARNING: Logging before InitGoogleLogging() is written to STDERR`;
  - warning-level (`W`) glog lines whose source location and message match a committed list. On this host that is `iou.cc:172] Tiny box dim seen, return 0.0 IOU.` and `iou.cc:216] Huge box dim seen…`, each followed by its indented box dump.

  Any other stderr content rejects the report. The reader returns a count for each accepted diagnostic, and producers record those counts in `check.json`. The rule is a deliberate refinement, not a loosening: today the strict reader cannot read 49 retained real reports, while the lenient readers ignore stderr entirely.
- **The breakdown set** is a constant in the detection concept. The contract verifier's derivation from evaluator source comments becomes a test that the constant equals the documented set. That test runs only where the evaluator source exists, behind the existing live tags.
- **Zero ground-truth classes.** The plain scorer computes its mean over classes with positive ground-truth count, as today. This is now stated in `check.json` (`mean_scope: populated classes`), and an empty populated set raises. The sustained scorer keeps requiring all four classes.
- **Score record reader.** One function reads the per-class score record (`LEVEL2_per_class`, class key set, finite values in [0, 1]). It is used by:
  - the sustained admission, whose existing strict check becomes this function;
  - the sustained contract;
  - the evidence projection, where a missing record means not scored yet and a malformed record raises;
  - the fixed-batch verifier.
- **Retained evidence is not rewritten.**
  - New producers write correctly keyed `metrics` dictionaries.
  - Audits compare a strict re-read against same-generation `check.json` files only.
  - Old `check.json` files are historical (ADR 0001) and are not re-audited by the new code.
- **Ordering.** Ticket 01, the replay, gates every migration ticket. The sustained-path ticket changes balanced16's source snapshot, so blob-store ticket 12 is blocked by it and re-admits once for both changes.

## Testing Decisions

- **Good tests** exercise a reader only through its interface: report text or JSON in, a parsed result or a raised error out. They use retained real reports, copied into small fixtures, plus synthetic malformed variants for every rejection rule.
- **Modules tested:**
  - the three strict readers;
  - the score record reader;
  - the plain detection scorer's mean and empty-scope rules.
- **Producers** are tested only for wiring: that they call the reader. They are not tested for parsing.
- **Prior art:**
  - `native_detection_adapter_test` for the detection reader;
  - the pooled handoff check's refusal counting for motion;
  - `metrics_sustained_v3_test` for scorer wiring.
- **Every ticket** passes the default CPU suite, the `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...`, with counts recorded in the ticket.

## Out of Scope

- Frozen code: `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/`, including their own lenient readers.
- Rewriting or re-auditing retained `check.json` files.
- The proto-text export re-reading in the audit scripts. That is export parsing, not a metric report.
- `resources/legacy_values`, which compares glog headers byte-for-byte and reads no metric values.
- Changing any gate threshold.

## Further Notes

- The `\S+` mis-read affects only non-gate keys today, so no admitted gate result changes. The replay records how many retained `check.json` files carry mis-keyed range entries.
- The motion `.get('minAde', 0)` default flagged by the architecture survey matches proto3 JSON's omission of zero values (an oracle at offset 0 legitimately scores 0). The migration makes that rule explicit; it does not change values.
