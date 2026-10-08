# First-class models, neural layers and training

Date: 2026-10-03 (America/Los_Angeles)

Status: design proposal for review. The user selected the package locations and the initial trainer scope below. No implementation or live migration verification has run.

## Goal and settled decisions

Make maintained perception models, their neural layers and their training code first-class scientific code in Sureal. A researcher must be able to find, construct, inspect and train the current architectures without navigating historical experiment tiers or hardware-labelled directories.

The user selected:

- `sureal/models/` and `sureal/training/` as first-class package directories.
- Consolidation of the duplicated one-frame producer loops first; retain the existing sustained loop.
- Models and training before the later data, geometry, evaluation, analysis and execution migrations.

Subsequent steering adds the [Sureal-local collaboration protocol](2026-10-03-sureal-serial-collaboration-design.md) as supporting infrastructure after pristine mainline and before this scientific migration. Corenius is a design reference only; all implementation stays in Sureal. Protocol ticket 53 is an execution prerequisite for task 44.

The migration preserves scientific behavior. Architecture improvements, new losses, new sampling strategies and new experiments are separate research changes with their own gates.

## Evidence behind the design

The initial review inspected mainline `d84f1d5` and the active `waymo-tracer` worktree. Before implementation, record the actual landed source revision and its complete dependency inventory; the worker continues to land active work.

Current scientific ownership is split:

- `pipeline/pillar_detector.py` and `pipeline/pillar_encoder.py`: baseline detector, point decoration, pillar encoding and scatter.
- `gpu/architecture_variants.py`, `gpu/architecture_followups.py`, `gpu/norm_variants.py`: maintained encoders, BEV treatments and normalization choices.
- `advanced/models.py`, `advanced/point_modules.py`, `advanced/range_fusion.py`, `advanced/spatial_modules.py`: ragged pillars, point attention and its MLP control, range fusion and its zero-input control, grid treatments and sparse BEV processing.
- `tier1/models.py`: model construction mixed with objectives, Adam configuration and determinism policy.
- `tier1/train.py` and `advanced/train.py`: nearly identical producer trajectories with different model and observation adapters.
- `cohort/sustained_loop.py` and `cohort/sustained_state.py`: substantial, already-concentrated training and exact continuation behavior.

The dense head path is repeated in `PillarDetector`, `EncodedDetector` and `AdvancedDetector`. Treatments also mutate positional internals of sequential modules. This weakens locality when changing an encoder or backbone.

Existing independent reference updates, literal NumPy losses, geometry checks, export checks and metric audits deliberately repeat producer behavior. Their independence is valuable and must survive.

The current catalogue has 16 tier1 treatment rows and eight advanced rows. `all_pillars` is an input/head equivalence control; it is not another trained model. The retained fixed-frame results record the trained tier1 rows and seven advanced rows as fitted, while `sparse_bev_transformer` is censored at 10,000 updates. These are fitting diagnostics on the selected training frame, not generalization evidence.

## Considered approaches

1. **Move files while retaining all existing construction and trajectory duplication.** This improves discovery but leaves the important maintenance problems intact.
2. **Use explicit scientific ownership and concentrate the duplicated producer behavior.** Recommended: one maintained construction seam, meaningful internal encoder/backbone seams, and one shared fixed-frame producer. Preserve specialized sustained behavior.
3. **Introduce a universal configurable model/trainer framework.** This widens the interface before the later segmentation and forecasting task contracts exist. Defer broad trainer unification and arbitrary combinations of model treatments.

## Package ownership

The following tree describes responsibilities. Implementation may combine closely related Python files; it must not create empty directories or shallow forwarding modules merely to reproduce the diagram.

```text
sureal/
  models/
    detectors/       detector assembly and ordered output heads
    layers/          pillar/point/range mechanisms and normalization
    backbones/       dense and sparse BEV processing
    construction.py supported model recipes and construction
  training/
    losses/          detection objectives and explicit weighting rules
    optimizers.py   existing optimizer policy
    fixed_frame.py  shared one-frame producer trajectory
    state/          explicit fixed-frame and sustained checkpoint formats
    sustained.py    existing specialized sustained update behavior
    determinism.py  existing seed and deterministic execution policy

experiments/waymo-perception/
  ...               existing recipes, fixture preparation and launch workers
  research/         original immutable evidence and journal
```

