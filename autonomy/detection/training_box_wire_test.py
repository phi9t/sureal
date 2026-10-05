"""Bounded byte-stream framing for one immutable native source at a time."""
import base64
import hashlib
import io
import json
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from detection.training_box_wire import stream_training_box_sources


class ShortReads(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 7) if size >= 0 else 7)


class NativeBoxWireTests(unittest.TestCase):
    def table(self, scene='a'):
        return pa.table({'key.segment_context_name': [scene], 'key.frame_timestamp_micros': [123],
                         'key.laser_object_id': ['actor'], '[LiDARBoxComponent].type': [1],
                         '[LiDARBoxComponent].box.center.x': [0.], '[LiDARBoxComponent].box.center.y': [0.],
                         '[LiDARBoxComponent].box.center.z': [12.], '[LiDARBoxComponent].box.size.x': [6.],
                         '[LiDARBoxComponent].box.size.y': [3.], '[LiDARBoxComponent].box.size.z': [2.],
                         '[LiDARBoxComponent].box.heading': [.1]})

    def fixture(self, tables=None):
        tables = [('a', self.table()), ('b', self.table('b').slice(0, 0))] if tables is None else tables
        inventory, payloads = [], []
        for scene, table in tables:
            buffer = pa.BufferOutputStream()
            pq.write_table(table, buffer)
            payload = buffer.getvalue().to_pybytes()
            inventory.append({'scene': scene, 'bytes': len(payload), 'native_rows': table.num_rows,
                              'sha256': hashlib.sha256(payload).hexdigest(),
                              'md5_base64': base64.b64encode(hashlib.md5(payload).digest()).decode()})
            payloads.append(payload)
        return inventory, payloads

    def packet(self, inventory, payloads, footer=True):
        data = b''.join(json.dumps(source).encode() + b'\n' + payload
                        for source, payload in zip(inventory, payloads))
        if footer:
            data += json.dumps({'kind': 'end', 'sources': len(inventory)}).encode() + b'\n'
        return data

    def consume(self, packet, inventory, acknowledge=None, reader=io.BytesIO):
        result = []
        for source in stream_training_box_sources(reader(packet), inventory=inventory,
                                                  acknowledge=acknowledge):
            result.append((source['scene'], source['expected_rows'], list(source['rows'])))
        return result

    def test_short_reads_native_columns_empty_source_and_acknowledgement(self):
        inventory, payloads = self.fixture()
        acknowledgements = []
        result = self.consume(self.packet(inventory, payloads), inventory,
                              acknowledge=acknowledgements.append, reader=ShortReads)
        self.assertEqual([(scene, rows) for scene, rows, _ in result], [('a', 1), ('b', 0)])
        self.assertEqual(result[0][2][0]['[LiDARBoxComponent].box.center.z'], 12.)
        self.assertEqual(result[1][2], [])
        self.assertEqual(acknowledgements, [
            {'scene': 'a', 'sha256': inventory[0]['sha256'], 'native_rows': 1, 'status': 'consumed'},
            {'scene': 'b', 'sha256': inventory[1]['sha256'], 'native_rows': 0, 'status': 'consumed'}])

    def test_corrupt_bytes_or_wrong_md5_refused_before_acknowledgement(self):
        inventory, payloads = self.fixture()
        bad = list(payloads)
        bad[0] = bytes([payloads[0][0] ^ 1]) + payloads[0][1:]
        acknowledgements = []
        with self.assertRaises(ValueError):
            self.consume(self.packet(inventory, bad), inventory, acknowledgements.append)
        self.assertEqual(acknowledgements, [])
        wrong_sha = [dict(source) for source in inventory]
        wrong_sha[0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.consume(self.packet(wrong_sha, payloads), wrong_sha)
        inventory[0]['md5_base64'] = base64.b64encode(b'wrong-checksum!!').decode()
        with self.assertRaises(ValueError):
            self.consume(self.packet(inventory, payloads), inventory)

    def test_wrong_order_header_identity_or_declared_size_refused(self):
        inventory, payloads = self.fixture()
        for mutation in ['order', 'size', 'scene', 'extra']:
            headers = [dict(source) for source in inventory]
            if mutation == 'order':
                headers = headers[::-1]
            elif mutation == 'size':
                headers[0]['bytes'] += 1
            elif mutation == 'scene':
                headers[0]['scene'] = 'heldout'
            else:
                headers[0]['extra'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.consume(self.packet(headers, payloads), inventory)

    def test_oversized_duplicate_key_and_truncated_header_refused(self):
        inventory, payloads = self.fixture()
        header = json.dumps(inventory[0]).encode()
        valid = self.packet(inventory, payloads)
        duplicate = b'{"scene":"ignored",' + header[1:] + b'\n' + valid[len(header) + 1:]
        for packet in [b' ' * 5000 + valid, duplicate, header]:
            with self.subTest(packet=packet[:60]), self.assertRaises(ValueError):
                self.consume(packet, inventory)

    def test_body_truncation_missing_footer_and_trailing_data_refused(self):
        inventory, payloads = self.fixture()
        valid = self.packet(inventory, payloads)
        partial_body = json.dumps(inventory[0]).encode() + b'\n' + payloads[0][:-1]
        for packet in [partial_body, self.packet(inventory, payloads, footer=False), valid + b'extra']:
            with self.subTest(packet=packet[-30:]), self.assertRaises(ValueError):
                self.consume(packet, inventory)

    def test_bad_native_schema_and_row_inventory_refused(self):
        inventory, payloads = self.fixture([('a', self.table().drop(['[LiDARBoxComponent].box.heading']))])
        with self.assertRaises(ValueError):
            self.consume(self.packet(inventory, payloads), inventory)
        inventory, payloads = self.fixture()
        inventory[0]['native_rows'] = 2
        with self.assertRaises(ValueError):
            self.consume(self.packet(inventory, payloads), inventory)

    def test_rows_cannot_be_skipped_before_next_source_ack(self):
        inventory, payloads = self.fixture()
        acknowledgements = []
        sources = stream_training_box_sources(io.BytesIO(self.packet(inventory, payloads)),
                                              inventory=inventory, acknowledge=acknowledgements.append)
        next(sources)
        with self.assertRaises(ValueError):
            next(sources)
        self.assertEqual(acknowledgements, [])

    def test_duplicate_or_malformed_inventory_refused(self):
        inventory, payloads = self.fixture()
        for bad_inventory in [inventory + [inventory[0]], [], [dict(inventory[0], bytes=True)],
                              [dict(inventory[0], native_rows=-1)], [dict(inventory[0], sha256='bad')]]:
            with self.subTest(inventory=bad_inventory), self.assertRaises(ValueError):
                self.consume(self.packet(inventory, payloads), bad_inventory)

    def test_producer_and_reference_consume_separate_verified_wire_passes(self):
        from detection.training_box_sources import training_box_statistics_from_sources
        from detection.training_box_reference import verify_training_box_distributions
        inventory, payloads = self.fixture()
        packet = self.packet(inventory, payloads)
        membership = {s: {'official_split': 'training', 'research_splits': ['train']} for s in ['a', 'b']}
        producer_ack, reference_ack = [], []
        producer = training_box_statistics_from_sources(
            stream_training_box_sources(io.BytesIO(packet), inventory=inventory, acknowledge=producer_ack.append),
            membership=membership, expected_scenes=['a', 'b'])
        self.assertEqual(producer['classes']['1']['median_length_width_height_center_z'], [6., 3., 2., 12.])
        reference = verify_training_box_distributions(
            stream_training_box_sources(io.BytesIO(packet), inventory=inventory, acknowledge=reference_ack.append),
            reported=producer, membership=membership, expected_scenes=['a', 'b'])
        self.assertEqual(reference['completed_sources'], 2)
        self.assertEqual(reference['native_rows'], 1)
        self.assertEqual(reference['eligible_box_rows'], 1)
        self.assertEqual(len(producer_ack), 2)
        self.assertEqual(len(reference_ack), 2)


if __name__ == '__main__':
    unittest.main()
