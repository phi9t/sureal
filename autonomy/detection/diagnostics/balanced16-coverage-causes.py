"""Literal whole-grid assignment reconciliation and uncovered-GT collision audit.

This keeps a deliberate independent nearest-BEV rectangle implementation.
"""
import json,resource,time
from pathlib import Path
import numpy as np
from evidence.source_snapshot import file_sha256
start=time.monotonic();sha=lambda p:file_sha256(p)
e=json.loads(Path('/tmp/inputs/expected.json').read_text())
for name,key in [('manifest.json','manifest_sha256'),('anchor-templates.json','anchors_sha256')]:assert sha(Path('/tmp/inputs')/name)==e[key]
assert sha('/source/groundtruth.json')==e['groundtruth_sha256']
manifest=json.loads(Path('/tmp/inputs/manifest.json').read_text());truth=json.loads(Path('/source/groundtruth.json').read_text());templates=np.asarray([t['values'] for t in json.loads(Path('/tmp/inputs/anchor-templates.json').read_text())['templates']]);assert templates.shape==(8,5)
index=np.arange(524288);cell=index//8;t=templates[index%8];anchors=np.column_stack((-63.75+.5*(cell%256),-63.75+.5*(cell//256),t[:,3],t[:,:3],t[:,4]))
def rectangles(boxes):
 angle=boxes[:,6]%np.pi;swap=np.minimum(angle,np.pi-angle)>np.pi/4;extent=np.where(swap[:,None],boxes[:,[4,3]],boxes[:,3:5]);return np.column_stack((boxes[:,:2]-extent/2,boxes[:,:2]+extent/2))
ar=rectangles(anchors);aa=(ar[:,2:]-ar[:,:2]).prod(1);results=[];counts={'no_overlap':0,'strictly_higher_winner':0,'equal_iou_tie':0,'mixed':0};total=0
for frame in manifest['frames']:
 directory=Path('/tmp/native')/frame['relative_directory']
 for name in ['report.json','targets.npz']:assert sha(directory/name)==frame['sha256'][name]
 report=json.loads((directory/'report.json').read_text());records=sorted([r for r in truth if r['context_name']+':'+str(r['frame_timestamp_micros'])==frame['identity'] and r['num_lidar_points_in_box']>0 and all(lo<=value<hi for value,lo,hi in zip(r['box'][:3],[-64,-64,-4],[64,64,6]))],key=lambda r:r['object_id']);assert [r['object_id'] for r in records]==report['eligible_object_ids']
 gt=np.array([r['box'] for r in records],float);classes=np.array([r['type'] for r in records]);gr=rectangles(gt);ga=(gr[:,2:]-gr[:,:2]).prod(1);maximum=np.zeros(len(gt));chunk=8192
 def overlap(begin,end):
  rect=ar[begin:end];extent=np.maximum(0,np.minimum(rect[:,None,2:],gr[None,:,2:])-np.maximum(rect[:,None,:2],gr[None,:,:2]));intersection=extent.prod(2);return intersection/(aa[begin:end,None]+ga[None,:]-intersection)
 for begin in range(0,len(ar),chunk):maximum=np.maximum(maximum,overlap(begin,min(begin+chunk,len(ar))).max(0))
 with np.load(directory/'targets.npz',allow_pickle=False) as a:labels=a['labels'];indices=a['target_indices']
 covered=set(np.unique(indices[labels>0]).tolist());missing=[i for i in range(len(gt)) if i not in covered];assert {records[i]['object_id'] for i in missing}==set(report['target_assignment']['uncovered_object_ids']);details={i:{'object_id':records[i]['object_id'],'class':int(classes[i]),'maximum_iou':float(maximum[i]),'maximizing_anchors':0,'strict_higher_anchors':0,'equal_tie_anchors':0,'winner_indices':set()} for i in missing}
 for begin in range(0,len(ar),chunk):
  end=min(begin+chunk,len(ar));o=overlap(begin,end);best=o.argmax(1);best_value=o[np.arange(end-begin),best];forced=((o==maximum[None,:])&(maximum[None,:]>0)).any(1);positive=(best_value>=.5)|forced;literal=np.full(end-begin,-1,dtype=np.int64);literal[best_value<.35]=0;literal[positive]=classes[best[positive]];matched=np.full(end-begin,-1,dtype=np.int64);matched[positive]=best[positive]
  np.testing.assert_array_equal(labels[begin:end],literal);np.testing.assert_array_equal(indices[begin:end],matched)
  for i,value in details.items():
   selected=(o[:,i]==maximum[i])&(maximum[i]>0);assert not np.any(selected&(best==i));value['maximizing_anchors']+=int(selected.sum());value['strict_higher_anchors']+=int((selected&(best_value>maximum[i])).sum());value['equal_tie_anchors']+=int((selected&(best_value==maximum[i])).sum());value['winner_indices'].update(best[selected].tolist())
 for i,value in details.items():
  strict,tied=value['strict_higher_anchors'],value['equal_tie_anchors'];cause='no_overlap' if maximum[i]==0 else 'strictly_higher_winner' if strict and not tied else 'equal_iou_tie' if tied and not strict else 'mixed';counts[cause]+=1;value['cause']=cause
  value['winners']=[{'object_id':records[j]['object_id'],'class':int(classes[j]),'identical_nearest_BEV_rectangle_at_1e-9':bool(np.allclose(gr[i],gr[j],rtol=0,atol=1e-9)),'center_z_difference':float(gt[j,2]-gt[i,2])} for j in sorted(value.pop('winner_indices'))]
 results.append({'identity':frame['identity'],'all524288_labels_and_indices_exact':True,'uncovered':list(details.values())});total+=len(details);print('AUDITED ASSIGNMENT',frame['identity'],len(details),flush=True)
summary={'frames':results,'uncovered_objects':total,'uncovered_causes':counts,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'independent literal existing nearest-BEV assignment/forced-match conflicts; no replacement targets, architecture or model inference'}
Path('/outputs/check.json').write_text(json.dumps(summary,indent=2)+'\n');print('PASS literal uncovered-target causes',counts,flush=True)
