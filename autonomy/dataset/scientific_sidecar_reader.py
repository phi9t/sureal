"""Verified, row-bounded decoded component replay for scientific reconstruction."""
import json
from pathlib import Path
import re
import numpy as np
from evidence.source_snapshot import file_sha256, require_digest


def iter_sidecar_rows(directory, *, expected_manifest_sha256):
    """Yield native-compatible rows, with one row's payload resident at a time.

    The expected manifest hash must come from independently validated provenance,
    not from the directory being admitted. Array values are returned flattened,
    matching sensor_records.select_rows; shape and absence remain explicit.
    """
    directory = Path(directory)

    try:
        require_digest(expected_manifest_sha256)
    except ValueError as error:
        raise ValueError('independent manifest SHA256 required')
    digest=file_sha256
    manifest_path = directory/'manifest.json'
    if digest(manifest_path) != expected_manifest_sha256:
        raise ValueError('sidecar manifest changed')
    report = json.loads(manifest_path.read_text())
    if report['schema_version'] != 1:
        raise ValueError('unsupported sidecar schema')
    seen, files = set(), {'manifest.json'}
    for record in report['rows']:
        identity = json.dumps(record['key'], sort_keys=True, separators=(',', ':'))
        if identity in seen or record['key'].get('key.segment_context_name') != report['scene']:
            raise ValueError('duplicate or conflicting native identity')
        seen.add(identity)
        for kind in ('metadata', 'arrays'):
            name = record[kind]
            if not isinstance(name, str) or Path(name).name != name or name in files:
                raise ValueError('unsafe or duplicated artifact path')
            files.add(name)
            if digest(directory/name) != record[kind+'_sha256']:
                raise ValueError('sidecar artifact changed')
        metadata = json.loads((directory/record['metadata']).read_text())
        row = metadata['fields']
        if {name: value for name, value in row.items() if name.startswith('key.')} != record['key']:
            raise ValueError('decoded native key differs from admitted identity')
        with np.load(directory/record['arrays'], allow_pickle=False) as arrays:
            aliases = []
            for prefix, alias in metadata['array_fields'].items():
                if not isinstance(prefix, str) or prefix+'.values' in row or prefix+'.shape' in row:
                    raise ValueError('conflicting array field declaration')
                if alias is None:
                    row[prefix+'.values'], row[prefix+'.shape'] = None, None
                else:
                    if not isinstance(alias, str) or alias not in arrays.files or alias in aliases:
                        raise ValueError('missing or shared native array alias')
                    aliases.append(alias); array = arrays[alias]
                    if array.dtype.hasobject or array.ndim == 0 or any(n <= 0 for n in array.shape):
                        raise ValueError('invalid decoded array')
                    row[prefix+'.values'] = array.reshape(-1)
                    row[prefix+'.shape'] = list(array.shape)
            if set(aliases) != set(arrays.files):
                raise ValueError('undeclared decoded arrays')
        yield row
    if {p.name for p in directory.iterdir()} != files:
        raise ValueError('undeclared sidecar artifacts')
