"""Admit retained recovery evidence against independently supplied identities."""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha, require_regular_file
from segmentation.semantic_recovery_accounting import verify_accounting

def verify_receipt(root,*,expected_sha256,expected_record,expected_runtime,expected_code,code_root):
    root=Path(root); code_root=Path(code_root)
    def require(ok):
        if not ok:raise ValueError('semantic recovery receipt identity/integrity differs')
    require(sha(root/'receipt.json')==expected_sha256)
    r=json.loads((root/'receipt.json').read_text())
    require(r['input_identity']==expected_record and r['runtime_lock']==expected_runtime)
    require(bool(expected_code) and r['candidate_hashes']==expected_code)
    for name,digest in expected_code.items():
        path=Path(name);require(not path.is_absolute() and '..' not in path.parts)
        require(sha(code_root/path)==digest)
    artifacts=r['artifacts']
    require(set(artifacts)=={'live.log','input/publication.json','input/trusted.json','output/support.json'})
    for name,digest in artifacts.items():
        p=root/name;require(sha(require_regular_file(p))==digest)
    require(json.loads((root/'input/trusted.json').read_text())==expected_record)
    require(sha(root/'input/publication.json')==expected_record['publication_manifest_sha256'])
    pub=json.loads((root/'input/publication.json').read_text());d=expected_record
    require(pub['scene']==d['scene'] and pub['role']=='scientific')
    require(pub['official_split']==d['membership']['official_split'] and pub['research_splits']==d['membership']['research_splits'])
    require(pub['archive']['sha256']==d['archive_sha256'] and pub['archive']['archive_bytes']==d['archive_bytes'] and pub['archive']['report_sha256']==d['report_sha256'])
    checks=r['checks'];require(len(checks)==1 and type(checks[0]['exit_code']) is int and checks[0]['exit_code']==0)
    command=checks[0]['command'];require(command[0]=='bwrap' and '--unshare-all' in command and '--clearenv' in command)
    t=r['transfer']
    require(t['sha256']==d['archive_sha256'] and t['archive_bytes']==d['archive_bytes'] and t['hdfs_uri']==d['archive_hdfs_uri'])
    require(type(t['transfer_exit_code']) is int and t['transfer_exit_code']==0)
    for key in ['working_bytes_before','working_peak_bytes_before_consumer','working_limit_bytes','file_size_limit_bytes']:
        require(type(t[key]) is int and t[key]>=0)
    require(t['file_size_limit_bytes']==d['archive_bytes'])
    require(t['working_peak_bytes_before_consumer']==t['working_bytes_before']+d['archive_bytes'])
    require(t['working_peak_bytes_before_consumer']<=t['working_limit_bytes']<=15*1024**3)
    require(json.loads((root/'output/support.json').read_text())==r['validation'])
    return verify_accounting(r['validation'],d)
