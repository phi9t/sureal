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
RETAINED_FIXTURES = Path(__file__).with_name("testdata") / "retained_source_snapshots"


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
                is_regular_file,
                materialize_receipt_sources,
                materialize_source_snapshot_archive,
                require_regular_file,
                snapshot_bazel_target,
                snapshot_source_pins,
                snapshot_target_and_materialize,
                source_snapshot_store_descriptor,
                store_from_receipt,
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
            "is_regular_file": is_regular_file,
            "materialize_receipt_sources": materialize_receipt_sources,
            "materialize_source_snapshot_archive": materialize_source_snapshot_archive,
            "require_regular_file": require_regular_file,
            "snapshot_bazel_target": snapshot_bazel_target,
            "snapshot_source_pins": snapshot_source_pins,
            "snapshot_target_and_materialize": snapshot_target_and_materialize,
            "source_snapshot_store_descriptor": source_snapshot_store_descriptor,
            "store_from_receipt": store_from_receipt,
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

    def snapshot_blob_key(self, digest):
        return "artifacts/source-snapshots/" + digest

    def local_blob_path(self, store, digest):
        return Path(store.root) / "artifacts" / "source-snapshots" / digest

    def install_layout_waystone(self, root, project_root="hdfs://harunava/user/tiger/waystone/sureal"):
        script = Path(root) / "waystone"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "if 'layout-profile' not in sys.argv:\n"
            "    raise SystemExit(2)\n"
            "print(json.dumps({\n"
            "    'schema_version': 1,\n"
            "    'project': 'sureal',\n"
            "    'storage_root': 'hdfs://harunava/user/tiger/waystone',\n"
            "    'project_root': '"
            + project_root.rstrip("/")
            + "',\n"
            "}))\n"
        )
        script.chmod(0o755)
        return script

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
                {"kind": "local", "root": str(store.root)},
            )
            self.assertEqual(
                receipt["source_snapshot_blob"],
                {
                    "key": self.snapshot_blob_key(receipt["source_snapshot_sha256"]),
                    "sha256": receipt["source_snapshot_sha256"],
                    "bytes": receipt["source_snapshot_archive_bytes"],
                },
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

    def test_descriptor_receipt_materializes_after_checkout_and_cache_removal(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            self.write_repo(repo)
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
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
                {"kind": "local", "root": str(store.root)},
            )
            self.assertEqual(receipt["source_snapshot_blob"]["key"], self.snapshot_blob_key(receipt["source_snapshot_sha256"]))
            resolved_store = api["store_from_receipt"](receipt)
            self.assertEqual(api["verify_receipt_sources"](receipt, resolved_store)["source_files"], 1)

            second_destination = Path(temporary) / "second"
            materialized = api["materialize_receipt_sources"](
                receipt,
                second_destination,
            )

            self.assertEqual(materialized["source_snapshot_root"], str(second_destination))
            self.assertEqual((second_destination / "autonomy/evidence/source_snapshot.py").read_text(), "module\n")

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
        with self.assertRaisesRegex(ValueError, "blob store descriptor kind"):
            api["store_from_receipt"](
                {
                    "source_snapshot_sha256": digest,
                    "source_pins": pins,
                    "source_snapshot_store": {"schema_version": 1, "kind": "shell", "prefix": "hdfs://fixture/sureal"},
                },
                waystone="/local/waystone",
            )

    def test_descriptor_fetch_propagates_missing_and_corrupt_archive_errors(self):
        api = self.api()
        archive = self.archive_bytes([("autonomy/evidence/source_snapshot.py", "module\n")])
        digest = hashlib.sha256(archive).hexdigest()
        pins = api["snapshot_source_pins"](archive)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = {
                "schema_version": 2,
                "source_snapshot_sha256": digest,
                "source_snapshot_target": "//autonomy:target",
                "source_snapshot_store": {"kind": "local", "root": str(root / "store")},
                "source_snapshot_blob": {"key": self.snapshot_blob_key(digest), "sha256": digest, "bytes": len(archive)},
                "source_pins": pins,
            }
            with self.assertRaisesRegex(api["SnapshotMissingError"], "source snapshot missing"):
                api["materialize_receipt_sources"](receipt, root / "missing")

            corrupt_store = api["LocalSnapshotStore"](root / "store")
            corrupt_store.store(digest, archive)
            self.local_blob_path(corrupt_store, digest).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "snapshot digest differs"):
                api["materialize_receipt_sources"](receipt, root / "corrupt")

    def test_retained_source_snapshot_receipts_keep_resolving(self):
        api = self.api()
        schema1_publication = json.loads((RETAINED_FIXTURES / "schema1" / "receipt.json").read_text())
        schema1 = dict(schema1_publication["resource_source_pins"])
        schema2_run = json.loads((RETAINED_FIXTURES / "schema2" / "run.json").read_text())
        schema2 = dict(schema2_run["source_hashes"])

        self.assertEqual(schema1["schema_version"], 1)
        self.assertIsInstance(schema1["source_snapshot_store"], str)
        self.assertEqual(schema2["schema_version"], 2)
        self.assertEqual(schema2["source_snapshot_store"]["kind"], "hdfs")

        with tempfile.TemporaryDirectory() as temporary:
            schema1_store = Path(temporary) / "schema1-store"
            schema2_store = Path(temporary) / "schema2-store"
            shutil.copytree(RETAINED_FIXTURES / "schema1" / "store", schema1_store)
            shutil.copytree(RETAINED_FIXTURES / "schema2" / "store", schema2_store)

            fake_waystone = self.install_layout_waystone(temporary)
            legacy_hdfs_store = api["store_from_receipt"](
                schema2,
                waystone=fake_waystone,
                tool_pins={str(fake_waystone): api["file_sha256"](fake_waystone)},
            )
            self.assertEqual(
                api["source_snapshot_store_descriptor"](legacy_hdfs_store),
                {"kind": "waystone", "project": "sureal"},
            )

            schema1_fixture = dict(schema1)
            schema1_fixture["source_snapshot_store"] = str(schema1_store)
            schema1_verified = api["verify_receipt_sources"](
                schema1_fixture,
                api["store_from_receipt"](schema1_fixture),
            )
            self.assertEqual(schema1_verified["source_files"], len(schema1["source_pins"]))
            self.assertEqual(schema1_verified["source_snapshot_sha256"], schema1["source_snapshot_sha256"])

            schema2_fixture = dict(schema2)
            schema2_fixture["source_snapshot_store"] = {
                "kind": "local",
                "root": str(schema2_store),
            }
            schema2_verified = api["verify_receipt_sources"](
                schema2_fixture,
                api["store_from_receipt"](schema2_fixture),
            )
            self.assertEqual(schema2_verified["source_files"], len(schema2["source_pins"]))
            self.assertEqual(schema2_verified["source_snapshot_sha256"], schema2["source_snapshot_sha256"])

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

    def test_local_snapshot_store_writes_source_snapshots_under_the_blob_key(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            data = b"snapshot bytes"
            digest = hashlib.sha256(data).hexdigest()
            store = api["LocalSnapshotStore"](Path(temporary) / "store")

            self.assertEqual(store.store(digest, data), digest)
            self.assertEqual(store.fetch(digest), data)
            self.assertEqual(self.local_blob_path(store, digest).read_bytes(), data)
            self.assertFalse((Path(temporary) / "store" / digest).exists())
            self.assertEqual(store.store(digest, data), digest)

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

            self.local_blob_path(store, digest).write_bytes(b"changed")
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
            blob_parent = store.root / "artifacts" / "source-snapshots"
            blob_parent.mkdir(parents=True)
            stale_tmp = blob_parent / (digest + ".tmp")
            stale_tmp.write_bytes(b"stale interrupted write")

            self.assertEqual(store.store(digest, data), digest)
            self.assertEqual(store.fetch(digest), data)
            self.assertEqual(stale_tmp.read_bytes(), b"stale interrupted write")

    def test_local_storage_refuses_snapshot_key_symlink_before_reading(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            digest = "1" * 64
            blob_parent = store.root / "artifacts" / "source-snapshots"
            blob_parent.mkdir(parents=True)
            (blob_parent / digest).symlink_to(Path(temporary) / "missing")

            with self.assertRaisesRegex(ValueError, "regular snapshot object required"):
                store.fetch(digest)

    def test_local_storage_refuses_snapshot_key_symlink_before_writing(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temporary:
            store = api["LocalSnapshotStore"](Path(temporary) / "store")
            data = b"snapshot bytes"
            digest = hashlib.sha256(data).hexdigest()
            blob_parent = store.root / "artifacts" / "source-snapshots"
            blob_parent.mkdir(parents=True)
            (blob_parent / digest).symlink_to(Path(temporary) / "missing")

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

            self.local_blob_path(store, snapshot.digest).write_bytes(b"not the snapshot")
            with self.assertRaisesRegex(ValueError, "snapshot digest differs"):
                api["verify_receipt_sources"](receipt, store)

            self.local_blob_path(store, snapshot.digest).unlink()
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
            self.assertTrue(api["is_regular_file"](source))
            self.assertFalse(api["is_regular_file"](link))
            with mock.patch("evidence.source_snapshot.require_regular_file", side_effect=OSError("unreadable")):
                self.assertFalse(api["is_regular_file"](source))
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["require_regular_file"](link)
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["file_sha256"](nested / "source.txt")


if __name__ == "__main__":
    unittest.main()
