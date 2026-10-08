"""Live independently rehashed reproducibility comparison across R0 runs."""
import json
from pathlib import Path
import sys
from evidence.source_snapshot import file_sha256 as sha


def read_run(root,expected_milestone):
    receipt=json.loads((root/'receipt.json').read_text())
    if receipt['milestone']!=expected_milestone or not all(c['exit_code']==0 for c in receipt['checks']):raise ValueError('incomplete live stage')
    for name,digest in receipt['code_hashes'].items():
        if sha(Path('/experiment')/name)!=digest:raise ValueError('changed candidate')
    for name,digest in receipt['artifacts'].items():
        if sha(root/name)!=digest:raise ValueError('changed stage artifacts')
    return receipt


def compare(geometry_a,geometry_b,native_a,native_b):
    ga,gb=read_run(geometry_a,'M3'),read_run(geometry_b,'M3')
    na,nb=read_run(native_a,'M1'),read_run(native_b,'M1')
    for left,right in [(ga,gb),(na,nb)]:
        for key in ['runtime_lock','source_receipt_sha256','code_hashes']:
            if left[key]!=right[key]:raise ValueError('run identity mismatch: '+key)
    if ga['runtime_lock']!=na['runtime_lock'] or ga['source_receipt_sha256']!=na['source_receipt_sha256']:raise ValueError('native/geometry cohort mismatch')
    artifacts_a={k:v for k,v in ga['artifacts'].items() if k.endswith('.npz')}
    artifacts_b={k:v for k,v in gb['artifacts'].items() if k.endswith('.npz')}
    if artifacts_a!=artifacts_b or len(artifacts_a)!=3970:raise ValueError('geometry reproducibility mismatch')
    ra=json.loads((geometry_a/'reconstruction/report.json').read_text());rb=json.loads((geometry_b/'reconstruction/report.json').read_text())
    if ra['rows']!=rb['rows'] or ra['points']!=rb['points']:raise ValueError('geometry coverage/identity mismatch')
    for name in ['manifest.jsonl','sources.json']:
        if sha(native_a/'native'/name)!=sha(native_b/'native'/name):raise ValueError('native reproducibility mismatch')
    if ga['validation']!=gb['validation']:raise ValueError('independent validation mismatch')
    return {'schema_version':1,'milestone':'M5-comparison','passed':True,'geometry_artifacts':len(artifacts_a),
            'points':ra['points'],'geometry_bytewise_equal':True,'native_manifest_bytewise_equal':True,
            'source_receipt_sha256':ga['source_receipt_sha256'],'runtime_lock':ga['runtime_lock'],
            'receipt_hashes':{name:sha(root/'receipt.json') for name,root in [('geometry_a',geometry_a),('geometry_b',geometry_b),('native_a',native_a),('native_b',native_b)]},
            'resources':{'geometry_a':{'seconds':ra['elapsed_seconds'],'peak_rss_kib':ra['peak_rss_kib']},
                         'geometry_b':{'seconds':rb['elapsed_seconds'],'peak_rss_kib':rb['peak_rss_kib']}},
            'scope':'engineering two-scene fixture; no learned-model quality claim'}

if __name__=='__main__':
    result=compare(*map(Path,sys.argv[1:5]));Path(sys.argv[5]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
