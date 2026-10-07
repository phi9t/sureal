import numpy as np
from detection.scored_proposals_v2 import decode_scored_proposals
from detection.detector_decode import decode_proposals
anchors=np.array([[0,0,0,2,2,2,0],[10,0,0,2,2,2,0],[20,0,0,2,2,2,0]],float)
logits=np.array([[5,-5,-5,-5],[-100,-100,-100,-100],[4,-5,-5,-5]],float);boxes=np.zeros((3,7));directions=np.array([[3,-3]]*3,float)
args={'iou_threshold':.5,'score_floor':.05,'pre_limit':4096,'post_limit':500}
reference=decode_proposals(logits,boxes,directions,anchors,**args)
for key,value in reference.items():
 result=decode_scored_proposals(logits,boxes,directions,anchors,**args)
 if isinstance(value,np.ndarray):np.testing.assert_array_equal(value,result[key])
boxes[1,3:6]=1000
result=decode_scored_proposals(logits,boxes,directions,anchors,**args)
for key in ['boxes','classes','scores','anchor_indices']:np.testing.assert_array_equal(reference[key],result[key])
assert result['anchor_indices'].tolist()==[0,2]
boxes[0,3]=1000
try:decode_scored_proposals(logits,boxes,directions,anchors,**args)
except ValueError:pass
else:raise AssertionError('selected invalid geometry accepted')
print('PASS scored decoder: unused finite residual extremes ignored; selected invalid geometry refused; ordinary proposals unchanged')
