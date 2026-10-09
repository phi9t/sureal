# 13: Review fixes for sustained resource publication and journal entry point

**What to build:** Fix the sustained-run, resource-stage, checkpoint-publication and research-journal review findings from the whole-branch blob-store review without weakening retained evidence.

**Status:** done

- [x] Legacy non-blob resource publication receipts restore schema, ordered check, readback and independent-admission validation strength while retained real receipts still validate read-only
- [x] Sustained resume filters unrelated blob publications by checkpoint manifest identity before release audit or blob readback
- [x] Resource-bound sustained stages execute and record the same wrapped launch plan, and receipt checks reject command, environment, namespace and GPU device-bind drift
- [x] Resource wrapper helpers move out of `insula.launch_plan` into `resources.command`, leaving launch-plan public API concept-neutral except legacy receipt readers
- [x] Sustained stage plan recording avoids hashing the live scientific output tree while keeping every stage input identified in the launch-plan receipt
- [x] Blob publication detection is shared and schema-versioned, and the research journal has a blob-store publish CLI entry point with offline readback coverage

## Comments

Done: fixed 6 review findings with test-first coverage. The focused red tests covered legacy publication strictness, retained legacy receipt validation, unrelated blob resume filtering, stage command/launch-plan mismatch, resource wrapper boundary cleanup, live scientific-root digest avoidance, shared blob receipt shape, and research-journal CLI publication.

Verification:

- Focused suite: 6/6 targets passed (`//autonomy/resources:checkpoint_test`, `//autonomy/training_execution:run_sustained_test`, `//autonomy/training_execution:sustained_controller_backend_test`, `//autonomy/training_execution:sustained_launch_plan_test`, `//autonomy/insula:launch_plan_boundary_test`, `//autonomy/retention:publication_test`)
- Resource/stage matcher rerun: 3/3 targets passed (`//autonomy/resources:stage_test`, `//autonomy/training_execution:sustained_controller_backend_test`, `//autonomy/insula:launch_plan_boundary_test`)
- Required autonomy gate: 185/185 tests passed
- Required parallax gate: 17/17 tests passed
- CUDA gate: GPU 1 was free (`GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, no compute process on that UUID); `CUDA_VISIBLE_DEVICES=1` autonomy CUDA gate passed 30/30 tests

Done follow-up: restored the deeper legacy non-blob checkpoint publication validation that the coordinator identified as still missing. The active validator now runs an equivalent of the frozen live-reference audit and independent-admission checks without importing `studies` back into `resources` (that dependency would create a Bazel cycle). The equivalent uses `insula.launch_plan.read_receipt_mounts` / `resources.command.inspect_command` for old command receipts, verifies executed archive helper/source pins for both retained legacy pin schemas, validates create/verify/rehydrate proofs, archive snapshot jobs and outputs, HDFS transfer log digests, independent audit input hashes/check.json identity, rootfs split-entry mount order, protected identity binds, and admission proof identity.

Red first: `//autonomy/resources:checkpoint_test` failed on the current head for the intended reasons before production edits: changed admission proof bytes, changed transfer log bytes, and reordered audit command mounts all raised `AssertionError: ValueError not raised`.

Retained receipts: read-only scan found 9 retained legacy checkpoint publications under `~/.cache/waystone/waymo-perception/insula/` with original proof roots; 9/9 validated, 0 failures. No retained legacy publications were present under `autonomy/research`.

Verification rerun:

- Focused checkpoint suite: `//autonomy/resources:checkpoint_test` passed
- Launch-plan boundary focused check: `//autonomy/insula:launch_plan_boundary_test` passed
- Required autonomy gate: 185/185 tests passed
- Required parallax gate: 17/17 tests passed
- CUDA gate: GPU 1 was free (`GPU-eaed2f0d-2541-8ca8-b6c4-3e2e45e86619`, 4 MiB used, no compute process on that UUID); `CUDA_VISIBLE_DEVICES=1` autonomy CUDA gate passed 30/30 tests
