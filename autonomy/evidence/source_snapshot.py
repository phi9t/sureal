"""Source snapshots for evidence receipts."""
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


REPO = Path(__file__).resolve().parents[2]
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceSnapshot:
    target: str
    digest: str
    archive_bytes: int
    source_pins: dict[str, str]


class SnapshotStore(Protocol):
    def store(self, digest: str, data: bytes) -> str: ...
    def fetch(self, digest: str) -> bytes: ...


class LocalSnapshotStore:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, digest: str) -> Path:
        require_digest(digest)
        return self.root / digest

    def store(self, digest: str, data: bytes) -> str:
        require_digest(digest)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from key")
        if self.root.is_symlink():
            raise ValueError("regular snapshot store directory required")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(digest)
        if path.is_symlink():
            raise ValueError("regular snapshot object required")
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError("snapshot digest differs from existing snapshot")
            return digest
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=path.name + ".", suffix=".tmp", delete=False) as output:
                tmp = Path(output.name)
                output.write(data)
            tmp.replace(path)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("snapshot digest differs after readback")
        return digest

    def fetch(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if self.root.is_symlink() or path.is_symlink():
            raise ValueError("regular snapshot object required")
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise FileNotFoundError(f"source snapshot missing: {digest}") from error
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("snapshot digest differs from requested digest")
        return data


def require_digest(digest: str) -> str:
    if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest):
        raise ValueError("sha256 digest required")
    return digest


def require_regular_file(path):
    path = Path(path)
    if not path.is_file() or any(candidate.is_symlink() for candidate in [path, *path.parents]):
        raise ValueError("regular non-symlinked file required: " + str(path))
    return path


def file_sha256(path) -> str:
    with require_regular_file(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def source_snapshot_receipt(root, source_paths, store: SnapshotStore, *, target: str, materialized_root=None) -> dict:
    archive, pins = archive_sources(root, source_paths)
    digest = hashlib.sha256(archive).hexdigest()
    store.store(digest, archive)
    receipt = {
        "schema_version": 1,
        "source_snapshot_sha256": digest,
        "source_snapshot_target": target,
        "source_pins": pins,
    }
    if isinstance(store, LocalSnapshotStore):
        receipt["source_snapshot_store"] = str(store.root)
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
        "source_snapshot_store": str(store.root) if isinstance(store, LocalSnapshotStore) else None,
        "source_snapshot_root": str(destination),
        "source_pins": pins,
    }
    return {key: value for key, value in receipt.items() if value is not None}


def store_from_receipt(receipt: Mapping, *, env_var: str | None = None) -> SnapshotStore:
    override = os.environ.get(env_var) if env_var else None
    root = override or receipt.get("source_snapshot_store")
    if not isinstance(root, str) or not root:
        raise ValueError("source snapshot store required")
    return LocalSnapshotStore(root)


def verify_materialized_sources(root, receipt, store: SnapshotStore | None = None) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    store = store if store is not None else store_from_receipt(receipt, env_var="SUREAL_SOURCE_SNAPSHOT_STORE")
    verified = verify_receipt_sources(receipt, store)
    root = Path(root)
    for name, digest in verified["source_pins"].items():
        try:
            found = file_sha256(root / name)
        except ValueError as error:
            raise ValueError("materialized source missing or irregular: " + name) from error
        if found != digest:
            raise ValueError("materialized source changed: " + name)
    return verified


def snapshot_source_pins(snapshot: bytes) -> dict[str, str]:
    pins = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot), mode="r:") as reader:
            for member in reader:
                name = safe_member_name(member.name)
                if name in pins or not member.isfile() or member.linkname:
                    raise ValueError("snapshot contains duplicate or nonregular member")
                stream = reader.extractfile(member)
                if stream is None:
                    raise ValueError("snapshot contains unreadable member")
                pins[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ValueError("invalid source snapshot") from error
    if not pins:
        raise ValueError("source snapshot contains no files")
    return dict(sorted(pins.items()))


def read_receipt(receipt) -> Mapping:
    if isinstance(receipt, (str, Path)):
        return json.loads(Path(receipt).read_text())
    return receipt


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


def verify_receipt_sources(receipt, store: SnapshotStore) -> dict:
    receipt = read_receipt(receipt)
    if not isinstance(receipt, Mapping):
        raise ValueError("receipt object required")
    digest = receipt_snapshot_digest(receipt)
    archive = store.fetch(digest)
    if hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError("snapshot digest differs from receipt")
    actual = snapshot_source_pins(archive)
    expected = receipt_source_pins(receipt)
    if actual != expected:
        raise ValueError("receipt source pins differ from snapshot")
    return {
        "source_snapshot_sha256": digest,
        "source_snapshot_target": receipt.get("source_snapshot_target"),
        "source_pins": actual,
        "source_files": len(actual),
    }
