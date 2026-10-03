"""Bind a bounded legacy replay to its unchanged native receipt.

The caller must separately validate the original NativeBackend stage and
checkpoint admission, then freeze this binding under its continuation identity.
This module alone grants neither native nor runner admission.
"""
from pathlib import Path
import re
from continuation.legacy_values import read_json, require_exact, compare_stage, CONTRACTS
from resources.sources import regular, sha
from resources.stage import validate_proof, require_separate


def read_reference(reference):
    if type(reference) is not dict or set(reference) != {'path', 'sha256'}:
        raise ValueError('exact external evidence reference required')
    path = Path(reference['path'])
    if not path.is_absolute() or not regular(path) or sha(path) != reference['sha256']:
        raise ValueError('unchanged absolute regular evidence reference required')
    return path, read_json(path)


def validate_execution(native_reference, replay_reference, *, current_sources,
                       source_pins, cap_bytes, timeout):
    """Actual original argv may change only its single native output binding."""
    native_path, native = read_reference(native_reference)
    _, replay = read_reference(replay_reference)
    _, proof = read_reference(replay['proof'])
    name = native['requested_stage']
    if (not isinstance(name, str) or re.fullmatch(r'(train|audit|literal-loss|export|proposals|score|metrics-audit)-(0|1000)', name) is None
            or native['stage'] != name or native_path.name != name + '-verified.json'
            or replay['requested_stage'] != name or replay['native_parent'] != native_reference):
        raise ValueError('same explicit legacy stage and immutable native parent required')
    original = Path(native['output_directory']); fresh = Path(proof['native_output_directory'])
    require_separate(original, fresh)
    command = native['command'].copy()
    if command.count('/outputs') != 1 or command[command.index('/outputs') - 1] != str(original):
        raise ValueError('one actual original output mount required')
    command[command.index('/outputs') - 1] = str(fresh)
    require_exact(command, proof['original_command'], 'original native argv with fresh outputs')
    require_exact(replay['actual_command'], proof['command'], 'actual bounded argv')
    admission = validate_proof(proof, replay['actual_command'], current_sources,
                               source_pins, fresh, cap_bytes, timeout)
    require_exact(admission, replay['resource_admission'], 'actual measured admission')
    artifacts = replay['output_artifacts']
    paths = {str(path): sha(path) for path in fresh.rglob('*') if path.is_file() and regular(path)}
    if any(path.is_symlink() for path in fresh.rglob('*')) or not paths or paths != artifacts:
        raise ValueError('complete unchanged regular replay artifact inventory required')
    if artifacts.get(str(fresh / 'live.log')) != proof['artifacts']['execution_log']['sha256']:
        raise ValueError('replay log must match bounded execution')
    # Recheck immutable references after opening the complete raw artifact set.
    read_reference(native_reference); read_reference(replay_reference); read_reference(replay['proof'])
    return native, replay, proof


def validate_cpu(native_reference, replay_reference, **kwargs):
    native, replay, proof = validate_execution(native_reference, replay_reference, **kwargs)
    stage = native['stage'].rsplit('-', 1)[0]
    if stage not in CONTRACTS:
        raise ValueError('producer and GPU audits require their independent state/head gates')
    compare_stage(stage, native['output_directory'], proof['native_output_directory'])
    return {'native_receipt': native_reference, 'replay_evidence': replay_reference,
            'resource_proof': replay['proof'], 'requested_stage': native['requested_stage'],
            'all_nonmeasurement_values_and_native_payloads_exact': True,
            'scope': 'bounded legacy CPU replay binding; full native, continuation-source and runner admission remain separate'}
