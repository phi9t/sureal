# 07: Retention publishers and resource bundles on launch plans

**What to build:** The retention publishers and the resource-bundle runner launch through launch plans. The resource bundle's swap of the root mount for read-only per-entry mounts is a plan option checked by the same lock and overlap rules.

**Blocked by:** 01, blob-store 11 (the blob-store migration rewrites these files)

**Status:** ready-for-agent

- [ ] The root-mount swap is a launch-plan option, with offline tests
- [ ] `resources/retention.py` and whatever retention publishing remains after blob-store 11 (the publication module and `retention/publish_scientific_directory.py`) build launch plans. No command-line splicing or hand-parsed lock remains
- [ ] Tests assert on plans, not command-line slices
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
