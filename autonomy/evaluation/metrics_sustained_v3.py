from resources.sustained_scoring_budget import DEFAULT_NATIVE_SECONDS
import importlib.util,json,subprocess,time
from pathlib import Path
from detection.detection_export import export_objects
from detection.native_detection_adapter import parse_result
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();out=Path('/outputs');records=json.loads(Path('/source/predictions.json').read_text());truth=json.loads(Path('/source/groundtruth.json').read_text());preparation=json.loads(Path('/source/preparation.json').read_text())
if preparation.get('decoder_version')!=3 or preparation.get('groundtruth_policy')!='all native four-class boxes; native evaluator handles eligibility' or len(preparation['frames'])!=16 or len(truth)!=preparation['native_groundtruth']:raise ValueError('full16 native GT V3 preparation required')
(out/'predictions.bin').write_bytes(export_objects(records));(out/'groundtruth.bin').write_bytes(export_objects(truth))
run=subprocess.run(['/metrics-build/compute_detection_metrics',str(out/'predictions.bin'),str(out/'groundtruth.bin')],capture_output=True,text=True,timeout=DEFAULT_NATIVE_SECONDS)
(out/'metrics.stdout').write_text(run.stdout);(out/'metrics.stderr').write_text(run.stderr)
parsed=parse_result(run.returncode,run.stdout,run.stderr);metrics=parsed['metrics']
names={1:'VEHICLE',2:'PEDESTRIAN',3:'SIGN',4:'CYCLIST'};per_class={int(category):metrics[f'OBJECT_TYPE_TYPE_{names[int(category)]}_LEVEL_2'] for category,count in preparation['groundtruth_by_class'].items() if count>0}
if set(per_class)!={1,2,3,4}:raise ValueError('finite complete native four-class scores required')
mean=sum(x['APH'] for x in per_class.values())/len(per_class)
passed=all(x['APH']>=.8 for x in per_class.values())
report={**preparation,'scope':'16-frame training-only full native GT V3 diagnostic; native eligibility handled by official evaluator; no heldout inference','LEVEL2_per_class':per_class,'mean_populated_class_APH':mean,'APH_gate_passed':passed,'all_class_APH_gate_passed':passed,'checkpoint_confirmation_required':True,'metrics':metrics,'diagnostics':parsed['diagnostics'],'scoring_seconds':time.monotonic()-start}
(out/'check.json').write_text(json.dumps(report,indent=2)+'\n');print('TERMINAL native overfit scoring; APH',mean,'all-class gate',passed,flush=True)
