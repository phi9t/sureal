"""Reopen numerical artifacts and independently derive analytic expectations."""
import json
from pathlib import Path
import sys
import numpy as np


def validate(path):
    report=json.loads(Path(path).read_text());a=report['analytic']
    x=np.asarray(a['x']);w=np.asarray(a['weights']);y=np.asarray(a['y'])
    assert np.array_equal(x,[[1,2],[3,4]]) and np.array_equal(w,[[2,0],[0,3]])
    assert np.array_equal(y,np.einsum('ik,kj->ij',x,w))
    assert np.array_equal(a['input_gradient'],2*y@w.T)
    assert np.array_equal(a['weight_gradient'],2*x.T@y)
    assert report['peak_allocated_bytes']>0 and report['elapsed_seconds']>0
    assert not any('tensorflow' in p.lower() for p in report['packages'])
    return {'status':'numerical artifacts independently verified','device':report['device']}

if __name__=='__main__':
    result=validate(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
