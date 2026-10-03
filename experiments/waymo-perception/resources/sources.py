"""Freeze the complete external resource execution closure independently."""
import hashlib
from pathlib import Path
import shutil

REQUIRED={'sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py',
          'stage_accounting.py','execute_worker.py','process_lifecycle.py'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def regular(path):
    return path.is_file() and not any(p.is_symlink() for p in [path,*path.parents])


def inventory(root):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('regular resource source directory required')
    names=set()
    for path in root.rglob('*'):
        if '__pycache__' in path.parts:continue
        if path.is_symlink():raise ValueError('resource source symlinks forbidden')
        if path.suffix=='.py' and path.is_file():
            if not regular(path):raise ValueError('regular resource source required')
            names.add(path.relative_to(root).as_posix())
    if not REQUIRED<=names:raise ValueError('complete resource execution helpers required')
    return names


def freeze_sources(current,destination):
    current=Path(current);destination=Path(destination);names=inventory(current)
    if destination==current or destination.is_relative_to(current):
        raise ValueError('resource snapshot must be outside current source tree')
    destination.mkdir(exist_ok=False);pins={}
    for name in sorted(names):
        original=current/name;snapshot=destination/name
        snapshot.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,snapshot)
        pins[name]={'original':str(original),'snapshot':str(snapshot),'sha256':sha(original)}
    validate_sources(current,pins)
    return pins


def validate_sources(current,pins):
    current=Path(current)
    try:
        if not isinstance(pins,dict) or set(pins)!=inventory(current):
            raise ValueError('current resource source inventory changed')
        roots=set()
        for name,pin in pins.items():
            if set(pin)!={'original','snapshot','sha256'}:
                raise ValueError('complete original/snapshot/digest binding required')
            original=current/name;snapshot=Path(pin['snapshot'])
            if str(original)!=pin['original'] or not snapshot.is_absolute() or not regular(original) or not regular(snapshot):
                raise ValueError('resource source path differs or is not regular')
            roots.add(snapshot.parents[len(Path(name).parts)-1])
            if sha(original)!=pin['sha256'] or sha(snapshot)!=pin['sha256']:
                raise ValueError('current or frozen resource source changed')
        if len(roots)!=1:raise ValueError('one complete resource snapshot required')
        root=roots.pop()
        if root==current or root.is_relative_to(current) or inventory(root)!=set(pins):
            raise ValueError('resource snapshot inventory differs')
        if any(Path(pin['snapshot'])!=root/name for name,pin in pins.items()):
            raise ValueError('resource snapshot paths differ')
    except (KeyError,TypeError,OSError,IndexError) as error:
        raise ValueError('complete immutable resource sources required') from error
    return root
