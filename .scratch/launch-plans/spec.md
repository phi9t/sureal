# Launch plans: one module checks runtime locks and describes every execution inside Insula

Status: ready-for-agent

Governing decisions: `autonomy/docs/adr/0003-executions-are-described-by-launch-plans.md`, `autonomy/docs/adr/0002-evidence-blobs-go-through-a-blob-store.md`, `autonomy/docs/adr/0001-source-pins-refer-to-snapshots.md` and `docs/adr/0002-bazel-runs-inside-insula.md`. Vocabulary follows `autonomy/CONTEXT.md`: runtime lock, launch plan, mount role, live implementation gate, source snapshot, source pin.

## Problem Statement

Every gate, verifier, publisher and training stage in the perception program runs its work inside a dedicated Insula. Each one decides for itself how to check the root filesystem it runs on and how to build the sandbox command line, and they do it differently.

- **About 50 active files read a runtime lock by hand, and most check too little.** Only `insula/entry` checks the recipe: that the lock was built from the committed Dockerfile and requirements. It does that only for the CPU root filesystem, and only after `--emit-plan` has already returned. The Bazel launcher checks the content digest and the Bazel version but not the recipe. Most other callers check only the content digest, which cannot notice a lock built from an old Dockerfile. That is how ticket 27 found `rootfs-v4` recorded against Dockerfile `61a783f4…` while the committed one is `8e6c2a38…`.
- **There are two lock forms, and each caller handles at most one.** CPU `rootfs-v4` and GPU `rootfs-v6` record recipe digests (`dockerfile_sha256`, `requirements_sha256`, Bazel version and binary digest). Metrics and motion-CLI root filesystems record `image_id`, `recipe_hashes` and sometimes a parent image. The motion and metrics verifiers even create a lock when it is missing.
- **About 45 active files build a sandbox command line, in seven different shapes.**
  1. Through `enter.sh` (strict).
  2. `launch_plan(...)` used as it is.
  3. `launch_plan(...)` plus extra mounts and environment spliced in before `--`. This is the bulk.
  4. `launch_plan(...)` with the root mount swapped for read-only per-entry mounts (`resources/retention.py`).
  5. `launch_plan(...)` plus GPU devices and driver libraries copied by hand from the Bazel launcher (`insula/verify_gpu_live.py`).
  6. An old receipt's command replayed and rewritten by mount target (`training_execution/admit_sustained.py`, `training_execution/sustained_controller_backend.py`, `insula/verify_gpu_isolation.py`). This is how the balanced16 sustained run gets its GPU.
  7. A hand-written `bwrap` call that copies the live-gate layout but drops `/source`, `PYTHONPATH` and the overlap check (`detection/training_box_replay.py`).

  The Bazel launcher is an eighth shape, and the only one that already builds a structured plan.
- **Three verifiers cannot run at all.** `motion/verify_motion_cli.py`, `motion/verify_motion_cli_expanded.py`, `motion/verify_motion_native.py` and `studies/scientific_cohort.py` pass the same directory as code and source. The overlap check rejects that with `ValueError`, before anything launches. `scientific_cohort_test.py` replaces `launch_plan` with a fake, so nothing noticed. This predates the semantic-layout refactor.
- **Tests can only check strings.** `launch_plan` returns a command line, so tests assert on `index('--ro-bind')` slices and literal lists. `resources/command.py` keeps a fixed arity table just to parse command lines back into mounts, and `resources/stage.py`, `retention/retention_audit.py` and `training_execution/checkpoint.py` scan command lines for mount targets.
- **Receipts record the machine, not the evidence.** Receipts store full command lines with absolute host paths. These cannot be checked again on another machine, and they tie audits to the command-line shape.

## Solution

One **launch-plan module** in `insula` is the only way to run something inside a dedicated Insula.

- A caller loads a **runtime lock**. The module checks it in full, in either lock form, before anything else happens.
- The caller describes what it needs: code, an optional source, an output, named extra inputs, an optional GPU request, environment and a command. It gets back a **launch plan**: mounts by **mount role**, devices, environment, working directory and command.
- The plan becomes a sandbox command line only when it launches. The overlap rules, GPU devices, driver libraries and the clean environment all live inside the module.
- Receipts record the plan by mount role and digest, never by host path or command line. The existing command-line parser stays, only to read old receipts.

Callers migrate in batches by launch shape and concept, the broken verifiers are fixed with a real run, and finally the command-line form of `launch_plan` is deleted. Frozen code keeps its own launches.

## User Stories

