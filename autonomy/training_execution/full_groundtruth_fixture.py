"""Live original16 native GT export, with independent direct row comparison.

Deliberate independent checker: atan2 periodic heading comparison stays separate from producer oriented-box wrap.
"""
import json,math,resource,time
from pathlib import Path
from detection.sustained_groundtruth import groundtruth_records
from evidence.source_snapshot import file_sha256

sha=file_sha256

def main():
 started=time.monotonic();manifest=json.loads(Path('/source/manifest.json').read_text());all_records=[];rows=[];totals={str(c):{'native':0,'positive_points':0,'training_roi':0} for c in range(1,5)}
 if len(manifest['frames'])!=16 or len({f['identity'] for f in manifest['frames']})!=16:raise ValueError('exact unique16 frames required')
 for f in manifest['frames']:
  context,timestamp=f['identity'].split(':');timestamp=int(timestamp);path=Path('/tmp/boxes')/context/'producer/targets.json'
  if sha(path)!=f['boxes_sha256']:raise ValueError('native labels changed')
  blob=json.loads(path.read_text());matching=[item for item in blob['frames'] if item.get('timestamp_micros',item['rows'][0]['frame_timestamp_micros'] if item['rows'] else None)==timestamp]
  if len(matching)!=1:raise ValueError('unique native label frame required')
  native=matching[0]['rows'];records,eligible=groundtruth_records(native,context,timestamp)
  # Separate reference uses direct source fields/atan2, not producer filters.
  if len(records)!=len(native) or {r['object_id'] for r in records}!={r['object_id'] for r in native}:raise ValueError('native GT was dropped')
  for original,record in zip(native,records):
   if original['object_id']!=record['object_id'] or original['type']!=record['type'] or original['box'][:6]!=record['box'][:6] or original['num_lidar_points_in_box']!=record['num_lidar_points_in_box'] or original['detection_difficulty']!=record['difficulty']:raise ValueError('native GT fields changed')
   difference=record['box'][6]-math.atan2(math.sin(original['box'][6]),math.cos(original['box'][6]))
   if abs(math.atan2(math.sin(difference),math.cos(difference)))>1e-12:raise ValueError('GT periodic heading changed')
   t=totals[str(record['type'])];t['native']+=1;t['positive_points']+=int(original['num_lidar_points_in_box']>0);t['training_roi']+=int(record['object_id'] in eligible)
  relative=Path(f['relative_directory'])
  if relative.is_absolute() or '..' in relative.parts:raise ValueError('safe native frame path required')
  report_path=Path('/tmp/native')/relative/'report.json'
  if sha(report_path)!=f['sha256']['report.json']:raise ValueError('native target report changed')
  report=json.loads(report_path.read_text())
  if sorted(eligible)!=sorted(report['eligible_object_ids']):raise ValueError('historical training eligibility differs')
  rows.append({'identity':f['identity'],'native_groundtruth':len(records),'training_eligible':len(eligible),'zero_point_boxes':sum(x['num_lidar_points_in_box']==0 for x in native),'outside_training_roi_positive_boxes':sum(x['num_lidar_points_in_box']>0 for x in native)-len(eligible)});all_records.extend(records)
 out=Path('/outputs');(out/'groundtruth.json').write_text(json.dumps(all_records,indent=2)+'\n');(out/'check.json').write_text(json.dumps({'frames':rows,'totals_by_class':totals,'native_groundtruth':len(all_records),'training_eligible':sum(t['training_roi'] for t in totals.values()),'elapsed_seconds':time.monotonic()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scope':'original16 full native four-class GT and independent direct-field/periodic-heading audit; ROI is training annotation only, no native scores or fit acceptance'},indent=2)+'\n');print('PASS full native16 GT',len(all_records),flush=True)
if __name__=='__main__':main()
