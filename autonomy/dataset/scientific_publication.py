"""Scientific publication identity after independent source/archive mirror checks.

Caller must verify the scene receipt and archive-check receipt against their
externally supplied hashes. This contract assembles metadata; it performs no
transfer and is not itself proof that HDFS contains the declared bytes.
"""
import re
from evidence.source_snapshot import require_digest
from dataset.blob_storage import scene_archive_blob_key, source_blob_key

COMPONENTS={'camera_box','camera_calibration','camera_hkp','camera_image','camera_segmentation','camera_to_lidar_box_association','lidar','lidar_box','lidar_calibration','lidar_camera_projection','lidar_camera_synced_box','lidar_hkp','lidar_pose','lidar_segmentation','projected_lidar_box','stats','vehicle_pose'}


def publication_manifest(admitted,scene_receipt,archive,archive_validation,*,mirror_sha256,scene_receipt_sha256,hdfs_root=None,archive_blob=None,store_descriptor=None):
    def require(condition,message):
        if not condition:raise ValueError(message)
    def digest(value):
        try:
            require_digest(value);return True
        except ValueError:
            return False
    scene=admitted['scene'];official=admitted['official_split'];splits=admitted['research_splits']
    require(isinstance(scene,str) and re.fullmatch('[A-Za-z0-9_]+',scene) is not None,'unsafe scene identity')
    legal={'train','development'} if official=='training' else {'validation','camera_validation'} if official=='validation' else set()
    require(isinstance(splits,list) and len(splits)>0 and len(splits)==len(set(splits)) and set(splits)<=legal and not {'train','development'}<=set(splits),'scientific partition conflict')
    if archive_blob is None:
        require(isinstance(hdfs_root,str) and hdfs_root.startswith('hdfs://') and '\n' not in hdfs_root,'invalid publication root')
    else:
        require(hdfs_root is None,'choose blob or HDFS publication target')
        require(isinstance(archive_blob,dict) and archive_blob.get('key')==scene_archive_blob_key(scene),'invalid archive blob key')
        require(archive_blob.get('sha256')==archive['sha256'] and archive_blob.get('bytes')==archive['archive_bytes'],'archive blob identity differs')
        require(archive_blob.get('verified_by_readback') is True,'archive blob readback required')
        require(isinstance(store_descriptor,dict) and store_descriptor.get('kind') in ('waystone','local'),'store descriptor required')
    require(digest(scene_receipt_sha256),'independent scene receipt identity required')
    require(scene_receipt['scene']==scene and scene_receipt['official_split']==official and scene_receipt['research_splits']==splits,'scene receipt membership differs')
    checks=scene_receipt['checks']
    require([c['stage'] for c in checks]==['reconstruct','independent-scene-check'] and all(type(c['exit_code']) is int and c['exit_code']==0 for c in checks),'successful independent scene commands required')
    native=scene_receipt['validation']
    require(native['passed'] is True and native['scene']==scene,'native scene check failed')
    require(set(admitted['components'])==COMPONENTS,'full native source inventory required')
    sources={}
    for component,r in admitted['components'].items():
        require(r['scene']==scene and r['component']==component and r['official_split']==official and r['research_splits']==splits,'source component identity differs')
        require(digest(r['sha256']),'native source digest required')
        if 'blob' in r:
            blob=r['blob']
            require(isinstance(blob,dict) and blob.get('key')==source_blob_key(official,component,scene) and blob.get('sha256')==r['sha256'] and blob.get('verified_by_readback') is True,'native source blob identity differs')
            require(isinstance(r.get('store_descriptor'),dict) and r['store_descriptor'].get('kind') in ('waystone','local'),'native source store descriptor required')
        else:
            require(r['sha256']==r['hdfs_roundtrip_sha256'],'native mirror identity differs')
        metadata=r['source_metadata'];generation=str(metadata['generation'])
        require(re.fullmatch('[1-9][0-9]*',generation) is not None and metadata['storage_url']==f'gs://waymo_open_dataset_v_2_0_1/{official}/{component}/{scene}.parquet#{generation}','source generation URI differs')
        source={'sha256':r['sha256'],'generation':generation,'source_uri':metadata['storage_url']}
        if 'blob' in r:
            source['blob']=dict(r['blob']);source['store_descriptor']=dict(r['store_descriptor'])
        else:
            source['hdfs_uri']=r['hdfs_uri']
        sources[component]=source
    require(scene_receipt['source_sha256']==native['source_lidar_sha256']==sources['lidar']['sha256'],'native LiDAR source differs')
    require(digest(archive['sha256']) and digest(archive['report_sha256']) and archive['report_sha256']==native['report_sha256'],'verified reconstruction manifest differs')
    require(mirror_sha256==archive['sha256']==archive_validation['archive_sha256'],'archive mirror differs')
    require(archive_validation['status']=='all canonical members reconciled to independently verified manifest' and archive_validation['report_sha256']==archive['report_sha256'],'independent archive check differs')
    for name in ('archive_bytes','members'):
        require(type(archive[name]) is int and archive[name]>0 and archive[name]==archive_validation[name],'archive inventory differs')
    require(type(native['records']) is int and native['records']>0 and type(native['points']) is int and native['points']>=0,'invalid native coverage')
    result={'schema_version':1,'role':'scientific','scene':scene,'official_split':official,'research_splits':list(splits),'source_lidar_sha256':sources['lidar']['sha256'],'sources':sources,'archive':dict(archive),'source_reconstruction_receipt_sha256':scene_receipt_sha256,'coverage':{'records':native['records'],'points':native['points']}}
    if archive_blob is None:
        result['archive_hdfs_uri']=hdfs_root.rstrip('/')+'/scientific/'+scene+'/'+archive['sha256']+'.tar'
    else:
        result['archive_blob']=dict(archive_blob);result['store_descriptor']=dict(store_descriptor)
    return result
