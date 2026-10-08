# 03: Motion verifiers and the scientific cohort run again

**What to build:** The motion verifiers and the scientific cohort, which today fail before launching because they mount the same directory as code and source, run on launch plans and pass for real. Image-form runtime locks are loaded through the module, and nothing creates a lock on the spot.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py`, `motion/verify_motion_native.py`, `motion/replay_motion_foundation.py`, `studies/scientific_cohort.py` and `studies/architecture/experiment_runner.py` build launch plans; no command-line splicing remains in them. If `experiment_runner` only drives frozen harness scripts, record why it stays as it is
- [ ] The motion verifiers load their image-form locks through the module and no longer create a lock when one is missing
- [ ] `studies/scientific_cohort_test.py` no longer replaces `launch_plan` with a fake. It asserts on the plan built against a fixture lock
- [ ] Acceptance: each motion verifier and the scientific cohort is run for real under `requires_live_gate` and passes. Commands, receipts and durations are recorded in the ticket. A failure unrelated to launching is reported as found, not hidden
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
