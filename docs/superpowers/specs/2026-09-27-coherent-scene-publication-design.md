# Coherent Scene Publication and Evidence Hardening Design

**Date:** 2026-09-27  
**Status:** Approved in-chat design; written specification awaiting review  
**Base:** `phi9t/mainline` at `4ff0ab8`

## Purpose

Publish a canonical, evidence-bounded account of Sureal's current contribution
and research direction, then make the repository's portable validation match the
claims in that account.

The publication must distinguish three things throughout:

1. Surflo's inherited reconstruction model and interfaces.
2. Sureal's reproduction, evaluation, and controlled-experiment infrastructure.
3. A learned persistent scene-hypothesis model that remains proposed research.

The work must not present the constructed shared-latent fixture as learned
evidence, rewrite immutable GPU measurements, or imply that CPU checks ran the
B200 reference suite.

## Canonical publication structure

Create `docs/coherent-scene-hypotheses.md` as the canonical long-form research
assessment. It will incorporate the supplied assessment and the detailed
forward-looking material currently in `MISSION.md`.

The document will:

- state its inspected commit and evidence scope;
- identify Sureal as a fork of Surflo and direct readers to upstream Surflo for
  the original project;
- explain the inherited architecture, including pointwise decoding and the
  difference between cached observation state and a sampled world hypothesis;
- separate recorded B200 evidence from independently rerun checks;
- distinguish the analytic mixed-support result from the photoreal unsupported
  result;
- describe support classifications as relative thresholded measurements, not
  object-completeness or scene-coherence certificates;
- explain the reproduction pathway and its representation boundaries;
- list verified engineering limitations; and
- define the next learned experiment as a research direction rather than a
  repository capability.

External research claims will use stable primary-source links already present in
the repository's source registry where available. Repository claims will link to
the relevant tracked files. No unresolved generated citation markers may remain
in the canonical public documents.

Reduce `MISSION.md` to a concise orientation that states the objective, current
boundary, core probabilistic distinction, and a link to the canonical document.
Add the canonical document to the README project map. `MISSION.md` remains the
short project mission; the new document owns the detailed roadmap and assessment.

## Portable numerical CI

Add a separate `numerical-contracts` job to
`.github/workflows/publication.yml`. The job will:

- use the same recursive, full-history checkout and SHA-pinned actions as the
  existing portable job;
- run on Python 3.10 with only the pinned CPU dependency needed by the pathway
  suite (`numpy==1.26.4`);
- execute the complete offline pathway unittest suite with
  `PYTHONPATH=experiments/3d-pathway`;
- set no opt-in hardware variables, so B200/container gates remain skipped;
- have its own timeout and remain distinct from publication packaging and secret
  scanning.

This job is evidence for deterministic concept fixtures, evaluator contracts,
corruption rejection, and aggregate-report semantics. It is not evidence for a
fresh GPU reference run. The README and canonical document will state that
boundary.

## Support-label terminology and evidence migration

The tracked photoreal summary is a derived artifact bound to immutable raw
evidence. Its generic `label` and `labels` fields will become
`support_label` and `support_labels`, and its schema version will advance from 1
to 2. The values remain `unsupported`, `hybrid`, `scene_a`, or `scene_b`, but
documentation will define them as thresholded relative-support classifications.

The migration will update:

- `experiments/photoreal-scenes/pipeline/probe_summary.py`;
- `experiments/photoreal-scenes/results.json`;
- `experiments/photoreal-scenes/verify_recipe.py`;
- the Module 15 endpoint loader and array semantics;
- affected tests and public documentation.

The raw B200 probe artifact and its recorded hash will not be changed. The
summary builder will continue reading the historical raw field
`hypothesis.label`, verify it against the measured support values, and emit the
new explicit derived vocabulary. Future raw-probe schema redesign is outside
this pass.

## Runtime and isolation contracts

Repo-owned CPU fixture results will explicitly record:

- `network_isolation: "python_socket_guard"`, meaning Python socket creation is
  blocked during the in-process lab; and
- `cpu_memory_scope: "process_lifetime_high_water_mark"`, meaning peak CPU
  memory is the dispatcher's cumulative process high-water mark rather than an
  isolated per-module peak.

These declarations will be emitted by the runner, required by validation, shown
in reports where runtime assumptions are summarized, and enforced by tests.
Maintained reference adapters continue to use container-level network isolation
and their existing per-process/container resource contracts. The two guarantees
must not be described as equivalent.

The result schema will require these fixed-value runtime-contract fields for
newly generated fixture results. Older cached fixture runs may require
regeneration before validation; tracked historical B200 evidence is unaffected.

## Deliberately deferred research work

The following recommendations belong in the canonical research directions but
will not be implemented as model claims in this change:

- render each complete hidden hypothesis and measure context-image agreement to
  test physical observational equivalence;
- centralize or strictly equivalence-test duplicated `SceneState`, plain, and
  guided scene setup before adding stochastic persistent state;
- train matched deterministic and shared-latent completion baselines;
- add oracle-hypothesis diagnostics, held-out layout/asset splits, and conjunctive
  evidence-preservation, validity, coverage, and persistence acceptance;
- connect a fixed sampled scene to appearance generation before adding dynamics
  or language.

Centralizing inherited inference setup is excluded because the current change
does not add sampled model state, and altering the reconstruction core would
expand the risk and required GPU verification without strengthening the
publication contract. The canonical document records it as a prerequisite for
that later model change.

## Testing and acceptance

Implementation follows test-first changes for executable behavior:

1. Publication tests fail until the canonical document, README link, concise
   mission, placeholder removal, and numerical CI job exist.
2. Photoreal and Module 15 tests fail until schema-v2 support-label vocabulary is
   emitted, verified, and consumed.
3. Runner and validator tests fail until network-isolation and memory-scope
   metadata are emitted and required.
4. Focused tests pass after each implementation step.
5. The complete 206-test pathway suite passes without enabling hardware gates.
6. The publication audit, distribution build, and Twine metadata validation pass.
7. `git diff --check` and the repository's offline source/citation audit pass.

The final report will identify the exact verification commands, passed counts,
skips, and any checks not independently rerun.

## Non-goals

- Training or claiming a learned scene-level latent model.
- Rerunning or modifying the recorded B200 experiments.
- Changing the `surflo` package/import/checkpoint compatibility boundary.
- Changing licensing, repository visibility, tags, releases, or package
  publication.
- Treating support labels as proof of complete objects or coherent scenes.
