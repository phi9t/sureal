# 05: Independent checkers declare their second implementations

**What to build:** Every active file that re-implements box math on purpose, to check a producer independently, says so in one line, so a future cleanup does not migrate the independence away. No behaviour changes. See `.scratch/box-geometry/spec.md` ("Independent checkers keep their copies").

**Blocked by:** 01

**Status:** done

- [x] The evaluation proposal audits (one-batch and sustained v3) and the full ground-truth fixture's atan2 comparison each carry a one-line note that their box math is a deliberate independent implementation of the producer's
- [x] `autonomy/ARCHITECTURE.md` gains one sentence stating the rule: producers use the geometry box module; independent checkers keep their own implementation
- [x] No executable line in these files changes (verified by a diff limited to comments and docstrings)
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09: Added deliberate independent-checker notes to `autonomy/evaluation/audit_proposals.py`, `autonomy/evaluation/audit_proposals_sustained_v3.py`, the header of `autonomy/evaluation/audit_metrics_sustained_v3.py`, and `autonomy/training_execution/full_groundtruth_fixture.py`; added the oriented-box producer/checker rule sentence to `autonomy/ARCHITECTURE.md`. Verified the diff is limited to comments/docstrings plus the one architecture sentence with `git diff --check` and diff review.

Gate counts:

- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 167/167 pass.
- `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 pass.
- `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 28/28 pass; GPU 1 was idle before the run.
