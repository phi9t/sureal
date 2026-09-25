# Surflo Insula scout

This directory captures the B200 scout run made on 2026-09-25 at Surflo commit
`bf14c6375a92911c45795710cd00bf2af17e9a13`. The result is a dedicated Surflo
Insula whose image definition, rootfs materializer, bubblewrap entrypoint, and
experiment runner all live in this directory.

The bundle ran every released execution class against real inputs: plain
inference, default guided inference with DA3, Gaussian rendering, mesh and
vertex-colour export, the VGGT/DA3 raw and TSDF evaluation baselines, and one
real training optimizer step. It also contains a controlled paired-scene probe
of the proposed scene-level uncertainty objective. `results.json` and
`synthetic_results.json` are the compact machine-readable records;
`recipe.json` is the executable manifest.

## Scout result

The shipped 16-view garden sample completed at the stock 100,000-point settings:

| Run | Reconstruction time | Wall time | Output |
|---|---:|---:|---|
| Plain, 100 ODE steps | 4.92 s | 29 s | 100,000 oriented points |
| Guided `default` | 58.06 s | 92 s | 184,945 saved points; 1.57M-vertex mesh |

The wall time includes model loading and startup; the reconstruction time is
reported by Surflo. The guided run used the stock 50+100 biphase schedule,
32 inner updates, 500 polish iterations, densification, DA3 priors, default
mesh extraction, and vertex-colour output.

One public Tanks & Temples scene was used to exercise the released metric
harness. Lower normalized Chamfer and higher F1 are better:

| Method | Chamfer (normalized) | F1 |
|---|---:|---:|
| Surflo plain | 0.004679 | **0.9057** |
| Surflo guided, no densification | **0.004610** | 0.8893 |
| VGGT raw pointmap | 0.006064 | 0.8565 |
| DA3 raw pointmap | 0.006527 | 0.8212 |
| VGGT + TSDF | 0.014753 | 0.7350 |
| DA3 + TSDF | 0.014351 | 0.7051 |

This is one scene, not a benchmark reproduction. It does establish that the
full comparison plumbing works and gives two useful warnings for the larger
experiment: guidance traded a small Chamfer gain for lower F1 here, and TSDF
fusion was much worse than either raw pointmap.

The training path also completed a real forward/backward/update using the
released 8,192-point batch shape and 16 cached views: loss 0.2193, surface-net
gradient norm 0.6169, and 13 GB reported process peak. This is a plumbing test
from a random initialization on one evaluation scene, not evidence about model
convergence.

## Synthetic ambiguity scout

The smallest falsifiable slice of the proposed synthetic pretraining direction
is now runnable. The analytic renderer creates two box-geometry rooms with the
same 16 context images but mutually different geometry behind an occluder: a
low sofa in scene A and a tall shelf in scene B. Eight target cameras reveal the
hidden region. The renderer records exact RGB, camera-axis and ray depth,
normals, object IDs, cameras, oriented surfaces, and context/target visibility.

The episode checks passed before inference:

| Invariant | Scene A | Scene B |
|---|---:|---:|
| Context pixels differing between scenes | 0 | 0 |
| Hidden-object context visibility | 0.000 | 0.000 |
| Hidden-object target visibility | 0.428 | 0.385 |
| Target-visible surface unobserved in context | 0.966 | 0.935 |

Stock Surflo then encoded the shared context once and decoded 100,000 points
for each of four random seeds. Alignment used only context cameras and
context-visible common geometry; no target or hidden geometry was used to fit
the predictions. Recall uses a threshold equal to 1% of the scene diagonal.

| Seed | Classification | Observed common recall | Unobserved common recall | Hidden A support | Hidden B support |
|---:|---|---:|---:|---:|---:|
| 0 | hybrid | 0.826 | 0.459 | 0.872 | 0.531 |
| 1 | scene-A-like | 0.825 | 0.452 | 0.867 | 0.488 |
| 2 | hybrid | 0.823 | 0.456 | 0.838 | 0.534 |
| 3 | hybrid | 0.824 | 0.468 | 0.874 | 0.542 |

Mean observed recall was 0.824 versus 0.459 for common surfaces visible only in
the targets. Three seeds crossed the probe's hybrid threshold; the remaining
seed favored scene A but still had substantial scene-B support. Only 0.256 of
the predicted completion candidates were close to either exact hidden
hypothesis on average. This is a controlled failure case for stock Surflo: its
point-sampling randomness does not act like a clean shared scene-hypothesis
sample here.

