import io,json
from pathlib import Path
import torch
from checkpoint_values import same_tensor_values
p=torch.nn.Parameter(torch.tensor([1.],device='cuda'));opt=torch.optim.Adam([p],lr=1e-4,foreach=False);p.square().sum().backward();opt.step();actual=opt.state_dict()['state'][0]['step'];assert actual.device.type=='cpu';buffer=io.BytesIO();torch.save(opt.state_dict(),buffer);buffer.seek(0);loaded=torch.load(buffer,map_location='cuda',weights_only=False)['state'][0]['step'];assert loaded.device.type=='cuda'
assert same_tensor_values(actual,loaded) and not same_tensor_values(actual,loaded+1) and not same_tensor_values(actual,loaded.double()) and not same_tensor_values(actual,loaded[None]);Path('/outputs/check.json').write_text(json.dumps({'CPU_Adam_counter_roundtrip_to_CUDA_exact_values':True,'value_dtype_shape_mismatches_refused':True}));print('PASS live Adam serialization/device regression')
