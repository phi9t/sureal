"""Linux child accounting, separate from model reports and aggregate charge.

wait4 reports the largest waited child's RSS in KiB, including waited
sub-descendants. It is not the simultaneous sum of a process tree. A separate
kernel cgroup cap provides enforcement; admission requires both pieces.
"""
import math
import os
import signal
import subprocess
import time

MEASUREMENT = 'wait4.ru_maxrss_KiB_largest_waited_child'


def measure(command, *, cwd, stream, timeout, env=None, observer=None):
    if (not isinstance(command, list) or not command or
        any(not isinstance(x, str) or not x for x in command) or
        type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('literal command and finite positive timeout required')
    start = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream,
                               stderr=subprocess.STDOUT, start_new_session=True)
    timed_out = False
    kill_at = None
    try:
        if observer is not None:
            observer(process.pid)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                process.returncode = os.waitstatus_to_exitcode(status)
                break
            if observer is not None:
                observer(None)
            now = time.monotonic()
            if not timed_out and now - start >= timeout:
                timed_out = True
                kill_at = now + .2
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif kill_at is not None and now >= kill_at:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                kill_at = None
            time.sleep(.01)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, status, _ = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
        raise
    if timed_out:
        # The direct child can exit before another member ignoring TERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return {'command':command.copy(), 'exit_code':process.returncode,
            'timed_out':timed_out, 'peak_rss_kib':usage.ru_maxrss,
            'elapsed_seconds':time.monotonic()-start, 'measurement':MEASUREMENT}


def admit(record, command, cap_bytes):
    try:
        scope = record['kernel_scope']
        lifecycle = record['stage_lifecycle']
        if (type(cap_bytes) is not int or cap_bytes <= 0 or
            record['command'] != command or type(record['exit_code']) is not int or
            record['exit_code'] != 0 or record['timed_out'] is not False or
            record['measurement'] != MEASUREMENT or
            type(record['peak_rss_kib']) is not int or
            not 0 < record['peak_rss_kib'] * 1024 <= cap_bytes or
            type(record['elapsed_seconds']) not in (int, float) or
            not math.isfinite(record['elapsed_seconds']) or record['elapsed_seconds'] < 0 or
            not isinstance(scope['path'], str) or
            not scope['path'].rsplit('/',1)[-1].startswith('sureal-sustained-') or
            not scope['path'].endswith('.scope') or
            type(scope['memory_max_bytes']) is not int or scope['memory_max_bytes'] != cap_bytes or
            type(scope['memory_swap_max_bytes']) is not int or scope['memory_swap_max_bytes'] != 0 or
            type(scope['oom']) is not int or scope['oom'] != 0 or
            type(scope['oom_kill']) is not int or scope['oom_kill'] != 0 or
            scope['members_verified'] is not True or
            lifecycle['subreaper_verified'] is not True or lifecycle['remaining_children'] != [] or
            type(lifecycle['caller_pid']) is not int or lifecycle['caller_pid']<=0 or
            lifecycle['scope_members_before'] != [lifecycle['caller_pid']] or
            lifecycle['scope_members_after'] != [lifecycle['caller_pid']] or
            scope['process_ids'] != [lifecycle['caller_pid']] or
            record.get('lifecycle_violation',False) is not False):
            raise ValueError('complete successful measured RSS and kernel-scope proof required')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('complete resource proof required') from error
    return {'peak_rss_bytes':record['peak_rss_kib'] * 1024,
            'aggregate_cap_bytes':cap_bytes,
            'scope':'largest waited-child RSS plus external aggregate kernel cap; not tree RSS sum'}


def admit_worker(host, worker, command, worker_argv, cap_bytes):
    admitted=admit(host,command,cap_bytes)
    try:
        lifecycle=worker['child_lifecycle']
        if (worker['worker_argv']!=worker_argv or
            worker['measurement']!='in-runtime getrusage SELF and waited CHILDREN KiB' or
            type(worker['worker_pid']) is not int or worker['worker_pid']<=0 or
            type(worker['exit_code']) is not int or worker['exit_code']!=0 or
            type(worker['self_peak_rss_kib']) is not int or worker['self_peak_rss_kib']<=0 or
            type(worker['waited_child_peak_rss_kib']) is not int or worker['waited_child_peak_rss_kib']<0 or
            type(worker['peak_rss_kib']) is not int or
            worker['peak_rss_kib']!=max(worker['self_peak_rss_kib'],worker['waited_child_peak_rss_kib']) or
            worker['peak_rss_kib']*1024>cap_bytes or
            type(worker['elapsed_seconds']) not in (int,float) or
            not math.isfinite(worker['elapsed_seconds']) or worker['elapsed_seconds']<0 or
            lifecycle['subreaper_verified'] is not True or lifecycle['remaining_children'] != []):
            raise ValueError('actual in-runtime worker resource proof required')
    except (KeyError,TypeError) as error:
        raise ValueError('complete worker resource proof required') from error
    admitted['peak_rss_bytes']=max(admitted['peak_rss_bytes'],worker['peak_rss_kib']*1024)
    admitted['scope']='separate launcher and in-runtime worker/waited-child peaks under aggregate kernel cap; not summed tree RSS'
    return admitted
