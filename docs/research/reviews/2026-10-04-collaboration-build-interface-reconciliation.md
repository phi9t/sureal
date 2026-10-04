# Task49 build-interface reconciliation

This is a normative, documentation-only correction of task49's build command
and input roles. It takes effect after independent review and mainline landing.
It preserves the live acceptance, source/retention, resource and scientific
contracts. It adds no code alias, runtime behavior or worker authority.

The original approved plan has SHA-256
`f8b74add792c297b403c97a8562f7b1213adeec63f2ed7f85c7e53abc9e69af3`, retained in
Git history and immutable source X `cdc2206d482ba4b9f62ffef41a87dd6e5da5d26f`.
Its `build-runtime --recipe --gate-admission --inputs --output` command is not
implemented. X supplies `build --materialization --packages --tools --output`.
The [updated plan](../../superpowers/plans/2026-10-03-sureal-two-worker-collaboration.md)
and [tooling guide](../../collaboration/README.md) give the operative command.

| Actual input | Binding and authority |
| --- | --- |
| `--materialization` | Independently verified retained candidate/tree/source; its Dockerfile and requirements lock select the recipe, base digest and package pins |
| `--packages` | Explicit offline directory; the complete `.deb` union and every hash must match that candidate lock |
| `--tools` | Admitted tool manifest; the builder verifies the actual Docker path/hash and retains literal build/export argv |
| `--output` | Fresh owned directory outside source; actual context, image/container identity, archive, inventory and manifest are retained |
| Prebuild admission | Lead verifies source/review/tool/input/output/resource authority before invocation; a build cannot admit itself |
| Runtime GateAdmission | Assembled from actual build/rootfs/helper/resource pins after building and before live execution; independent audit decides acceptance |

The independent interface reviews confirmed the equivalent bounded build
capability and the literal documentation mismatch. They did not waive the old
command or prove it executed. Review receipts remain external and immutable:
`/data02/home/philip.yang/devx/tmp/collab49-build-interface-review-20261004.json`
(SHA-256 `8ef772e8f24a8d109953f1f2674e4cb4abd6290da373cfc57bbf68a5430d7b83`)
and `/data02/home/philip.yang/devx/tmp/collab49-build-contract-review-20261004a.json`
(SHA-256 `84514f812b59e170fea6afcf15c7c0de62777c219e62f806487f5d4339b672b7`).

Original v5 actual inner build/export/context evidence and six-case A3 acceptance
remain unchanged. A structured outer v5 builder invocation was not retained;
no such claim is made. A separately recorded fresh exact-X reproduction of the
actual `build` CLI returned exit0 and `NOT_AUDITED`: outer command receipt
`/data02/home/philip.yang/workspace/.sureal-collab/bootstrap49-20261004a/build-interface49-reproduction-v1/actual-command.json`
SHA-256 `b9ad61808358fa2e3313ef4d1ff39814dcf41b0ac8cabd56d5d2497830bec811`;
new build manifest in `runtime-build49-v6-interface-reproduction` SHA-256
`b3325d17374ec084d02814b18db26d157c5abff0a9afb4169ca2407bfb15d48a`.
This reproduction is documentary evidence, not a new rootfs/kernel/milestone
acceptance or a replacement for original v5 evidence.

Land this scoped correction D after implementation X post acceptance. Generate
and review initial task definitions at D before real bootstrap/import; M has
sole parent D and map `source_commit` D. Re-pin the revised plan explicitly.
X, its original gate/post, actual landing and source remain historical inputs;
X must be an ancestor of M. M still needs its own fresh live gate, independent
review, exact landing/post and both-role closure. Task49 remains open until
those proofs exist. Models44–48 retain pending-plan/no-dispatch holds.

The existing user authorization applies to this scoped documentary correction.
The lead explicitly adopts the corrected plan content SHA-256
`7dd638f180d041c585c35a1a5e68b65cc220bcc0033353456a8df5623562d868`
after independent review/mainline landing. The original execution-authorization
file stays byte-identical: it is an immutable artifact of the original gate.
No historical admission/reference is rewritten to point at this revision.
