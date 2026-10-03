"""Freeze an outcome-independent all-class frame and its retention controls."""
import json,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'tier1'))
from catalog import select_fixture,catalog
from storage import sha,unique_payload_bytes
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing'
existing=P/'research/tier1-allclass-fixture-verified.json'
if existing.exists():
 receipt=json.loads(existing.read_text())
 for key in ['targets','report','physical','boxes']:assert sha(receipt[key])==receipt[key+'_sha256']
 for control in receipt['controls'].values():
  for key in ['observations','lineage']:assert sha(control[key])==control[key+'_sha256']
 for path,digest in receipt['source_pins'].items():assert sha(path)==digest
 verify_rootfs(C/'insula/rootfs-v2',receipt['runtime_lock']['rootfs_sha256'])
 print('VERIFIED existing immutable all-class fixture',receipt['identity']);sys.exit(0)
R=C/'insula/tier1-allclass-fixture-v2';R.mkdir();source=R/'source';source.mkdir();shutil.copytree(P/'pipeline',source/'pipeline',ignore=shutil.ignore_patterns('__pycache__'));shutil.copytree(P/'tier1',source/'tier1',ignore=shutil.ignore_patterns('__pycache__'));pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};root=C/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256'])
auditpath=P/'research/balanced16-labels-and-anchor-coverage-v3-verified.json';audit=json.loads(auditpath.read_text())
for p,h in audit['artifacts'].items():assert sha(p)==h
selected=select_fixture(audit);scene,t=selected['identity'].split(':');timestamp=int(t);baseline=W/'balanced16-native-v2'/scene/t/'producer';physical=W/'balanced16-physical-v2'/scene/'producer'/f'{t}.npz';labels=W/'balanced16-labels-v2'/scene/'producer';job0=json.loads((baseline.parent/'input/job.json').read_text());controls={};base=W/'tier1-allclass-fixture-v2';base.mkdir()
for name,points,pillars in [('baseline',32,20000),('retain64',64,20000),('all_pillars',32,30000)]:
 d=base/name;d.mkdir();inp=d/'input';inp.mkdir();job={'timestamp':timestamp,'roi':[-64,-64,-4,64,64,6],'packing_seed':job0['packing_seed'],'physical_filename':physical.name,'physical_sha256':sha(physical),'max_points':points,'pillar_cap':pillars};(inp/'job.json').write_text(json.dumps(job));checks=[]
 for mode in ['producer','reference']:
  out=d/mode;out.mkdir();cmd=launch_plan(root,source,physical.parent,out,['python','/experiment/tier1/packing.py',mode]);i=cmd.index('--');cmd[i:i]=['--ro-bind',str(inp),'/tmp/input','--ro-bind',str(labels),'/tmp/labels','--ro-bind',str(baseline),'/tmp/baseline',*(['--ro-bind',str(d/'producer'),'/tmp/produced'] if mode=='reference' else [])];r=subprocess.run(cmd,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;checks.append({'command':cmd,'exit_code':0})
 assert all(sha(p)==h for p,h in pins.items());assert unique_payload_bytes(W)<15*1024**3;controls[name]={'observations':str(d/'producer/observations.npz'),'observations_sha256':sha(d/'producer/observations.npz'),'lineage':str(d/'producer/point-lineage.npz'),'lineage_sha256':sha(d/'producer/point-lineage.npz'),'checks':checks,'validation':json.loads((d/'reference/check.json').read_text())};print('ADMITTED',name,'all-class fixture',flush=True)
receipt={'identity':selected['identity'],'selected_coverage':selected,'fixture_selection_rule':'allfourclasses; >=5cyclists; zero uncovered; minimum GT then lexical ID','controls':controls,'targets':str(baseline/'targets.npz'),'targets_sha256':sha(baseline/'targets.npz'),'report':str(baseline/'report.json'),'report_sha256':sha(baseline/'report.json'),'physical':str(physical),'physical_filename':physical.name,'physical_sha256':sha(physical),'boxes':str(labels/'targets.json'),'boxes_sha256':sha(labels/'targets.json'),'source_pins':pins,'runtime_lock':lock,'upstream_label_admission_sha256':sha(auditpath),'matrix':catalog(),'scope':'one fixed all-class training frame; no model outcomes used for selection'};(P/'research/tier1-allclass-fixture-verified.json').write_text(json.dumps(receipt,indent=2));print('READY single-frame all-class fixture',selected['identity'],flush=True)
