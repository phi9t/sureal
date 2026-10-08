#!/usr/bin/env python3
"""Materialize native metrics image and run pinned upstream tests offline."""
import sys
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256 as sha
from insula.runtime_identity import rootfs_identity,verify_rootfs
from insula.entry import launch_plan
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'metrics-rootfs'
IMAGE='sureal-waymo-metrics:source-pinned'

def materialize():
    lockpath=Path(str(ROOT)+'.lock.json')
    if ROOT.exists():
        lock=json.loads(lockpath.read_text());verify_rootfs(ROOT,lock['rootfs_sha256']);return lock
    image=subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()
    with tempfile.TemporaryDirectory(dir=CACHE,prefix='.metrics-rootfs-') as tmp:
        stage=Path(tmp);cid=subprocess.check_output(['docker','create',image,'/bin/true'],text=True).strip()
        try:
            export=subprocess.Popen(['docker','export',cid],stdout=subprocess.PIPE)
            result=subprocess.run(['tar','-C',str(stage),'-xf','-'],stdin=export.stdout)
            export.stdout.close()
            if export.wait() or result.returncode:raise RuntimeError('rootfs export failed')
        finally:subprocess.run(['docker','rm',cid],check=True,capture_output=True)
        lock={'schema_version':1,'image_id':image,'rootfs_sha256':rootfs_identity(stage),'upstream_commit':'99a4cb3ff07e2fe06c2ce73da001f850f628e45a',
              'recipe_hashes':{name:sha(HERE/'evaluation'/name) for name in ['Dockerfile','CMakeLists.txt']}}
        stage.rename(ROOT);lockpath.write_text(json.dumps(lock,indent=2)+'\n')
        return lock

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);lock=materialize();records=[]
    for name,h in lock['recipe_hashes'].items():
        if sha(HERE/'evaluation'/name)!=h:raise ValueError('metrics recipe changed')
    source=CACHE/'insula/m0-live-20260930-c/input';base='/upstream/src/waymo_open_dataset/metrics/tools/'
    commands=[('detection-tests',['/metrics-build/detection_metrics_test','--gtest_output=json:/outputs/detection-tests.json']),
              ('segmentation-tests',['/metrics-build/segmentation_metrics_test','--gtest_output=json:/outputs/segmentation-tests.json']),
              ('detection-fake',['/metrics-build/compute_detection_metrics',base+'fake_predictions.bin',base+'fake_ground_truths.bin']),
              ('segmentation-fake',['/metrics-build/compute_segmentation_metrics',base+'fake_segmentation_predictions.bin',base+'fake_segmentation_groundtruths.bin']),
              ('dependency-check',['python','-c','import importlib.util, subprocess; assert importlib.util.find_spec("tensorflow") is None; output=subprocess.check_output(["ldd","/metrics-build/compute_detection_metrics"],text=True); assert "tensorflow" not in output.lower(); print(output)'])]
    started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    for name,command in commands:
        verify_rootfs(ROOT,lock['rootfs_sha256'])
        plan=launch_plan(ROOT,HERE,source,out,command);p=subprocess.run(plan,text=True,capture_output=True)
        (out/(name+'.log')).write_text(p.stdout+p.stderr);records.append({'name':name,'command':plan,'exit_code':p.returncode});print(name,p.returncode,flush=True)
        if p.returncode:raise RuntimeError('native metric live check failed')
    for name in ['detection','segmentation']:
        report=json.loads((out/(name+'-tests.json')).read_text());assert report['failures']==0 and report['tests']>0
    receipt={'schema_version':1,'stage':'native-metrics-live','runtime_lock':lock,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),
             'checks':records,'elapsed_seconds':time.monotonic()-begin,'verifier_sha256':sha(Path(__file__)),
             'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'status':'live tests passed; external fixture expectation/config audit pending'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS native metric live suites',out,flush=True)

if __name__=='__main__':main()
