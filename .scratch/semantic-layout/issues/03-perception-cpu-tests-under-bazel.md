# 03: Every perception CPU test runs under Bazel, in place

**What to build:** A contributor runs one wrapper command and every perception unit test that passes today passes as a Bazel target, with the source tree exactly where it is now. Tests that need torch or a live-gate mount are tagged and excluded from the default run, so a missing package or mount is never reported as a failure.

**Blocked by:** 02 (One wrapper command runs Bazel inside Insula)

**Status:** ready-for-agent

- [x] All 176 existing test modules are Bazel test targets
- [x] The default test run passes at least the 140 modules that pass in today's baseline (532 tests)
- [x] Modules needing torch are tagged for the GPU configuration; modules needing a live-gate mount are tagged and excluded by default
- [x] The two modules that fail today are recorded with their cause and are either fixed without changing pinned sources or tagged as known failures
- [x] No `.py` file is added, changed or removed in the directories whose inventory the sustained-run guard validates
- [x] The pin report shows no pinned file changed
