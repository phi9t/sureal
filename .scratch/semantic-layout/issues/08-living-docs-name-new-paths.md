# 08: Living documents name the new paths

**What to build:** A reader following the README, the contributing guide, the agent guide, the architecture note, the task index or a component README finds commands and links that work with `parallax/` and `autonomy/`. Dated specs, plans and retained evidence keep the paths they were written with.

**Blocked by:** 06 (Rename the curriculum to `parallax/`), 07 (Rename the perception program to `autonomy/`)

**Status:** ready-for-agent

- [x] Every command shown in a living document runs as written
- [x] Every relative link in a living document resolves
- [x] The contributing guide's validation tiers describe the wrapper and the Bazel test commands
- [x] The stale 'planned layout' section of the perception README is replaced by a pointer to the architecture note
- [x] No file under a `research/` directory and no dated spec or plan is modified

## Comments

Built:

- Updated root and component living docs to name `parallax/` and `autonomy/`
  paths for current commands and links.
- Replaced the stale perception README planned-layout section with a pointer to
  `autonomy/ARCHITECTURE.md`.
- Fixed moved relative links in autonomy living docs, including the context,
  roadmap, research-task index and architecture idea pages.
- Removed the nonexistent `autonomy/explorer/build.py` command from the
  explorer README; it now names the admitted checked-in worker files and the
  retained-receipt scope.
- Added publication-audit coverage for current component paths, resolving
  relative links, Bazel wrapper validation tiers, and repo-relative command
  entry points in living markdown.

Verification:

- `python -m unittest tests.test_publication_audit.RepositoryIdentityTests.test_living_documents_name_the_current_component_paths tests.test_publication_audit.RepositoryIdentityTests.test_living_document_relative_links_resolve tests.test_publication_audit.RepositoryIdentityTests.test_living_document_repo_relative_command_entrypoints_exist -v` => `Ran 3 tests`, `OK`.
- `python -m unittest tests.test_publication_audit -v` => `Ran 30 tests`, `OK`.
- `python scripts/publication_audit.py --root .` => `{"errors": [], "gitlinks": 2, "max_blob_bytes": 26214400, "schema_version": 1, "status": "pass", "tracked_files": 4969}`.
- `git diff --check` => exit 0, no output.
- `rg -n "experiments/waymo-perception|experiments/3d-pathway" --glob '*.md' --glob '!**/research/**' --glob '!docs/superpowers/specs/**' --glob '!docs/superpowers/plans/**' --glob '!docs/adr/**' --glob '!submodules/**'` => no matches.
- `git diff --name-only | rg '(^|/)research/'` => no output.
- `git diff --name-only | rg '^docs/(adr|superpowers/(specs|plans))/'` => no output.
- `python3 autonomy/tools/layers.py` => `PASS: 0 layering problem(s) across 10 layers`.
- `./bazelw --emit-plan test //parallax/...` => selected `/data02/home/philip.yang/.cache/waystone/3d-pathway/insula/rootfs-v1` and Bazel target `//parallax/...`.
- `./bazelw --emit-plan test //autonomy/...` => selected `/data02/home/philip.yang/.cache/waystone/waymo-perception/insula/rootfs-v3` and Bazel target `//autonomy/...`.
- `./bazelw --emit-plan test --config=cuda //autonomy/...` => selected `/data02/home/philip.yang/.cache/waystone/waymo-perception/gpu-rootfs-v6` and Bazel args `--config=cuda //autonomy/...`.
- `python autonomy/architecture.py list` => listed runnable and planned architecture experiments.
- `python autonomy/architecture.py show residual_bev` => printed the `Residual BEV CNN` registry entry.
- `python autonomy/architecture.py run residual_bev --run-id residual-trial01 --dry-run` => printed a plan-only JSON with `scope` `plan only; no files, GPU or runtime checks`.
- `PYTHONPATH=autonomy python -c "from advanced.catalog import catalog; print('\n'.join(catalog()))"` => listed the advanced catalog entries.
- `PYTHONPATH=autonomy python autonomy/tracking/cli.py verify-journal` => `VERIFIED journal entries 129`.
- `autonomy/viewer/run.sh help` => printed viewer command usage.
- `autonomy/gcs.sh --help` => printed GCS wrapper usage.
- `bash -n autonomy/setup-gcs.sh autonomy/scripts/refresh-hdfs-auth.sh autonomy/scripts/install-hdfs-auth-keepalive.py autonomy/viewer/run.sh parallax/run.sh` => exit 0.
- `./bazelw test //parallax/...` => `Executed 0 out of 17 tests: 17 tests pass`.
- `./bazelw test //autonomy/... --test_output=errors` => `Executed 138 out of 138 tests: 138 tests pass`.
- `python3 autonomy/tools/pins.py check --base work/semantic-layout/integration` => exit 1 with `FAIL: 24 changed file(s) cited by retained receipts`.

Pinned files changed by this ticket and why:

- `autonomy/ARCHITECTURE.md`, `autonomy/README.md`,
  `autonomy/advanced/README.md`, `autonomy/architecture/README.md`,
  `autonomy/explorer/README.md`, `autonomy/roadmap.md`,
  `autonomy/scripts/HDFS_AUTH.md`, `autonomy/tier1/README.md`,
  `autonomy/tracking/README.md`, `autonomy/viewer/README.md`: updated
  living documentation to current `autonomy/` commands, wrapper guidance, and
  moved relative links.
- `autonomy/architecture/ideas/all_pillars.md`,
  `autonomy/architecture/ideas/coarse_mlp.md`,
  `autonomy/architecture/ideas/context_pfn.md`,
  `autonomy/architecture/ideas/deep_pfn.md`,
  `autonomy/architecture/ideas/grid_coarse.md`,
  `autonomy/architecture/ideas/grid_fine.md`,
  `autonomy/architecture/ideas/masked_pfn.md`,
  `autonomy/architecture/ideas/point_attention.md`,
  `autonomy/architecture/ideas/ragged_pillars.md`,
  `autonomy/architecture/ideas/range_fusion.md`,
  `autonomy/architecture/ideas/residual_bev.md`,
  `autonomy/architecture/ideas/retain64.md`,
  `autonomy/architecture/ideas/sparse_bev_transformer.md`,
  `autonomy/architecture/ideas/window_bev.md`: fixed moved relative links and
  current architecture-runner command paths.

Reviewer notes:

- No `.py` files under the protected old perception directories were changed.
- No file under any `research/` directory was changed.
- No dated spec or plan under `docs/adr/` or `docs/superpowers/` was changed.
- Commands that intentionally require credentials, datasets, live training,
  publishing, or local virtualenv setup were not executed for side effects; the
  ticket verifies their current repo-relative entry points, syntax, wrapper
  plans, and safe help/dry-run forms.
