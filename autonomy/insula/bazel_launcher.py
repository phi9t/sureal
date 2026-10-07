#!/usr/bin/env python3
"""Run repository Bazel inside an Insula rootfs."""
import argparse
import json
import os
import sys
from pathlib import Path


_THIS_FILE = Path(__file__).resolve()
AUTONOMY = _THIS_FILE.parents[1]
REPO = AUTONOMY.parent
AUTONOMY_CACHE = Path.home() / ".cache/waystone/waymo-perception"
DEFAULT_ROOTFS = AUTONOMY_CACHE / "insula/rootfs-v4"
GPU_ROOTFS = AUTONOMY_CACHE / "gpu-rootfs-v6"
CURRICULUM_ROOTFS = Path.home() / ".cache/waystone/3d-pathway/insula/rootfs-v2"
DEFAULT_CACHE = REPO / ".bazel-cache"
BAZEL_VERSION = "9.2.0"
GPU_DEVICES = ("/dev/nvidia1", "/dev/nvidiactl", "/dev/nvidia-uvm")
GPU_DRIVER_PREFIXES = (
    "libcuda.so",
    "libnvidia-ptxjitcompiler.so",
    "libnvidia-nvvm.so",
)
DEFAULT_GPU_DRIVER_LIBRARY_DIRS = (Path("/usr/lib/x86_64-linux-gnu"),)
ORIGINAL_CWD_FLAG = "--__sureal-bazelw-original-cwd"
from insula.runtime_identity import rootfs_identity
from insula.sandbox_plan import compose_bwrap_plan


def restore_original_cwd(argv):
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)
    if len(argv) >= 2 and argv[0] == ORIGINAL_CWD_FLAG:
        os.chdir(argv[1])
        argv = argv[2:]
    return argv


def default_lock(rootfs):
    return Path(str(rootfs) + ".lock.json")


def _is_parallax_target(argument):
    return argument == "//parallax" or argument.startswith(("//parallax:", "//parallax/"))


def _is_autonomy_target(argument):
    return argument == "//autonomy" or argument.startswith(("//autonomy:", "//autonomy/"))


def target_components(arguments):
    components = set()
    for argument in arguments:
        if argument.startswith("-"):
            continue
        if argument == "//...":
            components.update({"autonomy", "parallax"})
        elif _is_parallax_target(argument):
            components.add("parallax")
        elif _is_autonomy_target(argument):
            components.add("autonomy")
    return components


def uses_curriculum_rootfs(arguments):
    return target_components(arguments) == {"parallax"}


def uses_gpu_config(arguments):
    return any(argument == "--config=cuda" for argument in arguments)


def output_base_for(rootfs, arguments):
    if uses_gpu_config(arguments) or rootfs.resolve() == GPU_ROOTFS.resolve():
        return "/tmp/bazel-cache/output-base-gpu"
    if rootfs.resolve() == CURRICULUM_ROOTFS.resolve():
        return "/tmp/bazel-cache/output-base-3d-pathway"
    return "/tmp/bazel-cache/output-base"


def read_lock(path):
    try:
        lock = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ValueError(f"rootfs lock not found: {path}") from exc
    if lock.get("schema_version") != 1:
        raise ValueError("invalid rootfs lock schema")
    return lock


def verify_rootfs(rootfs, lock):
    if lock.get("bazel_version") != BAZEL_VERSION:
        raise ValueError(
            f"rootfs lock records Bazel {lock.get('bazel_version')!r}, expected {BAZEL_VERSION}"
        )
    expected = lock.get("rootfs_sha256")
    if not expected:
        raise ValueError("rootfs lock is missing rootfs_sha256")
    actual = rootfs_identity(rootfs)
    if actual != expected:
        raise ValueError(
            f"rootfs content does not match rootfs lock: expected {expected}, found {actual}"
        )


def bazel_command(arguments, output_base, update_lock=False):
    if not arguments:
        arguments = ["help"]
    command, *rest = arguments
    lockfile_mode = "update" if update_lock else "error"
    return [
        "bazel",
        f"--output_base={output_base}",
        command,
        "--ignore_dev_dependency",
        f"--lockfile_mode={lockfile_mode}",
        "--repository_cache=/tmp/bazel-cache/repository-cache",
        "--disk_cache=/tmp/bazel-cache/disk-cache",
        *rest,
    ]


# Bridge legacy absolute /experiment/<waymo-child> paths until ticket 26 removes them.
def repo_workspace_mounts(update_lock=False):
    mounts = [["--tmpfs", "/experiment"]]
    root_names = set()
    for path in sorted(REPO.iterdir(), key=lambda item: item.name):
        if path.name == ".bazel-cache":
            continue
        root_names.add(path.name)
        if update_lock and path.name == "MODULE.bazel.lock":
            continue
        mounts.append(["--ro-bind", str(path.resolve()), "/experiment/" + path.name])
    if update_lock:
        mounts.append(["--bind", str((REPO / "MODULE.bazel.lock").resolve()), "/experiment/MODULE.bazel.lock"])
    for path in sorted(AUTONOMY.iterdir(), key=lambda item: item.name):
        if path.is_dir() and path.name not in root_names:
            mounts.append(["--ro-bind", str(path.resolve()), "/experiment/" + path.name])
    return mounts


def gpu_device_mounts():
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
            pairs.append((Path(host), guest))
    else:
        pairs = [(Path(device), device) for device in GPU_DEVICES]
    mounts = []
    for host, guest in pairs:
        if not host.exists():
            raise ValueError(f"GPU device not found: {host}")
        mounts.append(["--dev-bind", str(host), guest])
    return mounts


