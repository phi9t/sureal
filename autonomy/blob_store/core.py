"""Backend-neutral, write-once storage for evidence blobs."""

import ctypes
import errno
import hashlib
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


CREDENTIAL_REFRESH_SCRIPT = "autonomy/resources/refresh-hdfs-auth.sh"
MAX_ATTEMPTS = 3
DEFAULT_DEADLINE_BASE_SECONDS = 5.0
DEFAULT_MINIMUM_THROUGHPUT_BYTES_PER_SECOND = 1024 * 1024
DEFAULT_BACKOFF_SECONDS = (0.25, 1.0)
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
BLOB_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]*$")
AT_FDCWD = -100
RENAME_NOREPLACE = 1
RENAMEAT2_SYSCALLS = {
    "x86_64": 316,
    "aarch64": 276,
}


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


class BlobStore:
    def __init__(
        self,
        adapter,
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
            existing = False
            try:
                self._call_primitive(
                    source_bytes,
                    lambda context: self._adapter._upload_blob(key, source, context),
                )
            except _PrimitiveConflict:
                existing = True

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
                if existing:
                    raise Conflict("blob key already holds different bytes: " + key)
                raise _PrimitiveCorrupt("blob readback digest mismatch")
            return {"key": key, "sha256": source_sha256, "bytes": source_bytes}

        return self._with_retries("put", key, attempt)

    def get(self, key, dest, sha256):
        key = validate_blob_key(key)
        expected_sha256 = _require_sha256(sha256)
        destination = Path(dest)

        def attempt():
            size = self._call_primitive(0, lambda context: self._adapter._blob_size(key, context))
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
                actual_sha256, _ = _file_sha256_and_size(temporary)
                if actual_sha256 != expected_sha256:
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
            except _PrimitiveMissing:
                raise Missing("blob missing: " + key) from None
            except _PrimitiveConflict:
                raise Conflict("blob key already exists: " + key) from None
            except _PrimitiveCorrupt:
                raise Corrupt("blob bytes failed verification: " + key) from None
            except _PrimitiveUnauthenticated:
                raise Unauthenticated(
                    "blob store authentication failed; run "
                    + CREDENTIAL_REFRESH_SCRIPT
                    + " to refresh credentials"
                ) from None
            except (_PrimitiveTransient, TimeoutError, OSError, Exception):
                if attempt == self._max_attempts:
                    raise Unavailable(
                        "blob store "
                        + operation_name
                        + " unavailable after "
                        + str(self._max_attempts)
                        + " attempts"
                    ) from None
                self._sleep(self._backoff_for_attempt(attempt))
        raise Unavailable("blob store " + operation_name + " unavailable") from None

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
    ):
        self._blobs = {validate_blob_key(key): bytes(value) for key, value in (blobs or {}).items()}
        self._delay_seconds = float(delay_seconds)
        self._transient_failures = int(transient_failures)
        self._unauthenticated = bool(unauthenticated)

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
            _rename_no_replace(temporary, path)
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
        for candidate in _path_ancestry(path):
            if candidate.is_symlink():
                raise _PrimitiveUnavailable("local blob path uses a symlink")


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
    if not candidate.is_file() or any(item.is_symlink() for item in [candidate, *candidate.parents]):
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


def _path_ancestry(path: Path) -> list[Path]:
    absolute = path.absolute()
    return [*reversed(absolute.parents), absolute]


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
        raise FileExistsError("blob destination already exists: " + str(destination))
    raise OSError(found, os.strerror(found), str(destination))
