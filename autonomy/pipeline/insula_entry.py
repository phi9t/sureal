"""Host-side lock checking and dedicated offline rootfs entry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from .runtime_identity import verify_rootfs


def launch_plan(root, experiment, source, output, command):
    roots = [Path(x).resolve() for x in (root, experiment, source, output)]
    root, experiment, source, output = roots
    if any(a == b or a in b.parents or b in a.parents
           for a, b in [(source, output),(root,output),(experiment,output)]):
        raise ValueError('unsafe overlapping mounts')
    return ['bwrap','--unshare-all','--die-with-parent','--ro-bind',str(root),'/',
            '--ro-bind',str(experiment),'/experiment','--ro-bind',str(source),'/source',
            '--bind',str(output),'/outputs','--proc','/proc','--dev','/dev',
            '--tmpfs','/tmp','--clearenv','--setenv','HOME','/tmp/private-home',
            '--setenv','PATH','/usr/local/bin:/usr/bin:/bin',
            '--setenv','PYTHONNOUSERSITE','1','--setenv','PYTHONDONTWRITEBYTECODE','1',
            '--setenv','PYTHONPATH','/experiment','--chdir','/experiment','--',*command]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rootfs',type=Path,default=Path(os.environ.get('WAYMO_INSULA_ROOT',str(Path.home()/'.cache/waystone/waymo-perception/insula/rootfs-v2'))))
    p.add_argument('--lock',type=Path)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--offline',action='store_true')
    p.add_argument('--emit-plan',action='store_true')
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args()
    command=args.command
    if command and command[0]=='--': command=command[1:]
    if not command: p.error('command required')
    here=Path(__file__).resolve().parents[1]
    plan=launch_plan(args.rootfs,here,args.source,args.output,command)
    if args.emit_plan:
        print(json.dumps(plan));return
    lock_path=args.lock or Path(str(args.rootfs)+'.lock.json')
    lock=json.loads(lock_path.read_text())
    if lock.get('schema_version')!=1: raise ValueError('invalid runtime lock schema')
    for key,file in [('requirements_sha256',here/'requirements-tracer.lock'),('dockerfile_sha256',here/'insula/Dockerfile')]:
        if lock[key]!=hashlib.sha256(file.read_bytes()).hexdigest(): raise ValueError('runtime recipe mismatch')
    verify_rootfs(args.rootfs,lock['rootfs_sha256'])
    if not args.source.is_dir() or not args.output.is_dir(): raise ValueError('mount directory missing')
    os.execvp(plan[0],plan)

if __name__=='__main__': main()
