# M0 live runtime execution ledger

2026-09-30: progress; M0 remains implementing, not verified-complete.

- Current Docker daemon 26.1.4 and actual bubblewrap unshare-all entry work. Prior permission failures do not describe current capability.
- Added a dedicated CPU Dockerfile using python:3.12-slim-bookworm pinned at sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e. Existing requirements-tracer.lock installed with pip --require-hashes.
- Built image sha256:5a2261db0dd5022d09a34f4aa8e3b81128cf83de132d5a5e1a20dadf396eed1d and exported rootfs outside git under the Waystone cache. Rootfs content identity 076f58ffecd1aca1cf1646545b49d23769c723dd98891246559abb577f3df0a6.
- Rootfs identity includes paths, file contents, modes and symlink targets. Two tests observed failing before implementation, then passing for mutation/mode/link and missing-rootfs rejection.
- Actual offline bubblewrap process entered dedicated rootfs, used /usr/local/bin/python 3.12.14 and computed NumPy arange(10).sum()==45. Imports report NumPy 2.5.3, Arrow 25.0.1, Pillow 12.3.0. This is preliminary live entry evidence, not the complete M0 receipt.
- build.sh refuses replacement of an existing rootfs; shell syntax and git whitespace checks passed.

Remaining: tested entry wrapper with runtime lock validation; synthetic Parquet/image write and independent reopen; reachable-host-listener network negative control; readonly/private/writable mount assertions; wrong lock/missing rootfs/failed assertion/child failure injections; two-run independent receipt checking. Do not close ticket 01 or start downstream milestone execution from this partial evidence.

## Full live probe progress

Added enter.sh and insula_entry.py: offline unshare-all, cleared environment, readonly rootfs/source/code, bounded writable output, private HOME, recipe/content verification, overlap rejection. Two entry-plan tests failed before implementation and now pass.

First verifier execution exposed missing readonly-rootfs mount destinations; added /experiment, /source and /outputs to Dockerfile and built rootfs-v2 instead of overwriting the original. Image identity is now sha256:e796dd50d0067485ca3fb4d729737e33edab9bee62a6644ee97c809112bef2c0.

verify-m0.py completed two live synthetic producer/independent-reopen invocations. Both checked network blocking with a reachable host listener, readonly source, writable output, private HOME, absent host paths and TensorFlow. Numeric, Parquet and PNG artifacts match across runs. Wrong-lock, missing-rootfs, failed-assertion and child-exit failures returned nonzero and emitted no promoted synthetic outputs.

Preliminary receipt: ~/.cache/waystone/waymo-perception/insula/m0-live-20260930-a/receipt.json. m0_receipt.py independently verified current captured candidate hashes, rootfs content, required assertion completeness and artifact hashes. M0 remains implementing pending receipt-checker tamper/regression tests and a fresh candidate run including that checker, plus final closure audit. No later milestone executed from this preliminary receipt.

## M0 closure

Current receipt m0-live-20260930-c passes independent validation after two live runs and four failure injections. Receipt checker rejects empty code inventory, missing assertion, changed log/artifact and missing expected artifact; its valid-receipt control passes. Ten targeted tests pass (six receipt, two rootfs identity, two entry plan). The compact m0-verified.json records receipt hash, runtime lock and resource observations. Ticket 01 is verified-complete; no GPU or scientific result is implied.

M1 continuation: full native inspection launched through enter.sh in verified rootfs-v2, output cache/insula/m1-output/native-replay-a. Running exec session 19012; poll this handle before considering another launch. M1 remains implementing until independent native reconciliation and its receipt are complete.
