import tempfile,unittest
from pathlib import Path


class ResourceSourceTests(unittest.TestCase):
    def api(self):
        try:
            from resources.sources import freeze_sources, validate_sources
        except ImportError:
            self.fail('separate resource execution source closure must exist')
        return freeze_sources, validate_sources

    def test_current_and_snapshot_edits_or_added_helpers_prevent_resume(self):
        freeze, validate = self.api()
        for fault in ['current-edit','snapshot-edit','extra-current','missing-snapshot','repin-snapshot']:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);current=root/'current';current.mkdir()
                for name in ['sources.py','command.py','stage.py','kernel_scope.py','scoped_stage.py','stage_accounting.py','execute_worker.py','process_lifecycle.py']:
                    (current/name).write_text('original '+name)
                pins=freeze(current,root/'snapshot');validate(current,pins)
                if fault=='current-edit':(current/'execute_worker.py').write_text('different worker')
                elif fault=='snapshot-edit':(root/'snapshot/execute_worker.py').write_text('different worker')
                elif fault=='extra-current':(current/'unbound.py').write_text('unbound helper')
                elif fault=='missing-snapshot':(root/'snapshot/command.py').unlink()
                else:
                    import hashlib
                    p=root/'snapshot/execute_worker.py';p.write_text('different worker');pins['execute_worker.py']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):validate(current,pins)

    def test_missing_required_helper_or_symlink_refused_before_copy(self):
        freeze, _ = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);current=root/'current';current.mkdir();(current/'execute_worker.py').write_text('one file')
            with self.assertRaises(ValueError):freeze(current,root/'snapshot')
            self.assertFalse((root/'snapshot').exists())

if __name__=='__main__':unittest.main()
