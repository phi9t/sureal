"""Keep measurement geometry and typed range lineage together on the device."""
import numpy as np
import torch

def load_observations(path, device):
 with np.load(path,allow_pickle=False) as arrays:
  observations=[torch.from_numpy(arrays[key]).to(device) for key in ('points','counts','coordinates')]
  observations[0]=observations[0].float()
  auxiliary={key:torch.from_numpy(arrays[key]).to(device) for key in arrays.files if key not in ('points','counts','coordinates')}
 return observations,auxiliary
