#!/usr/bin/env python3
"""Readonly public Python startup provenance. No RPC, goal, queue or filesystem writes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import sysconfig


def reference(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest}


def sample():
    stdlib = Path(sysconfig.get_path('stdlib')).resolve()
    bootstrap = []
    for name, module in sorted(sys.modules.items()):
        file = getattr(module, '__file__', None)
        if not file or name == '__main__':
            continue
        path = Path(file).resolve()
        if not path.is_relative_to(stdlib):
            bootstrap.append({'name': name, 'observed_path': str(Path(file)), **reference(path)})
    return {'schema_version': 1, 'kind': 'PythonBootstrapSample',
        'interpreter': reference(Path('/proc/self/exe').resolve()),
        'stdlib_root': str(stdlib), 'bootstrap_modules': bootstrap,
        'argv': [os.fsdecode(piece) for piece in Path('/proc/self/cmdline').read_bytes().split(b'\0') if piece],
        'source': reference(__file__)}


if __name__ == '__main__':
    print(json.dumps(sample(), sort_keys=True, separators=(',', ':')))
