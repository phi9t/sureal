"""Host transport: staging ownership lasts through the worker consumed ACK.

The caller supplies admitted inventory, a staging context yielding a binary
reader, and a live worker's streams. Queue exclusion, readback verification,
worker deadlines and exit/report verification remain caller responsibilities.
"""
import json
import math
import os
import select
import time


def send_training_box_sources(inventory, *, stage, worker_input, worker_ack,
                              ack_timeout_seconds=None, write_timeout_seconds=None):
    for timeout in (ack_timeout_seconds, write_timeout_seconds):
        if timeout is not None and (
                isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError('positive finite transport timeout required')

    def write(data):
        if write_timeout_seconds is None:
            worker_input.write(data)
            return
        # Exclusively owned pipe: bypass buffering so blocked writes can time out.
        fd = worker_input.fileno()
        blocking = os.get_blocking(fd)
        os.set_blocking(fd, False)
        deadline = time.monotonic() + write_timeout_seconds
        view = memoryview(data)
        try:
            while view:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                    raise TimeoutError('worker input write deadline exceeded')
                try:
                    count = os.write(fd, view)
                except BlockingIOError:
                    continue
                if count <= 0:
                    raise ValueError('worker input made no write progress')
                view = view[count:]
        finally:
            os.set_blocking(fd, blocking)
    completed = []
    for source in inventory:
        with stage(source) as reader:
            write((json.dumps(source) + '\n').encode())
            remaining = source['bytes']
            while remaining:
                chunk = reader.read(min(65536, remaining))
                if not chunk or len(chunk) > remaining:
                    raise ValueError('staged source truncated or oversized read')
                write(chunk)
                remaining -= len(chunk)
            if reader.read(1):
                raise ValueError('staged source exceeds declared size')
            worker_input.flush()
            if ack_timeout_seconds is None:
                line = worker_ack.readline(4097)
            else:
                # This stream must be exclusively owned by this sender. Read
                # directly from the pipe to bound even a partial-line stall.
                deadline = time.monotonic() + ack_timeout_seconds
                data = bytearray()
                fd = worker_ack.fileno()
                while len(data) <= 4096:
                    remaining_time = deadline - time.monotonic()
                    if remaining_time <= 0 or not select.select([fd], [], [], remaining_time)[0]:
                        raise TimeoutError('worker consumed acknowledgement deadline exceeded')
                    byte = os.read(fd, 1)
                    if not byte:
                        break
                    data.extend(byte)
                    if byte == b'\n':
                        break
                try:
                    line = data.decode('utf-8')
                except UnicodeDecodeError as error:
                    raise ValueError('invalid acknowledgement encoding') from error
            if not line or len(line) > 4096 or not line.endswith('\n'):
                raise ValueError('missing or oversized consumed acknowledgement')
            try:
                event = json.loads(line)
            except (ValueError, TypeError) as error:
                raise ValueError('invalid consumed acknowledgement') from error
            expected = dict(scene=source['scene'], sha256=source['sha256'],
                            native_rows=source['native_rows'], status='consumed')
            if json.dumps(event, sort_keys=True) != json.dumps(expected, sort_keys=True):
                raise ValueError('consumed acknowledgement identity mismatch')
            completed.append(event)
    write((json.dumps(dict(kind='end', sources=len(completed))) + '\n').encode())
    worker_input.flush()
    return completed