`sureal` must be installed alongside the existing `surflo` package. Existing Surflo reconstruction models, training, imports and checkpoints retain their own ownership.

Canonical scientific imports must not depend on adding experiment directories to `sys.path`, a particular working directory, `/tmp/inputs`, `/outputs`, or a GPU being present at import time. Importing model or training modules must not load fixtures, initialize CUDA, start training, write evidence or acquire a lock.

Only currently needed scientific dependencies move in this phase. For example, pillar decoration/scatter belong with their neural processing, while native dataset decoding, HDFS materialization and native metric execution remain behind the existing experiment adapters until their later migrations.

## Model module

The maintained construction seam creates supported models from explicit scientific model choices. Training choices such as learning rate, clipping, checkpoint scheduling and stopping policy belong to training recipes, not model construction.

The model module owns:

- Point decoration and the existing padded/ragged grouping behavior supplied to each encoder.
- Pillar, point-attention, point-MLP and range-fusion neural processing.
- Dense and sparse BEV processing and the supported grid treatments.
- Classification, seven-residual box and two-bin direction heads.
- Normalization choices, including train/eval behavior and buffer handling.
- The existing foreground-prior initialization of the classification head.

The seam for dense versus sparse BEV processing is justified by existing implementations. So are padded/ragged point processing and range-augmented observations. They are explicit internal variations, not an invitation to invent a universal sensor interface.

Concentrate shared dense feature/head execution. Preserve each treatment's necessary registration structure, construction sequence and parameter traversal order. A shared helper must not introduce extra module prefixes into checkpoint keys or reorder parameters. Preserve construction that consumes RNG even if a treatment subsequently replaces a module: removing those draws changes the seeded model.

Model input remains observations. Targets, annotation coverage, no-label-zone indicators and object identities do not enter learned sensor features. Range-augmented models retain their existing typed auxiliary measurements and lineage checks. In the first migration, observation binding may remain an explicit adapter operation; it must not silently read global fixture state.

For range models, bind the fixture's sensor/return/pixel measurements after device placement and before inference. These observation buffers are nonpersistent; restoring weights alone does not restore usable range observations. Preserve persistent normalization data separately from these fixture-specific buffers.

Keep existing output names, shapes and order: `classification`, `box_residuals`, `direction`. Preserve class, anchor, cell and heading interpretation. Decoding and native evaluation semantics are unchanged.

The existing catalogues remain the list of admitted treatments. Additional combinations of encoders, normalization and backbones require separate tests and research admission; availability of internal modules alone does not establish a valid experiment.

## Training module

Consolidate the duplicated `tier1/train.py` and `advanced/train.py` producer logic in one fixed-frame module. Thin experiment workers own the actual Insula filesystem, mounted fixtures, admitted identities, storage reservations and receipt writing; they pass the model, observations, targets and explicit recipe into scientific training.

Shared producer behavior includes:

- Deterministic construction and optimizer setup in the same order as today.
- Exact continuation from admitted checkpoints.
- Train/eval diagnostics, preserving and restoring normalization buffers during train-mode evaluation probes.
- Finite-value and gradient checks, clipping and optimizer updates.
- Ordered checkpoint samples, full trajectory records and synchronized update timings.
- Existing model/head/gradient diagnostics.
- Return of scientific results and state for the launch worker to persist.

Keep the existing Adam settings and default seed. Preserve the reference detector loss: focal classification, sine-based box comparison and Smooth L1 localization, direction cross-entropy, and the current `classification + 2 * localization + 0.2 * direction` total.

Existing defaults are seed 17 and Adam with the recipe's learning rate, betas `(0.9, 0.999)`, epsilon `1e-8`, zero weight decay and `foreach=False`. Execution retains its current deterministic policy. This phase uses the admitted Torch runtimes and does not introduce TensorFlow.

Loss weighting rules are explicit. The fixed-frame class-balanced positive loss currently requires positive support for every class. The sustained cohort objective has a different absent-class contract. Relocating them does not merge or relax these conditions.

Keep sampling distinct: one fixed frame, shuffled balanced training and sustained round-robin traversal are different recipes. Retain the sustained update loop rather than routing it through the fixed-frame loop.

Checkpoint state has a common home but two explicit formats. The one-frame format retains its curve, records, timing, Torch/CUDA RNG, model and Adam state. Sustained state retains the externally bound identity, steps, frame cursor, synchronized training time and Python/NumPy/Torch/CUDA RNG state. Do not convert historical checkpoint bytes or invent missing fields.

