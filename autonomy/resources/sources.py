"""Freeze the complete external resource execution closure independently."""
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,copy_source_snapshot,file_sha256,verify_materialized_sources

REQUIRED={'sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py',
          'stage_accounting.py','execute_worker.py','process_lifecycle.py'}
SNAPSHOT_TARGET='//autonomy:resource-source-layer'


def sha(path):
    return file_sha256(path)


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
    receipt=copy_source_snapshot(current,sorted(names),destination,LocalSnapshotStore(destination.parent/'source-snapshots'),target=SNAPSHOT_TARGET)
    validate_sources(current,receipt)
    return receipt


def validate_sources(current,pins):
    try:
        root=Path(pins['source_snapshot_root'])
        source_pins=pins['source_pins']
        if not isinstance(source_pins,dict) or not REQUIRED<=set(source_pins):
            raise ValueError('complete resource execution helpers required')
        verified=verify_materialized_sources(root,pins)
        if inventory(root)!=set(verified['source_pins']):
            raise ValueError('resource snapshot inventory differs')
    except FileNotFoundError:
        raise
    except (KeyError,TypeError,OSError,IndexError) as error:
        raise ValueError('complete immutable resource sources required') from error
    return root
