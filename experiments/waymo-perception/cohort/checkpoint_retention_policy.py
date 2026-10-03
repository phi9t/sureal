"""Constrain rolling retention to one declared sustained case checkpoint."""
import re
from pathlib import Path

def checkpoint_case(scientific_root,payload,step,*,requested_step=None):
 scientific_root=Path(scientific_root);payload=Path(payload)
 if type(step) is not int or not 0<=step<=32000:raise ValueError('bounded integer checkpoint step required')
 requested=step if requested_step is None else requested_step
 if type(requested) is not int or not step<=requested<=32000:raise ValueError('bounded actual/requested checkpoint identity required')
 case=payload.parent.name
 if payload.parent.parent!=scientific_root or payload.name!=f'update-{requested:02d}' or re.fullmatch(r'balanced16-sustained-[A-Za-z0-9][A-Za-z0-9-]{0,127}',case) is None:raise ValueError('one declared scientific sustained checkpoint required')
 if not payload.is_dir() or any(path.is_symlink() for path in [payload,*payload.parents]):raise ValueError('regular checkpoint ancestry required')
 return case
