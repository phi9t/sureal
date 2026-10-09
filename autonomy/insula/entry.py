"""Host-side lock checking and dedicated offline rootfs entry."""
import argparse
import json
import os
from pathlib import Path
from insula.launch_plan import build_plan, load_runtime_lock, plan_data, render_plan
from insula.runtime_roots import current_cpu_rootfs, default_lock


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rootfs',type=Path,default=Path(os.environ.get('WAYMO_INSULA_ROOT',str(current_cpu_rootfs()))))
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
    lock_path=args.lock or default_lock(args.rootfs)
    runtime=load_runtime_lock(args.rootfs,lock_path)
    here=Path(__file__).resolve().parents[1]
    if not args.source.is_dir() or not args.output.is_dir(): raise ValueError('mount directory missing')
    plan=build_plan(runtime,code=here,source=args.source,output=args.output,command=command)
    if args.emit_plan:
        print(json.dumps(plan_data(plan),sort_keys=True));return
    argv=render_plan(plan)
    os.execvp(argv[0],argv)

if __name__=='__main__': main()
