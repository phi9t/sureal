"""Independent retained-evidence audit; never invokes a distribution producer."""
import json
import math
from pathlib import Path

from evidence.source_snapshot import file_sha256


def verify_replay_receipt(root, *, expected_receipt_sha256, expected_job,
                          expected_sources, expected_runtime_lock, code_root):
    root, code_root = Path(root), Path(code_root)
    try:
        if (len(expected_sources) != 64 or len({s['scene'] for s in expected_sources}) != 64
                or [s['scene'] for s in expected_sources] != expected_job['scene_order']):
            raise ValueError('original full64 ordered source inventory required')
        receipt_path = root / 'receipt.json'
        if file_sha256(receipt_path) != expected_receipt_sha256:
            raise ValueError('externally pinned replay receipt changed')
        receipt = json.loads(receipt_path.read_text())
        if receipt['runtime_lock'] != expected_runtime_lock or len(receipt['phases']) != 2:
            raise ValueError('two passes in pinned runtime required')
        for name, digest in receipt['code_hashes'].items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts or file_sha256(code_root / path) != digest:
                raise ValueError('retained worker code differs')
        reports = []
        for role, phase in zip(('producer', 'reference'), receipt['phases']):
            folder = root / role
            if json.loads((folder / 'receipt.json').read_text()) != phase:
                raise ValueError('phase receipt differs from final replay evidence')
            report_path = folder / 'report.json'
            if file_sha256(report_path) != phase['report_sha256'] or phase['exit_code'] != 0:
                raise ValueError('successful hash-pinned worker report required')
            report = json.loads(report_path.read_text())
            identity = report['job_identity']
            for field, expected in [('mode', role), ('acquisition_sha256', expected_job['acquisition']['sha256']),
                                    ('cohort_sha256', expected_job['cohort']['sha256']),
                                    ('source_receipt_hashes', expected_job['source_receipt_hashes'])]:
                if identity[field] != expected:
                    raise ValueError('worker report provenance differs')
            if len(phase['acknowledgements']) != 64 or len(phase['transfers']) != 64:
                raise ValueError('full64 source ACK and transfer evidence required')
            for source, ack, transfer in zip(expected_sources, phase['acknowledgements'], phase['transfers']):
                h = source['header']
                expected_ack = dict(scene=source['scene'], sha256=h['sha256'],
                                    native_rows=h['native_rows'], status='consumed')
                if ack != expected_ack or transfer['scene'] != source['scene']:
                    raise ValueError('source consumed identity differs')
                for key, value in [('size_bytes', h['bytes']), ('sha256', h['sha256']),
                                   ('md5_base64', h['md5_base64']), ('hdfs_uri', source['hdfs_uri']),
                                   ('transfer_exit_code', 0)]:
                    if transfer[key] != value:
                        raise ValueError('verified source readback differs')
                if transfer['raw_peak_bytes_including_retained'] > transfer['file_size_limit_bytes'] + (
                        transfer['raw_peak_bytes_including_retained'] - transfer['size_bytes']):
                    raise ValueError('source exceeded file-size bound')
            resources = report['worker_resources']
            if (phase['worker_resources'] != resources or resources['rss_scope'] != 'worker_process_peak'
                    or type(resources['peak_rss_kib']) is not int or resources['peak_rss_kib'] <= 0
                    or not math.isfinite(resources['elapsed_seconds']) or resources['elapsed_seconds'] < 0):
                raise ValueError('valid in-worker resources required')
            reports.append(report)
        producer, reference = reports
        scenes = expected_job['scene_order']
        native_rows = sum(s['header']['native_rows'] for s in expected_sources)
        if (producer['completed_sources'] != sorted(scenes) or reference['completed_sources'] != 64
                or producer['native_rows'] != native_rows or reference['native_rows'] != native_rows
                or reference['status'] != 'native source accounting and quantiles independently verified'):
            raise ValueError('complete native accounting required')
        categories = {'1', '2', '3', '4'}
        fields = {'median_length_width_height_center_z', 'p10_length_width_height_center_z',
                  'p90_length_width_height_center_z'}
        if (set(reference['reference_quantiles']) != categories
                or set(producer['classes']) != categories
                or reference['eligible_box_rows'] != producer['rows']):
            raise ValueError('complete class quantile proof and eligible accounting required')
        for category, checked in reference['reference_quantiles'].items():
            produced = producer['classes'][category]
            if not isinstance(checked, dict) or set(checked) != fields:
                raise ValueError('all independent native quantile fields required')
            for field, values in checked.items():
                actual = produced[field]
                if values is None:
                    if actual is not None:
                        raise ValueError('absent class acquired quantiles')
                    continue
                if len(actual) != 4 or any(not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                                          for a, b in zip(actual, values)):
                    raise ValueError('retained independent quantiles differ')
        return {'status': 'both full64 replay receipts independently reconciled',
                'sources_per_pass': 64, 'native_rows': native_rows,
                'worker_resources': [r['worker_resources'] for r in reports],
                'scope': 'retained replay evidence; no anchor adoption or trained scientific result'}
    except (KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        raise ValueError('missing or malformed full replay evidence') from error
