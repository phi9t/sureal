# 03: Source snapshots through the blob store

**What to build:** Every gate and study stage stores and fetches its source snapshot through the blob store, content-addressed under `artifacts/source-snapshots/<sha256>`, so the most critical evidence path gains the store's deadlines, retries and typed failures. Existing receipts keep resolving.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Snapshot creation stores the archive through the blob store and new receipts carry the new store descriptor and blob key
- [ ] The existing local snapshot store is replaced by the blob store's local adapter; offline tests inject an in-memory or local store, never a fake command runner
- [ ] Every caller that rebuilt a store from a receipt uses the descriptor factory; receipts written before this change still resolve and verify (proved by a test over at least one retained receipt of each schema)
- [ ] The snapshot store no longer calls the Waystone tool directly
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded; the `requires_hdfs` contract suite passes once
