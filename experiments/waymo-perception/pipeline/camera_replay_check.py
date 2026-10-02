"""Compare archive replay to separately mounted original sidecars and decode images."""
import argparse,hashlib,io,json
from pathlib import Path
import numpy as np
from PIL import Image
from .camera_dataset import iter_camera_records

def main():
 p=argparse.ArgumentParser();p.add_argument('--publication-sha',required=True);p.add_argument('--usage',required=True);args=p.parse_args()
 trusted=json.loads(Path('/mnt/reference.json').read_text());catalogs={};indexes={};counts={};dimensions={};digest=hashlib.sha256();eligible=0;mask_pixels=0
 for component,h in trusted.items():
  path=Path('/opt')/component/'manifest.json';data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=h:raise ValueError('independent reference manifest differs')
  catalogs[component]=json.loads(data);indexes[component]=0;counts[component]=0
 for record in iter_camera_records('/source/camera.tar','/source/publication.json',expected_publication_sha256=args.publication_sha,usage=args.usage):
  component=record['component'];native=catalogs[component];row=native['rows'][indexes[component]];indexes[component]+=1
  path=Path('/opt')/component/row['metadata'];data=path.read_bytes()
  if hashlib.sha256(data).hexdigest()!=row['metadata_sha256']:raise ValueError('independent native row changed')
  original=json.loads(data);fields=dict(original['fields'])
  for field,meta in original['binary_fields'].items():
   value=(Path('/opt')/component/meta['artifact']).read_bytes()
   if len(value)!=meta['size_bytes'] or hashlib.sha256(value).hexdigest()!=meta['sha256']:raise ValueError('independent original binary changed')
   fields[field]=value
  if record['identity']!=row['key'] or {k:v for k,v in fields.items() if k.startswith('key.')}!=record['identity']:raise ValueError('original camera keys differ')
  expected={k:v for k,v in fields.items() if not k.startswith('key.')};actual=record['observations'] if component=='camera_image' else record['targets']
  if actual!=expected or (record['targets'] if component=='camera_image' else record['observations']):raise ValueError('native fields or observation/target separation differs')
  digest.update(json.dumps({'component':component,'identity':record['identity']},sort_keys=True).encode())
  for k,v in sorted(actual.items()):
   digest.update(k.encode());digest.update(hashlib.sha256(v).digest() if isinstance(v,bytes) else json.dumps(v,sort_keys=True).encode())
  key=tuple(record['identity'][k] for k in ['key.segment_context_name','key.frame_timestamp_micros','key.camera_name'])
  if component=='camera_image':
   with Image.open(io.BytesIO(actual['[CameraImageComponent].image'])) as image:
    if image.format!='JPEG' or image.mode!='RGB':raise ValueError('native RGB JPEG expected')
    image.load();dimensions[key]=image.size
  elif component=='camera_segmentation':
   prefix='[CameraSegmentationLabelComponent].';divisor=actual[prefix+'panoptic_label_divisor']
   if type(divisor) is not int or divisor<=0 or key not in dimensions:raise ValueError('native camera mask support differs')
   with Image.open(io.BytesIO(actual[prefix+'panoptic_label'])) as image:
    if image.format!='PNG' or image.size!=dimensions[key]:raise ValueError('panoptic image dimensions differ')
    pan=np.asarray(image)
   if pan.ndim!=2 or not np.issubdtype(pan.dtype,np.integer):raise ValueError('panoptic raster type differs')
   semantic=pan//divisor
   if np.any(semantic<0) or np.any(semantic>28):raise ValueError('native camera semantic namespace differs')
   eligible+=int(np.count_nonzero(semantic));mask_pixels+=pan.size
   with Image.open(io.BytesIO(actual[prefix+'num_cameras_covered'])) as coverage:
    if coverage.format!='PNG' or coverage.size!=dimensions[key]:raise ValueError('camera overlap dimensions differ')
    coverage.load()
  counts[component]+=1
 if any(indexes[c]!=len(catalogs[c]['rows']) for c in catalogs):raise ValueError('incomplete camera replay')
 result={'status':'all native camera fields/bytes match independent references; JPEG/PNG support decoded','rows':counts,'identity_field_digest':digest.hexdigest(),'camera_mask_pixels':mask_pixels,'eligible_camera_mask_pixels':eligible,'scope':'native payload replay/geometry only; predicted task quality, semantic class mapping and global identity associations remain unevaluated'}
 Path('/outputs/replay.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS independent camera replay',counts)
if __name__=='__main__':main()