Full replay through a producer is a determinism check, not an independent mathematical verifier. Independent reference updates and losses continue to use their own implementations.

## Experiments, evidence and migration

Experiments continue to own their case catalogues, selected fixtures, source packages, jobs and implementation-gate orchestration. Existing execution, native evaluation and HDFS mechanisms are retained for this phase.

Current sustained source guards inventory all Python files in `pipeline`, `gpu`, `tier1` and `cohort`. A move, helper addition or import change can invalidate a live run even when the affected code appears unrelated.

Therefore:

1. Let the implementation worker finish its active work and land every ready verified change. Record remaining changes and current source identities.
2. Implement the migration in an isolated worktree from a specified landed revision. Do not mutate the active worker's source tree.
3. Treat the migrated source closure as a new version. Freeze canonical package sources, launch adapters and their complete required scientific dependencies together.
4. Validate package staging and imports using that frozen closure. Repository availability alone is insufficient inside Insula.
5. Retain historical workers and source packages while they are required to reproduce prior evidence. New compatibility adapters may delegate to canonical modules for newly admitted jobs; never rewrite an old frozen source package to do so.
6. Retain historical source, input, runtime, checkpoint and evidence identities. Record new identities for migrated execution.

Historical evidence can legitimately refer to old source paths. Such references are provenance, not stale imports to rewrite.

## Actionable goal

From an installed Sureal package and the admitted all-class fixture, every currently supported model must construct and run through `sureal.models`; the tier1 and advanced one-frame treatments must train and resume through the same maintained producer in `sureal.training`. Their outputs, losses, gradients, parameter traversal, checkpoint state and native scores must match their frozen pre-migration implementations under the same runtime, inputs and recipes. The existing sustained loop remains exact and independently verified.

The model and trainer must be directly discoverable from the repository overview, with documented extension points and commands for live verification and timed overfit investigation.

## Milestones, verifiers and acceptance criteria

Each implementation milestone requires an actual, dedicated, locked Insula execution, independently audited outputs and retained receipts. Host tests alone do not close a milestone. CPU-capable import checks complement the live gates.

### MT-0 — Freeze the reference and prove isolated comparison execution

**Goal:** admit a reliable reference and isolated comparison machinery before relocating scientific behavior.

**Verifiers:** enumerate supported catalogues and their dependencies; hash the reference sources/fixtures/runtime; construct a reference model and execute a real forward pass in live Insula. Prove separately pinned source-closure execution and independent comparison/refusal machinery.

**Acceptance:** a retained reference inventory identifies every supported treatment and checkpoint format; the live reference output and its independent audit pass; independently pinned implementations can be compared without import contamination; the active worker's source inventory is unchanged. Installed canonical package import/staging acceptance belongs to MT-1, when the migrated model implementation exists.

Existing starting points are `tier1/run.py --contracts-only` and `advanced/admit.py --version UNIQUE`, with the three admitted fixture families. New migration gates must compare the separately frozen old and new implementations: existing same-implementation repeatability and full replay are necessary evidence but do not alone prove migration equivalence. Fixture availability is not payload verification; recheck pinned hashes before admission.

### MT-1 — Model and neural-layer ownership

**Goal:** migrate all currently supported model mechanisms and concentrate detector assembly without numerical changes.

**Verifiers:** construct each catalogue treatment from the same seed, compare ordered named parameters and buffers, initial values and RNG state, then compare train/eval heads, losses and gradients on the admitted fixture. Run corresponding live Insula model contracts and independent output audits. Include range/zero-range and attention/MLP controls and the ragged, grid and sparse cases.

**Acceptance:** every supported treatment passes; old admitted state loads strictly without key conversion; parameter traversal and optimizer parameter mapping are unchanged; output order and normalization buffers are unchanged; no canonical model import depends on a historical experiment module. Installed canonical imports and frozen package staging pass from a clean directory without experiment path injection or import-time job execution. Record exact equality where the frozen reference already promises it; do not widen tolerances to admit a mismatch.

In particular, baseline/encoded models register encoder, blocks, upsample and heads in that order; advanced models register encoder, upsample, heads, then blocks or spatial processing. Preserve each treatment's order rather than imposing one order on all treatments. The output grid remains 524,288 anchors, including fine/coarse input-grid treatments, with four classification channels, seven box channels and two direction channels per anchor.

