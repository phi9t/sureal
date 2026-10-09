import copy,unittest
from dataset.scientific_publication import publication_manifest,COMPONENTS

class ScientificPublicationTests(unittest.TestCase):
    def fixture(self):
        admitted={'scene':'scene','official_split':'training','research_splits':['train'],'components':{c:{'scene':'scene','component':c,'official_split':'training','research_splits':['train'],'sha256':'a'*64,'hdfs_roundtrip_sha256':'a'*64,'hdfs_uri':'hdfs://host/raw/training/'+c+'/scene.parquet','source_metadata':{'generation':'17','storage_url':'gs://waymo_open_dataset_v_2_0_1/training/'+c+'/scene.parquet#17'}} for c in COMPONENTS}}
        archive={'sha256':'b'*64,'report_sha256':'c'*64,'archive_bytes':10240,'members':11}
        validation={'archive_sha256':'b'*64,'report_sha256':'c'*64,'archive_bytes':10240,'members':11,'status':'all canonical members reconciled to independently verified manifest'}
        receipt={'scene':'scene','official_split':'training','research_splits':['train'],'source_sha256':'a'*64,'checks':[{'stage':'reconstruct','exit_code':0},{'stage':'independent-scene-check','exit_code':0}],'validation':{'passed':True,'scene':'scene','report_sha256':'c'*64,'source_lidar_sha256':'a'*64,'records':10,'points':10}}
        return admitted,receipt,archive,validation

    def test_scientific_identity_and_all_source_generations_retained(self):
        a,r,m,v=self.fixture();p=publication_manifest(a,r,m,v,mirror_sha256='b'*64,scene_receipt_sha256='d'*64,hdfs_root='hdfs://host/derived')
        self.assertEqual(p['role'],'scientific');self.assertEqual(p['research_splits'],['train']);self.assertEqual(set(p['sources']),set(COMPONENTS));self.assertEqual(p['archive_hdfs_uri'],'hdfs://host/derived/scientific/scene/'+'b'*64+'.tar')
        a['components']['lidar']['source_metadata']['generation']='99';self.assertEqual(p['sources']['lidar']['generation'],'17')

    def test_publication_manifest_uses_dataset_blob_key(self):
        a,r,m,v=self.fixture()
        key='datasets/scene-records-v1/scene/scientific/archive.tar'
        p=publication_manifest(
            a,r,m,v,
            mirror_sha256='b'*64,
            scene_receipt_sha256='d'*64,
            archive_blob={'key':key,'sha256':'b'*64,'bytes':10240,'verified_by_readback':True},
            store_descriptor={'kind':'waystone','project':'sureal'},
        )
        self.assertEqual(p['archive_blob']['key'],key)
        self.assertEqual(p['store_descriptor'],{'kind':'waystone','project':'sureal'})
        self.assertNotIn('archive_hdfs_uri',p)

    def test_publication_manifest_accepts_blob_source_records(self):
        a,r,m,v=self.fixture()
        for component, record in a['components'].items():
            record.pop('hdfs_uri')
            record.pop('hdfs_roundtrip_sha256')
            record['blob']={'key':f'datasets/waymo-perception-v2.0.1/scene/raw-training-{component}/source.parquet','sha256':record['sha256'],'bytes':100,'verified_by_readback':True}
            record['store_descriptor']={'kind':'waystone','project':'sureal'}
        p=publication_manifest(
            a,r,m,v,
            mirror_sha256='b'*64,
            scene_receipt_sha256='d'*64,
            archive_blob={'key':'datasets/scene-records-v1/scene/scientific/archive.tar','sha256':'b'*64,'bytes':10240,'verified_by_readback':True},
            store_descriptor={'kind':'waystone','project':'sureal'},
        )
        self.assertEqual(p['sources']['lidar']['blob']['key'],'datasets/waymo-perception-v2.0.1/scene/raw-training-lidar/source.parquet')
        self.assertNotIn('hdfs_uri',p['sources']['lidar'])

    def test_cross_identity_failed_checks_or_unverified_mirror_rejected(self):
        for mutation in ('mirror','report','source','partition','failed','missingcomponent','archivecount','nativecheck'):
            with self.subTest(mutation=mutation):
                a,r,m,v=self.fixture();mirror='b'*64
                if mutation=='mirror':mirror='0'*64
                elif mutation=='report':r['validation']['report_sha256']='0'*64
                elif mutation=='source':r['source_sha256']='0'*64
                elif mutation=='partition':a['research_splits']=['train','development']
                elif mutation=='failed':r['checks'][1]['exit_code']=1
                elif mutation=='missingcomponent':a['components'].pop('camera_image')
                elif mutation=='archivecount':v['members']=12
                elif mutation=='nativecheck':r['validation']['passed']=False
                with self.assertRaises(ValueError):publication_manifest(a,r,m,v,mirror_sha256=mirror,scene_receipt_sha256='d'*64,hdfs_root='hdfs://host/derived')

if __name__=='__main__':unittest.main()
