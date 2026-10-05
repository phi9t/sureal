"""Independent reopen of reconstruction points against prepared export vectors."""
import hashlib,json
from pathlib import Path
from evidence.source_snapshot import file_sha256
import numpy as np

root=Path('/source');prepared=Path('/opt')
report=json.loads((root/'report.json').read_text())
frames=json.loads((prepared/'real-semantics.json').read_text())
lookup={(f['context_name'],f['frame_timestamp_micros']):f for f in frames}
assert len(lookup)==len(frames)==60
identities=json.loads((prepared/'real-semantic-identities.json').read_text())
identity_lookup={(r['context'],r['timestamp'],r['return']):r for r in identities['identity_records']}
assert len(identity_lookup)==120
count=0
for row in report['rows']:
    if not (row['laser']==1 and row['segmentation_present']):continue
    path=root/row['artifact'];assert file_sha256(path)==row['sha256']
    key=(row['context'],row['timestamp']);index=row['return']-1
    with np.load(path) as points:
        expected=points['segmentation'][:,1]
        actual=np.asarray(lookup[key]['returns'][index],dtype=np.int64)
        assert np.array_equal(expected,actual)
        record=identity_lookup[(*key,row['return'])]
        assert record['points']==len(expected)==len(points['pixels'])
        assert record['pixels_sha256']==hashlib.sha256(points['pixels'].tobytes()).hexdigest()
        assert record['semantic_sha256']==hashlib.sha256(actual.tobytes()).hexdigest()
        count+=len(expected)
assert count==9726038
Path('/outputs/source-validation.json').write_text(json.dumps({'frames':60,'return_records':120,'points':count,'status':'independent reconstruction-source identity checks passed'},indent=2)+'\n')
print('PASS independent source identities',count)
