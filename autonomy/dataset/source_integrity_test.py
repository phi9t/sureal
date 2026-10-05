import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from dataset.source_integrity import verify_source


class SourceIntegrityTests(unittest.TestCase):
    def test_exact_source_and_mutated_digest_or_size(self):
        data = b'native-source-fixture'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'source'; path.write_bytes(data)
            expected = {'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                        'md5_base64': base64.b64encode(hashlib.md5(data).digest()).decode()}
            self.assertEqual(verify_source(path, **expected), expected)
            for key, value in [('size_bytes', len(data)+1), ('sha256', '0'*64),
                               ('md5_base64', base64.b64encode(b'0'*16).decode()),
                               ('size_bytes', True), ('sha256', 'bad'), ('md5_base64', 'bad')]:
                with self.subTest(key=key,value=value):
                    bad = dict(expected); bad[key] = value
                    with self.assertRaises(ValueError): verify_source(path, **bad)
            path.write_bytes(b'other-source-fixture')
            with self.assertRaises(ValueError): verify_source(path, **expected)

    def test_symlinks_and_nonregular_sources_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'source'; path.write_bytes(b'x')
            link = Path(tmp)/'link'; link.symlink_to(path)
            expected = {'size_bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest(),
                        'md5_base64': base64.b64encode(hashlib.md5(b'x').digest()).decode()}
            for source in (link, Path(tmp), Path(tmp)/'missing'):
                with self.subTest(source=source):
                    with self.assertRaises(ValueError): verify_source(source, **expected)


if __name__ == '__main__': unittest.main()
