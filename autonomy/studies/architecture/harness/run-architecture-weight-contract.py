from pathlib import Path
from evidence.source_snapshot import file_sha256 as sha
import json,subprocess,sys
code=Path('autonomy').resolve()
from insula.runtime_identity import verify_rootfs
cache=Path.home()/'.cache/waystone/waymo-perception';old=json.loads((cache/'detector-gpu-live-a/receipt.json').read_text());verify_rootfs(cache/'gpu-rootfs',old['runtime_lock']['rootfs_sha256']);label=sys.argv[1];output=cache/'insula'/('architecture-weight-contract-'+label);output.mkdir();command=old['checks'][0]['command'].copy();command=[str(output) if x==str(cache/'detector-gpu-live-a') else '/experiment/detection/architecture-weight-contract.py' if x in ['/experiment/gpu/detector-probe.py','/experiment/detection/detector-probe.py'] else x for x in command]
pins={str(p.relative_to(code)):sha(p) for p in [code/'detection/architecture-weight-contract.py',code/'detection/architecture_weight_contract.py',code/'detection/architecture_variants.py',code/'detection/norm_variants.py',*sorted((code/'pipeline').glob('*.py'))]}
run=subprocess.run(command,capture_output=True,text=True,timeout=90);(output/'live.log').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr)
if label=='red':assert run.returncode!=0 and 'detection.architecture_weight_contract' in run.stderr
else:
 assert run.returncode==0 and all(sha(code/p)==h for p,h in pins.items())
 record={'checks':[{'command':command,'exit_code':0}],'runtime_lock':old['runtime_lock'],'candidate_hashes':pins,'artifacts':{str(p):sha(p) for p in output.iterdir()},'scope':'live complete architecture shared-weight gate and corruption refusal'};(code/'research/architecture-weight-contract-verified.json').write_text(json.dumps(record,indent=2)+'\n')
