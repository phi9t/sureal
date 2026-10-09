# 02: One repo gate

**What to build:** A single Bazel target, run inside Insula, that runs every static quality check:
- every `*_boundary_test`;
- `storage_boundary_test`;
- the launch-plan boundary test;
- `scripts/publication_audit.py`, which today runs only in GitHub CI;
- whitespace checking (`git diff --check` style) over tracked files.

AGENTS.md names it as the command to run before landing.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] **Live first.** The gate runs for real on mainline. Its output, duration and any findings are recorded. Real findings are fixed or listed, never hidden.
- [ ] **One target** (for example `//:repo_gate` or `//autonomy:repo_gate`) aggregates the static checks. Live-gate and GPU checks are excluded.
- [ ] **`publication_audit.py` runs under Bazel inside the gate.** The CI workflow calls the same target or the same script.
- [ ] **Self-tests:** a test proves the gate's membership. A new `*_boundary_test` that isn't in the gate fails it.
- [ ] **AGENTS.md** gains a "Commands" section: the gate, the CPU, CUDA and parallax suites, and the Insula boundary.
- [ ] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.
