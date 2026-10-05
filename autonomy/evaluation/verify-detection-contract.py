#!/usr/bin/env python3
"""Native schema export and hand-derived default detection metric fixtures."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan
from pipeline.native_detection_adapter import parse_result
CACHE=Path.home()/'.cache/waystone/waymo-perception'
ROOT=CACHE/'metrics-rootfs'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def object_text(category='TYPE_VEHICLE',x=10,heading=0,points=20):
    return f'''objects {{ context_name: "analytic-scene" frame_timestamp_micros: 100
score: 1 overlap_with_nlz: false
object {{ type: {category} num_lidar_points_in_box: {points} detection_difficulty_level: LEVEL_1
box {{ center_x: {x} center_y: 0 center_z: 0 length: 4 width: 2 height: 2 heading: {heading} }} }} }}'''

def main():
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    lock=json.loads(Path(str(ROOT)+'.lock.json').read_text());verify_rootfs(ROOT,lock['rootfs_sha256'])
    gt=object_text()
    fixtures=[('perfect',gt,gt,1.,1.),('empty','',gt,0.,0.),
              ('wrong-class',object_text('TYPE_PEDESTRIAN'),gt,0.,0.),
              ('displaced',object_text(x=100),gt,0.,0.),
              ('heading-reversed',object_text(heading=3.141592653589793),gt,1.,0.),
              ('ignored-no-points',gt,object_text(points=0),0.,0.),
              ('extra-false-positive',gt+'\n'+object_text(x=100),gt,0.5,0.5),
              ('nlz-false-positive',gt+'\n'+object_text(x=100).replace('overlap_with_nlz: false','overlap_with_nlz: true'),gt,1.,1.)]
    checks=[];started=datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(dir=CACHE,prefix='detection-contract-') as tmp:
        source=Path(tmp)
        for name,pred,truth,_,_ in fixtures:
            (source/(name+'-pred.txt')).write_text(pred);(source/(name+'-gt.txt')).write_text(truth)
        for name,_,_,ap,aph in fixtures:
            script=f'''import subprocess
from pathlib import Path
for kind in ['pred','gt']:
    data=Path('/source/{name}-'+kind+'.txt').read_bytes()
    result=subprocess.run(['protoc','--proto_path=/upstream/src','--encode=waymo.open_dataset.Objects','waymo_open_dataset/protos/metrics.proto'],input=data,capture_output=True)
    assert result.returncode==0,result.stderr
    Path('/outputs/{name}-'+kind+'.bin').write_bytes(result.stdout)
result=subprocess.run(['/metrics-build/compute_detection_metrics','/outputs/{name}-pred.bin','/outputs/{name}-gt.bin'],capture_output=True,text=True)
print(result.stdout,end='')
import sys
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
'''
            command=['python','-c',script];plan=launch_plan(ROOT,HERE,source,out,command)
            result=subprocess.run(plan,capture_output=True,text=True)
            (out/(name+'.stdout')).write_text(result.stdout);(out/(name+'.stderr')).write_text(result.stderr)
            # Freeze full native default breakdown names, not output-derived names.
            reference=(CACHE/'detection-adapter-live-a/receipt.json')
            expected=set(json.loads(reference.read_text())['expected_breakdowns'])
            parsed=parse_result(result.returncode,result.stdout,result.stderr,expected)
            for level in [1,2]:
                metric=parsed['metrics'][f'OBJECT_TYPE_TYPE_VEHICLE_LEVEL_{level}']
                assert abs(metric['AP']-ap)<1e-6,(name,metric,ap)
                assert abs(metric['APH']-aph)<1e-6,(name,metric,aph)
            checks.append({'fixture':name,'command':plan,'exit_code':result.returncode,'expected_vehicle_AP':ap,'expected_vehicle_APH':aph})
            print(name,'passed',flush=True)
        dependencies=launch_plan(ROOT,HERE,source,out,['python','-c','import subprocess,importlib.util; assert importlib.util.find_spec("tensorflow") is None;\nfor binary in ["compute_detection_metrics","compute_segmentation_metrics"]:\n text=subprocess.check_output(["ldd","/metrics-build/"+binary],text=True); assert "not found" not in text and "tensorflow" not in text.lower(); print(binary,text)'])
        result=subprocess.run(dependencies,capture_output=True,text=True)
        (out/'dependency-closure.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr
    receipt={'stage':'native-default-detection-contract','runtime_lock':lock,'checks':checks,'started_utc':started,'ended_utc':datetime.now(timezone.utc).isoformat(),'verifier_sha256':sha(Path(__file__)),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'scope':'native schema encoding and default 3D detection analytic fixtures; ticket 09 not yet complete'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__':main()
