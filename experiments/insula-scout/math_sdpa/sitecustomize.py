"""Blackwell training workaround for torch 2.9.1+cu130.

The fused SDPA backward path segfaulted reproducibly in the scout environment.
Inference is unaffected.  Put this directory first on PYTHONPATH for training
to select PyTorch's math implementation before any Surflo module is imported.
"""

import torch

torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cuda.enable_cudnn_sdp(False)
print("[surflo scout] forced math SDPA backend", flush=True)
