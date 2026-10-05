# Coherent Scene Publication and Evidence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish Sureal's canonical coherent-scene assessment and make its CPU evidence, support terminology, and runtime guarantees enforceable.

**Architecture:** The long-form assessment becomes the canonical research document while `MISSION.md` becomes a concise entry point. Existing deterministic pathway machinery gains a required CPU CI gate and explicit runtime-contract metadata; the derived photoreal summary moves to schema-v2 support-label terminology without modifying its hash-bound raw GPU evidence.

**Tech Stack:** Markdown, Python 3.10 standard library, NumPy 1.26.4, JSON/JSON Schema, GitHub Actions, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-27-coherent-scene-publication-design.md`

## Global Constraints

- Preserve Surflo attribution, the `surflo` package/import/checkpoint boundary, and the non-commercial license.
- Do not alter or claim to rerun immutable B200 measurements.
- Do not claim that the constructed shared-latent fixture is a learned model.
- Keep GPU/reference execution separate from the required CPU numerical job.
- Use primary sources dated no later than 2026-09-25 for material research claims.
- Keep complete-hypothesis context rendering, scene-setup centralization, and learned shared-latent training as documented future work.
- Implement executable behavior test-first and retain SHA-pinned, least-privilege GitHub Actions.

## Review Focus

- A reader must not confuse inherited Surflo code with Sureal additions; Task 1's publication test pins the three-layer distinction and upstream link.
- A green CPU job must not imply a fresh B200 run; Task 2's workflow test pins the command, dependency, missing hardware opt-ins, and explanatory copy.
- Historical raw probe data still uses `hypothesis.label`; Task 3 tests old raw input to new schema-v2 output and verifies the raw artifact hash is unchanged.
- A support label must not be interpreted as object completeness; Task 3 tests explicit `support_label` names and guardrail prose while rejecting legacy derived fields.
- Fixture isolation and memory scope must not be overstated; Task 4 tampers with both fixed-value contracts and requires validation failure.

---

### Task 1: Canonical Research Assessment and Concise Mission

**Files:**
- Create: `docs/coherent-scene-hypotheses.md`
- Create: `experiments/3d-pathway/research/coherent-scene-publication-sources.md`
- Modify: `MISSION.md`
- Modify: `README.md`
- Modify: `scripts/publication_audit.py`
- Modify: `tests/test_publication_audit.py`
- Modify: `experiments/3d-pathway/pipeline/audit.py`
- Modify: `experiments/3d-pathway/tests/test_documentation.py`
- Modify if the source audit requires it: `experiments/3d-pathway/sources.json`

**Interfaces:**
- Consumes: the approved design, the user-supplied assessment, existing `MISSION.md`, tracked result files, and the primary-source research note.
- Produces: a canonical public document at `docs/coherent-scene-hypotheses.md`; a short `MISSION.md`; publication-audit enforcement that both files remain tracked and correctly linked.

- [ ] **Step 1: Write failing publication-document tests**

Add `RepositoryIdentityTests.test_canonical_assessment_separates_evidence_from_research_direction` and extend the fixture/audit contract to assert:

- `docs/coherent-scene-hypotheses.md` is required;
- README links `[Coherent scene hypotheses](docs/coherent-scene-hypotheses.md)`;
- the document names inherited reconstruction, Sureal infrastructure, and proposed learned research separately;
- it says recorded GPU measurements were not independently rerun;
- it calls the derived classifications support labels and disclaims completeness certification;
- `MISSION.md` links the canonical document, contains the scene-level factorization, and is no more than 120 lines;
- neither public document contains unresolved generated citation markers.

Add a pathway audit regression showing that an unknown citation, unregistered
external link, or forbidden terminology in the canonical document fails the
offline audit without making the canonical document duplicate all survey
module citations.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_publication_audit.RepositoryIdentityTests.test_canonical_assessment_separates_evidence_from_research_direction -v`

Expected: FAIL because the canonical document and contract do not exist.

- [ ] **Step 3: Write the canonical document and shorten the mission**

Use the supplied assessment as the factual spine. Merge only source-supported research directions from the old mission, using registered citation form `[source-id](primary-url)` for external claims. Replace `MISSION.md` with a concise objective/current-boundary/factorization/next-result page, add the README project-map link, require the document in `publication_audit.REQUIRED_PUBLIC_FILES` and its test fixture, and extend the pathway audit's citation/link/terminology checks to the canonical document.

- [ ] **Step 4: Run focused documentation and source audits**

Run:

