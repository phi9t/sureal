"""Bounded native reconstruction child; runs only inside its fresh user scope."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
sys.dont_write_bytecode=True

MEMORY_MAX=268435456
TIMEOUT_SECONDS=60


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def scope_facts(unit):
    lines=Path('/proc/self/cgroup').read_text().splitlines()
    paths=[line[3:] for line in lines if line.startswith('0::')]
    if len(paths)!=1 or Path(paths[0]).name!=unit:
        raise ValueError('Native reconstruction not in the exact fresh user scope')
    root=Path('/sys/fs/cgroup')/paths[0].lstrip('/')
    facts={'path':paths[0],'memory_max':int((root/'memory.max').read_text()),
           'memory_swap_max':int((root/'memory.swap.max').read_text()),
           'process_ids':sorted(int(x) for x in (root/'cgroup.procs').read_text().split()),
           'events':dict((k,int(v)) for k,v in
                         (line.split() for line in (root/'memory.events').read_text().splitlines()))}
    if facts['memory_max']!=MEMORY_MAX or facts['memory_swap_max']!=0 or facts['process_ids']!=[os.getpid()]:
        raise ValueError('Native reconstruction cap/membership differs')
    if facts['events']['oom'] or facts['events']['oom_kill']:
        raise ValueError('Native reconstruction scope had an OOM')
    return facts


def main(input_path):
    record=json.loads(Path(input_path).read_text())
    root=Path(input_path).parent
    tool=Path(record['tool']['path']); exported=Path(record['export']['path'])
    if digest(tool)!=record['tool']['sha256'] or digest(exported)!=record['export']['sha256']:
        raise ValueError('Native reconstruction input/tool changed')
    actual=record['argv']
    if actual!=[str(tool),'--json','--as',record['actor'],'import','--input',str(exported),
                '--target',str(root/'recovered.db'),'--new-instance']:
        raise ValueError('Unadmitted reconstruction command')
    if Path(actual[-2]).exists() or any((root/'kata-home').iterdir()):
        raise ValueError('Reconstruction target/home is not fresh')
    scope_environment=dict(os.environ)
    invocation=scope_environment.pop('INVOCATION_ID',None)
    if scope_environment!=record['environment'] or not isinstance(invocation,str) or len(invocation)!=32 or any(c not in '0123456789abcdef' for c in invocation):
        raise ValueError('Reconstruction environment differs')
    before=scope_facts(record['unit'])
    started=time.time_ns()//1000000
    timed_out=False
    # Limits are inherited by the native child. Memory is enforced by cgroup,
    # rather than a Go-incompatible virtual-address-space approximation.
    resource.setrlimit(resource.RLIMIT_FSIZE,(67108864,67108864))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(TIMEOUT_SECONDS,TIMEOUT_SECONDS))
    with (root/'native.stdout').open('xb') as out,(root/'native.stderr').open('xb') as err:
        child=subprocess.Popen(actual,cwd=root,env=record['environment'],stdout=out,stderr=err,
                               start_new_session=True)
        try:
            code=child.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(child.pid,signal.SIGKILL)
            code=child.wait()
    after=scope_facts(record['unit'])
    ended=time.time_ns()//1000000
    ref=lambda path:{'path':str(path),'sha256':digest(path)}
    result={'schema_version':1,'argv':actual,'cwd':str(root),'environment':record['environment'],
            'tool':record['tool'],'export':record['export'],'exit_code':code,
            'started_ms':started,'ended_ms':ended,'timeout_ms':TIMEOUT_SECONDS*1000,
            'timed_out':timed_out,'worker_pid':os.getpid(),'native_pid':child.pid,
            'scope_invocation_id':invocation,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            'measurement':'fresh-process getrusage CHILDREN largest waited native child KiB',
            'scope_before':before,'scope_after':after,
            'stdout':ref(root/'native.stdout'),'stderr':ref(root/'native.stderr')}
    with (root/'native-command.json').open('x') as stream:
        json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    if timed_out or code or ended-started>TIMEOUT_SECONDS*1000 or result['peak_rss_kib']*1024>MEMORY_MAX:
        raise ValueError('Bounded native reconstruction failed')
    if digest(tool)!=record['tool']['sha256'] or digest(exported)!=record['export']['sha256']:
        raise ValueError('Native reconstruction input/tool changed after execution')
    return 0


if __name__=='__main__':
    raise SystemExit(main(sys.argv[1]))
