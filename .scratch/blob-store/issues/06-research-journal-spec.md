# 06: Research-journal publication spec

**What to build:** Publishing the research journal, registry, dashboard and evidence snapshots is a direct-files publication spec, so it gains the blob store's deadlines, retries and failure kinds. The evidence concept keeps the journal itself (append, verify) and no longer publishes it.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The journal publication is a spec in direct mode (files stored as blobs, no archive, no release) under the `runs/` area
- [ ] Its receipt replaces the journal's HDFS verification record and verifies by readback; the previous record's bytes are preserved before the first publish under the new spec
- [ ] The evidence concept no longer calls the Waystone tool or the publication module; dependencies point downward
- [ ] Journal verification still passes on the current journal
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
