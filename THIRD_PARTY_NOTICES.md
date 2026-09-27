# Third-party notices

Surflo builds on several third-party projects. This file records what is
redistributed in this repository, who owns it, and under which terms. It is
informational: each component remains governed by its own license, and nothing
here modifies those terms.

**Summary of what constrains you.** Two of the components below are restricted
to non-commercial research and evaluation use, and one of them (the
Gaussian-Splatting License, §4.2) requires derivative works to carry the same
use limitation. Surflo is therefore released under the Gaussian-Splatting
License (see [`LICENSE.md`](LICENSE.md)) and **may not be used commercially**
without prior written consent from the respective licensors. This applies to
Surflo as a whole, not only to the files listed as 3DGS-derived.

---

## Code redistributed in this repository

### Gaussian Splatting — Inria and Max Planck Institut für Informatik (MPII)

*Gaussian-Splatting License* — non-commercial, research and evaluation use only.
Full text in [`LICENSE.md`](LICENSE.md), and in
`submodules/diff-gaussian-rasterization-surflo/LICENSE.md`.

Derived from <https://github.com/graphdeco-inria/gaussian-splatting>, modified:

- `surflo/structures/cameras.py`
- `surflo/structures/struct_utils.py`
- `surflo/rendering/surflo.py`
- `submodules/diff-gaussian-rasterization-surflo/` (the whole vendored
  rasterizer, which retains its own copy of the license)

Contact for use outside these terms: `stip-sophia.transfert@inria.fr`.

### VGGT — Meta Platforms, Inc.

*VGGT License* — see <https://github.com/facebookresearch/vggt/blob/main/LICENSE.txt>.
Redistribution (including of derivative works) is permitted only under the terms
of that agreement, a copy of which must be provided to any third party you
distribute to. Publications reporting results obtained with these materials must
acknowledge their use. The license also carries an Acceptable Use Policy.

Derived from <https://github.com/facebookresearch/vggt>, modified:

- `surflo/nn/vggt/` (backbone, heads, layers and utilities)

### PlenOctree — The PlenOctree Authors

*BSD 2-Clause License* (full text retained in the file header).

- `surflo/rendering/sh_utils.py`

### Kaolin — NVIDIA Corporation & Affiliates

*Apache License 2.0* (full text at <https://www.apache.org/licenses/LICENSE-2.0>).

Adapted from
<https://github.com/NVIDIAGameWorks/kaolin/blob/master/kaolin/ops/conversions/tetmesh.py>:

- `surflo/extraction/marchers/tetrahedra.py`
- `surflo/extraction/marchers/masked_tetrahedra.py`

### Bundled inside the vendored rasterizer

- **GLM** — G-Truc Creation, *MIT / The Happy Bunny License*
  (`submodules/diff-gaussian-rasterization-surflo/third_party/glm/`)
- **stb_image_write** — Sean Barrett, *MIT / public domain*
  (`submodules/diff-gaussian-rasterization-surflo/third_party/stbi_image_write.h`)

---

## Model weights downloaded at run time

### VGGT-1B — Meta Platforms, Inc.

*CC BY-NC 4.0* — **non-commercial**.
<https://huggingface.co/facebook/VGGT-1B>

Fetched automatically from the Hugging Face Hub on first model construction.
These weights are not redistributed in this repository, but every Surflo run
depends on them, so their non-commercial restriction applies in practice to any
use of Surflo.

### Depth Anything 3 BASE — ByteDance Ltd. and/or its affiliates

*Apache License 2.0.*
<https://huggingface.co/depth-anything/DA3-BASE>

The optional Module 12 maintained reference downloads the exact checkpoint at
run time. The weights are not redistributed in this repository. Other Depth
Anything 3 variants can carry different or conflicting terms and are not
silently substituted for this locked BASE checkpoint.

---

## Optional components installed separately

These are not redistributed here. They are fetched by
`install/build_extensions.sh` or by the optional extras, and each is governed by
its own license.

| Component | License | Notes |
|---|---|---|
| [nvdiffrast](https://github.com/NVlabs/nvdiffrast) | NVIDIA Source Code License (1-Way Commercial) | Optional — textured-mesh export only |
| [Depth-Anything-3](https://github.com/ByteDance-Seed/Depth-Anything-3) | Apache License 2.0 | Optional — monodepth expert guidance |
| [fused-ssim](https://github.com/rahul-goel/fused-ssim) | see upstream repository (no license declared in package metadata) | Required for guided inference |
| [GeoDel](https://github.com/Anttwo/GeoDel) | BSD 3-Clause | Fast Delaunay backend; vendors [Geogram](https://github.com/BrunoLevy/geogram) |

Python dependencies installed from PyPI (see `pyproject.toml`) carry their own
licenses. Note that `flow-matching` ships **contradictory metadata** — its
`License` field reads `CC-by-NC` while its trove classifier says `MIT License`.
Treat it as non-commercial until upstream clarifies, and verify before relying
on it for anything commercial.

---

## Publication and CI tooling

The following tools validate the repository but are not redistributed in its
source or package artifacts. Workflow actions are pinned to exact commits;
Python tools are pinned to exact releases.

| Tool | Pin | License and use |
|---|---|---|
| [actions/checkout](https://github.com/actions/checkout) | `d23441a48e516b6c34aea4fa41551a30e30af803` (v6) | MIT License |
| [actions/setup-python](https://github.com/actions/setup-python) | `ece7cb06caefa5fff74198d8649806c4678c61a1` (v6) | MIT License |
| [gitleaks/gitleaks-action](https://github.com/gitleaks/gitleaks-action) | `ff98106e4c7b2bc287b24eaf42907196329070c7` (v2.3.9) | Gitleaks Action EULA; personal-account repositories require no license key, while organization-account repositories do |
| [build 1.6.1](https://pypi.org/project/build/1.6.1/) | `1.6.1` | MIT License |
| [twine 7.0.0](https://pypi.org/project/twine/7.0.0/) | `7.0.0` | Apache License 2.0 |
| [tomli 2.4.1](https://pypi.org/project/tomli/2.4.1/) | `2.4.1` | MIT License |
| [Gitleaks CLI](https://github.com/gitleaks/gitleaks) | `v8.30.1`, release archive SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` | MIT License; used for the local full-history release gate |

The action EULA is retained upstream at the pinned revision. Its personal-
versus-organization account distinction is why publication uses the action only
for this personal-account repository; a future organization transfer must
re-evaluate the license-key requirement.

---

*This file is a good-faith inventory prepared by the authors, not legal advice.
If you intend to use Surflo outside non-commercial research and evaluation, seek
your own legal review and contact the respective licensors.*
