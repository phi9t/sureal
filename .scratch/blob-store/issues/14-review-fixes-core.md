# 14: Review fixes for blob-store core

**What to build:** Close the coordinator review findings in the blob-store core and its in-scope callers without weakening retained evidence verification.

**Status:** done

- [x] Route Waystone layout failures through blob-store retry/classification and keep legacy HDFS URI-to-key translation offline.
- [x] Use the strict legacy URI translator for old HDFS receipts.
- [x] Enforce expected byte counts through blob downloads that publish or consume receipt size fields.
- [x] Pass receipt byte counts through source snapshot and native-shape fetch paths while preserving typed blob-store errors.
- [x] Cross-check publication archive blob identity before eviction deletes local payloads.
- [x] Make receipt classifiers shape-specific and require descriptor, tool digest and readback evidence for new journal publication records.
- [x] Remove dead/duplicated blob-store plumbing where in scope and centralize the default Waystone descriptor/publication helpers.
- [x] Tighten storage-boundary scanning for new direct Waystone/HDFS access while preserving exact retained procedure records.

## Comments

Done: added red tests for all 8 review findings before implementation; the focused run failed 12/12 on the review cases before the fixes landed. After implementation, focused regression passed 12/12 tests, the widened core/caller set passed 18/18 tests, `//autonomy/...` passed 186/186, `//parallax/...` passed 17/17, and the GPU-1 CUDA autonomy gate passed 30/30.
