"""Independently execute fresh native import; never accept a supplied replay flag."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys
import time
import uuid

from .evidence import artifact, command_record, json_artifact, sqlite_projection
from .facts import require, content_digest
from .raw_git import InvalidEvidence, sha256, write_new
from .search_index import FTS_TABLES


def reconstruct_queue(export_ref, tool_ref, output, owner):
    exported=artifact(export_ref);tool=artifact(tool_ref)
    require(output.is_absolute() and not output.exists() and not output.is_symlink(),
            'Native reconstruction requires a new absolute audit-owned directory')
    require(output.parent.is_dir() and output.parent.resolve()==output.parent,
            'Native reconstruction parent must be physical and existing')
    require(isinstance(owner,str) and owner,'Independent reconstruction owner required')
    systemd=Path(shutil.which('systemd-run') or '').resolve()
    require(systemd.is_file(),'Actual user scope launcher absent')
    python=Path(sys.executable).resolve()
    helper=Path(__file__).with_name('recovery_process.py').resolve()
    output.mkdir(mode=0o700)
    for directory in ('kata-home','home'):
        (output/directory).mkdir(mode=0o700)
    attempt=uuid.uuid4().hex
    unit='sureal-sustained-collab-audit49-'+attempt+'.scope'
    environment={'HOME':str(output/'home'),'KATA_HOME':str(output/'kata-home'),
                 'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','GOMAXPROCS':'1','GOMEMLIMIT':'64MiB',
                 'PYTHONDONTWRITEBYTECODE':'1','XDG_RUNTIME_DIR':'/run/user/'+str(os.getuid())}
    argv=[str(tool),'--json','--as','sureal/audit49-'+attempt,'import',
          '--input',str(exported),'--target',str(output/'recovered.db'),'--new-instance']
    tool_before=sha256(tool);input_before=sha256(exported)
    inputs={'schema_version':1,'owner':owner,'tool':tool_ref,'export':export_ref,
            'unit':unit,'actor':argv[3],'argv':argv,'environment':environment,
            'target_absent':True,'kata_home_initial_files':[],
            'helper':{'path':str(helper),'sha256':sha256(helper)},
            'python':{'path':str(python),'sha256':sha256(python)}}
    write_new(output/'inputs.json',inputs)
    outer=[str(systemd),'--user','--scope','--quiet','--unit='+unit,
           '--property=MemoryMax=268435456','--property=MemorySwapMax=0',
           '--property=TasksMax=32','--',str(python),str(helper),str(output/'inputs.json')]
    started=time.time_ns()//1000000
    try:
        with (output/'scope.stdout').open('xb') as stdout,(output/'scope.stderr').open('xb') as stderr:
            process=subprocess.run(outer,cwd=output,env=environment,stdout=stdout,stderr=stderr,timeout=90)
    except subprocess.TimeoutExpired as error:
        raise InvalidEvidence('Native reconstruction user scope timed out; retained attempt needs reconciliation') from error
    ended=time.time_ns()//1000000
    ref=lambda path:{'path':str(path),'sha256':sha256(path)}
    command={'schema_version':1,'argv':outer,'cwd':str(output),'environment':environment,
             'tool':ref(systemd),'python':ref(python),'helper':ref(helper),
             'started_ms':started,'ended_ms':ended,'exit_code':process.returncode,
             'timeout_ms':90000,'stdout':ref(output/'scope.stdout'),'stderr':ref(output/'scope.stderr')}
    write_new(output/'scope-command.json',command)
    require(process.returncode==0,'Independent bounded native import failed; inspect retained scope stderr')
    raw=command_record(output/'native-command.json')
    require(raw['argv']==argv and raw['environment']==environment and raw['cwd']==str(output) and
            raw['exit_code']==0 and raw['timed_out'] is False and raw['worker_pid']!=raw['native_pid'] and
            type(raw['peak_rss_kib']) is int and 0<raw['peak_rss_kib']*1024<=268435456,
            'Actual bounded native reconstruction accounting/identity differs')
    for field in ('scope_before','scope_after'):
        scope=raw[field]
        require(Path(scope['path']).name==unit and scope['memory_max']==268435456 and
                scope['memory_swap_max']==0 and scope['process_ids']==[raw['worker_pid']] and
                scope['events']['oom']==scope['events']['oom_kill']==0,
                'Native reconstruction scope cap/descendants/OOM differs')
    require(sha256(tool)==tool_before and sha256(exported)==input_before and
            sha256(helper)==inputs['helper']['sha256'],'Native reconstruction input/authority changed')
    home_entries=list((output/'kata-home').rglob('*'))
    # Installed native import initializes only empty machine runtime dirs;
    # it must create no daemon/socket/PID/database/token payload in KATA_HOME.
    require(all(path.is_dir() and not path.is_symlink() and
                (path.relative_to(output/'kata-home').as_posix()=='runtime' or
                 re.fullmatch(r'runtime/[0-9a-f]{12}',path.relative_to(output/'kata-home').as_posix()))
                for path in home_entries),'Offline reconstruction unexpectedly created home runtime payload')
    require(not Path(str(output/'recovered.db')+'-wal').exists(),
            'Native recovery must settle its target before independent readback')
    files=[path for path in output.rglob('*') if path.is_file()]
    require(sum(path.stat().st_size for path in files)<=134217728,
            'Native recovery retained output exceeds 128MiB bound')
    recovered_ref=ref(output/'recovered.db')
    database=sqlite_projection(recovered_ref)
    rows={table:database['tables'][table] for table in sorted(FTS_TABLES)}
    receipt={'schema_version':1,'kind':'independent-native-scoped-reconstruction','owner':owner,
             'inputs':ref(output/'inputs.json'),'scope_command':ref(output/'scope-command.json'),
             'native_command':ref(output/'native-command.json'),'database':recovered_ref,
             'kata_home_final_directories':sorted(path.relative_to(output/'kata-home').as_posix()
                                                for path in home_entries),
             'physical_search_sha256':content_digest(rows),'fresh_instance_uid':database['meta']['instance_uid']}
    write_new(output/'reconstruction.json',receipt)
    # Reopen exactly what will be reported, rather than return a passed flag.
    json_artifact(ref(output/'reconstruction.json'))
    return database,ref(output/'reconstruction.json')
