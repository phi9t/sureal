# 01: Concept packages, with no behaviour change

**What to build:** Parallax reorganised into the approved concept layout (see `../spec.md`). Every command, report and test behaves exactly as before.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] **Moves.**
  - `math3d.py` → `camera/pinhole.py`, `camera/pose.py`, `geometry/triangulate.py` and `geometry/align.py`, with `fuse_tsdf` going to `fusion/tsdf.py`.
  - `reference_scene.py` → `scene/`.
  - `*_reference_runner.py` → `baselines/`.
  - `labs.py` and `curriculum.json` → `curriculum/`.
  - The lock and registry JSON files → `assets/`.
  - `*.schema.json` → `schemas/`.
  - `pipeline/` keeps only the orchestration code.
- [ ] Old import paths and file paths that callers, `run.sh`, BUILD targets or docs use keep working through thin re-export shims, or are updated in the same change. Nothing pinned by retained evidence is edited.
- [ ] Tests move from `parallax/tests/` to sit beside the code as `*_test.py`, import through the package root, and edit no `sys.path`. The Parallax entries in the import-checker baseline are removed.
- [ ] `parallax/BUILD.bazel` (or per-package BUILD files) gives each concept a `py_library`, and each test a `py_test`, so that `//parallax/...` still runs every test that ran before.
- [ ] **Live check, run first.** `run.sh list`, `all --profile smoke --fixture-only`, `validate` and `report`, run before and after the change inside the Parallax Insula. The report JSON is byte-identical apart from timestamps and run ids. Record the commands and diffs.
- [ ] `parallax/README.md` describes the new layout. `docs/repo-structure.md` is updated if it maps Parallax.
- [ ] **Gates:**
  - `//:repo_gate`;
  - `//parallax/...`, where the test count may change only by moves, with no tests lost;
  - `//autonomy/...`.
