# 07: Native-cache and pilot specs; retire the old retention publishers

**What to build:** The last two retention publication cases are specs, and the three copied publisher, sources and audit triples leave the active code.

**Blocked by:** 05

**Status:** done

- [x] Native cache and sustained pilot are publication specs
- [x] The three old publisher modules, their per-case sources modules and their old-shape audits, and the old resource retention audit, move to procedure records; nothing active imports them
- [x] Every retained receipt they produced still verifies through its source snapshot (not the working tree)
- [x] Default CPU suite, `--config=cuda` suite and `//parallax/...` pass with counts recorded

## Comments

Done 2026-10-09:
- Added archive-mode copy-staged publication specs for native cache and sustained pilot on the shared `publish(spec) -> receipt` / `audit(receipt)` path.
- Retired the old native-cache, sustained-checkpoint, sustained-pilot and resource-retention publisher/source/audit code from active modules by preserving the old bytes under `autonomy/studies/balanced16/procedure_records/legacy_*.py`.
- Consolidated active publisher source snapshots in `retention.publication_sources`; retained legacy source receipts still verify through their recorded source snapshots rather than the working tree.
- Updated sustained resource publication tests to use blob publication receipts through an in-memory blob store; no live native-cache or sustained-pilot publication run was performed, and no HDFS writes were performed.
- Verification:
  - Focused publication/source/resource slice: 5/5 tests passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 183/183 tests passed.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`: 17/17 tests passed.
  - GPU 1 was free by `nvidia-smi` (4 MiB used, no compute app on GPU 1 UUID), then `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`: 29/29 tests passed.
