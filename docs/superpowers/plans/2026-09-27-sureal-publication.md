# Sureal Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a release-safe Sureal research repository at `git@github.com:phi9t/sureal.git` while preserving Surflo compatibility, attribution, licensing, and complete Git history.

**Architecture:** A repository-owned offline audit defines the public contract, focused tests pin its failure behavior, and immutable GitHub Actions run the portable subset. Documentation and package metadata establish Sureal as a clearly attributed Surflo fork; the final cutover preserves the local `phi9t/mainline` workflow and pushes its reviewed tip to remote `main` only after clean-clone and full-history checks.

**Tech Stack:** Python 3.10+, standard-library `unittest`, `tomli` on Python 3.10, setuptools/PEP 517, Git/Git submodules, Bash, GitHub Actions, Gitleaks 8.30.1.

**Spec:** `docs/superpowers/specs/2026-09-27-sureal-publication-design.md`

## Global Constraints

- Public identity is **Sureal**; installed package, imports, checkpoints, configs, and commands remain `surflo`.
- State prominently that Sureal is a fork of `https://github.com/Anttwo/Surflo` and direct users seeking Surflo itself there.
- Preserve all inherited commits, original authorship, `LICENSE.md`, and `THIRD_PARTY_NOTICES.md` without history rewriting or permissive-license claims.
- The repository remains restricted to non-commercial research and evaluation by its inherited license.
- Target remote is exactly `git@github.com:phi9t/sureal.git`; publish the reviewed `phi9t/mainline` tip as remote `main` with a normal push.
- Do not rename the Python package, publish to PyPI, create tags/releases, force-push, or mutate GitHub visibility/settings.
- GitHub-hosted CI is portable and CPU-only; smoke and full CUDA/B200 validation remain separate tiers.
- Every external GitHub Action reference is an immutable commit SHA, not a floating tag.
- Secret checks report only rule names and paths, never suspected values.
- Tracked blobs must remain below the publication ceiling of 25 MiB (`26_214_400` bytes).

## Review Focus

- Repository paths containing spaces must be handled as `Path`/argument-list values, not shell-concatenated strings; Task 1 tests a fixture path containing spaces.
- An uninitialized but correctly declared submodule must validate from its index gitlink; Task 1 tests without creating the submodule worktree.
- A credential-shaped value must cause failure without appearing in output; Task 1 asserts the sentinel value is absent from serialized errors.
- Ignored generated files must not fail the audit, while the same path tracked in Git must fail; Task 1 tests both states.
- Malformed or incomplete `pyproject.toml` must return an actionable metadata error rather than a traceback; Task 1 tests invalid TOML and a wrong package name.

---

### Task 1: Repository-owned publication audit

**Files:**
- Create: `scripts/publication_audit.py`
- Create: `tests/__init__.py`
- Create: `tests/test_publication_audit.py`

**Interfaces:**
- Produces: `static_errors(root: Path, *, max_blob_bytes: int = 26_214_400) -> list[str]`
- Produces: `portable_command_errors(root: Path) -> list[str]`
- Produces: `audit_repository(root: Path) -> dict[str, object]`
- Produces: `main(argv: Sequence[str] | None = None) -> int`
- CLI: `python scripts/publication_audit.py --root PATH`; emits one JSON object with `schema_version`, `status`, `tracked_files`, `gitlinks`, `max_blob_bytes`, and `errors`.

- [ ] **Step 1: Write failing unit tests for the static audit contract**

Create a temporary Git repository fixture in a directory whose name contains a space. Add the final required-file set:

```python
REQUIRED_PUBLIC_FILES = {
    ".github/workflows/publication.yml",
    ".gitignore",
    ".gitmodules",
    "CONTRIBUTING.md",
    "LICENSE.md",
    "README.md",
    "RELEASING.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "UPSTREAM.md",
    "pyproject.toml",
}
```

Add tests named:

```python
def test_valid_public_fixture_has_no_static_errors(): ...
def test_missing_required_file_and_identity_copy_are_reported(): ...
def test_gitlinks_must_match_gitmodules_without_initialized_submodule(): ...
def test_tracked_generated_and_oversized_files_are_rejected(): ...
def test_ignored_generated_file_is_not_rejected(): ...
def test_secret_error_is_redacted(): ...
def test_invalid_or_wrong_package_metadata_is_reported(): ...
```

