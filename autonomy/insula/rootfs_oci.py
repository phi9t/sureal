"""Publish and restore Insula rootfs trees as OCI artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from evidence.source_snapshot import file_sha256
from insula.launch_plan import RuntimeLockError, load_runtime_lock
from insula.runtime_roots import (
    current_cpu_rootfs,
    current_curriculum_rootfs,
    current_gpu_rootfs,
    current_metrics_rootfs,
    current_motion_cli_rootfs,
    current_motion_metrics_rootfs,
    default_lock,
)


DEFAULT_REGISTRY = "ghcr.io/phi9t"
DEFAULT_MAX_PART_BYTES = 1024 * 1024 * 1024
DEFAULT_ZSTD_THREADS = 1
FIXED_MTIME_EPOCH = 0
ORAS_VERSION = "1.3.4"
ORAS_LINUX_AMD64_SHA256 = "f27adb935022d94df8dc77719c322dda592c78a0d57a6f7dcdd8d900b248c454"
ORAS_LINUX_AMD64_URL = (
    "https://github.com/oras-project/oras/releases/download/"
    f"v{ORAS_VERSION}/oras_{ORAS_VERSION}_linux_amd64.tar.gz"
)
ARTIFACT_TYPE = "application/vnd.sureal.rootfs.v1"
CONFIG_MEDIA_TYPE = "application/vnd.sureal.rootfs.config.v1+json"
MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
LAYOUT_VERSION = "1.0.0"
TAG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
ROLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
SAFE_LAYER_PATH_RE = re.compile(r"^[A-Za-z0-9._/+:-]+$")


class RootfsOciError(ValueError):
    """Raised when rootfs artifact publication or restore refuses an input."""


class CommandError(RootfsOciError):
    """Raised when an external command fails with redacted output."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArchiveTools:
    """Command-line tools used at the archive boundary."""

    tar_bin: Path | str = "tar"
    zstd_bin: Path | str = "zstd"
    zstd_threads: int = DEFAULT_ZSTD_THREADS


@dataclass(frozen=True)
class RootfsSpec:
    """A named rootfs tree and the lock that authorizes it."""

    role: str
    rootfs: Path
    lock: Path


@dataclass(frozen=True)
class PackedBundle:
    """Staged rootfs artifact files ready for OCI publication."""

    artifact_dir: Path
    manifest_path: Path
    lock_artifact_path: Path
    archive_path: Path
    archive_sha256: str
    archive_size: int
    rootfs_sha256: str
    lock_sha256: str
    role: str
    rootfs_name: str
    parts: tuple[dict[str, object], ...]
    files: tuple[dict[str, object], ...]

    def oci_annotations(self) -> dict[str, str]:
        return {
            "io.sureal.artifact.kind": "rootfs",
            "io.sureal.rootfs.role": self.role,
            "io.sureal.rootfs.name": self.rootfs_name,
            "io.sureal.rootfs.lock.sha256": self.lock_sha256,
            "io.sureal.rootfs.rootfs.sha256": self.rootfs_sha256,
            "io.sureal.rootfs.archive.sha256": self.archive_sha256,
            "io.sureal.rootfs.archive.size": str(self.archive_size),
            "io.sureal.rootfs.part.count": str(len(self.parts)),
            "io.sureal.rootfs.file.count": str(len(self.files)),
            "io.sureal.rootfs.manifest.sha256": file_sha256(self.manifest_path),
            **_rootfs_entry_annotations(self.files),
            **_artifact_file_annotations(_collect_artifact_files(self.artifact_dir)),
        }


@dataclass(frozen=True)
class PushResult:
    """Result of publishing a rootfs artifact."""

    role: str
    package: str
    tag: str
    reference: str
    digest: str
    archive_sha256: str
    archive_size: int
    rootfs_sha256: str
    lock_sha256: str
    part_count: int
    parts: tuple[dict[str, object], ...]
    elapsed_seconds: float

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "package": self.package,
            "tag": self.tag,
            "reference": self.reference,
            "digest": self.digest,
            "archive_sha256": self.archive_sha256,
            "archive_size": self.archive_size,
            "rootfs_sha256": self.rootfs_sha256,
            "lock_sha256": self.lock_sha256,
            "part_count": self.part_count,
            "parts": list(self.parts),
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(frozen=True)
class PullResult:
    """Result of restoring and checking a rootfs artifact."""

    role: str
    package: str
    reference: str
    digest: str
    target_rootfs: Path
    target_lock: Path
    rootfs_sha256: str
    lock_sha256: str
    archive_sha256: str
    part_count: int
    elapsed_seconds: float

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "package": self.package,
            "reference": self.reference,
            "digest": self.digest,
            "target_rootfs": str(self.target_rootfs),
            "target_lock": str(self.target_lock),
            "rootfs_sha256": self.rootfs_sha256,
            "lock_sha256": self.lock_sha256,
            "archive_sha256": self.archive_sha256,
            "part_count": self.part_count,
            "elapsed_seconds": self.elapsed_seconds,
        }


def active_rootfs_specs(
    *,
    waymo_cache: Path | None = None,
    pathway_cache: Path | None = None,
) -> tuple[RootfsSpec, ...]:
    """Return the active rootfs set owned by ``runtime_roots.py``."""
    waymo = Path(waymo_cache).expanduser() if waymo_cache is not None else None
    pathway = Path(pathway_cache).expanduser() if pathway_cache is not None else None
    roots = (
        ("cpu", current_cpu_rootfs(waymo)),
        ("gpu", current_gpu_rootfs(waymo)),
        ("metrics", current_metrics_rootfs(waymo)),
        ("motion-metrics", current_motion_metrics_rootfs(waymo)),
        ("motion-cli", current_motion_cli_rootfs(waymo)),
        ("parallax-curriculum", current_curriculum_rootfs(pathway)),
    )
    return tuple(RootfsSpec(role=role, rootfs=rootfs, lock=default_lock(rootfs)) for role, rootfs in roots)


def package_for_role(role: str) -> str:
    _require_safe_role(role)
    return f"sureal-rootfs-{role}"


def tag_for_lock(lock_sha256: str) -> str:
    digest = _normalize_sha256_hex(lock_sha256, "lock sha256")
    return digest[:12]


