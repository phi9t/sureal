import importlib.util,json,math,re,subprocess,time
from pathlib import Path
from pipeline.detection_export import export_objects
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();out=Path('/outputs');records=json.loads(Path('/source/predictions.json').read_text());truth=json.loads(Path('/source/groundtruth.json').read_text());preparation=json.loads(Path('/source/preparation.json').read_text())
if preparation.get('decoder_version')!=3 or preparation.get('groundtruth_policy')!='all native four-class boxes; native evaluator handles eligibility' or len(preparation['frames'])!=16 or len(truth)!=preparation['native_groundtruth']:raise ValueError('full16 native GT V3 preparation required')
(out/'predictions.bin').write_bytes(export_objects(records));(out/'groundtruth.bin').write_bytes(export_objects(truth))
run=subprocess.run(['/metrics-build/compute_detection_metrics',str(out/'predictions.bin'),str(out/'groundtruth.bin')],capture_output=True,text=True,timeout=600)
(out/'metrics.stdout').write_text(run.stdout);(out/'metrics.stderr').write_text(run.stderr);assert run.returncode==0
metrics={name:{'AP':float(ap),'APH':float(aph)} for name,ap,aph in re.findall(r'(\S+): \[mAP ([^\]]+)\] \[mAPH ([^\]]+)\]',run.stdout)}
names={1:'VEHICLE',2:'PEDESTRIAN',3:'SIGN',4:'CYCLIST'};per_class={int(category):metrics[f'OBJECT_TYPE_TYPE_{names[int(category)]}_LEVEL_2'] for category,count in preparation['groundtruth_by_class'].items() if count>0}
if set(per_class)!={1,2,3,4} or any(not math.isfinite(value) or not 0<=value<=1 for metrics_class in per_class.values() for value in metrics_class.values()):raise ValueError('finite complete native four-class scores required')
mean=sum(x['APH'] for x in per_class.values())/len(per_class)
passed=all(x['APH']>=.8 for x in per_class.values())
report={**preparation,'scope':'16-frame training-only full native GT V3 diagnostic; native eligibility handled by official evaluator; no heldout inference','LEVEL2_per_class':per_class,'mean_populated_class_APH':mean,'APH_gate_passed':passed,'all_class_APH_gate_passed':passed,'checkpoint_confirmation_required':True,'metrics':metrics,'scoring_seconds':time.monotonic()-start}
(out/'check.json').write_text(json.dumps(report,indent=2)+'\n');print('TERMINAL native overfit scoring; APH',mean,'all-class gate',passed,flush=True)
