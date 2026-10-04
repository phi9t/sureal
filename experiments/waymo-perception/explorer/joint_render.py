"""Native identity-indexed camera/LiDAR illustration; offline producer/reference."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from pipeline.sensor_records import select_rows,array_field
job=json.loads(Path('/tmp/input/job.json').read_text());mode=sys.argv[1];t=job['timestamp'];scene=job['scene']
source=Path('/source/lidar_camera_projection.parquet')
with source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==job['source']['sha256']
with np.load('/tmp/physical/frame.npz',allow_pickle=False) as a:xyz=a['physical_points'][:,:3];ids=a['measurement_identity']
assert len(ids)==len(xyz) and len(np.unique(ids,axis=0))==len(ids)
rows={r['key.laser_name']:r for r in select_rows(source,timestamps={t})};assert set(rows)==set(range(1,6))
image=Image.open('/tmp/camera/front.jpg').convert('RGB');W,H=image.size;indexes=[];slots=[];uvs=[]
for laser in range(1,6):
 row=rows[laser];assert row['key.segment_context_name']==scene
 for ret in (1,2):
  cp=array_field(row,f'[LiDARCameraProjectionComponent].range_image_return{ret}')
  ix=np.flatnonzero((ids[:,0]==laser)&(ids[:,1]==ret))
  if cp is None:assert len(ix)==0;continue
  pixels=ids[ix,2:];vals=cp[pixels[:,0],pixels[:,1]].reshape(-1,2,3)
  for slot in (0,1):
   v=vals[:,slot];keep=(v[:,0]==1)&(v[:,1]>=0)&(v[:,1]<W)&(v[:,2]>=0)&(v[:,2]<H)
   indexes.extend(ix[keep]);slots.extend([slot]*int(keep.sum()));uvs.extend(v[keep,1:])
indexes=np.asarray(indexes,dtype=np.int64);slots=np.asarray(slots,dtype=np.int64);uvs=np.asarray(uvs,dtype=np.int64);assert len(indexes)>1000
# Independent scalar native-value reconciliation for every correspondence.
for index,slot,uv in zip(indexes,slots,uvs):
 laser,ret,r,c=map(int,ids[index]);row=rows[laser];prefix=f'[LiDARCameraProjectionComponent].range_image_return{ret}';shape=row[prefix+'.shape'];flat=row[prefix+'.values'];offset=(r*shape[1]+c)*6+int(slot)*3;assert tuple(flat[offset:offset+3])==(1,int(uv[0]),int(uv[1]))
if mode=='reference':
 with np.load('/tmp/produced/correspondence.npz') as a:
  np.testing.assert_array_equal(a['point_indexes'],indexes);np.testing.assert_array_equal(a['slots'],slots);np.testing.assert_array_equal(a['uv'],uvs)
 for name,size in [('perspective.jpg',(960,640)),('bev.jpg',(900,900))]:
  with Image.open(Path('/tmp/produced')/name) as im:assert im.size==size
else:
 np.savez('/outputs/correspondence.npz',point_indexes=indexes,slots=slots,uv=uvs)
 def color(distance):
  f=float(np.clip(distance/80,0,1));return (int(255*f),int(230*(1-f)+80*f),int(255*(1-f)))
 image=image.resize((960,640));draw=ImageDraw.Draw(image)
 # Farther points first; near returns remain visible. No synthesized projection.
 order=np.argsort(np.linalg.norm(xyz[indexes,:2],axis=1))[::-1]
 for j in order[::max(1,len(order)//25000)]:
  u,v=uvs[j];x,y=u*960/W,v*640/H;draw.ellipse((x-1,y-1,x+1,y+1),fill=color(np.linalg.norm(xyz[indexes[j],:2])))
 draw.rectangle((0,0,960,32),fill=(15,20,28));draw.text((12,10),'FRONT camera + native projected LiDAR | cyan: near / orange: far (0-80 m)',fill=(235,240,245));image.save('/outputs/perspective.jpg',quality=90)
 canvas=Image.new('RGB',(900,900),(15,20,28));draw=ImageDraw.Draw(canvas);pos=lambda p:(450-p[1]*6,450-p[0]*6)
 for v in range(-60,61,20):
  draw.line((90,450-v*6,810,450-v*6),fill=(45,55,65));draw.line((450-v*6,90,450-v*6,810),fill=(45,55,65));draw.text((455-v*6,820),str(v),fill=(180,190,200));draw.text((55,445-v*6),str(v),fill=(180,190,200))
 mask=(np.abs(xyz[:,0])<60)&(np.abs(xyz[:,1])<60)&(xyz[:,2]>-4)&(xyz[:,2]<6)
 for p in xyz[mask]:draw.point(pos(p),fill=(90,110,130))
 front=xyz[indexes];front=front[(np.abs(front[:,0])<60)&(np.abs(front[:,1])<60)]
 for p in front:draw.point(pos(p),fill=color(np.linalg.norm(p[:2])))
 boxes=json.loads(Path('/tmp/labels/targets.json').read_text());frame=next(f for f in boxes['frames'] if f['timestamp_micros']==t)
 for r in frame['rows']:
  x,y,z,l,w,h,a=r['box']
  if r['num_lidar_points_in_box']<=0 or not (-60<x<60 and -60<y<60):continue
  c,s=np.cos(a),np.sin(a);corners=[pos((x+c*u-s*v,y+s*u+c*v)) for u,v in [(-l/2,-w/2),(l/2,-w/2),(l/2,w/2),(-l/2,w/2)]];draw.line(corners+[corners[0]],fill=(240,240,230),width=1)
 draw.polygon([(450,438),(444,459),(456,459)],fill=(255,255,255));draw.text((463,455),'Ego',fill=(235,240,245));draw.text((80,25),'BEV | X forward up / Y left left | axes in meters',fill=(235,240,245));draw.text((80,45),'Gray: all five LiDARs | colored: FRONT correspondences | white: native boxes',fill=(235,240,245));canvas.save('/outputs/bev.jpg',quality=90)
Path('/outputs/check.json').write_text(json.dumps({'scene':scene,'timestamp':t,'physical_points':len(xyz),'front_correspondences':len(indexes),'all_correspondences_scalar_checked':True,'mode':mode,'scope':'supplied native projections, all sensors/returns; not independent rolling-shutter reprojection; non-TOP geometry uncompensated'},indent=2));print('PASS joint render',mode,len(indexes))
