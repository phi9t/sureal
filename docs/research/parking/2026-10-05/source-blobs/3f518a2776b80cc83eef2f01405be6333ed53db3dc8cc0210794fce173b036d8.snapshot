"""Hash-artifact collection distinguishes typed source metadata from raw inputs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from audit_support.verification import collect_references


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a49-reference-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def ref(self,path):
        return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_review_inventory_and_symlink_descriptors_are_not_absolute_inputs(self):
        path=self.root/'inventory.json'
        path.write_text(json.dumps({'schema_version':1,'root':str(self.root/'retained-fixtures'),
            'files':[{'path':'cases/corrupt.json','sha256':'1'*64,'bytes':12,
                      'device':1,'inode':2,'kind':'file','mode':'0o644'},
                     {'path':'cases/alias','sha256':'2'*64,'bytes':7,
                      'device':1,'inode':3,'kind':'symlink','mode':'0o777'}]}))
        self.assertEqual(collect_references({'review_inventory':self.ref(path)}),[self.ref(path)])

    def test_task_map_binding_and_source_blob_pins_are_metadata(self):
        path=self.root/'map.json'
        path.write_text(json.dumps({'schema_version':1,'project':{'uid':'selected'},
            'source_commit':'a'*40,'binding':{'path':'.kata.toml','sha256':'1'*64},
            'tasks':{'49':{'spec':{'path':'docs/spec.md','blob':'b'*40,'sha256':'2'*64}}}}))
        self.assertEqual(collect_references({'map':self.ref(path)}),[self.ref(path)])

    def test_reference_scan_diagnostics_are_not_reopened_as_authority(self):
        path=self.root/'scan.json'
        path.write_text(json.dumps({'schema_version':1,'kind':'read-only-A3-reference-shape-scan',
            'issues':[{'owner':str(self.root/'negative.json'),'json_pointer':'$.tasks[0].spec',
                       'path':'docs/spec.md','sha256':'1'*64,'error':'missing blob'}]}))
        self.assertEqual(collect_references({'scan':self.ref(path)}),[self.ref(path)])

    def test_malformed_negative_payload_is_hashed_without_protocol_acceptance(self):
        payload=self.root/'corrupt.json';payload.write_bytes(b'{"schema_version":1,broken')
        holder=self.root/'holder.json';holder.write_text(json.dumps({'schema_version':1,'payload':self.ref(payload)}))
        self.assertEqual(collect_references({'fixture':self.ref(holder)}),[self.ref(holder),self.ref(payload)])

    def test_missing_and_corrupt_absolute_raw_inputs_still_fail_closed(self):
        path=self.root/'actual.json';path.write_text('{}')
        holder=self.root/'holder.json';holder.write_text(json.dumps({'schema_version':1,'actual':self.ref(path)}))
        path.write_text('{"changed":true}')
        with self.assertRaises(ValueError):collect_references({'fixture':self.ref(holder)})
        path.unlink()
        with self.assertRaises(ValueError):collect_references({'fixture':self.ref(holder)})

    def test_untyped_relative_reference_cannot_hide_a_required_input(self):
        with self.assertRaises(ValueError):
            collect_references({'actual_input':{'path':'missing.json','sha256':'1'*64}})

    def test_inventory_context_does_not_hide_additional_absolute_raw_inputs(self):
        value={'schema_version':1,'root':str(self.root),'files':[{
            'path':'retained/alias','kind':'symlink','sha256':'1'*64,
            'required_evidence':{'path':str(self.root/'absent.raw'),'sha256':'2'*64}}]}
        with self.assertRaises(ValueError):collect_references(value)

    def test_negative_definition_missing_blob_remains_source_pin_metadata(self):
        value={'schema_version':1,'tasks':[{'schema_version':1,'task_id':'49','source_commit':'a'*40,
            'goal':'negative parser input','dependencies':[],
            'spec':{'path':'docs/spec.md','sha256':'1'*64},
            'plan':{'path':'docs/plan.md','blob':'b'*40,'sha256':'2'*64}}]}
        self.assertEqual(collect_references(value),[])


if __name__=='__main__':
    unittest.main()
