# 03: Motion verifiers and the scientific cohort run again

**What to build:** The motion verifiers and the scientific cohort, which today fail before launching because they mount the same directory as code and source, run on launch plans and pass for real. Image-form runtime locks are loaded through the module, and nothing creates a lock on the spot.

**Blocked by:** 01

**Status:** ready-for-human

- [x] `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py`, `motion/verify_motion_native.py`, `motion/replay_motion_foundation.py`, `studies/scientific_cohort.py` and `studies/architecture/experiment_runner.py` build launch plans; no command-line splicing remains in them. If `experiment_runner` only drives frozen harness scripts, record why it stays as it is
- [x] The motion verifiers load their image-form locks through the module and no longer create a lock when one is missing
- [x] `studies/scientific_cohort_test.py` no longer replaces `launch_plan` with a fake. It asserts on the plan built against a fixture lock
- [ ] Acceptance: each motion verifier and the scientific cohort is run for real under `requires_live_gate` and passes. Commands, receipts and durations are recorded in the ticket. A failure unrelated to launching is reported as found, not hidden
- [x] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded

## Comments

### 2026-10-09 worker evidence

Implemented the launch-plan migration for the ticket-owned active callers:

- `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py` and `motion/verify_motion_native.py` now call `load_runtime_lock` for their image-form locks, build `LaunchPlan` objects with `build_plan`, render only at execution, and record `launch_plan` receipt data. The old missing-lock Docker export/create fallback is removed, so a missing lock is an error from the module.
- `motion/replay_motion_foundation.py` is import-safe, builds plans through the module, records plan receipts, and has `--output-root` so this worker could keep outputs under the required `lp03-runs` tree.
- `studies/scientific_cohort.py` now loads the current CPU runtime lock through `load_runtime_lock` before building eviction plans, declares `/opt` and `/srv` as plan inputs, and does not splice `--bind` / `--ro-bind` into a rendered command.
- `studies/architecture/experiment_runner.py` was left unchanged because it does not launch Insula directly in active code. It verifies receipts and dispatches copied frozen harness drivers from `studies/architecture/harness/`, which this ticket explicitly keeps frozen; its remaining `--ro-bind` reads are retained-receipt parsing for pinned manifest/worker verification.
- `studies/scientific_cohort_test.py` no longer replaces `launch_plan` with a fake. It uses a fixture runtime lock and asserts on `plan_data` for the built eviction plan.

TDD red evidence:

- `PYTHONPATH=autonomy python3 -m unittest autonomy.motion.verify_launch_plan_test autonomy.studies.scientific_cohort_test` failed first because the motion modules had no checked plan helpers, `replay_motion_foundation.py` executed at import time, `scientific_cohort.py` had no `build_eviction_plan`, and the old cohort path raised `code and source: host path mounted twice`.
- After the migration, the same focused unittest command passed 4/4 tests.

Focused and full gates:

- Focused Bazel: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/motion:verify_launch_plan_test //autonomy/studies:scientific_cohort_test` passed, 2/2 tests. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/focused-bazel-r2.log`.
- Default autonomy gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 169/169 tests. Ticket baseline was 168; new count is 169. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/autonomy-default.log`.
- Parallax gate: `./bazelw test --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //parallax/...` passed, 17/17 tests. Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/parallax.log`.
- CUDA autonomy gate: GPU 1 was free before the run (`index=1, utilization=0%, memory=4/183359 MiB`). `CUDA_VISIBLE_DEVICES=1 ./bazelw test --config=cuda --noexperimental_collect_system_network_usage --nocache_test_results --test_output=errors //autonomy/...` passed, 28/28 tests. GPU 1 was idle after the run (`index=1, utilization=0%, memory=4/183359 MiB`). Log: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/logs/autonomy-cuda.log`.

Real motion verifier runs under the launch-plan path wrote outputs under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC`:

- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli` passed in 4s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli/receipt.json`, sha256 `5479fe4edb087b5fb471d776e7c7164fca45dd4e28992a09fd8ddab27ac5eb9f`.
- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_cli_expanded.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli-expanded` passed in 4s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-cli-expanded/receipt.json`, sha256 `d72bb46ceb9c4ebf6c308f1ab10f86ea1f5363556ca3f88796827af9ad032617`.
- `PYTHONPATH=autonomy python3 autonomy/motion/verify_motion_native.py /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-native` passed in 5s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/verify-motion-native/receipt.json`, sha256 `db96875820612aaa217e11f9190c5c08229e4368110875405ae1977f91250451`.
- First `motion/replay_motion_foundation.py` run launched successfully but failed inside the native CLI fixture because the staged source closure omitted `motion/ingestion/strict_metric_reader.py`. That was a real non-launching failure and was fixed by staging that source file.
- `PYTHONPATH=autonomy python3 autonomy/motion/replay_motion_foundation.py --run-id replay-motion-foundation-r2 --output-root /data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC` passed in 14s. Receipt: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs/lp03-acceptance.VxmijC/replay-motion-foundation-r2/receipt.json`, sha256 `bfa112478d134bfdc75385203c94c18370a37de167ee5bd3c8acaf22d37cb1e0`.

Blocked acceptance item:

- I did not run a fresh `studies/scientific_cohort.py` lifecycle. Its publication stages invoke Waystone `put` to HDFS, and this worker was explicitly forbidden from HDFS writes. The script also requires output under the accounted scientific working root, while this run allows outside-repo writes only under `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-runs`.
- I checked for a no-write resume path through existing `cohort-v1` checkpoints and a trusted checkpoint registry. Existing checkpoint receipts use an older runtime lock, and `dataset.cohort_checkpoint.verify_checkpoint` compares `cp['runtime_lock']` exactly against the current `load_runtime_lock` result, so those retained checkpoints cannot satisfy this ticket's current-lock acceptance without a separate re-admission decision.
- The blocker is also recorded in the worker issue channel at `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/claude-worker-runs/workers/lp03-broken-verifiers-20261009T010152Z/tmp/claude-issues.jsonl`.

### 2026-10-09 live cohort preflight blocker

The live scientific cohort run was planned in
`docs/launch-plans/scientific-cohort-live-run.md` and committed before any live
execution. The selected one-scene run was
`6183008573786657189_5414_000_5434_000`, the smallest candidate with complete
source-audit records (`470536846` summed source object bytes), with fresh output
root:

`/data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/lp03-live-20261009T214131Z-6183008573786657189`

Planned command, not launched:

`systemd-run --user --scope --unit=sureal-cohort-20261009T214131Z-6183008573786657189 -p MemoryMax=17179869184 -p MemorySwapMax=0 -p MemoryAccounting=yes env HADOOP_CONF_DIR=/opt/tiger/yarn_deploy/hadoop/conf PYTHONPATH=autonomy python3 autonomy/studies/scientific_cohort.py --scene 6183008573786657189_5414_000_5434_000 --output /data02/home/philip.yang/.cache/waystone/waymo-perception/scientific-processing/lp03-live-20261009T214131Z-6183008573786657189`

Preflight evidence:

- JSON: `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-live/20261009T214131Z-6183008573786657189/preflight.json`, sha256 `20c01f12eea5c5fce350450e42964637488a9a71d5f6490bb46c6e20a100c9d5`.
- `/data02` free space passed: `130884612096` bytes free, above the `45` GiB requirement.
- Current CPU runtime lock loaded and verified through `load_runtime_lock`; lock sha256 `318e827c4832cbf2e6d02657c17bbda0ec696f5a7e2747b277922db364739403`.
- All source-audit records for the selected scene existed and `admit_scene` passed.
- `cohort-queue.lock` was not held by another cohort driver.
- Read-only Waystone `ls` checks showed all six planned publication blob keys absent:
  `datasets/scene-records-v1/6183008573786657189_5414_000_5434_000/scientific/archive.tar`,
  `datasets/scene-records-v1/6183008573786657189_5414_000_5434_000/scientific/publication.json`,
  `datasets/component-bundles-v1/6183008573786657189_5414_000_5434_000/scientific/archive.tar`,
  `datasets/component-bundles-v1/6183008573786657189_5414_000_5434_000/scientific/publication.json`,
  `runs/scientific-camera/6183008573786657189_5414_000_5434_000/archive/camera.tar`,
  `runs/scientific-camera/6183008573786657189_5414_000_5434_000/manifest/publication.json`.
