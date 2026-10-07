"""Separate coverage replay from retained per-scene native scans."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,'/experiment/cohort')
from balanced import select_balanced,coverage_summary
candidate=json.loads(Path('/tmp/candidate.json').read_text());root=Path('/source');frames=[];scenes=[]
for item in candidate['sources']:
 scene=item['scene'];directory=root/scene;receipt=directory/'receipt.json';assert hashlib.sha256(receipt.read_bytes()).hexdigest()==item['sha256'];r=json.loads(receipt.read_text());assert all(x['exit_code']==0 for x in r['checks'])
 for original,digest in r['artifacts'].items():assert hashlib.sha256((directory/'output'/Path(original).name).read_bytes()).hexdigest()==digest
 report=json.loads((directory/'output/frames.json').read_text());assert report['scene']==scene;frames.extend(report['frames']);scenes.append(scene)
assert len(set(scenes))==64 and select_balanced(frames)==candidate['frames'] and coverage_summary(frames)==candidate['available_coverage']
# Literal identity namespace and support totals, separate from summary implementation.
summary={}
for c in map(str,range(1,5)):
 tracks=set();scene_set=set();n=0;frame_count=0
 for f in candidate['frames']:
  scene=f['identity'].split(':')[0];ids=f['objects'][c];assert len(ids)==len(set(ids));n+=len(ids)
  if ids:frame_count+=1;scene_set.add(scene)
  for obj in ids:tracks.add((scene,obj))
 summary[c]={'eligible_objects':n,'unique_tracks':len(tracks),'frames':frame_count,'scenes':len(scene_set)}
 assert n>=16 and len(tracks)>=8 and frame_count>=8 and len(scene_set)>=4
assert summary==candidate['coverage']
Path('/outputs/check.json').write_text(json.dumps({'scanned_training_scenes':64,'selected_frames':16,'literal_coverage':summary,'selection_exactly_replayed':True,'scope':'training metadata coverage only; sensor/anchor support required'},indent=2));print('PASS balanced selection replay',summary)
