import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256


class FakeWaystone:
    def __init__(self):
        self.objects = {}
        self.commands = []

    def layout_profile(self, evidence_dir):
        self.commands.append(("layout-profile", str(evidence_dir)))
        return {
            "project": "sureal",
            "project_root": "hdfs://test/sureal",
            "paths": {"runs": "hdfs://test/sureal/runs"},
        }

    def authenticated_read(self, uri, evidence_dir):
        self.commands.append(("ls", uri, str(evidence_dir)))
        return {"stage": "authenticated-read", "command": ["waystone", "ls", uri], "exit_code": 0}

    def put_new(self, source, uri, stage, evidence_dir):
        self.commands.append(("put", uri, str(source), str(evidence_dir)))
        if uri in self.objects:
            raise FileExistsError("HDFS object already exists: " + uri)
        self.objects[uri] = Path(source).read_bytes()
        return {"stage": stage, "command": ["waystone", "put", str(source), uri], "exit_code": 0}

    def get(self, uri, destination, stage, evidence_dir):
        self.commands.append(("get", uri, str(destination), str(evidence_dir)))
        Path(destination).write_bytes(self.objects[uri])
        return {"stage": stage, "command": ["waystone", "get", uri, str(destination)], "exit_code": 0}


def fake_host_admitter(receipt_path, current_package, destination):
    destination = Path(destination)
    destination.mkdir(parents=True)
    marker = destination / "marker.py"
    marker.write_text("admitted\n")
    return {
        "schema_version": 2,
        "source_snapshot_root": str(destination.parent),
        "source_pins": {"autonomy/marker.py": file_sha256(marker)},
    }, Path(current_package)


class SymlinkAuditPublisherTests(unittest.TestCase):
    def make_audit(self, root):
        working = Path(root) / "scientific-processing"
        payload = working / "motion-current-geometry-audit-v3"
        (payload / "red" / "mutants").mkdir(parents=True)
        (payload / "green").mkdir()
        (payload / "green" / "report.json").write_text('{"ok": true}\n')
        (payload / "red" / "mutants" / "frame.bin").symlink_to("/source/training/frame.bin")
        return working, payload

    def test_archive_preserves_symlink_members_and_readback_listing_matches_source(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            waystone = FakeWaystone()
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence",
                preserve_symlinks=True,
                readback=True,
                write_receipt=True,
                scientific_processing=working,
                waystone=waystone,
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-test",
            )

            self.assertEqual(receipt["source_listing"], receipt["readback_listing"])
            self.assertIn(
                {
                    "path": "red/mutants/frame.bin",
                    "kind": "symlink",
                    "link_text": "/source/training/frame.bin",
                },
                receipt["source_listing"],
            )
            archive_bytes = waystone.objects[receipt["archive_hdfs_uri"]]
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
                member = archive.getmember("red/mutants/frame.bin")
                self.assertTrue(member.issym())
                self.assertEqual(member.linkname, "/source/training/frame.bin")
            self.assertTrue((payload / "red" / "mutants" / "frame.bin").is_symlink())

    def test_move_to_renames_same_filesystem_and_verifies_listing_again(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            destination = Path(directory) / "retired-audits" / payload.name
            destination.parent.mkdir()
            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-motion",
                evidence=Path(directory) / "evidence",
                preserve_symlinks=True,
                readback=True,
                write_receipt=True,
                move_to=destination,
                scientific_processing=working,
                waystone=FakeWaystone(),
                host_source_admitter=fake_host_admitter,
                identifier="motion-audit-move",
            )

            self.assertFalse(payload.exists())
            self.assertEqual(json.loads((Path(directory) / "evidence" / "hdfs-retention-motion-audit-move" / "move-completed.json").read_text())["moved_to"], str(destination))
            self.assertEqual(receipt["source_listing"], receipt["moved_listing"])
            self.assertEqual((destination / "red" / "mutants" / "frame.bin").readlink(), Path("/source/training/frame.bin"))

    def test_refuses_cross_device_move_without_deleting_source(self):
        from retention.publish_symlink_audit import publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_audit(directory)
            destination = Path(directory) / "retired-audits" / payload.name
            destination.parent.mkdir()
            with self.assertRaisesRegex(OSError, "cross-device"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-motion",
                    evidence=Path(directory) / "evidence",
                    preserve_symlinks=True,
                    readback=True,
                    write_receipt=True,
                    move_to=destination,
                    scientific_processing=working,
                    waystone=FakeWaystone(),
                    host_source_admitter=fake_host_admitter,
                    identifier="motion-audit-cross-device",
                    same_device=lambda source, target: False,
                )
            self.assertTrue(payload.exists())
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
