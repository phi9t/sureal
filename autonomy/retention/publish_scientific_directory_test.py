import json
import tempfile
import types
import unittest
from pathlib import Path

from evidence.source_snapshot import file_sha256

REAL_ARCHIVE_PUT_PREFLIGHT_FOUND_ZERO = (
    "Found 0 items in hdfs://harunava/user/tiger/waystone/sureal/runs/"
    "perception-closed-scientific-processing/cohort16-baseline-fit20261002a-dec4ce2778a4401d8b42734f397823d5/"
    "63f21a24760fe02f61129273b3f2a7bb1ff466b0eacd95fe53f28ff162167561/archive.tar.gz\n"
)


class FakeWaystone:
    def __init__(self, root, *, existing_suffixes=()):
        self.root = Path(root)
        self.objects = {}
        self.commands = []
        self.existing_suffixes = tuple(existing_suffixes)

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
        if uri in self.objects or any(uri.endswith(suffix) for suffix in self.existing_suffixes):
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


class ScientificDirectoryPublisherTests(unittest.TestCase):
    def make_payload(self, root, case="cohort16-baseline-fit20261002a"):
        working = Path(root) / "scientific-processing"
        payload = working / case
        (payload / "nested").mkdir(parents=True)
        (payload / "nested" / "checkpoint.pt").write_bytes(b"checkpoint")
        (payload / "metrics.json").write_text('{"loss": 1.25}\n')
        return working, payload

    def test_release_happy_path_records_required_stages_and_unlinks_only_planned_files(self):
        from retention.publish_scientific_directory import REQUIRED_RELEASE_STAGES, DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            sibling = working / "balanced16-native-v2"
            sibling.mkdir()
            (sibling / "keep.pt").write_bytes(b"protected")
            evidence = Path(directory) / "evidence"

            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=evidence,
                release=True,
                scientific_processing=working,
                waystone=FakeWaystone(directory),
                archive_runner=DirectArchiveRunner(),
                host_source_admitter=fake_host_admitter,
                identifier="cohort16-baseline-fit20261002a-test",
            )

            chunk_stages = [check["stage"] for chunk in receipt["chunks"] for check in chunk["checks"]]
            receipt_stages = [check["stage"] for check in receipt["stage_receipts"]]
            self.assertEqual(chunk_stages + receipt_stages, REQUIRED_RELEASE_STAGES)
            self.assertFalse((payload / "nested" / "checkpoint.pt").exists())
            self.assertFalse((payload / "metrics.json").exists())
            self.assertTrue((sibling / "keep.pt").exists())
            release_receipt = evidence / "hdfs-retention-cohort16-baseline-fit20261002a-test" / "release-completed.json"
            self.assertEqual(json.loads(release_receipt.read_text())["released_count"], 2)

    def test_without_release_stops_after_rehydrate_and_leaves_source_tree(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            evidence = Path(directory) / "evidence"

            receipt = publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=evidence,
                release=False,
                scientific_processing=working,
                waystone=FakeWaystone(directory),
                archive_runner=DirectArchiveRunner(),
                host_source_admitter=fake_host_admitter,
                identifier="dry-run",
            )

            self.assertEqual(
                [check["stage"] for chunk in receipt["chunks"] for check in chunk["checks"]],
                ["create-live", "archive-put", "archive-get", "manifest-put", "manifest-get", "verify-live", "rehydrate-live"],
            )
            self.assertEqual(receipt["stage_receipts"], [])
            self.assertTrue((payload / "nested" / "checkpoint.pt").exists())
            self.assertFalse((evidence / "hdfs-retention-dry-run" / "release-completed.json").exists())

    def test_refuses_protected_names(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            for case in [
                "balanced16-native-v2",
                "resource-retention-balanced16-sustained-baseline-controller20261003a-shared-abc",
            ]:
                working, payload = self.make_payload(directory, case=case)
                with self.assertRaisesRegex(ValueError, "protected"):
                    publish(
                        case=case,
                        root=payload,
                        hdfs_namespace="perception-closed-scientific-processing",
                        evidence=Path(directory) / ("evidence-" + case),
                        scientific_processing=working,
                        waystone=FakeWaystone(directory),
                        archive_runner=DirectArchiveRunner(),
                        host_source_admitter=fake_host_admitter,
                        identifier=case + "-test",
                    )

    def test_refuses_root_outside_scientific_processing(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working = Path(directory) / "scientific-processing"
            working.mkdir()
            payload = Path(directory) / "elsewhere" / "cohort16-baseline-fit20261002a"
            payload.mkdir(parents=True)
            (payload / "file.bin").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "direct child"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence",
                    scientific_processing=working,
                    waystone=FakeWaystone(directory),
                    archive_runner=DirectArchiveRunner(),
                    host_source_admitter=fake_host_admitter,
                    identifier="outside-test",
                )

    def test_refuses_to_overwrite_existing_hdfs_objects(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            with self.assertRaises(FileExistsError):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence",
                    scientific_processing=working,
                    waystone=FakeWaystone(directory, existing_suffixes=("archive.tar.gz",)),
                    archive_runner=DirectArchiveRunner(),
                    host_source_admitter=fake_host_admitter,
                    identifier="overwrite-test",
                )
            self.assertTrue((payload / "nested" / "checkpoint.pt").exists())

    def test_release_plan_escape_is_rejected_before_any_unlink(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            outside = Path(directory) / "outside.bin"
            outside.write_bytes(b"outside")
            inside = payload / "metrics.json"

            def bad_release_plan(root, publication):
                del publication
                return [
                    {
                        "path": "metrics.json",
                        "bytes": inside.stat().st_size,
                        "sha256": file_sha256(inside),
                        "local_path": str(inside),
                        "archive_hdfs_uri": "hdfs://test/inside/archive.tar.gz",
                    },
                    {
                        "path": "outside.bin",
                        "bytes": outside.stat().st_size,
                        "sha256": file_sha256(outside),
                        "local_path": str(outside),
                        "archive_hdfs_uri": "hdfs://test/outside/archive.tar.gz",
                    },
                ]

            with self.assertRaisesRegex(ValueError, "escapes"):
                publish(
                    case=payload.name,
                    root=payload,
                    hdfs_namespace="perception-closed-scientific-processing",
                    evidence=Path(directory) / "evidence",
                    release=True,
                    scientific_processing=working,
                    waystone=FakeWaystone(directory),
                    archive_runner=DirectArchiveRunner(),
                    host_source_admitter=fake_host_admitter,
                    release_planner=bad_release_plan,
                    identifier="escape-test",
                )
            self.assertTrue(inside.exists())
            self.assertTrue(outside.exists())

    def test_release_uses_independent_runner_before_release_plan(self):
        from retention.publish_scientific_directory import DirectArchiveRunner, publish

        with tempfile.TemporaryDirectory() as directory:
            working, payload = self.make_payload(directory)
            calls = []

            def independent_runner(source_root, chunks, output_dir, *, max_bytes):
                del chunks, max_bytes
                calls.append((Path(source_root), Path(output_dir).name))
                return {"stage": "independent", "command": ["independent"], "exit_code": 0}

            def release_planner(root, publication):
                self.assertEqual([receipt["stage"] for receipt in publication["stage_receipts"]], ["independent"])
                return []

            publish(
                case=payload.name,
                root=payload,
                hdfs_namespace="perception-closed-scientific-processing",
                evidence=Path(directory) / "evidence",
                release=True,
                scientific_processing=working,
                waystone=FakeWaystone(directory),
                archive_runner=DirectArchiveRunner(),
                independent_runner=independent_runner,
                host_source_admitter=fake_host_admitter,
                release_planner=release_planner,
                identifier="independent-runner-test",
            )

            self.assertEqual(calls, [(payload, "independent")])

    def test_waystone_put_new_treats_found_zero_preflight_as_absent(self):
        from retention.publish_scientific_directory import WaystoneClient

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "archive.tar.gz"
            source.write_bytes(b"archive")
            calls = []

            def runner(command, **kwargs):
                del kwargs
                calls.append(command)
                if command[-2:] == ["ls", "hdfs://example/archive.tar.gz"]:
                    return types.SimpleNamespace(returncode=0, stdout=REAL_ARCHIVE_PUT_PREFLIGHT_FOUND_ZERO, stderr="")
                if command[-4:-2] == ["put", "--mkdir-parents"]:
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                return types.SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            receipt = WaystoneClient(cli="/waystone", runner=runner, tool_pins={}).put_new(
                source,
                "hdfs://example/archive.tar.gz",
                "archive-put",
                Path(directory) / "evidence",
            )

            self.assertEqual(receipt["stage"], "archive-put")
            self.assertEqual([command for command in calls if command[-4:-2] == ["put", "--mkdir-parents"]], [receipt["command"]])

    def test_waystone_put_new_refuses_found_one_preflight(self):
        from retention.publish_scientific_directory import WaystoneClient

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "archive.tar.gz"
            source.write_bytes(b"archive")
            uri = "hdfs://example/archive.tar.gz"
            calls = []

            def runner(command, **kwargs):
                del kwargs
                calls.append(command)
                if command[-2:] == ["ls", uri]:
                    return types.SimpleNamespace(returncode=0, stdout="Found 1 items in hdfs://example/archive.tar.gz\nhdfs://example/archive.tar.gz\n", stderr="")
                if command[-4:-2] == ["put", "--mkdir-parents"]:
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                return types.SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            with self.assertRaisesRegex(FileExistsError, "HDFS object already exists"):
                WaystoneClient(cli="/waystone", runner=runner, tool_pins={}).put_new(
                    source,
                    uri,
                    "archive-put",
                    Path(directory) / "evidence",
                )

            self.assertEqual([command for command in calls if command[-4:-2] == ["put", "--mkdir-parents"]], [])

    def test_waystone_put_new_treats_nonzero_not_found_as_absent(self):
        from retention.publish_scientific_directory import WaystoneClient

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "archive.tar.gz"
            source.write_bytes(b"archive")

            def runner(command, **kwargs):
                del kwargs
                if command[-2:] == ["ls", "hdfs://example/archive.tar.gz"]:
                    return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"FileNotFound: object does not exist"}')
                if command[-4:-2] == ["put", "--mkdir-parents"]:
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                return types.SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            receipt = WaystoneClient(cli="/waystone", runner=runner, tool_pins={}).put_new(
                source,
                "hdfs://example/archive.tar.gz",
                "archive-put",
                Path(directory) / "evidence",
            )

            self.assertEqual(receipt["stage"], "archive-put")

    def test_waystone_put_new_raises_on_auth_error_with_missing_text(self):
        from retention.publish_scientific_directory import WaystoneClient

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "archive.tar.gz"
            source.write_bytes(b"archive")

            def runner(command, **kwargs):
                del kwargs
                if command[-2:] == ["ls", "hdfs://example/archive.tar.gz"]:
                    return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"auth token missing"}')
                if command[-4:-2] == ["put", "--mkdir-parents"]:
                    return types.SimpleNamespace(returncode=0, stdout="", stderr="")
                return types.SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

            with self.assertRaisesRegex(RuntimeError, "could not prove HDFS object absence"):
                WaystoneClient(cli="/waystone", runner=runner, tool_pins={}).put_new(
                    source,
                    "hdfs://example/archive.tar.gz",
                    "archive-put",
                    Path(directory) / "evidence",
                )


if __name__ == "__main__":
    unittest.main()
