"""Independently decode native semantic export and compare ordered vectors."""
import ast,json,re,subprocess,zlib
from pathlib import Path

out=Path('/outputs');original=json.loads(Path('/source/real-semantics.json').read_text())
def decode(message,proto,payload):
    result=subprocess.run(['protoc','--proto_path=/upstream/src','--decode=waymo.open_dataset.'+message,'waymo_open_dataset/'+proto],input=payload,capture_output=True)
    assert result.returncode==0,result.stderr
    return result.stdout.decode()

wire=decode('SegmentationFrameList','protos/segmentation_metrics.proto',(out/'real-semantics.bin').read_bytes())
contexts=re.findall(r'context_name: "([^"\n]+)"',wire)
timestamps=[int(v) for v in re.findall(r'frame_timestamp_micros: (\d+)',wire)]
assert contexts==[f['context_name'] for f in original]
assert timestamps==[f['frame_timestamp_micros'] for f in original]
payloads=re.findall(r'segmentation_label_compressed: "((?:\\.|[^"\\])*)"',wire)
assert len(payloads)==120
points=0
for escaped,values in zip(payloads,[r for frame in original for r in frame['returns']]):
    compressed=ast.literal_eval('b"'+escaped+'"')
    decoder=zlib.decompressobj();raw=decoder.decompress(compressed,8*1024*1024)
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
    text=decode('MatrixInt32','dataset.proto',raw)
    actual=[int(v) for v in re.findall(r'^data: (-?\d+)$',text,re.M)]
    dims=[int(v) for v in re.findall(r'dims: (\d+)',text)]
    assert dims==[len(values)] and actual==values
    points+=len(actual)
result=subprocess.run(['/metrics-build/compute_segmentation_metrics','/outputs/real-semantics.bin','/outputs/real-semantics.bin'],capture_output=True,text=True)
(out/'native-self-score.stdout').write_text(result.stdout);(out/'native-self-score.stderr').write_text(result.stderr)
assert result.returncode==0 and not result.stderr and 'miou=1\n' in result.stdout
(out/'wire-validation.json').write_text(json.dumps({'frames':60,'returns':120,'ordered_points':points,'result':'decoded frame identities and semantic vectors match source; native self-score mIoU 1','scope':'evaluation-only label replay, no model inference'},indent=2)+'\n')
print('PASS independent semantic wire decode',points,'points')
