"""Training-only target extraction; absence is never inferred to be annotated empty."""
from pipeline.training_box_sources import _native_record
P='[LiDARBoxComponent].'
def select_targets(rows,*,scene,timestamps,expected_rows):
 if type(expected_rows) is not int or expected_rows<0 or not timestamps or len(set(timestamps))!=len(timestamps) or any(type(t) is not int or t<0 for t in timestamps):raise ValueError('explicit unique frame selection required')
 frames={t:[] for t in timestamps};seen=set();count=0
 for row in rows:
  count+=1;r=_native_record(row,scene);key=(r['frame_timestamp_micros'],r['object_id'])
  if key in seen:raise ValueError('duplicate native box key')
  seen.add(key)
  try:points=row[P+'num_lidar_points_in_box'];difficulty=row[P+'difficulty_level.detection']
  except KeyError as error:raise ValueError('native evaluation metadata missing') from error
  if type(points) is not int or points<0 or difficulty is not None and (type(difficulty) is not int or difficulty not in (0,1,2)):raise ValueError('invalid native evaluation metadata')
  r.update(num_lidar_points_in_box=points,detection_difficulty=difficulty)
  if r['frame_timestamp_micros'] in frames:frames[r['frame_timestamp_micros']].append(r)
 if count!=expected_rows:raise ValueError('full native row count differs')
 return {'scene':scene,'native_rows':count,'frames':[{'timestamp_micros':t,'annotation_state':'native_box_rows_present' if frames[t] else 'no_native_box_rows_coverage_unresolved','rows':sorted(frames[t],key=lambda r:r['object_id'])} for t in sorted(frames)],'scope':'native target/evaluation fields only; no observation features; no empty-label coverage inferred'}
