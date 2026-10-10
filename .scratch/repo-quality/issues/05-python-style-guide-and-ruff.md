# 05: Python style guide, ruff lint and format, and checker self-tests

**What to build:**

- **A written Python style guide:** `docs/guides/python-style.md`, adapted from the Google Python Style Guide in the way milano adapts its C++ and shell guides. It records sureal's deliberate differences, and it covers:
  - naming;
  - module layout;
  - imports;
  - error types;
  - typing;
  - docstrings and comments;
  - no minified one-liners in new or touched code;
  - tests next to the code they test.
- **Ruff as both linter and formatter**, run as `py_test`s in the repo gate. The rule set is chosen from a live run over the tree.
- **Pinned sources are excluded.** These are files whose exact hash a retained receipt or a current-candidate audit checks:
  - `HOST_SOURCE_REQUIRED`;
  - the source-snapshot targets;
  - every `candidate_hashes` / `source_pins` entry in retained receipts.

  The list is derived by `autonomy/retained_receipt_sweep.py`, not written by hand.
- **Formatting reaches other sources in batches** by concept directory. The receipt sweep's counts must stay unchanged after each batch.
- **Every existing boundary or audit checker has** a positive test, a negative test, and a "the real repo scans clean" test.

**Blocked by:** 02

**Status:** done

- [x] **Live first.** Run `ruff check` and `ruff format --check` over the tree. Record the counts by rule and by directory, and how many files are pinned. Choose the rule set and the line length from that run.
- [x] **The style guide is written**, and AGENTS.md's engineering rules point at it.
- [x] **Ruff comes from the rootfs or a pinned Bazel dependency**, not from host pip (ADR 0002). Its config lives in `pyproject.toml` or `ruff.toml`.
- [x] **The pinned-file exclusion list is generated from receipts.** A test fails if a pinned file is ever formatted, or if its hash changes.
- [x] **The first batch of unpinned directories is formatted**, with the retained-receipt sweep counts unchanged. The remaining directories are listed for follow-up batches.
- [x] **The checker self-test gaps are filled.**
- [x] **Gates pass**, with counts recorded.

## Comments

2026-10-10 Done.

- Live Ruff probe: ran Ruff 0.6.9 against the real tree before implementation. Broad `ruff check` over the tree with `E4,E7,E9,F,I`, line length 120 and Python 3.10 found 13,780 findings:
  - by rule: `E401=313`, `E402=288`, `E701=3135`, `E702=8772`, `E703=18`, `E712=1`, `E722=1`, `E731=46`, `E741=25`, `F401=187`, `F541=4`, `F601=1`, `F811=1`, `F821=13`, `F841=20`, `I001=955`.
  - by directory: `autonomy/studies=5037`, `autonomy/training_execution=1412`, `autonomy/detection=1175`, `autonomy/dataset=1129`, `autonomy/resources=1067`, `autonomy/segmentation=508`, `autonomy/geometry=485`, `autonomy/camera=427`, `autonomy/motion=401`, `autonomy/evaluation=390`, `autonomy/research=287`, `autonomy/retention=249`, `tests=225`, `autonomy/range_view=202`, `autonomy/evidence=200`, `autonomy/inspection=174`, `surflo=145`, `autonomy/insula=106`, `scripts=47`, `experiments=36`, `parallax/pipeline=26`, `parallax/tests=21`, `parallax/insulas=8`, `autonomy/blob_store=4`, `training=4`, `examples=3`, `autonomy/association=2`, `docs=2`, `submodules=2`, `.scratch/semantic-layout=1`, and one finding each in `autonomy/architecture.py`, `autonomy/retained_receipt_sweep.py`, `autonomy/retained_receipt_sweep_main.py`, `autonomy/retained_receipt_sweep_test.py`, `autonomy/source_snapshot_targets_test.py`.
  - broad `ruff format --check` reported 876 files would be reformatted and 86 already formatted.
- Config chosen from the live run: `pyproject.toml` sets Ruff line length 120, target Python 3.10, and lint rules `E9` plus `F821`. The active unpinned subset had zero findings for those rules.
- Ruff is Bazel-pinned with `http_archive` `@ruff_linux_x86_64` at Ruff 0.6.9, SHA-256 `ed8ba4cac0c6dfc1c0e9c6c720daa5ea404a3bff0497a95d6e25293a7910e903`. `//:repo_gate_ruff_test` invokes `@ruff_linux_x86_64//:ruff`.
- Pinned/protected source discovery is shared in `scripts/pinned_sources.py` and derives retained receipt fields from `autonomy/retained_receipt_sweep.py`. Final discovery summary: `tracked_python=759`, `excluded_python=408`, `ruff_check_scope=351`, `ruff_format_scope=7`, `receipt_pinned_path_count=267`, `protected_source_count=2776`.
- First format batch: formatted active unpinned sources in `autonomy/association/` and `autonomy/blob_store/`. Batch files were `autonomy/association/contract.py`, `autonomy/association/test_contract.py`, `autonomy/association/test_provenance.py`, `autonomy/blob_store/contract_test.py`, `autonomy/blob_store/core_test.py`, `autonomy/blob_store/storage_boundary_test.py`, and `autonomy/blob_store/waystone_test.py`; Ruff changed 6 files and left `autonomy/blob_store/core_test.py` already formatted. `autonomy/blob_store/core.py` was excluded because it is protected.
- Follow-up format batches: `autonomy/camera`, `autonomy/dataset`, `autonomy/detection`, `autonomy/evaluation`, `autonomy/evidence`, `autonomy/geometry`, `autonomy/inspection`, `autonomy/insula`, `autonomy/motion`, `autonomy/range_view`, `autonomy/resources`, `autonomy/retention`, `autonomy/segmentation`, `autonomy/training_execution`, `parallax/insulas`, `parallax/pipeline`, `parallax/tests`, and `scripts`, always excluding protected and frozen sources.
- Receipt safety:
  - Before formatting: `PYTHONPATH=autonomy python3 autonomy/retained_receipt_sweep.py --require-host-data` reported `2279/14/14/2/9`, zero failures and zero skips.
  - After formatting: same command reported `2279/14/14/2/9`, zero failures and zero skips.
  - PA live manifests at `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/pa-live/pa01-20261009T223117Z/receipt-manifest.json`, `pa02-20261009T232458Z`, `pa03-20261010T003448Z`, and `pa04-20261010T014108Z` verified with `--extra-receipt-manifest`: `2532/14/18/2/9` plus `fresh_live_receipt_validation=31`, zero failures and zero skips.
- Affected live/test entry points after formatting: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/association:all_tests //autonomy/blob_store:all_tests` passed 6/6.
- Gates:
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed 17/17 tests, invocation `5e6ea970-6453-4660-9489-7c9a07c6a17f`.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 189/189 tests, invocation `e1a978cf-f3d8-4c1d-8c15-76bc6acdc46e`. This ticket added no `//autonomy/...` BUILD targets, so the autonomy test-target count did not change due to this ticket.
  - `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 17/17 tests, invocation `4545c4e8-25a7-482b-823f-884bdfee2da2`.
  - GPU 1 check before CUDA: UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` had 4 MiB used and no compute process. `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 30/30 tests, invocation `dd316c37-551e-412e-b573-709cd48bcbe5`.
