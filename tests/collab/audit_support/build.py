"""Reopen raw container export and bind its actual pinned build provenance."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile

from .conditions import option
from .evidence import artifact, command_record, directory_snapshot
from .facts import require
from .raw_git import InvalidEvidence, sha256


def tar_path(name):
    while name.startswith("./"):
        name=name[2:]
    name=name.rstrip("/")
    if name in {"","."}:
        return None
    path=PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts,"Export archive path escapes rootfs")
    return path.as_posix()


def check_export_archive(archive: Path, root: Path) -> int:
    expected=set();declared=set()
    with tarfile.open(archive,"r:*") as exported:
        for item in exported:
            name=tar_path(item.name)
            if name is None:
                continue
            require(name not in declared,"Duplicate export archive member")
            declared.add(name)
            expected.add(name)
            expected.update(str(parent) for parent in PurePosixPath(name).parents if str(parent)!=".")
            path=root/name
            require(all(not (root/parent).is_symlink() for parent in PurePosixPath(name).parents
                        if str(parent)!="."),"Export member traverses a rootfs symlink")
            require(os.path.lexists(path),"Export archive member missing from actual rootfs")
            info=path.lstat()
            require(stat.S_IMODE(info.st_mode)==item.mode,"Actual export/rootfs mode mismatch")
            if item.isfile() or item.islnk():
                require(stat.S_ISREG(info.st_mode),"Export/rootfs regular file type differs")
                if item.islnk():
                    require(tar_path(item.linkname) is not None,"Invalid export hardlink target")
                stream=exported.extractfile(item)
                require(stream is not None,"Actual export file bytes missing")
                with stream:
                    digest=hashlib.file_digest(stream,"sha256").hexdigest()
                require(sha256(path)==digest,"Actual rootfs bytes differ from exported container")
            elif item.issym():
                require(stat.S_ISLNK(info.st_mode) and os.readlink(path)==item.linkname,
                        "Actual export/rootfs symlink target differs")
            elif item.isdir():
                require(stat.S_ISDIR(info.st_mode),"Actual export directory differs")
            elif item.ischr() or item.isblk():
                require((stat.S_ISCHR(info.st_mode) if item.ischr() else stat.S_ISBLK(info.st_mode)) and
                        os.major(info.st_rdev)==item.devmajor and os.minor(info.st_rdev)==item.devminor,
                        "Actual exported device node differs")
            else:
                raise InvalidEvidence("Unsupported exported rootfs member type")
    observed=set()
    for directory,dirs,files in os.walk(root,followlinks=False):
        observed.update((Path(directory)/name).relative_to(root).as_posix() for name in dirs+files)
    require(observed==expected,"Actual rootfs/export member union differs")
    return len(expected)


def image_digest(value):
    suffix=value.removeprefix("sha256:") if isinstance(value,str) else ""
    require(isinstance(value,str) and value.startswith("sha256:") and len(suffix)==64 and
            all(char in "0123456789abcdef" for char in suffix),"Exact built image content identity required")


def docker_command(ref, action, admission):
    command=command_record(artifact(ref))
    tool=admission["tools"]["docker"]
    executable=artifact(tool)
    require(command["argv"][0]==str(executable) and command["exit_code"]==0 and
            action in command["argv"],"Actual pinned Docker "+action+" command missing")
    return command


def stdout(command):
    return artifact(command["stdout"]).read_text().strip()


def check_build(build, lock, source: Path, rootfs: Path, admission):
    base=build["base_image"]
    require(base==json.loads((source/"experiments/collaboration/runtime/requirements.lock").read_text())["base_image"],
            "Actual build base differs from requirements lock")
    suffix=base.rsplit("@sha256:",1)
    require(len(suffix)==2 and len(suffix[1])==64 and all(char in "0123456789abcdef" for char in suffix[1]),
            "Actual base image unpinned")
    recipe=(source/"experiments/collaboration/runtime/Dockerfile").read_text()
    froms=[line.split()[1] for line in recipe.splitlines() if line.strip().upper().startswith("FROM ")]
    require(froms==[base],"Actual Dockerfile FROM is not the admitted pinned base")
    context=directory_snapshot(build["build_context"])
    require(sha256(context/"Dockerfile")==lock["dockerfile_sha256"] and
            sha256(context/"requirements.lock")==lock["requirements_sha256"],"Actual build context recipe differs")
    requirements=json.loads((context/"requirements.lock").read_text())
    packages=requirements["debian_packages"]
    raw_packages={Path(ref["path"]).name:ref for ref in build["package_artifacts"]}
    require(set(raw_packages)==set(packages),"Actual package artifact union differs from requirements")
    for name,pin in packages.items():
        actual=artifact(raw_packages[name])
        require(sha256(actual)==pin["sha256"]==sha256(context/"packages"/name),
                "Actual offline package bytes differ from admitted lock/context")
    allowed={"Dockerfile","requirements.lock"}|{"packages/"+name for name in packages}
    context_manifest=json.loads(artifact(build["build_context"]).read_text())
    require(set(context_manifest["files"])==allowed,"Undeclared build context files")
    command=docker_command(build["build_command"],"build",admission)
    argv=command["argv"]
    recipe_flag="--file" if "--file" in argv else "-f"
    require(option(argv,recipe_flag)==str(context/"Dockerfile") and argv[-1]==str(context) and
            ("--network=none" in argv or "--network" in argv and option(argv,"--network")=="none"),
            "Actual build argv not bound to exact offline context/recipe")
    image_id_file=artifact(build["image_id_file"])
    require(option(argv,"--iidfile")==str(image_id_file) and image_id_file.read_text().strip()==build["image_id"],
            "Actual build image-id output differs from inspected image")
    base_command=docker_command(build["base_inspect_command"],"inspect",admission)
    require(base in base_command["argv"] and base in stdout(base_command),"Actual base readback differs")
    image_digest(build["image_id"])
    inspect=docker_command(build["inspect_command"],"inspect",admission)
    require(build["image_id"] in inspect["argv"] and stdout(inspect)==build["image_id"],
            "Actual built image inspect identity differs")
    create=docker_command(build["create_command"],"create",admission)
    container=build["container_id"]
    require(len(container)==64 and all(x in "0123456789abcdef" for x in container) and
            build["image_id"] in create["argv"] and stdout(create)==container,
            "Actual export container not created from admitted image")
    container_inspect=docker_command(build["container_inspect_command"],"inspect",admission)
    require(container in container_inspect["argv"] and stdout(container_inspect)==build["image_id"],
            "Actual export container image binding differs")
    export=docker_command(build["export_command"],"export",admission)
    archive=artifact(build["rootfs_archive"])
    require(container in export["argv"] and ("--output" in export["argv"] or "-o" in export["argv"]) and
            option(export["argv"],"--output" if "--output" in export["argv"] else "-o")==str(archive),
            "Actual export argv not bound to retained container/archive")
    members=check_export_archive(archive,rootfs)
    inventory=json.loads(artifact(build["rootfs_inventory"]).read_text())
    require(inventory["rootfs_sha256"]==build["rootfs_sha256"] and inventory["member_count"]==members,
            "Actual independently reopened export inventory differs")
    capabilities=[command_record(artifact(ref)) for ref in build["capability_commands"]]
    require(any(Path(record["argv"][0]).name=="git" and record["argv"][1:]==["--version"] and
                record["exit_code"]==0 and stdout(record).startswith("git version ") for record in capabilities),
            "Actual native Git capability missing")
    require(any(Path(record["argv"][0]).name.startswith("python") and record["argv"][1:]==["--version"] and
                record["exit_code"]==0 and stdout(record).startswith("Python 3.") for record in capabilities),
            "Actual native Python capability missing")
    return members
