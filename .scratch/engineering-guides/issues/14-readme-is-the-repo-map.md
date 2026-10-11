# 14: The README is the repo map, and AGENTS.md is the rules

**What to build:** A newcomer reads the README's project map and learns what every top-level directory is,
grouped by role:
- the research programs (`autonomy/`, `parallax/`);
- the repo harness (`harness/`);
- repo-wide docs (`docs/`);
- the inherited Surflo upstream tree (`surflo/`, `training/`, `configs/`, `scripts/`, `examples/`,
  `install/`, `media/`, `submodules/`).

`AGENTS.md` carries the rules and links the map rather than repeating it.

**Blocked by:** 10, 11, 12, 13

**Status:** ready-for-agent

Source: Milano commit `f7b4907` ("The README is the repo map and AGENTS.md is the rules").

- [ ] **README.** The "Project map" section lists every top-level directory once, grouped as above, with
  one line each.
- [ ] **ADR.** A new ADR, `docs/adr/0006-surflo-upstream-tree-keeps-its-layout.md`, records why the
  inherited tree stays at the root unchanged. Its paths are Surflo's documented interface, upstream merges stay
  mechanical, and the `surflo` package name is a compatibility boundary (`CONTRIBUTING.md`). It also records the
  rejected alternative of nesting the tree under `upstream/`.
- [ ] **Concept READMEs.** `docs/repo-structure.md` and ADR 0001 get a consequence note on the final top level.
  `CONTEXT-MAP.md` names a harness context if `harness/` grew domain terms.
- [ ] **Concept READMEs.** Every concept directory under `autonomy/`, `parallax/` and `harness/` has a short
  README in the subpackage shape (owns, boundaries, entry points). Fill the gaps; keep existing ones.
- [ ] **Gates.** `//:repo_gate` passes through `./bazelw`.
