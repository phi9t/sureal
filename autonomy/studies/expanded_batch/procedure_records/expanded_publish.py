"""Publish closed new-run cases in bounded HDFS chunks with live recovery proof."""
import argparse,fcntl,json,os,shutil,signal,subprocess,sys,uuid
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'tier1')]
from advanced.archive import sha,DEFAULT_LIMIT
from advanced.retention import release_plan
from tier1.admission import reserve_write
from tier1.storage import unique_payload_bytes
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing';CLI=Path.home()/'workspace/waystone/scripts/waystone'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True);parser.add_argument('--closure',type=Path,required=True);parser.add_argument('--case',required=True);parser.add_argument('--release',action='store_true');a=parser.parse_args()
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 results=json.loads(a.results.read_text());closure=json.loads(a.closure.read_text());assert closure['candidate_sha256']==sha(a.results);assert closure['validation']['all_cases_finished'];assert all(c['exit_code']==0 for c in closure['checks'])
 for path,digest in closure['artifacts'].items():assert sha(path)==digest
 case=results['cases'][a.case];assert case['status'] in ('sustained native overfit','failed to overfit by 10000 updates')
 payload=Path(case['output_directory']);assert payload.parent==W and payload.name.startswith(('tier1-overfit20261002b-','advanced-')) and not payload.is_symlink()
 # Tie current payload to the already closed producer/evaluator artifacts.
 admitted_files={};terminal_training=None
 for reference in case['verification_receipts']:
  assert sha(reference['receipt'])==reference['sha256'];evidence=json.loads(Path(reference['receipt']).read_text())
  admitted_files.update(evidence['artifacts']);admitted_files.update(evidence.get('transient_artifacts',{}))
  if evidence['name']==a.case+'-train-'+str(case['updates']):terminal_training=evidence['validation']
 training=json.loads((payload/'check.json').read_text())
 if terminal_training is None:
  assert a.case=='baseline' and 'adopted_baseline' in results
  assert sha(payload/'check.json')==results['adopted_baseline']['check_sha256']
  assert sha(payload/'checkpoint.pt')==results['adopted_baseline']['checkpoint_sha256']
 else:assert training==terminal_training
 assert sha(payload/'checkpoint.pt')==training['checkpoint_sha256']
 for file,digest in admitted_files.items():
  path=Path(file)
  if payload in path.parents and path.exists():assert sha(path)==digest,('post-closure payload mutation',path)
 native_files={str(p.relative_to(payload)):sha(p) for p in payload.rglob('*') if p.is_file()};assert native_files
 chunks=[];limit=max(64*1024**2,max((payload/name).stat().st_size for name in native_files));assert limit<=DEFAULT_LIMIT;current=[];size=0
 for name in sorted(native_files):
  length=(payload/name).stat().st_size
  if current and size+length>limit:chunks.append(current);current=[];size=0
  current.append(name);size+=length
 if current:chunks.append(current)
 identifier=payload.name+'-'+uuid.uuid4().hex;R=C/'insula'/('hdfs-retention-'+identifier);R.mkdir();source=R/'source';source.mkdir()
 for folder in ('advanced','pipeline'):shutil.copytree(P/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__'))
 pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};root=C/'insula/rootfs-v2';runtime=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,runtime['rootfs_sha256'])
 cli_pin=sha(CLI)
 waystone=CLI.parents[1];tool_pins={str(CLI):cli_pin}
 for relative in ['rust/target/debug/waystone','native/libhdfs_client/dist/lib/libhdfs_client.so','native/libhdfs_client/dist/bin/hdfs.bin']:
  tool_pins[str(waystone/relative)]=sha(waystone/relative)
 def external(arguments,label,timeout=300):
  assert all(sha(path)==digest for path,digest in tool_pins.items())
  command=[str(CLI),'--error-format','json','--command-timeout-secs',str(timeout),*(['--auth-source','token-file'] if arguments[0] in ['ls','put','get'] else []),*arguments]
  process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:stdout,stderr=process.communicate(timeout=timeout+5)
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGTERM)
   try:stdout,stderr=process.communicate(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
   (R/(label+'.log')).write_text(stdout+stderr);raise RuntimeError('bounded HDFS operation timed out: '+label)
  (R/(label+'.log')).write_text(stdout+stderr);assert process.returncode==0,label
  return stdout,{'stage':label,'command':command,'exit_code':0,'log_sha256':sha(R/(label+'.log'))}
 layout=json.loads(external(['layout-profile','--project','sureal','--json'],'layout',30)[0]);assert layout['project']=='sureal';remote=layout['paths']['runs'].rstrip('/')+'/perception-overfit/'+identifier
 external(['ls',layout['project_root']],'authenticated-read',30)
 temp=W/('hdfs-retention-'+identifier);temp.mkdir();publication={'closure_complete':True,'closure_receipt_sha256':sha(a.closure),'results_sha256':sha(a.results),'manifest_readback_exact':False,'source_pins':pins,'runtime_lock':runtime,'waystone_tool_sha256':tool_pins,'chunks':[]}
 def live(mode,inputdir,src,out,evidence):
  out.mkdir();command=launch_plan(root,source,src,out,['python','/experiment/advanced/archive_worker.py',mode]);index=command.index('--');command[index:index]=['--ro-bind',str(inputdir),'/tmp/inputs'];result=subprocess.run(command,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(result.stdout+result.stderr);assert result.returncode==0,str(out/'live.log');assert all(sha(path)==digest for path,digest in pins.items())
  evidence.mkdir();shutil.copy(out/'check.json',evidence/'check.json');shutil.copy(out/'live.log',evidence/'live.log')
  return {'stage':{'create':'create-live','verify':'verify-live','rehydrate':'rehydrate-live'}[mode],'command':command,'exit_code':0,'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in evidence.iterdir()}}
 for index,names in enumerate(chunks):
  total=sum((payload/name).stat().st_size for name in names);reserve_write(W,3*(total+len(names)*4096+10240)+2*1024**2)
  directory=temp/str(index);directory.mkdir();inputs=R/str(index)/'input';inputs.mkdir(parents=True);job={'source_sha256':{name:native_files[name] for name in names},'max_bytes':limit};(inputs/'job.json').write_text(json.dumps(job));checks=[live('create',inputs,payload,directory/'packed',R/str(index)/'create-proof')];manifest=json.loads((directory/'packed/manifest.json').read_text());digest=manifest['archive_sha256'];uri=remote+'/'+digest;download=directory/'download';download.mkdir()
  checks.append(external(['put','--mkdir-parents',str(directory/'packed/archive.tar.gz'),uri+'/archive.tar.gz'],f'{index}-archive-put')[1]);checks[-1]['stage']='archive-put'
  checks.append(external(['get',uri+'/archive.tar.gz',str(download/'archive.tar.gz')],f'{index}-archive-get')[1]);checks[-1]['stage']='archive-get'
  checks.append(external(['put','--mkdir-parents',str(directory/'packed/manifest.json'),uri+'/manifest.json'],f'{index}-manifest-put')[1]);checks[-1]['stage']='manifest-put'
  checks.append(external(['get',uri+'/manifest.json',str(download/'manifest.json')],f'{index}-manifest-get')[1]);checks[-1]['stage']='manifest-get'
  job['manifest_sha256']=sha(directory/'packed/manifest.json');(inputs/'job.json').write_text(json.dumps(job));checks.append(live('verify',inputs,download,directory/'verify',R/str(index)/'verify-proof'));checks.append(live('rehydrate',inputs,download,directory/'rehydrate',R/str(index)/'rehydrate-proof'))
  chunk={'archive_hdfs_uri':uri+'/archive.tar.gz','manifest_hdfs_uri':uri+'/manifest.json','manifest_sha256':job['manifest_sha256'],'manifest':manifest,'checks':checks};publication['chunks'].append(chunk);(R/'in-progress.json').write_text(json.dumps(publication,indent=2));print('ADMITTED HDFS archive and live recovery',a.case,index,flush=True)
  # Only this new verified temporary archive/download/recovery tree is released.
  release={str(p):sha(p) for p in directory.rglob('*') if p.is_file()};(R/str(index)/'temporary-release.json').write_text(json.dumps(release,indent=2));shutil.rmtree(directory)
 manifestpath=R/'publication-manifest.json';manifestpath.write_text(json.dumps(publication,indent=2));external(['put','--mkdir-parents',str(manifestpath),remote+'/publication-manifest.json'],'publication-manifest-put');readback=R/'publication-manifest-readback.json';external(['get',remote+'/publication-manifest.json',str(readback)],'publication-manifest-get');assert sha(readback)==sha(manifestpath);publication['manifest_readback_exact']=True;publication['publication_manifest_hdfs_uri']=remote+'/publication-manifest.json';publication['publication_manifest_sha256']=sha(manifestpath)
 plan=release_plan(payload,publication);publication['release_plan']=plan;receipt=R/'verified-publication.json';receipt.write_text(json.dumps(publication,indent=2))
 if a.release:
  for entry in plan:assert sha(entry['local_path'])==entry['sha256'];Path(entry['local_path']).unlink()
  (R/'release-completed.json').write_text(json.dumps({'publication_receipt_sha256':sha(receipt),'released':plan},indent=2))
 assert unique_payload_bytes(W)<=15*1024**3
 print('ADMITTED HDFS retention',receipt,'local release',a.release,flush=True)
if __name__=='__main__':main()
