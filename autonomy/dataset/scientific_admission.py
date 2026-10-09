"""Pure scientific source admission; this is not a transfer or payload verifier."""
import copy
import re
from dataset.blob_storage import source_blob_key


def check_raw_capacity(retained_bytes, source_bytes, limit_bytes, *, active_objects):
    values = (retained_bytes, source_bytes, limit_bytes, active_objects)
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('raw capacity requires nonnegative integer counts')
    if active_objects != 0:
        raise ValueError('another raw source already owns staging')
    total = retained_bytes + source_bytes
    if total > limit_bytes:
        raise ValueError('combined raw staging limit exceeded')
    return total


def admit_scene(manifest, records, scene):
    """Return an isolated identity manifest only after every required source admits.

    Callers combine the acquisition candidate with the cohort's explicit
    excluded_engineering_segments. Records are keyed by native component tag.
    Admission checks provenance consistency, not source content or live receipts.
    """
    try:
        if scene in manifest['excluded_engineering_segments']:
            raise ValueError('engineering scene cannot enter scientific cohort')
        group = manifest['scenes'][scene]
        official, splits = group['official_split'], group['research_splits']
        allowed = ({'train'}, {'development'}) if official == 'training' else (
            {'validation'}, {'camera_validation'}, {'validation', 'camera_validation'}) if official == 'validation' else ()
        if (not isinstance(splits, list) or len(set(splits)) != len(splits)
                or set(splits) not in allowed):
            raise ValueError('invalid or leaking scientific split membership')
        components = manifest['components']
        if len(set(components)) != len(components) or set(records) != set(components):
            raise ValueError('required component inventory differs')
        for component in components:
            record = records[component]
            if (record['scene'], record['component'], record['official_split'], record['research_splits']) != (
                    scene, component, official, splits):
                raise ValueError('component identity or split conflict')
            digest = record['sha256']
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('invalid source SHA256')
            metadata = record['source_metadata']
            generation = metadata['generation']
            if type(generation) not in (str, int) or not re.fullmatch('[1-9][0-9]*', str(generation)):
                raise ValueError('invalid source generation')
            size = metadata['size']
            if type(size) not in (str, int) or not re.fullmatch('[1-9][0-9]*', str(size)):
                raise ValueError('invalid source object size')
            relative = f'{official}/{component}/{scene}.parquet'
            if metadata['storage_url'] != f'gs://waymo_open_dataset_v_2_0_1/{relative}#{generation}':
                raise ValueError('source URI/generation conflict')
            if 'blob' in record:
                blob = record['blob']
                if (blob.get('key') != source_blob_key(official, component, scene)
                        or blob.get('sha256') != digest
                        or blob.get('bytes') != int(size)
                        or blob.get('verified_by_readback') is not True):
                    raise ValueError('source blob identity conflict')
                descriptor = record.get('store_descriptor')
                if not isinstance(descriptor, dict) or descriptor.get('kind') not in ('waystone', 'local'):
                    raise ValueError('source store descriptor required')
            else:
                if record['hdfs_roundtrip_sha256'] != digest:
                    raise ValueError('source/HDFS digest conflict')
                if record['hdfs_uri'] != manifest['hdfs_root'].rstrip('/') + '/' + relative:
                    raise ValueError('HDFS destination conflict')
            rows = record['inventory']['rows']
            if type(rows) is not int or rows < 0:
                raise ValueError('invalid native inventory count')
        return {'scene': scene, 'official_split': official,
                'research_splits': copy.deepcopy(splits), 'components': copy.deepcopy(records)}
    except (KeyError, TypeError) as error:
        raise ValueError('missing or invalid admission evidence') from error
