"""Raw-object materialization, independent filesystem tree reconstruction.

No archive attributes, worktree checkout, smudge filters or product imports.
Gitlinks remain declared objects, never filesystem inputs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile


class InvalidEvidence(ValueError):
    """A missing, malformed, mismatched or unprovable evidence contract."""


def run_git(repository: Path, *argv: str, data: bytes | None = None) -> bytes:
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_COUNT"):
        env.pop(name, None)
    try:
        result = subprocess.run(["git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null",
                                 "-C", str(repository), *argv], input=data, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except subprocess.TimeoutExpired as error:
        raise InvalidEvidence("Bounded Git read/rebuild timed out") from error
    if result.returncode:
        raise InvalidEvidence("Git read/rebuild failed: " + result.stderr.decode(errors="replace"))
    return result.stdout


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strict_json(path: Path) -> dict:
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise InvalidEvidence("Duplicate JSON key: " + key)
            obj[key] = value
        return obj
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               InvalidEvidence("Nonfinite JSON number")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvalidEvidence("Unreadable JSON artifact: " + str(path)) from error
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise InvalidEvidence("Expected schema_version1 object: " + str(path))
    return value


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def commit_context(repository: Path, candidate: str) -> dict:
    if len(candidate) not in (40, 64) or any(x not in "0123456789abcdef" for x in candidate):
        raise InvalidEvidence("Exact hexadecimal commit identity required")
    raw = run_git(repository, "cat-file", "commit", candidate)
    headers = raw.split(b"\n\n", 1)[0].splitlines()
    trees = [line[5:].decode() for line in headers if line.startswith(b"tree ")]
    parents = [line[7:].decode() for line in headers if line.startswith(b"parent ")]
    if len(trees) != 1 or len(parents) != 1:
        raise InvalidEvidence("Candidate must have exactly one parent")
    return {"candidate": candidate, "tree": trees[0], "parent": parents[0],
            "commit_sha256": hashlib.sha256(raw).hexdigest()}


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(x in ("", ".", "..", ".git") for x in path.parts):
        raise InvalidEvidence("Unsafe raw source path: " + value)
    if str(path) != value or "\x00" in value:
        raise InvalidEvidence("Noncanonical raw source path")
    return path


def entries(repository: Path, tree: str) -> list[dict]:
    result = []
    for record in run_git(repository, "ls-tree", "-rz", tree).split(b"\0"):
        if not record:
            continue
        head, name = record.split(b"\t", 1)
        mode, kind, oid = head.decode("ascii").split()
        path = name.decode("utf-8", errors="strict")
        safe_path(path)
        if (mode, kind) not in {("100644", "blob"), ("100755", "blob"),
                               ("120000", "blob"), ("160000", "commit")}:
            raise InvalidEvidence("Unsupported raw tree mode/type")
        result.append({"path": path, "mode": mode, "kind": kind, "oid": oid})
    return result


def raw_blobs(repository: Path, listed: list[dict]) -> dict[str, bytes]:
    ids = list(dict.fromkeys(item["oid"] for item in listed if item["kind"] == "blob"))
    stream = run_git(repository, "cat-file", "--batch", data="\n".join(ids).encode() + b"\n")
    output = {}
    cursor = 0
    for oid in ids:
        ending = stream.find(b"\n", cursor)
        header = stream[cursor:ending].decode().split()
        if len(header) != 3 or header[:2] != [oid, "blob"]:
            raise InvalidEvidence("Raw object batch mismatch")
        size = int(header[2]); start = ending + 1
        data = stream[start:start + size]
        if len(data) != size or stream[start + size:start + size + 1] != b"\n":
            raise InvalidEvidence("Truncated raw object")
        output[oid] = data
        cursor = start + size + 1
    if stream[cursor:]:
        raise InvalidEvidence("Extra raw object data")
    return output


def link_target(path: str, data: bytes, links: dict[str, str]) -> str:
    target = data.decode("utf-8", errors="strict")
    if not target or target.startswith("/") or "\x00" in target:
        raise InvalidEvidence("Unsafe symlink target")
    def normalize(parts):
        stack = []
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                if not stack:
                    raise InvalidEvidence("Symlink escapes source")
                stack.pop()
            else:
                stack.append(part)
                if "/".join(stack) in links:
                    raise InvalidEvidence("Symlink traversal before path normalization")
        return stack
    normalized = normalize([*PurePosixPath(path).parts[:-1], *target.split("/")])
    if ".git" in normalized:
        raise InvalidEvidence("Symlink references Git metadata")
    # Disallow chained traversal, including cycles, instead of following mutable links.
    for length in range(1, len(normalized) + 1):
        if "/".join(normalized[:length]) in links:
            raise InvalidEvidence("Symlink target traverses another symlink")
    return target


def filesystem_manifest(source: Path, listed: list[dict]) -> list[dict]:
    if source.is_symlink() or not source.is_dir():
        raise InvalidEvidence("Regular source directory required")
    expected = {item["path"]: item for item in listed if item["kind"] == "blob"}
    permitted_dirs = {str(parent) for path in expected for parent in PurePosixPath(path).parents
                      if str(parent) != "."}
    observed = set()
    for directory, dirs, files in os.walk(source, followlinks=False):
        for name in list(dirs) + files:
            path = Path(directory) / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or not path.is_dir():
                observed.add(rel)
            elif rel not in permitted_dirs:
                raise InvalidEvidence("Extra source directory: " + rel)
    if observed != set(expected):
        raise InvalidEvidence("Missing or extra materialized source files")
    links = {item["path"]: os.readlink(source / item["path"])
             for item in listed if item["mode"] == "120000"}
    manifest = []
    for item in listed:
        record = dict(item)
        if item["mode"] == "160000":
            if os.path.lexists(source / item["path"]):
                raise InvalidEvidence("Gitlink must remain manifest-only")
            record["excluded"] = True
        else:
            path = source / item["path"]
            info = path.lstat()
            if item["mode"] == "120000":
                if not stat.S_ISLNK(info.st_mode):
                    raise InvalidEvidence("Expected source symlink")
                data = os.fsencode(os.readlink(path))
                record["link_target"] = link_target(item["path"], data, links)
            else:
                if not stat.S_ISREG(info.st_mode):
                    raise InvalidEvidence("Expected regular source file")
                want_mode = 0o755 if item["mode"] == "100755" else 0o644
                if stat.S_IMODE(info.st_mode) != want_mode:
                    raise InvalidEvidence("Materialized source mode changed")
                data = path.read_bytes()
            record["sha256"] = hashlib.sha256(data).hexdigest()
            record["bytes"] = len(data)
        manifest.append(record)
    return manifest


def rebuild_tree(source: Path, listed: list[dict], object_format: str = "sha1") -> str:
    """Hash actual reopened bytes and construct all trees in an unrelated Git DB."""
    with tempfile.TemporaryDirectory(prefix="a49-rebuild-") as temp:
        repo = Path(temp)
        run_git(repo, "init", "--bare", "-q", "--object-format=" + object_format)
        root = {}
        for item in listed:
            parts = safe_path(item["path"]).parts
            node = root
            for part in parts[:-1]:
                node = node.setdefault(part, {})
                if not isinstance(node, dict):
                    raise InvalidEvidence("Conflicting raw tree paths")
            if item["mode"] == "160000":
                oid = item["oid"]
            else:
                path = source / item["path"]
                data = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
                oid = run_git(repo, "hash-object", "-w", "--stdin", data=data).decode().strip()
                if oid != item["oid"]:
                    raise InvalidEvidence("Actual source content differs from raw blob")
            node[parts[-1]] = (item["mode"], item["kind"], oid)
        def write(node):
            records = []
            for name, value in node.items():
                mode, kind, oid = ("040000", "tree", write(value)) if isinstance(value, dict) else value
                records.append(f"{mode} {kind} {oid}\t".encode() + name.encode() + b"\0")
            return run_git(repo, "mktree", "-z", "--missing", data=b"".join(records)).decode().strip()
        return write(root)


def materialize(repository: Path, candidate: str, source: Path, receipt: Path, owner: str) -> dict:
    context = commit_context(repository, candidate)
    if not owner or not source.is_absolute() or not receipt.is_absolute():
        raise InvalidEvidence("Explicit absolute owned output paths required")
    if os.path.lexists(source) or receipt.exists():
        raise InvalidEvidence("Fresh materialization outputs required")
    listed = entries(repository, context["tree"])
    blobs = raw_blobs(repository, listed)
    links = {item["path"]: blobs[item["oid"]].decode("utf-8")
             for item in listed if item["mode"] == "120000"}
    # Validate every target before creating any source entry.
    for item in listed:
        if item["mode"] == "120000":
            link_target(item["path"], blobs[item["oid"]], links)
    source.mkdir(parents=True)
    for item in listed:
        if item["kind"] == "commit":
            continue
        destination = source / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item["mode"] == "120000":
            destination.symlink_to(links[item["path"]])
        else:
            destination.write_bytes(blobs[item["oid"]])
            destination.chmod(0o755 if item["mode"] == "100755" else 0o644)
    manifest = filesystem_manifest(source, listed)
    rebuilt = rebuild_tree(source, listed, "sha256" if len(candidate) == 64 else "sha1")
    if rebuilt != context["tree"]:
        raise InvalidEvidence("Independent tree reconstruction mismatch")
    value = {"schema_version": 1, "kind": "raw-materialization", **context,
             "repository": str(repository.resolve()), "source": str(source),
             "owner": owner, "entries": manifest, "rebuilt_tree": rebuilt,
             "gitlinks_excluded": [x["path"] for x in manifest if x["mode"] == "160000"]}
    write_new(receipt, value)
    return value


def verify_materialization(receipt: Path, candidate: str) -> dict:
    value = strict_json(receipt)
    if value.get("kind") != "raw-materialization" or value.get("candidate") != candidate:
        raise InvalidEvidence("Materialization identity mismatch")
    repository = Path(value["repository"])
    context = commit_context(repository, candidate)
    for key, fact in context.items():
        if value.get(key) != fact:
            raise InvalidEvidence("Retained raw candidate differs: " + key)
    listed = entries(repository, context["tree"])
    source = Path(value["source"])
    manifest = filesystem_manifest(source, listed)
    rebuilt = rebuild_tree(source, listed, "sha256" if len(candidate) == 64 else "sha1")
    if manifest != value["entries"] or rebuilt != context["tree"] or rebuilt != value["rebuilt_tree"]:
        raise InvalidEvidence("Materialized source or rebuilt tree changed")
    return value


def retain(repository: Path, candidate: str, output: Path, owner: str) -> dict:
    """Retain all reachable raw objects without changing source repository refs."""
    context = commit_context(repository, candidate)
    if not owner or not output.is_absolute() or os.path.lexists(output):
        raise InvalidEvidence("Fresh absolute owned retention directory required")
    names = run_git(repository, "rev-list", "--objects", candidate)
    pack = run_git(repository, "pack-objects", "--stdout", data=names)
    output.mkdir(parents=True)
    pack_path = output / "objects.pack"
    with pack_path.open("xb") as stream:
        stream.write(pack)
        stream.flush()
        os.fsync(stream.fileno())
    recovered = output / "objects.git"
    recovered.mkdir()
    fmt = "sha256" if len(candidate) == 64 else "sha1"
    run_git(recovered, "init", "--bare", "-q", "--object-format=" + fmt)
    run_git(recovered, "index-pack", "--stdin", data=pack)
    run_git(recovered, "update-ref", "refs/retained/candidate", candidate)
    run_git(recovered, "fsck", "--full", "--no-reflogs")
    if commit_context(recovered, candidate) != context:
        raise InvalidEvidence("Cold retained raw commit differs")
    value = {"schema_version": 1, "kind": "raw-retention", **context,
             "owner": owner, "repository": str(recovered), "pack_path": str(pack_path),
             "pack_sha256": sha256(pack_path), "bytes": pack_path.stat().st_size,
             "object_count": len(names.splitlines())}
    write_new(output / "retention.json", value)
    return value


def verify_retention(path: Path, candidate: str) -> dict:
    value=strict_json(path)
    if value.get("kind")!="raw-retention" or value.get("candidate")!=candidate:
        raise InvalidEvidence("Exact retained candidate identity required")
    pack=Path(value["pack_path"])
    if not pack.is_file() or pack.is_symlink() or sha256(pack)!=value["pack_sha256"]:
        raise InvalidEvidence("Retained raw pack changed")
    with tempfile.TemporaryDirectory(prefix="a49-cold-pack-") as temp:
        recovered=Path(temp)
        fmt="sha256" if len(candidate)==64 else "sha1"
        run_git(recovered,"init","--bare","-q","--object-format="+fmt)
        run_git(recovered,"index-pack","--stdin",data=pack.read_bytes())
        run_git(recovered,"update-ref","refs/retained/candidate",candidate)
        run_git(recovered,"fsck","--full","--no-reflogs")
        actual=commit_context(recovered,candidate)
        if any(value.get(key)!=fact for key,fact in actual.items()):
            raise InvalidEvidence("Fresh cold raw pack candidate/tree differs")
        reachable=run_git(recovered,"rev-list","--objects",candidate).splitlines()
        if value["object_count"]!=len(reachable) or pack.stat().st_size!=value["bytes"]:
            raise InvalidEvidence("Raw retained reachable object count/pack bytes differ")
    existing=commit_context(Path(value["repository"]),candidate)
    if existing!=actual:
        raise InvalidEvidence("Existing retained repository differs from fresh pack")
    return value
