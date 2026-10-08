"""Evict only mirrored/replayed decoded point bytes, preserving recovery evidence."""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256 as digest


def evict_points(processing,publication,replay,*,expected_publication_sha256,expected_replay_sha256):
    processing,publication,replay=map(Path,(processing,publication,replay));record=processing/'point-eviction.json'
    if record.exists():raise ValueError('existing eviction evidence must be preserved')
    pp=publication/'receipt.json';rp=replay/'receipt.json'
    if digest(pp)!=expected_publication_sha256 or digest(rp)!=expected_replay_sha256:raise ValueError('independent receipt identity differs')
    pub=json.loads(pp.read_text());checked=json.loads(rp.read_text())
    if checked['publication_receipt_sha256']!=expected_publication_sha256 or checked['scene']!=pub['scene']:raise ValueError('replay publication linkage differs')
    if len(checked['checks'])!=2 or any(c['exit_code']!=0 for c in checked['checks']) or not pub['checks'] or any(c['exit_code']!=0 for c in pub['checks']):raise ValueError('successful mirror/replay checks required')
    target=pub['archive_hdfs_uri']
    if not isinstance(target,str) or not target.startswith('hdfs://'):raise ValueError('HDFS recovery source required')
    points=processing/'points';report=points/'report.json'
    if digest(report)!=pub['archive']['report_sha256']:raise ValueError('native point manifest changed')
    native=json.loads(report.read_text())
    if native['scene']!=pub['scene'] or checked['validation']['records']!=len(native['rows']):raise ValueError('scene replay inventory differs')
    files=[];names=set()
    for row in native['rows']:
        name=row['artifact']
        if name is None:continue
        if not isinstance(name,str) or name in ('','.', '..','report.json') or Path(name).name!=name or name in names:raise ValueError('unsafe point artifact')
        names.add(name);path=points/name
        if digest(path)!=row['sha256']:raise ValueError('point artifact changed')
        files.append({'path':str(path),'sha256':row['sha256'],'size_bytes':path.stat().st_size,'recovery_member':name})
    if {p.name for p in points.iterdir()}!=names|{'report.json'}:raise ValueError('unexpected point artifacts')
    archive=publication/'packed/scene.tar'
    if digest(archive)!=pub['archive']['sha256']:raise ValueError('local mirrored archive changed')
    files.append({'path':str(archive),'sha256':pub['archive']['sha256'],'size_bytes':archive.stat().st_size,'recovery_member':None})
    result={'status':'verified point eviction admitted','scene':pub['scene'],'archive_hdfs_uri':target,'archive_sha256':pub['archive']['sha256'],'publication_receipt_sha256':expected_publication_sha256,'replay_receipt_sha256':expected_replay_sha256,'files':files,'bytes_evicted':sum(r['size_bytes'] for r in files),'scope':'mirrored/replayed point payloads only; source sidecars and receipts retained'}
    with record.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    for row in files:Path(row['path']).unlink()
    result['status']='verified point eviction completed';record.write_text(json.dumps(result,indent=2)+'\n');return result
