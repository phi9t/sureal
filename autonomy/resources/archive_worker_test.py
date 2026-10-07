import importlib.util,json,tempfile,unittest
from pathlib import Path
from resources.sources import sha


class ResourceArchiveTests(unittest.TestCase):
    def api(self):
        try:from resources.archive_worker import process
        except ImportError:self.fail('raw resource closure needs bounded verified archive recovery')
        return process

    def test_roundtrip_exact_members_and_corrupt_manifest_refusal(self):
        process=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();(source/'proof.json').write_text('literal resource proof');packed=root/'packed';packed.mkdir()
            module=Path(__file__).resolve().parent/'resource_archive.py'
            job={'source_sha256':{'proof.json':sha(source/'proof.json')},'max_bytes':1024**2,'archive_module_path':str(module),'archive_module_sha256':sha(module)}
            created=process(job,'create',source,packed);self.assertEqual(created['members'],1)
            job['manifest_sha256']=sha(packed/'manifest.json');restored=root/'restored';restored.mkdir();result=process(job,'rehydrate',packed,restored)
            self.assertIs(result['verified_rehydration'],True);self.assertEqual((restored/'restored/proof.json').read_bytes(),(source/'proof.json').read_bytes())
            bad=root/'bad';bad.mkdir();job['manifest_sha256']='0'*64
            with self.assertRaises(ValueError):process(job,'rehydrate',packed,bad)
            self.assertFalse((bad/'restored').exists())

    def test_unpinned_archive_module_and_changed_source_refused(self):
        process=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();(source/'proof').write_text('source');out=root/'out';out.mkdir();module=Path(__file__).resolve().parent/'resource_archive.py'
            job={'source_sha256':{'proof':sha(source/'proof')},'max_bytes':1024**2,'archive_module_path':str(module),'archive_module_sha256':'0'*64}
            with self.assertRaises(ValueError):process(job,'create',source,out)
            job['archive_module_sha256']=sha(module);(source/'proof').write_text('changed')
            with self.assertRaises(ValueError):process(job,'create',source,out)
            self.assertFalse((out/'archive.tar.gz').exists())

    def test_bounded_driver_sized_chunks_and_over_limit_refusal(self):
        process=self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();(source/'driver').write_text('driver fixture');module=Path(__file__).resolve().parent/'resource_archive.py'
            job={'source_sha256':{'driver':sha(source/'driver')},'max_bytes':128*1024**2,'archive_module_path':str(module),'archive_module_sha256':sha(module)}
            good=root/'good';good.mkdir()
            try:result=process(job,'create',source,good)
            except ValueError:self.fail('shared driver dependencies require bounded128MiB chunks without increasing process/storage budgets')
            self.assertTrue(result['exact_members_and_hashes']);bad=root/'bad';bad.mkdir();job['max_bytes']+=1
            with self.assertRaises(ValueError):process(job,'create',source,bad)
            self.assertFalse((bad/'archive.tar.gz').exists())


if __name__=='__main__':unittest.main()
