import contextlib
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import types
import unittest
from dataclasses import fields
from pathlib import Path
from unittest import mock


GOLDEN_SOURCE_SNAPSHOT_SHA256 = "26d7ae75a8a99ed88f3e5350159faf024a632dd3deb70f403fa664b959c6fd18"


class SourceSnapshotTests(unittest.TestCase):
    def api(self):
        try:
            from evidence.source_snapshot import (
                HdfsSnapshotStore,
                LocalSnapshotStore,
                SnapshotAuthenticationError,
                SnapshotMissingError,
                archive_sources,
                file_digest,
                file_sha256,
                materialize_receipt_sources,
                materialize_source_snapshot_archive,
                require_regular_file,
                snapshot_bazel_target,
                snapshot_source_pins,
                snapshot_target_and_materialize,
                source_snapshot_store_descriptor,
                store_from_receipt,
                verify_or_materialize_receipt_sources,
                verify_receipt_sources,
            )
        except ImportError:
            self.fail("shared evidence source snapshot module must exist")
        return {
            "HdfsSnapshotStore": HdfsSnapshotStore,
            "LocalSnapshotStore": LocalSnapshotStore,
            "SnapshotAuthenticationError": SnapshotAuthenticationError,
            "SnapshotMissingError": SnapshotMissingError,
            "archive_sources": archive_sources,
            "file_digest": file_digest,
            "file_sha256": file_sha256,
            "materialize_receipt_sources": materialize_receipt_sources,
            "materialize_source_snapshot_archive": materialize_source_snapshot_archive,
            "require_regular_file": require_regular_file,
            "snapshot_bazel_target": snapshot_bazel_target,
            "snapshot_source_pins": snapshot_source_pins,
            "snapshot_target_and_materialize": snapshot_target_and_materialize,
            "source_snapshot_store_descriptor": source_snapshot_store_descriptor,
            "store_from_receipt": store_from_receipt,
            "verify_or_materialize_receipt_sources": verify_or_materialize_receipt_sources,
            "verify_receipt_sources": verify_receipt_sources,
        }

    def write_repo(self, root):
        (root / "autonomy/evidence").mkdir(parents=True)
        (root / "autonomy/evidence/source_snapshot.py").write_text("module\n")
        (root / "autonomy/evidence/source_snapshot_test.py").write_text("test\n")
        (root / "autonomy/BUILD.bazel").write_text("build\n")

    def runner_for(self, labels):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return types.SimpleNamespace(returncode=0, stdout="\n".join(labels) + "\n", stderr="")

        return run, calls

    def tar_members(self, archive_bytes):
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as reader:
            return {
                member.name: {
                    "data": reader.extractfile(member).read(),
                    "mtime": member.mtime,
                    "uid": member.uid,
                    "gid": member.gid,
                    "mode": member.mode,
                }
                for member in reader
            }

    def archive_bytes(self, members):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w", format=tarfile.PAX_FORMAT) as writer:
            for name, data in members:
                if isinstance(data, tarfile.TarInfo):
                    writer.addfile(data)
                    continue
                encoded = data if isinstance(data, bytes) else data.encode()
                info = tarfile.TarInfo(name)
                info.size = len(encoded)
                writer.addfile(info, io.BytesIO(encoded))
        return payload.getvalue()

    def hdfs_runner(self, remote, *, fail=None):
        calls = []
        fail = fail or {}

        def run(command, **kwargs):
            calls.append((command, kwargs))
            verb = command[5]
            if verb in fail:
                return types.SimpleNamespace(returncode=1, stdout="", stderr=fail[verb])
            if verb == "storage-prefix":
                return types.SimpleNamespace(returncode=0, stdout="hdfs://fixture/sureal\n", stderr="")
            if verb == "get":
                source = command[-2]
                destination = Path(command[-1])
                if source not in remote:
                    return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"FileNotFound: missing object"}')
                if destination.exists():
                    return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"Local destination already exists"}')
                destination.write_bytes(remote[source])
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            if verb == "put":
                source = Path(command[-2])
                destination = command[-1]
                if destination in remote:
                    return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"already exists"}')
                remote[destination] = source.read_bytes()
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")
            return types.SimpleNamespace(returncode=1, stdout="", stderr='{"error":"unexpected command"}')

        return run, calls

    def test_target_api_receipts_and_materializes_exact_bazel_closure_from_archive(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            (repo / "autonomy/support").mkdir()
            (repo / "autonomy/support/config.json").write_text('{"before": true}\n')
            destination = Path(temporary) / "materialized"
            labels = [
                "//autonomy:evidence/source_snapshot.py",
                "//autonomy:evidence/source_snapshot_test.py",
                "//autonomy:support/config.json",
            ]

            class MutatingStore(api["LocalSnapshotStore"]):
                def store(self, digest, data):
                    stored = super().store(digest, data)
                    (repo / "autonomy/evidence/source_snapshot.py").write_text("mutated checkout\n")
                    (repo / "autonomy/support/config.json").write_text('{"after": true}\n')
                    return stored

            store = MutatingStore(Path(temporary) / "store")
            receipt = api["snapshot_target_and_materialize"](
                "//autonomy:evidence__source_snapshot_test",
                destination,
                store=store,
                repo_root=repo,
                runner=self.runner_for(labels)[0],
            )

            self.assertEqual(receipt["schema_version"], 2)
            self.assertEqual(receipt["source_snapshot_target"], "//autonomy:evidence__source_snapshot_test")
            self.assertEqual(receipt["source_snapshot_root"], str(destination))
            self.assertEqual(
                receipt["source_snapshot_store"],
                {"schema_version": 1, "kind": "local", "root": str(store.root)},
            )
            self.assertEqual(
                list(receipt["source_pins"]),
                [
                    "autonomy/evidence/source_snapshot.py",
                    "autonomy/evidence/source_snapshot_test.py",
                    "autonomy/support/config.json",
                ],
            )
            self.assertEqual((destination / "autonomy/evidence/source_snapshot.py").read_text(), "module\n")
            self.assertEqual((destination / "autonomy/support/config.json").read_text(), '{"before": true}\n')
            self.assertEqual(api["verify_receipt_sources"](receipt, store)["source_pins"], receipt["source_pins"])

    def test_hdfs_descriptor_receipt_materializes_after_checkout_and_cache_removal(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            remote = {}
            hdfs_runner, hdfs_calls = self.hdfs_runner(remote)
            store = api["HdfsSnapshotStore"]("/local/waystone", runner=hdfs_runner)
            first_destination = Path(temporary) / "first"

            receipt = api["snapshot_target_and_materialize"](
                "//autonomy:target",
                first_destination,
                store=store,
                repo_root=repo,
                runner=self.runner_for(["//autonomy:evidence/source_snapshot.py"])[0],
            )
            shutil.rmtree(repo)
            shutil.rmtree(first_destination)

            self.assertEqual(
                receipt["source_snapshot_store"],
                {"schema_version": 1, "kind": "hdfs", "prefix": "hdfs://fixture/sureal"},
            )
            self.assertNotIn("waystone", receipt["source_snapshot_store"])
            resolved_store = api["store_from_receipt"](receipt, waystone="/local/waystone", runner=hdfs_runner)
            self.assertEqual(api["verify_receipt_sources"](receipt, resolved_store)["source_files"], 1)

            second_destination = Path(temporary) / "second"
            materialized = api["materialize_receipt_sources"](
                receipt,
                second_destination,
                waystone="/local/waystone",
                runner=hdfs_runner,
            )

            self.assertEqual(materialized["source_snapshot_root"], str(second_destination))
            self.assertEqual((second_destination / "autonomy/evidence/source_snapshot.py").read_text(), "module\n")
            self.assertGreaterEqual([call[0][5] for call in hdfs_calls].count("get"), 3)

    def test_verify_or_materialize_recovers_missing_pins_inside_existing_scaffold(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / "autonomy/detection").mkdir(parents=True)
            (repo / "autonomy/detection/worker.py").write_text("pinned\n")
            store = api["LocalSnapshotStore"](root / "store")
            archive, pins = api["archive_sources"](repo, ["autonomy/detection/worker.py"])
            digest = hashlib.sha256(archive).hexdigest()
            store.store(digest, archive)
            receipt = {
                "source_snapshot_sha256": digest,
                "source_snapshot_target": "//autonomy:fixture",
                "source_snapshot_store": str(store.root),
                "source_pins": pins,
            }
            destination = root / "materialized"
            (destination / "autonomy/research").mkdir(parents=True)
            (destination / "autonomy/research/retained.json").write_text("{}\n")

            verified = api["verify_or_materialize_receipt_sources"](receipt, destination, store)

            self.assertEqual(verified["source_snapshot_sha256"], digest)
            self.assertEqual((destination / "autonomy/detection/worker.py").read_text(), "pinned\n")
            self.assertEqual((destination / "autonomy/research/retained.json").read_text(), "{}\n")

    def test_verify_or_materialize_does_not_overwrite_changed_or_irregular_pins(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / "autonomy/detection").mkdir(parents=True)
            (repo / "autonomy/detection/worker.py").write_text("pinned\n")
            store = api["LocalSnapshotStore"](root / "store")
            archive, pins = api["archive_sources"](repo, ["autonomy/detection/worker.py"])
            digest = hashlib.sha256(archive).hexdigest()
            store.store(digest, archive)
            receipt = {
                "source_snapshot_sha256": digest,
                "source_snapshot_target": "//autonomy:fixture",
                "source_snapshot_store": str(store.root),
                "source_pins": pins,
            }
            changed = root / "changed"
            (changed / "autonomy/detection").mkdir(parents=True)
            (changed / "autonomy/detection/worker.py").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "materialized source changed"):
                api["verify_or_materialize_receipt_sources"](receipt, changed, store)
            linked = root / "linked"
            (linked / "autonomy/detection").mkdir(parents=True)
            (linked / "autonomy/detection/worker.py").symlink_to(repo / "autonomy/detection/worker.py")
            with self.assertRaisesRegex(ValueError, "materialized source missing or irregular"):
                api["verify_or_materialize_receipt_sources"](receipt, linked, store)

    def test_descriptor_resolution_validates_shape_and_never_uses_receipt_executables(self):
        api = self.api()
        digest = "0" * 64
        pins = {"autonomy/evidence/source_snapshot.py": "1" * 64}

        with self.assertRaisesRegex(ValueError, "source snapshot store descriptor"):
            api["store_from_receipt"](
                {
                    "source_snapshot_sha256": digest,
                    "source_pins": pins,
                    "source_snapshot_store": {
                        "schema_version": 1,
                        "kind": "hdfs",
                        "prefix": "hdfs://fixture/sureal",
                        "waystone": "/receipt/controlled/executable",
                    },
                },
                waystone="/local/waystone",
            )
        with self.assertRaisesRegex(ValueError, "HDFS source snapshot prefix"):
            api["store_from_receipt"](
                {
                    "source_snapshot_sha256": digest,
                    "source_pins": pins,
                    "source_snapshot_store": {
                        "schema_version": 1,
                        "kind": "hdfs",
                        "prefix": "/tmp/local-path-is-not-hdfs",
                    },
                },
                waystone="/local/waystone",
            )
        with self.assertRaisesRegex(ValueError, "source snapshot store kind"):
            api["store_from_receipt"](
                {
                    "source_snapshot_sha256": digest,
                    "source_pins": pins,
                    "source_snapshot_store": {"schema_version": 1, "kind": "shell", "prefix": "hdfs://fixture/sureal"},
                },
                waystone="/local/waystone",
            )

    def test_descriptor_fetch_propagates_missing_authentication_and_corrupt_archive_errors(self):
        api = self.api()
        archive = self.archive_bytes([("autonomy/evidence/source_snapshot.py", "module\n")])
        digest = hashlib.sha256(archive).hexdigest()
        pins = api["snapshot_source_pins"](archive)
        receipt = {
            "schema_version": 2,
            "source_snapshot_sha256": digest,
            "source_snapshot_target": "//autonomy:target",
            "source_snapshot_store": {"schema_version": 1, "kind": "hdfs", "prefix": "hdfs://fixture/sureal"},
            "source_pins": pins,
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_runner, _ = self.hdfs_runner({})
            with self.assertRaisesRegex(api["SnapshotMissingError"], "source snapshot missing"):
                api["materialize_receipt_sources"](receipt, root / "missing", waystone="/waystone", runner=missing_runner)

            auth_runner, _ = self.hdfs_runner({}, fail={"get": '{"error":"Kerberos authentication failed"}'})
            with self.assertRaisesRegex(api["SnapshotAuthenticationError"], "snapshot storage authentication failed"):
                api["materialize_receipt_sources"](receipt, root / "auth", waystone="/waystone", runner=auth_runner)

            corrupt_runner, _ = self.hdfs_runner(
                {
                    "hdfs://fixture/sureal/source-snapshots/" + digest: b"corrupt",
                }
            )
            with self.assertRaisesRegex(ValueError, "snapshot digest differs"):
                api["materialize_receipt_sources"](receipt, root / "corrupt", waystone="/waystone", runner=corrupt_runner)

    def test_archive_materialization_rejects_unsafe_members_and_preserves_destinations(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "existing"
            destination.mkdir()
            (destination / "keep.txt").write_text("keep\n")
            archive = self.archive_bytes([("autonomy/evidence/source_snapshot.py", "module\n")])
            digest = hashlib.sha256(archive).hexdigest()
            pins = api["snapshot_source_pins"](archive)

            with self.assertRaisesRegex(FileExistsError, "source snapshot destination already exists"):
                api["materialize_source_snapshot_archive"](archive, destination, digest=digest, source_pins=pins)
            self.assertEqual((destination / "keep.txt").read_text(), "keep\n")

            for member_name in ("../escape.py", "/absolute.py"):
                with self.assertRaisesRegex(ValueError, "safe snapshot member name"):
                    api["materialize_source_snapshot_archive"](
                        self.archive_bytes([(member_name, "bad\n")]),
                        Path(temporary) / ("unsafe-" + member_name.strip("/.").replace("/", "-")),
                    )

            duplicate = self.archive_bytes(
                [
                    ("autonomy/evidence/source_snapshot.py", "one\n"),
                    ("autonomy/evidence/source_snapshot.py", "two\n"),
                ]
            )
            with self.assertRaisesRegex(ValueError, "duplicate or nonregular"):
                api["materialize_source_snapshot_archive"](duplicate, Path(temporary) / "duplicate")

            link = tarfile.TarInfo("autonomy/evidence/link.py")
            link.type = tarfile.SYMTYPE
            link.linkname = "source_snapshot.py"
            with self.assertRaisesRegex(ValueError, "duplicate or nonregular"):
                api["materialize_source_snapshot_archive"](self.archive_bytes([("autonomy/evidence/link.py", link)]), Path(temporary) / "link")

            self.assertFalse((Path(temporary) / "duplicate").exists())
            self.assertFalse((Path(temporary) / "link").exists())

    def test_archive_materialization_refuses_destination_created_during_publication(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "raced"
            archive = self.archive_bytes([("autonomy/evidence/source_snapshot.py", "module\n")])
            digest = hashlib.sha256(archive).hexdigest()
            pins = api["snapshot_source_pins"](archive)
            from evidence import source_snapshot as source_snapshot_module

            original_mkdir = Path.mkdir
            original_rename = Path.rename
            competitor = {}

            def create_competitor():
                if "identity" not in competitor:
                    original_mkdir(destination)
                    competitor["identity"] = (destination.stat().st_dev, destination.stat().st_ino)

            def competing_mkdir(path, *args, **kwargs):
                if Path(path) == destination:
                    create_competitor()
                return original_mkdir(path, *args, **kwargs)

            def competing_rename(path, target):
                if Path(target) == destination:
                    create_competitor()
                return original_rename(path, target)

            stack = contextlib.ExitStack()
            stack.enter_context(mock.patch.object(Path, "mkdir", competing_mkdir))
            stack.enter_context(mock.patch.object(Path, "rename", competing_rename))
            if hasattr(source_snapshot_module, "_rename_no_replace"):
                original_publish = source_snapshot_module._rename_no_replace

                def competing_publish(path, target):
                    if Path(target) == destination:
                        create_competitor()
                    return original_publish(path, target)

                stack.enter_context(mock.patch.object(source_snapshot_module, "_rename_no_replace", competing_publish))
            with stack:
                with self.assertRaisesRegex(FileExistsError, "source snapshot destination already exists"):
                    api["materialize_source_snapshot_archive"](archive, destination, digest=digest, source_pins=pins)

            self.assertEqual((destination.stat().st_dev, destination.stat().st_ino), competitor["identity"])
            self.assertEqual(list(destination.iterdir()), [])
            self.assertEqual([path.name for path in root.iterdir() if path.name.startswith(".raced.")], [])

    def test_hdfs_storage_uploads_with_exact_readback_and_fetches_by_digest(self):
        api = self.api()
        remote = {}
        runner, calls = self.hdfs_runner(remote)
        data = b"snapshot bytes"
        digest = hashlib.sha256(data).hexdigest()
        store = api["HdfsSnapshotStore"]("/waystone", runner=runner)

        self.assertEqual(store.store(digest, data), digest)
        self.assertEqual(store.fetch(digest), data)
        self.assertEqual(
            remote,
            {
                "hdfs://fixture/sureal/source-snapshots/" + digest: data,
            },
        )
        verbs = [call[0][5] for call in calls]
        self.assertEqual(verbs, ["storage-prefix", "get", "put", "get", "get"])
        for command, kwargs in calls:
            self.assertEqual(command[:5], ["/waystone", "--error-format", "json", "--auth-source", "token-file"])
            self.assertEqual(command[5] == "put" and command[-3] == "--mkdir-parents", command[5] == "put")
            self.assertEqual(kwargs["env"]["HADOOP_CONF_DIR"], "/opt/tiger/yarn_deploy/hadoop/conf")

    def test_hdfs_storage_rejects_upload_when_exact_readback_differs(self):
        api = self.api()
        remote = {}
        runner, _ = self.hdfs_runner(remote)
        data = b"snapshot bytes"
        digest = hashlib.sha256(data).hexdigest()

        def corrupt_readback(command, **kwargs):
            result = runner(command, **kwargs)
            if command[5] == "put":
                remote[command[-1]] = b"corrupt"
            return result

        store = api["HdfsSnapshotStore"]("/waystone", runner=corrupt_readback)
        with self.assertRaisesRegex(ValueError, "snapshot digest differs after readback"):
            store.store(digest, data)

    def test_hdfs_storage_verifies_existing_digest_without_overwriting(self):
        api = self.api()
        data = b"snapshot bytes"
        digest = hashlib.sha256(data).hexdigest()
        remote = {
            "hdfs://fixture/sureal/source-snapshots/" + digest: data,
        }
        runner, calls = self.hdfs_runner(remote)
        store = api["HdfsSnapshotStore"]("/waystone", runner=runner)

        self.assertEqual(store.store(digest, data), digest)
        self.assertNotIn("put", [call[0][5] for call in calls])
        self.assertEqual(remote["hdfs://fixture/sureal/source-snapshots/" + digest], data)

    def test_hdfs_storage_fetches_snapshot_in_fresh_session_without_local_cache(self):
        api = self.api()
        data = b"snapshot bytes"
        digest = hashlib.sha256(data).hexdigest()
        remote = {
            "hdfs://fixture/sureal/source-snapshots/" + digest: data,
        }
        runner, _ = self.hdfs_runner(remote)

        first = api["HdfsSnapshotStore"]("/waystone", runner=runner)
        second = api["HdfsSnapshotStore"]("/waystone", runner=runner)

        self.assertEqual(first.fetch(digest), data)
        self.assertEqual(second.fetch(digest), data)

    def test_hdfs_storage_reports_authentication_failure_and_missing_object_distinctly(self):
        api = self.api()
        missing_runner, _ = self.hdfs_runner({})
        missing_store = api["HdfsSnapshotStore"]("/waystone", runner=missing_runner)

        with self.assertRaisesRegex(api["SnapshotMissingError"], "source snapshot missing"):
            missing_store.fetch("0" * 64)

        auth_runner, _ = self.hdfs_runner({}, fail={"get": '{"error":"Kerberos authentication failed"}'})
        auth_store = api["HdfsSnapshotStore"]("/waystone", runner=auth_runner)
        with self.assertRaisesRegex(api["SnapshotAuthenticationError"], "snapshot storage authentication failed"):
            auth_store.fetch("0" * 64)

    def test_bazel_target_snapshot_archives_exact_transitive_sources(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)
            runner, calls = self.runner_for(
                [
                    "//autonomy:BUILD.bazel",
                    "//autonomy:evidence/source_snapshot_test.py",
                    "//autonomy:evidence/source_snapshot.py",
                ]
            )
            store = api["LocalSnapshotStore"](repo / "snapshots")

            snapshot = api["snapshot_bazel_target"](
                "//autonomy:evidence__source_snapshot_test",
                store,
                repo_root=repo,
                runner=runner,
            )

            self.assertEqual(
                list(snapshot.source_pins),
                [
                    "autonomy/BUILD.bazel",
                    "autonomy/evidence/source_snapshot.py",
                    "autonomy/evidence/source_snapshot_test.py",
                ],
            )
            self.assertNotIn("archive_sha256", {field.name for field in fields(snapshot)})
            self.assertEqual(hashlib.sha256(store.fetch(snapshot.digest)).hexdigest(), snapshot.digest)
            members = self.tar_members(store.fetch(snapshot.digest))
            self.assertEqual(set(members), set(snapshot.source_pins))
            self.assertEqual(members["autonomy/evidence/source_snapshot.py"]["data"], b"module\n")
            self.assertEqual(
                calls[0][0],
                [
                    str(repo / "bazelw"),
                    "query",
                    "--output=label",
                    'kind("source file", filter("^//", labels("srcs", deps(//autonomy:evidence__source_snapshot_test)) union labels("data", deps(//autonomy:evidence__source_snapshot_test))))',
                ],
            )
            self.assertEqual(calls[0][1]["cwd"], repo)

    def test_source_snapshot_digest_matches_uncompressed_tar_golden(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)

            archive, pins = api["archive_sources"](
                repo,
                [
                    "autonomy/evidence/source_snapshot.py",
                    "autonomy/BUILD.bazel",
                ],
            )

            self.assertEqual(hashlib.sha256(archive).hexdigest(), GOLDEN_SOURCE_SNAPSHOT_SHA256)
            self.assertEqual(archive[:2], b"au")
            self.assertEqual(
                pins,
                {
                    "autonomy/BUILD.bazel": hashlib.sha256(b"build\n").hexdigest(),
                    "autonomy/evidence/source_snapshot.py": hashlib.sha256(b"module\n").hexdigest(),
                },
            )
            self.assertEqual(
                sorted(self.tar_members(archive)),
                [
                    "autonomy/BUILD.bazel",
                    "autonomy/evidence/source_snapshot.py",
                ],
            )

    def test_bazel_target_snapshot_ignores_rule_labels_after_expanding_data(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)
            (repo / "autonomy/support").mkdir()
            (repo / "autonomy/support/config.json").write_text("{}\n")
            calls = []

            def run(command, **kwargs):
                calls.append((command, kwargs))
                labels = (
                    [
                        "//autonomy:evidence/source_snapshot.py",
                        "//autonomy:support/config.json",
                    ]
                    if 'kind("source file",' in command[-1]
                    else [
                        "//autonomy:evidence/source_snapshot.py",
                        "//autonomy:support_files",
                        "//autonomy:support/config.json",
                    ]
                )
                return types.SimpleNamespace(returncode=0, stdout="\n".join(labels) + "\n", stderr="")

            snapshot = api["snapshot_bazel_target"]("//autonomy:target", api["LocalSnapshotStore"](repo / "snapshots"), repo_root=repo, runner=run)

            self.assertEqual(
                list(snapshot.source_pins),
                [
                    "autonomy/evidence/source_snapshot.py",
                    "autonomy/support/config.json",
                ],
            )
            self.assertNotIn("autonomy/support_files", snapshot.source_pins)
            self.assertIn('kind("source file",', calls[0][0][-1])

    def test_external_bazel_source_labels_are_excluded_from_repository_snapshot(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](repo / "snapshots")
            runner, _ = self.runner_for(
                [
                    "@bazel_tools//tools/python:tool.py",
                    "//autonomy:evidence/source_snapshot.py",
                ]
            )

            snapshot = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=runner)

            self.assertEqual(
                snapshot.source_pins,
                {
                    "autonomy/evidence/source_snapshot.py": hashlib.sha256(b"module\n").hexdigest(),
                },
            )

    def test_archive_is_deterministic_across_file_order_timestamp_and_ownership(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)
            labels = [
                "//autonomy:evidence/source_snapshot.py",
                "//autonomy:BUILD.bazel",
                "//autonomy:evidence/source_snapshot_test.py",
            ]
            store = api["LocalSnapshotStore"](repo / "snapshots")
            one = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(labels)[0])
            for path in repo.rglob("*"):
                if path.is_file():
                    os.utime(path, (123456789, 123456789))
            two = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(reversed(labels))[0])

            self.assertEqual(one.digest, two.digest)
            self.assertEqual(store.fetch(one.digest), store.fetch(two.digest))
            for member in self.tar_members(store.fetch(one.digest)).values():
                self.assertEqual(member["mtime"], 0)
                self.assertEqual(member["uid"], 0)
                self.assertEqual(member["gid"], 0)
                self.assertEqual(member["mode"], 0o444)

    def test_changed_added_or_removed_closure_source_changes_digest(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](repo / "snapshots")
            labels = ["//autonomy:BUILD.bazel", "//autonomy:evidence/source_snapshot.py"]
            original = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(labels)[0])

            (repo / "autonomy/evidence/source_snapshot.py").write_text("changed\n")
            changed = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(labels)[0])
            self.assertNotEqual(original.digest, changed.digest)

            added = api["snapshot_bazel_target"](
                "//autonomy:target",
                store,
                repo_root=repo,
                runner=self.runner_for([*labels, "//autonomy:evidence/source_snapshot_test.py"])[0],
            )
            self.assertNotEqual(changed.digest, added.digest)

            removed = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(labels[:1])[0])
            self.assertNotEqual(changed.digest, removed.digest)

    def test_local_storage_fetches_by_digest_and_refuses_corrupt_or_missing_snapshots(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            data = b"snapshot bytes"
            digest = hashlib.sha256(data).hexdigest()

            self.assertEqual(store.store(digest, data), digest)
            self.assertEqual(store.fetch(digest), data)

            (Path(temporary) / "store" / digest).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "snapshot digest differs"):
                store.fetch(digest)
            with self.assertRaisesRegex(FileNotFoundError, "source snapshot missing"):
                store.fetch("0" * 64)

    def test_local_storage_uses_unique_temp_name_in_store_directory(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            data = b"snapshot bytes"
            digest = hashlib.sha256(data).hexdigest()
            store.root.mkdir()
            stale_tmp = store.root / (digest + ".tmp")
            stale_tmp.write_bytes(b"stale interrupted write")

            self.assertEqual(store.store(digest, data), digest)
            self.assertEqual(store.fetch(digest), data)
            self.assertEqual(stale_tmp.read_bytes(), b"stale interrupted write")

    def test_local_storage_refuses_snapshot_key_symlink_before_reading(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            digest = "1" * 64
            store.root.mkdir()
            (store.root / digest).symlink_to(Path(temporary) / "missing")

            with self.assertRaisesRegex(ValueError, "regular snapshot object required"):
                store.fetch(digest)

    def test_local_storage_refuses_snapshot_key_symlink_before_writing(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            data = b"snapshot bytes"
            digest = hashlib.sha256(data).hexdigest()
            store.root.mkdir()
            (store.root / digest).symlink_to(Path(temporary) / "missing")

            with self.assertRaisesRegex(ValueError, "regular snapshot object required"):
                store.store(digest, data)

    def test_receipt_verification_uses_snapshot_not_working_tree(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            labels = ["//autonomy:BUILD.bazel", "//autonomy:evidence/source_snapshot.py"]
            snapshot = api["snapshot_bazel_target"]("//autonomy:target", store, repo_root=repo, runner=self.runner_for(labels)[0])
            receipt = {
                "source_snapshot_sha256": snapshot.digest,
                "source_snapshot_target": snapshot.target,
                "source_pins": snapshot.source_pins,
            }

            for path in repo.rglob("*"):
                if path.is_file():
                    path.unlink()

            verified = api["verify_receipt_sources"](receipt, store)
            self.assertEqual(verified["source_snapshot_sha256"], snapshot.digest)
            self.assertEqual(verified["source_pins"], snapshot.source_pins)

    def test_receipt_verification_accepts_only_current_source_pin_schema(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            snapshot = api["snapshot_bazel_target"](
                "//autonomy:target",
                store,
                repo_root=repo,
                runner=self.runner_for(["//autonomy:evidence/source_snapshot.py"])[0],
            )
            valid_receipt = {
                "source_snapshot_sha256": snapshot.digest,
                "source_pins": snapshot.source_pins,
            }

            self.assertEqual(api["verify_receipt_sources"](valid_receipt, store)["source_pins"], snapshot.source_pins)
            with self.assertRaisesRegex(ValueError, "receipt source snapshot digest required"):
                api["verify_receipt_sources"](
                    {
                        "source_snapshot": {"sha256": snapshot.digest},
                        "source_pins": snapshot.source_pins,
                    },
                    store,
                )
            for legacy_field in ("source_sha256", "source_hashes"):
                with self.assertRaisesRegex(ValueError, "receipt source pins required"):
                    api["verify_receipt_sources"](
                        {
                            "source_snapshot_sha256": snapshot.digest,
                            legacy_field: snapshot.source_pins,
                        },
                        store,
                    )
            with self.assertRaisesRegex(ValueError, "sha256 digest required"):
                api["verify_receipt_sources"](
                    {
                        "source_snapshot_sha256": snapshot.digest,
                        "source_pins": {
                            "autonomy/evidence/source_snapshot.py": {
                                "sha256": snapshot.source_pins["autonomy/evidence/source_snapshot.py"],
                            },
                        },
                    },
                    store,
                )

    def test_receipt_verification_rejects_altered_snapshot_member_union(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            snapshot = api["snapshot_bazel_target"](
                "//autonomy:target",
                store,
                repo_root=repo,
                runner=self.runner_for(["//autonomy:BUILD.bazel", "//autonomy:evidence/source_snapshot.py"])[0],
            )
            receipt = {
                "source_snapshot_sha256": snapshot.digest,
                "source_snapshot_target": snapshot.target,
                "source_pins": {"autonomy/BUILD.bazel": snapshot.source_pins["autonomy/BUILD.bazel"]},
            }

            with self.assertRaisesRegex(ValueError, "receipt source pins differ from snapshot"):
                api["verify_receipt_sources"](receipt, store)

    def test_receipt_verification_fails_for_corrupt_or_missing_snapshot(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            snapshot = api["snapshot_bazel_target"](
                "//autonomy:target",
                store,
                repo_root=repo,
                runner=self.runner_for(["//autonomy:evidence/source_snapshot.py"])[0],
            )
            receipt = {
                "source_snapshot_sha256": snapshot.digest,
                "source_snapshot_target": snapshot.target,
                "source_pins": snapshot.source_pins,
            }

            (Path(temporary) / "store" / snapshot.digest).write_bytes(b"not the snapshot")
            with self.assertRaisesRegex(ValueError, "snapshot digest differs"):
                api["verify_receipt_sources"](receipt, store)

            (Path(temporary) / "store" / snapshot.digest).unlink()
            with self.assertRaisesRegex(FileNotFoundError, "source snapshot missing"):
                api["verify_receipt_sources"](receipt, store)

    def test_file_digest_and_regular_file_check_reject_symlinks(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_text("contents")
            link = root / "link.txt"
            link.symlink_to(source)
            nested = root / "nested"
            nested.symlink_to(root, target_is_directory=True)

            self.assertEqual(api["file_sha256"](source), hashlib.sha256(b"contents").hexdigest())
            self.assertEqual(api["file_digest"](source, "md5"), hashlib.md5(b"contents").hexdigest())
            self.assertEqual(api["require_regular_file"](source), source)
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["require_regular_file"](link)
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["file_sha256"](nested / "source.txt")


if __name__ == "__main__":
    unittest.main()
