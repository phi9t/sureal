"""Frozen official SAM native-image engineering probe; oracle prompts explicit."""
import hashlib,importlib.util,json,time
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from segment_anything import SamPredictor,sam_model_registry
assert importlib.util.find_spec('tensorflow') is None and torch.cuda.device_count()==1
d=json.loads(Path('/mnt/trusted.json').read_text());teacher=json.loads(Path('/mnt/teacher.json').read_text())
assert d['prompt_origin']=='native_camera_box_oracle_engineering_only'
assert hashlib.file_digest(Path('/tmp/sam-checkpoint.pth').open('rb'),'sha256').hexdigest()==teacher['checkpoint_sha256']
assert hashlib.sha256(Path('/mnt/image.png').read_bytes()).hexdigest()==d['png_sha256']
image=np.asarray(Image.open('/mnt/image.png').convert('RGB'));assert list(image.shape[:2])==d['image_size']
torch.manual_seed(17);torch.cuda.manual_seed_all(17);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
started=time.monotonic();model=sam_model_registry['vit_b'](checkpoint='/tmp/sam-checkpoint.pth').cuda().eval();model.requires_grad_(False);predictor=SamPredictor(model);torch.cuda.synchronize();model_load_seconds=time.monotonic()-started
torch.cuda.reset_peak_memory_stats()
with torch.inference_mode():
 started=time.monotonic();predictor.set_image(image,image_format='RGB');torch.cuda.synchronize();image_encode_seconds=time.monotonic()-started
 boxes=torch.tensor([p['xyxy'] for p in d['prompts']],dtype=torch.float32,device='cuda');transformed=predictor.transform.apply_boxes_torch(boxes,image.shape[:2])
 started=time.monotonic();logits,scores,low_res=predictor.predict_torch(point_coords=None,point_labels=None,boxes=transformed,multimask_output=False,return_logits=True);torch.cuda.synchronize();decode_seconds=time.monotonic()-started
 assert logits.shape==(3,1,*image.shape[:2]) and scores.shape==(3,1) and low_res.shape==(3,1,256,256)
 assert all(torch.isfinite(t).all() for t in [logits,scores,low_res]);masks=(logits>model.mask_threshold).cpu().numpy();scores_array=scores.cpu().numpy()
 np.savez_compressed('/outputs/masks.npz',masks=masks,predicted_iou_scores=scores_array,original_boxes=boxes.cpu().numpy(),transformed_boxes=transformed.cpu().numpy(),low_resolution_logits=low_res.cpu().numpy())
 r={'status':'frozen official SAM native-image inference passed','frame':{k:d[k] for k in ['context','timestamp','camera']},'native_image_size':d['image_size'],'prompt_origin':d['prompt_origin'],'prompts':3,'teacher_code_commit':teacher['code_commit'],'teacher_checkpoint_sha256':teacher['checkpoint_sha256'],'teacher_parameters':sum(p.numel() for p in model.parameters()),'model_load_seconds':model_load_seconds,'image_encode_seconds':image_encode_seconds,'batched_decode_seconds':decode_seconds,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'positive_pixels':[int(m.sum()) for m in masks[:,0]],'predicted_iou_scores':scores_array[:,0].tolist(),'seed':17,'optimizer_steps':0,'device':torch.cuda.get_device_name(),'scope':'engineering oracle-box image probe; masks and predicted IoU are teacher outputs, not native labels or calibrated confidence; no predicted-box scientific comparison or point-support claim'}
 Path('/outputs/check.json').write_text(json.dumps(r,indent=2));print('PASS official SAM native image',r)
