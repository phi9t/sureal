"""Synthetic producer and actual isolation probes executed only inside Insula."""
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image


def main():
    port=int(sys.argv[1])
    assert sys.executable=='/usr/local/bin/python'
    assert Path(np.__file__).is_relative_to('/usr/local/lib')
    assert not Path('/data02').exists()
    assert not Path('/root/.config/gcloud').exists()
    assert not Path('/tmp/private-home').exists()
    home=Path(os.environ['HOME']);home.mkdir()
    assert list(home.iterdir())==[]
    try:
        Path('/source/sentinel').write_text('changed')
    except OSError:
        pass
    else:
        raise AssertionError('source writable')
    assert Path('/source/sentinel').read_text()=='readonly input\n'
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=0.5):
            raise AssertionError('host listener reachable')
    except OSError:
        pass
    assert importlib.util.find_spec('tensorflow') is None
    versions={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    assert not any('tensorflow' in name.lower() for name in versions)
    out=Path('/outputs')
    np.save(out/'matrix.npy',np.arange(12,dtype=np.int64).reshape(3,4)@np.arange(4,dtype=np.int64))
    pq.write_table(pa.table({'id':[7,11,19],'value':[0.25,0.5,0.75]}),out/'synthetic.parquet')
    Image.new('RGB',(3,2),(17,29,43)).save(out/'synthetic.png')
    (out/'observed.json').write_text(json.dumps({'versions':versions,'python':sys.version,'executable':sys.executable,
        'assertions':['dedicated_interpreter','private_home','readonly_source','host_paths_absent','network_blocked','no_tensorflow','writable_output']}))
    print('PASS live synthetic producer and isolation checks')

if __name__=='__main__':main()
