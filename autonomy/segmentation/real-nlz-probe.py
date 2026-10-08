"""Real full-cohort NLZ containment on evaluation-only native box replay."""
import json,time,resource
from pathlib import Path
from evidence.source_snapshot import file_sha256
import numpy as np
from segmentation.nlz_overlap import overlaps_nlz

root=Path('/source');records=json.loads(Path('/opt/real-boxes.json').read_text());manifest=json.loads((root/'report.json').read_text())
by_frame={}
for record in records:by_frame.setdefault((record['context_name'],record['frame_timestamp_micros']),[]).append(record)
by_measurement={}
for row in manifest['rows']:by_measurement.setdefault((row['context'],row['timestamp']),[]).append(row)
started=time.monotonic();results=[];positive_points=0
for key,boxes in by_frame.items():
    returns={}
    for row in by_measurement[key]:
        path=root/row['artifact'];assert file_sha256(path)==row['sha256']
        with np.load(path) as data:
            xyz=data['xyz'].copy();nlz=data['nlz'].copy()
        assert len(xyz)==row['points'];returns[(row['laser'],row['return'])]=(xyz,nlz)
        positive_points+=int(np.count_nonzero(nlz==1))
    for box in boxes:
        overlap=overlaps_nlz(box['box'],returns)
        results.append({'context_name':key[0],'frame_timestamp_micros':key[1],'object_id':box['object_id'],'overlap_with_nlz':overlap})
assert len(results)==38363
out=Path('/outputs');(out/'nlz-flags.json').write_text(json.dumps(results)+'\n')
(out/'nlz-report.json').write_text(json.dumps({'objects':len(results),'frames':len(by_frame),'flagged_boxes':sum(r['overlap_with_nlz'] for r in results),'nlz_points':positive_points,'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'method':'all five sensors and both returns; closed upright box containment; evaluation-only annotation flags','motion_policy':'M3 TOP compensated and non-TOP explicitly uncompensated; inherits those reference limitations'},indent=2)+'\n')
print('PASS real NLZ flags',len(results))
