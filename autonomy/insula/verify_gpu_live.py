#!/usr/bin/env python3
"""Materialize locked GPU rootfs and execute one-device offline probe."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parents[1]
from evidence.source_snapshot import file_sha256 as sha
from insula.runtime_identity import rootfs_identity,verify_rootfs
from insula.entry import launch_plan
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'gpu-rootfs'
IMAGE='sureal-waymo-gpu:torch291-cu130'
EXPECTED='sha256:46bdaa6e8d9058d7e09419085dfcf9a4527e801330045ae8e0f387f454413b86'

def main():
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    assert subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],text=True).strip()==EXPECTED
    lockpath=Path(str(ROOT)+'.lock.json')
    if not ROOT.exists():
        stage=CACHE/'gpu-rootfs-staging';stage.mkdir(exist_ok=False)
        cid=subprocess.check_output(['docker','create',EXPECTED,'/bin/true'],text=True).strip()
        try:
            process=subprocess.Popen(['docker','export',cid],stdout=subprocess.PIPE)
            unpack=subprocess.run(['tar','-C',str(stage),'-xf','-'],stdin=process.stdout)
            process.stdout.close()
            assert process.wait()==0 and unpack.returncode==0
        finally:subprocess.run(['docker','rm',cid],check=True,capture_output=True)
        recipes=['Dockerfile.gpu','gpu-requirements.lock','build_gpu.sh']
        lock={'image_id':EXPECTED,'rootfs_sha256':rootfs_identity(stage),
              'recipe_hashes':{name:sha(HERE/'insula'/name) for name in recipes}}
        stage.rename(ROOT);lockpath.write_text(json.dumps(lock,indent=2)+'\n')
    lock=json.loads(lockpath.read_text());verify_rootfs(ROOT,lock['rootfs_sha256'])
    for name,h in lock['recipe_hashes'].items():assert sha(HERE/'insula'/name)==h
    source=CACHE/'insula/m0-live-20260930-c/input'
    command=['/opt/waymo/bin/python','/experiment/insula/gpu_probe.py']
    plan=launch_plan(ROOT,HERE,source,out,command)
    extra=['--tmpfs','/driver'];driver={}
    for device in ['/dev/nvidia1','/dev/nvidiactl','/dev/nvidia-uvm']:
        assert Path(device).exists();extra+=['--dev-bind',device,device]
    # Dereference driver symlinks when mounting; hash the actual host ABI inputs.
    for prefix in ['libcuda.so','libnvidia-ptxjitcompiler.so','libnvidia-nvvm.so']:
        for p in sorted(Path('/usr/lib/x86_64-linux-gnu').glob(prefix+'*')):
            if p.is_file():
                extra+=['--ro-bind',str(p.resolve()),'/driver/'+p.name];driver[p.name]=sha(p.resolve())
    extra+=['--setenv','PATH','/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin',
            '--setenv','LD_LIBRARY_PATH','/driver:/usr/local/cuda/lib64',
            '--setenv','CUDA_VISIBLE_DEVICES','0']
    split=plan.index('--');plan[split:split]=extra
    started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
    result=subprocess.run(plan,capture_output=True,text=True)
    (out/'probe.stdout').write_text(result.stdout);(out/'probe.stderr').write_text(result.stderr)
    receipt={'stage':'gpu-runtime-probe','runtime_lock':lock,'driver_hashes':driver,'command':plan,'exit_code':result.returncode,
             'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-begin,
             'candidate_hashes':{str(p.relative_to(HERE)):sha(p) for p in [Path(__file__),HERE/'insula/gpu_probe.py']},
             'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
             'scope':'computation probe only; isolation and independent receipt verification pending'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(result.stdout,result.stderr,flush=True)
    if result.returncode:raise RuntimeError('GPU live computation failed')

if __name__=='__main__':main()
