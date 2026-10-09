# 01: Pin rendered command lines and retained-receipt verification

**What to build:** A safety net for the rest of this feature.

- A golden characterisation test pins the exact rendered argv for every plan shape that runs today.
- A repeatable offline sweep runs every active receipt verifier over the retained receipts it covers and records the pass counts.

No behaviour changes.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] **Golden argv test.** A test renders representative plans and asserts byte-identical argv: CPU, GPU with driver pins, symlink rootfs entries, `/tmp` tmpfs with mounts under `/tmp/`, resource-wrapped, and a sustained stage.
  - The expected values are generated at the base commit and checked in.
  - The test uses fixtures, not host-specific paths, so it runs on any machine and in the hermetic Bazel sandbox.
- [ ] **Retained-receipt sweep.**
  - A script or test (manual or tagged, if it needs host data) runs the active verifiers offline over retained receipts. This includes the plan-record receipts from the balanced16 re-admission (`autonomy/research/balanced16-sustained-bs1220261009T154234Z-*`) and the legacy command-line receipts.
  - It prints per-verifier pass and fail counts.
  - It writes nothing into retained evidence.
- [ ] **Baseline counts** from the sweep are recorded in this ticket's comments.
- [ ] **Gates pass:** the CPU suite, `//parallax/...`, and CUDA on GPU 1 when it is free. Counts recorded.
