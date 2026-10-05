"""Scientific publication identity after independent source/archive mirror checks.

Caller must verify the scene receipt and archive-check receipt against their
externally supplied hashes. This contract assembles metadata; it performs no
transfer and is not itself proof that HDFS contains the declared bytes.
"""
import re
COMPONENTS={'camera_box','camera_calibration','camera_hkp','camera_image','camera_segmentation','camera_to_lidar_box_association','lidar','lidar_box','lidar_calibration','lidar_camera_projection','lidar_camera_synced_box','lidar_hkp','lidar_pose','lidar_segmentation','projected_lidar_box','stats','vehicle_pose'}


def publication_manifest(admitted,scene_receipt,archive,archive_validation,*,mirror_sha256,scene_receipt_sha256,hdfs_root):
    def require(condition,message):
        if not condition:raise ValueError(message)
    def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    scene=admitted['scene'];official=admitted['official_split'];splits=admitted['research_splits']
    require(isinstance(scene,str) and re.fullmatch('[A-Za-z0-9_]+',scene) is not None,'unsafe scene identity')
    legal={'train','development'} if official=='training' else {'validation','camera_validation'} if official=='validation' else set()
    require(isinstance(splits,list) and len(splits)>0 and len(splits)==len(set(splits)) and set(splits)<=legal and not {'train','development'}<=set(splits),'scientific partition conflict')
    require(isinstance(hdfs_root,str) and hdfs_root.startswith('hdfs://') and '\n' not in hdfs_root,'invalid publication root')
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
        require(digest(r['sha256']) and r['sha256']==r['hdfs_roundtrip_sha256'],'native mirror identity differs')
        metadata=r['source_metadata'];generation=str(metadata['generation'])
        require(re.fullmatch('[1-9][0-9]*',generation) is not None and metadata['storage_url']==f'gs://waymo_open_dataset_v_2_0_1/{official}/{component}/{scene}.parquet#{generation}','source generation URI differs')
        sources[component]={'sha256':r['sha256'],'generation':generation,'source_uri':metadata['storage_url'],'hdfs_uri':r['hdfs_uri']}
    require(scene_receipt['source_sha256']==native['source_lidar_sha256']==sources['lidar']['sha256'],'native LiDAR source differs')
    require(digest(archive['sha256']) and digest(archive['report_sha256']) and archive['report_sha256']==native['report_sha256'],'verified reconstruction manifest differs')
    require(mirror_sha256==archive['sha256']==archive_validation['archive_sha256'],'archive mirror differs')
    require(archive_validation['status']=='all canonical members reconciled to independently verified manifest' and archive_validation['report_sha256']==archive['report_sha256'],'independent archive check differs')
    for name in ('archive_bytes','members'):
        require(type(archive[name]) is int and archive[name]>0 and archive[name]==archive_validation[name],'archive inventory differs')
    require(type(native['records']) is int and native['records']>0 and type(native['points']) is int and native['points']>=0,'invalid native coverage')
    return {'schema_version':1,'role':'scientific','scene':scene,'official_split':official,'research_splits':list(splits),'source_lidar_sha256':sources['lidar']['sha256'],'sources':sources,'archive':dict(archive),'archive_hdfs_uri':hdfs_root.rstrip('/')+'/scientific/'+scene+'/'+archive['sha256']+'.tar','source_reconstruction_receipt_sha256':scene_receipt_sha256,'coverage':{'records':native['records'],'points':native['points']}}
