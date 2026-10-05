"""Prepare live admitted grouping caches without modifying the original fixture."""
import json,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'tier1')]
from storage import sha,unique_payload_bytes
from admission import reserve_write
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing';fixture_path=P/'research/tier1-allclass-fixture-verified.json';fixture=json.loads(fixture_path.read_text());scene,timestamp=fixture['identity'].split(':');timestamp=int(timestamp);physical=Path(fixture['physical']);baseline=Path(fixture['controls']['baseline']['observations']).parent;targets=Path(fixture['targets']).parent;labels=Path(fixture['boxes']).parent
for key in ['physical','targets','report','boxes']:assert sha(fixture[key])==fixture[key+'_sha256']
receiptpath=P/'research/advanced-grouping-fixture-verified.json'
if receiptpath.exists():
 receipt=json.loads(receiptpath.read_text())
 for p,h in receipt['artifacts'].items():assert sha(p)==h
 print('VERIFIED existing advanced grouping fixture');sys.exit(0)
R=C/'insula/advanced-grouping-fixture-v1';R.mkdir();source=R/'source';source.mkdir()
for folder in ['advanced','pipeline']:shutil.copytree(P/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__'))
pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};root=C/'insula/rootfs-v2';lock=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,lock['rootfs_sha256']);seed=json.loads((baseline.parent/'input/job.json').read_text())['packing_seed'];controls={};base=W/'advanced-allclass-fixture-v1';base.mkdir()
for name in ['grid_fine','grid_coarse','ragged_pillars']:
 reserve_write(W,48*1024**2);d=base/name;d.mkdir();inp=d/'input';inp.mkdir();job={'case':name,'physical_filename':physical.name,'physical_sha256':fixture['physical_sha256'],'targets_sha256':fixture['targets_sha256'],'timestamp':timestamp,'packing_seed':seed};(inp/'job.json').write_text(json.dumps(job));checks=[]
 for mode in ['producer','reference']:
  out=d/mode;out.mkdir();cmd=launch_plan(root,source,physical.parent,out,['python','/experiment/advanced/cache_contract.py',mode]);i=cmd.index('--');cmd[i:i]=['--ro-bind',str(inp),'/tmp/input','--ro-bind',str(labels),'/tmp/labels','--ro-bind',str(targets),'/tmp/targets',*(['--ro-bind',str(d/'producer'),'/tmp/produced'] if mode=='reference' else [])];r=subprocess.run(cmd,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;checks.append({'command':cmd,'exit_code':0})
 assert all(sha(p)==h for p,h in pins.items());assert unique_payload_bytes(W)<=15*1024**3;controls[name]={'observations':str(d/'producer/observations.npz'),'observations_sha256':sha(d/'producer/observations.npz'),'lineage':str(d/'producer/point-lineage.npz'),'lineage_sha256':sha(d/'producer/point-lineage.npz'),'checks':checks,'validation':json.loads((d/'reference/check.json').read_text())};print('ADMITTED native grouping',name,flush=True)
artifacts={str(p):sha(p) for p in base.rglob('*') if p.is_file()};receipt={'fixture_receipt_sha256':sha(fixture_path),'identity':fixture['identity'],'controls':controls,'runtime_lock':lock,'source_pins':pins,'artifacts':artifacts,'scope':'same allclass frame/targets/physical anchors; range shard preparation remains separate'};receiptpath.write_text(json.dumps(receipt,indent=2));print('PASS native advanced grouping fixture')
