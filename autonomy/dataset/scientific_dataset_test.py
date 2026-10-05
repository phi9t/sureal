import hashlib,json
from pathlib import Path
import tempfile,unittest
import numpy as np
from dataset.scene_archive import create_scene_archive
from dataset.scientific_dataset import iter_scene_records

class ScientificDatasetTests(unittest.TestCase):
    def fixture(self,root,*,missing=False,bad_shape=False,projection_float=False,projection_fraction=False,instance_id=999,semantic_id=2):
        points=root/'points';points.mkdir();rows=[]
        for laser in range(1,6):
            for ret in (1,2):
                absent=missing and laser==1 and ret==2;name=None if absent else f'scene-10-{laser}-{ret}.npz'
                r={'context':'scene','timestamp':10,'laser':laser,'return':ret,'return_present':not absent,'motion':'compensated' if laser==1 else 'uncompensated','segmentation_present':laser==1 and not absent,'points':0 if absent else 1,'artifact':name,'sha256':None}
                if not absent:
                    arrays={'xyz':np.array([[1.,2.,3.]]),'pixels':np.array([[0,0]],dtype=np.int64),'physical_features':np.array([[4.,5.,6.]]),'nlz':np.array([-1.]),'camera_projection':np.zeros((1,6),dtype=np.int32)}
                    if projection_float:arrays['camera_projection']=arrays['camera_projection'].astype(np.float32)
                    if projection_fraction:arrays['camera_projection'][0,1]=0.5
                    if laser==1:arrays['segmentation']=np.array([[instance_id,semantic_id]],dtype=np.int32)
                    if bad_shape and laser==1 and ret==1:arrays['physical_features']=np.zeros((1,4))
                    np.savez(points/name,**arrays);r['sha256']=hashlib.sha256((points/name).read_bytes()).hexdigest()
                rows.append(r)
        report={'schema_version':1,'scene':'scene','rows':rows,'points':sum(r['points'] for r in rows),'source_lidar_sha256':'a'*64};(points/'report.json').write_text(json.dumps(report));digest=hashlib.sha256((points/'report.json').read_bytes()).hexdigest()
        archive=root/'scene.tar';meta=create_scene_archive(points,archive,expected_report_sha256=digest,sidecar_bytes=0,budget_bytes=10**7)
        publication={'schema_version':1,'role':'engineering-only','scene':'scene','archive':meta,'source_lidar_sha256':'a'*64};pub=root/'publication.json';pub.write_text(json.dumps(publication));return archive,pub,hashlib.sha256(pub.read_bytes()).hexdigest()

    def test_exact_observations_and_separate_supervision(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive,pub,digest=self.fixture(Path(tmp));records=list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
            self.assertEqual(len(records),10)
            for r in records:
                self.assertEqual(set(r['observations']),{'xyz','physical_features'})
                self.assertEqual(set(r['evaluation']),{'nlz'})
                self.assertEqual(set(r['correspondence']),{'camera_projection'})
                np.testing.assert_array_equal(r['observations']['physical_features'],[[4,5,6]])
                np.testing.assert_array_equal(r['identity']['pixels'],[[0,0]])
                self.assertEqual('segmentation' in r['targets'],r['identity']['laser']==1)

    def test_engineering_leakage_and_changed_publication_or_archive_rejected(self):
        for mutation in ('train','validation','publication','archive'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                archive,pub,digest=self.fixture(Path(tmp))
                if mutation=='publication':pub.write_text('{}')
                if mutation=='archive':archive.write_bytes(b'corrupt')
                with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage=mutation if mutation in ('train','validation') else 'engineering'))

    def test_scientific_whole_scene_partitions_and_cross_usage_rejection(self):
        for official,splits in [('training',['train']),('training',['development']),('validation',['validation']),('validation',['camera_validation']),('validation',['validation','camera_validation'])]:
            with self.subTest(official=official,splits=splits),tempfile.TemporaryDirectory() as tmp:
                archive,pub,_=self.fixture(Path(tmp));m=json.loads(pub.read_text());m.update(role='scientific',official_split=official,research_splits=splits);pub.write_text(json.dumps(m));digest=hashlib.sha256(pub.read_bytes()).hexdigest()
                for usage in splits:self.assertEqual(len(list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage=usage))),10)
                for usage in {'train','development','validation','camera_validation','engineering'}-set(splits):
                    with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage=usage))

    def test_malformed_or_duplicate_scientific_partition_rejected(self):
        for official,splits,usage in [('training',['train','train'],'train'),('training',['train','development'],'train'),('validation',['train'],'train'),('training','train','train'),('training',[],'train'),('unknown',['train'],'train')]:
            with self.subTest(official=official,splits=splits),tempfile.TemporaryDirectory() as tmp:
                archive,pub,_=self.fixture(Path(tmp));m=json.loads(pub.read_text());m.update(role='scientific',official_split=official,research_splits=splits);pub.write_text(json.dumps(m));digest=hashlib.sha256(pub.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage=usage))

    def test_missing_return_bad_payload_and_resident_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive,pub,digest=self.fixture(Path(tmp),missing=True);records=list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
            absent=[r for r in records if not r['return_present']];self.assertEqual(len(absent),1);self.assertEqual(absent[0]['observations'],{})
            with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering',max_record_bytes=1))
        with tempfile.TemporaryDirectory() as tmp:
            archive,pub,digest=self.fixture(Path(tmp),bad_shape=True)
            with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))

    def test_native_float_projection_storage_preserved_but_fractional_values_rejected(self):
        for fractional in (False,True):
            with self.subTest(fractional=fractional),tempfile.TemporaryDirectory() as tmp:
                archive,pub,digest=self.fixture(Path(tmp),projection_float=True,projection_fraction=fractional)
                if fractional:
                    with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
                else:
                    rows=list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
                    self.assertTrue(all(r['correspondence']['camera_projection'].dtype==np.float32 for r in rows))

    def test_native_unassigned_instance_preserves_valid_stuff_semantics(self):
        for instance in (-1,-2):
            with self.subTest(instance=instance),tempfile.TemporaryDirectory() as tmp:
                archive,pub,digest=self.fixture(Path(tmp),instance_id=instance,semantic_id=14)
                if instance==-2:
                    with self.assertRaises(ValueError):list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
                else:
                    rows=list(iter_scene_records(archive,pub,expected_publication_sha256=digest,usage='engineering'))
                    for r in rows:
                        if 'segmentation' in r['targets']:np.testing.assert_array_equal(r['targets']['segmentation'],[[-1,14]])

if __name__=='__main__':unittest.main()
