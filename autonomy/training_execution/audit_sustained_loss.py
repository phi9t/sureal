"""Read-only full16 checkpoint literal loss audit, with external file pins."""
import json,resource,time
from pathlib import Path
import numpy as np
from detection.sustained_contract import validate_contract
from detection.sustained_literal_loss import literal_losses,compare_losses
from evidence.source_snapshot import file_sha256

sha=file_sha256
def relative(root,name):
 path=Path(name)
 if path.is_absolute() or '..' in path.parts:raise ValueError('safe relative native input required')
 return Path(root)/path

def main():
 began=time.monotonic();manifest_path=Path('/tmp/inputs/manifest.json');manifest=json.loads(manifest_path.read_text());audit=json.loads(Path('/tmp/inputs/loss-audit.json').read_text());report_path=Path('/source/check.json')
 if sha(manifest_path)!=audit['manifest_sha256'] or sha(report_path)!=audit['report_sha256']:raise ValueError('externally pinned manifest/report differs')
 if manifest['recipe'] not in {'baseline','residual_bev','class_balanced','prior_bias'}:raise ValueError('frozen recipe required')
 frames=manifest['frames'];validate_contract(manifest['candidate'],[{k:f[k] for k in ['identity','split','sha256']} for f in frames]);report=json.loads(report_path.read_text())
 if report['recipe']!=manifest['recipe'] or report['manifest_sha256']!=audit['manifest_sha256'] or len(report['evaluation_losses'])!=16:raise ValueError('full16 paired recipe/evaluation report required')
 expected_names={f'heads-{i:02d}.npz' for i in range(16)}
 if set(audit['head_hashes'])!=expected_names or report['head_hashes']!=audit['head_hashes']:raise ValueError('complete externally pinned16 heads required')
 rows=[]
 for index,frame in enumerate(frames):
  directory=relative('/tmp/native',frame['relative_directory'])
  for name,digest in frame['sha256'].items():
   if sha(relative(directory,name))!=digest:raise ValueError('native input differs')
  name=f'heads-{index:02d}.npz';head=Path('/source/heads')/name
  if sha(head)!=audit['head_hashes'][name]:raise ValueError('external native head differs')
  with np.load(directory/'targets.npz',allow_pickle=False) as data:truth={k:data[k] for k in ['labels','box_targets','direction_targets']}
  with np.load(head,allow_pickle=False) as data:heads={k:data[k] for k in data.files}
  expected,parts=literal_losses(heads,truth,class_balanced=manifest['recipe']=='class_balanced');reported=report['evaluation_losses'][index]
  if reported['identity']!=frame['identity']:raise ValueError('native evaluation frame order differs')
  compare_losses(expected,reported['losses']);rows.append({'identity':frame['identity'],'literal_losses':expected,'class_contributions':parts});print('LOSS AUDITED',index,flush=True)
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 if rss>16*1024**2:raise ValueError('literal audit RSS cap exceeded')
 result={'frames':len(rows),'recipe':manifest['recipe'],'updates':report['updates'],'rows':rows,'manifest_sha256':audit['manifest_sha256'],'report_sha256':audit['report_sha256'],'head_hashes':audit['head_hashes'],'peak_rss_kib':rss,'elapsed_seconds':time.monotonic()-began,'scope':'full16 literal focal/sine-box/direction objectives; per-frame class contributions; no fit or native metric acceptance'}
 Path('/outputs/check.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS all16 literal detector losses',flush=True)
if __name__=='__main__':main()
