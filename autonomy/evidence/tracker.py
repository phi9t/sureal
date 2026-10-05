"""Evidence-derived experiment dashboard and append-only research journal CLI."""
import argparse,datetime,fcntl,hashlib,json,os,time
from pathlib import Path
from evidence.journal import append_entry,read_entries
from evidence.projection import project_experiments
from evidence.source_snapshot import file_sha256 as digest,require_regular_file
P=Path(__file__).resolve().parents[1]
R=P/'research';REGISTRY=R/'experiment-registry.json';JOURNAL=R/'research-journal.jsonl'
def atomic(path,value):
 temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(value);os.replace(temporary,path)
def read_optional(path):
 if not path.exists():return None,None
 raw=path.read_bytes();return json.loads(raw),hashlib.sha256(raw).hexdigest()
def snapshot(path):
 path=require_regular_file(path);data=path.read_bytes();h=digest(path);destination=R/'journal-evidence'/h;destination.parent.mkdir(exist_ok=True)
 if not destination.exists():
  with destination.open('xb') as output:output.write(data)
 if digest(destination)!=h:raise ValueError('immutable journal evidence changed')
 return destination

def refresh():
 with (R/'experiment-tracker.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);registry=json.loads(REGISTRY.read_text());rows=[];sources={};old,_=read_optional(R/'experiments.json');previous={row['id']:row['stage'] for row in (old or {}).get('experiments',[])}
  for run in registry['runs']:
   resultpath=P/run['results'];closurepath=P/run['closure'];admissionpath=P/run['admission'] if run.get('admission') else None
   result,h=read_optional(resultpath);closure,_=read_optional(closurepath);admission,_=read_optional(admissionpath) if admissionpath else (None,None)
   if result:
    metadata_path=Path(result['run_directory'])/'run.json';metadata,metadata_hash=read_optional(metadata_path)
    if metadata is None or metadata_hash!=result['metadata_sha256']:raise ValueError('immutable run metadata differs')
    result['_run_metadata']=metadata
   if closure:
    if not closure.get('checks') or any(digest(path)!=value for path,value in closure['artifacts'].items()):raise ValueError('live closure artifacts differ')
   projected=project_experiments(run['id'],run['recipes'],result,h,closure,admission)
   for row in projected:
    row['goal']=run.get('goals',{}).get(row['name'],row['goal']);row['result_path']=str(resultpath);row['closure_path']=str(closurepath) if closure else None
    row['results_hdfs_receipt']=str(P/run['hdfs_results']) if run.get('hdfs_results') and (P/run['hdfs_results']).exists() else None
    if previous.get(row['id'])!=row['stage'] and row['stage'] in ['verified_overfit','verified_censored','verified_equivalence_control','gpu_admitted','execution_failed']:
     evidence=[snapshot(path) for path in [resultpath,closurepath,admissionpath] if path and path.exists()]
     append_entry(JOURNAL,'observation',[row['id']],f"Evidence-derived stage: {row['stage']}. Updates: {row['updates']}; worst terminal native APH: {row['worst_terminal_APH']}. This is a fixed-batch training diagnostic.",evidence)
   rows+=projected;sources[run['id']]={'result_sha256':h,'result_path':str(resultpath)}
  payload={'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'fixed all-class training batch; no heldout, segmentation or full-dataset completion claim','experiments':rows,'sources':sources};atomic(R/'experiments.json',json.dumps(payload,indent=2)+'\n')
  lines=['# Experiment tracker','',payload['scope'],'','| Experiment | Stage | Confirmation update | Train seconds to confirmation | Worst terminal APH |','|---|---|---:|---:|---:|']
  for row in rows:
   fit=row['time_to_fit'] or {};seconds=fit.get('confirmation_train_seconds');aph=row['worst_terminal_APH'];lines.append(f"| {row['id']} | {row['stage']} | {row['confirmation_update'] or '—'} | {f'{seconds:.1f}' if seconds is not None else '—'} | {f'{aph:.3f}' if aph is not None else '—'} |")
  lines+=['','Each row’s goal, complete recipe, verifier contract and acceptance criteria are in [experiments.json](experiments.json). Definitions are in [experiment-registry.json](experiment-registry.json). Notes are in [research-journal.md](research-journal.md).','','Refresh: `python autonomy/evidence/tracker.py refresh`','Follow active runs: `python autonomy/evidence/tracker.py watch`'];atomic(R/'experiment-tracker.md','\n'.join(lines)+'\n')
  entries=read_entries(JOURNAL);notes=['# Research journal','','Append-only observations, hypotheses, decisions and follow-up work. Evidence snapshots and entry hash chains preserve what was known at the time.']
  for entry in entries:
   notes+=['',f"## {entry['sequence']}. {entry['utc']} — {entry['category']}",'',', '.join(entry['experiments']),'',entry['content']]
   if entry['evidence']:notes+=['','Evidence: '+', '.join(f"[{Path(e['path']).name[:12]}]({e['path']})" for e in entry['evidence'])]
  atomic(R/'research-journal.md','\n'.join(notes)+'\n');print('TRACKED',len(rows),'experiments;',len(entries),'journal entries',flush=True)

def main():
 parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True);commands.add_parser('refresh');watch=commands.add_parser('watch');watch.add_argument('--interval',type=int,default=60);note=commands.add_parser('note');note.add_argument('--category',choices=['observation','hypothesis','decision','follow_up'],required=True);note.add_argument('--experiment',action='append',required=True);note.add_argument('--text',required=True);note.add_argument('--evidence',type=Path,action='append',default=[]);commands.add_parser('verify-journal');args=parser.parse_args()
 if args.command=='note':append_entry(JOURNAL,args.category,args.experiment,args.text,args.evidence);refresh()
 elif args.command=='verify-journal':print('VERIFIED journal entries',len(read_entries(JOURNAL)))
 elif args.command=='watch':
  if args.interval<10:raise ValueError('poll at least10 seconds apart')
  while True:
   try:refresh()
   except (json.JSONDecodeError,FileNotFoundError):print('Result write in progress; retaining prior dashboard and retrying',flush=True)
   time.sleep(args.interval)
 else:refresh()
if __name__=='__main__':main()
