# Releasing Sureal

Sureal releases are repository snapshots, not PyPI publications. Preserve the
complete history, upstream attribution, `surflo` package identity, and inherited
non-commercial terms.

## Candidate checks

From a clean candidate commit:

```bash
python -m unittest tests.test_publication_audit -v
python scripts/publication_audit.py --root .
python -m pip install numpy==1.26.4
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v
python -m build
python -m twine check dist/*
python -m compileall -q scripts tests surflo
python experiments/3d-pathway/pipeline/audit.py --offline
git diff --check HEAD
gitleaks git --redact --no-banner --exit-code 1 .
```

Run `bash -n` on every tracked shell script. The required CPU numerical gate is
not evidence for a fresh B200 measurement. Verify the applicable smoke/full
scientific tier separately; do not represent the portable checks as GPU result
reproduction. Build output belongs in a temporary directory or an ignored
`dist/`, never in the commit.

## Clean-clone gate

Clone the exact candidate through the repository transport, not through shared
local objects, initialize recursive submodules, and repeat the portable audit,
tests, build, and metadata checks:

```bash
git clone --no-local --recursive <candidate-url> <temporary-directory>
```

Record the candidate commit and check artifact hashes. The clone must not rely
on untracked files, pre-existing caches, network access during test execution,
or the developer's configured remotes.

## First publication and future pushes

Before the first publication, confirm that `git ls-remote --heads --tags
git@github.com:phi9t/sureal.git` returns no refs. Stop if it does not: do not
overwrite unexpected remote state. Configure the original Surflo repository as
`upstream`, the Sureal repository as `origin`, and use a normal push of the
reviewed local tip to `refs/heads/main`.

Never force push the public branch, rewrite inherited history, or publish tags,
GitHub releases, package indexes, or repository-setting changes as an implicit
part of this checklist. After pushing, verify the remote SHA and repeat the
portable gate in a fresh recursive clone from the public remote.
