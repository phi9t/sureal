# 08: Scientific-directory and symlink-audit publishers on the blob store

**What to build:** Publishing a scientific directory and publishing a symlink audit go through the publication module or the blob store, so existence is never inferred from listing output.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Both publishers store through the publication module or the blob store; their bespoke Waystone client is gone
- [ ] No code parses "Found N items" or any listing output
- [ ] Their tests use an in-memory blob store instead of a fake Waystone
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
