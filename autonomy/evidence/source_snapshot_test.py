import hashlib
import io
import json
import os
import tarfile
import tempfile
import types
import unittest
from pathlib import Path


class SourceSnapshotTests(unittest.TestCase):
    def api(self):
        try:
            from evidence.source_snapshot import (
                LocalSnapshotStore,
                file_sha256,
                require_regular_file,
                snapshot_bazel_target,
                snapshot_source_pins,
                verify_receipt_sources,
            )
        except ImportError:
            self.fail("shared evidence source snapshot module must exist")
        return {
            "LocalSnapshotStore": LocalSnapshotStore,
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
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as reader:
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
            self.assertEqual(snapshot.archive_sha256, snapshot.digest)
            members = self.tar_members(store.fetch(snapshot.digest))
            self.assertEqual(set(members), set(snapshot.source_pins))
            self.assertEqual(members["autonomy/evidence/source_snapshot.py"]["data"], b"module\n")
            self.assertEqual(
                calls[0][0],
                [
                    str(repo / "bazelw"),
                    "query",
                    "--output=label",
                    'kind("source", deps(//autonomy:evidence__source_snapshot_test))',
                ],
            )
            self.assertEqual(calls[0][1]["cwd"], repo)

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
