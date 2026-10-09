import hashlib
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

from blob_store.core import (
    BlobStore,
    Conflict,
    LEGACY_WAYSTONE_PROJECT_ROOT,
    LocalFileBlobAdapter,
    Missing,
    Unauthenticated,
    Unavailable,
    WaystoneBlobAdapter,
    blob_adapter_from_descriptor,
    blob_key_from_uri,
    blob_store_descriptor,
)


FAKE_WAYSTONE = r"""#!/usr/bin/env python3
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote


OPTIONS_WITH_VALUES = {
    "--auth-source",
    "--command-timeout-secs",
    "--error-format",
    "--output",
    "--project",
    "--progress",
    "--retry-backoff-ms",
    "--transfer-retries",
}
FLAG_OPTIONS = {
    "--json",
    "--mkdir-parents",
    "--no-save-token",
    "--no-verify",
    "--overwrite",
    "--refresh-token",
    "--verify-md5",
}


def parse(argv):
    options = {}
    flags = set()
    positional = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in OPTIONS_WITH_VALUES:
            options[token] = argv[index + 1]
            index += 2
        elif token in FLAG_OPTIONS:
            flags.add(token)
            index += 1
        else:
            positional.append(token)
            index += 1
    return options, flags, positional


def object_path(uri):
    return Path(os.environ["FAKE_WAYSTONE_REMOTE"]) / quote(uri, safe="")


def append_log(verb, argv, options, flags, positional):
    record = {
        "verb": verb,
        "argv": argv,
        "options": options,
        "flags": sorted(flags),
        "positional": positional,
    }
    with Path(os.environ["FAKE_WAYSTONE_LOG"]).open("a") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def emit_error(message, exit_code, error_class=None):
    stderr_prefix = os.environ.get("FAKE_WAYSTONE_STDERR_PREFIX")
    if stderr_prefix:
        print(stderr_prefix, file=sys.stderr)
    payload = {
        "schema_version": 1,
        "type": "error",
        "exit_code": exit_code,
        "message": message,
    }
    if error_class:
        payload["class"] = error_class
    print(json.dumps(payload, sort_keys=True), file=sys.stderr)
    raise SystemExit(exit_code)


def fail_auth():
    emit_error("Kerberos token expired: secret stderr", 10, "auth")


def fail_missing():
    emit_error("file not found: secret stderr", 44)


def fail_conflict():
    emit_error("already exists: secret stderr", 49)


def hang_with_child():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    marker = Path(os.environ["FAKE_WAYSTONE_CHILD_PID"])
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import signal, sys, time; "
                "from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "Path(sys.argv[1]).write_text(str(__import__('os').getpid())); "
                "time.sleep(60)"
            ),
            str(marker),
        ]
    )
    Path(os.environ["FAKE_WAYSTONE_PARENT_PID"]).write_text(str(os.getpid()))
    while child.poll() is None:
        time.sleep(1)
    raise SystemExit(child.returncode or 0)


def main():
    options, flags, positional = parse(sys.argv[1:])
    if not positional:
        print('{"error":"missing verb"}', file=sys.stderr)
        raise SystemExit(2)
    verb = positional[0]
    append_log(verb, sys.argv[1:], options, flags, positional[1:])
    auth_fail_verbs = set(os.environ.get("FAKE_WAYSTONE_AUTH_FAIL_VERBS", "ls,get,put").split(","))
    if os.environ.get("FAKE_WAYSTONE_AUTH_FAIL") == "1" and verb in auth_fail_verbs:
        fail_auth()
    forced_class = os.environ.get("FAKE_WAYSTONE_ERROR_CLASS")
    forced_verbs = set(os.environ.get("FAKE_WAYSTONE_ERROR_VERBS", "ls,get,put").split(","))
    if forced_class and verb in forced_verbs:
        exit_code = int(os.environ.get("FAKE_WAYSTONE_ERROR_EXIT", "12"))
        message = os.environ.get("FAKE_WAYSTONE_ERROR_MESSAGE", "structured secret stderr")
        emit_error(message, exit_code, forced_class)
    if os.environ.get("FAKE_WAYSTONE_RAW_STDERR") and verb in forced_verbs:
        print(os.environ["FAKE_WAYSTONE_RAW_STDERR"], file=sys.stderr)
        raise SystemExit(int(os.environ.get("FAKE_WAYSTONE_ERROR_EXIT", "12")))
    if os.environ.get("FAKE_WAYSTONE_HANG_VERB") == verb:
        hang_with_child()

    storage_root = os.environ.get("FAKE_WAYSTONE_STORAGE_ROOT", "hdfs://fixture/storage/")
    project = options.get("--project", "sureal")
    project_root = storage_root.rstrip("/") + "/" + project + "/"
    if verb == "layout-profile":
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "profile": "fake",
                    "project": project,
                    "storage_root": storage_root,
                    "project_root": project_root,
                    "paths": {
                        "artifacts": project_root + "artifacts/",
                        "checkpoints": project_root + "checkpoints/",
                        "datasets": project_root + "datasets/",
                        "runs": project_root + "runs/",
                        "tmp": project_root + "tmp/",
                    },
                },
                sort_keys=True,
            )
        )
        return
    if verb == "put":
        source = Path(positional[-2])
        uri = positional[-1]
        destination = object_path(uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            fail_conflict()
        shutil.copyfile(source, destination)
        return
    if verb == "get":
        uri = positional[-2]
        destination = Path(positional[-1])
        source = object_path(uri)
        if not source.exists():
            fail_missing()
        shutil.copyfile(source, destination)
        return
    if verb == "ls":
        uri = positional[-1]
        source = object_path(uri)
        if not source.exists():
            fail_missing()
        size = source.stat().st_size
        print(
            json.dumps(
                {
                    "path": uri,
                    "type": "file",
                    "bytes": size,
                    "entries": [{"path": uri, "kind": "file", "size": size}],
                },
                sort_keys=True,
            )
        )
        return
    emit_error("unexpected verb", 3, "usage")


if __name__ == "__main__":
    main()
"""


