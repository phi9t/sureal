"""Recovery membership is checked against an external exact input inventory."""
import copy,errno,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evidence.source_snapshot import file_sha256 as sha


class ResourceRetentionTests(unittest.TestCase):
    def api(self):
        try:from resources.retention_audit import validate_union
        except ImportError:self.fail('resource publication requires a separate exact-member live recovery union gate')
        return validate_union

    def fixture(self,root):
        raw=root/'raw';raw.mkdir();asset=raw/'input.json';asset.write_text('frozen input');digest=sha(asset);expected={'input.json':{'path':str(asset),'sha256':digest,'bytes':asset.stat().st_size}}
        member={'path':'input.json','sha256':digest,'bytes':asset.stat().st_size};archive='a'*64
        validation={'archive_sha256':archive,'exact_members_and_hashes':True,'members':1,'payload_bytes':member['bytes']}
        checks=[]
        for stage in ['create-live','archive-put','archive-get','manifest-put','manifest-get','verify-live','rehydrate-live']:
            checks.append({'stage':stage,'exit_code':0,**({'validation':{**validation,**({'verified_rehydration':True} if stage=='rehydrate-live' else {})}} if stage.endswith('-live') else {})})
        prefix='hdfs://harunava/user/tiger/waystone/sureal/runs/perception-resource-closures/balanced16-test'
        chunk={'manifest':{'members':[member],'payload_bytes':member['bytes'],'archive_sha256':archive,'archive_bytes':100},'archive_hdfs_uri':prefix+'/'+archive+'/archive.tar.gz','manifest_hdfs_uri':prefix+'/'+archive+'/manifest.json','checks':checks}
        original={'schema_version':1,'kind':'shared','source_inventory':expected,'chunks':[chunk],'hdfs_prefix':prefix};pub={**copy.deepcopy(original),'manifest_readback_exact':True,'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json','publication_manifest_sha256':'b'*64}
        return pub,expected,original,raw

    def test_exact_union_and_missing_recovery_refusal(self):
        validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            pub,expected,original,raw=self.fixture(Path(temp));result=validate(pub,expected,original,raw)
            self.assertTrue(result['whole_member_union_exact']);self.assertEqual(result['files'],1)
            for fault in ['missing_member','changed_digest','duplicate_member','missing_rehydrate','wrong_namespace','readback','changed_input']:
                bad=copy.deepcopy(pub);readback=copy.deepcopy(original)
                if fault=='missing_member':bad['chunks'][0]['manifest']['members']=[]
                elif fault=='changed_digest':bad['chunks'][0]['manifest']['members'][0]['sha256']='0'*64
                elif fault=='duplicate_member':bad['chunks'][0]['manifest']['members']*=2
                elif fault=='missing_rehydrate':bad['chunks'][0]['checks'].pop()
                elif fault=='wrong_namespace':bad['hdfs_prefix']='hdfs://foreign/unknown'
                elif fault=='readback':bad['manifest_readback_exact']=False
                else:(raw/'input.json').write_text('changed input')
                # Corrupt even consistently rewritten candidate/readback copies;
                # the independent expected inventory still must hold.
                if fault not in {'readback','changed_input'}:readback={k:v for k,v in bad.items() if k not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256'}}
                with self.assertRaises(ValueError):validate(bad,expected,readback,raw)

    def test_foreign_root_resource_uris_are_refused_even_with_matching_blob_key_suffix(self):
        validate=self.api()
        with tempfile.TemporaryDirectory() as temp:
            pub,expected,original,raw=self.fixture(Path(temp))
            old_root='hdfs://harunava/user/tiger/waystone/sureal'
            foreign_root='hdfs://other-cluster/x'

            def rewrite(value):
                return value.replace(old_root,foreign_root)

            bad=copy.deepcopy(pub)
            bad['hdfs_prefix']=rewrite(bad['hdfs_prefix'])
            bad['publication_manifest_hdfs_uri']=rewrite(bad['publication_manifest_hdfs_uri'])
            for chunk in bad['chunks']:
                chunk['archive_hdfs_uri']=rewrite(chunk['archive_hdfs_uri'])
                chunk['manifest_hdfs_uri']=rewrite(chunk['manifest_hdfs_uri'])
            readback={k:v for k,v in bad.items() if k not in {'manifest_readback_exact','publication_manifest_hdfs_uri','publication_manifest_sha256'}}

            with self.assertRaises(ValueError):
                validate(bad,expected,readback,raw)

    def test_chunk_partition_is_complete_bounded_and_order_independent(self):
        try:from resources.retention_audit import partition
        except ImportError:self.fail('resource retention needs bounded chunk partitioning before writes')
        values={'b':{'bytes':7},'a':{'bytes':5},'c':{'bytes':4}}
        result=partition(values,10);self.assertEqual(result,[['a'],['b'],['c']]);self.assertEqual(partition(dict(reversed(list(values.items()))),10),result)
        with self.assertRaises(ValueError):partition({'large':{'bytes':11}},10)
        with self.assertRaises(ValueError):partition({},10)

    def test_live_result_is_bound_to_retained_job_and_downloaded_manifest(self):
        try:from resources.retention_audit import validate_archive_snapshot
        except ImportError:self.fail('live recovery admission must bind actual retained jobs, results and downloaded manifests')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pub,expected,original,raw=self.fixture(root);chunk=pub['chunks'][0]
            library=root/'archive.py';library.write_text('pinned archive');pub['archive_library']={'path':str(library),'sha256':sha(library)}
            pub['execution_directory']=str(root/'execution');pub['runtime_lock']={'rootfs_sha256':'r'*64};pub['rootfs_path']=str(root/'rootfs')
            for suffix in ['manifest','readback']:
                path=root/(suffix+'.json');path.write_text(json.dumps(chunk['manifest'],sort_keys=True,indent=2)+'\n')
                chunk[suffix+'_path']=str(path)
            chunk['manifest_sha256']=sha(path)
            inputs=root/'inputs';inputs.mkdir();job={'source_sha256':{'input.json':expected['input.json']['sha256']},'max_bytes':128*1024**2,'archive_module_path':'/tmp/resource-archive.py','archive_module_sha256':pub['archive_library']['sha256'],'manifest_sha256':chunk['manifest_sha256']}
            jobpath=inputs/'job.json';jobpath.write_text(json.dumps(job));out=root/'result';out.mkdir();checkpath=out/'check.json';log=out/'live.log';log.write_text('PASS archive recovery\n')
            check=chunk['checks'][6];checkpath.write_text(json.dumps(check['validation']))
            check.update({'input_directory':str(inputs),'input_hashes':{str(jobpath):sha(jobpath)},'artifacts':{str(p):sha(p) for p in out.iterdir()},'command':['bwrap','--unshare-all','--die-with-parent','--ro-bind',pub['rootfs_path'],'/','--ro-bind',pub['execution_directory'],'/experiment','--ro-bind',str(inputs),'/tmp/inputs','--ro-bind',str(library),'/tmp/resource-archive.py','--','python','/experiment/resources/archive_worker.py','rehydrate']})
            validate_archive_snapshot(pub,chunk,check,'rehydrate')
            for fault in ['result','job','library','mount','manifest','input_inventory']:
                bad=copy.deepcopy(check);candidate=copy.deepcopy(chunk)
                if fault=='result':bad['validation']['payload_bytes']+=1
                elif fault=='job':
                    altered=root/'bad-job';altered.mkdir();changed={**job,'source_sha256':{}};file=altered/'job.json';file.write_text(json.dumps(changed));bad['input_directory']=str(altered);bad['input_hashes']={str(file):sha(file)};bad['command'][bad['command'].index('/tmp/inputs')-1]=str(altered)
                elif fault=='library':bad['command'][bad['command'].index('/tmp/resource-archive.py')-1]=str(root/'foreign.py')
                elif fault=='mount':bad['command'][bad['command'].index('/experiment')-1]=str(root/'foreign')
                elif fault=='manifest':candidate['manifest']['archive_bytes']+=1
                else:bad['input_hashes']={}
                with self.assertRaises(ValueError):validate_archive_snapshot(pub,candidate,bad,'rehydrate')

    def test_cross_filesystem_member_uses_verified_bounded_copy(self):
        try:from resources.retention_audit import stage_member
        except ImportError:self.fail('driver inputs on another filesystem require bounded verified staging')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'driver.so';source.write_bytes(b'driver bytes');entry={'path':str(source),'sha256':sha(source),'bytes':source.stat().st_size};destination=root/'staged.so'
            with patch('resources.retention_audit.os.link',side_effect=OSError(errno.EXDEV,'cross-device')):
                result=stage_member(entry,destination,root,reserve=lambda *_: None);self.assertEqual(destination.read_bytes(),source.read_bytes());self.assertEqual(result['storage'],'copied');self.assertEqual(result['bytes'],len(b'driver bytes'))
            with patch('resources.retention_audit.os.link',side_effect=OSError(errno.EACCES,'not permitted')):
                with self.assertRaises(OSError):stage_member(entry,root/'refused.so',root)
            self.assertFalse((root/'refused.so').exists())
            with patch('resources.retention_audit.os.link',side_effect=OSError(errno.EXDEV,'cross-device')):
                with self.assertRaises(ValueError):stage_member(entry,root/'budget-refused.so',root,reserve=lambda *_: (_ for _ in ()).throw(ValueError('reserve refused')))
            self.assertFalse((root/'budget-refused.so').exists())

    def test_execution_package_uses_admitted_evidence_helper_not_current_tree(self):
        try:from resources.retention_audit import materialize_execution_package
        except ImportError:self.fail('retained execution must materialize helper packages from the admitted source closure')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);code=root/'code';execution=root/'execution';archive=root/'archive.py'
            (code/'resources').mkdir(parents=True);(code/'evidence').mkdir()
            (code/'resources/execute_worker.py').write_text('admitted worker')
            (code/'evidence/source_snapshot.py').write_text('admitted helper')
            archive.write_text('archive helper')
            pins={'source_pins':{str(path.relative_to(code)):sha(path) for path in code.rglob('*.py')}}
            current_helper=root/'current/evidence/source_snapshot.py';current_helper.parent.mkdir(parents=True);current_helper.write_text('changed current helper')
            materialize_execution_package(code,execution,archive,sha(archive),pins)
            self.assertEqual((execution/'evidence/source_snapshot.py').read_text(),'admitted helper')
            self.assertEqual((execution/'resources/execute_worker.py').read_text(),'admitted worker')
            self.assertEqual((execution/'resources/resource_archive.py').read_text(),'archive helper')
            from resources.retention_audit import validate_live_references
            pub={'resource_source_pins':pins,'resource_source_directory':str(root/'current/resources'),
                 'execution_directory':str(execution),'archive_library':{'sha256':sha(archive)},'chunks':[]}
            validate_live_references(pub)
            for name in pins['source_pins']:
                helper=execution/name;original=helper.read_bytes()
                helper.write_bytes(b'tampered execution helper')
                with self.assertRaises(ValueError):validate_live_references(pub)
                helper.unlink()
                with self.assertRaises(ValueError):validate_live_references(pub)
                helper.write_bytes(original)
            validate_live_references(pub)
            (code/'evidence/source_snapshot.py').write_text('tampered admitted helper')
            with self.assertRaises(ValueError):materialize_execution_package(code,root/'execution-2',archive,sha(archive),pins)
            (code/'evidence/source_snapshot.py').unlink()
            with self.assertRaises(ValueError):materialize_execution_package(code,root/'execution-3',archive,sha(archive),pins)


if __name__=='__main__':unittest.main()