1. As a researcher, I want one module that runs anything inside a dedicated Insula, so that I never assemble a sandbox command line myself.
2. As a researcher, I want to load a runtime lock by naming a root filesystem, so that I never parse lock JSON myself.
3. As a researcher, I want every runtime lock checked in full (schema, content digest and recipe digests), so that a root filesystem built from an old recipe is refused before it runs anything.
4. As a researcher, I want the recipe-digest form (CPU `rootfs-v4`, GPU `rootfs-v6`) checked against the committed Dockerfile and requirements it names, so that a stale lock is caught the way ticket 27 caught `rootfs-v4`.
5. As a researcher, I want the image form (metrics and motion-CLI root filesystems) checked against its recipe hashes and parent image, so that both lock forms get the same strictness.
6. As a researcher, I want a missing lock to be an error, never something a verifier creates on the spot, so that a lock always comes from a reviewed build.
7. As a researcher, I want the content-digest check to stay mandatory but run at most once per root filesystem per process, so that strictness does not make every stage slow.
8. As a researcher, I want the check to happen before any plan exists, including when I only ask to see the plan, so that `--emit-plan` cannot describe a launch that would be refused.
9. As a researcher, I want to say which code to mount, so that the plan mounts it read-only at `/experiment` and sets `PYTHONPATH` to it.
10. As a researcher, I want the source mount to be optional, so that a verifier that only needs code does not have to invent a source directory.
11. As a researcher, I want to name each extra input by its inside path and say whether it is read-only or writable, so that `/tmp/inputs`, `/tmp/native`, `/tmp/boxes` and the like are declared, not spliced.
12. As a researcher, I want a writable mount refused if it overlaps any other mount, so that no stage can write into its own code or inputs.
13. As a researcher, I want the same host directory mounted twice refused with a message naming both roles, so that mistakes like the motion verifiers' are explained, not just rejected.
14. As a researcher, I want read-only inputs allowed to nest, so that a stage can mount a whole scientific directory and one of its subdirectories without tripping the overlap rule.
15. As a researcher, I want to request a GPU by index, so that the plan carries exactly that device, the driver libraries and the GPU environment without my copying them.
16. As a researcher, I want GPU device and driver handling to live in one place shared with the Bazel launcher, so that a driver change is fixed once.
17. As a researcher, I want to add environment variables by name, so that settings like `CUBLAS_WORKSPACE_CONFIG` are declared on the plan.
18. As a researcher, I want the plan to start from a clean environment with a private home and no user site packages, so that no host setting leaks into evidence.
19. As a researcher, I want a launch plan I can read as data (mounts by role, devices, environment, working directory, command), so that I can inspect and compare plans without parsing strings.
20. As a researcher, I want the plan turned into a sandbox command line only when it launches, so that nothing else depends on the command-line shape.
21. As a researcher, I want stages that today replay an old receipt's command to get a fresh GPU launch plan instead, so that the balanced16 sustained run no longer depends on the shape of a receipt from another run.
22. As a researcher, I want the root-mount swap used by resource bundles expressed as a plan option, so that it is checked by the same overlap and lock rules.
23. As a researcher, I want `detection/training_box_replay.py` to use a launch plan, so that its hand-written sandbox gains the overlap check and `PYTHONPATH` it lacks.
24. As a researcher, I want the motion verifiers and the scientific cohort to run again, so that their gates mean something.
25. As a researcher, I want receipts to record a launch plan by mount role and digest, so that a receipt describes what ran, not where it ran.
26. As a researcher, I want the code mount identified by its source snapshot digest, so that it lines up with source pins (ADR 0001).
27. As a researcher, I want the root filesystem identified by its runtime lock digest, so that a receipt names the exact runtime it used.
28. As a researcher, I want each read-only input identified by a digest of its contents, so that a receipt can be checked again from the inputs themselves.
29. As a researcher, I want the output mount recorded by role only, so that receipts do not record a temporary host path.
30. As a researcher, I want the GPU recorded by requested index and the device's identity, so that GPU sharing can be audited without device paths.
31. As a researcher, I want receipts written before this change, with their command lines, to stay readable, so that historical evidence still verifies.
32. As a researcher, I want one reader that accepts both old command-line receipts and new plan receipts, so that audits do not branch on receipt age.
33. As a researcher, I want stage, retention and checkpoint audits to read mounts from the plan record, so that they stop scanning command lines.
34. As a researcher, I want semantic-recovery receipt checks to read the plan record, so that they stop checking for flag strings.
35. As a researcher, I want the live-gate support semantic-layout ticket 29 adds to `insula` built on launch plans, so that live gates are one more caller, not another launch shape.
36. As a researcher, I want `insula/entry` to be a thin command-line face of the module, so that `enter.sh` and the module cannot drift.
37. As a researcher, I want the Bazel launcher to build its plan with the module, so that Bazel inside Insula gets the same lock check as every gate.
38. As a researcher, I want `insula/entry` to default to the current CPU root filesystem, not `rootfs-v2`, so that running it without flags uses what the rest of the repository uses.
39. As a test author, I want to assert on a plan's mounts, devices and environment as data, so that tests stop slicing command lines.
40. As a test author, I want a fixture lock in each form and a tiny fixture root filesystem, so that lock checking is tested offline.
41. As a test author, I want a live test, tagged `requires_live_gate`, that runs a trivial command through a real plan in the current CPU root filesystem, so that the rendering is proven to work in a real sandbox.
42. As a test author, I want a GPU live test, tagged `requires_gpu`, that runs through a GPU plan on GPU 1, so that GPU device handling is proven without the sustained run.
43. As a maintainer, I want the command-line form of `launch_plan` deleted at the end, so that no new caller can go back to splicing.
44. As a maintainer, I want frozen code under `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/` left alone, so that retained procedures stay exactly as they were.
45. As a maintainer, I want the balanced16 sweep re-admitted once, after both this migration and the blob-store migration, so that its admission binds the code that will actually run.

