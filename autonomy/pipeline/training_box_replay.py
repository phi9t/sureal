"""Production full64 replay. Queue exclusion precedes all acquisition."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from insula.runtime_identity import verify_rootfs
from insula.staging_lease import staging_lease
from .staged_source import staged_source, WAYSTONE
from .training_box_process import run_source_worker


def sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def retained_raw_bytes(cache, code_root):
    slice_root = Path(cache) / 'slices/validation-two-scenes-20260929'
    dataset = json.loads((Path(code_root) / 'dataset.lock.json').read_text())
    for source in dataset['objects']:
        path = slice_root / source['relative_path']
        if path.is_symlink() or not path.is_file() or path.stat().st_size != source['size_bytes']:
            raise ValueError('retained engineering raw source size differs')
    total = 0
    for path in (slice_root / 'raw').rglob('*'):
        if path.is_symlink():
            raise ValueError('unaccountable retained raw symlink')
        if path.is_file():
            total += path.stat().st_size
    return total


def replay(*, cache, output, code_root, expected_candidate_sha256):
    cache, output, code_root = map(Path, (cache, output, code_root))
    with staging_lease(cache / 'scientific-processing/cohort-queue.lock'):
        candidate_path = code_root / 'research/training-box-replay-execution.candidate.json'
        if sha(candidate_path) != expected_candidate_sha256:
            raise ValueError('externally pinned execution candidate changed')
        candidate = json.loads(candidate_path.read_text())
        job_path = code_root / 'research/training-box-producer-job.candidate.json'
        if sha(job_path) != candidate['job_sha256']:
            raise ValueError('production job identity changed')
        job = json.loads(job_path.read_text())
        root = cache / 'insula/rootfs-v2'
        lock = json.loads(Path(str(root) + '.lock.json').read_text())
        if lock != candidate['runtime_lock']:
            raise ValueError('production runtime lock changed')
        verify_rootfs(root, lock['rootfs_sha256'])
        audit = cache / 'scientific-source-audit'
        def revalidate():
            for key in ('acquisition', 'cohort'):
                path = code_root / Path(job[key]['path']).name
                if sha(path) != job[key]['sha256']:
                    raise ValueError('production manifest changed')
            for scene, pins in job['source_receipt_hashes'].items():
                for component, digest in pins.items():
                    if sha(audit / f'training-{component}-{scene}.json') != digest:
                        raise ValueError('production receipt changed')
        revalidate()
        retained = retained_raw_bytes(cache, code_root)
        acquisition = json.loads((code_root / Path(job['acquisition']['path']).name).read_text())
        if candidate['raw_limit_bytes'] != acquisition['local_staging_limit_bytes']:
            raise ValueError('execution raw cap differs from acquisition contract')
        if retained + max(s['header']['bytes'] for s in candidate['sources']) > candidate['raw_limit_bytes']:
            raise ValueError('retained raw and one source exceed acquisition cap')
        if [s['scene'] for s in candidate['sources']] != job['scene_order']:
            raise ValueError('execution source selection differs')
        output.mkdir(parents=True, exist_ok=False)
        inputs = output / 'inputs'; inputs.mkdir()
        code_hashes = {str(p.relative_to(code_root)): sha(p)
                       for p in (code_root / 'pipeline').glob('*.py')}
        phases = []
        for role in ('producer', 'reference'):
            phase = output / role; phase.mkdir()
            report = phase / 'report.json'
            if role == 'producer':
                worker_job = '/experiment/research/' + job_path.name
                worker_job_sha = sha(job_path)
            else:
                producer_report = output / 'producer/report.json'
                shutil.copyfile(producer_report, inputs / 'producer.json')
                reference_job = dict(job, reported={'path': '/tmp/replay-inputs/producer.json',
                                                    'sha256': sha(producer_report)})
                save(inputs / 'reference.json', reference_job)
                worker_job = '/tmp/replay-inputs/reference.json'
                worker_job_sha = sha(inputs / 'reference.json')
            base = ['bwrap', '--unshare-all', '--die-with-parent',
                    '--ro-bind', str(root), '/', '--ro-bind', str(code_root), '/experiment',
                    '--bind', str(phase), '/outputs', '--proc', '/proc', '--dev', '/dev',
                    '--tmpfs', '/tmp', '--ro-bind', str(audit), '/tmp/source-audit',
                    '--ro-bind', str(inputs), '/tmp/replay-inputs', '--clearenv',
                    '--setenv', 'HOME', '/tmp/private-home', '--setenv', 'PATH', '/usr/local/bin:/usr/bin:/bin',
                    '--setenv', 'PYTHONNOUSERSITE', '1', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
                    '--setenv', 'PYTHONPATH', '/experiment', '--chdir', '/experiment', '--']
            # Fresh metadata admission occurs inside each worker before source consumption.
            command = [sys.executable, str(code_root / 'pipeline/training_box_resources.py'),
                       str(phase / 'resources.json'), *base, 'python', '-m',
                       'pipeline.training_box_job', '--job', worker_job,
                       '--expected-job-sha256', worker_job_sha, '--mode', role,
                       '--output', '/outputs/report.json']
            transfers = []
            by_scene = {s['scene']: s for s in candidate['sources']}
            @contextmanager
            def stage(header):
                revalidate()
                source = by_scene[header['scene']]
                if source['header'] != header:
                    raise ValueError('execution header differs')
                record = json.loads((audit / f"training-lidar_box-{header['scene']}.json").read_text())
                with staged_source(record, cache, retained_bytes=retained_raw_bytes(cache, code_root),
                                   limit_bytes=candidate['raw_limit_bytes'],
                                   transfer_command=['timeout', '--kill-after=10s', '120s', WAYSTONE]) as (path, evidence):
                    with path.open('rb') as reader:
                        yield reader
                    transfers.append(dict(scene=header['scene'], **evidence))
            result = run_source_worker(command, [s['header'] for s in candidate['sources']], stage=stage,
                                       stderr_path=phase / 'stderr.log', ack_timeout_seconds=120,
                                       write_timeout_seconds=120, exit_timeout_seconds=120)
            if not report.is_file() or len(result['acknowledgements']) != 64 or len(transfers) != 64:
                raise ValueError('incomplete production pass')
            worker_resources = json.loads(report.read_text())['worker_resources']
            if (worker_resources['rss_scope'] != 'worker_process_peak'
                    or worker_resources['peak_rss_kib'] <= 0):
                raise ValueError('worker memory measurement required')
            result.update(report_sha256=sha(report), transfers=transfers,
                          worker_resources=worker_resources,
                          resources=json.loads((phase / 'resources.json').read_text()))
            save(phase / 'receipt.json', result)
            phases.append(result)
        revalidate()
        if sha(candidate_path) != expected_candidate_sha256:
            raise ValueError('execution candidate changed during replay')
        if code_hashes != {str(p.relative_to(code_root)): sha(p)
                           for p in (code_root / 'pipeline').glob('*.py')}:
            raise ValueError('worker code changed during replay')
        save(output / 'receipt.json', dict(status='both full64 payload passes completed; independent receipt audit required',
                                          runtime_lock=lock, job_sha256=candidate['job_sha256'],
                                          candidate_sha256=sha(candidate_path), code_hashes=code_hashes, phases=phases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-candidate-sha256', required=True)
    args = parser.parse_args()
    replay(cache=Path.home()/'.cache/waystone/waymo-perception', output=args.output,
           code_root=Path(__file__).resolve().parents[1],
           expected_candidate_sha256=args.expected_candidate_sha256)


if __name__ == '__main__':
    main()
