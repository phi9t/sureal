"""Complete execution package and externally admitted runtime-lock binding."""
import hashlib,re
from pathlib import Path

REQUIRED=frozenset('''cohort/train_sustained.py cohort/sustained_contract.py cohort/sustained_loop.py cohort/sustained_loss.py cohort/sustained_state.py cohort/sustained_sources.py tier1/catalog.py tier1/models.py tier1/admission.py tier1/storage.py pipeline/pillar_detector.py pipeline/pillar_encoder.py pipeline/detector_loss.py gpu/norm_variants.py gpu/architecture_variants.py gpu/architecture_followups.py'''.split())

def validate_sources(root,hashes,runtime_lock,admitted_runtime_lock):
 root=Path(root)
 files={str(p.relative_to(root)):p for directory in ['pipeline','gpu','tier1','cohort'] for p in (root/directory).rglob('*.py')}
 if not isinstance(hashes,dict) or not REQUIRED<=files.keys() or hashes.keys()!=files.keys():raise ValueError('complete frozen execution-source inventory required')
 for name,path in files.items():
  expected=hashes[name]
  if path.is_symlink() or not path.is_file() or not isinstance(expected,str) or re.fullmatch('[0-9a-f]{64}',expected) is None:raise ValueError('regular pinned source required')
  with path.open('rb') as stream:found=hashlib.file_digest(stream,'sha256').hexdigest()
  if found!=expected:raise ValueError('execution source changed: '+name)
 if not isinstance(runtime_lock,dict) or runtime_lock!=admitted_runtime_lock or re.fullmatch('[0-9a-f]{64}',str(runtime_lock.get('rootfs_sha256',''))) is None or not runtime_lock.get('image_id'):raise ValueError('matching externally admitted runtime lock required')
 return {'source_files':len(files),'rootfs_sha256':runtime_lock['rootfs_sha256'],'scope':'source inventory and external lock equality; host must independently verify rootfs before launch'}
