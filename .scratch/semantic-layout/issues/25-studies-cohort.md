# 25: Studies batch: the 16-scene cohort study

**What to build:** The cohort study is dissolved the same way: training loops, losses, metrics, scoring and audits that are reusable live in their concept, the sustained controller stays a runnable tool, and the study's procedure records live under the study's own directory.

**Blocked by:** 22 (Concept batch: `resources`), 24 (Studies batch: the fixed-batch suites and the experiment catalog)

**Status:** ready-for-agent

- [ ] Scope: the balanced and sustained training, scoring, admission, retention and audit code of the cohort study
- [ ] The sustained controller, its workflow, state and admission remain runnable and tested
- [ ] Procedure records of closed gates are exported as files and are not test targets
- [ ] The one upward import from the fixed-batch suite into the cohort study is gone
- [ ] Every module in scope lives in its concept directory and is imported by package path; no `sys.path` manipulation remains in the moved code
- [ ] Each moved test sits beside its module as `foo_test.py` and is a Bazel test target
- [ ] Bazel visibility lets only the concepts above this one depend on it
- [ ] File digests and regular-file checks in the moved code come from the evidence module, not local copies
- [ ] The same test modules pass through the wrapper as before the batch, and the pin report for the batch is attached to the ticket
- [ ] Files under `research/` are unchanged
