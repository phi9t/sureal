"""One owned worker process; stderr cannot fill a pipe and block consumption."""
import io
import subprocess
import time
from pathlib import Path

from .training_box_sender import send_training_box_sources


def run_source_worker(command, inventory, *, stage, stderr_path,
                      ack_timeout_seconds, write_timeout_seconds,
                      exit_timeout_seconds):
    """Return only after all ACKs, footer, EOF and clean worker exit.

    The caller must pin code/runtime/input identities, admit all source records,
    own the queue lease, provide bounded verified staging, and verify the report.
    This function exclusively owns unbuffered worker pipes and reaps its process
    on transfer, protocol or completion failure.
    """
    started = time.monotonic()
    with Path(stderr_path).open('xb') as stderr:
        worker = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=stderr, bufsize=0)
        acknowledgement = io.TextIOWrapper(worker.stdout, encoding='utf-8')
        try:
            events = send_training_box_sources(
                inventory, stage=stage, worker_input=worker.stdin, worker_ack=acknowledgement,
                ack_timeout_seconds=ack_timeout_seconds, write_timeout_seconds=write_timeout_seconds)
            worker.stdin.close()
            status = worker.wait(timeout=exit_timeout_seconds)
            if status:
                raise ValueError('source worker failed; inspect retained stderr: ' + str(stderr_path))
            # The consumed ACKs exhaust the protocol. Other stdout is ambiguous.
            if acknowledgement.read(1):
                raise ValueError('unexpected worker output after source acknowledgements')
            return {'command': list(command), 'exit_code': status,
                    'acknowledgements': events, 'elapsed_seconds': time.monotonic() - started,
                    'stderr': str(stderr_path)}
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait()
            if not worker.stdin.closed:
                worker.stdin.close()
            acknowledgement.close()
