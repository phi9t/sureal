# 03: The balanced16 sustained scorer and metric audit read reports strictly

**What to build:** The sustained scorer and its metric audit, which both run on the balanced16 live path, read the detection metric report through the strict reader. The sustained scorer keeps requiring all four classes. This changes balanced16's source snapshot, so blob-store ticket 12 re-admits it once, covering this ticket together with the blob store migration.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The sustained scorer reads through the strict reader, records diagnostic counts, and still requires all four classes finite and in [0, 1]
- [ ] The sustained metric audit re-reads strictly and compares with the same-generation `check.json`
- [ ] The existing sustained scorer test still passes, extended for diagnostic counts and a rejected malformed report
- [ ] The ticket notes that blob-store ticket 12's re-admission covers this source-snapshot change; no balanced16 run happens here
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