- Fresh-output checks passed: the output root and scene checkpoint did not exist.

Blocking preflight result:

- The driver-accounted scientific working tree was already `17116464147` bytes
  before this run, above the `15` GiB cap of `16106127360` bytes by
  `1010336787` bytes.
- Including the selected scene's conservative source-size margin left
  `-1497668257` bytes of cap room.
- Because `studies/scientific_cohort.py` calls the same `total(WORKING)` cap
  logic and this worker is forbidden to modify or delete retained evidence,
  receipts, locks or shared cache contents outside this run's fresh output root,
  the live command was not launched and no HDFS writes were performed.
- Worker issue-channel copy:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-live/20261009T214131Z-6183008573786657189/claude-issues.jsonl`,
  sha256 `b9770ea026f8d018b72abf8a3c1699db74b8a911d7c17fe55387f912efc2c4ed`.

### 2026-10-09 release-audit blocker

After the user authorized clearing room by releasing earlier already-published
runs, I performed a read-only release eligibility audit and did not release any
files. Evidence:

- Release audit JSON:
  `/data02/home/philip.yang/devx/tmp/sureal-refactor-20261007/lp03-live/20261009T220714Z-release-audit/release-log.json`,
  sha256 `01fc75d5329b642f38d1685077261d69955491d6d046d0ced3d67b7a85627b23`.
- Driver-style `total(WORKING)` before and after the audit remained
  `17116464147` bytes. Nothing was unlinked.
- With the selected scene's conservative bundle upper bound of `487331470`
  bytes and the requested `1` GiB margin, the run still needs strictly more
  than `2571410081` bytes released before the 15 GiB driver cap can hold.

Candidate audit results:

- `balanced16-sustained-baseline-controller20261003a`:
  `1668358495` bytes, not released. Its sustained state has unreleased records,
  so resume still depends on the local payload; matching receipts reference
  current files, but no sanctioned release-only command in the repo releases
  that mixed resource shape without also crossing protected inputs.
- `balanced16-sustained-baseline-t27f20261008T081353Z`:
  `834175991` bytes, not released. Its sustained state has unreleased records
  and no publication receipt was found that references the live files.
- `balanced16-sustained-baseline-t27f20261008T074202Z`:
  `408621222` bytes, not released. No sustained state publication record and no
  matching publication receipt were found.
- `resource-retention-balanced16-sustained-baseline-controller20261003a-shared-5a74e356862244deb88a264e48f82908`:
  `1381569292` bytes, not released. The generic publisher protects this pattern;
  the live evidence root has no durable `verified-publication.json`; and
  `resources.resource_release_plan.release_plan` failed against the available
  receipt candidates.
- `resource-retention-balanced16-sustained-baseline-controller20261003a-shared-ac7ee99e41b54b5d9b54b1a24e64d95d`:
  `1381569470` bytes, not released for the same reasons as the `5a74...`
  sibling.
- `cohort-v1`: `1846777089` bytes, not released. Scene-level point, sidecar and
  camera eviction receipts already exist; repeat eviction refuses to overwrite
  evidence, and the remaining bytes are retained receipts/logs rather than
  payloads named by a release plan.
- Large architecture/norm/native-one-batch directories in the audit were not
  released because no publication receipt was found that references their
  current live files.

Because no candidate could be released under the sanctioned release rules, the
fresh preflight, live `scientific_cohort.py` run, post-run receipt verification
and new gate pass were not executed.
