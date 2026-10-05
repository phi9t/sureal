"""Exact retained pilot payload inventory bound to all21 admitted stage receipts.

This verifies bytes and lineage, not model quality or the underlying stage math.
The final receipt must first be independently admitted; expected_sha256 is its
external pin. Publication still requires full HDFS readback/live recovery and
independent whole-member-union verification before any release.
"""
import hashlib,json
from pathlib import Path
STEPS=(0,19,35)
STAGES=('train','audit','literal-loss','export','proposals','score','metrics-audit')
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def regular(path):return path.is_file() and not any(p.is_symlink() for p in [path,*path.parents])
def freeze_pilot_inventory(root,final_path,expected_sha256):
 root=Path(root);final_path=Path(final_path)
 if root.is_symlink() or not root.is_dir() or not regular(final_path) or sha(final_path)!=expected_sha256:raise ValueError('regular pilot root and externally pinned final receipt required')
 final=json.loads(final_path.read_text());manifest=Path(final['run_directory'])/'input/manifest.json'
 if Path(final['output_directory'])!=root or not regular(manifest) or sha(manifest)!=final['manifest_sha256']:raise ValueError('original pilot root/manifest differs')
 references=final['stage_receipts'];required={f'{name}-{step}' for step in STEPS for name in STAGES}
 if set(references)!=required:raise ValueError('complete21 pilot stage admissions required')
 expected={};parents={str(final_path):expected_sha256};seen=set();training={}
 for key,reference in references.items():
  receipt=Path(reference['path'])
  if not regular(receipt) or receipt in seen or sha(receipt)!=reference['sha256']:raise ValueError('unique unchanged pilot stage receipt required')
  seen.add(receipt);parents[str(receipt)]=reference['sha256'];record=json.loads(receipt.read_text())
  if record['stage']!=key or record['exit_code']!=0 or record['manifest_sha256']!=final['manifest_sha256']:raise ValueError('pilot stage/manifest admission differs')
  for name,digest in record['artifacts'].items():
   artifact=Path(name)
   if not regular(artifact) or sha(artifact)!=digest:raise ValueError('admitted stage artifact changed')
   if artifact.is_relative_to(root):
    if key.split('-')[0]!='train' or str(artifact.relative_to(root)) in expected:raise ValueError('unexpected or duplicate payload admission')
    expected[str(artifact.relative_to(root))]=digest
  if key.startswith('train-'):training[int(key.rsplit('-',1)[1])]=record
 inventory={}
 for p in root.rglob('*'):
  if p.is_symlink():raise ValueError('pilot payload symlink refused')
  if p.is_file():inventory[str(p.relative_to(root))]=sha(p)
 if not inventory or inventory!=expected:raise ValueError('pilot payload differs from complete admitted inventory')
 for step in STEPS:
  directory=root/f'update-{step:02d}';report=json.loads((directory/'check.json').read_text());heads={f'heads-{i:02d}.npz':sha(directory/'heads'/f'heads-{i:02d}.npz') for i in range(16)}
  if report['updates']!=step or report['stop_reason']!='sample' or report['resource_gate_passed'] is not True or report['checkpoint_sha256']!=sha(directory/'checkpoint.pt') or report['head_hashes']!=heads:raise ValueError('exact successful producer checkpoint/full16 heads required')
 return {'source_sha256':inventory,'parent_receipts':parents,'manifest_sha256':final['manifest_sha256'],'stage_admissions':len(references),'scope':'exact21-stage-bound engineering pilot payload inventory; no independent math/scientific quality admission'}