def pack_rootfs_bundle(
    spec: RootfsSpec,
    work_dir: Path,
    *,
    max_part_bytes: int = DEFAULT_MAX_PART_BYTES,
    tools: ArchiveTools | None = None,
) -> PackedBundle:
    """Build a deterministic tar.zst archive and split it into artifact layers."""
    _require_safe_role(spec.role)
    if max_part_bytes <= 0:
        raise RootfsOciError("--max-part-bytes must be positive")
    tools = tools or ArchiveTools()
    runtime = load_runtime_lock(spec.rootfs, spec.lock)
    rootfs = runtime.rootfs
    lock = runtime.lock_path
    if lock is None:
        raise RootfsOciError("runtime lock path required")
    root = Path(work_dir)
    if root.exists() and any(root.iterdir()):
        raise RootfsOciError(f"work directory must be absent or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    artifact_dir = root / "artifact"
    rootfs_dir = artifact_dir / "rootfs"
    lock_dir = artifact_dir / "lock"
    manifest_dir = artifact_dir / "manifest"
    for path in (rootfs_dir, lock_dir, manifest_dir):
        path.mkdir(parents=True, exist_ok=True)

    files = tuple(_rootfs_file_inventory(rootfs))
    archive_name = f"{rootfs.name}.tar.zst"
    archive_path = root / archive_name
    _create_archive(rootfs, archive_path, tools)
    archive_sha256 = file_sha256(archive_path)
    archive_size = archive_path.stat().st_size
    parts = tuple(_split_file(archive_path, rootfs_dir, archive_name, max_part_bytes))
    lock_artifact_path = lock_dir / f"{rootfs.name}.lock.json"
    shutil.copy2(lock, lock_artifact_path)
    lock_sha256 = file_sha256(lock_artifact_path)
    manifest_path = manifest_dir / "rootfs-manifest.json"
    manifest = {
        "schema_version": 1,
        "artifact_type": ARTIFACT_TYPE,
        "role": spec.role,
        "rootfs_name": rootfs.name,
        "rootfs_sha256": runtime.data["rootfs_sha256"],
        "lock_sha256": lock_sha256,
        "archive": {
            "path": f"rootfs/{archive_name}",
            "sha256": archive_sha256,
            "size": archive_size,
            "compression": "zstd",
            "zstd_level": 19,
            "zstd_threads": tools.zstd_threads,
            "fixed_mtime_epoch": FIXED_MTIME_EPOCH,
        },
        "parts": list(parts),
        "lock": {
            "path": f"lock/{lock_artifact_path.name}",
            "sha256": lock_sha256,
            "size": lock_artifact_path.stat().st_size,
        },
        "rootfs_files": list(files),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return PackedBundle(
        artifact_dir=artifact_dir,
        manifest_path=manifest_path,
        lock_artifact_path=lock_artifact_path,
        archive_path=archive_path,
        archive_sha256=archive_sha256,
        archive_size=archive_size,
        rootfs_sha256=str(runtime.data["rootfs_sha256"]),
        lock_sha256=lock_sha256,
        role=spec.role,
        rootfs_name=rootfs.name,
        parts=parts,
        files=files,
    )


def push_rootfs_artifact(
    spec: RootfsSpec,
    *,
    dry_run: bool,
    registry: Path | str | None = None,
    work_dir: Path,
    tag: str | None = None,
    max_part_bytes: int = DEFAULT_MAX_PART_BYTES,
    tools: ArchiveTools | None = None,
    oras_bin: Path | None = None,
) -> PushResult:
    """Pack and publish a rootfs to either a local OCI layout or GHCR."""
    started = time.monotonic()
    bundle = pack_rootfs_bundle(spec, work_dir, max_part_bytes=max_part_bytes, tools=tools)
    package = package_for_role(spec.role)
    tag = tag or tag_for_lock(bundle.lock_sha256)
    _require_safe_tag(tag)
    ref, _ = target_reference(registry=registry, dry_run=dry_run, package=package, tag=tag)
    if dry_run:
        digest = write_local_layout_artifact(
            registry=Path(registry).expanduser() if registry is not None else None,
            package=package,
            tag=tag,
            artifact_dir=bundle.artifact_dir,
            annotations=bundle.oci_annotations(),
        )
    else:
        digest = push_remote_artifact(
            ref=ref,
            package=package,
            tag=tag,
            bundle=bundle,
            registry=str(registry or DEFAULT_REGISTRY),
            oras_bin=oras_bin,
        )
    return PushResult(
        role=spec.role,
        package=package,
        tag=tag,
        reference=ref,
        digest=digest,
        archive_sha256=bundle.archive_sha256,
        archive_size=bundle.archive_size,
        rootfs_sha256=bundle.rootfs_sha256,
        lock_sha256=bundle.lock_sha256,
        part_count=len(bundle.parts),
        parts=bundle.parts,
        elapsed_seconds=time.monotonic() - started,
    )


def pull_rootfs_artifact(
    *,
    role: str,
    dry_run: bool,
    target_rootfs: Path,
    registry: Path | str | None = None,
    tag: str | None = None,
    digest: str | None = None,
    work_dir: Path,
    tools: ArchiveTools | None = None,
    oras_bin: Path | None = None,
) -> PullResult:
    """Pull, verify, extract, and atomically promote a rootfs artifact."""
    started = time.monotonic()
    _require_safe_role(role)
    if bool(tag) == bool(digest):
        raise RootfsOciError("pass exactly one of --tag or --digest")
    target = Path(target_rootfs).expanduser()
    lock_target = default_lock(target)
    if target.exists():
        raise RootfsOciError(f"target rootfs exists: {target}")
    if lock_target.exists():
        raise RootfsOciError(f"target lock exists: {lock_target}")
    package = package_for_role(role)
    ref, _ = target_reference(
        registry=registry,
        dry_run=dry_run,
        package=package,
        tag=tag,
        digest=digest,
    )
    work = Path(work_dir)
    if work.exists() and any(work.iterdir()):
        raise RootfsOciError(f"work directory must be absent or empty: {work}")
    artifact_dir = work / "artifact"
    if dry_run:
        resolved_digest, manifest = read_local_layout_manifest(
            registry=Path(registry).expanduser() if registry is not None else None,
            package=package,
            tag=tag,
            digest=digest,
        )
        materialize_local_artifact(
            registry=Path(registry).expanduser() if registry is not None else None,
            package=package,
            manifest=manifest,
            destination=artifact_dir,
        )
    else:
        resolved_digest, manifest = pull_remote_artifact(
            ref=ref,
            destination=artifact_dir,
            registry=str(registry or DEFAULT_REGISTRY),
            oras_bin=oras_bin,
        )
    annotations = _manifest_annotations(manifest)
    if annotations.get("io.sureal.artifact.kind") != "rootfs":
        raise RootfsOciError("manifest artifact kind is not rootfs")
    if annotations.get("io.sureal.rootfs.role") != role:
        raise RootfsOciError(
            f"manifest role is {annotations.get('io.sureal.rootfs.role')!r}, expected {role!r}"
        )
    payload = verify_artifact_files(artifact_dir, manifest)
    _restore_payload(payload, artifact_dir, target, tools or ArchiveTools())
    runtime = load_runtime_lock(target, lock_target)
    expected_rootfs_sha = str(payload["rootfs_sha256"])
    if runtime.data["rootfs_sha256"] != expected_rootfs_sha:
        raise RootfsOciError(
            "restored runtime lock rootfs_sha256 differs from artifact manifest: "
            f"expected {expected_rootfs_sha}, found {runtime.data['rootfs_sha256']}"
        )
    return PullResult(
        role=role,
        package=package,
        reference=ref,
        digest=resolved_digest,
        target_rootfs=target,
        target_lock=lock_target,
        rootfs_sha256=expected_rootfs_sha,
        lock_sha256=str(payload["lock_sha256"]),
        archive_sha256=str(payload["archive"]["sha256"]),
        part_count=len(payload["parts"]),
        elapsed_seconds=time.monotonic() - started,
    )


def verify_rootfs_spec(spec: RootfsSpec) -> dict[str, object]:
    """Load and report the runtime lock for one rootfs."""
    runtime = load_runtime_lock(spec.rootfs, spec.lock)
    return {
        "role": spec.role,
        "rootfs": str(runtime.rootfs),
        "lock": str(runtime.lock_path),
        "lock_sha256": runtime.lock_sha256,
        "rootfs_sha256": runtime.data["rootfs_sha256"],
        "form": runtime.form,
    }


def write_local_layout_artifact(
    *,
    registry: Path | None,
    package: str,
    tag: str,
    artifact_dir: Path,
    annotations: Mapping[str, str],
) -> str:
    """Write an OCI image layout artifact without contacting a registry."""
    if registry is None:
        raise RootfsOciError("--registry is required with --dry-run")
    _require_safe_tag(tag)
    layout = Path(registry) / package
    blobs = layout / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)
    (layout / "oci-layout").write_text(json.dumps({"imageLayoutVersion": LAYOUT_VERSION}) + "\n", encoding="utf-8")
    entries = _collect_artifact_files(artifact_dir)
    layers = []
    for entry in entries:
        src = artifact_dir / entry["path"]
        blob = blobs / entry["sha256"]
        if not blob.exists():
            shutil.copy2(src, blob)
        layers.append(
            {
                "mediaType": _media_type(str(entry["path"])),
                "digest": "sha256:" + str(entry["sha256"]),
                "size": entry["size"],
                "annotations": {
                    "org.opencontainers.image.title": entry["path"],
                    "io.sureal.file.sha256": entry["sha256"],
                    "io.sureal.file.size": str(entry["size"]),
                },
            }
        )
    config = _json_blob_bytes({"created": "1970-01-01T00:00:00Z"})
    config_digest = hashlib.sha256(config).hexdigest()
    (blobs / config_digest).write_bytes(config)
    manifest = {
        "schemaVersion": 2,
        "mediaType": MANIFEST_MEDIA_TYPE,
        "artifactType": ARTIFACT_TYPE,
        "config": {
            "mediaType": CONFIG_MEDIA_TYPE,
            "digest": "sha256:" + config_digest,
            "size": len(config),
        },
        "layers": layers,
        "annotations": dict(sorted(annotations.items())),
    }
    manifest_bytes = _json_blob_bytes(manifest)
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_blob = blobs / manifest_digest
    manifest_blob.write_bytes(manifest_bytes)
    descriptor = {
        "mediaType": MANIFEST_MEDIA_TYPE,
        "digest": "sha256:" + manifest_digest,
        "size": len(manifest_bytes),
        "annotations": {"org.opencontainers.image.ref.name": tag},
    }
    _update_index(layout / "index.json", descriptor, tag)
    return "sha256:" + manifest_digest


def read_local_layout_manifest(
    *,
    registry: Path | None,
    package: str,
    tag: str | None = None,
    digest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Read a manifest from a dry-run OCI image layout by tag or digest."""
    if registry is None:
        raise RootfsOciError("--registry is required with --dry-run")
    layout = Path(registry) / package
    digest_text = _resolve_local_digest(layout, tag=tag, digest=digest)
    blob = layout / "blobs" / "sha256" / digest_text.removeprefix("sha256:")
    manifest = _read_json_object(blob)
    return digest_text, manifest


def materialize_local_artifact(
    *,
    registry: Path | None,
    package: str,
    manifest: Mapping[str, object],
    destination: Path,
) -> None:
    """Materialize artifact layers from a local OCI image layout."""
    if registry is None:
        raise RootfsOciError("--registry is required with --dry-run")
    layout = Path(registry) / package
    blobs = layout / "blobs" / "sha256"
    destination.mkdir(parents=True, exist_ok=True)
    for layer in _manifest_layers(manifest):
        digest = str(layer["digest"]).removeprefix("sha256:")
        title = _layer_title(layer)
        src = blobs / digest
        if not src.is_file():
            raise RootfsOciError(f"missing local OCI blob: sha256:{digest}")
        dst = destination / title
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def push_remote_artifact(
    *,
    ref: str,
    package: str,
    tag: str,
    bundle: PackedBundle,
    registry: str,
    oras_bin: Path | None,
) -> str:
    """Push a staged rootfs artifact to GHCR through ORAS."""
    auth_env = prepare_remote_auth(registry=registry, oras_bin=oras_bin)
    existing = _try_remote_manifest(ref, oras_bin=oras_bin, env_extra=auth_env)
    if existing is not None:
        annotations = _manifest_annotations(existing)
        if _same_artifact_annotations(annotations, bundle.oci_annotations()):
            return resolve_remote_digest(ref, oras_bin=oras_bin, env_extra=auth_env)
        raise RootfsOciError(f"{ref}: tag already exists with different content")
    annotations = bundle.oci_annotations()
    annotation_file = bundle.artifact_dir.parent.resolve() / "oras-annotations.json"
    annotation_file.write_text(
        json.dumps({"manifest": annotations}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    command = [
        "push",
        "--artifact-type",
        ARTIFACT_TYPE,
        "--annotation-file",
        str(annotation_file),
    ]
    command.append(ref)
    for entry in _collect_artifact_files(bundle.artifact_dir):
        command.append(f"{entry['path']}:{_media_type(str(entry['path']))}")
    pushed = run_oras(command, oras_bin=oras_bin, cwd=bundle.artifact_dir, env_extra=auth_env)
    digest = _parse_digest(pushed.stdout)
    try:
        digest = resolve_remote_digest(ref, oras_bin=oras_bin, env_extra=auth_env)
    except RootfsOciError:
        pass
    check_ghcr_private(registry=registry, package=package)
    return digest


def pull_remote_artifact(
    *,
    ref: str,
    destination: Path,
    registry: str,
    oras_bin: Path | None,
) -> tuple[str, dict[str, object]]:
    """Pull a rootfs artifact from GHCR through ORAS."""
    auth_env = prepare_remote_auth(registry=registry, oras_bin=oras_bin)
    manifest = fetch_remote_manifest(ref, oras_bin=oras_bin, env_extra=auth_env)
    digest = resolve_remote_digest(ref, oras_bin=oras_bin, env_extra=auth_env)
    destination.mkdir(parents=True, exist_ok=True)
    run_oras(["pull", ref, "-o", str(destination)], oras_bin=oras_bin, env_extra=auth_env)
    return digest, manifest


def verify_artifact_files(artifact_dir: Path, manifest: Mapping[str, object]) -> dict[str, object]:
    """Verify pulled artifact layer files and return the embedded rootfs manifest."""
    layers_by_title = {_layer_title(layer): layer for layer in _manifest_layers(manifest)}
    for title, layer in sorted(layers_by_title.items()):
        path = Path(artifact_dir) / title
        if not path.is_file():
            raise RootfsOciError(f"pulled artifact is missing file: {title}")
        expected_size = int(layer["size"])
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise RootfsOciError(f"size mismatch for {title}: expected {expected_size}, found {actual_size}")
        expected_sha = str(layer["digest"]).removeprefix("sha256:")
        actual_sha = file_sha256(path)
        if actual_sha != expected_sha:
            raise RootfsOciError(f"sha256 mismatch for {title}: expected {expected_sha}, found {actual_sha}")
    manifest_path = Path(artifact_dir) / "manifest" / "rootfs-manifest.json"
    payload = _read_json_object(manifest_path)
    _validate_payload_manifest(payload, layers_by_title)
    return payload


def run_command(
    command: list[str | Path],
    *,
    cwd: Path | None = None,
    stdin: str | None = None,
    secrets: Iterable[str] = (),
    env_extra: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and redact secrets from any raised error."""
    env = dict(os.environ)
    env.pop("GHCR_TOKEN", None)
    if env_extra:
        env.update({str(key): str(value) for key, value in env_extra.items()})
    result = subprocess.run(
        [str(item) for item in command],
        cwd=str(cwd) if cwd is not None else None,
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = f"command failed rc={result.returncode}: {command[0]}"
        output = "\n".join(piece.rstrip() for piece in (result.stdout, result.stderr) if piece)
        if output:
            message += "\n" + redact(output, secrets)
        raise CommandError(message, result.returncode)
    return result


def run_oras(
    command: list[str],
    *,
    oras_bin: Path | None,
    cwd: Path | None = None,
    stdin: str | None = None,
    secrets: Iterable[str] = (),
    env_extra: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        [find_oras(oras_bin), *command],
        cwd=cwd,
        stdin=stdin,
        secrets=secrets,
        env_extra=env_extra,
    )


def install_oras(destination: Path) -> Path:
    """Install the pinned ORAS linux_amd64 binary into ``destination``."""
    destination = Path(destination).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        archive = Path(tmp) / "oras.tar.gz"
        with urllib.request.urlopen(ORAS_LINUX_AMD64_URL, timeout=60) as response:
            archive.write_bytes(response.read())
        actual = file_sha256(archive)
        if actual != ORAS_LINUX_AMD64_SHA256:
            raise RootfsOciError(
                f"ORAS archive sha256 mismatch: expected {ORAS_LINUX_AMD64_SHA256}, found {actual}"
            )
        with tarfile.open(archive, "r:gz") as tar:
            member = tar.getmember("oras")
            member.name = "oras"
            tar.extract(member, destination)
    binary = destination / "oras"
    binary.chmod(0o755)
    return binary


def find_oras(path: Path | None) -> Path:
    if path is not None:
        resolved = Path(path).expanduser()
        if resolved.is_file():
            return resolved
        raise RootfsOciError(f"oras binary not found: {resolved}")
    configured = os.environ.get("ORAS_BIN")
    if configured:
        resolved = Path(configured).expanduser()
        if resolved.is_file():
            return resolved
        raise RootfsOciError(f"oras binary not found: {resolved}")
    found = shutil.which("oras")
    if found:
        return Path(found)
    raise RootfsOciError("oras not found; run install-oras or pass --oras-bin")


def token_from_env_or_file() -> str | None:
    token = os.environ.get("GHCR_TOKEN")
    if token:
        return token
    token_file = os.environ.get("SUREAL_GHCR_TOKEN_FILE")
    if not token_file:
        return None
    path = Path(token_file).expanduser()
    mode = path.stat().st_mode & 0o777
    if mode != 0o600:
        raise RootfsOciError(f"GHCR token file must have mode 600: {path}")
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def prepare_remote_auth(*, registry: str, oras_bin: Path | None) -> dict[str, str]:
    token = token_from_env_or_file()
    if not token:
        raise RootfsOciError("set GHCR_TOKEN or SUREAL_GHCR_TOKEN_FILE")
    host = registry.rstrip("/").split("/", 1)[0]
    auth_dir = Path(tempfile.mkdtemp(prefix="sureal-oras-auth-"))
    auth_dir.chmod(0o700)
    env = {"DOCKER_CONFIG": str(auth_dir)}
    run_oras(
        ["login", host, "-u", "phi9t", "--password-stdin"],
        oras_bin=oras_bin,
        stdin=token,
        secrets=[token],
        env_extra=env,
    )
    return env


def fetch_remote_manifest(
    ref: str,
    *,
    oras_bin: Path | None,
    env_extra: Mapping[str, str] | None,
) -> dict[str, object]:
    result = run_oras(["manifest", "fetch", ref], oras_bin=oras_bin, env_extra=env_extra)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RootfsOciError("ORAS manifest fetch did not return a JSON object")
    return value


def resolve_remote_digest(
    ref: str,
    *,
    oras_bin: Path | None,
    env_extra: Mapping[str, str] | None,
) -> str:
    result = run_oras(["resolve", ref], oras_bin=oras_bin, env_extra=env_extra)
    return _parse_digest(result.stdout)


def check_ghcr_private(*, registry: str, package: str) -> None:
    token = token_from_env_or_file()
    if not token:
        raise RootfsOciError("cannot verify GHCR package visibility without a token")
    registry = registry.rstrip("/")
    parts = registry.split("/")
    if len(parts) < 2 or parts[0] != "ghcr.io":
        raise RootfsOciError(f"cannot verify package visibility for non-GHCR registry: {registry}")
    owner = parts[1]
    name = urllib.parse.quote(package, safe="")
    request = urllib.request.Request(
        f"https://api.github.com/users/{owner}/packages/container/{name}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            doc = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RootfsOciError(redact(f"failed to verify GHCR package visibility: {exc}", [token])) from exc
    visibility = doc.get("visibility") if isinstance(doc, dict) else None
    if visibility != "private":
        raise RootfsOciError(f"GHCR package {package} visibility is {visibility!r}; expected 'private'")


def target_reference(
    *,
    registry: Path | str | None,
    dry_run: bool,
    package: str,
    tag: str | None = None,
    digest: str | None = None,
) -> tuple[str, Path | None]:
    if bool(tag) == bool(digest):
        raise RootfsOciError("pass exactly one of tag or digest")
    if dry_run:
        if registry is None:
            raise RootfsOciError("--registry is required with --dry-run")
        layout = Path(registry).expanduser() / package
        if digest:
            return f"{layout}@{_normalize_digest(digest)}", layout
        return f"{layout}:{tag}", layout
    base = f"{str(registry or DEFAULT_REGISTRY).rstrip('/')}/{package}"
    if digest:
        return f"{base}@{_normalize_digest(digest)}", None
    return f"{base}:{tag}", None


def redact(text: str, secrets: Iterable[str]) -> str:
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "<redacted>")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        result = args.func(args)
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    except (OSError, RuntimeLockError, RootfsOciError, json.JSONDecodeError) as exc:
        print(redact(str(exc), [os.environ.get("GHCR_TOKEN", "")]), file=sys.stderr)
        return 1
    if isinstance(result, list):
        payload: object = [item.as_dict() if hasattr(item, "as_dict") else item for item in result]
    elif hasattr(result, "as_dict"):
        payload = result.as_dict()
    else:
        payload = result
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, (str, int, float)):
                print(f"{key}: {value}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    def common_publish(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dry-run", action="store_true", help="write an OCI layout instead of using GHCR")
        p.add_argument("--registry", help="GHCR registry root, or OCI layout root with --dry-run")
        p.add_argument("--work-dir", type=Path, required=True)
        p.add_argument("--tag")
        p.add_argument("--max-part-bytes", type=int, default=DEFAULT_MAX_PART_BYTES)
        p.add_argument("--zstd-bin", type=Path, default=None)
        p.add_argument("--tar-bin", type=Path, default=None)
        p.add_argument("--zstd-threads", type=int, default=DEFAULT_ZSTD_THREADS)
        p.add_argument("--oras-bin", type=Path, default=None)

    push = sub.add_parser("push", help="pack and publish one rootfs")
    common_publish(push)
    push.add_argument("--role", required=True)
    push.add_argument("--rootfs", type=Path, required=True)
    push.add_argument("--lock", type=Path)
    push.set_defaults(func=_main_push)

    push_active = sub.add_parser("push-active", help="pack and publish every active rootfs")
    common_publish(push_active)
    push_active.add_argument("--waymo-cache", type=Path)
    push_active.add_argument("--pathway-cache", type=Path)
    push_active.set_defaults(func=_main_push_active)

    pull = sub.add_parser("pull", help="pull and restore one rootfs")
    pull.add_argument("--dry-run", action="store_true", help="read an OCI layout instead of using GHCR")
    pull.add_argument("--registry")
    pull.add_argument("--role", required=True)
    pull.add_argument("--tag")
    pull.add_argument("--digest")
    pull.add_argument("--target-rootfs", type=Path, required=True)
    pull.add_argument("--work-dir", type=Path, required=True)
    pull.add_argument("--zstd-bin", type=Path, default=None)
    pull.add_argument("--tar-bin", type=Path, default=None)
    pull.add_argument("--zstd-threads", type=int, default=DEFAULT_ZSTD_THREADS)
    pull.add_argument("--oras-bin", type=Path, default=None)
    pull.set_defaults(func=_main_pull)

    verify = sub.add_parser("verify", help="verify a local rootfs and runtime lock")
    verify.add_argument("--role", required=True)
    verify.add_argument("--rootfs", type=Path, required=True)
    verify.add_argument("--lock", type=Path)
    verify.set_defaults(func=_main_verify)

    install = sub.add_parser("install-oras", help="download and verify the pinned ORAS binary")
    install.add_argument("--destination", type=Path, required=True)
    install.set_defaults(func=_main_install_oras)
    return parser


def _main_push(args: argparse.Namespace) -> PushResult:
    rootfs = Path(args.rootfs).expanduser()
    spec = RootfsSpec(args.role, rootfs, Path(args.lock).expanduser() if args.lock else default_lock(rootfs))
    return push_rootfs_artifact(
        spec,
        dry_run=args.dry_run,
        registry=args.registry,
        work_dir=args.work_dir.expanduser(),
        tag=args.tag,
        max_part_bytes=args.max_part_bytes,
        tools=_archive_tools(args),
        oras_bin=args.oras_bin,
    )


def _main_push_active(args: argparse.Namespace) -> list[PushResult]:
    results = []
    base = args.work_dir.expanduser()
    for spec in active_rootfs_specs(waymo_cache=args.waymo_cache, pathway_cache=args.pathway_cache):
        results.append(
            push_rootfs_artifact(
                spec,
                dry_run=args.dry_run,
                registry=args.registry,
                work_dir=base / spec.role,
                max_part_bytes=args.max_part_bytes,
                tools=_archive_tools(args),
                oras_bin=args.oras_bin,
            )
        )
    return results


def _main_pull(args: argparse.Namespace) -> PullResult:
    return pull_rootfs_artifact(
        role=args.role,
        dry_run=args.dry_run,
        registry=args.registry,
        tag=args.tag,
        digest=args.digest,
        target_rootfs=args.target_rootfs.expanduser(),
        work_dir=args.work_dir.expanduser(),
        tools=_archive_tools(args),
        oras_bin=args.oras_bin,
    )


def _main_verify(args: argparse.Namespace) -> dict[str, object]:
    rootfs = args.rootfs.expanduser()
    return verify_rootfs_spec(
        RootfsSpec(
            role=args.role,
            rootfs=rootfs,
            lock=args.lock.expanduser() if args.lock else default_lock(rootfs),
        )
    )


def _main_install_oras(args: argparse.Namespace) -> dict[str, str]:
    binary = install_oras(args.destination)
    return {
        "oras": str(binary),
        "version": ORAS_VERSION,
        "archive_sha256": ORAS_LINUX_AMD64_SHA256,
    }


def _archive_tools(args: argparse.Namespace) -> ArchiveTools:
    return ArchiveTools(
        tar_bin=args.tar_bin or "tar",
        zstd_bin=args.zstd_bin or "zstd",
        zstd_threads=args.zstd_threads,
    )


def _rootfs_file_inventory(rootfs: Path) -> list[dict[str, object]]:
    files = []
    for path in sorted(rootfs.rglob("*"), key=lambda item: item.relative_to(rootfs).as_posix()):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            continue
        files.append(
            {
                "path": path.relative_to(rootfs).as_posix(),
                "sha256": file_sha256(path),
                "size": info.st_size,
            }
        )
    return files


def _create_archive(rootfs: Path, archive: Path, tools: ArchiveTools) -> None:
    if tools.zstd_threads <= 0:
        raise RootfsOciError("--zstd-threads must be positive")
    tar_command = [
        str(tools.tar_bin),
        "--sort=name",
        f"--mtime=@{FIXED_MTIME_EPOCH}",
        "--owner=0",
        "--group=0",
        "--numeric-owner",
        "--xattrs",
        "--xattrs-include=security.capability",
        "--one-file-system",
        "-C",
        str(rootfs),
        "-cf",
        "-",
        ".",
    ]
    zstd_command = [
        str(tools.zstd_bin),
        "-19",
        f"-T{tools.zstd_threads}",
        "--no-progress",
        "-o",
        str(archive),
        "-",
    ]
    tar_proc = subprocess.Popen(tar_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
    zstd_proc: subprocess.Popen[bytes] | None = None
    try:
        assert tar_proc.stdout is not None
        zstd_proc = subprocess.Popen(
            zstd_command,
            stdin=tar_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
        )
        tar_proc.stdout.close()
        _, zstd_stderr = zstd_proc.communicate()
        tar_stderr = tar_proc.stderr.read() if tar_proc.stderr is not None else b""
        tar_return = tar_proc.wait()
    finally:
        if tar_proc.stdout is not None and not tar_proc.stdout.closed:
            tar_proc.stdout.close()
        if tar_proc.stderr is not None and not tar_proc.stderr.closed:
            tar_proc.stderr.close()
        if zstd_proc is not None and zstd_proc.stderr is not None and not zstd_proc.stderr.closed:
            zstd_proc.stderr.close()
    if tar_return != 0:
        raise CommandError(
            "command failed rc=%d: %s\n%s"
            % (tar_return, tar_command[0], tar_stderr.decode("utf-8", "replace")),
            tar_return,
        )
    if zstd_proc.returncode != 0:
        output = zstd_stderr or b""
        raise CommandError(
            "command failed rc=%d: %s\n%s" % (zstd_proc.returncode, zstd_command[0], output.decode("utf-8", "replace")),
            zstd_proc.returncode,
        )


def _extract_archive(archive: Path, destination: Path, tools: ArchiveTools) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    zstd_command = [str(tools.zstd_bin), "-d", "-c", str(archive)]
    tar_command = [str(tools.tar_bin), "-C", str(destination), "-xf", "-"]
    zstd_proc = subprocess.Popen(zstd_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
    tar_proc: subprocess.Popen[bytes] | None = None
    try:
        assert zstd_proc.stdout is not None
        tar_proc = subprocess.Popen(
            tar_command,
            stdin=zstd_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
        )
        zstd_proc.stdout.close()
        _, tar_stderr = tar_proc.communicate()
        zstd_stderr = zstd_proc.stderr.read() if zstd_proc.stderr is not None else b""
        zstd_return = zstd_proc.wait()
    finally:
        if zstd_proc.stdout is not None and not zstd_proc.stdout.closed:
            zstd_proc.stdout.close()
        if zstd_proc.stderr is not None and not zstd_proc.stderr.closed:
            zstd_proc.stderr.close()
        if tar_proc is not None and tar_proc.stderr is not None and not tar_proc.stderr.closed:
            tar_proc.stderr.close()
    if zstd_return != 0:
        raise CommandError(
            "command failed rc=%d: %s\n%s" % (zstd_return, zstd_command[0], zstd_stderr.decode("utf-8", "replace")),
            zstd_return,
        )
    if tar_proc is not None and tar_proc.returncode != 0:
        output = tar_stderr or b""
        raise CommandError(
            "command failed rc=%d: %s\n%s" % (tar_proc.returncode, tar_command[0], output.decode("utf-8", "replace")),
            tar_proc.returncode,
        )


def _split_file(src: Path, dst_dir: Path, archive_name: str, max_bytes: int) -> list[dict[str, object]]:
    parts = []
    with src.open("rb") as inp:
        index = 0
        while True:
            chunk = inp.read(max_bytes)
            if not chunk:
                break
            rel = f"rootfs/{archive_name}.part{index:04d}"
            dst = dst_dir / Path(rel).name
            dst.write_bytes(chunk)
            parts.append({"path": rel, "sha256": hashlib.sha256(chunk).hexdigest(), "size": len(chunk)})
            index += 1
    if not parts:
        rel = f"rootfs/{archive_name}.part0000"
        dst = dst_dir / Path(rel).name
        dst.write_bytes(b"")
        parts.append({"path": rel, "sha256": hashlib.sha256(b"").hexdigest(), "size": 0})
    return parts


def _restore_payload(payload: Mapping[str, object], artifact_dir: Path, target: Path, tools: ArchiveTools) -> None:
    archive = _reassemble_archive(payload, artifact_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    # The staged tree keeps the target's basename (and parent path): load_runtime_lock
    # selects the recipe spec from the rootfs name, so a renamed stage would be
    # checked against the wrong recipe.
    stage_root = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore.", dir=target.parent))
    stage = stage_root / target.name
    lock_stage = default_lock(stage)
    try:
        _extract_archive(archive, stage, tools)
        lock_payload = _payload_lock(payload)
        shutil.copy2(artifact_dir / lock_payload["path"], lock_stage)
        try:
            load_runtime_lock(stage, lock_stage)
        except RuntimeLockError as exc:
            raise RootfsOciError(str(exc)) from exc
        if target.exists():
            raise RootfsOciError(f"target rootfs exists: {target}")
        if default_lock(target).exists():
            raise RootfsOciError(f"target lock exists: {default_lock(target)}")
        stage.rename(target)
        lock_stage.rename(default_lock(target))
        stage_root.rmdir()
    except Exception:
        raise


def _reassemble_archive(payload: Mapping[str, object], artifact_dir: Path) -> Path:
    archive_info = _payload_archive(payload)
    parts = _payload_parts(payload)
    archive = Path(artifact_dir) / archive_info["path"]
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as out:
        for part in parts:
            src = Path(artifact_dir) / str(part["path"])
            actual = file_sha256(src)
            if actual != part["sha256"]:
                raise RootfsOciError(
                    f"sha256 mismatch for {part['path']}: expected {part['sha256']}, found {actual}"
                )
            with src.open("rb") as inp:
                shutil.copyfileobj(inp, out, 1024 * 1024)
    actual_size = archive.stat().st_size
    expected_size = int(archive_info["size"])
    if actual_size != expected_size:
        raise RootfsOciError(f"rootfs archive size mismatch: expected {expected_size}, found {actual_size}")
    actual_sha = file_sha256(archive)
    if actual_sha != archive_info["sha256"]:
        raise RootfsOciError(
            f"rootfs archive sha256 mismatch: expected {archive_info['sha256']}, found {actual_sha}"
        )
    return archive


def _validate_payload_manifest(
    payload: Mapping[str, object],
    layers_by_title: Mapping[str, Mapping[str, object]],
) -> None:
    if payload.get("schema_version") != 1:
        raise RootfsOciError("rootfs manifest schema_version must be 1")
    for key in ("role", "rootfs_name", "rootfs_sha256", "lock_sha256", "archive", "parts", "lock"):
        if key not in payload:
            raise RootfsOciError(f"rootfs manifest missing {key}")
    _normalize_sha256_hex(str(payload["rootfs_sha256"]), "rootfs sha256")
    _normalize_sha256_hex(str(payload["lock_sha256"]), "lock sha256")
    required_paths = {str(part["path"]) for part in _payload_parts(payload)}
    required_paths.add(str(_payload_lock(payload)["path"]))
    required_paths.add("manifest/rootfs-manifest.json")
    for path in sorted(required_paths):
        if path not in layers_by_title:
            raise RootfsOciError(f"rootfs manifest references missing artifact file: {path}")
    for item in [*_payload_parts(payload), _payload_lock(payload)]:
        _require_manifest_file_matches_layer(item, layers_by_title)
    lock_info = _payload_lock(payload)
    lock_path = Path(str(lock_info["path"]))
    if _unsafe_relative(lock_path.as_posix()):
        raise RootfsOciError(f"unsafe lock path: {lock_path}")
    rootfs_files = payload.get("rootfs_files")
    if not isinstance(rootfs_files, list):
        raise RootfsOciError("rootfs manifest rootfs_files must be a list")
    for entry in rootfs_files:
        if not isinstance(entry, Mapping):
            raise RootfsOciError("rootfs manifest rootfs_files entry must be an object")
        for key in ("path", "sha256", "size"):
            if key not in entry:
                raise RootfsOciError(f"rootfs manifest rootfs_files entry missing {key}")
        if _unsafe_relative(str(entry["path"])):
            raise RootfsOciError(f"unsafe rootfs file path: {entry['path']}")
        _normalize_sha256_hex(str(entry["sha256"]), "rootfs file sha256")


def _require_manifest_file_matches_layer(
    item: Mapping[str, object],
    layers_by_title: Mapping[str, Mapping[str, object]],
) -> None:
    path = str(item["path"])
    layer = layers_by_title[path]
    expected_digest = _normalize_sha256_hex(str(item["sha256"]), "artifact file sha256")
    layer_digest = str(layer["digest"]).removeprefix("sha256:")
    if layer_digest != expected_digest:
        raise RootfsOciError(
            f"rootfs manifest sha256 differs from layer {path}: "
            f"expected {expected_digest}, found {layer_digest}"
        )
    expected_size = int(item["size"])
    if int(layer["size"]) != expected_size:
        raise RootfsOciError(
            f"rootfs manifest size differs from layer {path}: "
            f"expected {expected_size}, found {layer['size']}"
        )


def _payload_archive(payload: Mapping[str, object]) -> Mapping[str, object]:
    archive = payload.get("archive")
    if not isinstance(archive, Mapping):
        raise RootfsOciError("rootfs manifest archive must be an object")
    for key in ("path", "sha256", "size"):
        if key not in archive:
            raise RootfsOciError(f"rootfs manifest archive missing {key}")
    _normalize_sha256_hex(str(archive["sha256"]), "archive sha256")
    path = str(archive["path"])
    if _unsafe_relative(path):
        raise RootfsOciError(f"unsafe archive path: {path}")
    return archive


def _payload_lock(payload: Mapping[str, object]) -> Mapping[str, object]:
    lock = payload.get("lock")
    if not isinstance(lock, Mapping):
        raise RootfsOciError("rootfs manifest lock must be an object")
    for key in ("path", "sha256", "size"):
        if key not in lock:
            raise RootfsOciError(f"rootfs manifest lock missing {key}")
    _normalize_sha256_hex(str(lock["sha256"]), "lock sha256")
    path = str(lock["path"])
    if _unsafe_relative(path):
        raise RootfsOciError(f"unsafe lock path: {path}")
    return lock


def _payload_parts(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    parts = payload.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RootfsOciError("rootfs manifest parts must be a non-empty list")
    result = []
    for part in parts:
        if not isinstance(part, Mapping):
            raise RootfsOciError("rootfs manifest part must be an object")
        for key in ("path", "sha256", "size"):
            if key not in part:
                raise RootfsOciError(f"rootfs manifest part missing {key}")
        path = str(part["path"])
        if _unsafe_relative(path):
            raise RootfsOciError(f"unsafe part path: {path}")
        _normalize_sha256_hex(str(part["sha256"]), "part sha256")
        result.append(part)
    return result


def _collect_artifact_files(root: Path) -> list[dict[str, object]]:
    entries = []
    for path in sorted(Path(root).rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if _unsafe_relative(rel) or not SAFE_LAYER_PATH_RE.fullmatch(rel):
            raise RootfsOciError(f"unsafe artifact path: {rel}")
        entries.append({"path": rel, "sha256": file_sha256(path), "size": path.stat().st_size})
    if not entries:
        raise RootfsOciError(f"no artifact files found under {root}")
    return entries


def _artifact_file_annotations(entries: Iterable[Mapping[str, object]]) -> dict[str, str]:
    annotations = {}
    entries = list(entries)
    annotations["io.sureal.file.count"] = str(len(entries))
    for index, entry in enumerate(entries):
        prefix = f"io.sureal.file.{index:04d}"
        annotations[f"{prefix}.path"] = str(entry["path"])
        annotations[f"{prefix}.sha256"] = str(entry["sha256"])
        annotations[f"{prefix}.size"] = str(entry["size"])
    return annotations


def _rootfs_entry_annotations(entries: Iterable[Mapping[str, object]]) -> dict[str, str]:
    annotations = {}
    entries = list(entries)
    annotations["io.sureal.rootfs.entry.count"] = str(len(entries))
    for index, entry in enumerate(entries):
        prefix = f"io.sureal.rootfs.entry.{index:06d}"
        annotations[f"{prefix}.path"] = str(entry["path"])
        annotations[f"{prefix}.sha256"] = str(entry["sha256"])
        annotations[f"{prefix}.size"] = str(entry["size"])
    return annotations


def _update_index(index_path: Path, descriptor: Mapping[str, object], tag: str) -> None:
    try:
        index = _read_json_object(index_path)
    except FileNotFoundError:
        index = {"schemaVersion": 2, "manifests": []}
    manifests = index.get("manifests")
    if not isinstance(manifests, list):
        raise RootfsOciError("OCI index manifests must be a list")
    kept = []
    for item in manifests:
        if not isinstance(item, Mapping):
            raise RootfsOciError("OCI index manifest descriptor must be an object")
        annotations = item.get("annotations")
        item_tag = annotations.get("org.opencontainers.image.ref.name") if isinstance(annotations, Mapping) else None
        if item_tag != tag:
            kept.append(item)
            continue
        if item.get("digest") == descriptor["digest"]:
            index["manifests"] = [*kept, item, *manifests[len(kept) + 1 :]]
            index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return
        raise RootfsOciError(f"{tag}: tag already exists with different content")
    index["schemaVersion"] = 2
    index["manifests"] = [*kept, descriptor]
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_local_digest(layout: Path, *, tag: str | None, digest: str | None) -> str:
    if digest:
        return _normalize_digest(digest)
    _require_safe_tag(str(tag))
    index = _read_json_object(layout / "index.json")
    manifests = index.get("manifests")
    if not isinstance(manifests, list):
        raise RootfsOciError("OCI index manifests must be a list")
    for item in manifests:
        if not isinstance(item, Mapping):
            continue
        annotations = item.get("annotations")
        if isinstance(annotations, Mapping) and annotations.get("org.opencontainers.image.ref.name") == tag:
            return _normalize_digest(str(item.get("digest")))
    raise RootfsOciError(f"{tag}: tag not found in local OCI layout")


def _manifest_layers(manifest: Mapping[str, object]) -> list[Mapping[str, object]]:
    layers = manifest.get("layers")
    if not isinstance(layers, list):
        raise RootfsOciError("manifest layers must be a list")
    result = []
    for layer in layers:
        if not isinstance(layer, Mapping):
            raise RootfsOciError("manifest layer must be an object")
        if "digest" not in layer or "size" not in layer:
            raise RootfsOciError("manifest layer digest and size required")
        result.append(layer)
    return result


def _manifest_annotations(manifest: Mapping[str, object]) -> Mapping[str, str]:
    annotations = manifest.get("annotations")
    if not isinstance(annotations, Mapping):
        raise RootfsOciError("manifest annotations required")
    return {str(key): str(value) for key, value in annotations.items()}


def _layer_title(layer: Mapping[str, object]) -> str:
    annotations = layer.get("annotations")
    if not isinstance(annotations, Mapping):
        raise RootfsOciError("manifest layer annotations required")
    title = str(annotations.get("org.opencontainers.image.title") or "")
    if _unsafe_relative(title):
        raise RootfsOciError(f"unsafe layer title: {title}")
    return title


def _media_type(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".tar.zst") or ".tar.zst.part" in path:
        return "application/vnd.sureal.rootfs.layer.v1+zstd"
    return "application/octet-stream"


def _json_blob_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _read_json_object(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RootfsOciError(f"{path}: expected a JSON object")
    return value


def _same_artifact_annotations(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    keys = {
        "io.sureal.rootfs.lock.sha256",
        "io.sureal.rootfs.rootfs.sha256",
        "io.sureal.rootfs.archive.sha256",
        "io.sureal.rootfs.manifest.sha256",
        "io.sureal.rootfs.part.count",
    }
    return all(left.get(key) == right.get(key) for key in keys)


def _try_remote_manifest(
    ref: str,
    *,
    oras_bin: Path | None,
    env_extra: Mapping[str, str] | None,
) -> dict[str, object] | None:
    try:
        return fetch_remote_manifest(ref, oras_bin=oras_bin, env_extra=env_extra)
    except CommandError:
        return None


def _parse_digest(text: str) -> str:
    match = re.search(r"sha256:[0-9a-f]{64}", text)
    if match is None:
        raise RootfsOciError(f"could not find digest in output: {text.strip()}")
    return match.group(0)


def _require_safe_role(role: str) -> None:
    if ROLE_RE.fullmatch(role) is None:
        raise RootfsOciError(f"unsafe rootfs role: {role!r}")


def _require_safe_tag(tag: str) -> None:
    if TAG_RE.fullmatch(tag) is None:
        raise RootfsOciError(f"not a valid OCI tag: {tag!r}")


def _normalize_sha256_hex(value: str, label: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RootfsOciError(f"invalid {label}: {value!r}")
    return value


def _normalize_digest(value: str) -> str:
    if DIGEST_RE.fullmatch(value) is None:
        raise RootfsOciError(f"invalid sha256 digest: {value!r}")
    return value if value.startswith("sha256:") else "sha256:" + value


def _unsafe_relative(path: str) -> bool:
    return (
        not path
        or path in {".", ".."}
        or path.startswith("/")
        or path.startswith("../")
        or "/../" in path
        or "\x00" in path
    )


if __name__ == "__main__":
    raise SystemExit(main())
