# Lossless compressed sidecar publication

Goal: publish every decoded member of scene 4575389405178805994_4900_000_4920_000 under the unchanged 15 GiB aggregate cap. Exact uncompressed packing exceeds capacity by 57,630,774 bytes. No source subset or scientific cohort reduction is permitted.

Use a separately versioned deterministic gzip container around the existing canonical USTAR stream. Preserve the complete bundle.json bytes, sorted member order, canonical headers, uncompressed member sizes, hashes, and source provenance. Record compressed container SHA/bytes and uncompressed stream SHA/bytes separately. Use gzip mtime=0 and an empty filename. Count compressed output as it is written and refuse before crossing a precomputed output ceiling; a partial archive cannot authorize upload or eviction. This avoids materializing the uncompressed archive.

The current independent component validator opens r|, which does not accept gzip. Add a separate compressed validator, preserving the original pinned validator. It must hash the compressed container, stream decompression, enforce a bounded manifest and declared uncompressed member totals, independently verify every member, reject missing/duplicate/unsafe members and truncated/corrupted gzip, and verify uncompressed stream identity. No extraction or expanded archive file is allowed.

Verifiers: live Insula fixture comparing decompressed compressed output byte-for-byte with the original archive; deterministic repeat; insufficient output-cap refusal before any network call; corruption/truncation/undeclared member refusal; bounded resident usage. Actual publication requires live packing, HDFS upload/readback, separate independent live validation, manifest-last upload/readback, and retained runtime/code/source/resource receipts.

Compatibility gate: inspect every lifecycle admission, eviction, and later task consumer that reads component bundles. Require explicit compressed-format handling and provenance, never rename compressed bytes as an ordinary tar without a format declaration. Keep existing scientific task inputs and evaluation support unchanged. Existing semantic recovery inventory is for point archives and must remain pinned; do not silently repoint it at component bundles.

Acceptance: all native files and identities retained, actual aggregate working storage never exceeds 16,106,127,360 bytes, roundtrip independently verified, verified eviction followed by camera lifecycle and independent checkpoint admission. This is an implementation plan; no compressed actual-source publication has run.
