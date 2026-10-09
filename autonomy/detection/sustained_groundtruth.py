"""Full native four-class GT; training ROI eligibility is reported separately."""
import math
from geometry.oriented_box import wrap_heading

def groundtruth_records(rows,context,timestamp):
 if not isinstance(context,str) or not context or type(timestamp) is not int or timestamp<0:raise ValueError('native context/time required')
 records=[];eligible=[];seen=set()
 for row in rows:
  identifier=row['object_id'];category=row['type'];box=row['box'];points=row['num_lidar_points_in_box'];difficulty=row['detection_difficulty']
  if not isinstance(identifier,str) or not identifier or identifier in seen or type(category) is not int or category not in (1,2,3,4):raise ValueError('unique native object identity/category required')
  if type(points) is not int or points<0 or difficulty is not None and (type(difficulty) is not int or difficulty not in (0,1,2)):raise ValueError('native point count/difficulty invalid')
  if not isinstance(box,(list,tuple)) or len(box)!=7 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in box) or any(x<=0 for x in box[3:6]):raise ValueError('finite positive native LWH geometry required')
  seen.add(identifier);native_box=list(box);native_box[6]=float(wrap_heading(native_box[6]))
  records.append({'context_name':context,'frame_timestamp_micros':timestamp,'object_id':identifier,'type':category,'box':native_box,'score':1.,'overlap_with_nlz':False,'num_lidar_points_in_box':points,'difficulty':difficulty})
  if points>0 and -64<=box[0]<64 and -64<=box[1]<64 and -4<=box[2]<6:eligible.append(identifier)
 return records,eligible
