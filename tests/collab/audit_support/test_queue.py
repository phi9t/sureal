"""Independent selected/foreign-project restore oracle, actual SQLite fixtures."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

try:
    from audit_support.cases import queue_restore
except ImportError:
    queue_restore = None


class QueueRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root/"case"; self.case.mkdir()
        self.source = self.root/"source.db"; self.restored = self.root/"restored.db"
        self.create_db(self.source,foreign=True,instance="source")
        self.create_db(self.restored,foreign=False,instance="fresh")
        self.baseline = self.root/"baseline.db"
        self.create_db(self.baseline,foreign=False,instance="fresh",selected=False)
        self.export = self.root/"export.jsonl"
        self.export.write_text('{"project_uid":"selected"}\n{"issue_uid":"chosen"}\n')
        export_cmd = self.command("export",["kata","export","--project-id","2","--output",str(self.export)])
        import_cmd = self.command("import",["kata","import","--input",str(self.export),
            "--target",str(self.restored),"--new-instance"])
        self.data = {"schema_version":1,"selected_project_uid":"selected",
            "source_db":self.ref(self.source),"restored_db":self.ref(self.restored),
            "native_baseline_db":self.ref(self.baseline),
            "export":self.ref(self.export),"actual_export_command":self.ref(export_cmd),
            "actual_import_command":self.ref(import_cmd)}
        self.manifest = self.root/"manifest.json"
        self.save()

    def create_db(self,path,foreign,instance,selected=True):
        c=sqlite3.connect(path)
        c.executescript('CREATE TABLE projects(id INTEGER,uid TEXT,name TEXT);'
            'CREATE TABLE issues(id INTEGER,uid TEXT,project_id INTEGER,metadata TEXT,status TEXT);'
            'CREATE TABLE links(from_issue_uid TEXT,to_issue_uid TEXT,type TEXT);'
            'CREATE TABLE comments(id INTEGER,uid TEXT,issue_id INTEGER,body TEXT);'
            'CREATE TABLE meta(key TEXT,value TEXT);')
        c.execute('INSERT INTO projects VALUES(1,\'00000000000000000000000000\',\'.kata-system\')')
        if selected:
            c.execute('INSERT INTO projects VALUES(2,\'selected\',\'fixture\')')
            c.execute('INSERT INTO issues VALUES(5,\'chosen\',2,\'{}\',\'open\')')
        if foreign:
            c.execute('INSERT INTO projects VALUES(3,\'foreign\',\'other\')')
            c.execute('INSERT INTO issues VALUES(6,\'unrelated\',3,\'{}\',\'open\')')
        c.executemany('INSERT INTO meta VALUES(?,?)',[('instance_uid',instance),('schema_version','25')])
        c.commit();c.close()

    def ref(self,path):
        return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

    def command(self,name,argv):
        stdout=self.root/(name+".stdout"); stdout.write_text("actual fixture command output\n")
        stderr=self.root/(name+".stderr"); stderr.write_bytes(b"")
        path=self.root/(name+".json")
        path.write_text(json.dumps({"schema_version":1,"argv":argv,"cwd":str(self.root),
            "exit_code":0,"started_ms":1,"ended_ms":2,"stdout":self.ref(stdout),"stderr":self.ref(stderr)}))
        return path

    def save(self):
        self.manifest.write_text(json.dumps(self.data))
        (self.case/"independent-oracle.json").write_text(json.dumps({"schema_version":1,
            "raw_root":str(self.root),"fixture_manifest":self.ref(self.manifest)}))

    def test_restore_uses_only_selected_uid_projection_and_fresh_instance(self):
        self.assertIsNotNone(queue_restore,"Independent scoped restore oracle absent")
        try:
            facts=queue_restore(self.case)
        except ValueError as error:
            self.fail("Native empty sentinel is legitimate baseline: "+str(error))
        self.assertEqual(facts["project_uid"],"selected")
        self.assertEqual(facts["issue_uids"],["chosen"])

    def test_foreign_row_restoration_is_refused_despite_pass_flags(self):
        self.assertIsNotNone(queue_restore)
        c=sqlite3.connect(self.restored)
        c.execute('INSERT INTO projects VALUES(3,\'foreign\',\'other\')'); c.commit(); c.close()
        self.data["restored_db"]=self.ref(self.restored)
        self.data["passed"]=True
        self.save()
        with self.assertRaises(ValueError):
            queue_restore(self.case)

    def test_unbound_foreign_auxiliary_row_cannot_hide_behind_clean_issue_union(self):
        c=sqlite3.connect(self.restored)
        c.execute('INSERT INTO comments VALUES(9,\'foreign-comment\',999,\'foreign\')')
        c.commit();c.close()
        self.data["restored_db"]=self.ref(self.restored);self.save()
        with self.assertRaises(ValueError):
            queue_restore(self.case)

    def test_native_sentinel_fresh_timestamp_is_not_selected_payload(self):
        for path,time in ((self.source,"2026-10-04T00:00:00.000Z"),
                          (self.baseline,"2026-10-04T01:00:00.000Z"),
                          (self.restored,"2026-10-04T02:00:00.000Z")):
            c=sqlite3.connect(path);c.execute('ALTER TABLE projects ADD COLUMN created_at TEXT')
            c.execute('UPDATE projects SET created_at=? WHERE id=1',(time,));c.commit();c.close()
        self.data["native_baseline_db"]=self.ref(self.baseline)
        self.data["source_db"]=self.ref(self.source)
        self.data["restored_db"]=self.ref(self.restored);self.save()
        self.assertEqual(queue_restore(self.case)["project_uid"],"selected")

    def test_native_sentinel_numeric_id_may_be_fresh_without_payload(self):
        c=sqlite3.connect(self.restored)
        c.execute("UPDATE projects SET id=4 WHERE uid='00000000000000000000000000'")
        c.commit();c.close()
        self.data["restored_db"]=self.ref(self.restored);self.save()
        self.assertEqual(queue_restore(self.case)["project_uid"],"selected")


if __name__=="__main__":
    unittest.main()
