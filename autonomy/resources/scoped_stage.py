"""A stage can be admitted only inside the externally installed kernel cap."""
import os
from pathlib import Path
import signal
import time
from resources.kernel_scope import read_scope, read_members, _path
from resources.process_lifecycle import enable_subreaper, completed_lifecycle, direct_children
from resources.stage_accounting import measure,admit


def _reap_completed():
    completed=[]
    while True:
        try:pid,_,usage=os.wait4(-1,os.WNOHANG)
        except ChildProcessError:break
        if not pid:break
        completed.append({'pid':pid,'peak_rss_kib':usage.ru_maxrss})
    return completed


def _settle_launchers(cap_bytes,caller,deadline):
    """Wait only until the stage deadline for adopted launcher completion.

    A Bubblewrap helper can exit after the direct launcher. Every completed
    helper is actually waited/measured; remaining children still refuse.
    The original worker's stricter no-unwaited-child gate is unchanged.
    """
    completed=[]
    while True:
        completed.extend(_reap_completed())
        terminal=read_scope(cap_bytes);children=direct_children()
        if not children and terminal['process_ids']==[caller] or time.monotonic()>=deadline:
            return completed,terminal,children
        time.sleep(min(.002,max(0,deadline-time.monotonic())))


def _cleanup(path):
    """Terminate only members of this initially exclusive stage scope.

    PID descriptors avoid signalling a different process after PID reuse.
    Orphaned stage children are adopted by the caller and reaped here.
    """
    killed=set();deadline=time.monotonic()+2
    while True:
        for pid in read_members(path):
            if pid==os.getpid():continue
            try:
                descriptor=os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            try:
                if _path(Path('/proc')/str(pid)/'cgroup')!=path:
                    raise ValueError('cleanup refuses a foreign process')
                signal.pidfd_send_signal(descriptor,signal.SIGKILL)
                killed.add(pid)
            except (FileNotFoundError,ProcessLookupError):
                pass
            finally:
                os.close(descriptor)
        while True:
            try:pid,_,_=os.wait4(-1,os.WNOHANG)
            except ChildProcessError:break
            if not pid:break
        if read_members(path)==[os.getpid()] and not direct_children():
            return {'complete':True,'terminated_process_ids':sorted(killed)}
        if time.monotonic()>=deadline:
            raise RuntimeError('stage process cleanup incomplete; resource admission forbidden')
        time.sleep(.01)


def run_scoped(command, *, cwd, stream, timeout, cap_bytes, env=None):
    started=time.monotonic()
    initial=read_scope(cap_bytes)
    caller=os.getpid()
    if initial['process_ids']!=[caller]:
        raise ValueError('stage requires an exclusive resource scope before launch')
    enable_subreaper()
    completed_lifecycle()
    membership=None
    def observe(pid):
        nonlocal membership
        state=read_scope(cap_bytes,pid=pid)
        if state['path']!=initial['path']:
            raise ValueError('resource scope changed during stage')
        if pid is not None:membership=state
    try:
        result=measure(command,cwd=cwd,stream=stream,timeout=timeout,env=env,observer=observe)
        # Bubblewrap can leave an exited helper for its subreaper to wait.
        # Include actual wait4 usage; never treat an un-reaped zombie as proof.
        completed,terminal,children=_settle_launchers(cap_bytes,caller,min(started+timeout,time.monotonic()+.1))
        result['completed_launcher_descendants']=completed
        result['peak_rss_kib']=max([result['peak_rss_kib']]+[item['peak_rss_kib'] for item in completed])
        result['elapsed_seconds']=time.monotonic()-started
        if result['elapsed_seconds']>timeout:result['timed_out']=True
    except BaseException:
        _cleanup(initial['path'])
        raise
    if membership is None or terminal['path']!=initial['path']:
        raise ValueError('worker membership or terminal scope missing')
    terminal['members_verified']=True
    result['kernel_scope']=terminal
    result['stage_lifecycle']={'caller_pid':caller,'scope_members_before':initial['process_ids'],
                              'scope_members_after':terminal['process_ids'],
                              'remaining_children':children,
                              'subreaper_verified':completed_lifecycle()['subreaper_verified'] if not children else False}
    if children or terminal['process_ids']!=[caller]:
        result['cleanup']=_cleanup(initial['path'])
        result['lifecycle_violation']=True
    if result['exit_code']==0 and not result['timed_out'] and not result.get('lifecycle_violation'):
        result['resource_admission']=admit(result,command,cap_bytes)
    return result
