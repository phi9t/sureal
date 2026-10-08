# 01: Launch-plan module with full runtime-lock checking

**What to build:** A researcher loads a runtime lock and gets back a launch plan describing one execution inside a dedicated Insula. The plan uses code, an optional source, an output, named inputs, environment and a command, and the researcher can read it as data, render it to run, and record it in a receipt. The lock is checked in full in either form before any plan exists. `insula/entry` and the Bazel launcher are rebuilt on the module, so both existing entry points prove it end to end. See `.scratch/launch-plans/spec.md` and autonomy ADR 0003.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The module in `insula` exposes only these operations: load runtime lock, build plan, read plan as data, render plan, record plan. It absorbs `sandbox_plan`, the lock reading in `entry`, and `runtime_identity`'s content check
- [ ] Both lock forms are checked in full: the recipe-digest form (`rootfs-v4`, `rootfs-v6`: schema, Dockerfile, requirements, test-tools requirements when present, Bazel version and binary when present, content digest) and the image form (metrics and motion-CLI: image id, recipe hashes, parent image when named, content digest). A missing lock is an error. Each failure names the field
- [ ] The content digest is cached per root filesystem path and lock digest for the life of the process. The time to check `rootfs-v4` and `rootfs-v6` uncached is measured and recorded in the ticket
- [ ] Mount rules hold: no host directory mounted twice, no writable mount overlapping any other, read-only mounts may nest, and errors name both roles. The source mount is optional. Named inputs are restricted to `/tmp`, `/opt`, `/srv` and `/mnt`. Extra environment that collides with a module-owned variable is an error
- [ ] The receipt record lists the runtime by lock digest and form, mounts by role, inside path, mode and digest, the environment and the command, with no host paths
- [ ] `insula/entry` checks the lock before emitting or executing a plan, and defaults to the root filesystem the Bazel launcher uses. The Bazel launcher builds its plan through the module and gains the recipe check. Its existing structural tests still pass
- [ ] The current CPU, GPU, metrics and motion-CLI root filesystems are named in exactly one place that every launch reads. Semantic-layout ticket 29 left the current CPU root's name repeated in six modules (Bazel launcher, resource backend, sustained admission, sustained controller, M0 receipt, semantic-recovery runtime), and `insula/entry` still defaults to `rootfs-v2`
- [ ] Offline tests with fixture locks in both forms and a tiny fixture root filesystem cover every lock failure, the cache, every mount rule and environment collisions, all asserting on plans as data
- [ ] A `requires_live_gate` test runs a trivial command through a real plan in the current CPU root filesystem and records its pass
- [ ] Default CPU suite, `--config=cuda` suite (GPU 1 only, `CUDA_VISIBLE_DEVICES=1`) and `//parallax/...` pass with counts recorded
