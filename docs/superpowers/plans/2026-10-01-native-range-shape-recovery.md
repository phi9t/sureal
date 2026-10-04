# Full scientific native range-image shape recovery

Status: source inventory prepared and verified live; execution pending.

Range-view input must preserve native H×W×4 dimensions, including empty edge
pixels. Positive-point pixel maxima cannot reconstruct dimensions. Original
scientific point archives omit dimensions; do not alter already pinned workers.

1. Admit all103 original source receipts and memberships using
   `scientific-native-range-shape-sources.candidate.json`. Live inventory verifier
   `scientific-native-shape-inventory-verified.json` proves source accounting only.
2. Wait for original processing, box replay and semantic recovery to be terminal.
   Hold shared whole-queue and raw-staging leases through each complete replay.
3. Recalculate retained raw bytes; stage one immutable HDFS LiDAR shard at a time,
   using original size/SHA256 and source integrity admission. Respect2GiB cap and
   cleanup only after native extraction and independent output admission.
4. In locked offline CPU Insula, read only native identity and both return-shape
   columns. Preserve null return shapes. Check source hashes, row/key inventory,
   duplicate/context/laser/frame keys, positive integer H/W and channel4. Do not
   decode or duplicate range payloads to infer shapes.
5. Independently reread native shape columns and compare every output identity and
   shape; check original reconstructed-point pixels against corresponding grids
   when admitting each scene for range encoding. Publish source/archive linkage,
   runtime/code/output identities and worker resources. Missing/changed/duplicate
   records refuse admission rather than shrinking the cohort.
6. Reconcile all103 scenes and203,850 expected native return records. Declare null
   shapes separately from present-empty returns. Only this full reconciliation can
   clear the scientific range-grid data gate.

Pinned serial readback totals17,382,154,779bytes; largest source204,311,418bytes.
These are candidate inventory quantities, not measured execution costs. No actual
scientific shape readback has started or been armed by this preparation.

Extractor preparation: `pipeline/native_range_shapes.py` admits complete native
row/key inventories, rejects duplicate/changed identities and malformed dimensions,
and preserves null shapes. Live red/green tests are retained under native-shape-tests
Insula outputs; `research/native-range-shape-extractor-verified.json` records two
passing groups with malformed/changed/duplicate/truncated-source mutations.
`research/native-shape-extractor-integration-verified.json` records exact agreement
with independently retained native metadata for both engineering scenes, all3,970
return records. Worker elapsed0.361s, peakRSS79,776KiB. Current code and receipt/output
hashes were checked. Initial inline-worker launch failed on string quoting; mounting
a read-only worker file resolved the launch, without changing source metadata.
Scientific HDFS staging, fresh independent reread and103-scene reconciliation remain
required; this extractor preparation does not clear the scientific gate.

Immutable source adapter preparation: `pipeline/native_range_shape_file.py`
checks declared size/SHA/MD5 before Parquet decoding, uses a single nonsymlink
regular-file descriptor for hashing and metadata reads, and checks file identity
before/after decoding. Only identity and shape columns are decoded. Live fixture
receipt `research/native-range-shape-file-verified.json` proves changed SHA/size/MD5
refusal before the decoder runs and symlink refusal. Native integration receipt
`research/native-shape-file-integration-verified.json` admits both original
engineering LiDAR sources and compares all3,970 shape records to retained
independent native metadata. These prepare the source consumer; real scientific
serial HDFS staging and whole-cohort independent replay remain pending.

Independent source reread preparation: `pipeline/native_range_shape_reference.py`
does not reuse either extraction adapter. It revalidates immutable source bytes,
rereads only native key/shape columns in different batches, compares each literal
record and null shape, and reconciles source key/order/count totals. Live fixtures
reject altered shape presence, dimensions, return identities, dropped records,
counts, key hashes and changed source bytes. Evidence:
`research/native-shape-reference-verified.json` and
`research/native-shape-reference-integration-verified.json`. Actual native reread
matches all3,970 engineering return records; outputs/receipts were rehashed.
Scientific full-cohort replay and independently admitted publication remain open.

Isolated consumer boundary: `pipeline.native_range_shape_worker` requires an
externally supplied job SHA before decoding its bounded trusted JSON. The job pins
scene, membership, source size/SHA/MD5 and native key inventory. It executes the
source adapter and independent literal reread, then publishes shape metadata with
its own RSS/elapsed resources and job identity. Existing output is never replaced;
changed job or invalid source produces no success report. Live fixture evidence
`research/native-shape-worker-verified.json` passes source/job refusal and successful
byte-admitted extraction/reread. This prepares the worker contract; native CLI
integration, host staging orchestration and whole103 scientific admission remain
pending. Job hash equality is not membership self-authorization: the host must
supply expectations from admitted original source/manifest identities.

