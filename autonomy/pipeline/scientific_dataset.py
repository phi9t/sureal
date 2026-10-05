"""Verified bounded archive replay with separate observation/target namespaces."""
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile
import numpy as np
from .scene_archive_validate import validate_archive


def iter_scene_records(archive, publication, *, expected_publication_sha256, usage,
                       max_record_bytes=128*1024**2):
    """Replay in canonical archive-name order; group by native identity, not order.

    Publication identity is supplied by the independent publication evidence.
    No unpacked scene cache is created. Only one point payload is loaded at once.
    The archive is fully checked before any observation can reach a model.
    """
    archive, publication = Path(archive), Path(publication)
    if (not isinstance(expected_publication_sha256,str)
            or not re.fullmatch('[0-9a-f]{64}',expected_publication_sha256)
            or type(max_record_bytes) is not int or max_record_bytes <= 0):
        raise ValueError('verified publication identity and positive resident cap required')
    if publication.is_symlink() or not publication.is_file():
        raise ValueError('publication is not a regular file')
    if hashlib.sha256(publication.read_bytes()).hexdigest()!=expected_publication_sha256:
        raise ValueError('publication identity changed')
    pub=json.loads(publication.read_text())
    if pub['schema_version']!=1:raise ValueError('unsupported publication schema')
    if pub['role']=='engineering-only':
        if usage!='engineering':raise ValueError('engineering scenes cannot enter scientific cohorts')
    elif pub['role']=='scientific':
        allowed=pub['research_splits'];official=pub['official_split']
        legal={'train','development'} if official=='training' else {'validation','camera_validation'} if official=='validation' else set()
        if (not isinstance(allowed,list) or not allowed
                or any(not isinstance(s,str) for s in allowed)
                or len(allowed)!=len(set(allowed)) or usage not in allowed
                or not set(allowed)<=legal or {'train','development'}<=set(allowed)):
            raise ValueError('scientific split membership conflict')
    else:raise ValueError('unknown publication role')
    meta=pub['archive']
    validation=validate_archive(archive,expected_report_sha256=meta['report_sha256'],expected_archive_sha256=meta['sha256'])
    if validation['archive_bytes']!=meta['archive_bytes']:
        raise ValueError('archive capacity identity differs')
    with tarfile.open(archive,'r|') as tar:
        first=tar.next();report=json.loads(tar.extractfile(first).read())
        if report['scene']!=pub['scene'] or report['source_lidar_sha256']!=pub['source_lidar_sha256']:
            raise ValueError('source scene or measurement identity differs')
        seen=set();frames=set();points=0
        for r in report['rows']:
            key=(r['context'],r['timestamp'],r['laser'],r['return'])
            if (key in seen or r['context']!=pub['scene'] or type(r['timestamp']) is not int or r['timestamp']<0
                    or type(r['laser']) is not int or r['laser'] not in range(1,6)
                    or type(r['return']) is not int or r['return'] not in (1,2)
                    or type(r['points']) is not int or r['points']<0
                    or type(r['return_present']) is not bool or type(r['segmentation_present']) is not bool
                    or r['motion']!=('compensated' if r['laser']==1 else 'uncompensated')):
                raise ValueError('invalid or duplicate native record identity')
            seen.add(key);frames.add(r['timestamp']);points+=r['points']
            name=f"{r['context']}-{r['timestamp']}-{r['laser']}-{r['return']}.npz"
            if r['return_present'] and r['artifact']!=name:raise ValueError('point artifact/native identity conflict')
        expected={(pub['scene'],t,l,r) for t in frames for l in range(1,6) for r in (1,2)}
        if seen!=expected or points!=report['points']:raise ValueError('incomplete scene inventory')
        order=sorted(report['rows'],key=lambda r:f"{r['context']}-{r['timestamp']}-{r['laser']}-{r['return']}.npz")
        for r in order:
            identity={k:r[k] for k in ('context','timestamp','laser','return','motion')}
            if not r['return_present']:
                yield {'identity':identity,'return_present':False,'observations':{},'targets':{},'evaluation':{},'correspondence':{}}
                continue
            member=tar.next()
            if member is None or member.name!=r['artifact'] or member.size>max_record_bytes:
                raise ValueError('payload sequence differs or resident record cap exceeded')
            data=tar.extractfile(member).read()
            if hashlib.sha256(data).hexdigest()!=r['sha256']:
                raise ValueError('payload changed during replay')
            with zipfile.ZipFile(io.BytesIO(data)) as zipped:
                if sum(info.file_size for info in zipped.infolist())>max_record_bytes:
                    raise ValueError('decoded payload exceeds resident record cap')
            with np.load(io.BytesIO(data),allow_pickle=False) as arrays:
                required={'xyz','pixels','physical_features','nlz','camera_projection'}
                if r['segmentation_present']:required.add('segmentation')
                if set(arrays.files)!=required:raise ValueError('undeclared or missing point arrays')
                payload={k:arrays[k] for k in arrays.files}
            n=r['points'];shapes={'xyz':(n,3),'pixels':(n,2),'physical_features':(n,3),'nlz':(n,),'camera_projection':(n,6),'segmentation':(n,2)}
            if any(a.shape!=shapes[k] for k,a in payload.items()):raise ValueError('point array shape differs')
            if any(not np.isfinite(payload[k]).all() for k in ('xyz','physical_features')):
                raise ValueError('nonfinite physical observations')
            for k in ('pixels','segmentation'):
                if k in payload and not np.issubdtype(payload[k].dtype,np.integer):raise ValueError('noninteger identity/target array')
            projection=payload['camera_projection']
            # Native v2 projection payloads may store integral coordinates in
            # float32 arrays. Preserve those bytes/dtypes; reject fractional data.
            if (not np.issubdtype(projection.dtype,np.number) or not np.isfinite(projection).all()
                    or not np.equal(projection,np.floor(projection)).all()):
                raise ValueError('nonintegral native projection values')
            if (np.any(payload['pixels']<0) or not np.isin(payload['nlz'],[-1,1]).all()
                    or not np.isin(payload['camera_projection'][:,[0,3]],range(6)).all()):
                raise ValueError('invalid native pixel, camera or NLZ metadata')
            targets={}
            if 'segmentation' in payload:
                seg=payload['segmentation']
                # Native instance -1 may accompany valid stuff semantics. It
                # must not become an ignored semantic point or a fabricated ID.
                if r['laser']!=1 or np.any(seg[:,0]<-1) or not np.isin(seg[:,1],range(23)).all():
                    raise ValueError('invalid native TOP semantic namespace')
                targets['segmentation']=seg
            identity['pixels']=payload['pixels']
            yield {'identity':identity,'return_present':True,
                   'observations':{k:payload[k] for k in ('xyz','physical_features')},
                   'targets':targets,'evaluation':{'nlz':payload['nlz']},
                   'correspondence':{'camera_projection':payload['camera_projection']}}
        if tar.next() is not None:raise ValueError('unexpected terminal scene member')
