"""Deterministic decoded component bundle with externally verified file identities."""
import hashlib,io,json,re,tarfile,gzip
from pathlib import Path


def create_component_archive(source,archive,*,expected_files,provenance,other_bytes,budget_bytes):
    source,archive=map(Path,(source,archive))
    if archive.exists() or source.resolve() in archive.resolve().parents or any(type(v) is not int or v<0 for v in (other_bytes,budget_bytes)):raise ValueError('invalid bundle destination/capacity')
    actual={str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()}
    if not expected_files or actual!=set(expected_files):raise ValueError('bundle inventory differs')
    sizes={}
    for name,expected in expected_files.items():
        parts=name.split('/')
        if len(parts)!=2 or any(p in ('','.', '..') for p in parts) or len(name.encode())>100 or name.startswith('/') or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('unsafe bundle member')
        p=source/name
        if p.is_symlink() or not p.is_file():raise ValueError('regular decoded member required')
        with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=expected:raise ValueError('decoded component changed')
        sizes[name]=p.stat().st_size
    manifest={'schema_version':1,'provenance':provenance,'files':{n:{'sha256':expected_files[n],'size_bytes':sizes[n]} for n in sorted(sizes)}}
    data=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    if len(data)>16*1024**2:raise ValueError('bundle manifest exceeds resident cap')
    logical=sum(512+((n+511)//512)*512 for n in [len(data),*sizes.values()])+1024;archive_bytes=((logical+10239)//10240)*10240
    resident=other_bytes+sum(sizes.values())
    ceiling=budget_bytes-resident
    if ceiling<=0:raise ValueError('compressed component output capacity unavailable')
    def header(name,size):
        t=tarfile.TarInfo(name);t.size=size;t.mode=0o644;t.uid=t.gid=t.mtime=0;t.uname=t.gname='';return t
    class LimitedOutput:
        def __init__(self,stream):self.stream=stream;self.bytes=0
        def write(self,data):
            if self.bytes+len(data)>ceiling:raise ValueError('compressed output exceeds combined working cap')
            count=self.stream.write(data);self.bytes+=count;return count
        def flush(self):self.stream.flush()
    class HashedInput:
        def __init__(self,stream):self.stream=stream;self.bytes=0;self.digest=hashlib.sha256()
        def write(self,data):
            count=self.stream.write(data);self.digest.update(data[:count]);self.bytes+=count;return count
        def flush(self):self.stream.flush()
    with archive.open('xb') as f:
        limited=LimitedOutput(f)
        with gzip.GzipFile(filename='',mode='wb',fileobj=limited,mtime=0,compresslevel=1) as gz:
            uncompressed=HashedInput(gz)
            with tarfile.open(fileobj=uncompressed,mode='w|',format=tarfile.USTAR_FORMAT) as tar:
                tar.addfile(header('bundle.json',len(data)),io.BytesIO(data))
                for name in sorted(sizes):
                    with (source/name).open('rb') as stream:tar.addfile(header(name,sizes[name]),stream)
    if uncompressed.bytes!=archive_bytes:raise ValueError('uncompressed stream accounting differs')
    working=resident+archive.stat().st_size
    with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    return {'sha256':digest,'manifest_sha256':hashlib.sha256(data).hexdigest(),'archive_bytes':archive.stat().st_size,'format':'canonical-ustar-gzip-v1','uncompressed_bytes':uncompressed.bytes,'uncompressed_sha256':uncompressed.digest.hexdigest(),'files':len(sizes),'working_set_bytes':working}
