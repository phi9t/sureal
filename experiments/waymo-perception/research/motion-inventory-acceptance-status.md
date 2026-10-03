# Current Motion source inventory admission

[Live aggregate evidence](motion-inventory-acceptance-live-verified.json) reconciles all 1,000 training and 150 validation Scenario metadata objects. Authenticated listings reach terminal pagination; unique object names, generations, sizes and checksum presence match the recorded totals. The acquired source in each split is the first lexicographic object and exactly matches its inventory metadata. Both source receipts establish exact HDFS readback.

The two independent full-source inventories reconcile **492 training + 287 validation = 779 records**. Every record index, offset and payload length agrees between the CRC reader and native protobuf inventory, and cumulative framing bytes reach the exact acquired source size. The selected lowest lexicographic native scenario ID agrees with its record, payload hash and reconciliation receipt. Current index10, 91 timestamps and native target counts2/8 are preserved. Five altered aggregate copies are rejected: offset, payload length, selected hash, incomplete pagination and selected identity.

This admission checks retained native inventories and selected payload identities inside locked CPU Insula. It does not reread both raw shards, reparse every protobuf, validate all sensor geometry, freeze a scientific cohort, or close ticket19. Existing raw/framing/native receipts and authorized HDFS eviction/recovery remain separately required.

**Review correction:** the first invocation printed781 despite correctly storing492/287. The success total now derives from verified split counts; the fresh second invocation prints779. The initial source/log/receipt remain retained under `insula/motion-inventory-acceptance-20261003a`; invocationb is current. Earlier summary prose stating781 is incorrect and must not be used as a denominator.

Replay the exact bubblewrap command in the receipt against its retained, hash-pinned input.json and `motion-evaluation/ingestion/inventory_acceptance_fixture.py`, with a fresh output directory. Required assertions, runtime identity, source/input hashes, output hashes and resource measurements are recorded. Full aggregate ticket19 acceptance remains open.
