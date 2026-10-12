# Agent guide

## Project overview

Sureal contains two research programs: `autonomy/` for perception research and
`parallax/` for 3D pathway work. Directories express concepts rather than
languages or runtimes; see
`docs/adr/0001-directories-express-concepts.md`.

## Execution boundary

Bazel is the verification boundary for this repository and must be launched
through `./bazelw`, which enters the pinned Insula rootfs. Do not run host
`bazel` directly or install dependencies on the host to satisfy a Bazel target.
The host may run only cheap static checks such as the versioned git hook; the
Insula gates remain the authority for claims about the tree.

## Commands

Shell scripts follow `docs/guides/shell-engineering.md`; ShellCheck runs in the
repo gate from a Bazel-pinned release archive, not from host packages.
The full build, rootfs and retained-evidence flow is documented in
`docs/guides/build-and-verify.md`.

Enable the versioned git hooks in a clone with:

```bash
git config core.hooksPath .githooks
```

Before landing, run the static repository gate:

```bash
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate
```

The broader CPU, CUDA and Parallax suites are:

```bash
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...
./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...
```

Use the CUDA command only when GPU 1 is actually free. The wrapper selects the
CPU, GPU or Parallax rootfs from the target pattern and mounted configuration.

### Test tiers

Bazel tags select test tiers (`docs/adr/0004-test-tiers-and-gpu-masking.md`):

- `requires_gpu` runs only in the CUDA gate.
- `requires_live_gate` runs only when a command asks for the live tier.
- `known_failure` is excluded from landing gates until its ticket removes the tag.

`--config=cuda` sets `SUREAL_REQUIRE_GPU=1`, so a GPU test fails, rather than
skips, when no CUDA device is visible. The filename suffixes `_live_test.py` and
`_host_test.py` mark tests that touch a live runtime or host-only data.

## Python imports

Python code under `autonomy/` and `parallax/` imports from that directory as
the import root: use `from evidence...` or `from insula...`, not relative
imports or sibling-directory import roots. Do not edit `sys.path` in active
code. Historical receipts and frozen procedure records are outside the active
import checker. Documented live commands and receipts may still set
`PYTHONPATH=autonomy`.

Python engineering follows `docs/guides/python-engineering.md`. Ruff lint and the current
format batch run in `//:repo_gate`; do not reformat retained receipts, source
snapshots or historical archives.

C++ and CUDA style follows `docs/guides/cpp-engineering.md`. The repo gate runs
the pinned clang-format check and the mechanical C++ lint over tracked active
C++ under `autonomy/` and `parallax/`, excluding historical archives and
submodules.

## Cache rules

Retained receipts and source snapshots are byte-exact evidence. Do not edit
receipts, retained evidence, root filesystems, locks or caches to make a check
pass. If scientific working storage needs cleanup, run the retention planner in
dry-run mode first and review the plan; pass `--apply` only after an explicit
cleanup decision. The planner is `autonomy/retention/scientific_retention_planner.py`
and is dry-run by default.

Never delete cache state by hand. Published-but-unreleased scientific runs go
through the retention publisher's release path; the planner unlinks only stray
logs and digest-verified leftovers from already released runs when apply is
explicitly approved.

## Engineering rules

Follow the accepted ADRs before changing boundaries:

- `docs/adr/0001-directories-express-concepts.md`: directories name concepts.
- `docs/adr/0002-bazel-runs-inside-insula.md`: Bazel runs inside Insula and
  takes dependencies from the rootfs.
- `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md`: source pins refer
  to source snapshots, not the working tree.
- `autonomy/docs/adr/0002-evidence-blobs-go-through-a-blob-store.md`: evidence
  blobs go through the backend-neutral blob store.
- `autonomy/docs/adr/0003-executions-are-described-by-launch-plans.md`: Insula
  executions are described by launch plans checked against full runtime locks.

Keep hooks and shell wrappers thin. Static hooks may run
`git diff --cached --check`, `harness/lint/check_identifiers.py`, and the
standalone storage-boundary scan in `harness/lint/check_storage_boundary.py`,
but they must not import repo runtime code or replace the Insula gates.

## Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/` in this
repo. See `docs/agents/issue-tracker.md`.

## Agent skills

### Triage labels

The five default triage roles are used unchanged, recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `CONTEXT-MAP.md` at the root points at each context's `CONTEXT.md`. See `docs/agents/domain.md`.
