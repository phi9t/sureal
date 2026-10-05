"""Additive collaboration entry; frozen scientific entrypoints remain untouched."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_plan(rootfs, reference, source, output, command, lock_path):
    if sys.version_info < (3, 11):
        raise ValueError("Python3.11 or newer required by frozen resource helpers")
    reference = Path(reference).resolve()
    lock = json.loads(Path(lock_path).read_bytes())
    recipe = Path(__file__).resolve().parent
    if lock.get("schema_version") != 1 or lock.get("kind") != "collaboration-runtime-lock":
        raise ValueError("separate collaboration runtime lock required")
    for field, name in (("dockerfile_sha256", "Dockerfile"), ("requirements_sha256", "requirements.lock")):
        if lock.get(field) != file_sha(recipe / name):
            raise ValueError("additive runtime recipe differs from lock")
    required = {"pipeline/insula_entry.py", "pipeline/runtime_identity.py"}
    if not required <= set(lock.get("helpers", {})):
        raise ValueError("frozen helper identity missing")
    for relative, expected in lock["helpers"].items():
        path = reference / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or path.is_symlink() or file_sha(path) != expected:
            raise ValueError("frozen helper content differs")
    sys.path.insert(0, str(reference))
    entry = importlib.import_module("pipeline.insula_entry")
    identity = importlib.import_module("pipeline.runtime_identity")
    if (Path(entry.__file__).resolve() != reference / "pipeline/insula_entry.py"
            or Path(identity.__file__).resolve() != reference / "pipeline/runtime_identity.py"):
        raise ValueError("frozen helper import came from another source")
    for name in ("experiment", "source", "outputs"):
        target = Path(rootfs) / name
        if not target.is_dir() or target.is_symlink():
            raise ValueError("physical rootfs mount destination missing: /" + name)
    identity.verify_rootfs(Path(rootfs), lock["rootfs_sha256"])
    plan = entry.launch_plan(rootfs, reference, source, output, command)
    path_index = plan.index("PYTHONPATH")
    plan[path_index + 1] = "/source:/experiment"
    directory_index = plan.index("--chdir")
    plan[directory_index + 1] = "/source"
    return plan


def main():
    parser = argparse.ArgumentParser()
    for name in ("rootfs", "reference", "source", "output", "lock"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--emit-plan", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("original worker command required")
    plan = make_plan(args.rootfs, args.reference, args.source, args.output, command, args.lock)
    if args.emit_plan:
        print(json.dumps(plan))
    else:
        os.execvp(plan[0], plan)


if __name__ == "__main__":
    main()
