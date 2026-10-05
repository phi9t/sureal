"""Source snapshots for evidence receipts."""
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol


REPO = Path(__file__).resolve().parents[2]
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SourceSnapshot:
    target: str
    digest: str
    archive_sha256: str
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
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("xb") as output:
            output.write(data)
        tmp.replace(path)
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
    expression = f'filter("^//", labels("srcs", deps({target})) union labels("data", deps({target})))'
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
    with gzip.GzipFile(fileobj=payload, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as writer:
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
        archive_sha256=digest,
        archive_bytes=len(archive),
        source_pins=pins,
    )


def snapshot_source_pins(snapshot: bytes) -> dict[str, str]:
    pins = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot), mode="r:gz") as reader:
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
    value = receipt.get("source_snapshot_sha256")
    if value is None and isinstance(receipt.get("source_snapshot"), Mapping):
        value = receipt["source_snapshot"].get("sha256")
    return require_digest(value)


def receipt_source_pins(receipt: Mapping) -> dict[str, str]:
    for field in ("source_pins", "source_sha256", "source_hashes"):
        if field in receipt:
            raw = receipt[field]
            break
    else:
        raise ValueError("receipt source pins required")
    if not isinstance(raw, Mapping):
        raise ValueError("receipt source pins required")
    pins = {}
    for name, value in raw.items():
        if isinstance(value, Mapping):
            value = value.get("sha256")
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