The valid fixture must contain the exact target/upstream URLs, package name `surflo`, and the phrases `fork of Surflo`, `surflo`, and `non-commercial research and evaluation`.

- [ ] **Step 2: Run the static tests and verify they fail**

Run: `python -m unittest tests.test_publication_audit -v`

Expected: import failure because `scripts/publication_audit.py` does not exist.

- [ ] **Step 3: Implement the static audit functions**

Use argument-list `subprocess` calls and the Git index as the source of truth:

- discover tracked files and gitlinks with `git ls-files --stage -z`;
- parse `.gitmodules` with `configparser` and compare declared paths exactly to mode `160000` paths;
- parse project metadata with `tomllib`, falling back to `tomli` on Python 3.10;
- inspect only tracked regular-file blobs for generated paths, credential patterns, and size;
- include paths/rule names in errors but never matched credential text;
- keep error ordering deterministic.

- [ ] **Step 4: Run static tests and verify they pass**

Run: `python -m unittest tests.test_publication_audit -v`

Expected: all static tests pass.

- [ ] **Step 5: Write failing tests for portable commands and JSON CLI behavior**

Add:

```python
def test_portable_checks_use_argument_lists_and_collect_failures(): ...
def test_cli_prints_machine_readable_pass_and_fail_results(): ...
def test_non_git_root_fails_cleanly(): ...
```

Patch subprocess execution and assert the portable command set includes tracked Python compilation, `bash -n` for every tracked `*.sh`, `git diff --check HEAD`, and the offline 3D-pathway audit.

- [ ] **Step 6: Run the new tests and verify they fail**

Run: `python -m unittest tests.test_publication_audit -v`

Expected: failures because portable checks and CLI aggregation are incomplete.

- [ ] **Step 7: Implement portable checks and the CLI**

`audit_repository()` combines errors and returns:

```python
{
    "schema_version": 1,
    "status": "pass" if not errors else "fail",
    "tracked_files": tracked_file_count,
    "gitlinks": gitlink_count,
    "max_blob_bytes": 26_214_400,
    "errors": errors,
}
```

`main()` prints canonical JSON and returns `0` only when status is `pass`.

- [ ] **Step 8: Run Task 1 verification**

Run:

```bash
python -m unittest tests.test_publication_audit -v
python -m compileall -q scripts/publication_audit.py tests/test_publication_audit.py
git diff --check
```

Expected: tests pass; compilation and diff checks emit no errors. The audit may still report missing public files until Tasks 2 and 3.

- [ ] **Step 9: Commit the audit implementation**

```bash
git add scripts/publication_audit.py tests/__init__.py tests/test_publication_audit.py
git commit -m "feat: add repository publication audit"
```

### Task 2: Sureal public identity, attribution, and contributor documentation

**Files:**
- Modify: `README.md:1-65,578-601`
- Modify: `pyproject.toml:1-9,63-65`
- Modify: `.gitignore`
- Create: `UPSTREAM.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `RELEASING.md`
- Modify: `tests/test_publication_audit.py`

**Interfaces:**
- Consumes: Task 1 `static_errors()` and exact identity contract.
- Produces: coherent public documentation while preserving all `surflo` runtime interfaces.
- Produces: package URLs `Homepage`/`Repository = https://github.com/phi9t/sureal`, `Upstream = https://github.com/Anttwo/Surflo`, and the existing paper URL.

- [ ] **Step 1: Write failing repository identity tests**

Add:

```python
def test_repository_declares_sureal_identity_and_surflo_compatibility(): ...
def test_package_metadata_keeps_surflo_name_and_points_to_both_repositories(): ...
def test_public_docs_cover_contribution_security_release_and_lineage(): ...
def test_original_surflo_citation_and_license_remain_present(): ...
```

Assert the README contains the Sureal name, linked fork disclosure, new recursive clone command, `surflo` compatibility sentence, and non-commercial warning.

- [ ] **Step 2: Run identity tests and verify they fail**

Run: `python -m unittest tests.test_publication_audit -v`

Expected: failures for missing Sureal identity/docs and old metadata URLs.

- [ ] **Step 3: Update README and package metadata**

Keep the original technical instructions. Add Sureal scope, explicit upstream disclosure, compatibility explanation, license warning, a project map linking `MISSION.md`, the 3D pathway survey, and its experiment README, plus portable/smoke/full validation tiers.

