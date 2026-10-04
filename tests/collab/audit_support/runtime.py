"""Literal rootfs/argv/kernel oracles; no producer or resource-helper imports."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import stat

from .facts import require
from .raw_git import InvalidEvidence


def rootfs_digest(root: Path) -> str:
    require(root.is_dir() and not root.is_symlink(), "Regular actual rootfs required")
    names = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        names.extend(Path(directory)/name for name in dirs+files)
    state = hashlib.sha256()
    for path in sorted(names):
        info = path.lstat()
        record = [path.relative_to(root).as_posix(), stat.S_IFMT(info.st_mode),
                  stat.S_IMODE(info.st_mode)]
        if stat.S_ISLNK(info.st_mode):
            record.append(os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            with path.open("rb") as stream:
                content = hashlib.file_digest(stream,"sha256").hexdigest()
            record.extend([info.st_size,content])
        elif not stat.S_ISDIR(info.st_mode):
            record.append(info.st_rdev)
        state.update((json.dumps(record,separators=(",",":"))+"\n").encode())
    return state.hexdigest()


def positive_int(value, reason):
    require(type(value) is int and value>0,reason)


def elapsed(value, timeout):
    require(type(value) in (float,int) and math.isfinite(value) and 0<=value<=timeout,
            "Measured elapsed exceeds bound or is invalid")


def check_measurements(host, worker, command, worker_argv, cap_bytes, timeout):
    positive_int(cap_bytes,"Exact positive kernel memory cap required")
    require(type(timeout) in (int,float) and math.isfinite(timeout) and timeout>0,
            "Finite positive runtime timeout required")
    require(host["command"]==command and type(host["exit_code"]) is int and host["exit_code"]==0 and
            host["timed_out"] is False and
            host["measurement"]=="wait4.ru_maxrss_KiB_largest_waited_child",
            "Actual host execution/accounting incomplete")
    positive_int(host["peak_rss_kib"],"Invalid host RSS")
    require(host["peak_rss_kib"]*1024<=cap_bytes,"Host measured RSS exceeds cap")
    elapsed(host["elapsed_seconds"],timeout)
    scope = host["kernel_scope"]; lifecycle = host["stage_lifecycle"]
    caller = lifecycle["caller_pid"]
    positive_int(caller,"Invalid scope caller PID")
    require(isinstance(scope["path"],str) and
            Path(scope["path"]).name.startswith("sureal-sustained-collab-") and
            scope["path"].endswith(".scope"),"Actual fresh collaboration scope required")
    require(type(scope["memory_max_bytes"]) is int and scope["memory_max_bytes"]==cap_bytes and
            type(scope["memory_swap_max_bytes"]) is int and scope["memory_swap_max_bytes"]==0 and
            type(scope["oom"]) is int and scope["oom"]==0 and
            type(scope["oom_kill"]) is int and scope["oom_kill"]==0,
            "Kernel cap/swap/oom proof wrong")
    require(scope["members_verified"] is True and scope["process_ids"]==[caller] and
            lifecycle["scope_members_before"]==[caller] and lifecycle["scope_members_after"]==[caller] and
            lifecycle["subreaper_verified"] is True and lifecycle["remaining_children"]==[] and
            host.get("lifecycle_violation",False) is False,"Unreconciled host descendants/scope ownership")
    require(worker["worker_argv"]==worker_argv and
            worker["measurement"]=="in-runtime getrusage SELF and waited CHILDREN KiB" and
            type(worker["exit_code"]) is int and worker["exit_code"]==0,
            "Actual worker argv/accounting incomplete")
    positive_int(worker["worker_pid"],"Invalid worker PID")
    positive_int(worker["self_peak_rss_kib"],"Invalid worker self RSS")
    require(type(worker["waited_child_peak_rss_kib"]) is int and worker["waited_child_peak_rss_kib"]>=0,
            "Invalid waited child RSS")
    require(type(worker["peak_rss_kib"]) is int and
            worker["peak_rss_kib"]==max(worker["self_peak_rss_kib"],worker["waited_child_peak_rss_kib"]) and
            worker["peak_rss_kib"]*1024<=cap_bytes,"Invalid/excess worker RSS")
    elapsed(worker["elapsed_seconds"],timeout)
    require(worker["child_lifecycle"]["subreaper_verified"] is True and
            worker["child_lifecycle"]["remaining_children"]==[],"Unreconciled worker descendants")


def bwrap_options(argv: list[str]) -> tuple[list[tuple[str,list[str]]],list[str]]:
    require(isinstance(argv,list) and argv and all(isinstance(x,str) and x for x in argv),
            "Literal nonempty final bwrap argv required")
    require(Path(argv[0]).name=="bwrap","Actual bwrap executable required")
    sizes = {"--ro-bind":2,"--bind":2,"--dev-bind":2,"--setenv":2,
             "--proc":1,"--dev":1,"--tmpfs":1,"--chdir":1,"--uid":1,"--gid":1,
             "--unshare-all":0,"--unshare-user":0,"--unshare-pid":0,"--unshare-net":0,
             "--unshare-ipc":0,"--unshare-uts":0,"--die-with-parent":0,"--new-session":0,
             "--clearenv":0,"--hostname":1,"--dir":1,"--symlink":2,
             "--cap-drop":1,"--setenv":2,"--unsetenv":1}
    result = []; index = 1
    while index<len(argv) and argv[index]!="--":
        option = argv[index]
        require(option in sizes,"Unadmitted bwrap option: "+option)
        count = sizes[option]; values = argv[index+1:index+1+count]
        require(len(values)==count,"Truncated bwrap option")
        result.append((option,values)); index += 1+count
    require(index<len(argv) and argv[index]=="--" and index+1<len(argv),"Missing native worker argv")
    return result,argv[index+1:]


def check_bwrap(argv, rootfs, source, reference, output):
    options,worker = bwrap_options(argv)
    require({"--unshare-all","--die-with-parent","--clearenv"} <= {opt for opt,_ in options},
            "Actual isolated namespaces and private environment required")
    mounts = [(opt,val) for opt,val in options if opt in
              {"--ro-bind","--bind","--dev-bind","--proc","--dev","--tmpfs"}]
    required=[("--ro-bind",[rootfs,"/"]), ("--ro-bind",[source,"/source"]),
              ("--ro-bind",[reference,"/experiment"]),("--bind",[output,"/outputs"]),
              ("--tmpfs",["/tmp"])]
    optional=[("--proc",["/proc"]),("--dev",["/dev"])]
    require(all(mount in required+optional for mount in mounts) and
            all(mounts.count(mount)==1 for mount in mounts),
            "Undeclared or shadowing original runtime mount")
    require(not any(opt in {"--dir","--symlink"} for opt,_ in options),
            "Undeclared runtime path substitution")
    for target, want in [("/",("--ro-bind",[rootfs,"/"])),
                         ("/source",("--ro-bind",[source,"/source"])),
                         ("/experiment",("--ro-bind",[reference,"/experiment"])),
                         ("/outputs",("--bind",[output,"/outputs"]))]:
        require([(opt,val) for opt,val in mounts if val[-1]==target]==[want],
                "Wrong actual mount for "+target)
    writable = [(opt,val) for opt,val in mounts if opt in {"--bind","--dev-bind"}]
    require(writable==[("--bind",[output,"/outputs"])],"Undeclared writable host mount")
    require([(opt,val) for opt,val in mounts if val[-1]=="/tmp"]==[("--tmpfs",["/tmp"])],
            "Actual private scratch tmpfs required")
    require([val for opt,val in options if opt=="--chdir"]==[["/source"]],
            "Final in-runtime cwd must be /source")
    require([val for opt,val in options if opt=="--setenv" and val[0]=="PYTHONPATH"]==
            [["PYTHONPATH","/source:/experiment"]],"Final PYTHONPATH differs from actual import closure")
    environment=[val for opt,val in options if opt=="--setenv"]
    expected_environment={"HOME":"/tmp/private-home","PATH":"/usr/local/bin:/usr/bin:/bin",
        "PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":"/source:/experiment"}
    require(len(environment)==len(expected_environment) and dict(environment)==expected_environment and
            not any(opt=="--unsetenv" for opt,_ in options),"Undeclared runtime executable/import environment")
    require(worker[0]=="python" and len(worker)>1 and worker[1].startswith("/source/"),
            "Native worker must execute pinned source script")
