"""Independently reconcile saved views, point samples and native image bytes."""
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from evidence.source_snapshot import file_sha256
from dataset.sensor_records import select_rows


def validate(source,geometry,out):
    report=json.loads((out/'report.json').read_text());dataset=json.loads((source/'slice.json').read_text())
    if file_sha256(geometry/'report.json')!=report['geometry_report_sha256']:raise ValueError('geometry report changed')
    for name,digest in report['artifacts'].items():
        if file_sha256(out/name)!=digest:raise ValueError('view artifact changed')
    if len(report['frames'])!=4:raise ValueError('frame coverage')
    actual={};camera_semantics={}
    for context in dataset['contexts']:
        stamps={f['timestamp'] for f in report['frames'] if f['context']==context}
        path=source/next(e['relative_path'] for e in dataset['objects'] if e['context']==context and e['component']=='camera_image')
        for row in select_rows(path,timestamps=stamps):
            actual[(context,row['key.frame_timestamp_micros'],row['key.camera_name'])]=row['[CameraImageComponent].image']
        segpath=source/next(e['relative_path'] for e in dataset['objects'] if e['context']==context and e['component']=='camera_segmentation')
        for row in select_rows(segpath,timestamps=stamps):
            import io
            prefix='[CameraSegmentationLabelComponent]'
            camera_semantics[(context,row['key.frame_timestamp_micros'],row['key.camera_name'])]=np.asarray(Image.open(io.BytesIO(row[prefix+'.panoptic_label'])))//row[prefix+'.panoptic_label_divisor']
    for frame in report['frames']:
        folder=out/frame['directory'];xyz=[]
        if len(frame['sensors'])!=10 or {r['camera'] for r in frame['cameras']}!={1,2,3,4,5}:raise ValueError('sensor coverage')
        for sensor in frame['sensors']:
            path=geometry/sensor['geometry_artifact']
            if file_sha256(path)!=sensor['geometry_sha256']:raise ValueError('source geometry changed')
            with np.load(path) as a:
                xyz.append(a['xyz'])
                if len(a['pixels'])!=sensor['points']:raise ValueError('sensor support count')
                with Image.open(folder/f'range-{sensor["laser"]}-{sensor["return"]}.png') as image:
                    rgb=np.asarray(image);y,x=a['pixels'].T
                    expected=np.clip(a['physical_features'][:,0]*2,0,255).astype(np.uint8)
                    if not np.array_equal(rgb[y,x],np.repeat(expected[:,None],3,axis=1)):raise ValueError('range display values')
                    unknown=np.all(rgb==[60,0,60],axis=-1)
                    if int(unknown.sum())!=sensor['unknown_pixels']:raise ValueError('unknown range display coverage')
        xyz=np.concatenate(xyz);mask=((xyz[:,:2]>=-75)&(xyz[:,:2]<75)).all(axis=1)
        histogram,_,_=np.histogram2d(xyz[mask,0],xyz[mask,1],bins=[np.linspace(-75,75,301),np.linspace(-75,75,301)])
        density=np.load(folder/'bev-density.npy')
        if not np.array_equal(density,histogram.T[::-1]):raise ValueError('BEV mapping')
        if int(mask.sum())!=frame['bev']['retained'] or int((~mask).sum())!=frame['bev']['clipped']:raise ValueError('BEV coverage')
        top=next(r for r in frame['sensors'] if r['laser']==1 and r['return']==1)
        with np.load(geometry/top['geometry_artifact']) as a:
            semantic_path=folder/'top-semantic.npy'
            if ('segmentation' in a)!=semantic_path.exists():raise ValueError('TOP semantic coverage')
            if semantic_path.exists():
                semantic=np.load(semantic_path);y,x=a['pixels'].T
                if not np.array_equal(semantic[y,x],a['segmentation'][:,1]):raise ValueError('TOP semantic display labels')
                known=np.zeros(semantic.shape,dtype=bool);known[y,x]=True
                if not np.all(semantic[~known]==-1):raise ValueError('unknown semantic pixels')
            for camera in frame['cameras']:
                name=camera['camera'];raw=actual[(frame['context'],frame['timestamp'],name)]
                if (folder/f'camera-{name}.jpg').read_bytes()!=raw:raise ValueError('native camera changed')
                semkey=(frame['context'],frame['timestamp'],name)
                sempath=folder/f'camera-{name}-semantic.npy'
                if (semkey in camera_semantics)!=sempath.exists():raise ValueError('camera semantic coverage')
                if sempath.exists() and not np.array_equal(np.load(sempath),camera_semantics[semkey]):raise ValueError('camera semantic labels changed')
                with np.load(folder/f'camera-{name}-samples.npz') as samples:
                    indexes,slots=samples['point_indexes'],samples['slots'];uv=samples['uv']
                    if not np.isfinite(uv).all() or not np.array_equal(uv,np.round(uv)):raise ValueError('noninteger native projection pixels')
                    uv=uv.astype(np.int64)
                    if not np.array_equal(samples['pixels'],a['pixels'][indexes]):raise ValueError('overlay pixel identity')
                    cp=a['camera_projection'].reshape(-1,2,3)[indexes,slots]
                    if not np.all(cp[:,0]==name) or not np.array_equal(cp[:,1:],uv):raise ValueError('overlay correspondence')
                    if not np.all((uv>=0)&(uv<[camera['width'],camera['height']])):raise ValueError('overlay image bounds')
                    with Image.open(folder/f'camera-{name}-overlay.png') as img:
                        if img.size!=(camera['width'],camera['height']):raise ValueError('resized overlay')
                        values=np.asarray(img)
                        if not np.all(values[uv[:,1],uv[:,0]]==[0,255,160]):raise ValueError('overlay rendered coordinate mismatch')
    if not any(f['top_segmentation_present'] for f in report['frames']) or not any(not f['top_segmentation_present'] for f in report['frames']):raise ValueError('supervision coverage')
    return {'passed':True,'frames':4,'camera_views':20,'sensor_return_views':40,'artifacts':len(report['artifacts'])}

if __name__=='__main__':print(json.dumps(validate(*map(Path,sys.argv[1:4]))))
