#!/usr/bin/env python3
"""Install a password-free, user-level HDFS renewal timer on this host."""
import hashlib,json,os,re,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[1];home=Path.home();waystone=home/'workspace/waystone';cli=waystone/'scripts/waystone'
def sha(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
source=P/'resources/hdfs_auth_keepalive.py';library=home/'.local/lib/sureal';library.mkdir(parents=True,exist_ok=True);installed=library/'hdfs_auth_keepalive.py';shutil.copy(source,installed);installed.chmod(0o700);state=home/'.local/state/sureal/hdfs-auth';state.mkdir(parents=True,exist_ok=True);state.chmod(0o700);config=state/'config.json';tools=[cli,waystone/'rust/target/debug/waystone',waystone/'native/libhdfs_client/dist/lib/libhdfs_client.so',waystone/'native/libhdfs_client/dist/bin/hdfs.bin'];config.write_text(json.dumps({'waystone':str(cli),'tool_sha256':{str(p):sha(p) for p in tools},'status_file':str(state/'status.json'),'interactive_refresh_script':str(P/'scripts/refresh-hdfs-auth.sh')},indent=2));config.chmod(0o600)
listing=subprocess.run(['/usr/bin/klist'],capture_output=True,text=True,check=True).stdout;cache=re.search(r'^Ticket cache: (.+)$',listing,re.MULTILINE).group(1);assert cache.startswith('FILE:') and '\n' not in cache and ' ' not in cache
units=home/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True);service=units/'sureal-hdfs-auth.service';timer=units/'sureal-hdfs-auth.timer'
service.write_text(f'''[Unit]
Description=Renew existing Kerberos ticket and refresh Sureal HDFS token cache

[Service]
Type=oneshot
UMask=0077
Environment=KRB5CCNAME={cache}
ExecStart=/usr/bin/python3 {installed} --config {config}
StandardInput=null
TimeoutStartSec=240
''')
timer.write_text('''[Unit]
Description=Refresh Sureal HDFS authentication every 30 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=30min
AccuracySec=30s
Unit=sureal-hdfs-auth.service

[Install]
WantedBy=timers.target
''')
for args in [['daemon-reload'],['enable','--now','sureal-hdfs-auth.timer'],['start','sureal-hdfs-auth.service']]:subprocess.run(['systemctl','--user',*args],check=True,timeout=250)
status=json.loads((state/'status.json').read_text());assert status['ok'];receipt={'service':str(service),'service_sha256':sha(service),'timer':str(timer),'timer_sha256':sha(timer),'installed_script':str(installed),'installed_script_sha256':sha(installed),'source_script_sha256':sha(source),'config_file':str(config),'config_sha256':sha(config),'status':status,'scope':'renew existing tickets and cached token; interactive login required beyond Kerberos renewal window'};(P/'research/hdfs-auth-keepalive-installed.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(status));print('Installed and started sureal-hdfs-auth.timer')
