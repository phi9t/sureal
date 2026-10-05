"""Shared immutable cohort/driver inputs, preserved once per resource epoch.

Runtime roots and GPU hardware remain explicitly digest-pinned environments;
their identities are in the native manifests/receipts, not checkpoint payloads.
"""
import json
from pathlib import Path
from advanced.archive import safe_name
from resources.sources import regular,sha


def shared_inventory(backend):
    backend.guard();files={};identities=set()
    if (sha(backend.source/'manifest.json')!=backend.manifest_sha or
        json.loads((backend.source/'manifest.json').read_text())!=backend.manifest or
        not backend.manifest['frames']):
        raise ValueError('unchanged native cohort manifest required')
    def add(name,path,digest):
        safe_name(name);path=Path(path)
        if not regular(path) or sha(path)!=digest:
            raise ValueError('unchanged shared dependency bytes required')
        value={'path':str(path),'sha256':digest,'bytes':path.stat().st_size}
        if name in files and files[name]!=value:raise ValueError('conflicting shared dependency member')
        files[name]=value
    try:
        for frame in backend.manifest['frames']:
            identity=frame['identity'];scene,timestamp=identity.split(':')
            safe_name(scene)
            if '/' in scene or not timestamp.isdecimal() or identity in identities:
                raise ValueError('unique native measurement identity required')
            identities.add(identity);relative=frame['relative_directory'];safe_name(relative)
            if set(frame['sha256'])!={'observations.npz','targets.npz','report.json'}:
                raise ValueError('complete native observation/target/report inputs required')
            for name,digest in frame['sha256'].items():
                add('native/'+relative+'/'+name,backend.native/relative/name,digest)
            add('physical/'+scene+'/producer/'+timestamp+'.npz',backend.native.parent/'balanced16-physical-v2'/scene/'producer'/(timestamp+'.npz'),frame['physical_sha256'])
            add('boxes/'+scene+'/producer/targets.json',backend.native.parent/'balanced16-labels-v2'/scene/'producer/targets.json',frame['boxes_sha256'])
        for path,digest in backend.old['driver_hashes'].items():
            add('drivers/'+Path(path).name,path,digest)
    except (KeyError,TypeError,OSError) as error:
        raise ValueError('complete native cohort/driver dependency inventory required') from error
    return files
