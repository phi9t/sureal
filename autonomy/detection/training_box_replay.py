"""Production full64 replay. Queue exclusion precedes all acquisition."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys

from insula.launch_plan import build_plan, load_runtime_lock, record_plan, render_plan
from insula.runtime_roots import default_lock
from insula.staging_lease import staging_lease
from dataset.staged_source import staged_source, WAYSTONE
from evidence.source_snapshot import file_sha256, require_regular_file
from .training_box_process import run_source_worker


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def retained_raw_bytes(cache, code_root):
    slice_root = Path(cache) / 'slices/validation-two-scenes-20260929'
    dataset = json.loads((Path(code_root) / 'dataset/dataset.lock.json').read_text())
    for source in dataset['objects']:
        path = slice_root / source['relative_path']
        if require_regular_file(path).stat().st_size != source['size_bytes']:
            raise ValueError('retained engineering raw source size differs')
    total = 0
    for path in (slice_root / 'raw').rglob('*'):
        if path.is_symlink():
            raise ValueError('unaccountable retained raw symlink')
        if path.is_file():
            require_regular_file(path)
            total += path.stat().st_size
    return total


def load_pinned_runtime(root, expected_lock):
    runtime = load_runtime_lock(Path(root), default_lock(root))
    if runtime.data != expected_lock:
        raise ValueError('production runtime lock changed')
    return runtime


def worker_launch_plan(runtime, *, code_root, source_audit, replay_inputs, output,
                       worker_job, worker_job_sha256, mode):
    return build_plan(
        runtime,
        code=code_root,
        output=output,
        named_inputs={
            '/tmp/source-audit': source_audit,
            '/tmp/replay-inputs': replay_inputs,
        },
        command=[
            'python', '-m', 'detection.training_box_job',
            '--job', worker_job,
            '--expected-job-sha256', worker_job_sha256,
            '--mode', mode,
            '--output', '/outputs/report.json',
        ],
    )


def measured_worker_command(plan, *, code_root, phase):
    return [sys.executable, str(Path(code_root) / 'detection/training_box_resources.py'),
            str(Path(phase) / 'resources.json'), *render_plan(plan)]


def replay(*, cache, output, code_root, expected_candidate_sha256):
    cache, output, code_root = map(Path, (cache, output, code_root))
    with staging_lease(cache / 'scientific-processing/cohort-queue.lock'):
        candidate_path = code_root / 'research/training-box-replay-execution.candidate.json'
        if file_sha256(candidate_path) != expected_candidate_sha256:
            raise ValueError('externally pinned execution candidate changed')
        candidate = json.loads(candidate_path.read_text())
        job_path = code_root / 'research/training-box-producer-job.candidate.json'
        if file_sha256(job_path) != candidate['job_sha256']:
            raise ValueError('production job identity changed')
        job = json.loads(job_path.read_text())
        root = cache / 'insula' / Path(candidate.get('runtime_root', 'rootfs-v2')).name
        runtime = load_pinned_runtime(root, candidate['runtime_lock'])
        lock = runtime.data
        audit = cache / 'scientific-source-audit'
        def revalidate():
            for key in ('acquisition', 'cohort'):
                path = code_root / Path(job[key]['path']).name
                if file_sha256(path) != job[key]['sha256']:
                    raise ValueError('production manifest changed')
            for scene, pins in job['source_receipt_hashes'].items():
                for component, digest in pins.items():
                    if file_sha256(audit / f'training-{component}-{scene}.json') != digest:
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
        code_hashes = {str(p.relative_to(code_root)): file_sha256(p)
                       for p in (code_root / 'detection').glob('*.py')}
        phases = []
        for role in ('producer', 'reference'):
            phase = output / role; phase.mkdir()
            report = phase / 'report.json'
            if role == 'producer':
                worker_job = '/experiment/research/' + job_path.name
                worker_job_sha = file_sha256(job_path)
            else:
                producer_report = output / 'producer/report.json'
                shutil.copyfile(producer_report, inputs / 'producer.json')
                reference_job = dict(job, reported={'path': '/tmp/replay-inputs/producer.json',
                                                    'sha256': file_sha256(producer_report)})
                save(inputs / 'reference.json', reference_job)
                worker_job = '/tmp/replay-inputs/reference.json'
                worker_job_sha = file_sha256(inputs / 'reference.json')
            # Fresh metadata admission occurs inside each worker before source consumption.
            plan = worker_launch_plan(runtime, code_root=code_root, source_audit=audit,
                                      replay_inputs=inputs, output=phase,
                                      worker_job=worker_job, worker_job_sha256=worker_job_sha,
                                      mode=role)
            command = measured_worker_command(plan, code_root=code_root, phase=phase)
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
            result.update(report_sha256=file_sha256(report), transfers=transfers,
                          worker_resources=worker_resources,
                          launch_plan=record_plan(plan),
                          resources=json.loads((phase / 'resources.json').read_text()))
            save(phase / 'receipt.json', result)
            phases.append(result)
        revalidate()
        if file_sha256(candidate_path) != expected_candidate_sha256:
            raise ValueError('execution candidate changed during replay')
        if code_hashes != {str(p.relative_to(code_root)): file_sha256(p)
                           for p in (code_root / 'detection').glob('*.py')}:
            raise ValueError('worker code changed during replay')
        save(output / 'receipt.json', dict(status='both full64 payload passes completed; independent receipt audit required',
                                          runtime_lock=lock, job_sha256=candidate['job_sha256'],
                                          candidate_sha256=file_sha256(candidate_path), code_hashes=code_hashes, phases=phases))


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
