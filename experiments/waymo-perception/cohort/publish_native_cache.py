"""Retain the independently admitted native input cache; model cases stay intact."""
import argparse,fcntl,json,os,shutil,signal,subprocess,sys,uuid
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P),str(P/'tier1')]
from advanced.archive import sha,DEFAULT_LIMIT
from advanced.retention import release_plan
from tier1.admission import reserve_write
from tier1.storage import unique_payload_bytes
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
C=Path.home()/'.cache/waystone/waymo-perception';W=C/'scientific-processing';CLI=Path.home()/'workspace/waystone/scripts/waystone'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');a=parser.parse_args();a.case='overfit-native-cache-v1'
 lock=(C/'insula/architecture-experiments.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 from cohort.cache_inventory import freeze_cache_inventory
 from cohort.retention_sources import freeze_host_sources,validate_host_sources
 payload=W/a.case
 admissions=sorted((P/'research').glob('overfit-native-cache-*-verified.json'))
 admissions=[p for p in admissions if 'receipt' in json.loads(p.read_text()) and Path(json.loads(p.read_text())['receipt']).is_relative_to(payload)]
 assert len(admissions)==16
 for path in admissions:
  admitted=json.loads(path.read_text());assert all(c['exit_code']==0 for c in admitted['checks'])
  for file,digest in admitted['artifacts'].items():assert sha(file)==digest
 inventory=freeze_cache_inventory(payload,admissions)
 native_files={str(p.relative_to(payload)):sha(p) for p in payload.rglob('*') if p.is_file()};assert native_files
 chunks=[];limit=max(64*1024**2,max((payload/name).stat().st_size for name in native_files));assert limit<=DEFAULT_LIMIT;current=[];size=0
 for name in sorted(native_files):
  length=(payload/name).stat().st_size
  if current and size+length>limit:chunks.append(current);current=[];size=0
  current.append(name);size+=length
 if current:chunks.append(current)
 identifier=payload.name+'-'+uuid.uuid4().hex;R=C/'insula'/('hdfs-retention-'+identifier);R.mkdir();host_pins=freeze_host_sources(P,R/'host-source');source=R/'source';source.mkdir()
 for folder in ('advanced','pipeline'):shutil.copytree(P/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__'))
 pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};root=C/'insula/rootfs-v2';runtime=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,runtime['rootfs_sha256'])
 cli_pin=sha(CLI)
 waystone=CLI.parents[1];tool_pins={str(CLI):cli_pin}
 for relative in ['rust/target/debug/waystone','native/libhdfs_client/dist/lib/libhdfs_client.so','native/libhdfs_client/dist/bin/hdfs.bin']:
  tool_pins[str(waystone/relative)]=sha(waystone/relative)
 def external(arguments,label,timeout=300):
  validate_host_sources(P,host_pins);assert all(sha(path)==digest for path,digest in tool_pins.items())
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
 layout=json.loads(external(['layout-profile','--project','sureal','--json'],'layout',30)[0]);assert layout['project']=='sureal';remote=layout['paths']['runs'].rstrip('/')+'/perception-native-cache/'+identifier
 external(['ls',layout['project_root']],'authenticated-read',30)
 temp=W/('hdfs-retention-'+identifier);temp.mkdir();(R/'expected.json').write_text(json.dumps(inventory,indent=2));publication={'closure_complete':True,'source_admission_complete':True,'host_source_pins':host_pins,'source_sha256':inventory['source_sha256'],'parent_receipts':inventory['parent_receipts'],'cache_inventory_sha256':sha(R/'expected.json'),'manifest_readback_exact':False,'source_pins':pins,'runtime_lock':runtime,'waystone_tool_sha256':tool_pins,'chunks':[]}
 def live(mode,inputdir,src,out,evidence):
  validate_host_sources(P,host_pins);out.mkdir();command=launch_plan(root,source,src,out,['python','/experiment/advanced/archive_worker.py',mode]);index=command.index('--');command[index:index]=['--ro-bind',str(inputdir),'/tmp/inputs'];result=subprocess.run(command,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(result.stdout+result.stderr);assert result.returncode==0,str(out/'live.log');assert all(sha(path)==digest for path,digest in pins.items())
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
 assert freeze_cache_inventory(payload,admissions)==inventory
 plan=release_plan(payload,publication);publication['release_plan']=plan;receipt=R/'verified-publication.json';receipt.write_text(json.dumps(publication,indent=2))
 # A separate independent full-inventory live gate is mandatory before release.
 independent=R/'independent';independent.mkdir();proof_inputs=R/'admission-input';proof_inputs.mkdir();(proof_inputs/'publication.json').write_text(json.dumps(publication));shutil.copyfile(readback,proof_inputs/'readback.json');shutil.copyfile(R/'expected.json',proof_inputs/'expected.json');shutil.copyfile(Path(host_pins['cohort/cache_retention_audit.py']['snapshot']),source/'cache_retention_audit.py')
 command=launch_plan(root,source,payload,independent,['python','/experiment/cache_retention_audit.py']);at=command.index('--');command[at:at]=['--ro-bind',str(proof_inputs),'/tmp/inputs'];audit=subprocess.run(command,capture_output=True,text=True,timeout=300);(independent/'live.log').write_text(audit.stdout+audit.stderr);assert audit.returncode==0,str(independent/'live.log');publication['independent_admission']={'command':command,'exit_code':0,'source_sha256':sha(source/'cache_retention_audit.py'),'inputs':{str(p):sha(p) for p in proof_inputs.iterdir()},'artifacts':{str(p):sha(p) for p in independent.iterdir()},'validation':json.loads((independent/'check.json').read_text())};receipt.write_text(json.dumps(publication,indent=2))
 if a.release:
  validate_host_sources(P,host_pins)
  for entry in plan:assert sha(entry['local_path'])==entry['sha256'];Path(entry['local_path']).unlink()
  (R/'release-completed.json').write_text(json.dumps({'publication_receipt_sha256':sha(receipt),'released':plan},indent=2))
 assert unique_payload_bytes(W)<=15*1024**3
 print('ADMITTED HDFS retention',receipt,'local release',a.release,flush=True)
if __name__=='__main__':main()
