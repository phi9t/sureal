"""Backend-neutral, write-once storage for evidence blobs."""

import hashlib
import json
import os
import pwd
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol


MAX_ATTEMPTS = 3
DEFAULT_DEADLINE_BASE_SECONDS = 5.0
DEFAULT_MINIMUM_THROUGHPUT_BYTES_PER_SECOND = 1024 * 1024
DEFAULT_BACKOFF_SECONDS = (0.25, 1.0)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
BLOB_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")
DEFAULT_WAYSTONE_LAYOUT_DEADLINE_SECONDS = 30.0
MISSING_MARKERS = (
    "does not exist",
    "file not found",
    "no such file",
)
CONFLICT_MARKERS = (
    "already exists",
    "file exists",
)
WAYSTONE_TRANSIENT_ERROR_CLASSES = ("external", "transfer")
WAYSTONE_PERMANENT_UNAVAILABLE_ERROR_CLASSES = ("usage", "verification")
WAYSTONE_SIZE_KEYS = (
    "bytes",
    "size",
    "length",
    "file_size",
    "fileSize",
    "content_length",
    "contentLength",
)
DEFAULT_WAYSTONE_RELATIVE = "workspace/waystone/scripts/waystone"
DEFAULT_HADOOP_CONF_DIR = "/opt/tiger/yarn_deploy/hadoop/conf"
DEFAULT_HDFS_AUTH_REFRESH = Path(__file__).resolve().parents[1] / "resources/refresh-hdfs-auth.sh"
WAYSTONE_TOOL_RELATIVES = (
    "rust/target/debug/waystone",
    "native/libhdfs_client/dist/lib/libhdfs_client.so",
    "native/libhdfs_client/dist/bin/hdfs.bin",
)


class BlobStoreError(RuntimeError):
    """Base class for blob store failures."""


class Missing(BlobStoreError):
    """The requested blob key does not exist."""


class Conflict(BlobStoreError):
    """The blob key is already bound to different bytes."""


class Corrupt(BlobStoreError):
    """A blob's bytes did not match the expected digest."""


class Unauthenticated(BlobStoreError):
    """Blob storage credentials need refreshing."""


class Unavailable(BlobStoreError):
    """The backing store did not complete the operation."""


class _PrimitiveError(Exception):
    pass


class _PrimitiveMissing(_PrimitiveError):
    pass


class _PrimitiveConflict(_PrimitiveError):
    pass


class _PrimitiveCorrupt(_PrimitiveError):
    pass


class _PrimitiveUnauthenticated(_PrimitiveError):
    pass


class _PrimitiveTransient(_PrimitiveError):
    pass


class _PrimitivePermanentUnavailable(_PrimitiveError):
    pass


class _PrimitiveUnavailable(_PrimitiveTransient):
    pass


class _PrimitiveTimeout(_PrimitiveTransient):
    pass


