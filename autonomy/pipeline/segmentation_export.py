"""Strict structured TOP point-semantic export through pinned native protobufs.

Only validated structured vectors are accepted; arbitrary compressed blobs are
not passed to the upstream CLI. Each return keeps its own native point order.
"""
import json
from pathlib import Path
import subprocess
import sys
import zlib


def validate_frame(frame):
    context=frame.get('context_name');timestamp=frame.get('frame_timestamp_micros');returns=frame.get('returns')
    if not isinstance(context,str) or not context or type(timestamp) is not int or not 0<=timestamp<2**63:
        raise ValueError('invalid native frame key')
    if not isinstance(returns,list) or len(returns)!=2:
        raise ValueError('exactly two TOP returns required')
    for values in returns:
        if not isinstance(values,list) or len(values)>1000000 or any(type(v) is not int or not 0<=v<=22 for v in values):
            raise ValueError('invalid native LiDAR semantic vector')
    return context,timestamp,returns


def encode(message,proto,text):
    result=subprocess.run(['protoc','--proto_path=/upstream/src','--encode=waymo.open_dataset.'+message,'waymo_open_dataset/'+proto],input=text.encode(),capture_output=True)
    if result.returncode:raise ValueError('native protobuf encoding failed: '+result.stderr.decode())
    return result.stdout


def export_frames(frames):
    validated=[validate_frame(frame) for frame in frames]
    keys=[(context,timestamp) for context,timestamp,_ in validated]
    if len(set(keys))!=len(keys):raise ValueError('duplicate frame key')
    text=[]
    for context,timestamp,returns in validated:
        parts=['frames { context_name: '+json.dumps(context)+' frame_timestamp_micros: '+str(timestamp)+' segmentation_labels { name: TOP ']
        for index,values in enumerate(returns,1):
            matrix='shape { dims: '+str(len(values))+' } '+' '.join('data: '+str(v) for v in values)
            payload=encode('MatrixInt32','dataset.proto',matrix)
            compressed=zlib.compress(payload)
            if zlib.decompress(compressed)!=payload:raise ValueError('compression integrity failure')
            escaped=''.join('\\%03o'%b for b in compressed)
            parts.append('ri_return'+str(index)+' { segmentation_label_compressed: "'+escaped+'" } ')
        parts.append('} }');text.append(''.join(parts))
    return encode('SegmentationFrameList','protos/segmentation_metrics.proto','\n'.join(text))

if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text())
    payload=export_frames(data)
    Path(sys.argv[2]).write_bytes(payload)
