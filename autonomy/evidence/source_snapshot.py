"""Source snapshots for evidence receipts."""
import ctypes
import errno
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol

from blob_store.core import (
    BlobStore,
    Conflict,
    Corrupt,
    LocalFileBlobAdapter,
    Missing,
    Unauthenticated,
    Unavailable,
    WaystoneBlobAdapter,
    blob_adapter_from_descriptor,
    blob_store_descriptor,
    validate_blob_key,
)


REPO = Path(__file__).resolve().parents[2]
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_HADOOP_CONF_DIR = "/opt/tiger/yarn_deploy/hadoop/conf"
SOURCE_SNAPSHOT_AREA = "artifacts"
SOURCE_SNAPSHOT_CHILD = "source-snapshots"
STORE_DESCRIPTOR_VERSION = 1
TARGET_RECEIPT_SCHEMA_VERSION = 2
AT_FDCWD = -100
RENAME_NOREPLACE = 1
RENAMEAT2_SYSCALLS = {
    "x86_64": 316,
    "aarch64": 276,
}
@dataclass(frozen=True)
class SourceSnapshot:
    target: str
    digest: str
    archive_bytes: int
    source_pins: dict[str, str]


class SnapshotStore(Protocol):
    def store(self, digest: str, data: bytes) -> str: ...
    def fetch(self, digest: str) -> bytes: ...


class SnapshotStorageError(RuntimeError):
    pass


class SnapshotAuthenticationError(PermissionError):
    pass


class SnapshotMissingError(FileNotFoundError):
    pass


def source_snapshot_blob_key(digest: str) -> str:
    return f"{SOURCE_SNAPSHOT_AREA}/{SOURCE_SNAPSHOT_CHILD}/{require_digest(digest)}"


def legacy_source_snapshot_blob_key(digest: str) -> str:
    return f"{SOURCE_SNAPSHOT_CHILD}/{require_digest(digest)}"


def source_snapshot_blob_record(digest: str, byte_count: int) -> dict:
    return {
        "key": source_snapshot_blob_key(digest),
        "sha256": require_digest(digest),
        "bytes": int(byte_count),
    }


