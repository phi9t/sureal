# 06: Rename the curriculum to `parallax/`

**What to build:** The 3D reconstruction curriculum lives at top-level `parallax/`, with its pipeline, Insula definitions, tests and research directly beneath it. Its runner, tests, CI job and the publication audit all work from the new location.

**Blocked by:** 05 (The curriculum's tests run under Bazel, in place)

**Status:** ready-for-agent

- [ ] The move is one commit containing only renames, so history follows every file
- [ ] A following commit updates the paths that code, the publication audit and its test, and CI depend on
- [ ] The curriculum's Bazel tests pass at the new location and its runner lists and runs a smoke module
- [ ] The publication audit and its unit test pass
- [ ] Files under the curriculum's `research/` are byte-identical
