# 11: Delete the old Waystone wrappers

**What to build:** The working tree holds one way to store a blob. A test enforces it.

**Blocked by:** 03, 05, 06, 07, 08, 09, 10

**Status:** ready-for-agent

- [ ] Every remaining Waystone wrapper, copied tool-pin block and storage-root constant outside the blob store is deleted (the HDFS login keepalive is the only other Waystone user and stays)
- [ ] A test fails if active code outside the blob store and the keepalive invokes the Waystone tool or names the storage root
- [ ] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded; the `requires_hdfs` contract suite passes once
