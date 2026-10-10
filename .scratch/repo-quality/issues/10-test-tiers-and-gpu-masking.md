# 10: Written test tiers; masked GPU tests fail instead of skipping

**What to build:** The test tags and suffixes are documented, and a CUDA test run with no visible GPU fails loudly instead of skipping.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Decision, from the coordinator under user delegation on 2026-10-10: under `--config=cuda`, a test tagged `requires_gpu` fails when no GPU is visible.

Source: `../research/milano-conventions.md`, test tiers.

- [ ] **ADR.** The ADR, plus a section in AGENTS.md, defines:
  - the tags `requires_gpu`, `requires_live_gate` and `known_failure`;
  - the suffixes `_live_test` and `_host_test`;
  - which gate runs which tier.
- [ ] **Masked-GPU check.** `--config=cuda` sets a test environment flag. GPU tests assert that a device is visible when the flag is set, and fail with a clear message otherwise. Default CPU runs are unaffected.
- [ ] **Regression test.** Running the CUDA config with the device masked makes a GPU test fail.
- [ ] **Gates:** `//:repo_gate`, `//autonomy/...`, and CUDA on GPU 1 when it is free.
