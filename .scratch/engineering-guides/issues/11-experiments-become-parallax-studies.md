# 11: The Surflo coherence experiments become Parallax studies

**What to build:** `experiments/` is gone. Its two remaining one-off studies of Surflo scene coherence join the
program they serve. The study records are the B200 Insula scout of 2026-09-25 and the photoreal paired-scene
benchmark. That program is Parallax: the pathway from reconstruction to persistent generative scenes, ending in
the coherent-scene question in `docs/coherent-scene-hypotheses.md`.

**Blocked by:** 07

**Status:** ready-for-agent

Decisions (coordinator, 2026-10-11):
- `experiments/insula-scout/` moves to `parallax/studies/surflo-insula-scout/`.
- `experiments/photoreal-scenes/` moves to `parallax/studies/photoreal-scenes/`.
- Studies follow autonomy's `studies/<name>/` convention: one-shot procedures plus their recorded results.
  `results.json` and the lock and recipe JSONs are recorded evidence and keep their bytes.
- Their colocated `tests/` dirs become `*_test.py` beside the code. Imports follow the `parallax/` import root.
  Wire them into Bazel only if they are pure CPU unit tests. Otherwise tag them `requires_live_gate`, or leave
  them as documented live commands.
- Their shell wrappers (`build.sh`, `enter.sh`, `run*.sh`, `probe.sh`, `install_env.sh`) come into the
  shell-lint scope. Fix them, or add them to the shrink-only baseline.

- [ ] Every reference is updated: README, MISSION, `docs/coherent-scene-hypotheses.md`, `parallax/README.md`,
  and the scripts' own relative paths. Verify each wrapper still resolves its paths with `bash -n` and a dry
  path check. Do not rerun the B200 study.
- [ ] `parallax/studies/README.md` says what a study is and lists both studies.
- [ ] Live first: `./bazelw test //:repo_gate` and `//parallax/...`.
