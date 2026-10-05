"""Preflight-only original-connection capture; no native control or stop oracle.

The independent observer rederives coverage from these immutable raw records.
Lifecycle projection is supplied by the separately pinned fixture operator.
"""
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import stat
import struct
import time

OUTPUT_CAP = 33554432
FRAME_CAP = 128
GAP_NS = 2000000000
PRIVATE_DELTAS = {'item/agentMessage/delta', 'item/plan/delta',
                  'item/reasoning/summaryTextDelta', 'item/reasoning/summaryPartAdded',
                  'item/reasoning/textDelta', 'item/commandExecution/outputDelta'}
CATEGORIES = ('owned_lifecycle', 'owned_private_delta_discarded',
              'unrelated_discarded', 'authorized_rpc_reply', 'protocol_ping')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reference(path):
    return {'path': str(Path(path)), 'sha256': digest(path)}


def output_bytes(roots):
    total = 0
    for root in roots:
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs+files:
                path = Path(directory)/name
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or not (
                    stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                    raise ValueError('unadmitted output entry')
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
    return total


class Channel:
    def __init__(self, root, fixture_output, identity, projection):
        self.root, self.fixture_output = Path(root), Path(fixture_output)
        for path in (self.root, self.fixture_output):
            if not path.is_absolute() or path.resolve() != path or not path.is_dir():
                raise ValueError('literal existing channel/fixture roots required')
        if self.root.is_relative_to(self.fixture_output) or self.fixture_output.is_relative_to(self.root):
            raise ValueError('channel and fixture roots overlap')
        self.identity, self.projection = dict(identity), projection
        self.frames, self.events, self.checkpoints = [], [], []
        self.errors = [reference(p) for p in sorted(self.root.glob('error-*.json'))]
        self.categories = {key: 0 for key in CATEGORIES}
        self.methods = {}
        self.last_covered_ns = self.identity['armed_ns']

    def write(self, name, value):
        data = (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()
        return self.write_bytes(name, data)

    def write_bytes(self, name, data):
        path = self.root/name
        if output_bytes((self.root, self.fixture_output))+len(data) > OUTPUT_CAP:
            raise ValueError('combined operator output cap')
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return reference(path)

    def fields(self, kind):
        return {'schema_version': 1, 'kind': kind, **{key: self.identity[key]
            for key in ('fixture_id', 'channel_id', 'connection_id')}}

    def error(self, error, rejected_owned_notification_header=None):
        # Exception messages and notification bodies never enter error records.
        value = {
            **self.fields('ChannelError'), 'observed_ns': time.monotonic_ns(),
            'error_type': type(error).__name__, 'coverage': 'unknown'}
        if rejected_owned_notification_header is not None:
            value['rejected_owned_notification_header'] = rejected_owned_notification_header
        ref = self.write(f'error-{len(self.errors)+1:04}.json', value)
        self.errors.append(ref)

    def record(self, value, wire_bytes, authorized_reply_id=None, protocol_ping=False):
        rejected_header = None
        try:
            if len(self.frames) >= FRAME_CAP or type(wire_bytes) is not int or wire_bytes <= 0:
                raise ValueError('complete frame cap/size')
            now, wall = time.monotonic_ns(), time.time_ns()//1000000
            event, reply = None, None
            if protocol_ping:
                if value is not None:
                    raise ValueError('ping cannot carry a retained body')
                category = 'protocol_ping'
            elif not isinstance(value, dict):
                raise ValueError('native envelope object missing')
            elif 'id' in value:
                if (type(value['id']) is not int or value['id'] != authorized_reply_id or
                    not ('result' in value or 'error' in value) or
                    ('result' in value and 'error' in value)):
                    raise ValueError('unadmitted native reply')
                category, reply = 'authorized_rpc_reply', value['id']
            else:
                params = value.get('params')
                if not isinstance(value.get('method'), str) or not isinstance(params, dict):
                    raise ValueError('unclassifiable native notification')
                if params.get('threadId') != self.identity['thread_id']:
                    category = 'unrelated_discarded'
                elif value['method'] in PRIVATE_DELTAS:
                    category = 'owned_private_delta_discarded'
                else:
                    rejected_header = {
                        'method': value['method'], 'thread_id': params['threadId'],
                        'parameter_keys': sorted(params),
                        'parsed_envelope_canonical_sha256': hashlib.sha256(
                            json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
                    public = self.projection(value, self.identity['thread_id'])
                    if public is None:
                        raise ValueError('unsupported owned native lifecycle')
                    category = 'owned_lifecycle'
                    presence = public.pop('field_presence')
                    event = self.write(f'event-{len(self.events)+1:04}.json', {
                        **self.fields('NativeOwnedLifecycleEvent'),
                        'frame_index': len(self.frames)+1, 'event_sequence': len(self.events)+1,
                        'received_ms': wall, 'received_ns': now, 'notification': public,
                        'native_fields_present': presence})
                    self.events.append(event)
                    self.methods[public['method']] = self.methods.get(public['method'], 0)+1
            ref = self.write(f'frame-{len(self.frames)+1:04}.json', {
                **self.fields('ChannelFrame'), 'frame_index': len(self.frames)+1,
                'received_ms': wall, 'received_ns': now, 'wire_bytes': wire_bytes,
                'category': category, 'previous': self.frames[-1] if self.frames else None,
                'event': event, 'reply_id': reply})
            self.frames.append(ref)
            self.categories[category] += 1
        except Exception as error:
            self.error(error, rejected_owned_notification_header=rejected_header)
            raise

    def checkpoint(self, connection, buffer, started_ns, final=False):
        if self.errors or buffer or select.select([connection], [], [], 0)[0]:
            raise ValueError('partial/error/readable socket cannot be checkpointed')
        peer = dict(zip(('pid', 'uid', 'gid'), struct.unpack('3i',
            connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))))
        if peer != self.identity['peer']:
            raise ValueError('original connection peer changed')
        covered = time.monotonic_ns()
        if (type(started_ns) is not int or not self.last_covered_ns <= started_ns <= covered or
            covered-self.last_covered_ns > GAP_NS or
            len(self.checkpoints) >= (65 if final else 64)):
            raise ValueError('checkpoint gap/order/ceiling')
        ref = self.write(f'checkpoint-{len(self.checkpoints)+1:04}.json', {
            **self.fields('ChannelCheckpoint'), 'checkpoint_sequence': len(self.checkpoints)+1,
            'previous': self.checkpoints[-1] if self.checkpoints else None,
            'observed_ns': time.monotonic_ns(), 'peer': peer,
            'prefix': {'frames': list(self.frames), 'events': list(self.events),
                       'category_counts': dict(self.categories), 'event_method_counts': dict(self.methods)},
            'drain': {'started_ns': started_ns, 'covered_through_ns': covered,
                      'receive_buffer_bytes': 0, 'socket_readable': False},
            'errors': list(self.errors)})
        self.checkpoints.append(ref)
        self.last_covered_ns = covered
        return ref

    def finish(self, close_request=None):
        return self.write('channel-final.json', {**self.fields('ChannelFinal'),
            'status': 'closed' if close_request and self.checkpoints and not self.errors else 'unknown',
            'last_checkpoint': self.checkpoints[-1] if self.checkpoints else None,
            'close_request': close_request, 'closed_ns': time.monotonic_ns(),
            'errors': list(self.errors)})