Native CLI boundary verified: `research/native-shape-worker-cli-verified.json`
records the actual module CLI on one immutable retained engineering LiDAR source,
with externally pinned job JSON and a new output. A second offline Insula process
checks the job/output byte identities, membership declaration, full original shape
records, literal source reread and producer-owned resource fields. All1,980 return
records pass. Original slice manifest/reference receipt and current worker/adapter/
reference/source-integrity code are pinned; all retained artifacts were rehashed.
This clears the native CLI plumbing preparation only. No scientific HDFS source
was staged and no full103 shape replay or scientific gate was closed.

All103 original per-source worker jobs are prepared in
`research/native-shape-jobs.candidate.json`, each with an external SHA and source
receipt pin. Live inventory evidence `research/native-shape-job-inventory-verified.json`
checks exact full-set membership, original source size/SHA/MD5/key inventories,
HDFS identities, worker code pins and203,850 expected return records. These jobs
are metadata preparation; no scientific payload readback has started or been armed.

Complete staging rehearsal: `research/native-shape-staging-driver-fixture-verified.json`
records an immutable original engineering LiDAR shard transferred by a controlled
local-copy command through the existing bounded staging context. Both shared queue
and raw leases remain held through actual worker CLI and separate live Insula
source/output admission. Competing claims of each lease are refused. All1,980
records pass; recorded raw peak including declared retained engineering bytes is
1,376,387,494bytes, below2GiB. The temporary staged shard is removed only after
independent admission. Current source/worker/staging identities and all retained
artifacts were rehashed. This rehearses host orchestration but does not validate
real network transfer, arm scientific execution or admit any original103 shape
payloads. Production transfer deadline and full-cohort driver remain required.

Transfer deadline preparation: `pipeline/native_shape_transfer.py` wraps only an
owned Waystone `get`, with a600-second default deadline. It starts a private process
group, kills the owned group on timeout/interruption, and reaps the direct child;
success/nonzero status propagates. Live evidence
`research/native-shape-transfer-deadline-verified.json` verifies success, nonzero
exit, invalid deadlines and actual timeout kill/reap (direct PID disappears).
The wrapper is additive; active processing/staging modules are unchanged. This
prepares deadline enforcement, not a real HDFS transfer result or integrated
production driver admission. Full103 scientific execution remains pending.

Deadline/staging failure path now verified live in
`research/native-shape-staging-deadline-verified.json`: a real child creates a
partial stage and exceeds its deadline; no source is yielded, the stage directory
is removed, and raw/queue leases can be reacquired. Success admits exact bytes and
also removes staging after consumption. Existing staging code is unchanged. This
checks wrapper integration and resource ownership on fixture transfers, not real
HDFS readback or full scientific shape admission.

Reusable host driver: `pipeline/native_shape_source_replay.py` now holds the shared
queue lease, checks externally supplied source-receipt/job identities and matching
native source/membership inventories, verifies locked runtime content, and stages
one raw source under the raw lease. Production transfer defaults to the600-second
wrapper. Producer and separate independent consumer both run offline Insula with
300-second execution deadlines; source/job/current code pins are rechecked before
receipt publication and staging cleanup. Existing outputs are refused.

`research/native-shape-source-driver-fixture-verified.json` admits a full native
engineering source via controlled local-copy transfer:1,980 records, both successful
live workers, original byte identities, current code/artifact hashes and removed
staging. A competing queue claimant is refused before output creation. This proves
the reusable one-source orchestration; real production transfer and full103-source
execution/admission remain pending and unarmed.

2026-10-01 full103 continuation armed in .scratch/await-scientific-native-shapes.py. It pins original manifest, source inventory, all103 jobs/source receipts, all current pipeline files and separate retained auditor. It waits for semantic recovery2230074 to be authoritatively terminal and all22 inventoried scenes admitted, with original81 plus22 exactly covering103. Each real HDFS source runs the existing live producer/source-reference driver, then a third isolated retained-receipt/grid accounting audit before a progress pointer is published. The separate auditor is verified live against the real retained engineering receipt and11 rehashed contract/grid/key/return/count mutants (research/native-shape-retained-audit-tests-verified.json). Actual raw bytes are recounted from retained local slices before each transfer; raw2GiB and working15GiB caps preserved. Source-only dimensions do not close the separate reconstructed point/grid linkage gate. No scientific shape payload has yet been admitted by arming.

Original shape waiter2300693 terminated when semantic2230074 failed seventh admission. New shape v2 continuation2350750 waits on semantic2348064 and unchanged full22 gate; its stdout log is outside scientific-processing. Exact103 original source/job preflight passed again. This is a replacement of confirmed terminal wait ownership, not overlapping or restarted scientific payload execution.
