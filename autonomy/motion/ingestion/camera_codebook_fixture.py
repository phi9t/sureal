import csv,json,time,resource,importlib.util
from pathlib import Path
import numpy as np
assert importlib.util.find_spec('tensorflow') is None
start=time.monotonic();book=np.load('/source/codebook.npy',allow_pickle=False);assert book.ndim==2 and book.dtype.kind=='f' and np.isfinite(book).all();rows=list(csv.DictReader(Path('/source/tokens.tsv').open(),delimiter='\t'));keys=np.asarray([[int(r[k]) for k in ['frame','camera','position','token']] for r in rows],dtype=np.int64);assert keys.shape==(22528,4);assert len({tuple(r[:3]) for r in keys})==22528;assert {(int(r[0]),int(r[1])) for r in keys}=={(f,c) for f in range(11) for c in range(1,9)}
for f in range(11):
 for c in range(1,9):assert sorted(keys[(keys[:,0]==f)&(keys[:,1]==c),2])==list(range(256))
def gather(tokens):
 if tokens.dtype.kind not in 'iu' or np.any(tokens<0) or np.any(tokens>=len(book)):raise ValueError('invalid codebook index')
 return book[tokens]
tokens=keys[:,3];features=gather(tokens);reference=np.stack([book[int(t)].copy() for t in tokens]);assert np.array_equal(features,reference);assert np.isfinite(features).all()
for bad in [np.array([-1]),np.array([len(book)]),np.array([.5])]:
 try:gather(bad)
 except ValueError:pass
 else:raise AssertionError('invalid index accepted')
np.save('/outputs/features.npy',features);np.save('/outputs/keys.npy',keys[:,:3]);Path('/outputs/check.json').write_text(json.dumps({'codebook_shape':list(book.shape),'dtype':str(book.dtype),'native_tokens':len(tokens),'minimum_index':int(tokens.min()),'maximum_index':int(tokens.max()),'feature_shape':list(features.shape),'all_indices_in_bounds':True,'literal_row_gather_exact':True,'invalid_indices_refused':3,'native_frame_camera_position_keys_unique':True,'tensorflow_absent':True,'elapsed_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'native historical camera-codebook features only; no RGB reconstruction or forecasting quality'},indent=2));print('VERIFIED CODEBOOK',book.shape,features.shape)
