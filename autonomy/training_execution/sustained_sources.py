"""Execution package source-snapshot and externally admitted runtime-lock binding."""
import re
from pathlib import Path
from evidence.source_snapshot import LocalSnapshotStore,source_snapshot_receipt,verify_materialized_sources

REQUIRED=frozenset('''cohort/train_sustained.py cohort/sustained_contract.py cohort/sustained_loop.py cohort/sustained_loss.py cohort/sustained_state.py cohort/sustained_sources.py evidence/source_snapshot.py insula/entry.py insula/runtime_identity.py detection/fixed_batch_catalog.py detection/fixed_batch_models.py resources/scientific_budget.py resources/scientific_payload.py detection/pillar_detector.py detection/pillar_encoder.py detection/detector_loss.py geometry/geometry.py geometry/geometry_foundation.py detection/norm_variants.py detection/architecture_variants.py detection/architecture_followups.py resources/replay_values.py range_view/range_frontend.py range_view/range_pillar_hybrid.py range_view/sparse_window_attention.py range_view/sparse_windows.py'''.split())
SNAPSHOT_TARGET='//autonomy:sustained-run-sources'

def source_paths(root):
 root=Path(root)
 paths=sorted(str(p.relative_to(root)) for directory in ['dataset','geometry','segmentation','resources','detection','range_view','inspection','camera','pipeline','cohort','evidence','insula'] for p in (root/directory).rglob('*.py') if '__pycache__' not in p.parts)
 if not REQUIRED<=set(paths):raise ValueError('complete sustained execution source closure required')
 return paths

def snapshot_sources(root,store_root):
 return source_snapshot_receipt(root,source_paths(root),LocalSnapshotStore(store_root),target=SNAPSHOT_TARGET,materialized_root=root)

def validate_sources(root,receipt,runtime_lock,admitted_runtime_lock):
 if not isinstance(runtime_lock,dict) or runtime_lock!=admitted_runtime_lock or re.fullmatch('[0-9a-f]{64}',str(runtime_lock.get('rootfs_sha256',''))) is None or not runtime_lock.get('image_id'):raise ValueError('matching externally admitted runtime lock required')
 verified=verify_materialized_sources(root,receipt)
 if not REQUIRED<=set(verified['source_pins']):raise ValueError('complete sustained execution source closure required')
 return {'source_files':verified['source_files'],'source_snapshot_sha256':verified['source_snapshot_sha256'],'source_snapshot_target':verified.get('source_snapshot_target'),'source_pins':verified['source_pins'],'rootfs_sha256':runtime_lock['rootfs_sha256'],'scope':'source snapshot and external lock equality; host must independently verify rootfs before launch'}
