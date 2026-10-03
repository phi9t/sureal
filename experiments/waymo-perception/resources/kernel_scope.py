"""Read genuine cgroup-v2 limits and membership; no missing-cap fallback."""
from pathlib import Path


def _path(proc_file):
    text=proc_file.read_text().strip().splitlines()
    if len(text)!=1 or not text[0].startswith('0::/'):
        raise ValueError('one unified kernel cgroup membership required')
    path=text[0][3:]
    if ('..' in Path(path).parts or
        not path.rsplit('/',1)[-1].startswith('sureal-sustained-') or
        not path.endswith('.scope')):
        raise ValueError('declared sustained resource scope required')
    return path


def read_scope(cap_bytes, *, pid=None, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup')):
    if type(cap_bytes) is not int or cap_bytes<=0 or (pid is not None and (type(pid) is not int or pid<=0)):
        raise ValueError('positive integer cap and process ID required')
    try:
        proc=Path(proc);cgroups=Path(cgroups);path=_path(proc/'self/cgroup');scope=cgroups/path.lstrip('/')
        maximum=(scope/'memory.max').read_text().strip();swap=(scope/'memory.swap.max').read_text().strip()
        if maximum!=str(cap_bytes) or swap!='0':
            raise ValueError('exact bounded memory.max and zero memory.swap.max required')
        events={}
        for line in (scope/'memory.events').read_text().splitlines():
            name,value=line.split()
            if name in events or not value.isdecimal():raise ValueError('unique nonnegative kernel counters required')
            events[name]=int(value)
        if events.get('oom')!=0 or events.get('oom_kill')!=0:
            raise ValueError('resource scope has an OOM event')
        process_ids=read_members(path,proc=proc,cgroups=cgroups)
        if pid is not None and (pid not in process_ids or _path(proc/str(pid)/'cgroup')!=path):
            raise ValueError('worker escaped the admitted resource scope')
    except (OSError,TypeError) as error:
        raise ValueError('kernel resource controls and membership must be observable') from error
    return {'path':path,'memory_max_bytes':cap_bytes,'memory_swap_max_bytes':0,
            'oom':events['oom'],'oom_kill':events['oom_kill'],
            'members_verified':pid is not None,'kernel_events':events,'process_ids':process_ids}


def read_members(path, *, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup')):
    """Membership remains readable for cleanup after a recorded OOM."""
    if _path(Path(proc)/'self/cgroup')!=path:
        raise ValueError('caller must still own the declared resource scope')
    values=(Path(cgroups)/path.lstrip('/')/'cgroup.procs').read_text().split()
    if any(not value.isdecimal() or int(value)<=0 for value in values):
        raise ValueError('positive kernel process IDs required')
    return sorted(set(map(int,values)))
