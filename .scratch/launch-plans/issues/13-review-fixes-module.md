# 13: Review fixes for the launch-plan module

**What to build:** Fix the coordinator review findings in the launch-plan module and its receipt readers without weakening retained evidence checks.

**Status:** done

- [x] Old command-line receipts with duplicate inside mounts read with bwrap last-mount-wins semantics, retained bwrap receipts scan cleanly read-only, and new plan records still reject duplicate inside mounts.
- [x] Architecture experiment receipt verification prefers command-form rows when present and verifies plan-form rows through recorded digests instead of host paths.
- [x] Plan records carry and require clean-environment facts, and GPU plans record/verify requested device minor and UUID while rejecting overrides that omit the requested GPU.
- [x] The Bazel launcher uses a public validated launch-plan module call instead of private helpers, and rendered plans never emit the same inside path twice.
- [x] The boundary scanner flags quoted bwrap option splicing, unquoted shell bwrap calls, and private launch-plan imports outside `insula/`, with planted-file coverage for each pattern.
- [x] `with_mounts` preserves launch-plan recording options, old receipt reads default away from digest hashing, record/render order is consistent, and unused unchecked runtime code is gone.

## Comments

Done. Added red-first coverage for the six review findings, including a retained read-only bwrap receipt scan that covered 2109 retained command rows; before the fix, base failed 4 rows on duplicate legacy mounts. The final gates passed: focused Python 69/69, focused Bazel 4/4, `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` 185/185, `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` 17/17, and GPU 1 CUDA gate `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` 30/30 after confirming GPU 1 UUID `GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619` had 4 MiB used and no compute process on that UUID. No findings were left for sibling workers from this module slice.