The hidden scene is intentionally not identifiable, so this test cannot label
one hypothesis as the uniquely correct answer. It tests completion coherence,
not hidden-scene recovery. It also does not yet test synthetic pretraining,
language supervision, appearance generation, or dynamics.

## Build and enter

Prerequisites are a working Docker or Podman daemon, host `bwrap`, NVIDIA driver
access, and all Surflo submodules initialized. No neighboring checkout or
external build harness is required.

```bash
git submodule update --init --recursive
experiments/insula-scout/build.sh
experiments/insula-scout/enter.sh
```

The generated state lives outside the repository:

```text
~/.cache/surflo/insula-scout/rootfs       dedicated CUDA 13.2 rootfs
~/.cache/surflo/insula-scout/venv         Python 3.10 environment
~/.cache/surflo/insula-scout/huggingface  model cache
~/.cache/surflo/insula-scout/checkpoints  Surflo checkpoint
~/.cache/surflo/insula-scout/outputs      inference outputs
~/.cache/surflo/insula-scout/eval-*       public-scene data and metrics
```

The B200 environment intentionally differs from the authors' CUDA 11.8-12.4,
torch <2.5 matrix. It uses torch 2.9.1+cu130 and compiles all native extensions
for `sm_100` with CUDA 13.2. The CUDA 13.0/13.2 minor mismatch is accepted by
the repository verifier and worked in these runs, but an exactly matched
toolkit would be cleaner.

`build.sh` removes the incompatible cu128 xformers wheel pulled by DA3. The
DA3-LARGE models in this experiment use their MLP fallback; an actual DA3
forward and Surflo's DA3-guided path both passed without xformers. DA3 still
prints an optional `gsplat` warning; Surflo's monodepth guidance and depth
baseline do not use that DA3 3DGS export path.

The optional nvdiffrast extension is compiled from a disposable source copy.
Its legacy setup does not leave `build/` or `*.egg-info` products in the Git
submodule.

## Re-run the scout

Each mode can be run separately, or `all` runs the full sequence:

```bash
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh verify
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh sample
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh eval
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh train-smoke
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh synthetic
CUDA_VISIBLE_DEVICES=0 experiments/insula-scout/run_scout.sh all
```

`sample` downloads the released checkpoint and reconstructs the repository's
garden images. `eval` downloads only `tnt/16views/Ignatius` from the public eval
dataset and runs all six methods in the table. `train-smoke` uses that cache for
one optimizer step and writes a roughly 6.2 GB checkpoint. `synthetic` first
regenerates and validates the paired episode, then runs the four-seed stock
model probe. Generated assets and full aligned predictions remain under the
cache root; the compact evidence is tracked in this directory.

Validate the tracked recipe and every cached evidence hash with:

```bash
python3 experiments/insula-scout/verify_recipe.py --strict-artifacts
```

Without `--strict-artifacts`, the validator checks the tracked manifest and
evidence while allowing a machine that has not downloaded the large model or
run artifacts yet.

On this B200/torch combination, fused SDPA inference succeeds but its backward
pass segfaults reproducibly. The training command therefore puts
`math_sdpa/sitecustomize.py` first on `PYTHONPATH`, disabling flash,
memory-efficient, and cuDNN SDPA before importing Surflo. The math backend ran
the stock 8,192-point training batch in 13 GB. Do not apply this workaround to
inference; it is slower and was unnecessary there.

## Limits and next experiment

The full multi-scene paper tables and full training were not attempted in this
scout. Full training requires the gated DL3DV-10K-Meshed data and the canonical
run uses four GPUs for 201 epochs. The repository has no test suite; installation
verification plus the real execution paths above are the available checks.

For the proposed pretraining direction, this scout establishes the baseline
failure but not the solution. The next model experiment should learn one shared
latent hypothesis per paired episode and reuse it for all point and target-view
queries. The first discriminating comparison is stock per-point randomness
versus a complete-scene latent plus a partial-observation conditional prior,
holding the decoder, observations, point budget, and evaluation thresholds
fixed. Success means individually sampled scenes favor one coherent hidden
hypothesis while a set of samples covers both—not merely a higher best-of-K
surface score.

After that static test works, add target-view appearance objectives and explicit
depth/normal/visibility controls on a leave-and-return camera path. Dynamic 4D
episodes and grounded language are later stages; adding them before coherent
static completion would obscure the key causal result.

All released Surflo, VGGT, checkpoint, and training-data license restrictions
still apply; this bundle does not change the non-commercial research status.
