import hashlib,json,math
from pathlib import Path
import numpy as np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
e=json.loads(Path('/tmp/expected.json').read_text());r=e['receipt']
assert sha('/experiment/research/architecture-'+r['manifest']['architecture_variant']+'-score-first-verified.json')==e['receipt_sha256']
for path,digest in r['artifacts'].items():
 directory=Path('/source') if 'prepared' in Path(path).parts else Path('/tmp/scored')
 assert sha(directory/Path(path).name)==digest
predictions=json.loads(Path('/source/predictions.json').read_text());truth=json.loads(Path('/source/groundtruth.json').read_text());frame=r['manifest']['frames'][0];assert len(r['manifest']['frames'])==1
scene,timestamp=frame['identity'].split(':');timestamp=int(timestamp)
with np.load('/tmp/heads/heads-00.npz',allow_pickle=False) as a:logits=a['classification'].astype(float);residuals=a['box_residuals'].astype(float);direction=a['direction'].argmax(1)
templates=np.array([x['values'] for x in json.loads(Path('/experiment/research/training-anchor-templates.candidate.json').read_text())['templates']]);index=np.arange(len(logits));template=templates[index%8];cell=index//8
anchors=np.column_stack((-63.75+.5*(cell%256),-63.75+.5*(cell//256),template[:,3],template[:,:3],template[:,4]));boxes=anchors.copy();diag=np.hypot(anchors[:,3],anchors[:,4]);boxes[:,:2]+=residuals[:,:2]*diag[:,None];boxes[:,2]+=residuals[:,2]*anchors[:,5];
with np.errstate(over='ignore',under='ignore'):boxes[:,3:6]*=np.exp(residuals[:,3:6])
raw=residuals[:,6]+anchors[:,6];boxes[:,6]=(raw+np.where((raw>0)!=(direction==1),np.pi,0)+np.pi)%(2*np.pi)-np.pi
p=np.empty_like(logits);pos=logits>=0;p[pos]=1/(1+np.exp(-logits[pos]));exp=np.exp(logits[~pos]);p[~pos]=exp/(1+exp);classes=p.argmax(1)+1;scores=p.max(1)
c,s=np.abs(np.cos(boxes[:,6])),np.abs(np.sin(boxes[:,6]));extent=np.column_stack((c*boxes[:,3]+s*boxes[:,4],s*boxes[:,3]+c*boxes[:,4]));lower=boxes[:,:2]-extent/2;upper=boxes[:,:2]+extent/2;area=extent.prod(1);candidate=index[scores>=.05];order=candidate[np.lexsort((candidate,-scores[candidate]))][:4096];kept=[]
while len(order) and len(kept)<500:
 i=order[0];kept.append(int(i));rest=order[1:];intersection=np.maximum(np.minimum(upper[i],upper[rest])-np.maximum(lower[i],lower[rest]),0).prod(1);union=area[i]+area[rest]-intersection;overlap=np.divide(intersection,union,out=np.zeros_like(intersection),where=union>0);order=rest[overlap<=.5]
assert [int(x['object_id'].split('-')[-1]) for x in predictions]==kept
physical=Path('/tmp/physical')/scene/'producer'/f'{timestamp}.npz';assert sha(physical)==frame['physical_sha256']
with np.load(physical,allow_pickle=False) as a:points=a['physical_points'][:,:3];flags=a['evaluation_nlz'];assert np.all(np.isin(flags,[-1,1]))
for record,i in zip(predictions,kept):
 assert record['context_name']==scene and record['frame_timestamp_micros']==timestamp and record['type']==int(classes[i]) and record['difficulty'] is None
 np.testing.assert_allclose(record['box'],boxes[i],rtol=1e-12,atol=1e-12);assert math.isclose(record['score'],scores[i],rel_tol=1e-12,abs_tol=1e-12)
 b=boxes[i];delta=points-b[:3];c,s=math.cos(b[6]),math.sin(b[6]);inside=(np.abs(c*delta[:,0]+s*delta[:,1])<=b[3]/2)&(np.abs(-s*delta[:,0]+c*delta[:,1])<=b[4]/2)&(np.abs(delta[:,2])<=b[5]/2)
 assert record['num_lidar_points_in_box']==int(inside.sum()) and record['overlap_with_nlz']==bool(np.any(inside&(flags==1)))
boxfile=Path('/tmp/boxes')/scene/'producer/targets.json';assert sha(boxfile)==frame['boxes_sha256'];native=[f for f in json.loads(boxfile.read_text())['frames'] if f['timestamp_micros']==timestamp];assert len(native)==1
eligible=[x for x in native[0]['rows'] if x['type'] in (1,2,3,4) and x['num_lidar_points_in_box']>0 and -64<=x['box'][0]<64 and -64<=x['box'][1]<64 and -4<=x['box'][2]<6];lookup={x['object_id']:x for x in eligible};assert {x['object_id'] for x in truth}==set(lookup)
for record in truth:
 original=lookup[record['object_id']];assert record['type']==original['type'] and record['difficulty']==original['detection_difficulty'] and record['num_lidar_points_in_box']==original['num_lidar_points_in_box'];b=original['box'].copy();b[6]=(b[6]+math.pi)%(2*math.pi)-math.pi;np.testing.assert_allclose(record['box'],b,rtol=0,atol=1e-12)
Path('/outputs/check.json').write_text(json.dumps({'predictions':len(predictions),'eligible_groundtruth':len(truth),'literal_score_first_decode_nms_and_measurement_metadata':True,'all_native_eligible_GT_retained':True,'scope':'independent one-batch prediction geometry and GT audit; protobuf/native metric audit separate'}));print('PASS independent one-batch proposals, measurement metadata and GT audit')
