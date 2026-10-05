from pathlib import Path
import hashlib,json,subprocess,sys
code=Path('autonomy').resolve();sys.path.insert(0,str(code))
from pipeline.runtime_identity import verify_rootfs
cache=Path.home()/'.cache/waystone/waymo-perception';old=json.loads((cache/'detector-gpu-live-a/receipt.json').read_text());verify_rootfs(cache/'gpu-rootfs',old['runtime_lock']['rootfs_sha256']);label=sys.argv[1];output=cache/'insula'/('architecture-followup-contract-'+label);output.mkdir();command=old['checks'][0]['command'].copy();command=[str(output) if x==str(cache/'detector-gpu-live-a') else '/experiment/gpu/architecture-followup-contract.py' if x=='/experiment/gpu/detector-probe.py' else x for x in command]
pins={str(p.relative_to(code)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [code/'gpu/architecture-followup-contract.py',code/'gpu/architecture_followups.py',code/'gpu/architecture_variants.py',code/'gpu/norm_variants.py',*sorted((code/'pipeline').glob('*.py'))]}
run=subprocess.run(command,capture_output=True,text=True,timeout=90);(output/'live.log').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr)
if label=='red':assert run.returncode!=0 and 'gpu.architecture_followups' in run.stderr
else:
 assert run.returncode==0 and all(hashlib.sha256((code/p).read_bytes()).hexdigest()==h for p,h in pins.items())
 record={'checks':[{'command':command,'exit_code':0}],'runtime_lock':old['runtime_lock'],'candidate_hashes':pins,'artifacts':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()},'scope':'live architecture followup contract fixture; no native training/quality claim'};(code/'research/architecture-followup-contract-verified.json').write_text(json.dumps(record,indent=2)+'\n')
