"""Independent streaming component bundle verification; never extracts paths."""
import hashlib,json,re,tarfile
from pathlib import Path


def validate_component_archive(archive,*,expected_archive_sha256,expected_manifest_sha256):
    archive=Path(archive)
    if archive.is_symlink() or not archive.is_file() or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in (expected_archive_sha256,expected_manifest_sha256)):raise ValueError('verified regular bundle identity required')
    with archive.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
    if actual!=expected_archive_sha256:raise ValueError('component archive digest differs')
    manifest=None;seen=set()
    with tarfile.open(archive,'r|') as tar:
        for member in tar:
            if not member.isreg() or member.mode!=0o644 or member.uid!=0 or member.gid!=0 or member.mtime!=0 or member.uname or member.gname:raise ValueError('noncanonical component member')
            stream=tar.extractfile(member)
            if manifest is None:
                if member.name!='bundle.json' or member.size>16*1024**2:raise ValueError('bounded manifest must be first')
                data=stream.read()
                if hashlib.sha256(data).hexdigest()!=expected_manifest_sha256:raise ValueError('component manifest differs')
                manifest=json.loads(data)
                if manifest['schema_version']!=1 or not manifest['files']:raise ValueError('invalid component manifest')
                for name,meta in manifest['files'].items():
                    parts=name.split('/')
                    if len(parts)!=2 or any(p in ('','.', '..') for p in parts) or name.startswith('/') or len(name.encode())>100 or type(meta['size_bytes']) is not int or meta['size_bytes']<0 or not re.fullmatch('[0-9a-f]{64}',meta['sha256']):raise ValueError('unsafe component inventory')
                continue
            name=member.name
            if name in seen or name not in manifest['files']:raise ValueError('duplicate or undeclared component')
            meta=manifest['files'][name];seen.add(name);digest=hashlib.sha256();size=0
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block);size+=len(block)
            if size!=member.size or size!=meta['size_bytes'] or digest.hexdigest()!=meta['sha256']:raise ValueError('decoded component content differs')
    if manifest is None or seen!=set(manifest['files']):raise ValueError('missing component members')
    return {'files':len(seen),'archive_sha256':actual,'manifest_sha256':expected_manifest_sha256,'archive_bytes':archive.stat().st_size,'provenance':manifest['provenance'],'status':'all decoded component identities reconciled'}