@dataclass(frozen=True)
class _OperationContext:
    deadline_at: float
    clock: Callable[[], float]
    sleep: Callable[[float], None]

    def check_deadline(self) -> None:
        if self.clock() > self.deadline_at:
            raise _PrimitiveTimeout("blob operation deadline expired")

    def elapse(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("delay seconds must be non-negative")
        if seconds:
            self.sleep(seconds)
        self.check_deadline()


class _BlobAdapter(Protocol):
    """Primitive adapter seam beneath the three-operation blob store.

    Adapters whose primitives can block must enforce ``context.deadline_at``
    themselves; ticket 02's Waystone adapter will pass it as a subprocess
    timeout and kill the process group on expiry.
    """

    def _upload_blob(self, key: str, source: Path, context: _OperationContext) -> None: ...
    def _download_blob(self, key: str, destination: Path, context: _OperationContext) -> None: ...
    def _blob_size(self, key: str, context: _OperationContext) -> int: ...
    def _blob_exists(self, key: str, context: _OperationContext) -> bool: ...


class BlobStore:
    def __init__(
        self,
        adapter: _BlobAdapter,
        *,
        deadline_base_seconds: float = DEFAULT_DEADLINE_BASE_SECONDS,
        minimum_throughput_bytes_per_second: float = DEFAULT_MINIMUM_THROUGHPUT_BYTES_PER_SECOND,
        max_attempts: int = MAX_ATTEMPTS,
        backoff_seconds=DEFAULT_BACKOFF_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if deadline_base_seconds < 0:
            raise ValueError("deadline base seconds must be non-negative")
        if minimum_throughput_bytes_per_second <= 0:
            raise ValueError("minimum throughput must be positive")
        if max_attempts < 1:
            raise ValueError("max attempts must be positive")
        self._adapter = adapter
        self._deadline_base_seconds = float(deadline_base_seconds)
        self._minimum_throughput_bytes_per_second = float(minimum_throughput_bytes_per_second)
        self._max_attempts = int(max_attempts)
        self._backoff_seconds = tuple(float(value) for value in backoff_seconds)
        self._clock = clock
        self._sleep = sleep

    def put(self, key, file):
        key = validate_blob_key(key)
        source = _require_regular_file(file)
        source_sha256, source_bytes = _file_sha256_and_size(source)

        def attempt():
            existing_error = None
            try:
                self._call_primitive(
                    source_bytes,
                    lambda context: self._adapter._upload_blob(key, source, context),
                )
            except _PrimitiveConflict as error:
                existing_error = error

            with tempfile.TemporaryDirectory(prefix="blob-store-readback.") as directory:
                readback = Path(directory) / "blob"
                try:
                    self._call_primitive(
                        source_bytes,
                        lambda context: self._adapter._download_blob(key, readback, context),
                    )
                except _PrimitiveMissing as error:
                    raise _PrimitiveCorrupt("blob readback missing") from error
                readback_sha256, readback_bytes = _file_sha256_and_size(readback)

            if readback_sha256 != source_sha256 or readback_bytes != source_bytes:
                if existing_error is not None:
                    raise Conflict("blob key already holds different bytes: " + key) from existing_error
                raise _PrimitiveCorrupt("blob readback digest mismatch")
            return {"key": key, "sha256": source_sha256, "bytes": source_bytes}

        return self._with_retries("put", key, attempt)

    def get(self, key, dest, sha256, *, expected_bytes=None):
        key = validate_blob_key(key)
        expected_sha256 = _require_sha256(sha256)
        if expected_bytes is not None and (type(expected_bytes) is not int or expected_bytes < 0):
            raise ValueError("expected byte count must be a non-negative integer")
        destination = Path(dest)

        def attempt():
            size = self._call_primitive(0, lambda context: self._adapter._blob_size(key, context))
            if expected_bytes is not None and size != expected_bytes:
                raise _PrimitiveCorrupt("blob byte count mismatch")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent,
                    prefix="." + destination.name + ".",
                    suffix=".tmp",
                    delete=False,
                ) as output:
                    temporary = Path(output.name)
                self._call_primitive(
                    size,
                    lambda context: self._adapter._download_blob(key, temporary, context),
                )
                actual_sha256, actual_bytes = _file_sha256_and_size(temporary)
                if actual_sha256 != expected_sha256 or (
                    expected_bytes is not None and actual_bytes != expected_bytes
                ):
                    raise _PrimitiveCorrupt("blob digest mismatch")
                os.replace(temporary, destination)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        return self._with_retries("get", key, attempt)

    def exists(self, key):
        key = validate_blob_key(key)

        def attempt():
            return bool(
                self._call_primitive(
                    0,
                    lambda context: self._adapter._blob_exists(key, context),
                )
            )

        return self._with_retries("exists", key, attempt)

    def _deadline_seconds(self, byte_count: int) -> float:
        return self._deadline_base_seconds + max(0, int(byte_count)) / self._minimum_throughput_bytes_per_second

    def _call_primitive(self, byte_count: int, operation):
        context = _OperationContext(
            deadline_at=self._clock() + self._deadline_seconds(byte_count),
            clock=self._clock,
            sleep=self._sleep,
        )
        context.check_deadline()
        result = operation(context)
        context.check_deadline()
        return result

    def _with_retries(self, operation_name: str, key: str, operation):
        for attempt in range(1, self._max_attempts + 1):
            try:
                return operation()
            except BlobStoreError:
                raise
            except _PrimitiveMissing as error:
                raise Missing("blob missing: " + key) from error
            except _PrimitiveConflict as error:
                raise Conflict("blob key already exists: " + key) from error
            except _PrimitiveCorrupt as error:
                raise Corrupt("blob bytes failed verification: " + key) from error
            except _PrimitiveUnauthenticated as error:
                raise Unauthenticated(
                    "blob store authentication failed; " + self._authentication_action()
                ) from error
            except _PrimitivePermanentUnavailable as error:
                raise Unavailable("blob store " + operation_name + " unavailable") from error
            except (_PrimitiveTransient, TimeoutError, OSError) as error:
                if attempt == self._max_attempts:
                    raise Unavailable(
                        "blob store "
                        + operation_name
                        + " unavailable after "
                        + str(self._max_attempts)
                        + " attempts"
                    ) from error
                self._sleep(self._backoff_for_attempt(attempt))
            except Exception as error:
                raise Unavailable("blob store " + operation_name + " unavailable") from error
        raise Unavailable("blob store " + operation_name + " unavailable")

    def _authentication_action(self) -> str:
        action = getattr(self._adapter, "authentication_action", None)
        if callable(action):
            action = action()
        if isinstance(action, str) and action.strip():
            return action.strip()
        return "refresh blob store credentials"

    def _backoff_for_attempt(self, attempt: int) -> float:
        if not self._backoff_seconds:
            return 0.0
        index = min(attempt - 1, len(self._backoff_seconds) - 1)
        return self._backoff_seconds[index]


class InMemoryBlobAdapter:
    def __init__(
        self,
        blobs: Mapping[str, bytes] | None = None,
        *,
        delay_seconds: float = 0.0,
        transient_failures: int = 0,
        unauthenticated: bool = False,
        authentication_action: str = "refresh in-memory blob store credentials",
    ):
        self._blobs = {validate_blob_key(key): bytes(value) for key, value in (blobs or {}).items()}
        self._delay_seconds = float(delay_seconds)
        self._transient_failures = int(transient_failures)
        self._unauthenticated = bool(unauthenticated)
        self.authentication_action = authentication_action

    def _upload_blob(self, key: str, source: Path, context: _OperationContext) -> None:
        self._before_operation(context)
        if key in self._blobs:
            raise _PrimitiveConflict("blob exists")
        self._blobs[key] = Path(source).read_bytes()

    def _download_blob(self, key: str, destination: Path, context: _OperationContext) -> None:
        self._before_operation(context)
        try:
            data = self._blobs[key]
        except KeyError as error:
            raise _PrimitiveMissing("blob missing") from error
        Path(destination).write_bytes(data)

    def _blob_size(self, key: str, context: _OperationContext) -> int:
        self._before_operation(context)
        try:
            return len(self._blobs[key])
        except KeyError as error:
            raise _PrimitiveMissing("blob missing") from error

    def _blob_exists(self, key: str, context: _OperationContext) -> bool:
        self._before_operation(context)
        return key in self._blobs

    def _before_operation(self, context: _OperationContext) -> None:
        if self._unauthenticated:
            raise _PrimitiveUnauthenticated("authentication failed")
        if self._transient_failures > 0:
            self._transient_failures -= 1
            raise _PrimitiveTransient("transient failure")
        context.elapse(self._delay_seconds)


class LocalFileBlobAdapter:
    def __init__(self, root):
        self.root = Path(root)

    def _upload_blob(self, key: str, source: Path, context: _OperationContext) -> None:
        path = self._path_for_key(key)
        self._ensure_parent(path.parent, context)
        self._reject_symlink_ancestry(path.parent)
        if path.exists() or path.is_symlink():
            raise _PrimitiveConflict("blob exists")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=path.parent,
                prefix="." + path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                with Path(source).open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
            context.check_deadline()
            self._reject_symlink_ancestry(path.parent)
            _link_no_replace(temporary, path)
            temporary.unlink()
            temporary = None
            context.check_deadline()
        except FileExistsError as error:
            raise _PrimitiveConflict("blob exists") from error
        except OSError as error:
            raise _PrimitiveUnavailable("local blob write failed") from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _download_blob(self, key: str, destination: Path, context: _OperationContext) -> None:
        path = self._existing_blob_path(key)
        try:
            shutil.copyfile(path, destination)
        except FileNotFoundError as error:
            raise _PrimitiveMissing("blob missing") from error
        except OSError as error:
            raise _PrimitiveUnavailable("local blob read failed") from error
        context.check_deadline()

    def _blob_size(self, key: str, context: _OperationContext) -> int:
        path = self._existing_blob_path(key)
        context.check_deadline()
        return path.stat().st_size

    def _blob_exists(self, key: str, context: _OperationContext) -> bool:
        path = self._path_for_key(key)
        self._reject_symlink_ancestry(path)
        context.check_deadline()
        if not path.exists():
            return False
        if not path.is_file():
            raise _PrimitiveUnavailable("local blob path is not a file")
        return True

    def _existing_blob_path(self, key: str) -> Path:
        path = self._path_for_key(key)
        self._reject_symlink_ancestry(path)
        if not path.exists():
            raise _PrimitiveMissing("blob missing")
        if not path.is_file():
            raise _PrimitiveUnavailable("local blob path is not a file")
        return path

    def _path_for_key(self, key: str) -> Path:
        segments = validate_blob_key(key).split("/")
        return self.root.joinpath(*segments)

    def _ensure_parent(self, parent: Path, context: _OperationContext) -> None:
        self._reject_symlink_ancestry(self.root)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise _PrimitiveUnavailable("local blob root unavailable") from error
        self._reject_symlink_ancestry(self.root)
        if not self.root.is_dir():
            raise _PrimitiveUnavailable("local blob root is not a directory")

        relative_parent = parent.relative_to(self.root)
        current = self.root
        for segment in relative_parent.parts:
            current = current / segment
            if current.is_symlink():
                raise _PrimitiveUnavailable("local blob path uses a symlink")
            if current.exists():
                if not current.is_dir():
                    raise _PrimitiveUnavailable("local blob parent is not a directory")
            else:
                try:
                    current.mkdir()
                except OSError as error:
                    raise _PrimitiveUnavailable("local blob parent unavailable") from error
            context.check_deadline()

    def _reject_symlink_ancestry(self, path: Path) -> None:
        for candidate in _path_ancestry(self.root, path):
            if candidate.is_symlink():
                raise _PrimitiveUnavailable("local blob path uses a symlink")


class WaystoneBlobAdapter:
    def __init__(
        self,
        *,
        project: str = "sureal",
        command_prefix=None,
        tool_pins: Mapping[str, str] | None = None,
        key_prefix: str | None = None,
        legacy_prefix: str | None = None,
        hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
        authentication_action: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.project = _require_descriptor_name(project, "Waystone project")
        self.command_prefix = _waystone_command_prefix(command_prefix)
        self._tool_pins = _validate_tool_pins(
            waystone_tool_pins(Path(self.command_prefix[0])) if tool_pins is None else tool_pins
        )
        self._key_prefix = validate_blob_key(key_prefix) if key_prefix else None
        self._legacy_prefix = _normalize_hdfs_prefix(legacy_prefix) if legacy_prefix else None
        self._hadoop_conf_dir = str(hadoop_conf_dir)
        self.authentication_action = str(authentication_action or DEFAULT_HDFS_AUTH_REFRESH)
        self._clock = clock
        self._layout = None
        self._tool_pin_stats = {}

    @property
    def tool_sha256(self) -> dict[str, str]:
        return dict(self._tool_pins)

    def _upload_blob(self, key: str, source: Path, context: _OperationContext) -> None:
        uri = self._uri_for_key(key, context)
        result = self._run(
            [
                "put",
                "--auth-source",
                "token-file",
                "--command-timeout-secs",
                str(self._command_timeout_seconds(context)),
                "--mkdir-parents",
                str(source),
                uri,
            ],
            context,
        )
        if result.returncode != 0:
            self._raise_waystone_failure(result, missing=False, conflict=True)

    def _download_blob(self, key: str, destination: Path, context: _OperationContext) -> None:
        uri = self._uri_for_key(key, context)
        result = self._run(
            [
                "get",
                "--auth-source",
                "token-file",
                "--command-timeout-secs",
                str(self._command_timeout_seconds(context)),
                "--overwrite",
                uri,
                str(destination),
            ],
            context,
        )
        if result.returncode != 0:
            self._raise_waystone_failure(result, missing=True, conflict=False)

    def _blob_size(self, key: str, context: _OperationContext) -> int:
        uri = self._uri_for_key(key, context)
        result = self._run(
            [
                "ls",
                "--auth-source",
                "token-file",
                "--command-timeout-secs",
                str(self._command_timeout_seconds(context)),
                "--output",
                "json",
                uri,
            ],
            context,
        )
        if result.returncode != 0:
            self._raise_waystone_failure(result, missing=True, conflict=False)
        return _waystone_blob_size(result.stdout)

    def _blob_exists(self, key: str, context: _OperationContext) -> bool:
        uri = self._uri_for_key(key, context)
        result = self._run(
            [
                "ls",
                "--auth-source",
                "token-file",
                "--command-timeout-secs",
                str(self._command_timeout_seconds(context)),
                "--output",
                "json",
                uri,
            ],
            context,
        )
        if result.returncode == 0:
            return _waystone_blob_exists(result.stdout)
        try:
            self._raise_waystone_failure(result, missing=True, conflict=False)
        except _PrimitiveMissing:
            return False
        return False

    def blob_key_from_uri(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("blob key or HDFS URI required")
        if not value.startswith("hdfs://"):
            return validate_blob_key(value)
        prefixes = []
        if self._legacy_prefix is not None:
            prefixes.append(self._legacy_prefix)
        layout = self._layout_profile()
        self._validate_legacy_prefix(layout)
        prefixes.append(_normalize_hdfs_prefix(layout["project_root"]))
        prefixes.append(_normalize_hdfs_prefix(layout["storage_root"]) + "/" + self.project)
        for prefix in sorted(set(prefixes), key=len, reverse=True):
            candidate_prefix = prefix + "/"
            if value == prefix:
                raise ValueError("absolute HDFS URI does not name a blob")
            if value.startswith(candidate_prefix):
                return validate_blob_key(value[len(candidate_prefix) :])
        raise ValueError("absolute HDFS URI is outside the Waystone project root")

    def _uri_for_key(self, key: str, context: _OperationContext | None = None) -> str:
        key = validate_blob_key(key)
        if self._key_prefix is not None:
            key = self._key_prefix + "/" + key
        return _normalize_hdfs_prefix(self._layout_profile(context)["project_root"]) + "/" + key

    def _layout_profile(self, context: _OperationContext | None = None) -> dict:
        if self._layout is None:
            context = self._layout_context(context)
            result = self._run(
                [
                    "layout-profile",
                    "--project",
                    self.project,
                    "--json",
                ],
                context,
            )
            if result.returncode != 0:
                self._raise_waystone_failure(result, missing=False, conflict=False)
            try:
                layout = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                raise _PrimitiveUnavailable("Waystone layout unavailable") from error
            if layout.get("project") != self.project:
                raise _PrimitiveUnavailable("Waystone layout project mismatch")
            project_root = _normalize_hdfs_prefix(layout.get("project_root"))
            storage_root = _normalize_hdfs_prefix(layout.get("storage_root"))
            if not project_root.startswith(storage_root + "/"):
                raise _PrimitiveUnavailable("Waystone layout root mismatch")
            self._layout = {
                "project": self.project,
                "storage_root": storage_root,
                "project_root": project_root,
            }
            self._validate_legacy_prefix(self._layout)
        return dict(self._layout)

    def _layout_context(self, context: _OperationContext | None) -> _OperationContext:
        if context is not None:
            return context
        return _OperationContext(
            deadline_at=self._clock() + DEFAULT_WAYSTONE_LAYOUT_DEADLINE_SECONDS,
            clock=self._clock,
            sleep=time.sleep,
        )

    def _validate_legacy_prefix(self, layout: Mapping[str, str] | None = None) -> None:
        if self._legacy_prefix is None:
            return
        if layout is None:
            layout = self._layout_profile()
        if self._legacy_prefix != _normalize_hdfs_prefix(layout["project_root"]):
            raise ValueError("legacy HDFS prefix must match the Waystone project root")

    def _run(self, arguments: list[str], context: _OperationContext) -> subprocess.CompletedProcess:
        self._check_tool_pins()
        context.check_deadline()
        command = [*self.command_prefix, "--error-format", "json", *arguments]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=self._environment(),
            )
        except OSError as error:
            raise _PrimitiveUnavailable("Waystone command unavailable") from error
        try:
            stdout, stderr = process.communicate(timeout=self._remaining_seconds(context))
        except subprocess.TimeoutExpired as error:
            self._kill_process_group(process)
            raise _PrimitiveTimeout("Waystone command timed out") from error
        context.check_deadline()
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def _kill_process_group(self, process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=1.0)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()

    def _check_tool_pins(self) -> None:
        for path, expected in self._tool_pins.items():
            stat_tuple = _file_stat_tuple(Path(path))
            if self._tool_pin_stats.get(path) == stat_tuple:
                continue
            if _file_sha256_and_size(Path(path))[0] != expected:
                raise RuntimeError("pinned Waystone tool digest changed")
            self._tool_pin_stats[path] = stat_tuple

    def _command_timeout_seconds(self, context: _OperationContext) -> int:
        return max(1, int(self._remaining_seconds(context) + 0.999))

    def _remaining_seconds(self, context: _OperationContext) -> float:
        remaining = context.deadline_at - self._clock()
        if remaining <= 0:
            raise _PrimitiveTimeout("blob operation deadline expired")
        return remaining

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.setdefault("HADOOP_CONF_DIR", self._hadoop_conf_dir)
        return environment

    def _raise_waystone_failure(self, result, *, missing: bool, conflict: bool) -> None:
        payload = _waystone_error_payload(result)
        if payload is None:
            raise _PrimitivePermanentUnavailable("Waystone command failed")
        error_class = payload.get("class")
        if error_class == "auth":
            raise _PrimitiveUnauthenticated("Waystone authentication failed")
        if error_class == "timeout":
            raise _PrimitiveTimeout("Waystone command timed out")
        if error_class in WAYSTONE_PERMANENT_UNAVAILABLE_ERROR_CLASSES:
            raise _PrimitivePermanentUnavailable("Waystone command failed")
        if missing and _waystone_error_message_has_marker(payload, MISSING_MARKERS):
            raise _PrimitiveMissing("Waystone blob missing")
        if conflict and _waystone_error_message_has_marker(payload, CONFLICT_MARKERS):
            raise _PrimitiveConflict("Waystone blob exists")
        if error_class in WAYSTONE_TRANSIENT_ERROR_CLASSES:
            raise _PrimitiveUnavailable("Waystone command failed")
        if error_class:
            raise _PrimitivePermanentUnavailable("Waystone command failed")
        raise _PrimitivePermanentUnavailable("Waystone command failed")


def blob_store_descriptor(adapter) -> dict[str, str]:
    if isinstance(adapter, WaystoneBlobAdapter):
        return {"kind": "waystone", "project": adapter.project}
    if isinstance(adapter, LocalFileBlobAdapter):
        return {"kind": "local", "root": str(adapter.root)}
    raise ValueError("blob store adapter descriptor unsupported")


def blob_adapter_from_descriptor(
    descriptor,
    *,
    command_prefix=None,
    waystone=None,
    tool_pins: Mapping[str, str] | None = None,
    hadoop_conf_dir: str = DEFAULT_HADOOP_CONF_DIR,
):
    if not isinstance(descriptor, Mapping):
        raise ValueError("blob store descriptor required")
    kind = descriptor.get("kind")
    if kind == "local":
        if set(descriptor) != {"kind", "root"}:
            raise ValueError("blob store descriptor required")
        root = descriptor["root"]
        if not isinstance(root, str) or not root:
            raise ValueError("local blob store root required")
        return LocalFileBlobAdapter(root)
    if kind == "waystone":
        if set(descriptor) != {"kind", "project"}:
            raise ValueError("blob store descriptor required")
        return WaystoneBlobAdapter(
            project=descriptor["project"],
            command_prefix=_descriptor_command_prefix(command_prefix, waystone),
            tool_pins=tool_pins,
            hadoop_conf_dir=hadoop_conf_dir,
        )
    if kind == "hdfs":
        allowed = {"kind", "prefix", "project", "schema_version"}
        if not set(descriptor).issubset(allowed) or "prefix" not in descriptor:
            raise ValueError("blob store descriptor required")
        adapter = WaystoneBlobAdapter(
            project=descriptor.get("project", "sureal"),
            command_prefix=_descriptor_command_prefix(command_prefix, waystone),
            tool_pins=tool_pins,
            legacy_prefix=descriptor["prefix"],
            hadoop_conf_dir=hadoop_conf_dir,
        )
        adapter._validate_legacy_prefix()
        return adapter
    raise ValueError("blob store descriptor kind required")


def blob_key_from_uri(value: str, adapter_or_descriptor, **factory_kwargs) -> str:
    adapter = (
        blob_adapter_from_descriptor(adapter_or_descriptor, **factory_kwargs)
        if isinstance(adapter_or_descriptor, Mapping)
        else adapter_or_descriptor
    )
    if hasattr(adapter, "blob_key_from_uri"):
        return adapter.blob_key_from_uri(value)
    return validate_blob_key(value)


def waystone_tool_pins(waystone=None) -> dict[str, str]:
    if waystone is None:
        waystone = _default_waystone()
    cli = Path(waystone)
    root = cli.parents[1]
    pins = {str(cli): _file_sha256_and_size(cli)[0]}
    for relative in WAYSTONE_TOOL_RELATIVES:
        path = root / relative
        pins[str(path)] = _file_sha256_and_size(path)[0]
    return pins


def validate_blob_key(key: str) -> str:
    if not isinstance(key, str):
        raise ValueError("blob key must be a string")
    if key.startswith("/") or key != key.strip("/") or not key:
        raise ValueError("safe relative blob key required")
    parts = key.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("safe relative blob key required")
    if any(not BLOB_KEY_SEGMENT.fullmatch(part) for part in parts):
        raise ValueError("safe relative blob key required")
    return key


def _require_sha256(value: str) -> str:
    if not isinstance(value, str) or not HEX_SHA256.fullmatch(value):
        raise ValueError("sha256 digest required")
    return value


def _require_regular_file(path) -> Path:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError("regular non-symlinked file required: " + str(candidate))
    return candidate


def _file_sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with _require_regular_file(path).open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _file_stat_tuple(path: Path) -> tuple[int, int, int, int, int]:
    stat_result = _require_regular_file(path).stat()
    return (
        stat_result.st_dev,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
        stat_result.st_ctime_ns,
    )


def _path_ancestry(root: Path, path: Path) -> list[Path]:
    root_absolute = root.absolute()
    path_absolute = path.absolute()
    try:
        relative = path_absolute.relative_to(root_absolute)
    except ValueError as error:
        raise _PrimitiveUnavailable("local blob path escapes root") from error
    current = root_absolute
    ancestry = [current]
    for segment in relative.parts:
        current = current / segment
        ancestry.append(current)
    return ancestry


def _link_no_replace(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except FileExistsError as error:
        raise FileExistsError("blob destination already exists: " + str(destination)) from error


def _require_descriptor_name(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or not BLOB_KEY_SEGMENT.fullmatch(value):
        raise ValueError(label + " required")
    return value


def _waystone_command_prefix(command_prefix) -> list[str]:
    if command_prefix is None:
        return [str(_default_waystone())]
    if isinstance(command_prefix, (str, os.PathLike)):
        command_prefix = [str(command_prefix)]
    prefix = [str(part) for part in command_prefix]
    if not prefix or any(not part for part in prefix):
        raise ValueError("Waystone command prefix required")
    return prefix


def _default_waystone() -> Path:
    configured = os.environ.get("SUREAL_WAYSTONE")
    if configured:
        return Path(configured)
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        home = Path.home()
    return home / DEFAULT_WAYSTONE_RELATIVE


def _descriptor_command_prefix(command_prefix, waystone):
    if command_prefix is not None and waystone is not None:
        raise ValueError("choose command_prefix or waystone")
    if command_prefix is not None:
        return command_prefix
    if waystone is not None:
        return [str(waystone)]
    return None


def _validate_tool_pins(tool_pins: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(tool_pins, Mapping) or not tool_pins:
        raise ValueError("Waystone tool pins required")
    pins = {}
    for path, digest in tool_pins.items():
        if not isinstance(path, str) or not path:
            raise ValueError("Waystone tool pin path required")
        pins[path] = _require_sha256(digest)
    return pins


def _normalize_hdfs_prefix(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("HDFS prefix required")
    value = value.rstrip("/")
    if (
        not value
        or not value.startswith("hdfs://")
        or any(character in value for character in ("\x00", "\n", "\r"))
        or "@" in value.split("://", 1)[1].split("/", 1)[0]
    ):
        raise ValueError("HDFS prefix required")
    return value


def _waystone_error_payload(result) -> Mapping[str, object] | None:
    stderr = getattr(result, "stderr", "") or ""
    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping) and payload.get("type") == "error":
            return payload
    return None


def _waystone_error_message_has_marker(payload: Mapping[str, object], markers: tuple[str, ...]) -> bool:
    message = payload.get("message")
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in markers)


def _waystone_blob_size(stdout: str) -> int:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as error:
        raise _PrimitiveUnavailable("Waystone size output unavailable") from error
    if _waystone_listing_is_empty(payload):
        raise _PrimitiveMissing("Waystone blob missing")
    size = _find_waystone_size(payload)
    if size is None or size < 0:
        raise _PrimitiveUnavailable("Waystone size output unavailable")
    return size


def _waystone_blob_exists(stdout: str) -> bool:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as error:
        raise _PrimitiveUnavailable("Waystone exists output unavailable") from error
    if _waystone_listing_is_empty(payload):
        return False
    return _find_waystone_size(payload) is not None


def _waystone_listing_is_empty(value) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("count") == 0
        and isinstance(value.get("entries"), list)
        and not value.get("entries")
    )


def _find_waystone_size(value) -> int | None:
    if isinstance(value, Mapping):
        for key in WAYSTONE_SIZE_KEYS:
            found = value.get(key)
            if type(found) is int:
                return found
        entries = value.get("entries")
        if isinstance(entries, list) and len(entries) == 1:
            return _find_waystone_size(entries[0])
    return None
