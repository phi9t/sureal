"""Canonical digest of exported rootfs content, modes, and link targets."""
import hashlib
import json
import stat
from pathlib import Path
from evidence.source_snapshot import file_sha256


def rootfs_identity(root: Path) -> str:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('missing or symlink rootfs')
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        kind = stat.S_IFMT(info.st_mode)
        record = [path.relative_to(root).as_posix(), kind, stat.S_IMODE(info.st_mode)]
        if stat.S_ISLNK(info.st_mode):
            record.append(str(path.readlink()))
        elif stat.S_ISREG(info.st_mode):
            record.extend([info.st_size, file_sha256(path)])
        elif not stat.S_ISDIR(info.st_mode):
            record.append(info.st_rdev)
        digest.update((json.dumps(record, separators=(',', ':')) + '\n').encode())
    return digest.hexdigest()


def verify_rootfs(root: Path, expected: str) -> None:
    if rootfs_identity(root) != expected:
        raise ValueError('rootfs content does not match runtime lock')