### MT-2 — Loss, optimizer and state ownership

**Goal:** put existing training policy and state under `sureal.training` while preserving explicit fixed-frame and sustained contracts.

**Verifiers:** live forward/backward and optimizer updates compared with frozen reference outputs; independent literal-loss and reference-update checks; uninterrupted versus resumed execution, including malformed identity/state rejection; existing sustained continuation verification.

**Acceptance:** loss terms, masks, gradients, Adam mapping/moments and RNG continuation match; fixed-frame all-class and sustained absent-class rules remain distinct; existing corruption checks reject invalid state before mutating live state; independent verifiers do not import the producer implementation being verified.

### MT-3 — Shared fixed-frame producer and research entrypoints

**Goal:** replace duplicated producer trajectories with one maintained fixed-frame implementation and thin tier1/advanced launch adapters.

**Verifiers:** live matched trajectories and all sampled heads; uninterrupted versus resumed state; independent losses, proposal/export checks and native AP/APH scoring; range-observation binding; synchronization, resource and reservation receipts. Exercise the timed fixed-batch overfit command and its reporting path.

**Acceptance:** both treatment families execute and resume through the shared producer; checkpoint keys and scientific records match; native scores match the reference; train/eval probes do not alter trajectory state; no launch adapter rewrites the shared trainer's source. All current GPU/RSS/storage limits and exclusive-lock behavior remain enforced.

Full fixed-batch research verification retains the existing primary and extension ceilings and requires all four classes to achieve LEVEL2 APH at least 0.8 at two consecutive sampled checkpoints including terminal. Record iterations, synchronized training time and the sampled fit interval. A capped failure is reported as censored. A pre-existing censored treatment is not required to improve as a condition of a behavior-preserving migration; its outcome remains visible. Numerical migration probes must not be described as new overfit or generalization evidence.

### MT-4 — Retention, discovery and landing

**Goal:** make the migrated scientific code usable by researchers and retain reproducible evidence.

**Verifiers:** documented package import, model inspection and training commands from a clean directory; reproduce summaries from pinned receipts; archive migration receipts and scientific results using the current verified HDFS retention path, exact readback and actual recovery; review the isolated diff and integration checks.

**Acceptance:** repository navigation links directly to models/layers/backbones, losses/training/state and their live verifiers; source closures and checkpoints remain reproducible; HDFS evidence binds exact bytes and identities; the research journal records the migration and deferred work; only reviewed, verified, owned changes land. Local deletion follows existing verified retention/recovery and resource admission rules.

## Exclusions and later phases

This phase does not add model capacity, change normalization defaults, tune learning rates, alter loss weights, replace native detection metrics, or claim better learning. Detection and segmentation remain distinct tasks. It does not introduce SAM, camera models, radar data, JAX equivalents or a universal multi-task trainer.

Data processing, general geometry, task evaluation, analysis and execution become first-class scientific ownership in subsequent phases. This phase establishes their seams without prematurely relocating their full implementations.

## Review questions

The chosen package locations and initial producer scope are settled. Review the proposed composition, checkpoint/parameter-order invariants and live migration milestones together as the concrete phase-one design. After agreement, write the implementation plan with exact source mappings, dependency closures, tests and execution commands against the landed reference revision.

## Work items and queue

The milestone contracts are decomposed into independently reviewable task specifications:

| Milestone | Task specification | Blocked by |
| --- | --- | --- |
| MT-0 | [44 — reference admission](../../research/tasks/44-models-training-reference-admission.md) | Design/plan review and admitted local protocol 53 |
| MT-1 | [45 — models and layers](../../research/tasks/45-first-class-models-and-layers.md) | 44 |
| MT-2 | [46 — training policy and state](../../research/tasks/46-first-class-training-policy-and-state.md) | 45 |
| MT-3 | [47 — shared fixed-frame producer](../../research/tasks/47-shared-fixed-frame-producer.md) | 46 |
| MT-4 | [48 — retention and closeout](../../research/tasks/48-models-training-retention-and-closeout.md) | 47 |

[Research work guide](../../research/README.md) explains the spec → task → implementation plan → evidence progression. [Queue policy](../../research/task-queue.md) distinguishes scheduling from requirements and experiment outcomes.
