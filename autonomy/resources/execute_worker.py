"""Measure the actual worker inside Insula without changing its source bytes."""
import json
import os
from pathlib import Path
import resource
import runpy
import sys
import time

_RESOURCE_LAYER_ROOT=Path(__file__).resolve().parents[1]
if str(_RESOURCE_LAYER_ROOT) not in sys.path:
    sys.path.insert(0,str(_RESOURCE_LAYER_ROOT))

from evidence.source_snapshot import require_regular_file
from resources.process_lifecycle import enable_subreaper, completed_lifecycle


def main():
    if len(sys.argv)<3:
        raise ValueError('resource output directory and original worker path required')
    output=Path(sys.argv[1]);worker=Path(sys.argv[2]);args=sys.argv[2:]
    if not output.is_dir():raise ValueError('existing output and regular worker required')
    require_regular_file(worker)
    sys.argv=args
    enable_subreaper()
    completed_lifecycle()
    started=time.monotonic()
    # Keep its globals through accounting, as they would remain alive at EOF.
    state=runpy.run_path(str(worker),run_name='__main__')
    lifecycle=completed_lifecycle()
    own=resource.getrusage(resource.RUSAGE_SELF)
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={'worker_argv':args,'worker_pid':os.getpid(),
             'measurement':'in-runtime getrusage SELF and waited CHILDREN KiB',
             'self_peak_rss_kib':own.ru_maxrss,
             'waited_child_peak_rss_kib':children.ru_maxrss,
             'peak_rss_kib':max(own.ru_maxrss,children.ru_maxrss),
             'elapsed_seconds':time.monotonic()-started,'exit_code':0,
             'child_lifecycle':lifecycle,
             'scope':'worker process and largest waited child; not simultaneous tree RSS sum'}
    path=output/'worker-resource.json'
    with path.open('x') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    return state

if __name__=='__main__':main()
