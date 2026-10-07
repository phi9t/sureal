"""Immutable per-stage command inputs, so old receipts remain replayable."""
import shutil
from pathlib import Path
from evidence.source_snapshot import file_sha256,require_regular_file

def freeze_inputs(source,destination):
 source=Path(source);destination=Path(destination)
 files=list(source.iterdir())
 try:
  require_regular_file(source/'manifest.json')
  for p in files:
   require_regular_file(p)
 except ValueError as error:raise ValueError('regular JSON inputs with a manifest required') from error
 if any(p.suffix!='.json' for p in files):raise ValueError('regular JSON inputs with a manifest required')
 if destination.exists():raise FileExistsError(destination)
 shutil.copytree(source,destination)
 hashes={}
 for path in destination.iterdir():
  hashes[str(path)]=file_sha256(path)
 return destination,hashes

def bind_stage_paths(arguments,source,frozen):
 """Redirect every template input alias to this stage's immutable snapshot."""
 source=Path(source);frozen=Path(frozen)
 return [str(frozen/Path(value).relative_to(source)) if Path(value).is_absolute() and Path(value).is_relative_to(source) else value for value in arguments]
