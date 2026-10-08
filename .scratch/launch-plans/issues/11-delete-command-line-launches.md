# 11: Delete the command-line form of launch_plan

**What to build:** No active code can build a sandbox command line except the launch-plan module's renderer. `launch_plan`'s command-line form and `live_gate_plan` are gone, and a check keeps it that way.

**Blocked by:** 02, 03, 04, 05, 06, 07, 08, 09, 10

**Status:** ready-for-agent

- [ ] `insula.entry.launch_plan` (command-line form) and `sandbox_plan.live_gate_plan` are deleted, and no active import of either remains
- [ ] A test fails if any active file outside the module renders `bwrap` arguments or parses a runtime lock itself. Frozen areas are excluded by path
- [ ] The documentation that describes launching inside Insula (`autonomy/ARCHITECTURE.md` and `insula` docs) names the launch-plan module as the only way in
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
