from pathlib import Path
import hashlib,json,subprocess,sys
code=Path('autonomy').resolve();sys.path.insert(0,str(code))
from insula.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
variant=sys.argv[1];cache=Path.home()/'.cache/waystone/waymo-perception';evidence=code/('research/architecture-'+variant+'-execution-verified.json');receipt=json.loads(evidence.read_text());
def verify_producer():
 for path,h in receipt['artifacts'].items():assert sha(path)==h,path
 for path,h in receipt['candidate_hashes'].items():assert sha(code/path)==h,path
 for path,h in receipt['driver_hashes'].items():assert sha(path)==h,path
 command=receipt['checks'][0]['command'];inputs=Path(command[command.index('/tmp/inputs')-1]);native=Path(command[command.index('/tmp/native')-1])
 assert sha(inputs/'manifest.json')==receipt['manifest_sha256']
 for frame in receipt['manifest']['frames']:
  for path,h in frame['sha256'].items():assert sha(native/frame['relative_directory']/path)==h,path
verify_producer()
verify_rootfs(cache/'gpu-rootfs',receipt['runtime_lock']['rootfs_sha256']);base=cache/'insula'/('architecture-'+variant+'-checkpoint-audit-strict-v2');base.mkdir();out=base/'output';out.mkdir()
command=receipt['checks'][0]['command'].copy();command=[str(out) if x==str(cache/'scientific-processing'/('architecture-'+variant+'-v1')) else '/experiment/gpu/audit-retain64-checkpoint.py' if x=='/experiment/gpu/native-retain64-learning-curve.py' else x for x in command];i=command.index('--');command[i:i]=['--ro-bind',str(cache/'scientific-processing'/('architecture-'+variant+'-v1')),'/tmp/retained'];worker=code/'gpu/audit-retain64-checkpoint.py';digest=sha(worker)
run=subprocess.run(command,capture_output=True,text=True,timeout=120);(out/'live.log').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr);assert run.returncode==0 and sha(worker)==digest
verify_producer()
previous=code/('research/architecture-'+variant+'-checkpoint-audit-verified.json')
if previous.exists():previous.with_name(previous.stem+'-historical-v1.json').write_bytes(previous.read_bytes())
record={'checks':[{'command':command,'exit_code':0}],'runtime_lock':receipt['runtime_lock'],'producer_evidence_sha256':sha(evidence),'worker_sha256':digest,'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in out.iterdir()}};(code/('research/architecture-'+variant+'-checkpoint-audit-verified.json')).write_text(json.dumps(record,indent=2)+'\n')
