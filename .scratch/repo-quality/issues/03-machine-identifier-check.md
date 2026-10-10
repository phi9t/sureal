# 03: Machine-identifier boundary test

**What to build:** A boundary test, ported from milano's `scripts/check_identifiers.py`, that fails when an active tracked file contains any of:
- a host name;
- a `/dataNN/` path;
- a `/home/<user>/` path;
- an e-mail address outside the allowed attribution.

Retained records are exempt under ADR 0001, through the same exemption style as `storage_boundary_test`. Existing hits go into an explicit baseline allowlist that may only shrink.

**Blocked by:** 02

**Status:** done

- [x] **Live first.** The scan runs over the real tree. The hit counts by kind and by directory are recorded, and each class of hit is triaged as: fix now, retained or exempt, or baselined.
- [x] **The test** uses milano's pattern-splitting trick so that it doesn't match itself, and it is part of the repo gate.
- [x] **Baseline:** an allowlist file with a reason for each entry. A test fails if a baselined entry no longer exists, which keeps the baseline shrinking.
- [x] **Self-tests:** positive, negative, and the real repo scanning clean against the baseline.
- [x] **Gates pass**, with counts recorded.

## Comments

### 2026-10-10 Done

Implemented `scripts/check_identifiers.py`, `scripts/check_identifiers_test.py`,
`scripts/check_identifiers_baseline.json`, and added `//:check_identifiers_test`
to `REPO_GATE_TESTS` in `BUILD.bazel`.

Live validation came first. A first unrestricted tracked-file probe was stopped
because it scanned large retained evidence too slowly. The policy-shaped live
scan then covered tracked UTF-8 files and exempted retained evidence/frozen
procedure records:

```text
python3 scripts/check_identifiers.py --no-baseline --json
exit=1
scanned_text_files=2038
skipped_binary_files=22
skipped_retained_files=3134
total_hits=4961
hit_counts_by_kind={'email address': 43, 'host data path': 2460, 'user home path': 2458}
hit_counts_by_top_directory={'.scratch': 438, 'LICENSE.md': 1, 'THIRD_PARTY_NOTICES.md': 1, 'autonomy': 16, 'docs': 4467, 'submodules': 31, 'surflo': 3, 'tests': 4}
```

Triage:
- Fix now: four initial e-mail false positives from Python matrix-multiply
  expressions; fixed by scanning Python e-mail candidates only in strings and
  comments. No active source leak remained outside intentional/synthetic or
  legacy buckets.
- Retained or exempt: 3134 retained evidence/frozen-procedure files were
  skipped by policy.
- Baselined: 174 path/kind entries covering 4961 existing legacy, fixture,
  upstream attribution, or host-environment sentinel hits. Each entry has a
  reason; a stale entry fails the test so the baseline can only shrink.

Post-baseline live run:

```text
python3 scripts/check_identifiers.py --json
exit=0
scanned_text_files=2041
skipped_binary_files=22
skipped_retained_files=3134
total_hits=4961
unexpected_hits=0
stale_baseline_entries=0
```

Focused checks:

```text
python3 -m unittest scripts.check_identifiers_test -v
Ran 7 tests in 2.957s
OK

./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:check_identifiers_test
Executed 1 out of 1 test: 1 test passes.
```

Gate evidence:

```text
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate
Executed 8 out of 8 tests: 8 tests pass.

./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
Executed 189 out of 189 tests: 189 tests pass.
```

The `//autonomy/...` count is unchanged from base `022e197`: this ticket only
adds root `scripts` tests and `BUILD.bazel` repo-gate membership, not autonomy
targets.

```text
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...
Executed 17 out of 17 tests: 17 tests pass.
```

GPU 1 availability was checked before CUDA: the required UUID had no compute
process and memory used was below 1024 MiB. CUDA gate:

```text
CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
Executed 30 out of 30 tests: 30 tests pass.
```

Shared-file overlap: `BUILD.bazel` only, limited to adding the new root
identifier test to the existing repo gate.
