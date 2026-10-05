from pathlib import Path
import hashlib,json,subprocess,sys
code=Path('autonomy').resolve();sys.path.insert(0,str(code))
from pipeline.runtime_identity import verify_rootfs
from pipeline.insula_entry import launch_plan
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
variant=sys.argv[1];assert variant in ['deep_pfn','context_pfn','residual_bev']
cache=Path.home()/'.cache/waystone/waymo-perception';evidence=code/('research/architecture-'+variant+'-execution-verified.json');receipt=json.loads(evidence.read_text());source=cache/('scientific-processing/architecture-'+variant+'-v1');base=cache/('insula/architecture-'+variant+'-loss-audit-v2');base.mkdir();inputs=base/'input';inputs.mkdir();out=base/'output';out.mkdir();(inputs/'expected.json').write_text(json.dumps({'receipt':receipt,'receipt_sha256':sha(evidence),'source_directory':str(source)}))
root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);worker=Path('.scratch/audit-architecture-learning-curve.py').resolve();digest=sha(worker)
command=launch_plan(root,code,source,out,['python','/tmp/worker.py']);i=command.index('--');command[i:i]=['--ro-bind',str(worker),'/tmp/worker.py','--ro-bind',str(inputs/'expected.json'),'/tmp/expected.json','--ro-bind',str(cache/'scientific-processing/overfit-native-cache-v1'),'/tmp/native','--ro-bind',str(cache/'scientific-processing/native-one-batch-overfit-v1'),'/tmp/baseline']
run=subprocess.run(command,capture_output=True,text=True,timeout=120);(out/'live.log').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr);assert run.returncode==0 and sha(worker)==digest
record={'checks':[{'command':command,'exit_code':0}],'runtime_lock':lock,'producer_evidence_sha256':sha(evidence),'worker_sha256':digest,'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in out.iterdir()}};(code/('research/architecture-'+variant+'-loss-audit-verified.json')).write_text(json.dumps(record,indent=2)+'\n')
