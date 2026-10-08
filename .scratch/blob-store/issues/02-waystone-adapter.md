# 02: Waystone adapter and store descriptors

**What to build:** Production code can store and fetch blobs in HDFS through Waystone by naming only blob keys; Waystone supplies the project root. A receipt's store descriptor rebuilds the right adapter, and receipts written before this change (absolute `hdfs://` URIs, prefix-style descriptors) still resolve to blob keys.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A Waystone adapter passes the contract suite from ticket 01; that run is tagged `requires_hdfs`, excluded by default, and is run once live against a scratch area with results recorded in the ticket
- [ ] The adapter resolves the project root from Waystone's layout profile; no storage root, cluster or user appears in sureal code
- [ ] The adapter verifies the pinned Waystone tool digests before each operation, kills the whole process group when a deadline passes, and classifies missing and authentication output into the failure kinds; no exit code or stderr text escapes
- [ ] Store descriptors are `{kind, project}` for Waystone and `{kind, root}` for local; one factory builds an adapter from a descriptor
- [ ] The factory accepts old prefix-style descriptors, and an old absolute URI is turned into a blob key by stripping Waystone's storage root
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded
