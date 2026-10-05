# Semantic layout: `parallax/` and `autonomy/` under Bazel inside Insula

Status: ready-for-agent

Governing decisions: `docs/adr/0001-directories-express-concepts.md`, `docs/adr/0002-bazel-runs-inside-insula.md`, and the autonomy ADR "A source pin refers to a source snapshot, not to the working tree". The layout standard is `docs/repo-structure.md`. Vocabulary follows `CONTEXT-MAP.md`.

## Problem Statement

The two research programs in this repository live under `experiments/` in directories whose names cannot be imported (`3d-pathway`, `waymo-perception`) and whose internal structure says how code is run, not what it is about.

In the perception program this has four concrete costs:

- **Nothing can be edited in place.** 652 of 694 tracked files outside `research/` are pinned by at least one receipt, and a source pin currently refers to the working tree. Changing a file leaves its receipts describing bytes the tree no longer holds, so every change is made by copying the file to a `_v2` or `_v3` name.
- **The directories hide the subject.** `gpu/` is named after a runtime, `tests/` and `scripts/` after a kind of file, `tier1/`, `advanced/` and `cohort/` after stages of the research program, and `pipeline/` holds 107 unrelated modules. The C++ evaluators are split from the Python that drives them.
- **Imports depend on path manipulation.** There are 91 `sys.path` insertions, and 14 module names exist in more than one directory.
- **There is no single build or test entry point.** Thirteen directories hold test modules, each run a different way. Twenty-six test modules need torch and can only run inside a live gate. Shared behaviour is copied: a file-digest helper is defined in 61 files.

## Solution

The repository follows the semantic polyglot layout. `parallax/` and `autonomy/` are top-level components, organised internally by concept. Bazel 9.2, running inside an Insula rootfs through one wrapper command, is the only way to build and test them. A source pin refers to a source snapshot stored in HDFS, so the working tree is free to change.

From a contributor's point of view:

- One command runs every test of a component inside Insula, including the torch tests.
- A file can be edited, moved or deleted without breaking retained evidence.
- The directory a file lives in says which part of the system it belongs to.
- Imports are plain package imports resolved by the build graph.

## User Stories

Layout

1. As a contributor, I want the 3D reconstruction curriculum to live at top-level `parallax/`, so that it has an importable name and is a first-class component.
2. As a contributor, I want the perception research program to live at top-level `autonomy/`, so that ongoing work has one obvious home.
3. As a contributor, I want `parallax/` to keep its `pipeline/`, `insulas/`, `tests/` and `research/` directly beneath it, so that the curriculum's own structure survives the move unchanged.
4. As a contributor, I want code in `autonomy/` grouped by concept (sandbox entry, evidence, dataset, geometry, detection, segmentation, range view, camera, motion, resources, inspection, studies), so that I can find code by subject.
5. As a contributor, I want the C++ camera and motion evaluators to live in the same concept directory as the Python that drives them, so that one concept is not torn across languages.
6. As a contributor, I want model variants that today live in a directory named after the GPU runtime to live with the detector they vary, so that the directory name says what the code is.
7. As a contributor, I want library code from the study stages moved to the concept it implements, so that a detector loss is found under detection and not under a study name.
8. As a researcher, I want each study's one-shot procedure scripts kept together under a directory named for that study, so that the record of what was run stays legible.
9. As a contributor, I want each test to sit beside the module it tests as `foo_test.py`, so that I do not have to search a separate tree.
10. As an upstream maintainer of `surflo/`, I want that package untouched, so that the fork stays mergeable.
11. As a contributor, I want `submodules/`, `training/`, `configs/`, `install/`, the root `scripts/` and `tests/`, and the three smaller experiments left where they are, so that this change has a bounded blast radius.
12. As a reader of the repository, I want living documents, the agent guide, the context map, the contributing guide and the CI workflow to name the new paths, so that instructions I follow actually work.
13. As a reader of retained evidence, I want receipts and dated specs to keep the paths they were written with, so that history is not rewritten.

Build and test

