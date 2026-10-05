"""Independent reopening and expected-value checks, separate from producer."""
import json
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from PIL import Image


def main():
    out=Path('/outputs')
    assert np.load(out/'matrix.npy').tolist()==[14,38,62]
    assert pq.read_table(out/'synthetic.parquet').to_pydict()=={'id':[7,11,19],'value':[0.25,0.5,0.75]}
    with Image.open(out/'synthetic.png') as img:
        assert img.size==(3,2)
        assert list(img.getdata())==[(17,29,43)]*6
    obs=json.loads((out/'observed.json').read_text())
    required={'dedicated_interpreter','private_home','readonly_source','host_paths_absent','network_blocked','no_tensorflow','writable_output'}
    assert set(obs['assertions'])==required
    assert obs['executable']=='/usr/local/bin/python'
    for name,version in {'numpy':'2.5.3','pyarrow':'25.0.1','pillow':'12.3.0'}.items():
        assert {k.lower():v for k,v in obs['versions'].items()}[name]==version
    assert Path('/source/sentinel').read_text()=='readonly input\n'
    print('PASS independent numeric, Parquet, image, coverage and version validation')

if __name__=='__main__':main()
