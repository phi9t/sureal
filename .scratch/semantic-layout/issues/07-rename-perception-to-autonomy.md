# 07: Rename the perception program to `autonomy/`

**What to build:** The perception research program lives at top-level `autonomy/`, moved whole. Everything that ran before the move runs after it: the Bazel tests, the architecture experiment catalog, the tracker and journal, the publication audit and CI. The internal structure is not changed in this ticket.

**Blocked by:** 03 (Every perception CPU test runs under Bazel, in place), 04 (Torch tests run under Bazel in the GPU rootfs)

**Status:** ready-for-agent

- [ ] The move is one commit containing only renames
- [ ] A following commit updates every hard-coded occurrence of the old path in code: the architecture harness drivers, the gate scripts still in use, the rootfs build script, the publication audit and its test, the collaboration tests and CI
- [ ] Sandbox mount points inside the rootfs are unchanged
- [ ] The default Bazel run passes the same modules as before the move, and the GPU configuration runs the same torch modules
- [ ] The architecture runner lists and shows experiments from the new location; the journal's hash chain verifies
- [ ] The context map points at the glossary's new location and the perception ADR has moved with the tree
- [ ] Files under `research/` are byte-identical, and the pin report for the content-editing commit is attached to the ticket
