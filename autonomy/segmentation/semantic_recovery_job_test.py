import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from segmentation.semantic_recovery_job import recover_semantic_archive
from segmentation.semantic_recovery_runtime import recovery_rootfs, validate_recovery_output
from insula.staging_lease import staging_lease

class SemanticRecoveryJobGateTests(unittest.TestCase):
    def test_ticket29_recovery_runtime_uses_current_cpu_rootfs_and_execution_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';output=root/'t29-execution/semantic-recovery/current'
            self.assertEqual(recovery_rootfs(cache).name,'rootfs-v5-t29-20261008T230657Z')
            validate_recovery_output(output)
            output.mkdir(parents=True)
            with self.assertRaises(ValueError):validate_recovery_output(output)
            output.rmdir()
            target=root/'target';target.mkdir()
            link=root/'link';link.symlink_to(target)
            with self.assertRaises(ValueError):validate_recovery_output(link)

    def test_staging_cache_can_be_separate_from_rootfs_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=root/'cache';staging=root/'ticket-execution-cache'
            (cache/'scientific-processing').mkdir(parents=True)
            rootfs=recovery_rootfs(cache);rootfs.mkdir(parents=True)
            Path(str(rootfs)+'.lock.json').write_text('{"schema_version":1,"rootfs_sha256":"%s"}' % ('c'*64))
            publication=root/'publication.json'
            publication.write_text('{"scene":"scene-a","role":"scientific","official_split":"validation","research_splits":["validation"],"archive":{"sha256":"%s","archive_bytes":1,"report_sha256":"%s"}}' % ('a'*64,'b'*64))
            record={
                'publication_manifest':str(publication),
                'publication_manifest_sha256':'pub-sha',
                'archive_hdfs_uri':'hdfs://archive',
                'archive_sha256':'a'*64,
                'archive_bytes':1,
                'report_sha256':'b'*64,
                'records':1,
                'membership':{'official_split':'validation','research_splits':['validation']},
                'scene':'scene-a',
            }
            def fake_staged(record_arg,cache_arg,**kwargs):
                self.assertEqual(Path(cache_arg),staging)
                raise RuntimeError('stop before live transfer')
            with patch('segmentation.semantic_recovery_job.sha',return_value='pub-sha'), \
                 patch('segmentation.semantic_recovery_job.verify_rootfs'), \
                 patch('segmentation.semantic_recovery_job.staged_derived_archive',side_effect=fake_staged):
                with self.assertRaises(RuntimeError):
                    recover_semantic_archive(record,cache=cache,staging_cache=staging,code_root=root,output=root/'output')

    def test_queue_refused_before_output_or_source_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp);working=cache/'scientific-processing';working.mkdir()
            output=working/'recovery'
            with staging_lease(working/'cohort-queue.lock'):
                with self.assertRaises(ValueError):
                    recover_semantic_archive({},cache=cache,code_root=cache/'missing',output=output)
            self.assertFalse(output.exists())

if __name__ == '__main__':
    unittest.main()
