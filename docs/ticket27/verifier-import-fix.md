# Ticket 27 Verifier Import Fix

## Change

`autonomy/training_execution/audit_sustained_transition.py` no longer imports
`sustained_chunk_reference` through normal import resolution. The verifier now:

1. Resolves `Path(__file__).resolve().with_name("sustained_chunk_reference.py")`.
2. Requires that sibling with `require_regular_file`.
3. Loads it with `importlib.util.spec_from_file_location`.
4. Uses the loaded module's `reference_chunk`.

This keeps the verifier standalone under `/tmp/verifier` and does not mutate
`sys.path`.

## Regression Coverage

Added `autonomy/training_execution/audit_sustained_transition_import_test.py`.
It copies `audit_sustained_transition.py` and a sentinel
`sustained_chunk_reference.py` into a temp verifier directory, runs the copied
audit with `runpy.run_path` from a different cwd and without the verifier
directory on `sys.path`, and confirms the sentinel sibling is the module used.

The same test also places foreign top-level and package copies on `sys.path` so
fallback imports from `/experiment` would fail the test. A missing sibling must
raise the `require_regular_file` validation error.

Red check before the fix:

```text
./bazelw test --noexperimental_collect_system_network_usage \
  --nocache_test_results --test_output=errors \
  //autonomy/training_execution:audit_sustained_transition_import_test
```

Result: failed as expected. The temp verifier run either raised
`ModuleNotFoundError: No module named 'sustained_chunk_reference'` or loaded the
foreign `sustained_chunk_reference.py` placed on `sys.path`.

Green checks after the fix:

```text
./bazelw test --noexperimental_collect_system_network_usage \
  --nocache_test_results --test_output=errors \
  //autonomy/training_execution:audit_sustained_transition_import_test
```

Result: passed, 1/1 test target.

```text
./bazelw test --noexperimental_collect_system_network_usage \
  --nocache_test_results --test_output=errors \
  //autonomy/training_execution:sustained_controller_backend_test
```

Result: passed, 1/1 test target.

```text
./bazelw test --noexperimental_collect_system_network_usage \
  --nocache_test_results --test_output=errors //autonomy/...
```

Result: passed, 155/155 test targets.

## Execute Worker Import Audit

Audit method: parse each target script for bare imports whose top-level name is
a sibling `.py` file in that script's directory. These are the imports that
would have depended on `python worker.py` putting the script directory at
`sys.path[0]`.

| Script | Used by | Verdict |
| --- | --- | --- |
| `autonomy/training_execution/train_sustained.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/training_execution/audit_sustained_transition.py` | `sustained_controller_backend.py` verifier at `/tmp/verifier/audit_sustained_transition.py` | Fixed. Loads verifier sibling `sustained_chunk_reference.py` explicitly by file path. |
| `autonomy/training_execution/replay_sustained.py` | `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/training_execution/audit_sustained_loss.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/evaluation/prepare_sustained_v3.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/evaluation/audit_proposals_sustained_v3.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/evaluation/metrics_sustained_v3.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/evaluation/audit_metrics_sustained_v3.py` | `sustained_controller_backend.py`, `admit_sustained.py` | No bare sibling imports. Package imports only. |
| `autonomy/resources/archive_worker.py` | resource retention live archive checks through the resource runner path | No bare sibling imports. Its separately pinned helper is loaded by explicit file path from `/tmp/resource-archive.py`. |

## Other `runpy.run_path` Targets

Production call sites outside `resources/execute_worker.py`:

| Caller | Target | Verdict |
| --- | --- | --- |
| `autonomy/dataset/verify-scientific-replay.py` | `autonomy/dataset/verify-archive-dataset.py` | Target is read to extract `REPLAY`; no bare sibling import dependency found in the target. |
| `autonomy/motion/ingestion/pooled_finite_fixture.py` | `/experiment/check.py` | External mounted check script, not a repo sibling module. The repo fixture imports only returned `verify` and `aggregate` symbols. |

Test-only `runpy.run_path` callers observed:

| Caller | Target | Verdict |
| --- | --- | --- |
| `autonomy/evaluation/metrics_sustained_v3_test.py` | temp worker path | Test harness only. |
| `autonomy/training_execution/audit_sustained_transition_test.py` | local `audit_sustained_transition.py` | GPU guard test only. |
| `autonomy/training_execution/sustained_worker_guard_test.py` | local `train_sustained.py`, `replay_sustained.py` | GPU guard test only. |

## Verifier Pinning

`sustained_controller_backend.py` still copies both verifier files from the
source-frozen package at case creation:

```text
audit_sustained_transition.py
sustained_chunk_reference.py
```

Verifier pins are computed dynamically from the copied files:

```text
self.verifier_pins={str(p):sha(p) for p in self.verifier.iterdir()}
```

The guard then requires exactly those two verifier filenames and compares each
copied verifier digest to `source_pin(self.pins, "training_execution/" + name)`.
There is no hard-coded verifier hash in this path, so the new verifier bytes are
picked up automatically when the package snapshot is created.

## Not Checked

No GPU, HDFS, container build, or live admission was run in this worker. The
worker launch forbids GPU/network/HDFS/real-data writes, so verification was
limited to the local Bazel tests above and static source audit.
