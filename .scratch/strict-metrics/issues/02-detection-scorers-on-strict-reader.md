# 02: Detection scoring and audits read reports strictly

**What to build:** These now read their detection metric report through the strict reader and record the diagnostic counts:
- the plain detection scorer;
- its metric audit;
- the real-export check.

`check.json` gains correctly keyed range breakdowns. The plain scorer states its mean scope and raises on an empty populated set. It also gains tests, which it has never had.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The plain scorer reads through the strict reader with the committed breakdown set, records the accepted diagnostic counts, records `mean_scope`, and raises when no class is populated
- [ ] The metric audit re-reads the report strictly and compares it with a same-generation `check.json`; the lenient pattern is gone
- [ ] The real-export check reads the whole report strictly instead of searching for one line
- [ ] New tests cover the plain scorer's wiring, mean rule and empty-scope error through its interface
- [ ] No lenient detection-report pattern remains in active code outside the sustained path (ticket 03) and frozen code
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
