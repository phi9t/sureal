# 10: `docs/` holds only repo-wide docs

**What to build:** A reader opening `docs/` finds only repo-wide material:
- ADRs, guides and agent docs;
- the research essays linked from the README (`3d-reconstruction-pathway.md`, `coherent-scene-hypotheses.md`,
  `repo-structure.md`);
- a dated `archive/`.

Concept-specific records live with the concept they describe. Ticket-numbered directories no longer sit beside
the design docs.

**Blocked by:** 08, 09 (they move the Insula and collaboration docs that this ticket would otherwise touch)

**Status:** ready-for-agent

Mapping (coordinator, 2026-10-11). Adjust a row only with a reason recorded in the commit:

| From | To | Why |
|---|---|---|
| `docs/research/` (parked Waymo research program records) | `autonomy/docs/research/` | autonomy program records |
| `docs/blob-store/`, `docs/launch-plans/`, `docs/strict-metrics/` | `autonomy/docs/<same>/` | autonomy ADR 0002/0003 subjects |
| `docs/ticket27/`, `docs/ticket29/`, `docs/refactor-finish/` | `autonomy/docs/archive/<name>/` | historical autonomy closeouts |
| `docs/superpowers/` (dated plans and specs) | `docs/archive/superpowers/` | repo-wide historical plans |
| `docs/collaboration/` | already moved by 09 | |

- [ ] `git mv` per the table. Every active reference is updated: README, AGENTS.md, CONTEXT files, guides,
  ADRs (consequence notes only), concept READMEs, code constants, and tests that read these paths. Bazel `data`
  globs must keep the same files.
- [ ] Records under the archive directories keep their bytes, even where their internal links now point at
  old paths. Each archive directory gets a one-paragraph `README.md` saying it is historical and naming the date
  of the move.
- [ ] `docs/README.md` indexes what remains in `docs/`.
- [ ] Live first: `./bazelw test //:repo_gate`, then `//autonomy/...` and `//parallax/...`.
