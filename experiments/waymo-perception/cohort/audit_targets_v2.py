"""Literal anchor/assignment/residual audit; imports no production math helpers."""
import hashlib,json,math
from pathlib import Path
import numpy as np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(prepared,boxroot,job):
 prepared,boxroot=map(Path,(prepared,boxroot));assert sha(boxroot/'targets.json')==job['boxes_sha256'];roi=np.array([-64,-64,-4,64,64,6])
 boxes=json.loads((boxroot/'targets.json').read_text());assert boxes['scene']==job['scene'];frames=[f for f in boxes['frames'] if f['timestamp_micros']==job['timestamp_micros']];assert len(frames)==1 and frames[0]['annotation_state']=='native_box_rows_present';rows=frames[0]['rows'];gtrows=[];reasons={k:0 for k in ('unknown_class','zero_native_points','center_outside_roi','eligible')}
 for row in rows:
  assert row['context_name']==job['scene'] and row['frame_timestamp_micros']==job['timestamp_micros']
  if row['type'] not in (1,2,3,4):reason='unknown_class'
  elif row['num_lidar_points_in_box']==0:reason='zero_native_points'
  elif not all(roi[i]<=row['box'][i]<roi[i+3] for i in range(3)):reason='center_outside_roi'
  else:reason='eligible';gtrows.append(row)
  reasons[reason]+=1
 gtrows.sort(key=lambda r:r['object_id']);gt=np.asarray([r['box'] for r in gtrows],dtype=np.float64).reshape(-1,7);gt[:,6]=(gt[:,6]+np.pi)%(2*np.pi)-np.pi;classes=np.asarray([r['type'] for r in gtrows],dtype=np.int64);templates=np.asarray(job['templates']);N=524288;i=np.arange(N);cell=i//8;t=templates[i%8];anchors=np.column_stack((roi[0]+(2*(cell%256)+1)*.25,roi[1]+(2*(cell//256)+1)*.25,t[:,3],t[:,:3],t[:,4]))
 def rect(b):
  angle=b[:,6]%np.pi;swap=np.minimum(angle,np.pi-angle)>np.pi/4;wx=np.where(swap,b[:,4],b[:,3]);wy=np.where(swap,b[:,3],b[:,4]);return np.column_stack((b[:,0]-wx/2,b[:,1]-wy/2,b[:,0]+wx/2,b[:,1]+wy/2))
 ar=rect(anchors);gr=rect(gt)
 def overlap(start,end):
  a=ar[start:end];w=np.maximum(0,np.minimum(a[:,None,2],gr[None,:,2])-np.maximum(a[:,None,0],gr[None,:,0]));h=np.maximum(0,np.minimum(a[:,None,3],gr[None,:,3])-np.maximum(a[:,None,1],gr[None,:,1]));inter=w*h;aa=(a[:,2]-a[:,0])*(a[:,3]-a[:,1]);ga=(gr[:,2]-gr[:,0])*(gr[:,3]-gr[:,1]);return inter/(aa[:,None]+ga[None,:]-inter)
 maxima=np.zeros(len(gt));chunk=8192
 if len(gt):
  for start in range(0,N,chunk):maxima=np.maximum(maxima,overlap(start,min(start+chunk,N)).max(axis=0))
 covered=set();positive_counts={str(c):0 for c in range(1,5)};positive_total=negative_total=ignored_total=0
 with np.load(prepared/'targets.npz',allow_pickle=False) as a:
  assert set(a.files)=={'labels','box_targets','direction_targets','target_indices'}
  assert a['labels'].shape==(N,) and a['box_targets'].shape==(N,7) and a['direction_targets'].shape==(N,) and a['target_indices'].shape==(N,)
  a={name:a[name] for name in a.files}
  for start in range(0,N,chunk):
   end=min(start+chunk,N);length=end-start;labels=np.zeros(length,dtype=np.int64);matched=np.full(length,-1,dtype=np.int64);residuals=np.zeros((length,7));direction=np.zeros(length,dtype=np.int64)
   if len(gt):
    o=overlap(start,end);best=o.argmax(axis=1);maximum=o[np.arange(length),best];forced=np.any((o==maxima[None,:])&(maxima[None,:]>0),axis=1);positive=(maximum>=.5)|forced;labels[:]=-1;labels[maximum<.35]=0;labels[positive]=classes[best[positive]];matched[positive]=best[positive];covered.update(best[positive].tolist());box=gt[best[positive]];anc=anchors[start:end][positive];diagonal=np.sqrt(anc[:,3]**2+anc[:,4]**2);residuals[positive,0]=(box[:,0]-anc[:,0])/diagonal;residuals[positive,1]=(box[:,1]-anc[:,1])/diagonal;residuals[positive,2]=(box[:,2]-anc[:,2])/anc[:,5];residuals[positive,3:6]=np.log(box[:,3:6]/anc[:,3:6]);residuals[positive,6]=box[:,6]-anc[:,6];direction[positive]=(box[:,6]>0).astype(np.int64)
   np.testing.assert_array_equal(a['labels'][start:end],labels);np.testing.assert_array_equal(a['target_indices'][start:end],matched);np.testing.assert_array_equal(a['direction_targets'][start:end],direction);np.testing.assert_allclose(a['box_targets'][start:end],residuals,rtol=1e-12,atol=1e-12)
   positive_total+=int((labels>0).sum());negative_total+=int((labels==0).sum());ignored_total+=int((labels<0).sum())
   for c in range(1,5):positive_counts[str(c)]+=int((labels==c).sum())
 report=json.loads((prepared/'report.json').read_text());tr=report;assert tr['target_reasons']==reasons and tr['positive_anchor_counts_by_class']==positive_counts and tr['positive_anchors']==positive_total and tr['negative_anchors']==negative_total and tr['ignored_anchors']==ignored_total and tr['eligible_targets_without_positive_anchor']==len(gt)-len(covered);assert tr['uncovered_object_ids']==[r['object_id'] for j,r in enumerate(gtrows) if j not in covered]
 return {'identity':f"{job['scene']}:{job['timestamp_micros']}",'covered_objects':{str(c):sorted(gtrows[i]['object_id'] for i in covered if gtrows[i]['type']==c) for c in range(1,5)},'eligible_GT':len(gt),'uncovered_GT':len(gt)-len(covered),'positive_anchor_counts_by_class':positive_counts,'all_anchor_labels_indices_residuals_directions_exact':True}
job=json.loads(Path('/tmp/input/job.json').read_text());results=[]
for frame in job['selection']:
 timestamp=int(frame['identity'].split(':')[1]);results.append(verify(Path('/source')/str(timestamp),'/tmp/boxes',dict(job,timestamp_micros=timestamp)));print('AUDITED TARGETS',frame['identity'],flush=True)
Path('/outputs/check.json').write_text(json.dumps({'frames':results,'scope':'independent literal target assignment/residual/coverage replay; no measurement retention or model quality claim'},indent=2))