def gpu_driver_library_dirs():
    configured = os.environ.get("SUREAL_BAZEL_GPU_DRIVER_LIBRARY_DIRS")
    if not configured:
        return DEFAULT_GPU_DRIVER_LIBRARY_DIRS
    return tuple(Path(item) for item in configured.split(os.pathsep) if item)


def gpu_driver_mounts():
    mounts = []
    directories = gpu_driver_library_dirs()
    for prefix in GPU_DRIVER_PREFIXES:
        found = []
        for directory in directories:
            found.extend(sorted(path for path in directory.glob(prefix + "*") if path.is_file()))
        if not found:
            searched = ", ".join(str(directory) for directory in directories)
            raise ValueError(f"GPU driver library {prefix} not found in {searched}")
        for path in found:
            mounts.append(["--ro-bind", str(path.resolve()), "/driver/" + path.name])
    return mounts


def gpu_environment():
    return [
        ["--setenv", "PATH", "/opt/waymo/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"],
        ["--setenv", "LD_LIBRARY_PATH", "/driver:/usr/local/cuda/lib64"],
        ["--setenv", "CUDA_VISIBLE_DEVICES", "0"],
    ]


def sandbox_plan(rootfs, cache, arguments, update_lock=False):
    rootfs = rootfs.resolve()
    cache = cache.resolve()
    gpu = uses_gpu_config(arguments) or rootfs == GPU_ROOTFS.resolve()
    mounts = [
        ["--ro-bind", str(rootfs), "/"],
        ["--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf"],
        *repo_workspace_mounts(update_lock),
        ["--tmpfs", "/outputs"],
        ["--tmpfs", "/tmp"],
        ["--bind", str(cache), "/tmp/bazel-cache"],
    ]
    pre_dev_mounts = []
    post_dev_mounts = []
    environment = [
        ["--setenv", "HOME", "/tmp/bazel-cache/home"],
        ["--setenv", "USER", "sureal"],
        ["--setenv", "LOGNAME", "sureal"],
        ["--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin"],
        ["--setenv", "TMPDIR", "/tmp"],
        ["--setenv", "PYTHONNOUSERSITE", "1"],
        ["--setenv", "PYTHONDONTWRITEBYTECODE", "1"],
    ]
    if gpu:
        pre_dev_mounts.extend([["--tmpfs", "/driver"], *gpu_driver_mounts()])
        post_dev_mounts.extend(gpu_device_mounts())
        environment = [
            item for item in environment if not (item[0] == "--setenv" and item[1] == "PATH")
        ]
        environment.extend(gpu_environment())
    bazel = bazel_command(arguments, output_base_for(rootfs, arguments), update_lock)
    plan = compose_bwrap_plan(
        unshare_flags=[
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
        ],
        mounts_before_devices=[*mounts, *pre_dev_mounts],
        mounts_after_devices=post_dev_mounts,
        environment=environment,
        chdir="/experiment",
        command=bazel,
    )
    return {
        "argv": plan.argv,
        "bazel": bazel,
        "environment": plan.environment,
        "mounts": plan.mounts,
        "update_lock": update_lock,
    }


def parse(argv):
    parser = argparse.ArgumentParser(prog="bazelw", description=__doc__)
    parser.add_argument("--rootfs", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=None)
    parser.add_argument("--cache", type=Path, default=Path(os.environ.get("SUREAL_BAZEL_CACHE", DEFAULT_CACHE)))
    parser.add_argument("--emit-plan", action="store_true")
    parser.add_argument("--update-lock", action="store_true")
    parser.add_argument("bazel_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.bazel_args and args.bazel_args[0] == "--":
        args.bazel_args = args.bazel_args[1:]
    components = target_components(args.bazel_args)
    if len(components) > 1:
        parser.error(
            "target pattern spans autonomy and parallax; run each component "
            "separately so the wrapper can select the correct rootfs"
        )
    if args.rootfs is None:
        configured = os.environ.get("SUREAL_BAZEL_ROOTFS")
        if configured:
            args.rootfs = Path(configured)
        elif uses_gpu_config(args.bazel_args):
            args.rootfs = GPU_ROOTFS
        elif uses_curriculum_rootfs(args.bazel_args):
            args.rootfs = CURRICULUM_ROOTFS
        else:
            args.rootfs = DEFAULT_ROOTFS
    if args.lock is None:
        args.lock = Path(os.environ.get("SUREAL_BAZEL_ROOTFS_LOCK", default_lock(args.rootfs)))
    return args


def main(argv=None):
    argv = restore_original_cwd(argv)
    args = parse(argv)
    try:
        lock = read_lock(args.lock)
        verify_rootfs(args.rootfs, lock)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    plan = sandbox_plan(args.rootfs, args.cache, args.bazel_args, args.update_lock)
    plan["rootfs"] = str(args.rootfs.resolve())
    plan["lock"] = str(args.lock.resolve())
    plan["cache"] = str(args.cache.resolve())
    if args.emit_plan:
        print(json.dumps(plan, sort_keys=True))
        return 0
    for name in (
        "home",
        "output-base",
        "output-base-3d-pathway",
        "output-base-gpu",
        "repository-cache",
        "disk-cache",
    ):
        (args.cache / name).mkdir(parents=True, exist_ok=True)
    os.execvp(plan["argv"][0], plan["argv"])


if __name__ == "__main__":
    raise SystemExit(main())
