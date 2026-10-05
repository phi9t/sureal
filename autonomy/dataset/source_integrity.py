"""Bounded source-byte verification before payload decoding or promotion."""
import base64
import hashlib
import os
import re
import stat
from evidence.source_snapshot import require_digest, require_regular_file


def verify_source(path, *, size_bytes, sha256, md5_base64):
    if type(size_bytes) is not int or size_bytes <= 0:
        raise ValueError('source size must be a positive integer')
    if not isinstance(sha256, str) or not re.fullmatch('[0-9a-f]{64}', sha256):
        raise ValueError('invalid expected source SHA256')
    require_digest(sha256)
    try:
        md5_bytes = base64.b64decode(md5_base64, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('invalid expected MD5') from error
    if len(md5_bytes) != 16 or base64.b64encode(md5_bytes).decode() != md5_base64:
        raise ValueError('invalid expected MD5')
    try:
        require_regular_file(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != size_bytes:
                raise ValueError('source is not a regular file of expected size')
            sha, md5 = hashlib.sha256(), hashlib.md5()
            count = 0
            for block in iter(lambda: source.read(1024 * 1024), b''):
                count += len(block); sha.update(block); md5.update(block)
            after = os.fstat(source.fileno())
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(before) != identity(after):
                raise ValueError('source changed during verification')
    except OSError as error:
        raise ValueError('source cannot be opened safely') from error
    actual = {'size_bytes': count, 'sha256': sha.hexdigest(),
              'md5_base64': base64.b64encode(md5.digest()).decode()}
    if actual != {'size_bytes': size_bytes, 'sha256': sha256, 'md5_base64': md5_base64}:
        raise ValueError('source content differs from immutable identity')
    return actual
