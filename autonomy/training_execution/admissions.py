"""Require independent identity coverage and all mandatory live fit admissions."""
import json
from pathlib import Path
from detection.balanced import coverage_summary
from evidence.source_snapshot import file_sha256,require_regular_file
sha=file_sha256
def validate_coverage_claim(claim,frames):
 if set(claim)!={'1','2','3','4'}:raise ValueError('Exactly all four classes required')
 literal=coverage_summary([dict(f,objects=f['covered_objects']) for f in frames])
 if claim!=literal:raise ValueError('Producer coverage differs from independent covered identities')
 if any(v['eligible_objects']<16 or v['unique_tracks']<8 or v['frames']<8 or v['scenes']<4 for v in literal.values()):raise ValueError('Insufficient independent class coverage')
 return literal

def required_fit_admissions(run):
 run=Path(run);names=['protocol','coverage','train','checkpoint','loss']
 if any(not (run/(name+'-verified.json')).is_file() for name in names):raise ValueError('Missing mandatory live fit admission')
 meta=json.loads((run/'run.json').read_text());result={}
 for name in names:
  path=run/(name+'-verified.json');r=json.loads(path.read_text())
  if not r.get('checks') or any(c['exit_code']!=0 for c in r['checks']):raise ValueError('Failed admission: '+name)
  if r['manifest_sha256']!=meta['manifest_sha256'] or r['source_sha256']!=meta['source_sha256']:raise ValueError('Admission source/manifest mismatch: '+name)
  for p,h in r['artifacts'].items():
   try:artifact=require_regular_file(p)
   except ValueError as error:raise ValueError('Changed admission artifact: '+p) from error
   if sha(artifact)!=h:raise ValueError('Changed admission artifact: '+p)
  result[name]={'sha256':sha(path),'validation':r.get('validation')}
 cp=result['checkpoint']['validation'];loss=result['loss']['validation']
 if cp.get('frames_exactly_replayed')!=16 or not cp.get('initial_and_final_heads_exact') or cp.get('optimizer_updates')!=2000 or not cp.get('optimizer_state_validated'):raise ValueError('Incomplete checkpoint replay')
 if loss.get('literal_frame_checkpoint_losses')!=len(meta['manifest']['frames'])*len(meta['manifest']['execution']['checkpoint_grid']) or not loss.get('timing_and_clipping_validated') or not loss.get('all_frames_optimized'):raise ValueError('Incomplete literal loss replay')
 return result
