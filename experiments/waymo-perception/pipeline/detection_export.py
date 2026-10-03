"""Validated native upright-3D export; annotation metadata is evaluation-only."""
import json,math
from pathlib import Path
import sys
from .segmentation_export import encode


def validate_object(record):
    for key in ['context_name','object_id']:
        if not isinstance(record.get(key),str) or not record[key]:raise ValueError('native identity required')
    timestamp=record.get('frame_timestamp_micros')
    if type(timestamp) is not int or not 0<=timestamp<2**63:raise ValueError('timestamp')
    category=record.get('type')
    if type(category) is not int or category not in [1,2,3,4]:raise ValueError('box class namespace')
    box=record.get('box')
    if not isinstance(box,list) or len(box)!=7 or any(type(v) not in [int,float] or not math.isfinite(v) for v in box):raise ValueError('finite upright box required')
    if any(v<=0 for v in box[3:6]) or not -math.pi<=box[6]<math.pi:raise ValueError('box dimensions or heading convention')
    score=record.get('score')
    if type(score) not in [int,float] or not math.isfinite(score) or not 0<=score<=1:raise ValueError('confidence score')
    if type(record.get('overlap_with_nlz')) is not bool:raise ValueError('explicit NLZ overlap required')
    points=record.get('num_lidar_points_in_box')
    if type(points) is not int or not 0<=points<2**31:raise ValueError('evaluation point count')
    difficulty=record.get('difficulty')
    if difficulty is not None and (type(difficulty) is not int or difficulty not in [0,1,2]):raise ValueError('difficulty')
    return record


def export_objects(records):
    validated=[validate_object(record) for record in records];keys=[(r['context_name'],r['frame_timestamp_micros'],r['object_id']) for r in validated]
    if len(set(keys))!=len(keys):raise ValueError('duplicate native object identity')
    text=[]
    for r in validated:
        box=' '.join(name+': '+str(value) for name,value in zip(['center_x','center_y','center_z','length','width','height','heading'],r['box']))
        difficulty='' if r.get('difficulty') is None else 'detection_difficulty_level: '+str(r['difficulty'])
        text.append('objects { context_name: '+json.dumps(r['context_name'])+' frame_timestamp_micros: '+str(r['frame_timestamp_micros'])+' score: '+str(r['score'])+' overlap_with_nlz: '+str(r['overlap_with_nlz']).lower()+' object { id: '+json.dumps(r['object_id'])+' type: '+str(r['type'])+' num_lidar_points_in_box: '+str(r['num_lidar_points_in_box'])+' '+difficulty+' box { '+box+' } } }')
    return encode('Objects','protos/metrics.proto','\n'.join(text))

if __name__=='__main__':
    records=json.loads(Path(sys.argv[1]).read_text());payload=export_objects(records);Path(sys.argv[2]).write_bytes(payload)
