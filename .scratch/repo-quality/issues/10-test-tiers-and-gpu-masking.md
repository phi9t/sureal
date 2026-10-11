# 10: Written test tiers; masked GPU tests fail instead of skipping

**What to build:** The test tags and suffixes are documented, and a CUDA test run with no visible GPU fails loudly instead of skipping.

**Blocked by:** None (can start immediately)

**Status:** done

Decision, from the coordinator under user delegation on 2026-10-10: under `--config=cuda`, a test tagged `requires_gpu` fails when no GPU is visible.

Source: `../research/milano-conventions.md`, test tiers.

- [ ] **ADR.** The ADR, plus a section in AGENTS.md, defines:
  - the tags `requires_gpu`, `requires_live_gate` and `known_failure`;
  - the suffixes `_live_test` and `_host_test`;
  - which gate runs which tier.
- [x] **Masked-GPU check.** `--config=cuda` sets a test environment flag. GPU tests assert that a device is visible when the flag is set, and fail with a clear message otherwise. Default CPU runs are unaffected.
- [x] **Regression test.** Running the CUDA config with the device masked makes a GPU test fail.
- [x] **Gates:** `//:repo_gate`, `//autonomy/...`, and CUDA on GPU 1 when it is free.

## Comments

- 2026-10-10 Worker evidence:
  - Added `docs/adr/0003-test-tiers-and-gpu-masking.md`, which defines the `requires_gpu`, `requires_live_gate`, and `known_failure` tags; the `_live_test.py` and `_host_test.py` suffixes; and the static, CPU autonomy, Parallax, and CUDA gate commands. The AGENTS.md section is still missing because this worker run's hard allowlist did not permit editing root `AGENTS.md`.
  - Implemented CUDA-tier fail-not-skip behavior in `autonomy/insula/bazel_launcher.py`: `--config=cuda` sets `SUREAL_REQUIRE_GPU=1` in Bazel's test environment. Missing GPU device files under `--config=cuda` no longer stop before Bazel starts; invalid GPU overrides and driver errors still fail in wrapper planning.
  - Added `autonomy/insula/gpu_visibility.py`, `autonomy/insula/gpu_visibility_test.py`, and `autonomy/insula/gpu_visibility_guard_test.py`. The shared guard is a no-op when `SUREAL_REQUIRE_GPU` is unset and raises `AssertionError: SUREAL_REQUIRE_GPU=1 requires one visible CUDA device; found 0` when the requested CUDA tier sees no device.
  - Wired the guard into the live GPU tests `autonomy/insula/launch_plan_gpu_live_test.py` and `autonomy/training_execution/sustained_launch_plan_gpu_smoke_test.py`, and tagged `//autonomy/insula:gpu_visibility_guard_test` with `requires_gpu` so a masked CUDA config has a small regression target.
  - Live source-pin check before edits: `TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/repo10-test-tiers-and-gpu-ma-20261011T002235Z/tmp/prelive-pins.XXXXXX ./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test` passed 1/1 test, invocation `76d44f76-2496-491e-8b03-66117d0e738f`, elapsed 11.693s.
  - Live masked-CUDA check before the fix: `CUDA_VISIBLE_DEVICES= TMPDIR=~/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/repo10-test-tiers-and-gpu-ma-20261011T002235Z/tmp/prelive-masked-cuda.XXXXXX ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:launch_plan_gpu_live_test` exited 1 before Bazel test execution with `insula.launch_plan.PlanError: GPU device not found: /dev/nvidia1`; 0 test targets executed.
  - Red test evidence: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:bazel_wrapper_test //autonomy/insula:gpu_visibility_test` failed 2/2 before implementation. `gpu_visibility_test` could not import the missing helper, and `bazel_wrapper_test` showed the emitted Bazel command lacked `--test_env=SUREAL_REQUIRE_GPU=1`.
  - Focused post-fix check: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:bazel_wrapper_test //autonomy/insula:gpu_visibility_test` passed 2/2 tests, invocation `0a2ee790-50b8-4948-a694-c49fcb13f986`, elapsed 20.175s.
  - Masked-CUDA regression after the fix: `CUDA_VISIBLE_DEVICES= ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/insula:gpu_visibility_guard_test` failed 1/1 test as expected, invocation `c6278140-be2c-4c55-b436-f9b0e386af70`, elapsed 3.795s, with `AssertionError: SUREAL_REQUIRE_GPU=1 requires one visible CUDA device; found 0`.
  - Final repo gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate` passed 19/19 tests, invocation `1b7edf41-c113-4858-afb8-9ad492b4b1f2`, elapsed 78.652s. This included `//:pinned_sources_test` passing.
  - Final CPU autonomy gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed 190/190 tests, invocation `ee743511-d42e-4142-a1d7-090ce0f86b4b`, elapsed 92.128s.
  - Final Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed 20/20 tests, invocation `23e5c317-316b-4694-a652-f85ee816f5c4`, elapsed 391.341s.
  - Full CUDA autonomy gate intentionally skipped for this worker run per coordinator instruction: this sandbox has no GPU devices, no GPU use was allowed, and the coordinator runs CUDA.
  - SHA256 digests of committed implementation/policy files: `docs/adr/0003-test-tiers-and-gpu-masking.md` `2bc15132f221522e4876d9f4686d00629c34489c7b715bef28ad5e6efd930081`; `autonomy/insula/gpu_visibility.py` `e5a576d8d1b582899071cdf7026eb4b8f16f660584dce18807cff7c37f46a6f7`; `autonomy/insula/gpu_visibility_test.py` `2ae5bd1494f9f94f573045f90fa2272a0a83d0996d69d9b212df2f1f5f52f038`; `autonomy/insula/gpu_visibility_guard_test.py` `9feff9c4899ddffeb5d0ecaf1e38327c407675b7f2806eced683e6137dd43fef`; `autonomy/insula/bazel_launcher.py` `1cf9ffaa9763325d80f5c6c217c01fb983f04308291453c79b8dae09078c7bde`; `autonomy/insula/BUILD.bazel` `93a1df73ef982ad32dd917bc438d95f78b164279ca6fce4d1417b03ad6ed6107`; `autonomy/insula/bazel_wrapper_test.py` `d70c98d5ede44e5ca7c5631140ead661ac14035968a98c6a57ee1c92360b21c7`; `autonomy/insula/launch_plan_gpu_live_test.py` `884d76d893e843bf3da45461c1b3b7646febe27b6edbd7373f5b92a224e19e91`; `autonomy/training_execution/sustained_launch_plan_gpu_smoke_test.py` `d5e094d6efdc6971863bcac67a1303e49a4b4491587ff4ff71a7563fc4d9586c`.
  - Focused test-log SHA256 digests: `autonomy/insula:bazel_wrapper_test` `eb67526da0e61c0a52292d8ca1eccbfec358578405054a29e90a8bdc2d1391cd`; `autonomy/insula:gpu_visibility_test` `69fb411bb2f5b3b0800bd88d12cc467810b41d359b3d5650bd2e59cd47bd76ba`; `autonomy/insula:gpu_visibility_guard_test` masked CUDA log `a63997d69cf84fb060e057dfdf9fc2e17491f23fa0e0587a37d9e0d694658358`.
  - Missing before `**Status:** done`: root `AGENTS.md` still needs the test-tier section defining the same tags, suffixes, and gate mapping. This worker could not edit that path under the hard allowlist.

### 2026-10-11 coordinator

- **ADR renumbered** to `docs/adr/0004-test-tiers-and-gpu-masking.md`, because `0003` was already taken by repo-quality 09's shell ADR. The digests above refer to the 0003 path at the worker commit.
- **AGENTS.md** gains a "Test tiers" section. It was outside the worker's allowlist.
- **Gates** are recorded in the landing commit's verification run, which includes CUDA on GPU 1.
