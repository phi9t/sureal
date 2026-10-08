"""Read Git facts without index refresh, hooks or shell interpolation."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .contracts import Refusal


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def physical(path: Path) -> Path:
    path = Path(path).absolute()
    if path != path.resolve() or any(part.is_symlink() for part in [path, *path.parents]):
        raise Refusal("DIRTY_SOURCE", "source/state aliases are not admitted")
    return path


def run_git(root: Path, *args: str, input_bytes: bytes | None = None, tool_pin: dict | None = None) -> bytes:
    found = tool_pin.get("path") if tool_pin else shutil.which("git", path=os.defpath)
    if found is None:
        raise Refusal("SOURCE_UNAVAILABLE", "Git is unavailable")
    git = physical(Path(found)) if tool_pin else Path(found).resolve()
    if tool_pin and sha(git) != tool_pin.get("sha256"):
        raise Refusal("SOURCE_UNAVAILABLE", "Git executable differs from project pin")
    environment = {"PATH": os.defpath, "LC_ALL": "C",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                   "GIT_TERMINAL_PROMPT": "0"}
    try:
        with tempfile.TemporaryDirectory(prefix="sureal-collab-private-hooks-") as hooks:
            result = subprocess.run([str(git), "--no-optional-locks", "-c", "core.hooksPath=" + hooks,
                                     "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                                     "-C", str(root), *args], input=input_bytes, capture_output=True,
                                    env=environment, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Refusal("SOURCE_UNAVAILABLE", "Git read did not complete") from error
    if result.returncode:
        raise Refusal("SOURCE_UNAVAILABLE", "Git identity/object is unavailable",
                      {"argv": ["git", *args], "exit_code": result.returncode})
    return result.stdout


class GitWorkspace:
    @staticmethod
    def inspect(root: Path, *, tool_pin: dict | None = None):
        root = physical(root)
        def read(*args):
            return run_git(root, *args, tool_pin=tool_pin)
        top = Path(read("rev-parse", "--path-format=absolute", "--show-toplevel").decode().strip())
        if top != root:
            raise Refusal("DIRTY_SOURCE", "exact repository root required")
        common = Path(read("rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
        git_dir = Path(read("rev-parse", "--path-format=absolute", "--git-dir").decode().strip())
        head = read("rev-parse", "--verify", "HEAD^{commit}").decode().strip()
        refs = {}
        for line in read("for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines():
            ref, commit = line.split(" ", 1)
            refs[ref] = commit
        # symbolic-ref --quiet legitimately returns1 for detached source.
        ref = (git_dir / "HEAD").read_text().strip()
        ref = ref.removeprefix("ref: ") if ref.startswith("ref: ") else None
        index = git_dir / "index"
        config = common / "config"
        return {"schema_version": 1, "root": str(root), "common_git_dir": str(common), "git_dir": str(git_dir),
                "ref": ref, "head": head, "tree": read("rev-parse", "HEAD^{tree}").decode().strip(),
                "index_sha256": sha(index) if index.exists() else None, "refs": refs,
                "status_z_hex": read("status", "--porcelain=v1", "-z", "--untracked-files=all").hex(),
                "ignored_z_hex": read("status", "--porcelain=v1", "-z", "--ignored", "--untracked-files=all").hex(),
                "submodule_status": read("submodule", "status", "--recursive").decode(),
                "config_sha256": sha(config) if config.exists() else None}


def admitted_source(root: Path, ref: str, base: str, *, tool_pin: dict | None = None):
    facts = GitWorkspace.inspect(root, tool_pin=tool_pin)
    if facts["ref"] != ref:
        raise Refusal("UNADMITTED_SPEC", "canonical integration ref differs from admission", facts)
    if facts["head"] != base:
        raise Refusal("STALE_BASE", "current canonical base differs from admission", facts)
    if facts["status_z_hex"]:
        raise Refusal("DIRTY_SOURCE", "tracked/index/untracked source must be clean", facts)
    if any(line.startswith(("+", "U")) for line in facts["submodule_status"].splitlines()):
        raise Refusal("DIRTY_SOURCE", "submodule disposition changed", facts)
    return facts
