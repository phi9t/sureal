"""Offline, hash-bound full training-box producer or independent verifier job.

The host owns HDFS transfer/staging and supplies one verified byte-stream source
at a time. This worker owns full metadata admission, row consumption and aggregate
publication. It never acquires data, selects a smaller cohort or adopts anchors.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import sys
import tempfile
import time

from dataset.scientific_admission import admit_scene
from evidence.source_snapshot import file_sha256, require_regular_file
from .training_box_wire import stream_training_box_sources


_JSON_BYTES = 32 * 1024**2


def _pinned_json(path, expected):
    path = Path(path)
    if (not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected)
            or require_regular_file(path).stat().st_size > _JSON_BYTES):
        raise ValueError('bounded regular hash-pinned metadata required')
    with path.open('rb') as file:
        content = file.read(_JSON_BYTES + 1)
    if len(content) > _JSON_BYTES or file_sha256(path) != expected:
        raise ValueError('metadata identity differs')
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError('metadata object required')
    return value


def _admit_inputs(job):
    try:
        if job['schema_version'] != 1:
            raise ValueError('unsupported training-box job schema')
        acquisition = _pinned_json(job['acquisition']['path'], job['acquisition']['sha256'])
        cohort = _pinned_json(job['cohort']['path'], job['cohort']['sha256'])
        membership = acquisition['scenes']
        components = acquisition['components']
        exclusions = cohort['excluded_engineering_segments']
        if (cohort['dataset'] != 'perception-v2.0.1' or not isinstance(membership, dict)
                or len(membership) != 103 or not isinstance(components, list)
                or len(components) != 17 or len(set(components)) != 17 or 'lidar_box' not in components
                or not isinstance(exclusions, list) or not all(isinstance(s, str) for s in exclusions)):
            raise ValueError('original full Perception cohort/source inventory required')
        training = {scene for scene, group in membership.items()
                    if isinstance(group, dict) and group.get('official_split') == 'training'
                    and group.get('research_splits') == ['train']}
        original = cohort['cohorts']['train']
        order = job['scene_order']
        pins = job['source_receipt_hashes']
        if (len(training) != 64 or not isinstance(original, list) or len(original) != 64
                or len(set(original)) != 64 or set(original) != training
                or not isinstance(order, list) or len(order) != 64 or len(set(order)) != 64
                or set(order) != training or not isinstance(pins, dict) or set(pins) != training):
            raise ValueError('all original64 training scenes required; no reduced or non-training selection')
        audit = Path(job['source_audit_root'])
        if not audit.is_dir():
            raise ValueError('admitted source receipt root required')
        manifest = dict(acquisition, excluded_engineering_segments=exclusions)
        inventory = []
        for scene in order:
            if not isinstance(pins[scene], dict) or set(pins[scene]) != set(components):
                raise ValueError('all17 source receipt identities required per training scene')
            records = {}
            for component in components:
                filename = f'training-{component}-{scene}.json'
                if Path(filename).name != filename or '..' in Path(filename).parts:
                    raise ValueError('unsafe source receipt identity')
                records[component] = _pinned_json(audit / filename, pins[scene][component])
            admitted = admit_scene(manifest, records, scene)
            source = admitted['components']['lidar_box']
            inventory.append({'scene': scene, 'bytes': int(source['source_metadata']['size']),
                              'native_rows': source['inventory']['rows'], 'sha256': source['sha256'],
                              'md5_base64': source['source_metadata']['md5_hash']})
        return inventory, membership, order
    except (KeyError, TypeError) as error:
        raise ValueError('missing or malformed original source admission') from error


def _publish_complete(path, result):
    """Expose only a completely written result, without replacing existing output."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.partial-box-',
                                         delete=False) as file:
            temporary = Path(file.name)
            json.dump(result, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_training_box_job(job_path, *, expected_job_sha256, mode, source_stream,
                         acknowledgement_stream, output_path):
    """Run one offline pass after admitting all64×17 externally pinned receipts.

    Reference mode additionally hash-pins the producer report before consuming
    fresh source bytes. Worker output is created only after the full byte stream,
    source accounting and statistics/quantile checks succeed. Live runtime and
    host staging/HDFS receipts are separate required caller evidence.
    """
    if mode not in ('producer', 'reference'):
        raise ValueError('explicit producer/reference worker role required')
    started = time.monotonic()
    output = Path(output_path)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('new private worker output required')
    if importlib.util.find_spec('tensorflow') is not None:
        raise ValueError('TensorFlow-free worker required')
    job = _pinned_json(job_path, expected_job_sha256)
    inventory, membership, order = _admit_inputs(job)
    reported = None
    if mode == 'reference':
        try:
            reported = _pinned_json(job['reported']['path'], job['reported']['sha256'])
        except (KeyError, TypeError) as error:
            raise ValueError('hash-pinned producer report required') from error
        identity = reported.get('job_identity')
        expected_identity = {
            'mode': 'producer',
            'acquisition_sha256': job['acquisition']['sha256'],
            'cohort_sha256': job['cohort']['sha256'],
            'source_receipt_hashes': job['source_receipt_hashes'],
        }
        if not isinstance(identity, dict) or any(
                identity.get(key) != value for key, value in expected_identity.items()):
            raise ValueError('producer report provenance must match admitted sources and cohort')

    def acknowledge(event):
        acknowledgement_stream.write(json.dumps(event) + '\n')
        acknowledgement_stream.flush()

    sources = stream_training_box_sources(source_stream, inventory=inventory, acknowledge=acknowledge)
    if mode == 'producer':
        from .training_box_sources import training_box_statistics_from_sources
        result = training_box_statistics_from_sources(sources, membership=membership, expected_scenes=order)
    else:
        from .training_box_reference import verify_training_box_distributions
        result = verify_training_box_distributions(sources, reported=reported,
                                                   membership=membership, expected_scenes=order)
    result['job_identity'] = {'mode': mode, 'job_sha256': expected_job_sha256,
                              'acquisition_sha256': job['acquisition']['sha256'],
                              'cohort_sha256': job['cohort']['sha256'],
                              'source_receipt_hashes': job['source_receipt_hashes']}
    result['worker_resources'] = {
        'elapsed_seconds': time.monotonic() - started,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'rss_scope': 'worker_process_peak',
    }
    _publish_complete(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--expected-job-sha256', required=True)
    parser.add_argument('--mode', choices=('producer', 'reference'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_training_box_job(args.job, expected_job_sha256=args.expected_job_sha256,
                                  mode=args.mode, source_stream=sys.stdin.buffer,
                                  acknowledgement_stream=sys.stdout, output_path=args.output)
    print('PASS complete training-box', args.mode, result.get('native_rows'), 'native rows', file=sys.stderr)


if __name__ == '__main__':
    main()