class LocalSnapshotStore:
    def __init__(self, root):
        self.root = Path(root)
        self._adapter = LocalFileBlobAdapter(self.root)
        self._store = BlobStore(self._adapter)

    def path_for(self, digest: str) -> Path:
        return self.root.joinpath(*source_snapshot_blob_key(digest).split("/"))

    def legacy_path_for(self, digest: str) -> Path:
        return self.root / require_digest(digest)

    def store(self, digest: str, data: bytes) -> str:
        require_digest(digest)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from key")
        if self.root.is_symlink():
            raise ValueError("regular snapshot store directory required")
        path = self.path_for(digest)
        if path.is_symlink():
            raise ValueError("regular snapshot object required")
        _put_snapshot_blob(self._store, digest, data)
        return digest

    def fetch(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("regular snapshot object required")
        try:
            return _get_snapshot_blob(self._store, digest)
        except SnapshotMissingError:
            pass
        return self._fetch_legacy(digest)

    def _fetch_legacy(self, digest: str) -> bytes:
        path = self.legacy_path_for(digest)
        if path.is_symlink():
            raise ValueError("regular snapshot object required")
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise FileNotFoundError(f"source snapshot missing: {digest}") from error
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from requested digest")
        return data


class HdfsSnapshotStore:
    def __init__(
        self,
        waystone=None,
        *,
        prefix: str | None = None,
        project: str = "sureal",
        command_prefix=None,
        tool_pins: Mapping[str, str] | None = None,
        hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
        legacy_layout: bool | None = None,
    ):
        self.waystone = None if waystone is None else str(waystone)
        self.legacy_layout = prefix is not None if legacy_layout is None else bool(legacy_layout)
        resolved_command_prefix = command_prefix
        if resolved_command_prefix is None and waystone is not None:
            resolved_command_prefix = [str(waystone)]
        self._adapter = WaystoneBlobAdapter(
            project=project,
            command_prefix=resolved_command_prefix,
            tool_pins=tool_pins,
            legacy_prefix=prefix,
            hadoop_conf_dir=hadoop_conf_dir,
        )
        self._store = BlobStore(self._adapter)

    @property
    def prefix(self) -> str:
        return require_hdfs_prefix(self._adapter._layout_profile()["project_root"])

    def uri_for(self, digest: str) -> str:
        return f"{self.prefix}/{self._key_for_digest(digest)}"

    def _key_for_digest(self, digest: str) -> str:
        return legacy_source_snapshot_blob_key(digest) if self.legacy_layout else source_snapshot_blob_key(digest)

    def store(self, digest: str, data: bytes) -> str:
        require_digest(digest)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from key")
        _put_snapshot_blob(self._store, digest, data, key=self._key_for_digest(digest))
        return digest

    def fetch(self, digest: str) -> bytes:
        return _get_snapshot_blob(self._store, digest, key=self._key_for_digest(digest))


class _BlobSnapshotStore:
    def __init__(self, adapter, *, legacy_layout: bool = False):
        self._adapter = adapter
        self._store = BlobStore(adapter)
        self.legacy_layout = bool(legacy_layout)

    def _key_for_digest(self, digest: str) -> str:
        return legacy_source_snapshot_blob_key(digest) if self.legacy_layout else source_snapshot_blob_key(digest)

    def store(self, digest: str, data: bytes) -> str:
        require_digest(digest)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from key")
        _put_snapshot_blob(self._store, digest, data, key=self._key_for_digest(digest))
        return digest

    def fetch(self, digest: str) -> bytes:
        return _get_snapshot_blob(self._store, digest, key=self._key_for_digest(digest))


def _put_snapshot_blob(store: BlobStore, digest: str, data: bytes, *, key: str | None = None) -> dict:
    key = source_snapshot_blob_key(digest) if key is None else validate_blob_key(key)
    with tempfile.NamedTemporaryFile(prefix=digest + ".", suffix=".snapshot") as source:
        source.write(data)
        source.flush()
        try:
            result = store.put(key, source.name)
        except Conflict as error:
            raise ValueError("snapshot digest differs from existing snapshot") from error
        except Corrupt as error:
            raise ValueError("snapshot digest differs after readback") from error
        except Unauthenticated as error:
            raise SnapshotAuthenticationError(str(error)) from error
        except Missing as error:
            raise SnapshotMissingError(f"source snapshot missing: {digest}") from error
        except Unavailable as error:
            raise SnapshotStorageError("snapshot storage unavailable") from error
    if result["sha256"] != digest or result["bytes"] != len(data):
        raise ValueError("snapshot digest differs after readback")
    return result


def _get_snapshot_blob(
    store: BlobStore,
    digest: str,
    *,
    key: str | None = None,
    expected_bytes: int | None = None,
) -> bytes:
    key = source_snapshot_blob_key(digest) if key is None else validate_blob_key(key)
    with tempfile.TemporaryDirectory(prefix=digest + ".") as directory:
        destination = Path(directory) / (digest + ".snapshot")
        try:
            store.get(key, destination, digest, expected_bytes=expected_bytes)
        except Missing as error:
            raise SnapshotMissingError(f"source snapshot missing: {digest}") from error
        except Corrupt as error:
            raise ValueError("snapshot digest differs from requested digest") from error
        except Unauthenticated as error:
            raise SnapshotAuthenticationError(str(error)) from error
        except Unavailable as error:
            raise SnapshotStorageError("snapshot storage unavailable") from error
        return destination.read_bytes()


def require_digest(digest: str) -> str:
    if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
        raise ValueError("sha256 digest required")
    return digest


def require_hdfs_prefix(prefix: str) -> str:
    if not isinstance(prefix, str):
        raise ValueError("HDFS source snapshot prefix required")
    prefix = prefix.rstrip("/")
    if (
        not prefix
        or not prefix.startswith("hdfs://")
        or any(character in prefix for character in ("\x00", "\n", "\r"))
        or "@" in prefix.split("://", 1)[1].split("/", 1)[0]
    ):
        raise ValueError("HDFS source snapshot prefix required")
    return prefix


def require_regular_file(path):
    path = Path(path)
    if not path.is_file() or any(candidate.is_symlink() for candidate in [path, *path.parents]):
        raise ValueError("regular non-symlinked file required: " + str(path))
    return path


def is_regular_file(path) -> bool:
    try:
        require_regular_file(path)
    except (OSError, ValueError):
        return False
    return True


def file_digest(path, algorithm: str) -> str:
    with require_regular_file(path).open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def file_sha256(path) -> str:
    return file_digest(path, "sha256")


def _renameat2_syscall_number() -> int:
    machine = os.uname().machine
    try:
        return RENAMEAT2_SYSCALLS[machine]
    except KeyError as error:
        raise OSError(errno.ENOSYS, "renameat2 syscall number unknown for " + machine) from error


def _rename_no_replace(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    try:
        renameat2 = libc.renameat2
    except AttributeError:
        result = libc.syscall(
            _renameat2_syscall_number(),
            AT_FDCWD,
            ctypes.c_char_p(source_bytes),
            AT_FDCWD,
            ctypes.c_char_p(destination_bytes),
            RENAME_NOREPLACE,
        )
    else:
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(
            AT_FDCWD,
            ctypes.c_char_p(source_bytes),
            AT_FDCWD,
            ctypes.c_char_p(destination_bytes),
            RENAME_NOREPLACE,
        )
    if result == 0:
        return
    found = ctypes.get_errno()
    if found == errno.EEXIST:
        raise FileExistsError("source snapshot destination already exists: " + str(destination))
    raise OSError(found, os.strerror(found), str(destination))


def safe_member_name(name: str) -> str:
    if not isinstance(name, str) or not name or any(c in name for c in ["\\", "\x00", "\n", "\r"]):
        raise ValueError("safe snapshot member name required")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError("safe snapshot member name required")
    return name


def label_to_path(label: str) -> str:
    if label.startswith("@"):
        raise ValueError("external source labels are not part of the repository snapshot")
    if not label.startswith("//") or ":" not in label:
        raise ValueError("main-repository Bazel source label required: " + label)
    package, name = label[2:].split(":", 1)
    relative = f"{package}/{name}" if package else name
    return safe_member_name(relative)


def bazel_source_paths(target: str, *, repo_root=REPO, bazel=None, runner=subprocess.run) -> list[str]:
    if not isinstance(target, str) or not target.startswith("//"):
        raise ValueError("Bazel target label required")
    repo_root = Path(repo_root)
    bazel = str(repo_root / "bazelw") if bazel is None else str(bazel)
    expression = f'kind("source file", filter("^//", labels("srcs", deps({target})) union labels("data", deps({target}))))'
    result = runner(
        [bazel, "query", "--output=label", expression],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    paths = [label_to_path(line.strip()) for line in result.stdout.splitlines() if line.startswith("//")]
    if not paths:
        raise ValueError("Bazel target has no repository source files")
    if len(paths) != len(set(paths)):
        raise ValueError("Bazel source closure contains duplicate paths")
    return sorted(paths)


def archive_sources(repo_root, source_paths) -> tuple[bytes, dict[str, str]]:
    repo_root = Path(repo_root).resolve()
    pins = {}
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w", format=tarfile.PAX_FORMAT) as writer:
        for name in sorted(source_paths):
            safe_member_name(name)
            path = require_regular_file(repo_root / name)
            try:
                path.resolve(strict=True).relative_to(repo_root)
            except ValueError as error:
                raise ValueError("source path escapes repository: " + name) from error
            data = path.read_bytes()
            pins[name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o444
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.pax_headers = {}
            writer.addfile(info, io.BytesIO(data))
    return payload.getvalue(), pins


def snapshot_bazel_target(target: str, store: SnapshotStore, *, repo_root=REPO, bazel=None, runner=subprocess.run) -> SourceSnapshot:
    source_paths = bazel_source_paths(target, repo_root=repo_root, bazel=bazel, runner=runner)
    archive, pins = archive_sources(repo_root, source_paths)
    digest = hashlib.sha256(archive).hexdigest()
    store.store(digest, archive)
    return SourceSnapshot(
        target=target,
        digest=digest,
        archive_bytes=len(archive),
        source_pins=pins,
    )


def source_snapshot_store_descriptor(store: SnapshotStore) -> dict:
    adapter = getattr(store, "_adapter", None)
    if adapter is not None:
        return blob_store_descriptor(adapter)
    raise ValueError("source snapshot store descriptor required")


def source_snapshot_receipt(root, source_paths, store: SnapshotStore, *, target: str, materialized_root=None) -> dict:
    archive, pins = archive_sources(root, source_paths)
    digest = hashlib.sha256(archive).hexdigest()
    store.store(digest, archive)
    receipt = {
        "schema_version": 1,
        "source_snapshot_sha256": digest,
        "source_snapshot_target": target,
        "source_snapshot_archive_bytes": len(archive),
        "source_snapshot_store": source_snapshot_store_descriptor(store),
        "source_snapshot_blob": source_snapshot_blob_record(digest, len(archive)),
        "source_pins": pins,
    }
    if materialized_root is not None:
        receipt["source_snapshot_root"] = str(Path(materialized_root))
    return receipt


def copy_source_snapshot(root, source_paths, destination, store: SnapshotStore, *, target: str) -> dict:
    root = Path(root)
    destination = Path(destination)
    if destination == root or destination.is_relative_to(root):
        raise ValueError("source snapshot copy must be outside current source tree")
    archive, pins = archive_sources(root, source_paths)
    destination.mkdir(exist_ok=False)
    try:
        for name in sorted(pins):
            source = root / name
            target_path = destination / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target_path)
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    for name, digest in pins.items():
        if file_sha256(destination / name) != digest:
            raise ValueError("source changed while snapshot was materialized")
    digest = hashlib.sha256(archive).hexdigest()
    store.store(digest, archive)
    receipt = {
        "schema_version": 1,
        "source_snapshot_sha256": digest,
        "source_snapshot_target": target,
        "source_snapshot_archive_bytes": len(archive),
        "source_snapshot_store": source_snapshot_store_descriptor(store),
        "source_snapshot_blob": source_snapshot_blob_record(digest, len(archive)),
        "source_snapshot_root": str(destination),
        "source_pins": pins,
    }
    return {key: value for key, value in receipt.items() if value is not None}


def _store_from_descriptor(
    descriptor,
    *,
    waystone=None,
    command_prefix=None,
    tool_pins: Mapping[str, str] | None = None,
    hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
) -> SnapshotStore:
    if isinstance(descriptor, str):
        if not descriptor:
            raise ValueError("source snapshot store required")
        return LocalSnapshotStore(descriptor)
    if not isinstance(descriptor, Mapping):
        raise ValueError("source snapshot store descriptor required")
    kind = descriptor.get("kind")
    normalized = descriptor
    if kind == "local":
        if "schema_version" in descriptor:
            if descriptor.get("schema_version") != STORE_DESCRIPTOR_VERSION:
                raise ValueError("source snapshot store descriptor schema required")
            if set(descriptor) != {"schema_version", "kind", "root"}:
                raise ValueError("source snapshot store descriptor fields required")
            normalized = {"kind": "local", "root": descriptor.get("root")}
    if kind == "hdfs":
        allowed = {"schema_version", "kind", "prefix", "project"}
        if not set(descriptor).issubset(allowed) or "prefix" not in descriptor:
            raise ValueError("source snapshot store descriptor fields required")
        normalized = dict(descriptor)
        normalized["prefix"] = require_hdfs_prefix(descriptor.get("prefix"))
    adapter = blob_adapter_from_descriptor(
        normalized,
        waystone=waystone,
        command_prefix=command_prefix,
        tool_pins=tool_pins,
        hadoop_conf_dir=hadoop_conf_dir,
    )
    if isinstance(adapter, LocalFileBlobAdapter):
        return LocalSnapshotStore(adapter.root)
    return _BlobSnapshotStore(adapter, legacy_layout=kind == "hdfs")


def store_from_receipt(
    receipt: Mapping,
    *,
    env_var: str | None = None,
    waystone=None,
    command_prefix=None,
    tool_pins: Mapping[str, str] | None = None,
    hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
) -> SnapshotStore:
    override = os.environ.get(env_var) if env_var else None
    if override:
        return LocalSnapshotStore(override)
    descriptor = receipt.get("source_snapshot_store")
    if descriptor is None:
        raise ValueError("source snapshot store required")
    return _store_from_descriptor(
        descriptor,
        waystone=waystone,
        command_prefix=command_prefix,
        tool_pins=tool_pins,
        hadoop_conf_dir=hadoop_conf_dir,
    )


def verify_materialized_sources(root, receipt, store: SnapshotStore | None = None, *, package: str | None = None) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    store = store if store is not None else store_from_receipt(receipt, env_var="SUREAL_SOURCE_SNAPSHOT_STORE")
    verified = verify_receipt_sources(receipt, store)
    root = Path(root)
    prefix = None
    if package is not None:
        package = safe_member_name(package)
        if "/" in package:
            raise ValueError("top-level source package required")
        prefix = package + "/"
    for name, digest in verified["source_pins"].items():
        materialized_name = name
        if prefix is not None:
            if not name.startswith(prefix):
                raise ValueError("materialized source outside package: " + name)
            materialized_name = name.removeprefix(prefix)
        try:
            found = file_sha256(root / materialized_name)
        except ValueError as error:
            raise ValueError("materialized source missing or irregular: " + name) from error
        if found != digest:
            raise ValueError("materialized source changed: " + name)
    return verified


def _snapshot_entries(snapshot: bytes) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
    pins = {}
    entries = []
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot), mode="r:") as reader:
            for member in reader:
                name = safe_member_name(member.name)
                if name in pins or not member.isfile() or member.linkname:
                    raise ValueError("snapshot contains duplicate or nonregular member")
                stream = reader.extractfile(member)
                if stream is None:
                    raise ValueError("snapshot contains unreadable member")
                data = stream.read()
                pins[name] = hashlib.sha256(data).hexdigest()
                entries.append((name, data))
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ValueError("invalid source snapshot") from error
    if not pins:
        raise ValueError("source snapshot contains no files")
    return dict(sorted(pins.items())), sorted(entries)


def snapshot_source_pins(snapshot: bytes) -> dict[str, str]:
    pins, _ = _snapshot_entries(snapshot)
    return pins


def read_receipt(receipt) -> Mapping:
    if isinstance(receipt, (str, Path)):
        return json.loads(Path(receipt).read_text())
    return receipt


def source_snapshot_package_root(receipt, *, package: str = "autonomy") -> Path:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    root_value = receipt.get("source_snapshot_root")
    if not isinstance(root_value, str) or not root_value:
        raise ValueError("source snapshot root required")
    root = Path(root_value)
    if receipt.get("schema_version") == TARGET_RECEIPT_SCHEMA_VERSION:
        safe_member_name(package)
        if "/" in package:
            raise ValueError("top-level source package required")
        return root / package
    return root


def source_snapshot_member_path(receipt, relative: str, *, package: str = "autonomy") -> Path:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    relative = safe_member_name(relative)
    pins = receipt_source_pins(receipt)
    if receipt.get("schema_version") == TARGET_RECEIPT_SCHEMA_VERSION:
        safe_member_name(package)
        if "/" in package:
            raise ValueError("top-level source package required")
        member = f"{package}/{relative}"
    else:
        member = relative
    if member not in pins:
        raise ValueError("receipt source member required: " + member)
    return Path(receipt["source_snapshot_root"]) / member


def receipt_snapshot_digest(receipt: Mapping) -> str:
    if "source_snapshot_sha256" not in receipt:
        raise ValueError("receipt source snapshot digest required")
    return require_digest(receipt["source_snapshot_sha256"])


def receipt_source_pins(receipt: Mapping) -> dict[str, str]:
    if "source_pins" not in receipt:
        raise ValueError("receipt source pins required")
    raw = receipt["source_pins"]
    if not isinstance(raw, Mapping):
        raise ValueError("receipt source pins required")
    pins = {}
    for name, value in raw.items():
        pins[safe_member_name(name)] = require_digest(value)
    return dict(sorted(pins.items()))


def receipt_snapshot_blob(receipt: Mapping, digest: str | None = None) -> dict | None:
    blob = receipt.get("source_snapshot_blob")
    if blob is None:
        return None
    if not isinstance(blob, Mapping):
        raise ValueError("receipt source snapshot blob required")
    if set(blob) != {"key", "sha256", "bytes"}:
        raise ValueError("receipt source snapshot blob fields required")
    receipt_digest = receipt_snapshot_digest(receipt) if digest is None else require_digest(digest)
    blob_digest = require_digest(blob["sha256"])
    if blob_digest != receipt_digest:
        raise ValueError("source snapshot blob digest differs from receipt")
    byte_count = blob["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise ValueError("source snapshot blob bytes required")
    return {
        "key": validate_blob_key(blob["key"]),
        "sha256": blob_digest,
        "bytes": byte_count,
    }


def _fetch_receipt_archive(store: SnapshotStore, digest: str, blob: Mapping | None) -> bytes:
    if blob is None:
        return store.fetch(digest)
    blob_store = getattr(store, "_store", None)
    if blob_store is not None:
        return _get_snapshot_blob(blob_store, digest, key=blob["key"], expected_bytes=blob["bytes"])
    return store.fetch(digest)


def _verified_receipt_archive(receipt: Mapping, store: SnapshotStore) -> tuple[str, bytes, dict[str, str]]:
    digest = receipt_snapshot_digest(receipt)
    blob = receipt_snapshot_blob(receipt, digest)
    archive = _fetch_receipt_archive(store, digest, blob)
    if hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError("snapshot digest differs from receipt")
    expected_bytes = blob["bytes"] if blob is not None else receipt.get("source_snapshot_archive_bytes")
    if expected_bytes is not None:
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise ValueError("source snapshot archive bytes required")
        if len(archive) != expected_bytes:
            raise ValueError("snapshot bytes differ from receipt")
    actual = snapshot_source_pins(archive)
    expected = receipt_source_pins(receipt)
    if actual != expected:
        raise ValueError("receipt source pins differ from snapshot")
    return digest, archive, actual


def verify_receipt_sources(receipt, store: SnapshotStore) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    digest, _, actual = _verified_receipt_archive(receipt, store)
    return {
        "source_snapshot_sha256": digest,
        "source_snapshot_target": receipt.get("source_snapshot_target"),
        "source_pins": actual,
        "source_files": len(actual),
    }


def materialize_source_snapshot_archive(snapshot: bytes, destination, *, digest: str | None = None, source_pins: Mapping | None = None) -> dict:
    if digest is not None:
        digest = require_digest(digest)
        if hashlib.sha256(snapshot).hexdigest() != digest:
            raise ValueError("snapshot digest differs from receipt")
    actual, entries = _snapshot_entries(snapshot)
    if source_pins is not None:
        expected = {}
        for name, value in source_pins.items():
            expected[safe_member_name(name)] = require_digest(value)
        if actual != dict(sorted(expected.items())):
            raise ValueError("source pins differ from snapshot")
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("source snapshot destination already exists: " + str(destination))
    temporary = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix="." + destination.name + ".", suffix=".tmp", dir=destination.parent))
        for name, data in entries:
            target = temporary / name
            try:
                target.resolve().relative_to(temporary.resolve())
            except ValueError as error:
                raise ValueError("source snapshot member escapes destination: " + name) from error
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError("source snapshot materialization conflict: " + name)
            target.write_bytes(data)
            target.chmod(0o444)
        for name, expected_digest in actual.items():
            if file_sha256(temporary / name) != expected_digest:
                raise ValueError("materialized source differs from snapshot: " + name)
        _rename_no_replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    return {
        "source_snapshot_sha256": digest or hashlib.sha256(snapshot).hexdigest(),
        "source_snapshot_root": str(destination),
        "source_pins": actual,
        "source_files": len(actual),
    }