class WaystoneAdapterTests(unittest.TestCase):
    def install_fake_waystone(self, root):
        script = Path(root) / "waystone"
        script.write_text(FAKE_WAYSTONE)
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def fake_environment(self, root):
        remote = Path(root) / "remote"
        remote.mkdir()
        return {
            "FAKE_WAYSTONE_REMOTE": str(remote),
            "FAKE_WAYSTONE_LOG": str(Path(root) / "waystone.jsonl"),
        }

    def with_environment(self, values):
        class Environment:
            def __enter__(self_nonlocal):
                self_nonlocal.original = {key: os.environ.get(key) for key in values}
                os.environ.update(values)

            def __exit__(self_nonlocal, exc_type, exc, traceback):
                for key, value in self_nonlocal.original.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        return Environment()

    def sha256(self, path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            digest.update(stream.read())
        return digest.hexdigest()

    def write_file(self, root, name, data):
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def log_records(self, root):
        log = Path(root) / "waystone.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()]

    def test_waystone_adapter_uses_layout_profile_and_real_subprocess_storage_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                    key_prefix="tmp/blob-store-offline/run-20261009",
                )
                store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                source = self.write_file(root, "source.bin", b"offline waystone bytes")
                expected_sha = hashlib.sha256(b"offline waystone bytes").hexdigest()
                key = "runs/offline/run-20261009/output/blob.bin"

                result = store.put(key, source)
                destination = root / "downloaded.bin"
                store.get(key, destination, expected_sha)

            self.assertEqual(result, {"key": key, "sha256": expected_sha, "bytes": len(b"offline waystone bytes")})
            self.assertEqual(destination.read_bytes(), b"offline waystone bytes")
            self.assertEqual(blob_store_descriptor(adapter), {"kind": "waystone", "project": "sureal"})
            records = self.log_records(root)
            self.assertEqual(records[0]["verb"], "layout-profile")
            self.assertEqual(records[0]["options"]["--project"], "sureal")
            self.assertIn("--json", records[0]["flags"])
            storage_records = [record for record in records if record["verb"] in {"put", "get", "ls"}]
            self.assertTrue(storage_records)
            for record in storage_records:
                self.assertEqual(record["options"]["--auth-source"], "token-file")
                self.assertIn("hdfs://fixture/storage/sureal/", " ".join(record["argv"]))

    def test_descriptor_factory_accepts_new_and_legacy_descriptors_and_maps_absolute_uris(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            local_root = root / "local-store"
            with self.with_environment(env):
                local = blob_adapter_from_descriptor({"kind": "local", "root": str(local_root)})
                waystone = blob_adapter_from_descriptor(
                    {"kind": "waystone", "project": "sureal"},
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                legacy = blob_adapter_from_descriptor(
                    {"schema_version": 1, "kind": "hdfs", "prefix": "hdfs://fixture/storage/sureal"},
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )

                self.assertIsInstance(local, LocalFileBlobAdapter)
                self.assertEqual(blob_store_descriptor(local), {"kind": "local", "root": str(local_root)})
                self.assertEqual(blob_store_descriptor(waystone), {"kind": "waystone", "project": "sureal"})
                self.assertEqual(
                    blob_key_from_uri("hdfs://fixture/storage/sureal/runs/legacy/run-1/output/blob.bin", waystone),
                    "runs/legacy/run-1/output/blob.bin",
                )
                self.assertEqual(
                    blob_key_from_uri(
                        "hdfs://fixture/storage/sureal/artifacts/source-snapshots/" + "a" * 64,
                        legacy,
                    ),
                    "artifacts/source-snapshots/" + "a" * 64,
                )
                self.assertEqual(blob_key_from_uri("runs/already/run-1/output/blob.bin", waystone), "runs/already/run-1/output/blob.bin")

            with self.assertRaises(ValueError):
                blob_adapter_from_descriptor(
                    {"kind": "waystone", "project": "sureal", "waystone": "/receipt-controlled/executable"},
                    command_prefix=[str(fake)],
                )
            with self.with_environment(env):
                with self.assertRaises(ValueError):
                    blob_adapter_from_descriptor(
                        {"schema_version": 1, "kind": "hdfs", "prefix": "hdfs://fixture/storage/legacy-sureal"},
                        command_prefix=[str(fake)],
                        tool_pins={str(fake): self.sha256(fake)},
                    )

    def test_legacy_hdfs_descriptor_uri_to_key_translation_is_offline(self):
        missing_waystone = Path("/definitely/missing/waystone")
        digest = "a" * 64
        uri = LEGACY_WAYSTONE_PROJECT_ROOT + "/artifacts/source-snapshots/" + digest

        key = blob_key_from_uri(
            uri,
            {"schema_version": 1, "kind": "hdfs", "prefix": LEGACY_WAYSTONE_PROJECT_ROOT},
            command_prefix=[str(missing_waystone)],
        )

        self.assertEqual(key, "artifacts/source-snapshots/" + digest)
        with self.assertRaisesRegex(ValueError, "legacy project URI"):
            blob_key_from_uri(
                "hdfs://harunava/user/tiger/waystone/sureal-other/artifacts/source-snapshots/" + digest,
                {"schema_version": 1, "kind": "hdfs", "prefix": LEGACY_WAYSTONE_PROJECT_ROOT},
                command_prefix=[str(missing_waystone)],
            )

    def test_layout_profile_authentication_failures_are_public_for_uri_and_legacy_factory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env.update(
                {
                    "FAKE_WAYSTONE_AUTH_FAIL": "1",
                    "FAKE_WAYSTONE_AUTH_FAIL_VERBS": "layout-profile",
                }
            )
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                with self.assertRaises(Unauthenticated) as by_uri:
                    blob_key_from_uri("hdfs://fixture/storage/sureal/runs/auth/blob.bin", adapter)
                self.assertIn("refresh-hdfs-auth.sh", str(by_uri.exception))

                with self.assertRaises(Unauthenticated) as by_factory:
                    blob_adapter_from_descriptor(
                        {"schema_version": 1, "kind": "hdfs", "prefix": "hdfs://fixture/storage/sureal"},
                        command_prefix=[str(fake)],
                        tool_pins={str(fake): self.sha256(fake)},
                    )
                self.assertIn("refresh-hdfs-auth.sh", str(by_factory.exception))

    def test_layout_profile_transient_failures_are_retried_before_public_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env.update(
                {
                    "FAKE_WAYSTONE_ERROR_CLASS": "external",
                    "FAKE_WAYSTONE_ERROR_VERBS": "layout-profile",
                    "FAKE_WAYSTONE_ERROR_MESSAGE": "layout transient secret stderr",
                }
            )
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                with self.assertRaises(Unavailable) as caught:
                    blob_key_from_uri("hdfs://fixture/storage/sureal/runs/retry/blob.bin", adapter)

            self.assertNotIn("secret stderr", str(caught.exception))
            records = self.log_records(root)
            self.assertEqual([record["verb"] for record in records].count("layout-profile"), 3)

    def test_metadata_operations_have_a_sane_deadline_floor(self):
        class RecordingAdapter:
            def __init__(self):
                self.deadlines = []

            def _upload_blob(self, key, source, context):
                raise AssertionError("not used")

            def _download_blob(self, key, destination, context):
                self.deadlines.append(("download", context.deadline_at - context.clock()))
                Path(destination).write_bytes(b"x")

            def _blob_size(self, key, context):
                self.deadlines.append(("size", context.deadline_at - context.clock()))
                return 1

            def _blob_exists(self, key, context):
                self.deadlines.append(("exists", context.deadline_at - context.clock()))
                return True

        with tempfile.TemporaryDirectory() as directory:
            adapter = RecordingAdapter()
            store = BlobStore(
                adapter,
                deadline_base_seconds=5.0,
                minimum_throughput_bytes_per_second=1024 * 1024,
                backoff_seconds=(),
                clock=lambda: 100.0,
            )
            store.exists("runs/metadata/blob.bin")
            store.get("runs/metadata/blob.bin", Path(directory) / "blob.bin", hashlib.sha256(b"x").hexdigest(), expected_bytes=1)

        metadata_deadlines = [seconds for kind, seconds in adapter.deadlines if kind in {"exists", "size"}]
        self.assertGreaterEqual(min(metadata_deadlines), 30.0)

    def test_missing_authentication_and_conflict_classification_do_not_leak_backend_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                    key_prefix="tmp/blob-store-offline/classification",
                )
                store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                with self.assertRaises(Missing) as missing:
                    store.get("runs/missing/run-20261009/output/blob.bin", root / "missing.bin", "0" * 64)
                self.assertNotIn("FileNotFound", str(missing.exception))
                self.assertNotIn("secret stderr", str(missing.exception))

                first = self.write_file(root, "first.bin", b"first")
                second = self.write_file(root, "second.bin", b"second")
                key = "runs/conflict/run-20261009/output/blob.bin"
                store.put(key, first)
                with self.assertRaises(Conflict) as conflict:
                    store.put(key, second)
                self.assertNotIn("already exists", str(conflict.exception))
                self.assertNotIn("secret stderr", str(conflict.exception))

            auth_env = dict(env)
            auth_env["FAKE_WAYSTONE_AUTH_FAIL"] = "1"
            with self.with_environment(auth_env):
                auth_adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                auth_store = BlobStore(auth_adapter, backoff_seconds=(0.0, 0.0))
                with self.assertRaises(Unauthenticated) as auth:
                    auth_store.exists("runs/auth/run-20261009/output/blob.bin")
                self.assertIn("refresh-hdfs-auth.sh", str(auth.exception))
                self.assertNotIn("Kerberos", str(auth.exception))
                self.assertNotIn("secret stderr", str(auth.exception))

    def test_structured_waystone_error_can_follow_non_json_stderr_prelude(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env["FAKE_WAYSTONE_STDERR_PREFIX"] = "wrapper prelude secret stderr"
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                first = self.write_file(root, "first.bin", b"first")
                second = self.write_file(root, "second.bin", b"second")
                key = "runs/prefix-conflict/run-20261009/output/blob.bin"
                store.put(key, first)
                with self.assertRaises(Conflict) as conflict:
                    store.put(key, second)

            self.assertNotIn("wrapper prelude", str(conflict.exception))
            self.assertNotIn("secret stderr", str(conflict.exception))

    def test_structured_waystone_error_classes_drive_failure_mapping(self):
        cases = (
            ("auth", 10, Unauthenticated, 1),
            ("timeout", 11, Unavailable, 3),
            ("usage", 2, Unavailable, 1),
            ("external", 12, Unavailable, 3),
            ("transfer", 20, Unavailable, 3),
            ("verification", 21, Unavailable, 1),
        )
        for error_class, exit_code, expected_error, expected_attempts in cases:
            with self.subTest(error_class=error_class):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    fake = self.install_fake_waystone(root)
                    env = self.fake_environment(root)
                    env.update(
                        {
                            "FAKE_WAYSTONE_ERROR_CLASS": error_class,
                            "FAKE_WAYSTONE_ERROR_EXIT": str(exit_code),
                            "FAKE_WAYSTONE_ERROR_MESSAGE": (
                                "structured secret stderr for "
                                + error_class
                                + " at hdfs://fixture/storage/sureal/runs/token-file-exists/blob.bin"
                            ),
                        }
                    )
                    with self.with_environment(env):
                        adapter = WaystoneBlobAdapter(
                            project="sureal",
                            command_prefix=[str(fake)],
                            tool_pins={str(fake): self.sha256(fake)},
                        )
                        store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                        with self.assertRaises(expected_error) as caught:
                            store.exists("runs/classes/run-20261009/output/blob.bin")

                    self.assertNotIn("structured secret stderr", str(caught.exception))
                    self.assertNotIn("exit_code", str(caught.exception))
                    records = self.log_records(root)
                    attempts = [record for record in records if record["verb"] == "ls"]
                    self.assertEqual(len(attempts), expected_attempts)

    def test_transient_structured_message_with_token_file_and_exists_is_not_auth_or_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env.update(
                {
                    "FAKE_WAYSTONE_ERROR_CLASS": "external",
                    "FAKE_WAYSTONE_ERROR_EXIT": "12",
                    "FAKE_WAYSTONE_ERROR_VERBS": "put",
                    "FAKE_WAYSTONE_ERROR_MESSAGE": (
                        "transfer failed for hdfs://fixture/storage/sureal/runs/token-file-exists/blob.bin "
                        "with --auth-source token-file"
                    ),
                }
            )
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                source = self.write_file(root, "source.bin", b"retryable")
                with self.assertRaises(Unavailable) as caught:
                    store.put("runs/token-file-exists/run-20261009/output/blob.bin", source)

            self.assertNotIn("token-file", str(caught.exception))
            records = self.log_records(root)
            attempts = [record for record in records if record["verb"] == "put"]
            self.assertEqual(len(attempts), 3)

    def test_unparseable_waystone_error_is_unavailable_without_marker_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env.update(
                {
                    "FAKE_WAYSTONE_RAW_STDERR": "not-json secret stderr with token-file and already exists",
                    "FAKE_WAYSTONE_ERROR_EXIT": "12",
                    "FAKE_WAYSTONE_ERROR_VERBS": "put",
                }
            )
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(adapter, backoff_seconds=(0.0, 0.0))
                source = self.write_file(root, "source.bin", b"not retryable without structure")
                with self.assertRaises(Unavailable) as caught:
                    store.put("runs/raw-error/run-20261009/output/blob.bin", source)

            self.assertNotIn("secret stderr", str(caught.exception))
            records = self.log_records(root)
            attempts = [record for record in records if record["verb"] == "put"]
            self.assertEqual(len(attempts), 1)

    def test_waystone_adapter_checks_tool_digest_before_every_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(adapter, max_attempts=1, backoff_seconds=())
                self.assertFalse(store.exists("runs/pin/run-20261009/output/blob.bin"))
                fake.write_text(FAKE_WAYSTONE + "\n# changed\n")
                fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
                with self.assertRaises(Unavailable):
                    store.exists("runs/pin/run-20261009/output/blob.bin")

    def test_waystone_adapter_enforces_deadline_by_killing_the_subprocess_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env["FAKE_WAYSTONE_HANG_VERB"] = "ls"
            env["FAKE_WAYSTONE_PARENT_PID"] = str(root / "parent.pid")
            env["FAKE_WAYSTONE_CHILD_PID"] = str(root / "child.pid")
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(
                    adapter,
                    deadline_base_seconds=0.2,
                    metadata_deadline_min_seconds=0.2,
                    minimum_throughput_bytes_per_second=1024 * 1024,
                    max_attempts=1,
                    backoff_seconds=(),
                )
                with self.assertRaises(Unavailable):
                    store.exists("runs/hang/run-20261009/output/blob.bin")

            child_pid = int((root / "child.pid").read_text())
            deadline = time.monotonic() + 2.0
            while self.process_is_running(child_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(self.process_is_running(child_pid))

    def test_waystone_adapter_enforces_deadline_when_layout_profile_hangs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = self.install_fake_waystone(root)
            env = self.fake_environment(root)
            env["FAKE_WAYSTONE_HANG_VERB"] = "layout-profile"
            env["FAKE_WAYSTONE_PARENT_PID"] = str(root / "parent.pid")
            env["FAKE_WAYSTONE_CHILD_PID"] = str(root / "child.pid")
            with self.with_environment(env):
                adapter = WaystoneBlobAdapter(
                    project="sureal",
                    command_prefix=[str(fake)],
                    tool_pins={str(fake): self.sha256(fake)},
                )
                store = BlobStore(
                    adapter,
                    deadline_base_seconds=0.5,
                    metadata_deadline_min_seconds=0.5,
                    minimum_throughput_bytes_per_second=1024 * 1024,
                    max_attempts=1,
                    backoff_seconds=(),
                )
                with self.assertRaises(Unavailable):
                    store.exists("runs/layout-hang/run-20261009/output/blob.bin")

            child_pid = int((root / "child.pid").read_text())
            deadline = time.monotonic() + 2.0
            while self.process_is_running(child_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(self.process_is_running(child_pid))

    def process_is_running(self, pid):
        stat_path = Path("/proc") / str(pid) / "stat"
        try:
            fields = stat_path.read_text().split()
        except FileNotFoundError:
            return False
        if len(fields) > 2 and fields[2] == "Z":
            return False
        return True


if __name__ == "__main__":
    unittest.main()
