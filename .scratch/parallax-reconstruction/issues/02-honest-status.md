# 02: Every module and metric declares whether it is synthetic or real

**What to build:** Readers of a Parallax report can tell measured numbers from illustrative ones.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `curriculum.json` gives each module an `implementation` value of `synthetic`, `real` or `real+baseline`. The schema enforces it. All 15 modules start as `synthetic`.
- [ ] **Labelling.** Every hardcoded metric in the synthetic labs is labelled `illustrative`, for example `accuracy_mm` and `f_score_2mm` in the MVS lab and `map_f_score` in the SLAM lab. Metrics computed from data in the lab keep their values but are labelled as computed on synthetic data.
- [ ] Reports (JSON and rendered) show the status of each module and of each metric. The validator rejects a module marked `real` whose metrics are not all computed.
- [ ] The README states plainly what is real and what is illustrative today.
- [ ] **Live check.** `all --profile smoke` runs inside the Parallax Insula, and the report shows the labels. Record the commands.
- [ ] **Gates:** `//:repo_gate` and `//parallax/...`.
