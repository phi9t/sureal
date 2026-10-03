"""Independent native-Parquet reconciliation of decoded scene sidecars."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq


def validate_component(source, output):
    source, output = Path(source), Path(output)
    report = json.loads((output/'manifest.json').read_text())

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def digest(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    native = pq.ParquetFile(source)
    require(report['schema_version'] == 1, 'unsupported sidecar schema')
    require(report['source_sha256'] == digest(source), 'native source changed')
    require(report['native_schema_sha256'] == hashlib.sha256(str(native.schema_arrow).encode()).hexdigest(), 'native schema differs')
    require(len(report['rows']) == native.metadata.num_rows, 'native row inventory differs')
    prefixes = {name[:-6] for name in native.schema_arrow.names if name.endswith('.shape')}
    excluded = {prefix+suffix for prefix in prefixes for suffix in ('.values', '.shape')}
    files = {'manifest.json'}; count = 0; array_count = 0
    for batch in native.iter_batches(batch_size=1):
        original = batch.to_pylist()[0]; record = report['rows'][count]
        expected_keys = {name: value for name, value in original.items() if name.startswith('key.')}
        require(record['key'] == expected_keys, 'native identity differs')
        require(expected_keys['key.segment_context_name'] == report['scene'], 'native scene differs')
        for kind in ('metadata', 'arrays'):
            name = record[kind]
            require(isinstance(name, str) and Path(name).name == name and name not in files, 'unsafe or duplicate artifact path')
            files.add(name)
            require(digest(output/name) == record[kind+'_sha256'], 'artifact hash differs')
        metadata = json.loads((output/record['metadata']).read_text())
        require(metadata['fields'] == {name: value for name, value in original.items() if name not in excluded}, 'native scalar fields differ')
        require(set(metadata['array_fields']) == prefixes, 'native array inventory differs')
        with np.load(output/record['arrays'], allow_pickle=False) as arrays:
            aliases = []
            for prefix in prefixes:
                value, shape = original[prefix+'.values'], original[prefix+'.shape']
                alias = metadata['array_fields'][prefix]
                if value is None:
                    require(shape is None and alias is None, 'native missing payload differs')
                    continue
                require(alias is not None and alias in arrays.files, 'native array missing')
                aliases.append(alias); actual = arrays[alias]
                require(list(actual.shape) == shape, 'native array shape differs')
                raw = batch.column(batch.schema.get_field_index(prefix+'.values'))[0].values.to_numpy(zero_copy_only=False)
                require(actual.dtype == raw.dtype, 'native array dtype differs')
                require(np.array_equal(actual.reshape(-1), raw, equal_nan=True), 'native array values differ')
                array_count += 1
            require(len(set(aliases)) == len(aliases) and set(arrays.files) == set(aliases), 'undeclared or shared array alias')
        count += 1
    require({p.name for p in output.iterdir()} == files, 'undeclared component artifacts')
    total = sum((output/name).stat().st_size for name in files)
    require(total == report['output_bytes'], 'derived byte accounting differs')
    return {'rows': count, 'arrays': array_count, 'output_bytes': total,
            'source_sha256': report['source_sha256'], 'status': 'all native identities, scalars and shaped arrays reconciled'}
