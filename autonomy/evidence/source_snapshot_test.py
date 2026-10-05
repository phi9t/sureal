import hashlib
import io
import json
import os
import tarfile
import tempfile
import types
import unittest
from dataclasses import fields
from pathlib import Path


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
                file_sha256,
                require_regular_file,
                snapshot_bazel_target,
                snapshot_source_pins,
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
            "file_sha256": file_sha256,
            "require_regular_file": require_regular_file,
            "snapshot_bazel_target": snapshot_bazel_target,
            "snapshot_source_pins": snapshot_source_pins,
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
            self.assertEqual(api["require_regular_file"](source), source)
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["require_regular_file"](link)
            with self.assertRaisesRegex(ValueError, "regular non-symlinked file required"):
                api["file_sha256"](nested / "source.txt")


if __name__ == "__main__":
    unittest.main()
