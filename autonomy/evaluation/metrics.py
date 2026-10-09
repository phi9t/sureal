import importlib.util,json,subprocess,time
from pathlib import Path
from detection.detection_export import export_objects
from detection.native_detection_adapter import parse_result
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();out=Path('/outputs');records=json.loads(Path('/source/predictions.json').read_text());truth=json.loads(Path('/source/groundtruth.json').read_text());preparation=json.loads(Path('/source/preparation.json').read_text())
(out/'predictions.bin').write_bytes(export_objects(records));(out/'groundtruth.bin').write_bytes(export_objects(truth))
run=subprocess.run(['/metrics-build/compute_detection_metrics',str(out/'predictions.bin'),str(out/'groundtruth.bin')],capture_output=True,text=True,timeout=600)
(out/'metrics.stdout').write_text(run.stdout);(out/'metrics.stderr').write_text(run.stderr)
parsed=parse_result(run.returncode,run.stdout,run.stderr);metrics=parsed['metrics']
names={1:'VEHICLE',2:'PEDESTRIAN',3:'SIGN',4:'CYCLIST'};per_class={int(category):metrics[f'OBJECT_TYPE_TYPE_{names[int(category)]}_LEVEL_2'] for category,count in preparation['groundtruth_by_class'].items() if count>0}
if not per_class:raise ValueError('no populated detection classes')
mean=sum(x['APH'] for x in per_class.values())/len(per_class)
report={**preparation,'scope':'16-frame training-only overfit diagnostic; all eligible ROI-center GT retained including uncovered boxes; no heldout inference','LEVEL2_per_class':per_class,'mean_populated_class_APH':mean,'mean_scope':'populated classes','APH_gate_passed':mean>=.8,'metrics':metrics,'diagnostics':parsed['diagnostics'],'scoring_seconds':time.monotonic()-start}
(out/'check.json').write_text(json.dumps(report,indent=2)+'\n');print('TERMINAL native overfit scoring; APH',mean,'gate',mean>=.8,flush=True)
