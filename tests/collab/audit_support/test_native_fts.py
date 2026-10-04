"""Searchable native FTS5 payload must agree with independently known issue text."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_support.evidence import sqlite_projection
from audit_support.cases import check_auxiliary_closure


class NativeSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="a49-native-search-")
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"native.db"
        inputs=Path(__file__).parent/"fixtures"
        schema=inputs/"kata-schema25.sql"
        provenance=json.loads((inputs/"kata-schema25-provenance.json").read_text())
        self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(),provenance["schema_sha256"])
        self.connection=sqlite3.connect(self.path)
        self.connection.executescript(schema.read_text())
        self.connection.executemany('INSERT INTO meta(key,value) VALUES(?,?)',
            [('schema_version','25'),('instance_uid','independent-native-fixture')])
        self.connection.execute("INSERT INTO projects(uid,name) VALUES('00000000000000000000000001','native-search')")
        self.connection.execute("INSERT INTO issues(uid,project_id,short_id,title,body,author) "
            "VALUES('00000000000000000000000002',1,'0002','Café geometry','Lidar range','independent-oracle')")
        self.connection.execute("INSERT INTO comments(uid,issue_id,author,body) "
            "VALUES('00000000000000000000000003',1,'independent-oracle','coöperative trajectory')")
        self.connection.commit()
        self.addCleanup(self.connection.close)

    def reference(self):
        self.connection.commit()
        return {"path":str(self.path),"sha256":hashlib.sha256(self.path.read_bytes()).hexdigest()}

    def test_native_index_with_unicode_and_ordered_comments_is_valid(self):
        self.assertEqual(self.connection.execute("SELECT rowid FROM issues_fts WHERE issues_fts MATCH 'cafe'").fetchall(),[(1,)])
        facts=sqlite_projection(self.reference())
        self.assertEqual(facts["projects"][0]["uid"],"00000000000000000000000001")

    def test_searchable_orphan_native_fts_row_is_refused(self):
        self.connection.execute("INSERT INTO issues_fts(rowid,title,body,comments) "
            "VALUES(999999,'foreignsecretneedle','','')")
        self.assertEqual(self.connection.execute("SELECT rowid FROM issues_fts WHERE issues_fts MATCH 'foreignsecretneedle'").fetchall(),[(999999,)])
        with self.assertRaises(ValueError):
            sqlite_projection(self.reference())

    def test_foreign_indexed_term_on_existing_issue_is_refused(self):
        self.connection.execute("INSERT INTO issues_fts(rowid,title,body,comments) "
            "VALUES(1,'foreignsecretneedle','','')")
        self.assertEqual(self.connection.execute("SELECT rowid FROM issues_fts WHERE issues_fts MATCH 'foreignsecretneedle'").fetchall(),[(1,)])
        with self.assertRaises(ValueError):
            sqlite_projection(self.reference())

    def test_empty_orphan_document_cannot_hide_from_vocabulary(self):
        self.connection.execute("INSERT INTO issues_fts(rowid,title,body,comments) VALUES(999999,'','','')")
        with self.assertRaises(ValueError):
            sqlite_projection(self.reference())

    def test_native_empty_document_remains_a_valid_indexed_issue(self):
        self.connection.execute('DELETE FROM comments')
        # Native titles must be nonblank; punctuation is legitimate tokenless text.
        self.connection.execute("UPDATE issues SET title='...',body='' WHERE id=1")
        facts=sqlite_projection(self.reference())
        self.assertEqual(facts["search_index"]["documents"],[1])
        self.assertEqual(facts["search_index"]["instances"],[])

    def test_index_only_optimization_is_visible_to_readonly_status_oracle(self):
        for body in ('first changed body','second changed body'):
            self.connection.execute('UPDATE issues SET body=? WHERE id=1',(body,))
            self.connection.commit()
        before=sqlite_projection(self.reference())
        self.connection.execute("INSERT INTO issues_fts(issues_fts) VALUES('optimize')")
        after=sqlite_projection(self.reference())
        self.assertEqual(before["issues"],after["issues"])
        self.assertEqual(before["search_index"],after["search_index"])
        self.assertNotEqual(before["tables"],after["tables"])

    def test_deleted_foreign_term_cannot_hide_in_current_shadow_payload(self):
        clean=sqlite_projection(self.reference())
        marker='foreignhistoricalpayloadneedle'
        self.connection.execute("INSERT INTO issues_fts(rowid,title,body,comments) VALUES(999999,?,'','')",(marker,))
        self.connection.commit()
        self.connection.execute("INSERT INTO issues_fts(issues_fts,rowid,title,body,comments) "
                                "VALUES('delete',999999,?,'','')",(marker,))
        self.connection.commit()
        self.assertEqual(self.connection.execute("SELECT rowid FROM issues_fts WHERE issues_fts MATCH ?",(marker,)).fetchall(),[])
        current=self.connection.execute('SELECT block FROM issues_fts_data').fetchall()
        self.assertTrue(any(marker.encode() in row[0] for row in current))
        contaminated=sqlite_projection(self.reference())
        self.assertEqual(clean['search_index'],contaminated['search_index'])
        # Ignoring shadow rows after active-posting validation wrongly accepts
        # this actual insert/commit/delete/commit contamination.
        with self.assertRaises(ValueError):
            check_auxiliary_closure(clean,contaminated,{'tables':{}},clean['projects'][0]['uid'],clean)

    def test_native_physical_closure_accepts_exact_fresh_rows_with_unicode_comments(self):
        fresh=sqlite_projection(self.reference())
        check_auxiliary_closure(fresh,fresh,{'tables':{}},fresh['projects'][0]['uid'],fresh)

    def test_native_physical_closure_refuses_missing_reconstruction(self):
        fresh=sqlite_projection(self.reference())
        with self.assertRaises(ValueError):
            check_auxiliary_closure(fresh,fresh,{'tables':{}},fresh['projects'][0]['uid'])


if __name__=="__main__":
    unittest.main()
