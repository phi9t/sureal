# 03: New receipts are checked by comparing plans, and the resource wrapper is plan data

**What to build:**

- **The resource wrapper is plan data:** wrapper mounts with explicit mount roles, plus a command prefix. The resource runner and the resource verifier both build the same expected wrapped plan.
- **The launch-plan module checks new receipts:** every receipt with a `launch_plan` record is checked by comparing that record with the expected plan, by role, target, mode, digest, devices, environment, working directory and command.
- **The rendered command line in a new receipt is checked by rendering the record,** never by parsing the command line.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The launch-plan module has one public plan-versus-record comparison, and its rejections name the mismatched field.
- [ ] **The resource wrapper produces a plan.** `resources.stage` runs and checks resource stages through it, and no active code splices mounts into rendered argv for new launches.
- [ ] **No new receipt goes through the legacy parser.** These all use plan comparison when the receipt has a plan record:
  - every active `read_receipt_mounts({'command': …})`-style call in `resources.stage`, `resources.checkpoint` and `training_execution.sustained_controller_backend`;
  - `check_stage`.

  Receipts without one still go through the legacy parser.
- [ ] **The ordering rule exists only in the renderer.** The `/tmp`, `/tmp/*` and device mount order is defined only in `render_plan`, and the private index helpers used for splicing are deleted or used only by the legacy path.
- [ ] **Tampering tests:** for a new receipt, a record with a changed mount digest, a changed role, or a reordered argv each fails verification.
- [ ] **Live acceptance**, run for real on this ticket's code (GPU 1 only, and only when it is free). Record the commands, receipts and durations in Comments, and report failures as found:
  - the three motion verifiers and `replay_motion_foundation.py`;
  - one resource-measured stage through `resources.stage`;
  - the GPU live gate (`insula/verify_gpu_live.py` or its current equivalent) on GPU 1.

  Their fresh receipts must verify through the new plan comparison, and a tampered copy of one must fail.
- [ ] The golden argv test is unchanged and passes, and the retained-receipt sweep matches the baseline exactly.
- [ ] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.