## Implementation Decisions

- **Location and shape.** The launch-plan module lives in `insula`. It absorbs `insula/sandbox_plan.py`, the lock reading in `insula/entry.py` and `insula/runtime_identity.py`, and the GPU device and driver handling now in `insula/bazel_launcher.py`. Its interface:
  - **Load a runtime lock:** given a root filesystem, it returns a checked runtime lock, or raises a lock error that names the field that failed.
  - **Build a launch plan:** given a runtime lock, code, optional source, output, named inputs (inside path to host path and mode), an optional GPU index, extra environment and a command, it returns a launch plan or raises a plan error.
  - **Read a plan:** a plan exposes its mounts by role, devices, environment, working directory and command as data.
  - **Render a plan:** the plan gives its sandbox command line for the one place that executes it.
  - **Record a plan:** the plan gives its receipt record by role and digest.

  Nothing else is public.
- **Lock forms.** One checker handles both forms.
  - **Recipe-digest form:** it requires `schema_version` 1 and compares `dockerfile_sha256` and `requirements_sha256` (and `test_tools_requirements_sha256` when present) with the committed recipe files named for that root filesystem. It also checks the Bazel version and binary digest when present, and the content digest.
  - **Image form:** it requires `image_id`, `recipe_hashes` matching the committed recipe files, the parent image when one is named, and the content digest.

  The mapping from root filesystem to its recipe files lives in the module. No existing lock file is rewritten.
- **Content digest cost.** The full content digest stays mandatory. The module caches the verified result per root filesystem path and lock digest for the life of the process. The first ticket measures the cost on `rootfs-v4` and `rootfs-v6` and records it.
- **Mount rules.**
  - The rootfs is mounted read-only at `/`.
  - The code is read-only at `/experiment` and becomes `PYTHONPATH`.
  - The optional source is read-only at `/source`.
  - The output is writable at `/outputs`.
  - Named inputs go at caller-chosen inside paths under `/tmp`, `/opt`, `/srv` or `/mnt`.
  - `/proc`, `/dev` and a tmpfs at `/tmp` come after the inputs, in the order the current plan uses.
  - No host directory may be mounted twice, and no writable mount may overlap any other mount. Read-only mounts may nest.
  - Plan errors name the two roles that collide.
- **Environment.** The plan clears the environment. It sets the private home, `PATH`, `PYTHONNOUSERSITE`, `PYTHONDONTWRITEBYTECODE` and `PYTHONPATH` as the live-gate plan does today. Extra environment is added by name, and a name that collides with a module-owned variable is an error.
- **GPU.** A GPU request names one index. The module adds that device, the control and UVM devices, the driver libraries under `/driver` and the GPU environment, using the code now in the Bazel launcher, including its `SUREAL_BAZEL_GPU_DEVICES` override. The module does not choose a GPU; callers pass the index they were told to use. In this program that is GPU 1.
- **Root-mount swap.** The resource-bundle case (`resources/retention.py`) becomes a plan option that replaces the single root mount with read-only per-entry mounts of the same root filesystem, under the same lock check.
- **Receipt record.** A plan's receipt record lists:
  - the runtime by lock digest and lock form;
  - each mount by role, inside path, mode and digest. Code uses the source snapshot digest when the caller supplies one, otherwise a content digest. Read-only inputs use a content digest. Output and tmpfs mounts carry no digest.
  - the GPU by requested index and device UUID;
  - the environment;
  - the command.

  It holds no host paths. New receipts carry this record in place of a command line.
