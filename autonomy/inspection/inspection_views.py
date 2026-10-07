"""Deterministic sensor-to-scene views with retained overlay point identities."""
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np
import pyarrow.parquet as pq
from PIL import Image,ImageDraw
from .inspection import bev_raster,projection_samples,range_raster
from dataset.sensor_records import select_rows


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def scalar_image(values):
    valid=np.isfinite(values);gray=np.zeros(values.shape,dtype=np.uint8)
    gray[valid]=np.clip(values[valid]*2,0,255).astype(np.uint8)
    rgb=np.repeat(gray[...,None],3,axis=-1);rgb[~valid]=[60,0,60]
    return Image.fromarray(rgb)


def main():
    source,geometry,out=map(Path,sys.argv[1:4]);out.mkdir(exist_ok=False)
    dataset=json.loads((source/'slice.json').read_text());reconstruction=json.loads((geometry/'report.json').read_text())
    records=[]
    for context in dataset['contexts']:
        paths={e['component']:source/e['relative_path'] for e in dataset['objects'] if e['context']==context}
        top=[r for r in reconstruction['rows'] if r['context']==context and r['laser']==1 and r['return']==1]
        selected={next(r['timestamp'] for r in top if r['segmentation_present']),next(r['timestamp'] for r in top if not r['segmentation_present'])}
        shapes={}
        columns=['key.frame_timestamp_micros','key.laser_name',*[f'[LiDARComponent].range_image_return{i}.shape' for i in [1,2]]]
        for r in pq.read_table(paths['lidar'],columns=columns).to_pylist():
            if r['key.frame_timestamp_micros'] in selected:
                for ret in [1,2]:shapes[(r['key.frame_timestamp_micros'],r['key.laser_name'],ret)]=r[f'[LiDARComponent].range_image_return{ret}.shape'][:2]
        camera_rows=list(select_rows(paths['camera_image'],timestamps=selected))
        camera_labels={(r['key.frame_timestamp_micros'],r['key.camera_name']):r for r in select_rows(paths['camera_segmentation'],timestamps=selected)}
        for stamp in sorted(selected):
            name=f'{context}-{stamp}';frameout=out/name;frameout.mkdir();xyzs=[];sensorrows=[]
            for r in reconstruction['rows']:
                if r['context']!=context or r['timestamp']!=stamp:continue
                if sha(geometry/r['artifact'])!=r['sha256']:raise ValueError('geometry artifact changed')
                with np.load(geometry/r['artifact']) as a:
                    xyzs.append(a['xyz']);shape=shapes[(stamp,r['laser'],r['return'])]
                    values=range_raster(a['pixels'],a['physical_features'][:,0],shape)
                    scalar_image(values).save(frameout/f'range-{r["laser"]}-{r["return"]}.png')
                    sensorrows.append({'laser':r['laser'],'return':r['return'],'points':r['points'],'unknown_pixels':int(np.prod(shape)-r['points']),
                                       'geometry_artifact':r['artifact'],'geometry_sha256':r['sha256']})
            xyz=np.concatenate(xyzs);density,counts=bev_raster(xyz)
            np.save(frameout/'bev-density.npy',density)
            gray=np.clip(np.log1p(density)/np.log(65)*255,0,255).astype(np.uint8)
            Image.fromarray(gray).resize((900,900),Image.Resampling.NEAREST).save(frameout/'bev.png')
            # Oblique orthographic point-cloud view, explicitly distinct from camera projection.
            oblique=xyz[::max(1,len(xyz)//30000)];uv=np.c_[450+3*(oblique[:,0]-oblique[:,1]),600-2*(oblique[:,0]+oblique[:,1])-8*oblique[:,2]]
            canvas=Image.new('RGB',(900,900));draw=ImageDraw.Draw(canvas)
            for x,y in uv:
                if 0<=x<900 and 0<=y<900:draw.point((int(x),int(y)),fill=(130,210,230))
            canvas.save(frameout/'point-cloud-oblique.png')
            toprow=next(r for r in top if r['timestamp']==stamp)
            with np.load(geometry/toprow['artifact']) as a:
                if 'segmentation' in a:
                    semantic=np.full(shapes[(stamp,1,1)],-1,dtype=np.int32);semantic[a['pixels'][:,0],a['pixels'][:,1]]=a['segmentation'][:,1]
                    np.save(frameout/'top-semantic.npy',semantic)
                    colors=np.zeros((*semantic.shape,3),dtype=np.uint8);valid=semantic>=0
                    for ch,mult in enumerate([53,97,193]):colors[...,ch][valid]=(semantic[valid]*mult%255).astype(np.uint8)
                    Image.fromarray(colors).save(frameout/'top-semantic.png')
                cameras=[]
                for camera_row in camera_rows:
                    if camera_row['key.frame_timestamp_micros']!=stamp:continue
                    camera=camera_row['key.camera_name'];image_bytes=camera_row['[CameraImageComponent].image']
                    (frameout/f'camera-{camera}.jpg').write_bytes(image_bytes)
                    image=Image.open(io.BytesIO(image_bytes)).convert('RGB');draw=ImageDraw.Draw(image)
                    indexes,slots,uv=projection_samples(a['camera_projection'],camera,*image.size)
                    np.savez(frameout/f'camera-{camera}-samples.npz',point_indexes=indexes,slots=slots,uv=uv,pixels=a['pixels'][indexes])
                    for x,y in uv:draw.ellipse((int(x)-1,int(y)-1,int(x)+1,int(y)+1),fill=(0,255,160))
                    image.save(frameout/f'camera-{camera}-overlay.png')
                    label=camera_labels.get((stamp,camera))
                    if label:
                        p='[CameraSegmentationLabelComponent]';pan=np.asarray(Image.open(io.BytesIO(label[p+'.panoptic_label'])));sem=pan//label[p+'.panoptic_label_divisor']
                        np.save(frameout/f'camera-{camera}-semantic.npy',sem)
                    cameras.append({'camera':camera,'samples':len(indexes),'width':image.width,'height':image.height,'segmentation_present':label is not None,
                                    'source_image_sha256':hashlib.sha256(image_bytes).hexdigest()})
            records.append({'context':context,'timestamp':stamp,'directory':name,'sensors':sensorrows,'cameras':cameras,'points':len(xyz),'bev':counts,
                            'top_segmentation_present':toprow['segmentation_present']})
    artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    report={'schema_version':1,'frames':records,'artifacts':artifacts,'geometry_report_sha256':sha(geometry/'report.json'),
            'display_contract':{'bev':'x horizontal, y upward; [-75,75) meters; 0.5m cells; density is observation support, not free-space truth',
                                'range':'gray=clipped 2*meters; purple=unobserved/invalid range','camera':'native original-image pixels; TOP return1; up to 5000 samples per camera',
                                'semantic':'native category IDs; visualization colors carry no learned predictions'},
            'limitations':['supplied camera projections; not independent rolling-shutter/moving-point reprojection','non-TOP explicitly uncompensated','no future-history or occupancy inference']}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS generated',len(records),'inspection frames',len(artifacts),'artifacts',flush=True)

if __name__=='__main__':main()
