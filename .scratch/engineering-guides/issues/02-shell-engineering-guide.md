# 02: Shell engineering guide

**What to build:** A contributor writing a Sureal shell wrapper follows `docs/guides/shell-engineering.md`, which
states the function contract, scoping and diagnostics rules Milano uses. The existing shell-style lint
points at the new guide.

**Blocked by:** None (can start immediately)

**Status:** done

Source: `~/workspace/milano/docs/guides/shell-engineering.md` and
`~/workspace/milano/docs/adr/0001-python-over-shell-for-policy.md`. Sureal's
`docs/guides/shell-style.md` and `docs/adr/0003-python-over-shell-for-policy.md` are the starting point.

- [x] **Rename.** `docs/guides/shell-style.md` becomes `docs/guides/shell-engineering.md` (`git mv`). It is expanded with:
  - "use shell only for glue", linking Sureal ADR 0003;
  - the file shape;
  - function comments, including the structured `Globals:` / `Arguments:` / `Outputs:` / `Returns:` block for
    non-obvious or cross-script functions;
  - `local` for function variables;
  - `${var}` braces in new and rewritten scripts;
  - arrays for argv;
  - `case` for option parsing;
  - diagnostics with `printf ... >&2`;
  - the ShellCheck disable policy;
  - a closing checklist.
- [x] **Sureal deltas recorded explicitly.** These stay:
  - the `#!/usr/bin/env bash` shebang;
  - the 150-line limit and the shrinking `scripts/shell_style_baseline.json`;
  - the Bazel-pinned ShellCheck and shfmt;
  - receipt-pinned scripts are exempt.
- [x] **References.** `AGENTS.md`, `scripts/check_shell_style.py` and its tests, and any other active reference
  name the new path. A grep over active files, excluding `.scratch/` history, finds no `shell-style.md`.
- [x] **No weakening.** The mechanical lint keeps every rule it enforces today. Add a mechanical rule only if
  the real tree already passes it, or the same change fixes the violations in unpinned files.
- [x] **Gates.** `//:repo_gate` passes through `./bazelw`.

## Comments

2026-10-10:

- Live check before edits:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed. Invocation ID `a8a18fe1-8760-4d73-872a-421bd910a19b`; count: 23/23 tests passed.
- Implemented `git mv docs/guides/shell-style.md docs/guides/shell-engineering.md`. The new guide documents
  shell-as-glue with a link to ADR 0003, file shape, function comments with `Globals:` / `Arguments:` /
  `Outputs:` / `Returns:`, `local` scoping, `${var}` braces, argv arrays, `case` option parsing,
  `printf ... >&2` diagnostics, ShellCheck disable policy and a closing checklist. It also records Sureal
  deltas: `#!/usr/bin/env bash`, 150-line shrinking baseline, Bazel-pinned ShellCheck and shfmt, and
  receipt/source-pin exemptions.
- Active reference check:
  `rg -l "shell-style\\.md" --glob '!/.scratch/**' --glob '!*.jsonl' . | wc -l` returned 0.
  `rg -l "docs/guides/shell-engineering\\.md" --glob '!/.scratch/**' --glob '!*.jsonl' . | wc -l`
  returned 3: `AGENTS.md`, `scripts/check_shell_style.py`, `scripts/check_shell_style_test.py`.
- No weakening evidence: `scripts/check_shell_style.py` kept its mechanical policy logic unchanged; the only
  checker change was the module docstring naming `docs/guides/shell-engineering.md`. Focused gate
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:check_shell_style_test //:repo_gate_shell_style_test`
  passed. Invocation ID `98e27534-51cc-43b4-a014-31b1ff2566e9`; count: 2/2 tests passed.
- Source-pin guard:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:pinned_sources_test`
  passed. Invocation ID `e243ae72-058c-4ceb-a9da-a8a552cb1125`; count: 1/1 test passed.
- Required gates:
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //:repo_gate`
  passed. Invocation ID `3e5fb79b-78aa-4774-a14d-d0a556fc85e9`; count: 23/23 tests passed.
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...`
  passed. Invocation ID `0b2ad92f-be29-46bc-ac5c-bc1b93d44d78`; count: 191/191 tests passed.
  `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...`
  passed. Invocation ID `04ddc1ec-cfb5-485c-84dd-eff27fb175b6`; count: 32/32 tests passed.
  CUDA gate skipped as requested because this sandbox has no GPU devices and the coordinator runs CUDA.
- SHA-256 digests after implementation, before ticket bookkeeping:
  `AGENTS.md` `63f85fd55363f407535bf882c779f6ef24879c49967bb84ba23e19b2e266e71f`;
  `docs/guides/shell-engineering.md` `9733b4cb9f535b80f9277950444a94fbef9f327dc71c16d53ce2f45836e6f027`;
  `scripts/check_shell_style.py` `c0d306e89396fe7dc17115db4642e0190b03acb5d8a910ca2d3c8db2bb4b8364`;
  `scripts/check_shell_style_test.py` `990ddb56d8ca95c30e6c5dc24df6deb1ed5d51f82d4768fea64a6a096456457b`.