```bash
python -m unittest tests.test_publication_audit -v
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_documentation.py' -v
python experiments/3d-pathway/pipeline/audit.py --offline
```

Expected: all tests and the audit PASS with no unresolved citation or terminology errors.

- [ ] **Step 5: Commit**

```bash
git add README.md MISSION.md docs/coherent-scene-hypotheses.md scripts/publication_audit.py tests/test_publication_audit.py experiments/3d-pathway/pipeline/audit.py experiments/3d-pathway/tests/test_documentation.py experiments/3d-pathway/research/coherent-scene-publication-sources.md experiments/3d-pathway/sources.json
git commit -m "docs: publish coherent scene assessment"
```

---

### Task 2: Required CPU Numerical CI

**Files:**
- Modify: `.github/workflows/publication.yml`
- Modify: `README.md`
- Modify: `docs/coherent-scene-hypotheses.md`
- Modify: `tests/test_publication_audit.py`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Consumes: the existing `publication` workflow and complete 3D-pathway CPU unittest command.
- Produces: a separate `numerical-contracts` job using Python 3.10 and `numpy==1.26.4` with no hardware opt-in variables.

- [ ] **Step 1: Write a failing workflow contract test**

Add `PublicationWorkflowTests.test_publication_workflow_runs_required_cpu_numerical_contracts` asserting the parsed workflow text contains:

- a `numerical-contracts` job;
- the existing immutable checkout/setup-python SHAs;
- recursive submodules and Python `3.10`;
- `numpy==1.26.4`;
- `PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v`;
- no `SURFLO_REQUIRE_` variable in that job;
- a timeout of at least 20 minutes.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -m unittest tests.test_publication_audit.PublicationWorkflowTests.test_publication_workflow_runs_required_cpu_numerical_contracts -v`

Expected: FAIL because the job is absent.

- [ ] **Step 3: Add the numerical job and provenance copy**

Add the standalone job, document that it covers fixture/evaluator/aggregate contracts rather than GPU references, and add the NumPy CI dependency/provenance to `THIRD_PARTY_NOTICES.md`.

- [ ] **Step 4: Run publication tests and YAML-sensitive audit**

Run:

```bash
python -m unittest tests.test_publication_audit -v
python scripts/publication_audit.py --root .
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/publication.yml README.md docs/coherent-scene-hypotheses.md tests/test_publication_audit.py THIRD_PARTY_NOTICES.md
git commit -m "ci: require pathway numerical contracts"
```

---

### Task 3: Schema-v2 Support-Label Vocabulary

**Files:**
- Modify: `experiments/photoreal-scenes/pipeline/probe_summary.py`
- Modify: `experiments/photoreal-scenes/verify_recipe.py`
- Modify: `experiments/photoreal-scenes/results.json`
- Modify: `experiments/photoreal-scenes/README.md`
- Modify: `experiments/photoreal-scenes/tests/test_probe_recipe.py`
- Modify: `experiments/3d-pathway/pipeline/surflo_endpoint.py`
- Modify: `experiments/3d-pathway/tests/test_generation_dynamic_surflo.py`
- Modify: `docs/coherent-scene-hypotheses.md`

**Interfaces:**
- Consumes: schema-v1 raw probe records with `runs[].hypothesis.label` and `aggregate.labels` plus measured supports.
- Produces: schema-v2 derived summaries with `runs[].support_label` and `aggregate.support_labels`; Module 15 arrays named `paired_support_labels` with semantics explicitly limited to thresholded support.

- [ ] **Step 1: Write failing migration and endpoint tests**

Update/add tests that build a summary from historical raw input and assert:

- `schema_version == 2`;
- each derived run has `support_label` and no `label`;
- the aggregate has `support_labels` and no `labels`;
- the raw-results SHA-256 remains the hash of the unchanged input;
- verification rejects legacy schema-v1 derived summaries;
- Module 15 exposes `paired_support_labels`, rejects `paired_labels`, and recomputes values from supports.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python -m unittest discover -s experiments/photoreal-scenes/tests -p 'test_probe_recipe.py' -v
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_generation_dynamic_surflo.py' -v
```

Expected: FAIL on schema version and legacy field names.

- [ ] **Step 3: Implement the derived-schema migration**

Keep historical raw parsing unchanged, validate its label against measured support, translate to the explicit derived fields, update strict recipe verification and Module 15 consumption, and regenerate only the tracked derived `results.json` from the same raw evidence/hash.

- [ ] **Step 4: Update terminology documentation and rerun focused tests**