Label the existing BibTeX as the original Surflo paper citation. Change only descriptive/URL metadata in `pyproject.toml`; retain `name = "surflo"`, `version = "0.1.0"`, Python constraint, dependencies, and license.

- [ ] **Step 4: Add focused public policy documents**

Create:

- `UPSTREAM.md`: origin, upstream URL, compatibility, inherited components, Sureal additions;
- `CONTRIBUTING.md`: branch/PR flow, compatibility, licensing, generated artifacts, exact test tiers;
- `SECURITY.md`: supported `main`, private advisory URL, no public secret reports, research-code boundary;
- `RELEASING.md`: exact audit, package, Gitleaks, clean-clone, remote-empty, and non-force push checks.

Do not add invented maintainers or a Sureal citation.

- [ ] **Step 5: Normalize `.gitignore` without changing effective coverage**

Remove development-era headings and duplicates only after adding:

```python
def test_publication_generated_paths_remain_ignored(): ...
```

Cover `.worktrees/`, `.env`, `.venv/`, `*.egg-info/`, `__pycache__/`, `*.pyc`, `checkpoints/`, `outputs/`, `wandb/`, `training/logs/`, and `training/outputs/`.

- [ ] **Step 6: Run Task 2 verification**

Run:

```bash
python -m unittest tests.test_publication_audit -v
python experiments/3d-pathway/pipeline/audit.py --offline
git diff --check
```

Expected: tests pass; pathway audit reports 15 modules, 84 sources, nine assets, and no errors. The full audit may still report the missing workflow until Task 3.

- [ ] **Step 7: Commit the documentation surface**

```bash
git add README.md pyproject.toml .gitignore UPSTREAM.md CONTRIBUTING.md SECURITY.md RELEASING.md tests/test_publication_audit.py
git commit -m "docs: prepare Sureal public repository"
```

### Task 3: Immutable portable CI and history secret scanning

**Files:**
- Create: `.github/workflows/publication.yml`
- Modify: `tests/test_publication_audit.py`

**Interfaces:**
- Consumes: Task 1 CLI and Task 2 public files.
- Produces: workflow `publication` with `portable` and `secret-scan` jobs.
- Produces: a repository for which `python scripts/publication_audit.py --root .` is green.

- [ ] **Step 1: Write failing workflow-contract tests**

Add:

```python
def test_publication_workflow_is_sha_pinned_and_least_privilege(): ...
def test_publication_workflow_runs_a_recursive_full_history_checkout(): ...
def test_publication_workflow_runs_audit_tests_build_and_twine(): ...
def test_real_repository_passes_publication_audit(): ...
```

Assert exact action references:

- `actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803` (`v6`)
- `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1` (`v6`)
- `gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7` (`v2.3.9`)

Reject any workflow `uses:` value ending in a floating tag such as `@v6`.

- [ ] **Step 2: Run workflow tests and verify they fail**

Run: `python -m unittest tests.test_publication_audit -v`

Expected: failures because the workflow is absent.

- [ ] **Step 3: Implement the `publication` workflow**

Use top-level `permissions: { contents: read }`, triggers for pushes to `main` and pull requests, concurrency cancellation, and timeouts.

`portable` job runs recursive full-history checkout, Python 3.10 setup, installs `build==1.6.1 twine==7.0.0 tomli==2.4.1`, runs root tests/audit, builds sdist+wheel, and runs Twine check.

`secret-scan` job runs another full-history recursive checkout and the pinned Gitleaks action with `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`. Do not add CUDA, model, dataset, or artifact-upload steps.

- [ ] **Step 4: Run Task 3 verification**

Run:

```bash
python -m unittest tests.test_publication_audit -v
python scripts/publication_audit.py --root .
git diff --check
```

Expected: tests pass and audit JSON contains `"status": "pass"` and `"errors": []`.

- [ ] **Step 5: Commit CI**

```bash
git add .github/workflows/publication.yml tests/test_publication_audit.py
git commit -m "ci: add portable publication gate"
```

### Task 4: Candidate validation and whole-branch review

**Files:**
- Verify only; modify Task 1-3 files solely to address observed failures or review findings.

**Interfaces:**
- Consumes: complete candidate branch and promoted B200 report `pathway-full-e2e-20260927-r6`.
- Produces: reviewed, clean commit range `26deded..HEAD` ready to land.

