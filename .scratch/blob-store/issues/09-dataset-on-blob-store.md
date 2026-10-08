# 09: Dataset scripts on the blob store

**What to build:** Cohort acquisition, scene and sidecar publishing, and staged-source fetching in the dataset concept store and fetch through the blob store under the `datasets/` area.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] No dataset module builds a Waystone command line
- [ ] New blob keys use the `datasets/` area; fetches of previously published data resolve old URIs through the descriptor factory
- [ ] Tests use an in-memory blob store where they previously faked commands
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
