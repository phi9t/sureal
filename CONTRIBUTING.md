# Contributing

Contributions are welcome when they preserve reproducibility, attribution, and
the repository's existing compatibility boundary.

## Workflow

1. Branch from the current integration branch and keep each change focused.
2. Add or update tests before changing behavior.
3. Do not rename the `surflo` package, silently change checkpoint/config
   formats, or weaken source and artifact locks.
4. Open a pull request that explains the evidence, assumptions, failure modes,
   commands run, and any GPU or dataset requirements.

Do not commit checkpoints, datasets, generated run directories, credentials, or
machine-local caches. Compact, intentionally selected reports may be tracked
when their inputs and generation commands are documented. New third-party code,
models, data, or actions must record provenance, a fixed revision or digest, and
compatible license terms.

All contributions remain subject to the inherited license restriction:
non-commercial research and evaluation only. See [LICENSE.md](LICENSE.md),
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [UPSTREAM.md](UPSTREAM.md).

## Validation tiers

Run the narrowest relevant tests while developing, then the applicable gate:

```bash
# Portable CPU publication gate (required for every pull request)
python -m unittest tests.test_publication_audit -v
python scripts/publication_audit.py --root .

# Containerized numerical and adapter smoke checks
experiments/3d-pathway/run.sh all --profile smoke

# Hash-verified GPU acceptance; requires the documented NVIDIA B200 environment
experiments/3d-pathway/run.sh all --profile full
```

The portable gate does not claim CUDA or scientific-result reproduction. State
which smoke or full modules you ran, and explain any hardware-gated checks that
were not run.