def materialize_receipt_sources(
    receipt,
    destination,
    store: SnapshotStore | None = None,
    *,
    env_var: str | None = None,
    waystone=None,
    command_prefix=None,
    tool_pins: Mapping[str, str] | None = None,
    hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    store = store if store is not None else store_from_receipt(
        receipt,
        env_var=env_var,
        waystone=waystone,
        command_prefix=command_prefix,
        tool_pins=tool_pins,
        hadoop_conf_dir=hadoop_conf_dir,
    )
    digest, archive, pins = _verified_receipt_archive(receipt, store)
    materialized = materialize_source_snapshot_archive(archive, destination, digest=digest, source_pins=pins)
    return {
        "source_snapshot_sha256": digest,
        "source_snapshot_target": receipt.get("source_snapshot_target"),
        "source_snapshot_store": receipt.get("source_snapshot_store"),
        "source_snapshot_blob": receipt.get("source_snapshot_blob"),
        "source_snapshot_root": materialized["source_snapshot_root"],
        "source_pins": pins,
        "source_files": len(pins),
    }


def verify_or_materialize_receipt_sources(
    receipt,
    destination=None,
    store: SnapshotStore | None = None,
    *,
    env_var: str | None = None,
    waystone=None,
    command_prefix=None,
    tool_pins: Mapping[str, str] | None = None,
    hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    root_value = destination if destination is not None else receipt.get("source_snapshot_root")
    if root_value is None:
        raise ValueError("source snapshot root required")
    root = Path(root_value)
    resolved_store = store if store is not None else store_from_receipt(
        receipt,
        env_var=env_var,
        waystone=waystone,
        command_prefix=command_prefix,
        tool_pins=tool_pins,
        hadoop_conf_dir=hadoop_conf_dir,
    )
    if root.exists():
        return verify_materialized_sources(root, receipt, resolved_store)
    return materialize_receipt_sources(
        receipt,
        root,
        resolved_store,
        env_var=env_var,
        waystone=waystone,
        command_prefix=command_prefix,
        tool_pins=tool_pins,
        hadoop_conf_dir=hadoop_conf_dir,
    )


def snapshot_target_and_materialize(
    target: str,
    destination,
    *,
    store: SnapshotStore | None = None,
    repo_root=REPO,
    bazel=None,
    runner=subprocess.run,
) -> dict:
    store = HdfsSnapshotStore() if store is None else store
    snapshot = snapshot_bazel_target(target, store, repo_root=repo_root, bazel=bazel, runner=runner)
    archive = store.fetch(snapshot.digest)
    materialized = materialize_source_snapshot_archive(
        archive,
        destination,
        digest=snapshot.digest,
        source_pins=snapshot.source_pins,
    )
    return {
        "schema_version": TARGET_RECEIPT_SCHEMA_VERSION,
        "source_snapshot_sha256": snapshot.digest,
        "source_snapshot_target": snapshot.target,
        "source_snapshot_archive_bytes": snapshot.archive_bytes,
        "source_snapshot_store": source_snapshot_store_descriptor(store),
        "source_snapshot_blob": source_snapshot_blob_record(snapshot.digest, snapshot.archive_bytes),
        "source_snapshot_root": materialized["source_snapshot_root"],
        "source_pins": snapshot.source_pins,
    }