14. As a contributor, I want one wrapper command that runs Bazel inside Insula, so that I never run a build on an unpinned host environment.
15. As a contributor, I want the wrapper to refuse to run when the rootfs does not match its recorded identity, so that I cannot build against the wrong image by accident.
16. As a contributor, I want the wrapper to print the sandbox command it would run without running it, so that I can inspect the isolation.
17. As a contributor, I want Bazel 9.2 already present in the rootfs, so that there is no separate tool to install.
18. As a contributor, I want every third-party package, including the Python interpreter and torch, to come from the rootfs, so that a build and a live implementation gate cannot disagree about a wheel.
19. As a contributor, I want Bazel's output base and caches kept in a git-ignored directory that persists between runs, so that repeat builds are fast.
20. As a contributor, I want network access during builds, so that Bazel module dependencies resolve without a separate capture step.
21. As a contributor, I want `test //autonomy/...` to run every unit test of the perception program, so that I have one definition of "the tests pass".
22. As a contributor, I want `test //parallax/...` to run the curriculum's CPU numerical contract, so that both components share one entry point.
23. As a contributor, I want torch-dependent tests to run under Bazel in the GPU rootfs when I opt in, so that I get feedback on model code without staging a live gate.
24. As a contributor, I want GPU and CUDA targets excluded from the default test run, so that the default works on the CPU rootfs.
25. As a contributor, I want tests that need a live-gate mount to be tagged and excluded by default, so that a missing mount is not reported as a failure.
26. As a contributor, I want imports to resolve through the build graph with no `sys.path` manipulation, so that which module I get never depends on the order directories were inserted.
27. As a contributor, I want a build failure when a concept directory imports from a concept above it in the declared layering, so that the dependency structure cannot erode silently.
28. As a contributor, I want Bazel visibility to be the mechanism that enforces layering, so that the rule lives in the build graph and not in a separate script.
29. As a CI maintainer, I want the publication workflow to keep passing after the renames, so that the portable gates remain the merge requirement.

Evidence

30. As a researcher, I want a source pin to refer to a source snapshot, so that editing a file does not invalidate evidence.
31. As a researcher, I want a source snapshot to contain exactly the transitive sources of the gate's build target, so that the snapshot is neither a whole-tree dump nor a hand-picked list.
32. As a researcher, I want the receipt to record the snapshot's digest, so that a receipt identifies its sources by content.
33. As a researcher, I want snapshots stored content-addressed in HDFS with exact readback on upload, so that they outlive the local cache.
34. As a researcher, I want to verify a receipt against its snapshot without the working tree, so that verification still works after the tree changes.
35. As a researcher, I want verification to fail clearly when a snapshot is missing or its bytes differ from the recorded digest, so that a broken record is never reported as verified.
36. As a researcher, I want one module that takes snapshots and verifies them, so that the seven existing hand-written freezing mechanisms can retire.
37. As a contributor, I want one shared way to digest a file and to check that a path is a regular, non-symlinked file, so that 61 copies of the same helper become one.
38. As a researcher, I want receipts written before this change left byte-identical, so that they remain honest historical records.
39. As a researcher, I want it stated which commands no longer verify old receipts against the tree, so that a failing legacy check is not mistaken for corrupted evidence.
40. As a researcher, I want the research journal's hash chain and content-addressed evidence store to keep verifying after the move, so that the journal's integrity is continuous.

Re-admission

41. As a researcher, I want the frozen balanced16 sweep re-admitted on the new paths, sources and rootfs before it resumes, so that its results are bound to code that actually exists.
42. As a researcher, I want the sustained-run guard to validate a source snapshot instead of an exact inventory of four directories, so that adding a file to the tree no longer blocks a run.
43. As a researcher, I want the architecture experiment runner to keep listing, showing, running and verifying experiments after the move, so that the documented experiment catalog still works.
44. As a researcher, I want the experiment tracker and journal commands to keep working from their new location, so that recording evidence is uninterrupted.
45. As a researcher, I want any check that compares a runtime lock with the previous rootfs digest identified and re-admitted on the new image, so that no gate silently runs on an unadmitted runtime.

Migration safety

46. As a reviewer, I want each rename done as a pure move with no content edits in the same commit, so that history follows the files and the diff is reviewable.
47. As a reviewer, I want the number of passing test modules to be the same before and after each structural step, so that a move is shown to change no behaviour.
48. As a reviewer, I want a report of which source pins a change touches, so that the evidence impact of each step is known before it lands.
49. As a contributor, I want the previous rootfs images left on disk, so that past receipts still find the digests they recorded.

## Implementation Decisions

