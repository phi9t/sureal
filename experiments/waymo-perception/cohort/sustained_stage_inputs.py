"""Immutable per-stage command inputs, so old receipts remain replayable."""
import hashlib,shutil
from pathlib import Path

def freeze_inputs(source,destination):
 source=Path(source);destination=Path(destination)
 files=list(source.iterdir())
 if source.is_symlink() or not (source/'manifest.json').is_file() or any(p.is_symlink() or not p.is_file() or p.suffix!='.json' for p in files):raise ValueError('regular JSON inputs with a manifest required')
 if destination.exists():raise FileExistsError(destination)
 shutil.copytree(source,destination)
 hashes={}
 for path in destination.iterdir():
  with path.open('rb') as stream:hashes[str(path)]=hashlib.file_digest(stream,'sha256').hexdigest()
 return destination,hashes
