"""CPU-only model/source inventory; no forward, optimizer or buffer intervention."""
import gc
import hashlib
import importlib.util
import inspect
import json
import resource
import time
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from tier1.catalog import catalog
from tier1.models import build


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tensor_record(value):
    value = value.detach().cpu().contiguous()
    return {'shape': list(value.shape), 'dtype': str(value.dtype),
            'sha256': hashlib.sha256(value.numpy().tobytes()).hexdigest()}


def main():
    began = time.monotonic()
    assert importlib.util.find_spec('tensorflow') is None
    assert not list(Path('/dev').glob('nvidia*')) and not Path('/dev/dri').exists()
    assert not torch.cuda.is_available()
    torch.set_num_threads(1)
    inputs = json.loads(Path('/source/inputs.json').read_text())
    for name, digest in inputs['source_snapshot_sha256'].items():
        assert sha(Path('/experiment') / name) == digest, name
    fresh = {}
    for case_name in ['baseline', 'residual_bev', 'class_balanced_focal',
                      'foreground_prior', 'full_bn', 'point_ln', 'no_norm']:
        torch.manual_seed(17)
        model = build(catalog()[case_name])
        assert all(p.device.type == 'cpu' for p in model.parameters())
        parameter_hashes = {k: tensor_record(v) for k, v in model.named_parameters()}
        buffers = {k: tensor_record(v) for k, v in model.named_buffers()}
        initial_modes = {k: v.training for k, v in model.named_modules()}
        model.eval()
        assert all(not v.training for v in model.modules())
        assert buffers == {k: tensor_record(v) for k, v in model.named_buffers()}
        assert parameter_hashes == {k: tensor_record(v) for k, v in model.named_parameters()}
        modules = []
        for name, module in model.named_modules():
            if isinstance(module, (nn.BatchNorm1d, nn.BatchNorm2d, nn.GroupNorm, nn.LayerNorm)):
                row = {'name': name, 'type': type(module).__name__, 'eps': module.eps,
                       'training_before_eval': initial_modes[name], 'training_after_eval': module.training,
                       'parameters': {k: list(v.shape) for k, v in module.named_parameters(recurse=False)},
                       'buffers': {k: tensor_record(v) for k, v in module.named_buffers(recurse=False)}}
                for attr in ['num_features', 'num_channels', 'num_groups', 'normalized_shape',
                             'momentum', 'affine', 'elementwise_affine', 'track_running_stats']:
                    if hasattr(module, attr):
                        row[attr] = getattr(module, attr)
                modules.append(row)
        fresh[case_name] = {'kind': 'fresh_random_source_model_no_trained_weights',
                            'parameters': sum(p.numel() for p in model.parameters()),
                            'counts': dict(Counter(m['type'] for m in modules)), 'modules': modules,
                            'buffer_keys': list(buffers), 'eval_changed_parameters_or_buffers': False,
                            'forward_calls': 0, 'optimizer_calls': 0}
        del model
        gc.collect()
    retained = {}
    for name, record in inputs['historical_checkpoints'].items():
        path = Path(record['container_path'])
        assert sha(path) == record['sha256']
        # Trusted first-party checkpoint bytes; NumPy sampling state requires full decoding.
        # No model/optimizer is restored and no tensor is changed.
        state = torch.load(path, map_location='cpu', weights_only=False)
        tensors = state['model']
        assert state['steps'] == 2000 and state['manifest_sha256'] == record['manifest_sha256']
        assert all(v.device.type == 'cpu' for v in tensors.values())
        norm_buffers = {k: tensor_record(v) for k, v in tensors.items()
                        if k.endswith(('running_mean', 'running_var', 'num_batches_tracked'))}
        assert set(norm_buffers) == {'encoder.norm.running_mean', 'encoder.norm.running_var',
                                     'encoder.norm.num_batches_tracked'}
        for key in ['running_mean', 'running_var']:
            assert tensors['encoder.norm.' + key].shape == (64,)
            assert torch.isfinite(tensors['encoder.norm.' + key]).all()
        assert (tensors['encoder.norm.running_var'] >= 0).all()
        retained[name] = {'kind': 'saved_trained_state_dictionary_read_only_no_model_restore',
                          'checkpoint_sha256': record['sha256'], 'steps': state['steps'],
                          'manifest_sha256': state['manifest_sha256'], 'top_level_keys': list(state),
                          'model_tensor_count': len(tensors), 'bn_buffers': norm_buffers,
                          'bn_counter': int(tensors['encoder.norm.num_batches_tracked']),
                          'bn_mean_range': [float(tensors['encoder.norm.running_mean'].min()),
                                            float(tensors['encoder.norm.running_mean'].max())],
                          'bn_variance_range': [float(tensors['encoder.norm.running_var'].min()),
                                                float(tensors['encoder.norm.running_var'].max())],
                          'optimizer_state_present': 'optimizer' in state,
                          'rng_keys_present': [k for k in state if 'rng' in k],
                          'serialized_module_modes_present': False,
                          'file_bytes_unchanged_after_read': sha(path) == record['sha256']}
        assert retained[name]['file_bytes_unchanged_after_read']
        del state, tensors
        gc.collect()
    torch_sources = {}
    for cls in [nn.BatchNorm1d, nn.BatchNorm2d, nn.GroupNorm, nn.LayerNorm]:
        path = Path(inspect.getfile(cls))
        torch_sources[str(path)] = sha(path)
    result = {'scope': 'fresh CPU source/model module inventory and read-only retained state inspection',
              'torch': torch.__version__, 'cuda_available': False, 'tensorflow_available': False,
              'gpu_devices_present': [], 'source_snapshot_sha256': inputs['source_snapshot_sha256'],
              'fresh_models': fresh, 'retained_state': retained, 'torch_source_sha256': torch_sources,
              'forward_calls': 0, 'optimizer_updates': 0, 'interventions': 0,
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'elapsed_seconds': time.monotonic() - began}
    assert result['peak_rss_kib'] < 2 * 1024**2
    Path('/outputs/inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'result': 'inventory_checked', 'fresh_cases': len(fresh),
                      'retained_checkpoints': len(retained), 'peak_rss_kib': result['peak_rss_kib'],
                      'elapsed_seconds': result['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
