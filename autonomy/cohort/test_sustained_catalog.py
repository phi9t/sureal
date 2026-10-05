import copy
import unittest
from cohort.sustained_catalog import validate_catalog

class CatalogTests(unittest.TestCase):
    def fixture(self):
        manifest={'frames':[{'identity':'scene:1'},{'identity':'scene:2'}]}
        reports=[{'identity':'scene:1','predictions':1,'native_groundtruth':1}, {'identity':'scene:2','predictions':0,'native_groundtruth':0}]
        row={'context_name':'scene','frame_timestamp_micros':1,'object_id':'a'}
        return manifest,reports,[row.copy()],[row.copy()]

    def test_empty_frames_allowed(self):
        validate_catalog(*self.fixture())

    def test_foreign_frames_refused_for_each_catalog(self):
        for index in (2,3):
            values=list(self.fixture())
            foreign=values[index][0].copy();foreign['context_name']='foreign'
            values[index].append(foreign)
            with self.assertRaises(ValueError):validate_catalog(*values)

    def test_duplicate_ids_refused_even_when_counts_repinned(self):
        for index,key in ((2,'predictions'),(3,'native_groundtruth')):
            values=list(self.fixture());values[index].append(values[index][0].copy());values[1][0][key]=2
            with self.assertRaises(ValueError):validate_catalog(*values)

    def test_counts_and_report_order_and_manifest_uniqueness(self):
        values=list(self.fixture());values[1][0]['native_groundtruth']=2
        with self.assertRaises(ValueError):validate_catalog(*values)
        values=list(self.fixture());values[1].reverse()
        with self.assertRaises(ValueError):validate_catalog(*values)
        values=list(self.fixture());values[0]['frames'][1]['identity']='scene:1'
        with self.assertRaises(ValueError):validate_catalog(*values)
