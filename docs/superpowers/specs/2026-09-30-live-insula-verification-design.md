# Live Insula verification and implementation gates

Date: 2026-09-30. Status: user-directed specification.

Every implementation milestone must execute live inside its locked dedicated
Insula, exercise the implemented behavior and independently validate outputs.
Host unit tests support implementation but cannot establish completion.

## M0 — Prove Insula itself works

M0 is the first implementation milestone and blocks every subsequent live gate.
It requires no Waymo data, model, geometric conversion or native-table replay.
Its deliverable is a functioning reproducible runtime and a verified live receipt.

### Runtime acceptance

- Build/materialize the dedicated CPU image/rootfs and install the hash-locked
  runtime dependencies. Verify image/rootfs identity and package versions.
- Enter the rootfs and run a real process. Confirm the process uses the expected
  interpreter and dependency paths inside the rootfs, not a host fallback.
- Exercise real NumPy computation, a small synthetic Parquet write/read and a
  synthetic image encode/decode. Validate values after reopening artifacts.
- Prove the offline namespace cannot connect to a reachable host test listener;
  test the host listener first so an unavailable server cannot fake isolation.
- Prove inputs are readonly, the designated output mount is writable, HOME is
  private, unintended host paths are absent and credentials are not mounted.
- Inject a wrong runtime lock, missing rootfs, failed check and failed command.
  Each must return nonzero and prohibit successful promotion/completion.
- Repeat live entry from the same locked runtime and validate its receipt.

Mount the fixture inputs readonly and the bounded staging output writable.
Keep build/network provisioning separate from offline execution. Rootfs identity
must cover its executable/dependency contents, not just a text marker. A CPU
M0 does not establish a GPU runtime: when GPU work begins, an additional live
runtime gate must prove the selected Torch/JAX device and actual device computation.

M0 passes only when all required checks pass in a live runtime. If the runtime
cannot build or start, record blocked with the exact command/error; do not begin
by calling the host geometry implementation a completed milestone.

## Milestone dependency sequence

| Milestone | Prerequisite | Required live evidence |
|---|---|---|
| M0: Insula runtime | Available build/isolation capabilities | Runtime entry, locks, synthetic IO/computation, mount/network boundaries, failure behavior |
| M1: Native data replay | Verified M0 | Real acquired Parquet slice, source checksums and unchanged native-row manifest reconciliation |
| M2: Mathematical geometry core | Verified M0 | Independent analytic fixtures, Lie identities, manifold Jacobians, boundary/singularity and covariance checks |
| M3: Sensor adapters and reconstruction | Verified M1 and M2 | Real sensors/returns, calibrated reconstruction, pixel/projection/semantic identity conservation |
| M4: Sensor-to-scene inspection | Verified M3 | Validated geometry artifacts, representative views, coverage, timing/association limitations |
| M5: Reproducible R0 closeout | Verified M1–M4 | Two full selected-cohort runs, independent validation and reproducibility receipts |

M1 and M2 can be worked independently after M0. Preparation or host tests do not
close their milestones. Model research starts after verified R0, with task-specific
live gates rather than treating R0 as blanket proof of later implementations.

## Verifier and evidence contract

Declare each milestone's inputs, changed behavior, assertions, artifacts and
resource limit before execution. Capture exact command/arguments and live logs.
Write a schema-versioned receipt with milestone ID, UTC start/end, command exit
status, code/source/runtime hashes, observed versions, individual assertion
results, resource observations and artifact hashes/paths. M0 uses synthetic
fixture hashes; subsequent data milestones include cohort/source receipts.

Validate artifact hashes, schema, required assertion completeness and candidate
code/runtime/input identity independently. A historical receipt cannot close
changed code. Runtime content locks and source checks are rechecked before live
execution. An exit-zero command is insufficient when any required assertion is
missing or false. Capture failure evidence in a separate bounded failed-run
record; success artifacts remain staged until independent validation passes.

States: planned → implementing → implemented-awaiting-live-verification →
verified-complete. Blocked records identify a prerequisite/error and preserve
work. No silently skipped check, mock execution, host fallback or metadata flag
can replace a required live check. Keep logs/large artifacts outside git; commit
small recipes, locks and reviewable evidence summaries. Completion claims must
name the verified candidate and its receipt.

## Later implementation examples

Geometry: analytic/numerical fixtures run live; native adapters additionally
reconstruct real measurements and reconcile original sensor/return/pixel keys.
Views alone do not prove geometry. Dataset/evaluation adapters: live conversion,
export and independently checked fixture results without TensorFlow.

Models: live forward/backward on representative inputs, finite outputs/losses/
gradients, actual declared CPU/GPU execution, prediction export and independent
validation. These are engineering gates. Small-cohort overfit, held-out metrics,
multiple seeds and controlled ablations remain separate scientific requirements.

## Current status

Existing geometry code is implemented and host-tested, awaiting live verification.
Earlier host-library bubblewrap tracer evidence does not close M0's dedicated
rootfs contract. Recheck runtime capabilities under current permissions; prior
permission failures are historical evidence, not a permanent assumption.
