import unittest
import numpy as np
from pipeline.semantic_support import semantic_support

class SemanticSupportTests(unittest.TestCase):
    def record(self,ret,labels=None,points=3):
        return {'identity':{'context':'scene','timestamp':10,'laser':1,'return':ret},'return_present':True,'observations':{'xyz':np.zeros((points,3))},'targets':{} if labels is None else {'segmentation':np.asarray(labels,dtype=np.int32).reshape(-1,2)}}

    def test_valid_point_support_preserves_stuff_and_masks_undefined(self):
        rows=[self.record(1,[[-1,14],[8,0],[9,2]]),self.record(2,[[-1,14]],1)]
        r=semantic_support(rows)
        self.assertEqual(r['native_counts'][0],1);self.assertEqual(r['native_counts'][14],2);self.assertEqual(r['native_counts'][2],1)
        self.assertEqual(r['labeled_point_elements'],4);self.assertEqual(r['eligible_point_elements'],3)
        self.assertEqual(r['annotated_frames'],1);self.assertEqual(r['annotated_returns'],2)

    def test_absent_labels_and_empty_labeled_returns_remain_distinct(self):
        r=semantic_support([self.record(1),self.record(2,[],0)])
        self.assertEqual(r['unannotated_returns'],1);self.assertEqual(r['annotated_returns'],1);self.assertEqual(r['empty_annotated_returns'],1)

    def test_duplicate_non_top_invalid_class_and_label_count_rejected(self):
        for mutation in ('duplicate','sensor','class','size'):
            with self.subTest(mutation=mutation):
                row=self.record(1,[[-1,14],[8,0],[9,2]])
                if mutation=='sensor':row['identity']['laser']=2
                elif mutation=='class':row['targets']['segmentation'][0,1]=23
                elif mutation=='size':row['targets']['segmentation']=np.array([[1,2]])
                with self.assertRaises(ValueError):semantic_support([row,row] if mutation=='duplicate' else [row])

if __name__=='__main__':unittest.main()
