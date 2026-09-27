# Upstream lineage

Sureal is a fork of [Surflo](https://github.com/Anttwo/Surflo). The complete Git history is retained so that original authorship, later changes, and the point at
which this research branch diverged remain inspectable. Users looking for
Surflo itself should use the upstream repository.

## Compatibility boundary

The installed package and Python import name remain `surflo`. Checkpoint
formats, Hydra configuration names, CLI entry points, and the core inference
API also retain their Surflo-compatible names. A Sureal repository name does
not imply a new package or a replacement citation for the original Surflo
paper.

Inherited code and assets remain governed by [LICENSE.md](LICENSE.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). In particular, the repository
is limited to non-commercial research and evaluation.

## Sureal additions

Work developed on this fork includes:

- the [research mission](MISSION.md) around persistent sampled scene states;
- the sourced [3D reconstruction pathway](docs/3d-reconstruction-pathway.md);
- repo-owned, controlled [pathway labs](experiments/3d-pathway/README.md), source
  locks, reference adapters, reports, and acceptance tests; and
- publication, reproducibility, and release-safety tooling.

These additions build on Surflo as a reference case study while keeping the
lineage explicit.
