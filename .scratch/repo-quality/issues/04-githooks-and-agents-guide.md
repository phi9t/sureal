# 04: Versioned git hooks and a full AGENTS.md

**What to build:**
- A `.githooks/pre-commit` that runs `git diff --cached --check` and the identifier and storage scans as standalone static scripts. It imports no repo code, per ADR 0002.
- A one-line enable command.
- AGENTS.md gains milano-style sections: execution boundary, commands, cache rules ("run the retention planner's dry run and review it before any apply"), and engineering rules.

**Blocked by:** 01, 03

**Status:** ready-for-agent

- [ ] **Live first.** The hook runs for real on a commit that is clean and on one with a planted violation, in a scratch clone. It blocks the violation and allows the clean commit. Recorded.
- [ ] **The hooks are versioned under `.githooks/`.** `git config core.hooksPath .githooks` is documented, and a test checks that the hooks are executable and start with `#!/bin/bash`.
- [ ] **AGENTS.md** has these sections: execution boundary, commands, cache rules, engineering rules (pointing at the ADRs), and the issue tracker.
- [ ] **Gates pass**, with counts recorded.
