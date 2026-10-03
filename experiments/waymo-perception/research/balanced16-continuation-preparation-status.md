# Balanced16 continuation preparation

[Combined live CPU suite](balanced16-continuation-cpu-suite-v1-verified.json) passed15 groups:7 execution-contract,3 loss and5 restart/state groups. Sources were frozen before execution; no GPU devices were bound.

The class-balanced port matches the admitted all-present equation exactly, handles missing cyclist/pedestrian classes with a declared zero-positive branch and preserves negative/box/direction terms. It is a candidate treatment, not a demonstrated improvement.

Safe serialized CPU restart at update19 reproduces the uninterrupted state at35, including Adam and Python/NumPy/Torch RNG, across a16-frame cursor boundary. Review exposed mutable Adam aliases and late malformed-RNG failure; dedicated live RED reproduced both, then the fixed suite passed. Restored continuation cannot mutate the retained input snapshot, and malformed RNG is refused before live state changes.

The [implementation plan](../../../docs/superpowers/plans/2026-10-03-balanced16-sustained-overfit.md) still requires native GPU/CUDA restart and all16 head replay, trainer/controller implementation, independent literal losses/proposals/export/native metrics, HDFS recovery/retention and full fit decisions. No new16-frame training has launched and ticket07/scientific training remain gated. Replay each receipt command using retained frozen source and a fresh output directory.
