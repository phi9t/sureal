import pathlib,json,csv,copy,time,resource
from motion.ingestion.strict_metric_reader import parse_result
start=time.monotonic();mapping={1:'TYPE_VEHICLE',2:'TYPE_PEDESTRIAN',3:'TYPE_CYCLIST'}
def verify(score,expected):
 parsed=parse_result(score);classes=parsed['classes'];rows=[]
 expected_kinds=set()
 for r in expected:
  kind=int(r['object_type']);assert kind in mapping;expected_kinds.add(kind)
  if kind not in classes:raise ValueError('extra native class')
  metrics=classes[kind];count=metrics['counts'];ade=int(r['ade_count']);fde=int(r['fde_count'])
  if count['min_ade']!=ade or count['min_fde']!=fde:raise ValueError('count/horizon mismatch')
  for key,value,number in [('minAde',float(r['ade']),ade),('minFde',float(r['fde']),fde)]:
   if number and abs(metrics[key]-value)>1e-3:raise ValueError('literal displacement mismatch')
  rows.append({'object_type':kind,'ADE_measurements':ade,'FDE_measurements':fde,'missing_endpoint_measurements':ade-fde,'minADE':metrics['minAde'],'minFDE':metrics['minFde']})
 if set(classes)!=expected_kinds:raise ValueError('extra native class')
 return rows
reports=[];refusals=0
for split in ['training','validation']:
 for offset in [0,2]:
  expected=list(csv.DictReader((pathlib.Path('/source')/split/f'expected-{offset}.tsv').open(),delimiter='\t'));score=json.loads((pathlib.Path('/source')/split/f'score-{offset}.json').read_text());reports.append({'split':split,'oracle_offset_meters':offset,'classes':verify(score,expected)})
  for kind in ['count','displacement']:
   bad=copy.deepcopy(score)
   if kind=='count':bad['counts'][0]['min_fde']+=1
   else:bad['metrics']['metricsBundles'][0]['minAde']=100
   try:verify(bad,expected)
   except ValueError:refusals+=1
   else:raise AssertionError('corrupt scorer output accepted')
assert refusals==8
pathlib.Path('/outputs/check.json').write_text(json.dumps({'comparisons':reports,'count_or_displacement_corruptions_refused':refusals,'float_displacement_tolerance_meters':1e-3,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'oracle native metric handoff parity only; missing futures are not perfect predictions; no forecasting quality'},indent=2));print('VERIFIED four native oracle comparisons and eight refusals')
