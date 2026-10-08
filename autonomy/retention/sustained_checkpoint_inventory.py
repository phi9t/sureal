"""Byte-lineage gate for one externally admitted sustained checkpoint.

The seven stage receipts must already be independently admitted. This helper
checks the exact retained inventory, never stage mathematics or native quality.
HDFS readback, live recovery and separate union admission still precede release.
"""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256,is_regular_file
STAGES=('train','audit','literal-loss','export','proposals','score','metrics-audit')
sha=file_sha256
def freeze_checkpoint_inventory(root,final_path,expected_sha256):
 root=Path(root);final_path=Path(final_path)
 if not root.is_dir() or any(p.is_symlink() for p in [root,*root.parents]) or not is_regular_file(final_path) or sha(final_path)!=expected_sha256:raise ValueError('regular checkpoint root and externally pinned admission required')
 final=json.loads(final_path.read_text());step=final['step'];manifest=Path(final['manifest_path'])
 if type(step) is not int or not 0<=step<=32000 or Path(final['output_directory'])!=root or not is_regular_file(manifest) or sha(manifest)!=final['manifest_sha256']:raise ValueError('bounded checkpoint identity and unchanged manifest required')
 references=final['stage_receipts']
 if set(references)!=set(STAGES):raise ValueError('all seven checkpoint stage admissions required')
 parents={str(final_path):expected_sha256};seen=set();expected={}
 for name in STAGES:
  reference=references[name];path=Path(reference['path'])
  if path in seen or not is_regular_file(path) or sha(path)!=reference['sha256']:raise ValueError('unique unchanged stage receipt required')
  seen.add(path);parents[str(path)]=reference['sha256'];record=json.loads(path.read_text())
  if record['stage']!=f'{name}-{step}' or type(record['exit_code']) is not int or record['exit_code']!=0 or record['manifest_sha256']!=final['manifest_sha256'] or not record['artifacts']:raise ValueError('completed stage with unchanged checkpoint manifest required')
  for artifact,digest in record['artifacts'].items():
   artifact=Path(artifact)
   if not is_regular_file(artifact) or sha(artifact)!=digest:raise ValueError('stage artifact changed')
   if artifact.is_relative_to(root):
    member=str(artifact.relative_to(root))
    if name!='train' or member in expected:raise ValueError('foreign or duplicate checkpoint payload admission')
    expected[member]=digest
 inventory={}
 for path in root.rglob('*'):
  if path.is_symlink():raise ValueError('checkpoint payload symlink refused')
  if path.is_file():inventory[str(path.relative_to(root))]=sha(path)
 required={'checkpoint.pt','check.json','live.log'}|{f'heads/heads-{i:02d}.npz' for i in range(16)}
 if set(inventory)!=required or inventory!=expected:raise ValueError('exact checkpoint/report/log and all16 heads required')
 report=json.loads((root/'check.json').read_text());requested=report['requested_updates'];reason=report['stop_reason']
 if report.get('manifest_sha256')!=final['manifest_sha256'] or type(report['updates']) is not int or report['updates']!=step or type(requested) is not int or not step<=requested<=32000 or reason not in {'sample','time_cap'} or reason=='sample' and requested!=step or report['resource_gate_passed'] is not True:raise ValueError('bounded resource-admitted producer outcome required')
 heads={f'heads-{i:02d}.npz':inventory[f'heads/heads-{i:02d}.npz'] for i in range(16)}
 if report['head_hashes']!=heads or report['checkpoint_sha256']!=inventory['checkpoint.pt']:raise ValueError('producer checkpoint/head identities differ')
 return {'source_sha256':inventory,'parent_receipts':parents,'manifest_sha256':final['manifest_sha256'],'step':step,'requested_step':requested,'stop_reason':reason,'stage_admissions':7,'scope':'exact externally admitted seven-stage checkpoint byte lineage; no independent math, native fit, publication or scientific acceptance'}
