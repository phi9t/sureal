"""Deterministic decoded component bundle with externally verified file identities."""
import hashlib,io,json,re,tarfile
from pathlib import Path
from evidence.source_snapshot import file_sha256, require_regular_file


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
        require_regular_file(p)
        actual=file_sha256(p)
        if actual!=expected:raise ValueError('decoded component changed')
        sizes[name]=p.stat().st_size
    manifest={'schema_version':1,'provenance':provenance,'files':{n:{'sha256':expected_files[n],'size_bytes':sizes[n]} for n in sorted(sizes)}}
    data=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    if len(data)>16*1024**2:raise ValueError('bundle manifest exceeds resident cap')
    logical=sum(512+((n+511)//512)*512 for n in [len(data),*sizes.values()])+1024;archive_bytes=((logical+10239)//10240)*10240
    working=other_bytes+sum(sizes.values())+archive_bytes
    if working>budget_bytes:raise ValueError('component bundle exceeds combined working set')
    def header(name,size):
        t=tarfile.TarInfo(name);t.size=size;t.mode=0o644;t.uid=t.gid=t.mtime=0;t.uname=t.gname='';return t
    with archive.open('xb') as f:
        with tarfile.open(fileobj=f,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            tar.addfile(header('bundle.json',len(data)),io.BytesIO(data))
            for name in sorted(sizes):
                with (source/name).open('rb') as stream:tar.addfile(header(name,sizes[name]),stream)
    if archive.stat().st_size!=archive_bytes:raise ValueError('bundle byte accounting differs')
    digest=file_sha256(archive)
    return {'sha256':digest,'manifest_sha256':hashlib.sha256(data).hexdigest(),'archive_bytes':archive_bytes,'files':len(sizes),'working_set_bytes':working}
