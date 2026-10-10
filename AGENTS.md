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

Shell scripts follow `docs/guides/shell-style.md`; ShellCheck runs in the
repo gate from a Bazel-pinned release archive, not from host packages.

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
`git diff --cached --check`, `scripts/check_identifiers.py`, and the standalone
storage-boundary scan, but they must not import repo runtime code or replace the
Insula gates.

## Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/` in this
repo. See `docs/agents/issue-tracker.md`.

## Agent skills

### Triage labels

The five default triage roles are used unchanged, recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `CONTEXT-MAP.md` at the root points at each context's `CONTEXT.md`. See `docs/agents/domain.md`.