- **Old receipts.** `resources/command.py` keeps its command-line parser, renamed for its one remaining job: reading receipts written before this change. A single reader returns mounts by inside path for both receipt forms, and the stage, retention, checkpoint and semantic-recovery audits use it.
- **`insula/entry`.** It becomes the command-line face of the module. It checks the lock first, then emits or executes the plan. Its default root filesystem becomes the current CPU root filesystem the rest of the repository uses.
- **Bazel launcher.** It builds its plan through the module, keeping its workspace, cache and resolver mounts as named inputs, and gains the recipe check it lacks today.
- **Migration order.**
  1. Core.
  2. Batches that each depend only on the core.
  3. The receipt-reading audits.
  4. Deletion of the command-line form.

  Tickets that touch the retention publishers, `resources/retention.py` or the sustained run wait for blob-store ticket 11, because the blob-store migration rewrites those files. The sustained-run ticket blocks blob-store ticket 12, so balanced16 is re-admitted once after both migrations.
- **Ticket 29.** Semantic-layout ticket 29 may add minimal live-gate support to `insula`. A later ticket here rebuilds it on launch plans.
- **Frozen code.** `research/`, `studies/*/procedure_records/` and `studies/architecture/harness/` keep their launches. The harness learning-curve and checkpoint scripts that replay receipt commands stay as they are.

## Testing Decisions

- **One seam.** Tests go through the launch-plan module's interface: load a runtime lock, build a plan, read the plan as data, and record it. They assert on mounts by role, devices and environment, never on command-line strings. The only test that looks at a command line checks that rendering keeps every mount, device and variable in the order the sandbox needs.
- **Offline fixtures.** A tiny fixture root filesystem with a lock in each form, plus fixture recipe files, cover:
  - every lock-check failure: wrong schema, wrong content digest, stale Dockerfile, stale requirements, wrong recipe hash, missing parent, missing lock;
  - the per-process cache;
  - every mount rule: duplicate directory, writable overlap, read-only nesting allowed;
  - the environment collisions;
  - the GPU additions, with a fake device list through the existing override.
- **Live tests.** One test tagged `requires_live_gate` runs a trivial command through a real plan in the current CPU root filesystem. One test tagged `requires_gpu` runs a trivial CUDA query through a GPU plan on GPU 1. The overlapping-mount ticket's acceptance runs the motion verifiers and the scientific cohort for real, under `requires_live_gate`.
- **Receipt reader.** It is tested with a retained old receipt (command-line form) and a freshly recorded plan, and must return the same mounts by inside path for equivalent launches.
- **Callers.** Each migrated caller's tests stop faking `launch_plan`. A caller either gets a real plan built against a fixture lock, or its test asserts on the plan it built.
- **Prior art:**
  - `insula/bazel_wrapper_test.py` already asserts on mount lists from `--emit-plan`. That is the style to follow.
  - `insula/runtime_identity_test.py` tests content digests.
  - `insula/cpu_rootfs_build_test.py` and `insula/build_gpu_bazel_rootfs_v6_test.py` show the fields each lock form carries.
  - `insula/entry_test.py` and `training_execution/sustained_controller_backend_test.py` are examples of the string-slicing tests to replace.

## Out of Scope

- Changing any frozen code or any retained receipt.
- Rewriting existing lock files, or rebuilding root filesystems. Semantic-layout ticket 29 owns the CPU rebuild.
- Choosing which GPU a run uses. That stays the caller's instruction; this program uses GPU 1 only.
- Systemd scopes, process-group kill and stage timeouts. These stay with `resources/stage.py` and the run controller.
- Moving any blob storage. That is the blob-store spec.
- Performance work beyond caching the content digest per process.

## Further Notes

- The survey behind this spec counted about 51 active Python files that mention a lock file and about 47 that build or splice a sandbox command line, outside frozen areas. Counts are approximate; the migration tickets list their files.
- The lock-form split is by form, not by GPU or CPU: GPU `rootfs-v6` uses the recipe-digest form like CPU `rootfs-v4`. The image form is used by the metrics and motion-CLI root filesystems.
- `admit_sustained.py` and `sustained_controller_backend.py` also mount a copy of the runtime lock at `/tmp/runtime-lock.json` and point `SUREAL_SOURCE_SNAPSHOT_STORE` at a local snapshot directory. The first becomes an ordinary named input. The second changes under the blob-store spec.
