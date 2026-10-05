# 06: Rename the curriculum to `parallax/`

**What to build:** The 3D reconstruction curriculum lives at top-level `parallax/`, with its pipeline, Insula definitions, tests and research directly beneath it. Its runner, tests, CI job and the publication audit all work from the new location.

**Blocked by:** 05 (The curriculum's tests run under Bazel, in place)

**Status:** ready-for-agent

- [ ] The move is one commit containing only renames, so history follows every file
- [ ] A following commit updates the paths that code, the publication audit and its test, and CI depend on
- [ ] The curriculum's Bazel tests pass at the new location and its runner lists and runs a smoke module
- [ ] The publication audit and its unit test pass
- [ ] Files under the curriculum's `research/` are byte-identical
- [ ] The wrapper selects the curriculum rootfs for `//parallax/...` targets, and a target pattern that spans both components (for example `//...`) either runs each component in its own rootfs or is refused with a clear message; it must not silently run curriculum tests in the perception rootfs
- [ ] The curriculum runner script's import bootstrap (added in ticket 05 for Bazel's safe-path mode) is simplified to setting the import path, with the Bazel tests still passing
