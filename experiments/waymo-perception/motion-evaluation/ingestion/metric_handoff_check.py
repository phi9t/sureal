import pathlib,json,csv,copy,time,resource
start=time.monotonic();mapping={1:'TYPE_VEHICLE',2:'TYPE_PEDESTRIAN',3:'TYPE_CYCLIST'}
def verify(score,expected):
 bundles={x['objectFilter']:x for x in score['metrics']['metricsBundles']};counts={x['object_type']:x for x in score['counts']};rows=[]
 for r in expected:
  kind=int(r['object_type']);assert kind in mapping;bundle=bundles[mapping[kind]];count=counts[kind];ade=int(r['ade_count']);fde=int(r['fde_count'])
  if int(bundle['measurementStep'])!=15 or count['measurement_step']!=15 or count['min_ade']!=ade or count['min_fde']!=fde:raise ValueError('count/horizon mismatch')
  for key,value,number in [('minAde',float(r['ade']),ade),('minFde',float(r['fde']),fde)]:
   if number and abs(float(bundle.get(key,0))-value)>1e-3:raise ValueError('literal displacement mismatch')
  rows.append({'object_type':kind,'ADE_measurements':ade,'FDE_measurements':fde,'missing_endpoint_measurements':ade-fde,'minADE':float(bundle.get('minAde',0)),'minFDE':float(bundle.get('minFde',0))})
 if set(counts)!=set(int(r['object_type']) for r in expected):raise ValueError('extra native class')
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
