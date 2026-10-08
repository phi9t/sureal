# 05: Independent checkers declare their second implementations

**What to build:** Every active file that re-implements box math on purpose, to check a producer independently, says so in one line, so a future cleanup does not migrate the independence away. No behaviour changes. See `.scratch/box-geometry/spec.md` ("Independent checkers keep their copies").

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The evaluation proposal audits (one-batch and sustained v3) and the full ground-truth fixture's atan2 comparison each carry a one-line note that their box math is a deliberate independent implementation of the producer's
- [ ] `autonomy/ARCHITECTURE.md` gains one sentence stating the rule: producers use the geometry box module; independent checkers keep their own implementation
- [ ] No executable line in these files changes (verified by a diff limited to comments and docstrings)
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only) and `//parallax/...` pass with counts recorded
