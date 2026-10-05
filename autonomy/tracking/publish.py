import hashlib,json,os,signal,subprocess,sys,uuid
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));from tracking.journal import digest as sha,read_entries
import fcntl

def main():
 cli=Path.home()/'workspace/waystone/scripts/waystone';C=Path.home()/'.cache/waystone/waymo-perception';R=C/'insula'/('research-journal-publication-'+uuid.uuid4().hex);R.mkdir();pins={str(cli):sha(cli)};checks=[]
 for relative in ['rust/target/debug/waystone','native/libhdfs_client/dist/lib/libhdfs_client.so','native/libhdfs_client/dist/bin/hdfs.bin']:
  tool=cli.parents[1]/relative;pins[str(tool)]=sha(tool)
 def io(args,label):
  command=[str(cli),'--error-format','json','--auth-source','token-file',*args];process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:out,error=process.communicate(timeout=90)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);out,error=process.communicate();raise RuntimeError('bounded transfer timed out')
  (R/(label+'.log')).write_text(out+error);assert process.returncode==0,error;checks.append({'command':command,'exit_code':0,'log':str(R/(label+'.log'))});assert all(sha(path)==digest for path,digest in pins.items());return out
 layout=json.loads(subprocess.run([str(cli),'layout-profile','--project','sureal','--json'],capture_output=True,text=True,check=True,timeout=15).stdout);uri=layout['paths']['runs'].rstrip('/')+'/perception-research-journal/snapshot-'+R.name;files=['experiment-registry.json','experiments.json','experiment-tracker.md','research-journal.jsonl','research-journal.md']+[str(p.relative_to(P/'research')) for p in (P/'research/journal-evidence').iterdir() if p.is_file()];manifest={}
 staging=R/'staged';staging.mkdir()
 with (P/'research/experiment-tracker.lock').open('a') as trackerlock,(P/'research/research-journal.lock').open('a') as journallock:
  fcntl.flock(trackerlock,fcntl.LOCK_EX);fcntl.flock(journallock,fcntl.LOCK_SH);read_entries(P/'research/research-journal.jsonl')
  for name in files:
   original=P/'research'/name;copy=staging/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(original.read_bytes())
 for index,name in enumerate(files):
  source=staging/name;digest=sha(source);remote=uri+'/'+name;io(['--mkdir-parents','put',str(source),remote],f'{index}-put');copy=R/name;copy.parent.mkdir(parents=True,exist_ok=True);io(['get',remote,str(copy)],f'{index}-get');assert sha(copy)==digest;manifest[name]={'hdfs_uri':remote,'sha256':digest,'bytes':source.stat().st_size}
 indexpath=R/'manifest.json';indexpath.write_text(json.dumps(manifest,indent=2));io(['--mkdir-parents','put',str(indexpath),uri+'/manifest.json'],'manifest-put');readback=R/'manifest-readback.json';io(['get',uri+'/manifest.json',str(readback)],'manifest-get');assert sha(readback)==sha(indexpath);receipt={'all_results_uploaded_and_readback_exact':True,'hdfs_prefix':uri,'files':manifest,'manifest_hdfs_uri':uri+'/manifest.json','manifest_sha256':sha(indexpath),'checks':checks,'tool_pins':pins,'scope':'research registry, dashboard, append-only journal and every immutable evidence snapshot; exact HDFS readback'};(P/'research/research-journal-hdfs-verified.json').write_text(json.dumps(receipt,indent=2));print('ADMITTED research journal HDFS snapshot',uri,flush=True)

if __name__=='__main__':main()
