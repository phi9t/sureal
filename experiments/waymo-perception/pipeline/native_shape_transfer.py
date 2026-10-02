"""Deadline for one owned Waystone readback; caller retains staging ownership."""
import argparse
import math
import os
import signal
import subprocess
import sys
import time

WAYSTONE='/data02/home/philip.yang/workspace/waystone/scripts/waystone'

def bounded_transfer(command,*,timeout_seconds):
    if (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float))
        or not math.isfinite(timeout_seconds) or timeout_seconds<=0
        or not isinstance(command,(list,tuple)) or not command
        or any(not isinstance(v,str) or not v for v in command)):
        raise ValueError('explicit command and finite positive deadline required')
    start=time.monotonic();child=subprocess.Popen(command,start_new_session=True)
    try:
        code=child.wait(timeout=timeout_seconds)
    except BaseException as error:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()
        if isinstance(error,subprocess.TimeoutExpired):
            raise ValueError('source transfer deadline expired; owned process killed and reaped') from error
        raise
    return {'exit_code':code,'pid':child.pid,'deadline_seconds':timeout_seconds,
            'elapsed_seconds':time.monotonic()-start}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--timeout-seconds',type=float,default=600);parser.add_argument('operation',choices=['get']);parser.add_argument('source');parser.add_argument('destination');args=parser.parse_args()
    if not args.source.startswith('hdfs://'):parser.error('explicit HDFS source required')
    result=bounded_transfer([WAYSTONE,args.operation,args.source,args.destination],timeout_seconds=args.timeout_seconds)
    raise SystemExit(result['exit_code'] if result['exit_code']>=0 else 1)
if __name__=='__main__':main()
