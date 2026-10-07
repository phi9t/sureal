#!/usr/bin/env python3
"""Reconcile current live evaluator evidence; any failed requirement stays open."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import subprocess,sys,time
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from insula.runtime_identity import verify_rootfs
from insula.entry import launch_plan

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    cache=Path.home()/'.cache/waystone/waymo-perception';out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    names=['metrics-live-a','detection-adapter-live-a','detection-contract-live-b','segmentation-contract-live-b','segmentation-export-live-a','real-semantic-live-b','real-detection-live-b','real-nlz-live-a','real-camera-semantic-live-a','real-camera-source-check-a','real-box-source-check-a']
    receipts={};started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    for name in names:
        folder=cache/name;record=json.loads((folder/'receipt.json').read_text())
        assert record.get('exit_code',0)==0,name
        assert all(c['exit_code']==0 for c in record.get('checks',[])),name
        for artifact,h in record['artifacts'].items():assert sha(folder/artifact)==h,(name,artifact)
        for path,h in record.get('candidate_hashes',record.get('code_hashes',{})).items():assert sha(HERE/path)==h,(name,path)
        if 'verifier_sha256' in record:
            verifier={'metrics-live-a':'verify-native-metrics.py','detection-contract-live-b':'verify-detection-contract.py'}[name]
            assert sha(HERE/'evaluation'/verifier)==record['verifier_sha256']
        if 'checker_sha256' in record:
            checker={'real-camera-source-check-a':'camera/validate-real-camera-source.py','real-box-source-check-a':'evaluation/validate-real-box-source.py'}[name]
            assert sha(HERE/checker)==record['checker_sha256']
        receipts[name]={'receipt_sha256':sha(folder/'receipt.json'),'path':str(folder/'receipt.json')}
    cpu=cache/'insula/rootfs-v2';metrics=cache/'metrics-rootfs'
    cpulock=json.loads(Path(str(cpu)+'.lock.json').read_text());metriclock=json.loads(Path(str(metrics)+'.lock.json').read_text())
    verify_rootfs(cpu,cpulock['rootfs_sha256']);verify_rootfs(metrics,metriclock['rootfs_sha256'])
    contracts=json.loads((HERE/'evaluation/contracts.json').read_text());source=cache/'metrics-source/src/waymo_open_dataset'
    assert subprocess.check_output(['git','-C',str(cache/'metrics-source'),'rev-parse','FETCH_HEAD'],text=True).strip()==contracts['upstream_commit']
    for path,h in contracts['source_hashes'].items():
        assert sha(source/path)==h and sha(metrics/'upstream/src/waymo_open_dataset'/path)==h
        pinned=subprocess.check_output(['git','-C',str(cache/'metrics-source'),'show',contracts['upstream_commit']+':src/waymo_open_dataset/'+path])
        assert hashlib.sha256(pinned).hexdigest()==h
    checks=[]
    commands=[('current-boundaries',cpu,['python','/experiment/evaluation/evaluator-unit-checks.py']),
              ('native-runtime-closure',metrics,['python','-c','import importlib.util,subprocess; assert importlib.util.find_spec("tensorflow") is None;\nfor name in ["compute_detection_metrics","compute_segmentation_metrics"]:\n data=subprocess.check_output(["ldd","/metrics-build/"+name],text=True); assert "not found" not in data and "tensorflow" not in data.lower(); print(name,data)'])]
    for name,root,command in commands:
        plan=launch_plan(root,HERE,cache/'insula/m0-live-20260930-c/input',out,command);result=subprocess.run(plan,capture_output=True,text=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
        checks.append({'name':name,'command':plan,'exit_code':result.returncode})
    unit=json.loads((out/'evaluator-unit-results.json').read_text());assert unit['tests']==15 and unit['failures']==unit['errors']==unit['skips']==0
    build=(HERE/'evaluation/CMakeLists.txt').read_text();assert 'tensorflow' not in build.lower()
    resources={}
    for name in ['real-semantic-live-b','real-detection-live-b']:
        record=json.loads((cache/name/'receipt.json').read_text());assert record['elapsed_seconds']>0 and record['children_peak_rss_kib']>0
        resources[name]={k:record[k] for k in ['elapsed_seconds','children_peak_rss_kib','output_bytes']}
    for name,file in [('real-nlz-live-a','nlz-report.json'),('real-camera-semantic-live-a','camera-report.json')]:
        report=json.loads((cache/name/file).read_text());assert report['elapsed_seconds']>0 and report['peak_rss_kib']>0
        resources[name]={k:report[k] for k in ['elapsed_seconds','peak_rss_kib']}
    report={'stage':'perception-evaluator-gate-audit','status':'evidence reconciled; independent final audit required','receipts':receipts,'checks':checks,'contracts_sha256':sha(HERE/'evaluation/contracts.json'),'runtime_locks':{'cpu':cpulock,'metrics':metriclock},'resources':resources,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,'auditor_sha256':sha(Path(__file__)),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'scope':'default native 3D AP/APH and TOP semantic IoU plus explicitly nonofficial camera semantic diagnostic; LET/2D detection/panoptic STQ require separate gates'}
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS consolidated evaluator evidence audit')

if __name__=='__main__':main()
