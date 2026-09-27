# Sureal Publication Design

**Status:** Approved in conversation on September 27, 2026  
**Target repository:** `git@github.com:phi9t/sureal.git`  
**Source branch:** `phi9t/mainline`  
**Publication branch:** `main`

## Context

The repository began as a fork of
[Surflo](https://github.com/Anttwo/Surflo) and now includes substantial
reproduction infrastructure and research work around classical reconstruction,
neural rendering, foundation geometry, and persistent generative scenes. The
destination repository exists and was empty when this design was prepared.

Sureal will be the public repository and research identity. The Python package,
imports, checkpoint formats, configuration names, and command interfaces will
remain `surflo` for compatibility. The complete 48-commit history will be
preserved as the inherited baseline (with the publication commits added on
top) so that authorship and provenance remain inspectable.

The inherited Gaussian-Splatting License restricts the repository to
non-commercial research and evaluation. Publication must preserve that license,
all upstream notices, and the existing third-party inventory.

## Goals

- Make a fresh recursive clone understandable, installable, and auditable.
- Give Sureal an honest public identity without implying authorship of Surflo.
- Preserve the working `surflo` API and all inherited history.
- Detect public-release hazards before the first push and on future changes.
- Publish the reviewed history to `phi9t/sureal` as `main` without rewriting it.

## Non-goals

- Renaming the Python package or changing checkpoint/config compatibility.
- Re-licensing inherited or derivative code.
- Publishing to PyPI, creating a GitHub release, or adding a release tag.
- Changing GitHub visibility, branch protection, topics, or other repository
  settings.
- Making GPU-heavy reconstruction execute on GitHub-hosted runners.
- Claiming that Sureal is the original Surflo project or paper implementation.

## Identity and Attribution

The README will lead with Sureal and immediately identify it as a fork of
Surflo. It will link to the upstream repository and explicitly direct users who
want Surflo itself to that project. The original authors and paper citation
will remain intact and will be labeled as attribution for inherited Surflo
work.

The README will explain why `import surflo` remains the supported interface.
Sureal-specific additions will be summarized separately: the executable 3D
reconstruction pathway, controlled scenes, pinned maintained references,
cross-era reports, and the persistent-scene research direction.

`pyproject.toml` will retain `project.name = "surflo"` while updating the
description and project URLs to distinguish the Sureal repository, Surflo
upstream, and the Surflo paper. No maintainer-specific citation metadata will
be invented. A future Sureal paper can add its own citation record.

The non-commercial restriction will be visible near the start of the README.
`LICENSE.md` and `THIRD_PARTY_NOTICES.md` will remain authoritative and will not
be weakened or paraphrased as a permissive license.

## Public Documentation Surface

The release change will update or add:

- `README.md`: Sureal identity, fork disclosure, compatibility note, license
  warning, new clone URL, project map, validation tiers, and original Surflo
  citation.
- `UPSTREAM.md`: concise lineage, upstream URL, compatibility boundary, and a
  list of Sureal-owned research additions.
- `CONTRIBUTING.md`: contribution workflow, test tiers, generated-artifact
  policy, licensing expectations, and pull-request checks.
- `SECURITY.md`: supported branch, private vulnerability-reporting route via
  GitHub Security Advisories, and a warning not to file public secret reports.
- `RELEASING.md`: repeatable pre-publication and future release checklist.
- `pyproject.toml`: public repository and upstream metadata without renaming
  the installed package.
- `.gitignore`: remove development-era headings and duplicate rules while
  preserving every effective exclusion needed by existing workflows.

The existing technical installation, inference, training, evaluation, mission,
and reconstruction-pathway material will remain accessible. The README may
reorder or summarize it, but it will not silently discard working commands or
the original scientific attribution.

## Publication Audit

A repository-owned audit command will check the public contract without network
access. It will verify:

- required public files and the exact target/upstream repository links;
- the Sureal fork disclosure and `surflo` compatibility statement;
- preservation of the non-commercial license and third-party notice links;
- valid `pyproject.toml` metadata and expected package name;
- declared Git submodules matching index gitlinks;
- absence of tracked generated artifacts and common credential-shaped content;
- absence of tracked blobs above the repository's documented size ceiling;
- shell syntax, Python compilation, and the offline 3D-pathway source audit.

The audit will report filenames and rule names, never suspected secret values.
Its checks will be deterministic and covered by focused tests. Dedicated secret
scanning will also examine the complete Git history before publication and in
GitHub Actions.

## Continuous Integration

GitHub Actions will provide a portable CPU publication gate. Third-party actions
will be pinned to immutable commit SHAs. The workflow will:

1. check out the full repository and recursive submodules;
2. set up Python 3.10;
3. run the repository publication audit and its tests;
4. build the source and wheel distributions in isolation;
5. validate distribution metadata;
6. run Python compilation, shell syntax, and the offline pathway audit; and
7. run a pinned history-aware secret scanner.

The workflow will not install CUDA, download checkpoints or datasets, or claim
to reproduce GPU results. Documentation will distinguish three tiers:

- **Public CI:** portable publication and metadata contracts.
- **Smoke:** local/container numerical and adapter checks.
- **Full:** the existing hash-verified NVIDIA B200 all-module acceptance gate.

## Remote and Branch Cutover

The existing `origin` (`https://github.com/Anttwo/Surflo`) will be renamed to
`upstream`. The new SSH target will become `origin`. The local
`phi9t/mainline` branch remains the working integration branch; its reviewed
tip will be pushed to `origin/main`.

Immediately before the first push, the implementation will verify that the
target has no heads or tags. Publication will use a normal non-force push. If
the remote is no longer empty, authentication fails, or validation is not
green, the process stops without rewriting or overwriting remote state.

No tags, GitHub releases, or repository-setting mutations are part of this
cutover.

## Verification and Acceptance

Before publication:

- current-tree and full-history credential scans report no findings;
- the publication audit and focused tests pass;
- the existing project test suite passes in proportion to available hardware;
- package distributions build and their metadata validates;
- `git diff --check`, Python compilation, and shell syntax pass;
- the 3D-pathway offline audit reports 15 modules, 84 sources, nine assets, and
  no errors; and
- a clean recursive clone from the candidate commit passes the portable gate.

After publication:

- `origin/main` resolves to the reviewed local commit;
- a fresh recursive clone from `git@github.com:phi9t/sureal.git` succeeds;
- the portable publication gate passes from that clone; and
- the local working branch remains clean and retains `upstream` for reference.

The existing promoted B200 report remains evidence for the GPU tier; the
publication work does not regenerate expensive results unless implementation
changes touch those contracts.

## Failure Handling

Checks fail closed with actionable messages. Secret-like values are never
printed. Temporary package and clone directories are created outside the
repository and removed only after their exact paths are validated. Remote
publication is last, after all reversible local work and review are complete.
No automated step force-pushes, deletes branches, changes visibility, or alters
GitHub settings.
