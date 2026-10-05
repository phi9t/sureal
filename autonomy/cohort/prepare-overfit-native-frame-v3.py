"""Native training-cache preparation, never a scientific optimizer invocation."""
import hashlib,json,sys,time,resource,importlib.util
from pathlib import Path
import numpy as np
sys.path.insert(0,'/tmp/workers')
from detection.pillar_packing import pack_points
from detection.anchor_grid import anchor_grid
from overfit_detection_targets_v2 import build_targets
assert importlib.util.find_spec('tensorflow') is None
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
job=json.loads(Path('/tmp/input/job.json').read_text());started=time.monotonic();source=Path('/source')/job['physical_file'];assert sha(source)==job['physical_sha256'];boxes=Path('/tmp/boxes/targets.json');assert sha(boxes)==job['box_report_sha256'];native=json.loads(boxes.read_text());frame=[f for f in native['frames'] if f['timestamp_micros']==job['timestamp_micros']];assert native['scene']==job['scene'] and len(frame)==1;frame=frame[0]
# Box-row absence cannot authorize an all-background training target.
assert frame['annotation_state']=='native_box_rows_present' and frame['rows'],'native annotation coverage unresolved'
with np.load(source,allow_pickle=False) as arrays:
 assert set(arrays.files)=={'physical_points','measurement_identity','evaluation_nlz','return_states'}
 physical=arrays['physical_points'];assert physical.ndim==2 and physical.shape[1]==4 and len(physical)>0 and np.isfinite(physical).all()
packed=pack_points(physical,roi=job['roi'],cell_size=[.25,.25],max_pillars=20000,max_points=32,seed=job['packing_seed']);assert packed['grid']==[512,512] and len(packed['counts'])>0
# Save model observations separately from point lineage and target supervision.
np.savez('/outputs/observations.npz',points=packed['points'],counts=packed['counts'],coordinates=packed['coordinates']);np.savez('/outputs/point-lineage.npz',source_indices=packed['source_indices'])
anchors=anchor_grid(nx=512,ny=512,cell_size=[.25,.25],origin=job['roi'][:2],templates=job['templates']);targets=build_targets(anchors,frame['rows'],scene=job['scene'],timestamp=job['timestamp_micros'],roi=job['roi'],positive=.5,negative=.35);np.savez('/outputs/targets.npz',**{k:targets[k] for k in ('labels','box_targets','direction_targets','target_indices')})
supervision_state='no_eligible_roi_targets' if targets['report']['eligible_targets']==0 else 'positive_anchors_present' if targets['report']['positive_anchors']>0 else 'eligible_targets_have_no_positive_anchor'
report={'scene':job['scene'],'timestamp_micros':job['timestamp_micros'],'packing_seed':job['packing_seed'],'packing':packed['counts_report'],'target_assignment':targets['report'],'supervision_state':supervision_state,'eligible_object_ids':targets['eligible_object_ids'],'physical_sha256':job['physical_sha256'],'box_report_sha256':job['box_report_sha256'],'scope':'deterministic training-only physical packing and target cache; no optimizer update or overfit/heldout quality'}
Path('/outputs/report.json').write_text(json.dumps(report,indent=2)+'\n');Path('/outputs/resources.json').write_text(json.dumps({'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}));print('PASS native overfit frame preparation',job['scene'],job['timestamp_micros'],targets['report']['positive_anchor_counts_by_class'])
