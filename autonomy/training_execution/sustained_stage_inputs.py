"""Immutable per-stage plan inputs."""
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

def bind_stage_paths(inputs,source,frozen):
 """Redirect every template input alias to this stage's immutable snapshot."""
 source=Path(source);frozen=Path(frozen)
 return {
  inside: frozen/Path(host).relative_to(source)
  if Path(host).is_absolute() and Path(host).is_relative_to(source)
  else Path(host)
  for inside,host in dict(inputs).items()
 }

def split_stage_plan_inputs(inputs,source,frozen):
 """Split a stage input map into the source mount and named launch-plan inputs."""
 bound=bind_stage_paths(inputs,source,frozen)
 source_mount=None
 named_inputs={}
 for inside,host in bound.items():
  if not isinstance(inside,str) or not inside.startswith('/'):raise ValueError('declared stage input path required')
  if inside=='/source':source_mount=host
  else:named_inputs[inside]=host
 return source_mount,named_inputs
