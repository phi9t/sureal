"""Execution package source-snapshot and externally admitted runtime-lock binding."""
import re
from pathlib import Path
from evidence.source_snapshot import receipt_snapshot_digest,snapshot_target_and_materialize,store_from_receipt,verify_or_materialize_receipt_sources

REQUIRED=frozenset('''training_execution/train_sustained.py detection/sustained_contract.py training_execution/sustained_loop.py detection/sustained_loss.py training_execution/sustained_state.py training_execution/sustained_sources.py evidence/source_snapshot.py insula/entry.py insula/runtime_identity.py detection/fixed_batch_catalog.py detection/fixed_batch_models.py resources/scientific_budget.py resources/scientific_payload.py resources/sustained_scoring_budget.py detection/pillar_detector.py detection/pillar_encoder.py detection/detector_loss.py geometry/geometry.py geometry/geometry_foundation.py detection/norm_variants.py detection/architecture_variants.py detection/architecture_followups.py resources/replay_values.py range_view/range_frontend.py range_view/range_pillar_hybrid.py range_view/sparse_window_attention.py range_view/sparse_windows.py'''.split())
SNAPSHOT_TARGET='//autonomy/training_execution:train_sustained'

def source_paths(root):
 root=Path(root)
 paths=sorted(name for name in REQUIRED if (root/name).exists())
 if not REQUIRED<=set(paths):raise ValueError('complete sustained execution source closure required')
 return paths

def snapshot_sources(root,store_root=None,*,destination=None,store=None,repo_root=None,bazel=None,runner=None):
 root=Path(root)
 if destination is None:raise ValueError('source snapshot destination required')
 if root.name!='autonomy':raise ValueError('Bazel target source snapshot context required')
 kwargs={'repo_root':Path(repo_root) if repo_root is not None else root.parent}
 if store is not None:kwargs['store']=store
 if bazel is not None:kwargs['bazel']=bazel
 if runner is not None:kwargs['runner']=runner
 receipt=snapshot_target_and_materialize(SNAPSHOT_TARGET,destination,**kwargs)
 validate_sources(Path(destination)/'autonomy',receipt,{'rootfs_sha256':'0'*64,'image_id':'snapshot-fixture'},{'rootfs_sha256':'0'*64,'image_id':'snapshot-fixture'})
 return receipt

def cache_snapshot_for_runtime(receipt,store_root):
 digest=receipt_snapshot_digest(receipt)
 data=store_from_receipt(receipt,env_var='SUREAL_SOURCE_SNAPSHOT_STORE').fetch(digest)
 return LocalSnapshotStore(store_root).store(digest,data)

def source_pin(receipt,name):
 pins=receipt['source_pins']
 found=pins.get(name)
 if found is None:found=pins.get('autonomy/'+name)
 if found is None:raise ValueError('complete sustained execution source closure required')
 return found

def validate_sources(root,receipt,runtime_lock,admitted_runtime_lock):
 if not isinstance(runtime_lock,dict) or runtime_lock!=admitted_runtime_lock or re.fullmatch('[0-9a-f]{64}',str(runtime_lock.get('rootfs_sha256',''))) is None or not runtime_lock.get('image_id'):raise ValueError('matching externally admitted runtime lock required')
 snapshot_root=Path(receipt.get('source_snapshot_root',root))
 verified=verify_or_materialize_receipt_sources(receipt,snapshot_root,env_var='SUREAL_SOURCE_SNAPSHOT_STORE')
 required={'autonomy/'+name for name in REQUIRED} if receipt.get('schema_version')==2 else REQUIRED
 if not required<=set(verified['source_pins']):raise ValueError('complete sustained execution source closure required')
 return {'source_files':verified['source_files'],'source_snapshot_sha256':verified['source_snapshot_sha256'],'source_snapshot_target':verified.get('source_snapshot_target'),'source_pins':verified['source_pins'],'rootfs_sha256':runtime_lock['rootfs_sha256'],'scope':'source snapshot and external lock equality; host must independently verify rootfs before launch'}
