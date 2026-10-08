"""Rootfs identities cover content and symlink/mode changes, not markers."""
import tempfile
import unittest
from pathlib import Path
from insula.runtime_identity import rootfs_identity, verify_rootfs

class RuntimeIdentityTests(unittest.TestCase):
    def test_mutation_and_symlink_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'python').write_bytes(b'original')
            (root / 'link').symlink_to('python')
            expected = rootfs_identity(root)
            verify_rootfs(root, expected)
            (root / 'python').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_rootfs(root, expected)
            (root / 'python').write_bytes(b'original')
            (root / 'link').unlink()
            (root / 'link').symlink_to('/host/python')
            with self.assertRaises(ValueError):
                verify_rootfs(root, expected)

    def test_missing_rootfs_and_mode_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / 'python'
            p.write_bytes(b'x')
            expected = rootfs_identity(root)
            p.chmod(0o755)
            with self.assertRaises(ValueError):
                verify_rootfs(root, expected)
            with self.assertRaises(ValueError):
                verify_rootfs(root / 'missing', expected)

if __name__ == '__main__':
    unittest.main()
