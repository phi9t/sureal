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
DEFAULT_CACHE = REPO / ".bazel-cache"
BAZEL_VERSION = "9.2.0"
ORIGINAL_CWD_FLAG = "--__sureal-bazelw-original-cwd"
LIVE_GATE_CACHE_MOUNT = "/tmp/sureal-waymo-cache"
LIVE_GATE_BWRAP = "/tmp/live-gate-bwrap"
from insula.launch_plan import (
    Mount,
    _assemble_plan,
    _gpu_mounts_environment_and_request,
    load_runtime_lock,
    plan_data,
    render_plan,
)
from insula.runtime_roots import (
    current_cpu_rootfs,
    current_curriculum_rootfs,
    current_gpu_rootfs,
    default_lock,
)


DEFAULT_ROOTFS = current_cpu_rootfs()
GPU_ROOTFS = current_gpu_rootfs()
CURRICULUM_ROOTFS = current_curriculum_rootfs()


def restore_original_cwd(argv):
    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)
    if len(argv) >= 2 and argv[0] == ORIGINAL_CWD_FLAG:
        os.chdir(argv[1])
        argv = argv[2:]
    return argv


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


def uses_live_gate_filter(arguments):
    for argument in arguments:
        if not argument.startswith("--test_tag_filters="):
            continue
        filters = argument.split("=", 1)[1].split(",")
        if "requires_live_gate" in filters:
            return True
    return False


def output_base_for(rootfs, arguments):
    if uses_gpu_config(arguments) or rootfs.resolve() == GPU_ROOTFS.resolve():
        return "/tmp/bazel-cache/output-base-gpu"
    if rootfs.resolve() == CURRICULUM_ROOTFS.resolve():
        return "/tmp/bazel-cache/output-base-3d-pathway"
    return "/tmp/bazel-cache/output-base"


def bazel_command(arguments, output_base, update_lock=False, test_environment=None):
    if not arguments:
        arguments = ["help"]
    command, *rest = arguments
    lockfile_mode = "update" if update_lock else "error"
    test_environment = test_environment or {}
    test_environment_flags = (
        [f"--test_env={name}={value}" for name, value in sorted(test_environment.items())]
        if command == "test"
        else []
    )
    return [
        "bazel",
        f"--output_base={output_base}",
        command,
        "--ignore_dev_dependency",
        f"--lockfile_mode={lockfile_mode}",
        "--repository_cache=/tmp/bazel-cache/repository-cache",
        "--disk_cache=/tmp/bazel-cache/disk-cache",
        *test_environment_flags,
        *rest,
    ]


def repo_workspace_mounts(update_lock=False):
    mounts = [Mount("workspace:/experiment", "tmpfs", "/experiment", "writable")]
    for path in sorted(REPO.iterdir(), key=lambda item: item.name):
        if path.name == ".bazel-cache":
            continue
        if update_lock and path.name == "MODULE.bazel.lock":
            continue
        mounts.append(
            Mount(
                f"workspace:/{path.name}",
                "bind",
                "/experiment/" + path.name,
                "read_only",
                path.resolve(),
            )
        )
    if update_lock:
        mounts.append(
            Mount(
                "workspace:/MODULE.bazel.lock",
                "bind",
                "/experiment/MODULE.bazel.lock",
                "writable",
                (REPO / "MODULE.bazel.lock").resolve(),
            )
        )
    return mounts


def sandbox_plan(runtime, cache, arguments, update_lock=False):
    rootfs = runtime.rootfs
    cache = cache.resolve()
    gpu = uses_gpu_config(arguments) or rootfs == GPU_ROOTFS.resolve()
    mounts = [
        Mount("runtime", "bind", "/", "read_only", rootfs),
        Mount("resolver", "bind", "/etc/resolv.conf", "read_only", Path("/etc/resolv.conf")),
        *repo_workspace_mounts(update_lock),
        Mount("outputs", "tmpfs", "/outputs", "writable"),
        Mount("tmp", "tmpfs", "/tmp", "writable"),
        Mount("bazel-cache", "bind", "/tmp/bazel-cache", "writable", cache),
    ]
    test_environment = {}
    if uses_live_gate_filter(arguments):
        _add_nested_launch_support(mounts)
        live_root = LIVE_GATE_CACHE_MOUNT + "/insula/" + current_cpu_rootfs().name
        test_environment = {
            "SUREAL_LIVE_GATE_BWRAP": LIVE_GATE_BWRAP,
            "WAYMO_INSULA_ROOT": live_root,
            "WAYMO_INSULA_LOCK": live_root + ".lock.json",
        }
    environment = [
        ("--setenv", "HOME", "/tmp/bazel-cache/home"),
        ("--setenv", "USER", "sureal"),
        ("--setenv", "LOGNAME", "sureal"),
        ("--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin"),
        ("--setenv", "TMPDIR", "/tmp"),
        ("--setenv", "PYTHONNOUSERSITE", "1"),
        ("--setenv", "PYTHONDONTWRITEBYTECODE", "1"),
    ]
    if gpu:
        gpu_mounts, gpu_environment, gpu_request = _gpu_mounts_environment_and_request(gpu_index=1)
        mounts.extend(gpu_mounts)
        environment = [item for item in environment if not (item[0] == "--setenv" and item[1] == "PATH")]
        environment.extend(gpu_environment)
        test_environment["SUREAL_BAZEL_GPU_DEVICE_UUIDS"] = (
            f"{gpu_request.requested_index}={gpu_request.device_uuid}"
        )
        _add_nested_launch_support(mounts)
        gpu_live_root = LIVE_GATE_CACHE_MOUNT + "/" + current_gpu_rootfs().name
        test_environment["SUREAL_LIVE_GATE_BWRAP"] = LIVE_GATE_BWRAP
        test_environment["WAYMO_GPU_INSULA_ROOT"] = gpu_live_root
        test_environment["WAYMO_GPU_INSULA_LOCK"] = gpu_live_root + ".lock.json"
    else:
        gpu_request = None
    bazel = bazel_command(
        arguments,
        output_base_for(rootfs, arguments),
        update_lock,
        test_environment=test_environment,
    )
    plan = _assemble_plan(
        runtime,
        mounts=mounts,
        environment=environment,
        command=bazel,
        working_directory="/experiment",
        unshare_flags=[
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
        ],
        gpu=gpu_request,
    )
    data = plan_data(plan)
    result = {
        "argv": render_plan(plan),
        "bazel": bazel,
        "environment": data["environment"],
        "mounts": data["mounts"],
        "update_lock": update_lock,
    }
    if "gpu" in data:
        result["gpu"] = data["gpu"]
    return result


def _add_nested_launch_support(mounts):
    inside_paths = {mount.inside_path for mount in mounts}
    if LIVE_GATE_CACHE_MOUNT not in inside_paths:
        mounts.append(Mount("waymo-cache", "bind", LIVE_GATE_CACHE_MOUNT, "read_only", AUTONOMY_CACHE))
    if LIVE_GATE_BWRAP not in inside_paths:
        mounts.append(Mount("live-gate-bwrap", "bind", LIVE_GATE_BWRAP, "read_only", Path("/usr/bin/bwrap")))


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
        runtime = load_runtime_lock(args.rootfs, args.lock)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    plan = sandbox_plan(runtime, args.cache, args.bazel_args, args.update_lock)
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
