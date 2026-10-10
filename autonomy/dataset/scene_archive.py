"""Deterministic decoded-scene packaging with bounded local admission."""
import json
from pathlib import Path
import re
import tarfile
from evidence.source_snapshot import file_sha256, require_digest
from resources.scientific_budget import check_working


def create_scene_archive(points, archive, *, expected_report_sha256, sidecar_bytes, budget_bytes):
    points, archive = Path(points), Path(archive)
    if (any(type(v) is not int or v < 0 for v in (sidecar_bytes,budget_bytes))
            or archive.exists() or points.resolve() in archive.resolve().parents):
        raise ValueError('invalid archive destination or derived budget')
    try:
        require_digest(expected_report_sha256)
    except ValueError as error:
        raise ValueError('independent reconstruction manifest identity required')
    if file_sha256(points/'report.json') != expected_report_sha256:
        raise ValueError('reconstruction manifest changed')
    report = json.loads((points/'report.json').read_text()); expected = {'report.json':expected_report_sha256}
    for row in report['rows']:
        name = row['artifact']
        if name is None:
            if row['return_present'] or row['points'] != 0:raise ValueError('inconsistent absent return')
            continue
        if not isinstance(name,str) or Path(name).name != name or name in expected:
            raise ValueError('unsafe or duplicate scene member')
        expected[name] = row['sha256']
    if {p.name for p in points.iterdir()} != set(expected):
        raise ValueError('scene inventory differs from verified manifest')
    names = ['report.json'] + sorted(set(expected)-{'report.json'})
    sizes = {}
    for name in names:
        if file_sha256(points/name) != expected[name]:raise ValueError('scene member changed')
        sizes[name] = (points/name).stat().st_size
    logical = sum(512+((size+511)//512)*512 for size in sizes.values())+1024
    archive_bytes = ((logical+10239)//10240)*10240
    new_bytes = sum(sizes.values())+archive_bytes
    working = sidecar_bytes+new_bytes
    cap_record = check_working(sidecar_bytes,new_bytes,where='dataset.scene_archive.create_scene_archive',limit=budget_bytes)
    with archive.open('xb') as stream:
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as tar:
            for name in names:
                header = tarfile.TarInfo(name);header.size=sizes[name];header.mode=0o644
                header.uid=header.gid=header.mtime=0;header.uname=header.gname=''
                with (points/name).open('rb') as source:tar.addfile(header,source)
    if archive.stat().st_size != archive_bytes:
        raise ValueError('archive byte accounting differs')
    return {'sha256':file_sha256(archive),'archive_bytes':archive_bytes,
            'members':len(names),'working_set_bytes':working,
            'report_sha256':expected_report_sha256,'scientific_working_cap':cap_record}