Layout

- `experiments/3d-pathway/` is renamed to `parallax/` and `experiments/waymo-perception/` to `autonomy/`, each as one whole-directory move. `experiments/` keeps the three smaller experiments.
- Inside `autonomy/` the starting concept directories are `insula`, `evidence`, `dataset`, `geometry`, `detection`, `segmentation`, `range_view`, `camera`, `motion`, `resources`, `inspection` and `studies`. Names may be adjusted while moving code, but every directory must name a concept.
- The concept reorganisation is a separate step after the rename, done one concept at a time, lowest layer first.
- `research/` under each component is retained evidence and is moved with its component but never reorganised or rewritten.
- Python packages are importable from the repository root (`autonomy.detection...`, `parallax.pipeline...`). Bare cross-directory imports are removed.
- Tests are renamed to `foo_test.py` and moved beside the module they test as each concept is reorganised.

Procedure records

- A procedure record is a script that ran one gate or one study stage and wrote a receipt. Records of closed gates move under `autonomy/studies/<study>/` and are kept as records: they are exported from the build graph as files, are not test targets, and are not required to stay runnable. Re-running a closed gate means restoring its sources from history or from a snapshot.
- Tools that remain in use stay runnable and tested: the architecture experiment runner, the sustained-run controller and its resource backend, the experiment tracker and journal, the dataset acquisition and publication commands, and the viewer.
- The version-suffixed copies (`_v2`, `_v3`) are not merged in this work. Where a later version supersedes an earlier one that only a closed gate used, the earlier one moves to that study's records.

Build

- Bazel 9.2 with Bzlmod; the module file, its lock file and the Bazel version file sit at the repository root. The lock file is committed.
- Bazel packages cover `autonomy/` and `parallax/` only. Package boundaries follow concept directories; a build file is not added to every directory.
- Bazel is baked into a new version of the CPU rootfs and of the GPU rootfs, built from the existing image definitions and the existing hash-pinned requirement locks plus a checksum-verified Bazel binary. Existing images are not modified or deleted.
- The Python toolchain is the rootfs interpreter with the rootfs's installed packages. `rules_python` does not fetch third-party packages. uv remains the tool that authors the locks the rootfs is built from.
- One wrapper script at the repository level is the only entry point. It verifies the rootfs against its lock, enters the sandbox with a cleared environment and a fixed home, mounts the repository and the cache directory, and runs Bazel. It has a mode that prints the sandbox command without executing it. It selects the GPU rootfs when the GPU configuration is requested.
- Bazel's output base, repository cache and disk cache live in one git-ignored directory at the repository root, also listed in the Bazel ignore file.
- Network is available inside the sandbox during builds.
- Default test runs exclude targets tagged as needing a GPU or a live-gate mount. A named configuration includes the GPU targets.
- Layering between concept directories is enforced with Bazel visibility. The existing import-layering check is kept until visibility covers every concept, then removed.
- The C++ evaluators get Bazel targets where they build from sources in this repository. Evaluators that need the upstream Waymo sources keep their CMake build inside their dedicated rootfs.
- The viewer's web front end stays on its own npm toolchain.

Evidence

- One evidence module owns file digests, the regular-file check, source snapshots and their verification. Its interface is small: take a snapshot of a build target's transitive sources and return its digest; fetch a snapshot by digest; verify that a receipt's source pins match a snapshot.
- A source snapshot is a deterministic archive (stable member order, no timestamps or ownership) so that the same sources always produce the same digest.
- Snapshots are stored content-addressed, keyed by digest. Storage is behind an interface with two adapters: HDFS for real use, a local directory for tests. Upload uses exact readback, as the journal's publication already does.
- New receipts record the snapshot digest and the build target it was taken from. The schema of existing receipts is not changed and existing receipts are not rewritten.
- The sustained-run guard and the resource-source validator verify against a snapshot instead of requiring an exact inventory of directories and matching original path strings.
- The architecture runner's verification without a run identifier, which compares tracked receipts with the working tree, is retired. Verification with a run identifier already uses a snapshot and is kept.
- The seven existing freezing mechanisms are replaced by the evidence module as the tools that use them are moved.

Order of work

