"""Independent streaming component bundle verification; never extracts paths."""
import hashlib,json,re,tarfile,gzip
from pathlib import Path
from evidence.source_snapshot import file_sha256, require_digest, require_regular_file


def validate_component_archive(archive,*,expected_archive_sha256,expected_manifest_sha256,expected_uncompressed_sha256,expected_uncompressed_bytes):
    archive=Path(archive)
    try:
        require_regular_file(archive);require_digest(expected_archive_sha256);require_digest(expected_manifest_sha256);require_digest(expected_uncompressed_sha256)
    except ValueError as error:
        raise ValueError('verified regular bundle identity required') from error
    actual=file_sha256(archive)
    if actual!=expected_archive_sha256:raise ValueError('component archive digest differs')
    if type(expected_uncompressed_bytes) is not int or expected_uncompressed_bytes<=0 or expected_uncompressed_bytes>64*1024**3:raise ValueError('bounded uncompressed stream identity required')
    class CheckedStream:
        def __init__(self,stream):self.stream=stream;self.bytes=0;self.digest=hashlib.sha256()
        def read(self,size=-1):
            if size<0:raise ValueError('unbounded decompression read refused')
            data=self.stream.read(min(size,1024*1024));self.bytes+=len(data)
            if self.bytes>expected_uncompressed_bytes:raise ValueError('decompressed stream exceeds declared bytes')
            self.digest.update(data);return data
    manifest=None;seen=set()
    raw=gzip.open(archive,'rb');checked=CheckedStream(raw)
    with raw,tarfile.open(fileobj=checked,mode='r|') as tar:
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
        while checked.read(1024*1024):pass
        if checked.bytes!=expected_uncompressed_bytes or checked.digest.hexdigest()!=expected_uncompressed_sha256:raise ValueError('complete decompressed stream identity differs')
    if manifest is None or seen!=set(manifest['files']):raise ValueError('missing component members')
    return {'files':len(seen),'archive_sha256':actual,'manifest_sha256':expected_manifest_sha256,'archive_bytes':archive.stat().st_size,'format':'canonical-ustar-gzip-v1','uncompressed_bytes':checked.bytes,'uncompressed_sha256':checked.digest.hexdigest(),'provenance':manifest['provenance'],'status':'all decoded component identities reconciled'}
