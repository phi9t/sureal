"""Renew existing tickets and cached tokens; never obtain passwords unattended."""
import argparse,json,os,signal,subprocess,time
from pathlib import Path
from evidence.source_snapshot import file_sha256

def refresh_once(waystone,run):
 valid=run(['/usr/bin/klist','-s'],'ticket-validity')==0
 renewed=run(['/usr/bin/kinit','-R'],'ticket-renewal')==0
 if not valid and not renewed:
  return {'ok':False,'ticket_renewed':False,'interactive_login_required':True,'stage':'ticket-renewal'}
 if run(['/usr/bin/klist','-s'],'ticket-validity-after-renewal')!=0:
  return {'ok':False,'ticket_renewed':renewed,'interactive_login_required':True,'stage':'ticket-validity-after-renewal'}
 code=run([str(waystone),'--error-format','json','--command-timeout-secs','60','auth','keepalive','--refresh-token','--json'],'token-refresh')
 return {'ok':code==0,'ticket_renewed':renewed,'interactive_login_required':code!=0,'renewal_window_warning':not renewed,'stage':'token-refresh','exit_code':code}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);a=parser.parse_args();config=json.loads(a.config.read_text())
 for path,digest in config['tool_sha256'].items():
  if file_sha256(path)!=digest:raise RuntimeError('Pinned HDFS tool changed; reinstall keepalive after verification')
 def run(command,label):
  process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  try:return process.wait(timeout=75)
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGTERM)
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
   return 124
 status=refresh_once(config['waystone'],run);status['checked_unix_seconds']=int(time.time());status['interactive_refresh_script']=config['interactive_refresh_script'];state=Path(config['status_file']);state.parent.mkdir(parents=True,exist_ok=True);temporary=state.with_name(state.name+'.tmp');temporary.write_text(json.dumps(status,indent=2));temporary.chmod(0o600);os.replace(temporary,state);print(json.dumps(status),flush=True)
 raise SystemExit(0 if status['ok'] else 10)
if __name__=='__main__':main()