1. Bazel, the new rootfs versions and the wrapper, with the existing tree unchanged and existing tests running as Bazel targets in place.
2. The two renames, with path references updated.
3. The evidence module and snapshot-based verification.
4. The concept reorganisation inside `autonomy/`, one concept at a time.
5. Re-admission of the balanced16 sweep.

Step 3 precedes step 4 because reorganising edits and moves pinned files; after step 3 that no longer strands evidence.

## Testing Decisions

A good test here exercises behaviour through a public entry point and survives files being moved. Tests must not assert on a module's location, on `sys.path`, or on the digest of a source file in the working tree.

Seams, highest first:

- **The wrapper running Bazel.** `test //autonomy/...` and `test //parallax/...` inside Insula are the acceptance seam for every structural step. A step is correct when the same test modules pass after it as before it.
- **The evidence module's interface.** Snapshot, fetch and verify are tested through the interface with the local-directory storage adapter. Cases: identical sources give identical digests; any changed, added or removed source changes the digest; a receipt verifies against its snapshot and fails against an altered one; a missing snapshot is an explicit failure; the working tree is not consulted during verification.
- **The wrapper's plan output.** The printed sandbox command is tested as data: cleared environment, fixed home, read-only rootfs, the expected mounts, and refusal on a rootfs identity mismatch.

Baseline for parity, measured on the current tree with the tracer environment: 176 test modules, of which 140 pass (532 tests), 34 are unavailable outside a rootfs or live gate (26 need torch, 2 need pytest, the rest need live-gate mounts), and 2 fail. The two failures predate this work: one spawns a Python interpreter without NumPy, the other needs the upstream protocol-buffer sources. Under Bazel in the CPU rootfs the passing set must not shrink, and under the GPU configuration the 26 torch modules must run.

Prior art:

- The journal's tests show the pattern for content-addressed storage and hash-chain verification.
- The resource-source tests show the pattern for freezing sources to a directory and validating them.
- The architecture runner's tests show snapshot-based resume and verification.
- The layering, pin-report and test-runner tools added under `tools/` have unit tests using temporary trees and temporary git repositories.

The pin report is used during migration as a measurement, not a gate: each step records which source pins it touches.

## Out of Scope

- Any change to `surflo/`, `submodules/`, `training/`, `configs/`, `install/`, or the root `scripts/` and `tests/`.
- Moving `collaboration`, `insula-scout` or `photoreal-scenes` out of `experiments/`.
- Cargo and uv workspaces. The repository has no Rust, and Python packages come from the rootfs.
- A sealed network or a separate dependency-capture step for builds.
- Merging the version-suffixed copies, or refactoring closed procedure records.
- Rewriting, re-signing or migrating existing receipts, journal entries or dated specs.
- New research results. Re-admitting the balanced16 sweep restores the ability to run it; running it is separate work.
- Sharing code between `parallax/` and `autonomy/`.
- Building the viewer's front end or the upstream-dependent C++ evaluators with Bazel.

## Further Notes

- **`parallax/` runtime mismatch.** The curriculum's required CPU gate is declared for Python 3.10 with NumPy 1.26.4, while the perception CPU rootfs has Python 3.12 and a newer NumPy. If the curriculum's tests do not pass in the perception rootfs, `parallax/` needs its own rootfs line; taking packages from the rootfs rules out fetching a second NumPy through Bazel. The existing CI job for the curriculum stays as it is until this is resolved.
- **Nested sandboxing is unverified.** Sibling repositories disagree on whether Bazel's own sandbox works inside the Insula sandbox, and one found that the Bazel server does not survive the sandbox's process namespace being torn down. The first step must establish which spawn strategy and server mode work here before anything depends on them.
- **Hard-coded paths.** The old perception path is written into 23 architecture harness drivers, several gate scripts, the rootfs build script, the publication audit and its test, the collaboration tests and the CI workflow. Sandbox mount points inside the rootfs (`/experiment`, `/source`, `/outputs`) are a separate convention and do not change with the rename.
- **Checkout-specific pins already fail.** The only resumable sustained run recorded its sources under a different worktree path, so its guard already rejects this checkout. Re-admission, not repair, is the path forward.
- **New rootfs digests.** Baking Bazel in changes the image digest. Every check that compares a runtime lock with the previous digest must be found and re-admitted; this is part of step 1.
- **Glossary wording.** The tools and the architecture note written earlier say "cited" where the glossary now says "pinned". They are corrected when they move.
