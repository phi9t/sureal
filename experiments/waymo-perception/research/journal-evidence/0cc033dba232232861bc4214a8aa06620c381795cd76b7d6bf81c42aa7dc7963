import hashlib,json,os,subprocess,sys,time
from pathlib import Path
P=Path('/data02/home/philip.yang/workspace/sureal/.worktrees/waymo-tracer/experiments/waymo-perception');sys.path.insert(0,str(P))
from pipeline.insula_entry import launch_plan
R=Path('/tmp/sureal-memory-live20261003a');R.mkdir();code=R/'code';code.mkdir();inputs=R/'inputs';inputs.mkdir()
script=code/'probe.py';script.write_text("import importlib.util,sys,time\nassert importlib.util.find_spec('tensorflow') is None\nprint('READY no tensorflow',flush=True)\ntime.sleep(2)\nx=bytearray(int(sys.argv[1]))\nprint('ALLOCATED',len(x),flush=True)\ntime.sleep(1)\n")
root=Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2';checks=[]
for name,amount in [('within',8*1024**2),('over',128*1024**2)]:
 output=R/name;output.mkdir();unit='sureal-live-memory-'+name+'20261003a';native=launch_plan(root,code,inputs,output,['python','/experiment/probe.py',str(amount)]);cmd=['systemd-run','--user','--scope','--unit='+unit,'-p','MemoryAccounting=yes','-p','MemoryMax=67108864','-p','MemorySwapMax=0',*native]
 process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);samples=[];cg=None;started=time.monotonic()
 while process.poll() is None:
  if time.monotonic()-started>30:process.kill();raise TimeoutError('probe deadline')
  if cg is None:
   query=subprocess.run(['systemctl','--user','show',unit+'.scope','-p','ControlGroup','--value'],capture_output=True,text=True)
   if query.returncode==0 and query.stdout.strip():cg=Path('/sys/fs/cgroup')/query.stdout.strip().lstrip('/')
  if cg and (cg/'memory.max').exists():
   maximum=(cg/'memory.max').read_text().strip();assert maximum=='67108864';events=(cg/'memory.events').read_text();samples.append({'current':int((cg/'memory.current').read_text()),'max':maximum,'events':events})
  time.sleep(.01)
 text=process.communicate()[0];(R/(name+'.log')).write_text(text);assert samples and 'READY no tensorflow' in text
 if name=='within':assert process.returncode==0 and 'ALLOCATED 8388608' in text
 else:assert process.returncode!=0 and 'ALLOCATED 134217728' not in text
 check={'name':name,'command':cmd,'exit_code':process.returncode,'samples':samples,'stdout':text,'scope':'actual live Insula allocation under external kernel64MiB cap; over-limit must refuse, no model execution'};checks.append(check);print(name,process.returncode,'samples',len(samples),flush=True)
proof={'checks':checks,'scope':'live external memory-cap engineering probe only; historical stageRSS and full-controller resource admission remain open','fixture_sha256':hashlib.sha256(script.read_bytes()).hexdigest()};(P/'research/sustained-external-memory-live-probe.json').write_text(json.dumps(proof,indent=2)+'\n')
