# 14: The README is the repo map, and AGENTS.md is the rules

**What to build:** A newcomer reads the README's project map and learns what every top-level directory is,
grouped by role:
- the research programs (`autonomy/`, `parallax/`);
- the repo harness (`harness/`);
- repo-wide docs (`docs/`);
- the inherited Surflo upstream component (`surflo/`, folded together by ticket 15).

`AGENTS.md` carries the rules and links the map rather than repeating it.

**Blocked by:** 10, 11, 12, 13, 15

**Status:** ready-for-agent

Source: Milano commit `f7b4907` ("The README is the repo map and AGENTS.md is the rules").

- [ ] **README.** The "Project map" section lists every top-level directory once, grouped as above, with
  one line each.
- [ ] **ADR.** A new ADR, `docs/adr/0006-four-top-level-components.md`, records the final top level:
  - the two research programs, the harness, and the inherited Surflo component;
  - why Surflo is one component, while its package name and import paths stay the compatibility boundary;
  - the rejected alternative of leaving the upstream tree loose at the root.
- [ ] **Concept READMEs.** `docs/repo-structure.md` and ADR 0001 get a consequence note on the final top level.
  `CONTEXT-MAP.md` names a harness context if `harness/` grew domain terms.
- [ ] **Concept READMEs.** Every concept directory under `autonomy/`, `parallax/` and `harness/` has a short
  README in the subpackage shape (owns, boundaries, entry points). Fill the gaps; keep existing ones.
- [ ] **Gates.** `//:repo_gate` passes through `./bazelw`.
