# Agent guide

## Commands

Bazel is the verification boundary for this repository and must be launched
through `./bazelw`, which enters the pinned Insula rootfs. Do not run host
`bazel` directly or install dependencies on the host to satisfy a Bazel target.
Shell scripts follow `docs/guides/shell-style.md`; ShellCheck runs in the
repo gate from a Bazel-pinned release archive, not from host packages.

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

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage roles are used unchanged, recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `CONTEXT-MAP.md` at the root points at each context's `CONTEXT.md`. See `docs/agents/domain.md`.
