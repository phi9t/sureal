# 09: Collaboration tooling moves into `harness/workflow/`

**What to build:** The multi-agent collaboration tooling lives in `harness/workflow/`, Milano's name for the
same concept: `scripts/collab.py`, `scripts/collab_live.py` and `scripts/_collab/`. `scripts/` then holds only
Surflo's inherited user entry points.

**Blocked by:** 06, 07

**Status:** ready-for-agent

- [ ] `git mv` into `harness/workflow/`. Drop the leading underscore if the package is no longer hidden behind
  a CLI wrapper. Imports follow the `harness/` import root.
- [ ] Every caller is updated: `.kata.toml`, `.githooks/`, docs, `AGENTS.md`, `docs/collaboration/`, and tests.
- [ ] `harness/workflow/README.md` in the subpackage README shape. `harness/README.md` maps it.
- [ ] `scripts/README.md` (or the README project map) says that `scripts/` is Surflo's user entry points only.
- [ ] Live first: run the collab CLI's own smoke or tests, then `./bazelw test //:repo_gate`.
