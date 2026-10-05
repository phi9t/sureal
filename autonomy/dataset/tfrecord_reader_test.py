"""Independent TFRecord envelope fixtures; no TensorFlow dependency."""
import hashlib
import io
import struct
import unittest
from pipeline.tfrecord_reader import crc32c, masked_crc32c, read_records


def fixture_crc(data):
    # Independent bit-at-a-time reference, distinct from candidate lookup table.
    value=0xffffffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value=(value>>1) ^ (0x82f63b78 if value&1 else 0)
    value ^= 0xffffffff
    return (((value>>15)|(value<<17))+0xa282ead8)&0xffffffff


def frame(payload):
    length=struct.pack('<Q',len(payload))
    return length+struct.pack('<I',fixture_crc(length))+payload+struct.pack('<I',fixture_crc(payload))


class ReaderTests(unittest.TestCase):
    def test_known_vectors_and_mask(self):
        self.assertEqual(crc32c(b''),0)
        self.assertEqual(crc32c(b'123456789'),0xe3069283)
        self.assertEqual(masked_crc32c(b''),0xa282ead8)
        for payload in [b'',b'a',bytes(range(256)),b'123456789']:
            self.assertEqual(masked_crc32c(payload),fixture_crc(payload))

    def test_records_offsets_hash_and_empty(self):
        payloads=[b'abc',b'',bytes(range(256))]
        rows=list(read_records(io.BytesIO(b''.join(frame(x) for x in payloads)),max_record_bytes=256))
        self.assertEqual([r['payload'] for r in rows],payloads)
        self.assertEqual([r['offset'] for r in rows],[0,19,35])
        self.assertEqual([r['index'] for r in rows],[0,1,2])
        self.assertEqual([r['sha256'] for r in rows],[hashlib.sha256(x).hexdigest() for x in payloads])
        self.assertEqual(list(read_records(io.BytesIO(b''),max_record_bytes=256)),[])

    def test_faults(self):
        good=frame(b'abc')
        for position in [0,8,12,15]:
            mutated=bytearray(good);mutated[position]^=1
            with self.subTest(position=position),self.assertRaises(ValueError):
                list(read_records(io.BytesIO(mutated),max_record_bytes=256))
        for length in range(1,len(good)):
            with self.subTest(length=length),self.assertRaises(ValueError):
                list(read_records(io.BytesIO(good[:length]),max_record_bytes=256))
        with self.assertRaises(ValueError):
            list(read_records(io.BytesIO(frame(b'abc')),max_record_bytes=2))
        # Oversized advertised payload must be refused before requesting it.
        class Bounded(io.BytesIO):
            def read(self,n=-1):
                if n>12:raise AssertionError('oversized allocation attempted')
                return super().read(n)
        header=struct.pack('<Q',2**40)
        with self.assertRaises(ValueError):
            list(read_records(Bounded(header+struct.pack('<I',fixture_crc(header))),max_record_bytes=256))
        for cap in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):list(read_records(io.BytesIO(b''),max_record_bytes=cap))

    def test_short_reads(self):
        class Short(io.BytesIO):
            def read(self,n=-1):return super().read(min(n,2))
        rows=list(read_records(Short(frame(b'123456789')),max_record_bytes=256))
        self.assertEqual(rows[0]['payload'],b'123456789')


if __name__=='__main__':unittest.main()
