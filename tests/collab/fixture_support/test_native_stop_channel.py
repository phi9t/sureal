"""Public component controls; never native/live milestone evidence."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest

BASE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('fixture_operator', BASE/'native_stop_fixture.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class ChannelControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.output, self.channel = root/'fixture', root/'channel'
        self.output.mkdir()
        self.channel.mkdir()

    def capture(self):
        spec = importlib.util.spec_from_file_location('capture', BASE/'native_stop_channel.py')
        self.assertTrue(Path(spec.origin).exists(), 'continuous channel source is not implemented')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        peer = {'pid': os.getpid(), 'uid': os.getuid(), 'gid': os.getgid()}
        identity = {'fixture_id': 'component-1', 'channel_id': 'channel-1',
                    'connection_id': 'connection-1', 'thread_id': 'owned',
                    'armed_ns': time.monotonic_ns(), 'peer': peer}
        return module.Channel(self.channel, self.output, identity,
                              fixture.public_owned_notification), left, right

    def event(self):
        return {'method': 'item/started', 'params': {'threadId': 'owned',
                'turnId': 'turn', 'startedAtMs': 1791150058587,
                'item': {'id': 'item', 'type': 'commandExecution',
                'status': 'inProgress', 'source': 'userShell', 'cwd': '/owned',
                'command': '/public/fixture', 'processId': None, 'exitCode': None,
                'aggregatedOutput': 'PRIVATE'}}}

    def test_all_complete_frames_form_exact_private_safe_hash_chain(self):
        cap, _, _ = self.capture()
        cap.record(self.event(), 123)
        cap.record({'method': 'item/reasoning/textDelta',
                    'params': {'threadId': 'owned', 'delta': 'PRIVATE'}}, 81)
        cap.record({'method': 'item/started', 'params':
                    {'threadId': 'unrelated', 'secret': 'PRIVATE'}}, 42)
        cap.record({'id': 7, 'result': {}}, 21, authorized_reply_id=7)
        cap.record(None, 4, protocol_ping=True)
        frames = [json.loads(p.read_text()) for p in sorted(self.channel.glob('frame-*.json'))]
        self.assertEqual([f['frame_index'] for f in frames], [1, 2, 3, 4, 5])
        self.assertEqual([f['category'] for f in frames], ['owned_lifecycle',
            'owned_private_delta_discarded', 'unrelated_discarded',
            'authorized_rpc_reply', 'protocol_ping'])
        self.assertIsNone(frames[0]['previous'])
        for n in range(1, 5):
            self.assertEqual(frames[n]['previous'], fixture.reference(
                self.channel/f'frame-{n:04}.json'))
        event = json.loads(fixture.reopen(frames[0]['event']).read_text())
        self.assertEqual(event['notification']['params']['item']['cwd'], '/owned')
        self.assertTrue(event['native_fields_present']['item.processId'])
        self.assertNotIn('PRIVATE', ''.join(p.read_text() for p in self.channel.iterdir()))

    def test_unknown_owned_tool_and_unadmitted_reply_refuse_with_retained_gap(self):
        for bad in [{'method': 'item/mcpToolCall/progress',
                     'params': {'threadId': 'owned', 'message': 'PRIVATE'}},
                    {'id': 999, 'result': {}}]:
            with self.subTest(bad=bad):
                cap, _, _ = self.capture()
                with self.assertRaises(ValueError):
                    cap.record(bad, 123)
                self.assertTrue(list(self.channel.glob('error-*.json')))
                self.assertFalse(list(self.channel.glob('frame-*.json')))

    def test_rejected_owned_notification_retains_safe_actionable_header(self):
        cap, _, _ = self.capture()
        rejected = {'method': 'thread/unrecognizedLifecycle', 'params':
                    {'threadId': 'owned', 'privateReasoning': 'PRIVATE_CONTENT',
                     'content': 'PRIVATE_CONTENT'}}
        with self.assertRaisesRegex(ValueError, 'unsupported owned native lifecycle'):
            cap.record(rejected, 123)
        error = json.loads(next(self.channel.glob('error-*.json')).read_text())
        header = error['rejected_owned_notification_header']
        self.assertEqual(header['method'], rejected['method'])
        self.assertEqual(header['thread_id'], 'owned')
        self.assertEqual(header['parameter_keys'], ['content', 'privateReasoning', 'threadId'])
        expected = hashlib.sha256(json.dumps(rejected, sort_keys=True,
                    separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(header['parsed_envelope_canonical_sha256'], expected)
        self.assertEqual(error['coverage'], 'unknown')
        self.assertFalse(list(self.channel.glob('frame-*.json')))
        self.assertFalse(list(self.channel.glob('event-*.json')))
        self.assertNotIn('PRIVATE_CONTENT', ''.join(p.read_text() for p in self.channel.iterdir()))

    def test_checkpoint_requires_actual_drained_socket_and_chain_prefix(self):
        cap, left, right = self.capture()
        cap.record(self.event(), 123)
        started = time.monotonic_ns()
        ref = cap.checkpoint(left, b'', started)
        value = json.loads(fixture.reopen(ref).read_text())
        self.assertEqual(len(value['prefix']['frames']), 1)
        self.assertEqual(value['prefix']['category_counts']['owned_lifecycle'], 1)
        self.assertEqual(value['drain']['receive_buffer_bytes'], 0)
        self.assertFalse(value['drain']['socket_readable'])
        self.assertGreaterEqual(value['drain']['covered_through_ns'], started)
        right.sendall(b'unread')
        with self.assertRaises(ValueError):
            cap.checkpoint(left, b'', time.monotonic_ns())

    def test_partial_buffer_or_dead_peer_cannot_get_checkpoint(self):
        cap, left, right = self.capture()
        with self.assertRaises(ValueError):
            cap.checkpoint(left, b'partial', time.monotonic_ns())
        right.close()
        with self.assertRaises(ValueError):
            cap.checkpoint(left, b'', time.monotonic_ns())

    def test_combined_output_cap_and_frame_ceiling_are_literal(self):
        cap, _, _ = self.capture()
        with (self.output/'existing').open('wb') as stream:
            stream.truncate(33554432)
        with self.assertRaises(ValueError):
            cap.record(None, 4, protocol_ping=True)
        (self.output/'existing').unlink()
        for _ in range(128):
            cap.record(None, 4, protocol_ping=True)
        with self.assertRaises(ValueError):
            cap.record(None, 4, protocol_ping=True)

    def test_checkpoint_gap_is_not_retimed(self):
        from unittest.mock import patch
        cap, left, _ = self.capture()
        late = cap.last_covered_ns+2000000001
        with patch.object(time, 'monotonic_ns', return_value=late):
            with self.assertRaises(ValueError):
                cap.checkpoint(left, b'', late)

    def test_wire_counts_reply_and_lifecycle_at_receive_boundary_once(self):
        import struct
        cap, left, _ = self.capture()
        wire = fixture.Wire.__new__(fixture.Wire)
        wire.connection, wire.channel = left, cap
        wire.timeout, wire.deadline, wire.sequence = .1, time.monotonic()+.1, 7
        wire.pending_reply_id = 7
        wire.send = lambda *args: None
        def frame(value):
            body = json.dumps(value).encode()
            return (b'\x81'+bytes([len(body)]) if len(body) < 126 else
                    b'\x81\x7e'+struct.pack('!H', len(body)))+body
        wire.buffer = frame(self.event())+frame({'id': 7, 'result': {}})
        wire.receive()
        wire.receive()
        self.assertEqual(len(cap.frames), 2)
        self.assertEqual(cap.categories['owned_lifecycle'], 1)
        self.assertEqual(cap.categories['authorized_rpc_reply'], 1)
        self.assertFalse(wire.buffer)

    def test_passive_replayed_reply_is_not_an_authorized_rpc(self):
        cap, left, _ = self.capture()
        wire = fixture.Wire.__new__(fixture.Wire)
        wire.connection, wire.channel = left, cap
        wire.timeout, wire.deadline, wire.sequence = .1, time.monotonic()+.1, 7
        wire.pending_reply_id = None
        body = json.dumps({'id': 7, 'result': {}}).encode()
        wire.buffer = b'\x81'+bytes([len(body)])+body
        with self.assertRaises(ValueError):
            wire.receive()

    def test_final_missing_close_or_prior_error_stays_unknown(self):
        cap, _, _ = self.capture()
        final = json.loads(fixture.reopen(cap.finish()).read_text())
        self.assertEqual(final['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
