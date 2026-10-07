"""Freeze the complete external resource execution closure independently."""
from pathlib import Path
from evidence.source_snapshot import (
    file_sha256,
    require_regular_file,
    snapshot_target_and_materialize,
    verify_or_materialize_receipt_sources,
)

REQUIRED=frozenset({'sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py',
                    'stage_accounting.py','execute_worker.py','process_lifecycle.py'})
EVIDENCE_REQUIRED=frozenset({'evidence/source_snapshot.py'})
SNAPSHOT_TARGET='//autonomy/resources:execute_worker'


def sha(path):
    return file_sha256(path)


def regular(path):
    try:
        require_regular_file(path)
    except (OSError, ValueError):
        return False
    return True


def inventory(root):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('regular resource source directory required')
    names=set()
    for path in root.rglob('*'):
        if '__pycache__' in path.parts:continue
        if path.is_symlink():raise ValueError('resource source symlinks forbidden')
        if path.suffix=='.py' and path.is_file() and not (path.name.endswith('_test.py') or path.name.startswith('test_')):
            if not regular(path):raise ValueError('regular resource source required')
            names.add(path.relative_to(root).as_posix())
    if not REQUIRED<=names:raise ValueError('complete resource execution helpers required')
    return names


def source_paths(current):
    current=Path(current)
    if current.name!='resources':
        raise ValueError('resource source directory required')
    names={'resources/'+name for name in inventory(current)}
    helper=current.parent/'evidence/source_snapshot.py'
    if not regular(helper):
        raise ValueError('complete resource evidence helpers required')
    return sorted(names|EVIDENCE_REQUIRED)


def _materialized_paths(root):
    root=Path(root)
    names={'resources/'+name for name in inventory(root/'resources')}
    helper=root/'evidence/source_snapshot.py'
    if not regular(helper):
        raise ValueError('complete resource evidence helpers required')
    return names|EVIDENCE_REQUIRED


def _repo_root_for(current):
    current=Path(current)
    if current.name!='resources':
        raise ValueError('resource source directory required')
    if current.parent.name!='autonomy':
        return None
    return current.parents[1]


def freeze_sources(current,destination,*,store=None,repo_root=None,bazel=None,runner=None):
    current=Path(current);destination=Path(destination)
    inventory(current)
    helper=current.parent/'evidence/source_snapshot.py'
    if not regular(helper):
        raise ValueError('complete resource evidence helpers required')
    if repo_root is None:
        repo_root=_repo_root_for(current)
    if repo_root is not None:
        repo_root=Path(repo_root)
    if repo_root is None:
        raise ValueError('Bazel target source snapshot context required')
    kwargs={'repo_root':repo_root}
    if store is not None:kwargs['store']=store
    if bazel is not None:kwargs['bazel']=bazel
    if runner is not None:kwargs['runner']=runner
    receipt=snapshot_target_and_materialize(SNAPSHOT_TARGET,destination,**kwargs)
    validate_sources(current,receipt)
    return receipt


def _is_schema2(receipt):
    return receipt.get('schema_version')==2


def _required_schema2():
    return {'autonomy/resources/'+name for name in REQUIRED}|{'autonomy/evidence/source_snapshot.py'}


def package_member_name(name):
    if name.startswith('autonomy/'):
        return name.removeprefix('autonomy/')
    return name


def package_member_path(package_root,name):
    return Path(package_root)/package_member_name(name)


def validate_sources(current,pins):
    try:
        root=Path(pins['source_snapshot_root'])
        source_pins=pins['source_pins']
        if _is_schema2(pins):
            required=_required_schema2()
        else:
            required={'resources/'+name for name in REQUIRED}|EVIDENCE_REQUIRED
        if not isinstance(source_pins,dict) or not required<=set(source_pins):
            raise ValueError('complete resource execution helpers required')
        verified=verify_or_materialize_receipt_sources(pins,root,env_var='SUREAL_SOURCE_SNAPSHOT_STORE')
        if _is_schema2(pins):
            if not required<=set(verified['source_pins']):
                raise ValueError('complete resource execution helpers required')
            return root/'autonomy'
        if _materialized_paths(root)!=set(verified['source_pins']):
            raise ValueError('resource snapshot inventory differs')
    except FileNotFoundError:
        raise
    except (KeyError,TypeError,OSError,IndexError) as error:
        raise ValueError('complete immutable resource sources required') from error
    return root
