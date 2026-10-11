# 15: The inherited Surflo tree folds into one `surflo/` component

**What to build:** Everything inherited from upstream Surflo lives under one top-level component, `surflo/`,
next to `autonomy/`, `parallax/` and `harness/`. A reader sees four components at the root, not a dozen loose
upstream directories.

**Blocked by:** 06, 07, 09 (after they land, `scripts/` holds only Surflo's entry points)

**Status:** ready-for-agent

Decision (user, 2026-10-11): fold the Surflo material into the `surflo` directory.

Layout (coordinator, 2026-10-11):

```text
surflo/                 component root, and the Python import root (like autonomy/ and parallax/)
├── README.md           what the inherited tree is, and the upstream compatibility boundary
├── surflo/             the `surflo` Python package (was ./surflo/); `import surflo` is unchanged
├── training/           was ./training/   (`import training` is unchanged)
├── configs/            was ./configs/
├── scripts/            was ./scripts/    (infer, evaluate, preprocess, repack_checkpoint, download_dl3dv_10k_meshed)
├── examples/           was ./examples/
├── install/            was ./install/
├── media/              was ./media/
└── submodules/         was ./submodules/ (vendored rasterizer plus the nvdiffrast and Depth-Anything-3 gitlinks)
```

- [ ] **Moves.** Done with `git mv`. Gitlink submodules move with `git mv`, so `.gitmodules` updates. Nothing
  inside the package changes except paths. The package name `surflo` and its import paths stay the same,
  which keeps compatibility with checkpoints, configs and downstream code (`CONTRIBUTING.md`).
- [ ] **Packaging.** `pyproject.toml` stays at the repo root and finds the package under the component:
  `[tool.setuptools.packages.find] where = ["surflo"]`. Prove that `import surflo` and the console entry
  points, if any, still resolve after an editable install, in the Insula or the Parallax rootfs. Do not
  install anything on the host.
- [ ] **References.** Every reference is updated:
  - README instructions (`python scripts/infer.py ...` becomes `python surflo/scripts/infer.py ...`, or a
    documented `cd surflo`);
  - `install/` scripts' relative paths;
  - config search paths in code;
  - `media/` image links in README;
  - Bazel targets, `.bazelignore` and `.github/workflows`;
  - Parallax references: `baselines/foundation_geometry_reference_runner.py`, `insulas/*/Dockerfile`,
    `curriculum/surflo_endpoint.py`, and the Surflo Insula studies from ticket 11 if they landed;
  - the publication audit and the identifier and import checkers' roots.
- [ ] **Import root.** `surflo/` is added as an import root to the import checker and its docs. `training/`
  and `scripts/` keep importing `surflo` and `training` absolutely.
- [ ] **README.** `surflo/README.md` keeps the upstream attribution, and links `UPSTREAM.md` and the license.
  The root README's "Surflo reference implementation" section either moves into `surflo/README.md`, linked from
  the root, or has its paths updated. Pick one and say which.
- [ ] **Live first.**
  - Smoke the moved entry points: `python -c "import surflo, training"` and `scripts/infer.py --help`, in
    the rootfs that carries torch.
  - `./bazelw test //:repo_gate` and `//parallax/...`.
  - Run `parallax/run.sh` smoke if it touches Surflo.
