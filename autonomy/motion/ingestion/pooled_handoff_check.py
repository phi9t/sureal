import pathlib,json,csv,copy,time,resource,math
from motion.ingestion.strict_metric_reader import parse_result
start=time.monotonic();mapping={1:'TYPE_VEHICLE',2:'TYPE_PEDESTRIAN',3:'TYPE_CYCLIST'}
def aggregate(rows):
 result={}
 for scenario in rows:
  for r in scenario:
   kind=int(r['object_type']);entry=result.setdefault(kind,{'ade_count':0,'fde_count':0,'ade_sum':0.,'fde_sum':0.});a,b=int(r['ade_count']),int(r['fde_count']);entry['ade_count']+=a;entry['fde_count']+=b;entry['ade_sum']+=float(r['ade'])*a;entry['fde_sum']+=float(r['fde'])*b
 return result

def verify(score,reference):
 if score['scenarios']!=2:raise ValueError('scenario count')
 classes=parse_result(score)['classes']
 if set(classes)!=set(reference):raise ValueError('class identity/duplicate')
 result=[]
 for kind,expect in reference.items():
  metrics=classes[kind];count=metrics['counts']
  for metric in ['ade','fde']:
   n=expect[metric+'_count'];value=expect[metric+'_sum']/max(n,1);key='minAde' if metric=='ade' else 'minFde'
   observed=metrics[key]
   if not math.isfinite(value):raise ValueError('nonfinite pooled displacement')
   if count['min_'+metric]!=n or abs(observed-value)>1e-3:raise ValueError('pooled support or displacement')
  result.append({'object_type':kind,'ADE_measurements':expect['ade_count'],'FDE_measurements':expect['fde_count'],'missing_endpoint_measurements':expect['ade_count']-expect['fde_count'],'minADE':metrics['minAde'],'minFDE':metrics['minFde']})
 return result
rows=[];refused=0
for train,val in [(0,0),(0,2),(2,0),(2,2)]:
 refs=[list(csv.DictReader((pathlib.Path('/source')/f'{split}-expected-{offset}.tsv').open(),delimiter='\t')) for split,offset in [('training',train),('validation',val)]];expected=aggregate(refs);score=json.loads((pathlib.Path('/source')/f'pooled-{train}-{val}.json').read_text());rows.append({'training_oracle_offset_m':train,'validation_oracle_offset_m':val,'classes':verify(score,expected)})
 for fault in ['scenario_count','count','displacement','class','duplicate','nonfinite_ade','nonfinite_fde']:
  bad=copy.deepcopy(score)
  if fault=='scenario_count':bad['scenarios']=1
  elif fault=='count':bad['counts'][0]['min_fde']+=1
  elif fault=='displacement':bad['metrics']['metricsBundles'][0]['minAde']=100
  elif fault=='class':bad['counts'][0]['object_type']=3
  elif fault=='duplicate':bad['counts'].append(copy.deepcopy(bad['counts'][0]))
  elif fault=='nonfinite_ade':bad['metrics']['metricsBundles'][0]['minAde']='NaN'
  else:bad['metrics']['metricsBundles'][0]['minFde']=float('nan')
  try:verify(bad,expected)
  except ValueError:refused+=1
  else:raise AssertionError('corrupt pooled score accepted')
assert refused==28
assert any(abs(r['classes'][0]['minADE']-r['classes'][0]['minFDE'])>.01 for r in rows)
pathlib.Path('/outputs/check.json').write_text(json.dumps({'controls':rows,'corrupt_score_refusals':refused,'displacement_tolerance_m':1e-3,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'two acquired native scenarios pooled solely as oracle scorer diagnostic; training and validation never mixed for scientific model evaluation'},indent=2));print('PASS four native pooled controls and28 corrupt score refusals')