Define the thresholded classifier and state that `scene_a`/`scene_b` means greater relative support after the unsupported/hybrid gates, not adequate object coverage. Run the Step 2 commands; expected PASS.

- [ ] **Step 5: Commit**

```bash
git add experiments/photoreal-scenes experiments/3d-pathway/pipeline/surflo_endpoint.py experiments/3d-pathway/tests/test_generation_dynamic_surflo.py docs/coherent-scene-hypotheses.md
git commit -m "fix: name photoreal outcomes as support labels"
```

---

### Task 4: Explicit Fixture Runtime Contracts

**Files:**
- Modify: `experiments/3d-pathway/result.schema.json`
- Modify: `experiments/3d-pathway/pipeline/runner.py`
- Modify: `experiments/3d-pathway/pipeline/validator.py`
- Modify: `experiments/3d-pathway/pipeline/reporting.py`
- Modify: `experiments/3d-pathway/tests/test_foundation.py`
- Modify: `experiments/3d-pathway/tests/test_review_fixes.py`
- Modify: `experiments/3d-pathway/tests/test_e2e_completion.py`
- Modify: `experiments/3d-pathway/README.md`
- Modify: `docs/coherent-scene-hypotheses.md`

**Interfaces:**
- Consumes: in-process fixture execution under `offline_network()` and `resource.getrusage(RUSAGE_SELF).ru_maxrss`.
- Produces: `resources.network_isolation == "python_socket_guard"` and `resources.cpu_memory_scope == "process_lifetime_high_water_mark"`, required by schema and semantic validation and displayed in reports.

- [ ] **Step 1: Write failing emission, tamper-rejection, and reporting tests**

Extend fixture tests to assert both exact resource fields. Tamper each field in a promoted run and assert validation fails with a runtime-contract mismatch. Extend report tests to require both scopes in module and aggregate resource sections.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_foundation.py' -v
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_review_fixes.py' -v
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_e2e_completion.py' -v
```

Expected: FAIL because the fields are absent and reports omit them.

- [ ] **Step 3: Emit, validate, and report the exact contracts**

Add both fixed strings to `resources`, require them in JSON Schema and semantic validation, and render them in per-module and aggregate reports. Update the pathway README and canonical assessment to contrast the Python guard with maintained adapters' container network isolation and to call memory process-cumulative.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 commands; expected PASS with only the documented opt-in hardware skip in the end-to-end file.

- [ ] **Step 5: Commit**

```bash
git add experiments/3d-pathway/result.schema.json experiments/3d-pathway/pipeline/runner.py experiments/3d-pathway/pipeline/validator.py experiments/3d-pathway/pipeline/reporting.py experiments/3d-pathway/tests experiments/3d-pathway/README.md docs/coherent-scene-hypotheses.md
git commit -m "fix: declare fixture runtime measurement scope"
```

---

### Task 5: Full Publication Verification

**Files:**
- Modify only if verification exposes a defect in an earlier task; add a failing regression test before any fix.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: a clean, reviewable branch with all portable publication and numerical gates passing.

- [ ] **Step 1: Run the complete CPU test suites**

Run:

```bash
python -m unittest tests.test_publication_audit -v
PYTHONPATH=experiments/3d-pathway python -m unittest discover -s experiments/3d-pathway/tests -p 'test_*.py' -v
```

Expected: publication tests PASS; all 206-or-more pathway tests PASS with only explicit hardware-gate skips.

- [ ] **Step 2: Run repository and source audits**

Run:

```bash
python scripts/publication_audit.py --root .
python experiments/3d-pathway/pipeline/audit.py --offline
git diff --check phi9t/mainline...HEAD
```

Expected: both audits report pass/no errors; diff check emits nothing.

- [ ] **Step 3: Build and validate distributions**

Use the existing pinned publication environment or create an isolated Python 3.10 environment containing `build==1.6.1`, `twine==7.0.0`, and `tomli==2.4.1`.

Run:

```bash
python -m build
python -m twine check dist/*
```

Expected: exactly one wheel and one source archive build; both pass Twine metadata validation.

- [ ] **Step 4: Review scope and evidence language**

Inspect the final diff and confirm no raw B200 artifact, checkpoint/package compatibility boundary, license, repository setting, tag, or release changed. Confirm every learned-scene statement is future tense and every measured claim identifies recorded versus rerun evidence.

- [ ] **Step 5: Commit any verification-only correction**

If Step 1-4 required a tested correction, commit it as `fix: address coherent-scene publication verification`. Otherwise create no empty commit.
