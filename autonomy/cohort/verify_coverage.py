"""Live protocol, balanced-selection, and corrected original coverage admissions."""
import hashlib,json,subprocess,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACKAGE))
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cache=Path.home()/'.cache/waystone/waymo-perception';root=cache/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);base=cache/'insula/cohort-coverage-verification-v2';base.mkdir();candidate=PACKAGE/'research/balanced16-selection.candidate.json';pins={str(p):sha(p) for p in (PACKAGE/'cohort').glob('*.py')};checks=[]
def live(name,source,argv,extra=None):
 out=base/name;out.mkdir();command=launch_plan(root,PACKAGE,source,out,argv);i=command.index('--');command[i:i]=extra or [];run=subprocess.run(command,capture_output=True,text=True,timeout=180);(out/'live.log').write_text(run.stdout+run.stderr);assert run.returncode==0,(name,run.stderr);print(run.stdout+run.stderr,flush=True);checks.append({'name':name,'command':command,'exit_code':0});return out
live('tests',PACKAGE,['python','-m','unittest','discover','-s','/experiment/cohort','-p','test_*.py'])
selection=live('selection',cache/'scientific-processing/balanced-coverage-scan-gcs-v2',['python','/experiment/cohort/audit_selection.py'],['--ro-bind',str(candidate),'/tmp/candidate.json'])
oldinputs=cache/'insula/cohort16-baseline-fit20261002a/inputs';extra=['--ro-bind',str(oldinputs),'/tmp/inputs',*[x for folder,target in [('overfit-native-cache-v1','/tmp/native'),('overfit-point-frames-v1','/tmp/physical'),('overfit-box-targets-v1','/tmp/boxes')] for x in ['--ro-bind',str(cache/'scientific-processing'/folder),target]]]
original=live('original-corrected',PACKAGE,['python','/experiment/cohort/coverage.py'],extra)
assert all(sha(p)==h for p,h in pins.items());receipt={'checks':checks,'runtime_lock':lock,'worker_hashes':pins,'selection_sha256':sha(candidate),'balanced_selection':json.loads((selection/'check.json').read_text()),'original_corrected_coverage':json.loads((original/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in base.rglob('*') if p.is_file()},'scope':'independently replayed native metadata selection and corrected original input coverage; full physical/anchor support and model quality are separate'};(PACKAGE/'research/balanced16-selection-verified.json').write_text(json.dumps(receipt,indent=2)+'\n')
