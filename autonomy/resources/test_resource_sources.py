import tempfile,unittest
from pathlib import Path


class ResourceSourceTests(unittest.TestCase):
    def api(self):
        try:
            from resources.sources import freeze_sources, validate_sources
        except ImportError:
            self.fail('separate resource execution source closure must exist')
        return freeze_sources, validate_sources

    def write_current(self,current):
        for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']:
            (current/name).write_text('original '+name)

    def test_snapshot_verification_accepts_current_edits_extra_files_and_moved_checkout(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'current';current.mkdir();self.write_current(current)
            pins=freeze(current,root/'code')
            self.assertEqual(validate(current,pins),root/'code')
            (current/'execute_worker.py').write_text('changed checkout copy')
            (current/'unbound.py').write_text('unrelated helper')
            self.assertEqual(validate(current,pins),root/'code')
            moved=root/'moved-checkout';moved.mkdir();self.write_current(moved)
            self.assertEqual(validate(moved,pins),root/'code')

    def test_altered_or_missing_snapshot_refused(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'current';current.mkdir();self.write_current(current)
            pins=freeze(current,root/'code');snapshot=Path(pins['source_snapshot_store'])/pins['source_snapshot_sha256']
            snapshot.write_bytes(b'not the admitted snapshot')
            with self.assertRaises(ValueError):validate(current,pins)
            snapshot.unlink()
            with self.assertRaises(FileNotFoundError):validate(current,pins)

    def test_changed_materialized_code_refused(self):
        freeze, validate = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'current';current.mkdir();self.write_current(current)
            pins=freeze(current,root/'code')
            (root/'code/execute_worker.py').write_text('different worker')
            with self.assertRaises(ValueError):validate(current,pins)

    def test_missing_required_helper_or_symlink_refused_before_copy(self):
        freeze, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'current';current.mkdir();(current/'execute_worker.py').write_text('one file')
            with self.assertRaises(ValueError):freeze(current,root/'snapshot')
            self.assertFalse((root/'snapshot').exists())

if __name__=='__main__':unittest.main()
