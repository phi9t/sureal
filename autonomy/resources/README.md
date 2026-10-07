# External resource verification

This layer measures the actual processes without changing the frozen model,
loss, decoder or evaluator source bytes. It also owns the bounded replay
continuation comparators that bind fresh executions back to their native
receipts.

`run_scoped` requires an existing, exclusive `sureal-sustained-*.scope` with
the exact requested `memory.max`, zero swap, and zero OOM counters. It refuses
an uncapped invocation before starting the worker. The host becomes a Linux
child subreaper, waits for completed launcher helpers and includes their
`wait4` peaks. Any surviving stage process prevents admission and is killed
using a PID descriptor after verifying membership in the owned scope. The
same cleanup applies to detached children surviving a timeout. Failed stages
never receive `resource_admission`.

`execute_worker.py OUTPUT_DIR ORIGINAL_WORKER [ARGS...]` runs the unchanged
worker script with its original argv. It also becomes a subreaper. All
worker-created processes must complete and be waited for;
running children and completed double-fork orphans both prevent a successful
`worker-resource.json`. This contract intentionally excludes detached model
workers and persistent multiprocessing loaders. The frozen workers use
waited subprocesses. Integration must separately verify native model/state
equivalence rather than infer it from this wrapper.

`admit_worker` checks the exact executed command, worker argv, lifecycle,
kernel controls, measured elapsed time and two separate memory observations:
the launcher's largest waited-process peak and the worker's SELF / largest
waited-CHILDREN peaks. Each peak is in KiB. Their maximum is a reported peak,
not simultaneous summed process-tree RSS. The external kernel cap supplies
aggregate enforcement; its memory charge can include cache and can censor a
run earlier than a per-process RSS bound would. Raw `measure` output alone is
insufficient for resource admission.

Current evidence:

- `research/sustained-resource-lifecycle-suite-green-v2-verified.json`: all
  15 resource tests executed in live Insula, with source and log hashes.
- `research/sustained-resource-scoped-lifecycle-green-v3-verified.json`:
  real capped detached-success refusal, detached-timeout cleanup, and valid
  TensorFlow-free Insula worker under 128 MiB.
- `research/sustained-resource-foundation-current-verification.json`:
  exact source/artifact readback and fresh identities of the actual runtimes.

The earlier capped fixture `sustained-resource-scoped-live-v2-verified.json`
incorrectly attached the GPU runtime lock to a CPU-rootfs command. Its runtime
verification claim is invalidated explicitly in the current verification;
the raw receipt is retained. The native score1000 replay matches metrics and
protobuf bytes under 16 GiB but used an earlier frozen resource version. It
is a bounded diagnostic, not admission under the current lifecycle gate.
