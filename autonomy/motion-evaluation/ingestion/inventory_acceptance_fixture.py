"""Independent aggregate reconciliation of native pilot source inventories."""
import copy,csv,hashlib,io,json,resource,time
from pathlib import Path

def validate(d):
 inventory=d['inventory'];assert inventory['release']=='v1.2.1'
 assert inventory['bucket']=='waymo_open_dataset_motion_v_1_2_1'
 report={}
 for split,count,records in [('training',1000,492),('validation',150,287)]:
  observed=inventory['splits'][split];objects=observed['objects'];assert len(objects)==observed['object_count']==count
  assert len({x['name'] for x in objects})==count
  assert sum(int(x['size']) for x in objects)==observed['total_bytes']
  assert all(x['bucket']==inventory['bucket'] and x['name'].startswith(observed['prefix']) and int(x['size'])>0 and int(x['generation'])>0 and x['crc32c'] and x['md5Hash'] for x in objects)
  assert all(x['http_status']==200 for x in observed['pages']) and not observed['pages'][-1]['next_page']
  pilot=d[split];source=pilot['source']['source'];assert source==min(objects,key=lambda x:x['name'])
  assert pilot['source']['hdfs_readback_exact'] is True
  frames=pilot['frames'];native=pilot['native'];assert len(frames)==len(native)==records
  assert len({x['scenario_id'] for x in native})==records
  offset=0
  for i,(frame,row) in enumerate(zip(frames,native)):
   assert frame['index']==int(row['index'])==i
   assert frame['offset']==int(row['offset'])==offset
   assert frame['payload_bytes']==int(row['payload_bytes'])>0
   assert len(frame['sha256'])==64
   offset+=frame['payload_bytes']+16
  assert offset==int(source['size'])
  selected=min(native,key=lambda x:x['scenario_id']);i=int(selected['index']);rec=pilot['reconciliation']
  assert selected==rec['selected'] and rec['records']==records and rec['source_bytes']==offset
  assert int(selected['current_index'])==10 and int(selected['timestamps'])==91
  assert int(selected['targets'])==({'training':2,'validation':8}[split])
  assert frames[i]['sha256']==pilot['selected_sha256']==rec['selected_payload_sha256']
  assert pilot['source']['inventory_sha256']==d['inventory_sha256']
  report[split]={'objects':count,'records_reconciled':records,'source_bytes':offset,'native_selected':selected,'selected_payload_sha256':pilot['selected_sha256']}
 return report

if __name__=='__main__':
 start=time.monotonic();d=json.loads(Path('/source/input.json').read_text());report=validate(d)
 refused=0
 for mutation in range(5):
  bad=copy.deepcopy(d)
  if mutation==0:bad['training']['frames'][1]['offset']+=1
  elif mutation==1:bad['validation']['native'][0]['payload_bytes']='1'
  elif mutation==2:bad['training']['selected_sha256']='0'*64
  elif mutation==3:bad['inventory']['splits']['validation']['pages'][-1]['next_page']=True
  else:bad['training']['reconciliation']['selected']['scenario_id']='wrong'
  try:validate(bad)
  except AssertionError:refused+=1
  else:raise AssertionError('corrupt inventory admitted')
 result={'splits':report,'corrupt_inventory_copies_refused':refused,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'live aggregate of complete authenticated metadata and two independently produced full source record inventories; not a fresh raw-shard CRC/protobuf replay, scientific cohort, or full ticket19 closeout'}
 Path('/outputs/check.json').write_text(json.dumps(result,indent=2));print('PASS 1150 objects /',sum(x['records_reconciled'] for x in report.values()),'paired records /',refused,'corruption refusals')
