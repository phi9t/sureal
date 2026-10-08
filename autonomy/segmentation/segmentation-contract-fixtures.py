"""Live native protobuf/compression/segmentation scoring contract fixtures."""
import json
from pathlib import Path
import re
import subprocess
import zlib

PROTO='/upstream/src'
OUT=Path('/outputs')


def encode(message,proto,text):
    result=subprocess.run(['protoc','--proto_path='+PROTO,'--encode=waymo.open_dataset.'+message,'waymo_open_dataset/'+proto],input=text.encode(),capture_output=True)
    assert result.returncode==0,result.stderr
    return result.stdout


def frame(labels):
    # One semantic value per original point; instance IDs are not metric input.
    matrix='shape { dims: '+str(len(labels))+' } '+' '.join('data: '+str(x) for x in labels)
    compressed=zlib.compress(encode('MatrixInt32','dataset.proto',matrix))
    escaped=''.join('\\%03o'%b for b in compressed)
    text='frames { context_name: "fixture" frame_timestamp_micros: 100 segmentation_labels { name: TOP '
    for ret in [1,2]:text+='ri_return'+str(ret)+' { segmentation_label_compressed: "'+escaped+'" } '
    return encode('SegmentationFrameList','protos/segmentation_metrics.proto',text+'} }')


def main():
    classes=list(range(1,23))
    fixtures=[('perfect',classes,classes,1.),('undefined-predictions',[0]*22,classes,0.),
              ('wrong-class',classes[1:]+classes[:1],classes,0.),
              ('ignored-groundtruth',classes+[1],classes+[0],1.),
              ('absent-classes',[1],[1],1.)]
    results=[]
    for name,pred,truth,mean in fixtures:
        predpath=OUT/(name+'-pred.bin');gtpath=OUT/(name+'-gt.bin')
        predpath.write_bytes(frame(pred));gtpath.write_bytes(frame(truth))
        run=subprocess.run(['/metrics-build/compute_segmentation_metrics',str(predpath),str(gtpath)],capture_output=True,text=True)
        (OUT/(name+'.stdout')).write_text(run.stdout);(OUT/(name+'.stderr')).write_text(run.stderr)
        assert run.returncode==0 and not run.stderr,run.stderr
        ious={name:float(value) for name,value in re.findall(r'^(TYPE_[A-Z_]+):([0-9.eE+-]+)$',run.stdout,re.M)}
        match=re.search(r'^miou=([0-9.eE+-]+)$',run.stdout,re.M)
        assert len(ious)==22 and match is not None
        assert abs(float(match[1])-mean)<1e-6,(name,run.stdout)
        assert all(abs(v-mean)<1e-6 for v in ious.values()),(name,ious)
        results.append({'fixture':name,'expected_miou':mean,'observed_miou':float(match[1]),'classes':len(ious),'exit_code':run.returncode})
    (OUT/'fixture-results.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS five native segmentation contract fixtures')

if __name__=='__main__':main()
