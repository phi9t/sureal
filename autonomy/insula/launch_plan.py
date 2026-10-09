"""Checked runtime locks and structured Insula launch plans."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from evidence.source_snapshot import file_sha256
from insula.runtime_identity import rootfs_identity
from insula.runtime_roots import (
    CURRENT_CPU_ROOTFS_NAME,
    CURRENT_CURRICULUM_ROOTFS_NAME,
    CURRENT_GPU_ROOTFS_NAME,
    CURRENT_METRICS_ROOTFS_NAME,
    CURRENT_MOTION_CLI_ROOTFS_NAME,
    CURRENT_MOTION_METRICS_ROOTFS_NAME,
    default_lock,
)


BAZEL_VERSION = "9.2.0"
BAZEL_LINUX_X86_64_SHA256 = (
    "7668a95db1250f12c40407251e4e203b4ec8bf39bc495d2f485b2d8c99048694"
)
REPO = Path(__file__).resolve().parents[2]
AUTONOMY = REPO / "autonomy"

_ROOTFS_CONTENT_CACHE: set[tuple[str, str]] = set()
_DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin"
_GPU_PATH = "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
_MODULE_ENVIRONMENT = {
    "HOME",
    "PATH",
    "PYTHONNOUSERSITE",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONPATH",
    "LD_LIBRARY_PATH",
    "CUDA_VISIBLE_DEVICES",
}
_NAMED_INPUT_PREFIXES = ("/tmp", "/opt", "/srv", "/mnt")
_GPU_DRIVER_PREFIXES = (
    "libcuda.so",
    "libnvidia-ptxjitcompiler.so",
    "libnvidia-nvvm.so",
)
_GPU_CONTROL_DEVICES = {
    "/dev/nvidiactl",
    "/dev/nvidia-uvm",
    "/dev/nvidia-uvm-tools",
    "/dev/nvidia-modeset",
}
_DEFAULT_GPU_DRIVER_LIBRARY_DIRS = (Path("/usr/lib/x86_64-linux-gnu"),)


class RuntimeLockError(ValueError):
    """Raised when a runtime lock is missing or does not match its rootfs."""


class PlanError(ValueError):
    """Raised when a launch plan violates mount or environment rules."""


@dataclass(frozen=True)
class RuntimeLock:
    rootfs: Path
    lock_path: Path | None
    data: dict
    form: str
    lock_sha256: str


@dataclass(frozen=True)
class Mount:
    role: str
    kind: str
    inside_path: str
    mode: str
    host_path: Path | None = None
    phase: str = "before_devices"


@dataclass(frozen=True)
class LaunchPlan:
    runtime: RuntimeLock
    mounts: tuple[Mount, ...]
    environment: tuple[tuple[str, str, str], ...]
    working_directory: str
    command: tuple[str, ...]
    unshare_flags: tuple[str, ...]
    gpu: "GPURequest | None" = None


@dataclass(frozen=True)
class GPURequest:
    requested_index: int
    device_uuid: str


@dataclass(frozen=True)
class _RecipeSpec:
    fields: Mapping[str, Path]
    bazel: bool


@dataclass(frozen=True)
class _ImageSpec:
    fields: Mapping[str, Path]
    parent_image_id: str | None = None


def load_runtime_lock(rootfs: Path, lock_path: Path | None = None) -> RuntimeLock:
    """Load and fully check a runtime lock before a launch plan exists."""
    rootfs = Path(rootfs).resolve()
    lock_path = default_lock(rootfs) if lock_path is None else Path(lock_path).resolve()
    try:
        raw = lock_path.read_text()
    except FileNotFoundError as exc:
        raise RuntimeLockError(f"runtime lock missing: {lock_path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeLockError(f"runtime lock JSON: {exc}") from exc
    if data.get("schema_version") != 1:
        raise RuntimeLockError("schema_version: expected 1")

    lock_sha256 = file_sha256(lock_path)
    if "recipe_hashes" in data:
        form = "image"
        _check_image_lock(rootfs, data)
    else:
        form = "recipe-digest"
        _check_recipe_lock(rootfs, data)
    _check_rootfs_content(rootfs, data, lock_sha256)
    return RuntimeLock(
        rootfs=rootfs,
        lock_path=lock_path,
        data=dict(data),
        form=form,
        lock_sha256=lock_sha256,
    )


def build_plan(
    runtime: RuntimeLock,
    *,
    code: Path,
    output: Path,
    command: Iterable[object],
    source: Path | None = None,
    named_inputs: Mapping[str, Path] | None = None,
    writable_inputs: Mapping[str, Path] | None = None,
    extra_environment: Mapping[str, object] | None = None,
    gpu_index: int | None = None,
    source_snapshot_digest: str | None = None,
) -> LaunchPlan:
    mounts = [
        Mount("runtime", "bind", "/", "read_only", runtime.rootfs),
        Mount("code", "bind", "/experiment", "read_only", Path(code)),
    ]
    if source is not None:
        mounts.append(Mount("source", "bind", "/source", "read_only", Path(source)))
    mounts.append(Mount("output", "bind", "/outputs", "writable", Path(output)))
    for inside, host in (named_inputs or {}).items():
        _validate_named_input_path(inside)
        mounts.append(Mount(f"input:{inside}", "bind", inside, "read_only", Path(host)))
    for inside, host in (writable_inputs or {}).items():
        _validate_named_input_path(inside)
        mounts.append(Mount(f"input:{inside}", "bind", inside, "writable", Path(host)))

    environment = [
        ("--setenv", "HOME", "/tmp/private-home"),
        ("--setenv", "PATH", _DEFAULT_PATH),
        ("--setenv", "PYTHONNOUSERSITE", "1"),
        ("--setenv", "PYTHONDONTWRITEBYTECODE", "1"),
        ("--setenv", "PYTHONPATH", "/experiment"),
    ]
    if gpu_index is not None:
        gpu_mounts, gpu_environment, gpu = _gpu_mounts_environment_and_request(gpu_index)
        mounts.extend(gpu_mounts)
        environment = [
            item for item in environment if not (item[0] == "--setenv" and item[1] == "PATH")
        ]
        environment.extend(gpu_environment)
    else:
        gpu = None
    environment = _merge_environment(environment, extra_environment)
    mounts.append(Mount("tmp", "tmpfs", "/tmp", "writable", None, "after_devices"))
    plan = _assemble_plan(
        runtime,
        mounts=mounts,
        environment=environment,
        command=command,
        working_directory="/experiment",
        unshare_flags=("--unshare-all", "--die-with-parent"),
        gpu=gpu,
    )
    if source_snapshot_digest is not None:
        object.__setattr__(plan, "_source_snapshot_digest", source_snapshot_digest)
    return plan


def plan_data(plan: LaunchPlan) -> dict:
    """Return a data view of a launch plan without rendering argv."""
    data = {
        "runtime": {
            "rootfs": str(plan.runtime.rootfs),
            "lock": str(plan.runtime.lock_path) if plan.runtime.lock_path is not None else None,
            "lock_sha256": plan.runtime.lock_sha256,
            "form": plan.runtime.form,
        },
        "mounts": [_mount_data(mount, include_host=True) for mount in plan.mounts],
        "devices": [_mount_data(mount, include_host=True) for mount in plan.mounts if mount.kind == "dev-bind"],
        "environment": [list(item) for item in plan.environment],
        "working_directory": plan.working_directory,
        "command": list(plan.command),
    }
    if plan.gpu is not None:
        data["gpu"] = _gpu_request_data(plan.gpu)
    return data


def render_plan(plan: LaunchPlan) -> list[str]:
    """Render a launch plan to bwrap argv at the execution boundary."""
    argv = ["bwrap", *plan.unshare_flags]
    for mount in plan.mounts:
        if mount.phase == "before_devices":
            argv.extend(_render_mount(mount))
    argv.extend(["--proc", "/proc", "--dev", "/dev"])
    for mount in plan.mounts:
        if mount.phase == "after_devices":
            argv.extend(_render_mount(mount))
    argv.append("--clearenv")
    for item in plan.environment:
        argv.extend(item)
    argv.extend(["--chdir", plan.working_directory, "--", *plan.command])
    return [str(item) for item in argv]


def record_plan(plan: LaunchPlan) -> dict:
    """Return the host-path-free receipt record for a launch plan."""
    record = {
        "runtime": {
            "lock_sha256": plan.runtime.lock_sha256,
            "form": plan.runtime.form,
        },
        "mounts": [_record_mount(plan, mount) for mount in plan.mounts if mount.kind != "dev-bind"],
        "devices": [_record_device(mount) for mount in plan.mounts if _record_device_mount(plan, mount)],
        "environment": {item[1]: item[2] for item in plan.environment if item[0] == "--setenv"},
        "working_directory": plan.working_directory,
        "command": list(plan.command),
    }
    if plan.gpu is not None:
        record["gpu"] = _gpu_request_data(plan.gpu)
    return record


def _assemble_plan(
    runtime: RuntimeLock,
    *,
    mounts: Iterable[Mount],
    environment: Iterable[tuple[object, object, object]],
    command: Iterable[object],
    working_directory: str,
    unshare_flags: Iterable[object],
    gpu: GPURequest | None = None,
) -> LaunchPlan:
    mount_tuple = tuple(mounts)
    _validate_mounts(mount_tuple)
    return LaunchPlan(
        runtime=runtime,
        mounts=mount_tuple,
        environment=tuple((str(a), str(b), str(c)) for a, b, c in environment),
        working_directory=str(working_directory),
        command=tuple(str(item) for item in command),
        unshare_flags=tuple(str(flag) for flag in unshare_flags),
        gpu=gpu,
    )


def _unchecked_runtime(rootfs: Path) -> RuntimeLock:
    return RuntimeLock(
        rootfs=Path(rootfs).resolve(),
        lock_path=None,
        data={},
        form="unchecked",
        lock_sha256="",
    )


def _check_recipe_lock(rootfs: Path, data: Mapping[str, object]) -> None:
    spec = _recipe_spec_for(rootfs)
    for field, path in spec.fields.items():
        _require_field(data, field)
        expected = file_sha256(path)
        if data[field] != expected:
            raise RuntimeLockError(f"{field}: expected {expected}, found {data[field]!r}")
    if spec.bazel:
        _require_field(data, "bazel_version")
        if data["bazel_version"] != BAZEL_VERSION:
            raise RuntimeLockError(
                f"bazel_version: expected {BAZEL_VERSION}, found {data['bazel_version']!r}"
            )
        _require_field(data, "bazel_linux_x86_64_sha256")
        if data["bazel_linux_x86_64_sha256"] != BAZEL_LINUX_X86_64_SHA256:
            raise RuntimeLockError(
                "bazel_linux_x86_64_sha256: "
                f"expected {BAZEL_LINUX_X86_64_SHA256}, "
                f"found {data['bazel_linux_x86_64_sha256']!r}"
            )


def _check_image_lock(rootfs: Path, data: Mapping[str, object]) -> None:
    spec = _image_spec_for(rootfs)
    _require_field(data, "image_id")
    if not isinstance(data["image_id"], str) or not data["image_id"]:
        raise RuntimeLockError("image_id: non-empty image id required")
    _require_field(data, "recipe_hashes")
    expected = {name: file_sha256(path) for name, path in spec.fields.items()}
    if data["recipe_hashes"] != expected:
        raise RuntimeLockError(
            f"recipe_hashes: expected {expected}, found {data['recipe_hashes']!r}"
        )
    if spec.parent_image_id is not None:
        _require_field(data, "parent_image_id")
        if data["parent_image_id"] != spec.parent_image_id:
            raise RuntimeLockError(
                f"parent_image_id: expected {spec.parent_image_id}, "
                f"found {data['parent_image_id']!r}"
            )


def _check_rootfs_content(rootfs: Path, data: Mapping[str, object], lock_sha256: str) -> None:
    _require_field(data, "rootfs_sha256")
    key = (str(rootfs), lock_sha256)
    if key in _ROOTFS_CONTENT_CACHE:
        return
    try:
        actual = rootfs_identity(rootfs)
    except ValueError as exc:
        raise RuntimeLockError(f"rootfs_sha256: {exc}") from exc
    expected = data["rootfs_sha256"]
    if actual != expected:
        raise RuntimeLockError(
            f"rootfs_sha256: rootfs content does not match rootfs lock: "
            f"expected {expected}, found {actual}"
        )
    _ROOTFS_CONTENT_CACHE.add(key)


def _require_field(data: Mapping[str, object], field: str) -> None:
    if field not in data:
        raise RuntimeLockError(f"{field}: missing from runtime lock")


def _recipe_spec_for(rootfs: Path) -> _RecipeSpec:
    path = rootfs.as_posix()
    if rootfs.name == CURRENT_GPU_ROOTFS_NAME:
        return _RecipeSpec(
            fields={
                "dockerfile_sha256": AUTONOMY / "insula/Dockerfile.gpu-bazel-rootfs-v6",
                "requirements_sha256": AUTONOMY / "insula/gpu-requirements.lock",
            },
            bazel=True,
        )
    if rootfs.name == CURRENT_CURRICULUM_ROOTFS_NAME and "/3d-pathway/insula/" in path:
        return _RecipeSpec(
            fields={
                "dockerfile_sha256": REPO / "parallax/insulas/bazel-rootfs.Dockerfile",
                "requirements_sha256": REPO / "parallax/insulas/bazel-requirements.lock",
            },
            bazel=True,
        )
    return _RecipeSpec(
        fields={
            "dockerfile_sha256": AUTONOMY / "insula/Dockerfile",
            "requirements_sha256": AUTONOMY / "requirements-tracer.lock",
            "test_tools_requirements_sha256": AUTONOMY
            / "insula/cpu-test-tools-requirements.lock",
        },
        bazel=True,
    )


def _image_spec_for(rootfs: Path) -> _ImageSpec:
    if rootfs.name == CURRENT_METRICS_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "evaluation/Dockerfile",
                "CMakeLists.txt": AUTONOMY / "evaluation/CMakeLists.txt",
            }
        )
    if rootfs.name == CURRENT_MOTION_METRICS_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "motion/ingestion/native_metric.Dockerfile",
                "CMakeLists.txt": AUTONOMY / "motion/CMakeLists.txt",
            },
            parent_image_id="sha256:c0018cf57e482c6a9e6623ea32f29c6039f22f5dafb0f3311bad6d411a7bb135",
        )
    if rootfs.name == CURRENT_MOTION_CLI_ROOTFS_NAME:
        return _ImageSpec(
            fields={
                "Dockerfile": AUTONOMY / "motion/cli/motion_cli.Dockerfile",
                "CMakeLists.txt": AUTONOMY / "motion/cli/CMakeLists.txt",
                "motion_metrics_main.cc": AUTONOMY / "motion/cli/motion_metrics_main.cc",
            },
            parent_image_id="sha256:84fb83dd874d0cfff8e9ee3df0759d89f9ad85e9538c0071c9eb606a13d8c233",
        )
    raise RuntimeLockError(f"recipe_hashes: no image-form recipe is known for {rootfs.name}")


def _merge_environment(
    base_environment: Iterable[tuple[str, str, str]],
    extra_environment: Mapping[str, object] | None,
) -> list[tuple[str, str, str]]:
    environment = list(base_environment)
    if not extra_environment:
        return environment
    owned = {item[1] for item in environment if item[0] == "--setenv"} | _MODULE_ENVIRONMENT
    for name in sorted(extra_environment):
        if name in owned:
            raise PlanError(f"{name}: extra environment collides with module-owned variable")
        environment.append(("--setenv", str(name), str(extra_environment[name])))
    return environment


def _validate_named_input_path(path: str) -> None:
    inside = PurePosixPath(path)
    if not inside.is_absolute() or ".." in inside.parts:
        raise PlanError(f"{path}: named input path must be absolute and normalized")
    if str(inside) not in _NAMED_INPUT_PREFIXES and not any(
        str(inside).startswith(prefix + "/") for prefix in _NAMED_INPUT_PREFIXES
    ):
        raise PlanError(f"{path}: named input must be under /tmp, /opt, /srv or /mnt")


def _validate_mounts(mounts: tuple[Mount, ...]) -> None:
    host_mounts = []
    inside_roles: dict[str, str] = {}
    for mount in mounts:
        previous = inside_roles.get(mount.inside_path)
        if previous is not None:
            raise PlanError(f"{previous} and {mount.role}: duplicate inside mount {mount.inside_path}")
        inside_roles[mount.inside_path] = mount.role
        if mount.host_path is not None:
            host_mounts.append((mount, Path(mount.host_path).resolve()))
    for index, (left, left_path) in enumerate(host_mounts):
        for right, right_path in host_mounts[index + 1 :]:
            if left_path == right_path:
                if left.mode == right.mode == "read_only" and left_path.is_file():
                    continue
                raise PlanError(f"{left.role} and {right.role}: host path mounted twice")
            overlaps = left_path in right_path.parents or right_path in left_path.parents
            if overlaps and ("writable" in (left.mode, right.mode)):
                raise PlanError(f"{left.role} and {right.role}: writable mount overlaps another mount")


def _render_mount(mount: Mount) -> list[str]:
    if mount.kind == "tmpfs":
        return ["--tmpfs", mount.inside_path]
    if mount.host_path is None:
        raise PlanError(f"{mount.role}: host path required")
    if mount.kind == "dev-bind":
        return ["--dev-bind", str(mount.host_path), mount.inside_path]
    if mount.kind != "bind":
        raise PlanError(f"{mount.role}: unsupported mount kind {mount.kind}")
    flag = "--bind" if mount.mode == "writable" else "--ro-bind"
    return [flag, str(mount.host_path), mount.inside_path]


def _mount_data(mount: Mount, *, include_host: bool) -> dict:
    data = {
        "role": mount.role,
        "inside_path": mount.inside_path,
        "mode": mount.mode,
        "kind": mount.kind,
    }
    if include_host and mount.host_path is not None:
        data["host_path"] = str(Path(mount.host_path).resolve())
    return data


def _record_mount(plan: LaunchPlan, mount: Mount) -> dict:
    data = _mount_data(mount, include_host=False)
    if mount.role == "runtime":
        data["digest"] = plan.runtime.data.get("rootfs_sha256", "")
    elif mount.role == "code" and hasattr(plan, "_source_snapshot_digest"):
        data["digest"] = getattr(plan, "_source_snapshot_digest")
    elif mount.host_path is not None and mount.mode == "read_only":
        data["digest"] = _content_digest(Path(mount.host_path))
    return data


def _record_device(mount: Mount) -> dict:
    return {"role": mount.role, "inside_path": mount.inside_path}


def _record_device_mount(plan: LaunchPlan, mount: Mount) -> bool:
    if mount.kind != "dev-bind":
        return False
    return not (plan.gpu is not None and mount.role.startswith("gpu-device:"))


def _content_digest(path: Path) -> str:
    path = Path(path)
    if path.is_file():
        return file_sha256(path)
    if not path.is_dir() or path.is_symlink():
        raise PlanError(f"{path}: mounted digest input must be a regular file or directory")
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        info = item.lstat()
        kind = stat.S_IFMT(info.st_mode)
        record = [item.relative_to(path).as_posix(), kind, stat.S_IMODE(info.st_mode)]
        if stat.S_ISLNK(info.st_mode):
            record.append(str(item.readlink()))
        elif stat.S_ISREG(info.st_mode):
            record.extend([info.st_size, file_sha256(item)])
        elif not stat.S_ISDIR(info.st_mode):
            record.append(info.st_rdev)
        digest.update((json.dumps(record, separators=(",", ":")) + "\n").encode())
    return digest.hexdigest()


def _gpu_mounts_environment_and_request(gpu_index: int):
    if type(gpu_index) is not int or gpu_index < 0:
        raise PlanError("gpu_index: non-negative integer required")
    mounts = [Mount("gpu-driver-root", "tmpfs", "/driver", "writable", None)]
    for path in _gpu_driver_paths():
        mounts.append(
            Mount(
                f"gpu-driver:{path.name}",
                "bind",
                "/driver/" + path.name,
                "read_only",
                path,
            )
        )
    for host, guest in _gpu_device_pairs(gpu_index):
        mounts.append(Mount(f"gpu-device:{guest}", "dev-bind", guest, "writable", host, "after_devices"))
    return mounts, [
        ("--setenv", "PATH", _GPU_PATH),
        ("--setenv", "LD_LIBRARY_PATH", "/driver:/usr/local/cuda/lib64"),
        ("--setenv", "CUDA_VISIBLE_DEVICES", "0"),
    ], GPURequest(gpu_index, _gpu_device_uuid(gpu_index))


def _gpu_request_data(gpu: GPURequest) -> dict:
    return {"requested_index": gpu.requested_index, "device_uuid": gpu.device_uuid}


def _gpu_device_pairs(gpu_index: int) -> list[tuple[Path, str]]:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DEVICES")
    if configured:
        pairs = []
        for item in configured.split(","):
            if not item:
                continue
            if "=" in item:
                host, guest = item.split("=", 1)
            else:
                host = guest = item
            _validate_gpu_device_override_path(item, host, gpu_index, side="host")
            _validate_gpu_device_override_path(item, guest, gpu_index, side="guest")
            pairs.append((Path(host), guest))
    else:
        pairs = [
            (Path(f"/dev/nvidia{gpu_index}"), f"/dev/nvidia{gpu_index}"),
            (Path("/dev/nvidiactl"), "/dev/nvidiactl"),
            (Path("/dev/nvidia-uvm"), "/dev/nvidia-uvm"),
        ]
    for host, _ in pairs:
        if not host.exists():
            raise PlanError(f"GPU device not found: {host}")
    return pairs


def _validate_gpu_device_override_path(
    entry: str,
    path: str,
    gpu_index: int,
    *,
    side: str,
) -> None:
    requested_gpu = f"/dev/nvidia{gpu_index}"
    if path == requested_gpu or path in _GPU_CONTROL_DEVICES:
        return
    if re.fullmatch(r"/dev/nvidia\d+", path):
        raise PlanError(
            f"{entry}: GPU override {side} path {path} does not match requested {requested_gpu}"
        )
    if side == "guest" or path.startswith("/dev/nvidia"):
        allowed = ", ".join(sorted([requested_gpu, *_GPU_CONTROL_DEVICES]))
        raise PlanError(f"{entry}: GPU override {side} path {path} is not allowed; expected {allowed}")


def _gpu_device_uuid(gpu_index: int) -> str:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DEVICE_UUIDS")
    if configured:
        mapping = {}
        for item in configured.split(","):
            if not item:
                continue
            index, uuid = item.split("=", 1)
            mapping[int(index)] = uuid
        try:
            return mapping[gpu_index]
        except KeyError as exc:
            raise PlanError(f"gpu_index {gpu_index}: device UUID override missing") from exc
    try:
        return subprocess.check_output(
            [
                "nvidia-smi",
                f"--id={gpu_index}",
                "--query-gpu=uuid",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise PlanError(f"gpu_index {gpu_index}: device UUID lookup failed") from exc


def _gpu_driver_paths() -> list[Path]:
    configured = os.environ.get("SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS")
    directories = (
        tuple(Path(item) for item in configured.split(os.pathsep) if item)
        if configured
        else _DEFAULT_GPU_DRIVER_LIBRARY_DIRS
    )
    found_paths = []
    for prefix in _GPU_DRIVER_PREFIXES:
        found = []
        for directory in directories:
            found.extend(sorted(path for path in directory.glob(prefix + "*") if path.is_file()))
        if not found:
            searched = ", ".join(str(directory) for directory in directories)
            raise PlanError(f"GPU driver library {prefix} not found in {searched}")
        found_paths.extend(found)
    return found_paths


__all__ = [
    "RuntimeLockError",
    "PlanError",
    "load_runtime_lock",
    "build_plan",
    "plan_data",
    "render_plan",
    "record_plan",
]
