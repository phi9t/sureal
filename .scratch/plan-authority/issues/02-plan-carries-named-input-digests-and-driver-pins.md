# 02: The plan carries named-input digests and is the only authority for GPU driver pins

**What to build:**

- A launch plan can declare the digest of any named input when it is built, and the public `record_plan` records it.
- The sustained controller's hidden-attribute path and its local `record_plan` are gone.
- For new receipts, GPU driver pins are checked once, from the `gpu-driver:*` mount digests in the plan record.
- Legacy receipts keep their current driver check.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The plan builder accepts declared named-input digests, and `insula.launch_plan.record_plan` records them. There is no `object.__setattr__` on a `LaunchPlan` anywhere in active code.
- [ ] The scientific-root and source-snapshot digests of sustained stages reach the receipt through the public recording path. A test proves that recording through the public `record_plan` keeps them.
- [ ] **New-receipt driver pins:**
  - Verification reads only the plan record.
  - Any `driver_hashes` field still written is derived from the plan record when the receipt is written.
  - `resources.dependencies` and `admit_sustained` read pins through one launch-plan function.
- [ ] A mismatched driver digest in a new receipt fails with one clear error. A test covers a tampered record.
- [ ] **Live acceptance comes first.** Real runs on this ticket's code: the ticket 01 live set, including a GPU live gate on GPU 1 whose fresh receipt carries driver pins only through the plan record. The fresh receipts must verify, and a tampered driver digest must fail. Record the results in Comments.
- [ ] The golden argv test from 01 is unchanged and passes.
- [ ] The retained-receipt sweep's counts match ticket 01's baseline exactly.
- [ ] **Gates pass:** CPU, parallax, and CUDA on GPU 1 when it is free. Counts recorded.
