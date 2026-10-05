"""Independent streaming validation of immutable decoded-scene archives."""
import hashlib
import json
from pathlib import Path
import re
import tarfile
from evidence.source_snapshot import file_sha256, require_digest, require_regular_file


def validate_archive(archive, *, expected_report_sha256, expected_archive_sha256):
    archive=Path(archive)
    try:
        require_digest(expected_report_sha256);require_digest(expected_archive_sha256);require_regular_file(archive)
    except ValueError as error:
        raise ValueError('independent archive/manifest identities required') from error
    actual=file_sha256(archive)
    if actual != expected_archive_sha256:raise ValueError('archive digest differs')
    seen=set();expected=None;size=archive.stat().st_size;payload_bytes=0
    with tarfile.open(archive,'r|') as tar:
        for member in tar:
            if (not member.isfile() or member.name in ('', '.', '..') or Path(member.name).name!=member.name or member.name in seen
                    or member.size<0 or member.size>size
                    or (member.uid,member.gid,member.mtime,member.mode,member.uname,member.gname)!=(0,0,0,0o644,'','')):
                raise ValueError('unsafe, duplicate or noncanonical archive member')
            seen.add(member.name);source=tar.extractfile(member)
            if expected is None:
                if member.name!='report.json' or member.size>64*1024**2:
                    raise ValueError('bounded verified manifest must be first')
                data=source.read()
                if hashlib.sha256(data).hexdigest()!=expected_report_sha256:
                    raise ValueError('archive manifest differs')
                report=json.loads(data)
                if report['schema_version']!=1:raise ValueError('unsupported scene schema')
                expected={'report.json':expected_report_sha256}
                for row in report['rows']:
                    name=row['artifact']
                    if name is None:
                        if row['return_present'] or row['points']!=0:raise ValueError('inconsistent absent return')
                        continue
                    if not isinstance(name,str) or name in ('', '.', '..') or Path(name).name!=name or name in expected:
                        raise ValueError('unsafe or duplicate manifest member')
                    expected[name]=row['sha256']
            else:
                if member.name not in expected:raise ValueError('undeclared archive member')
                digest=hashlib.sha256();count=0
                for block in iter(lambda:source.read(1024*1024),b''):
                    digest.update(block);count+=len(block)
                if count!=member.size or digest.hexdigest()!=expected[member.name]:
                    raise ValueError('scene member content differs')
            payload_bytes+=member.size
    if expected is None or seen!=set(expected):raise ValueError('incomplete scene archive')
    return {'members':len(seen),'payload_bytes':payload_bytes,'archive_bytes':size,
            'archive_sha256':actual,'report_sha256':expected_report_sha256,
            'status':'all canonical members reconciled to independently verified manifest'}