- [ ] **Step 1: Run root tests and publication audit**

Run `python -m unittest discover -s tests -v` and `python scripts/publication_audit.py --root .`; require all tests and audit status `pass`.

- [ ] **Step 2: Build and validate distributions outside the repository**

Use `mktemp -d`, install pinned tooling if absent, then run `python -m build --sdist --wheel --outdir "$release_tmp/dist"` and `python -m twine check "$release_tmp"/dist/*`. Require one sdist, one wheel, and two `PASSED` results.

- [ ] **Step 3: Run full-history Gitleaks 8.30.1**

Download `gitleaks_8.30.1_linux_x64.tar.gz` from the official GitHub release into the validated temporary directory. Verify SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` before extraction. Run:

```bash
"$release_tmp/gitleaks" git --redact --no-banner --exit-code 1 .
```

Expected: exit `0`, no findings, no secret values printed.

- [ ] **Step 4: Run existing project verification**

Run:

```bash
python -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v
python experiments/3d-pathway/pipeline/audit.py --offline
python -m compileall -q surflo scripts training examples experiments
while IFS= read -r -d '' script; do bash -n "$script"; done < <(git ls-files -z '*.sh')
git diff --check
```

Expected: 206 existing tests pass with six opt-in skips; audit returns 15 modules, 84 sources, nine assets, no errors; remaining commands succeed.

- [ ] **Step 5: Revalidate the promoted full B200 report without rerunning GPU work**

Call `validator.validate_report()` on `$HOME/.cache/surflo/3d-pathway/runs/pathway-full-e2e-20260927-r6`. Assert `full_acceptance`, both profile lists equal `["full"]`, module IDs `01`-`15`, and eight reference adapters. Do not relaunch the B200 aggregate because publication-only files do not change its implementation hashes.

- [ ] **Step 6: Verify from a fresh recursive local clone**

Clone the candidate branch with `--no-local --recursive` from a `file://` URL into a validated temporary path. Run root tests, audit, isolated distribution build, and Twine check. Require success without source-worktree caches.

- [ ] **Step 7: Request a whole-branch review**

Review fixed range `26deded..HEAD` against the spec along Standards and Spec axes. Require no Critical or Important findings. Address valid findings test-first, commit as `fix: address publication review`, and rerun Steps 1-6.

### Task 5: Land and publish without rewriting history

**Files:**
- Git refs/remotes only; no source edits after review.

**Interfaces:**
- Consumes: reviewed candidate branch, clean `phi9t/mainline`, empty target remote.
- Produces: local `phi9t/mainline` and remote `origin/main` at the identical reviewed commit.

- [ ] **Step 1: Rebase and fast-forward locally**

Verify both worktrees are clean. Rebase `codex/sureal-publication` onto current `phi9t/mainline`, rerun root tests/audit, then:

```bash
git -C /data02/home/philip.yang/workspace/surflo merge --ff-only codex/sureal-publication
```

Expected: no merge commit; `phi9t/mainline` equals reviewed feature tip.

- [ ] **Step 2: Configure exact remotes**

Require existing `origin` fetch URL `https://github.com/Anttwo/Surflo`, then:

```bash
git remote rename origin upstream
git remote add origin git@github.com:phi9t/sureal.git
```

If remotes differ unexpectedly, stop rather than replace them.

- [ ] **Step 3: Recheck remote-empty precondition**

Run `git ls-remote --heads --tags origin` with batch-mode SSH and a finite timeout. Require success with no output; any ref aborts publication.

- [ ] **Step 4: Push reviewed full history to remote `main`**

Run:

```bash
git push -u origin phi9t/mainline:refs/heads/main
```

Expected: new remote `main`; no tags pushed.

- [ ] **Step 5: Verify remote commit and remote clone**

Require `git ls-remote origin refs/heads/main` to equal local `git rev-parse phi9t/mainline`. Fresh-clone Sureal with `--recursive --branch main`, then run root tests, audit, isolated distribution build, and Twine check. Require every portable gate to pass from the published repository.

- [ ] **Step 6: Final state and cleanup**

Verify the main checkout is clean, remotes are correct, commit IDs match, and no tag was created. Remove the clean feature worktree and delete its merged branch if Git permits non-forced cleanup. Preserve all cache-backed B200 runs. Report repository visibility/settings as unchanged.
