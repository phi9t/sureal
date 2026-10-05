"""Fresh process measuring one worker tree with standard-library rusage."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import time


def main():
    output, *command = sys.argv[1:]
    started = time.monotonic()
    worker = subprocess.run(command)
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    Path(output).write_text(json.dumps({'elapsed_seconds': time.monotonic() - started,
                                       'peak_rss_kib': usage.ru_maxrss,
                                       'worker_exit_code': worker.returncode}) + '\n')
    sys.exit(worker.returncode)


if __name__ == '__main__':
    main()
