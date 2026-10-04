"""Raw export must agree with the physical rootfs; fields alone are not provenance."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

try:
    from audit_support.build import check_export_archive
except ImportError:
    check_export_archive=None


class ExportTests(unittest.TestCase):
    def test_actual_export_content_mode_and_member_union_are_reopened(self):
        self.assertIsNotNone(check_export_archive,"Independent export/rootfs oracle absent")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"rootfs";root.mkdir()
            (root/"file").write_bytes(b"raw")
            (root/"file").chmod(0o644)
            archive=Path(temp)/"export.tar"
            with tarfile.open(archive,"w") as out:
                info=tarfile.TarInfo("file");info.mode=0o644;info.size=3
                out.addfile(info,io.BytesIO(b"raw"))
            self.assertEqual(check_export_archive(archive,root),1)
            (root/"file").write_bytes(b"bad")
            with self.assertRaises(ValueError):
                check_export_archive(archive,root)
            (root/"file").write_bytes(b"raw")
            (root/"extra").write_text("hidden")
            with self.assertRaises(ValueError):
                check_export_archive(archive,root)


if __name__=="__main__":
    unittest.main()
