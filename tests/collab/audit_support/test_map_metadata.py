"""A relative M binding pin still requires actual raw source bytes."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

from audit_support.cases import map_gate, verify_definition
from audit_support.facts import content_digest
from audit_support.raw_git import materialize
from audit_support.verification import collect_references


class MapMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a49-map-source-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Map oracle fixture');self.git('config','user.email','oracle@localhost')
        (self.repo/'docs').mkdir();(self.repo/'docs/spec.md').write_text('private spec\n')
        (self.repo/'docs/plan.md').write_text('private plan\n')
        self.git('add','docs');self.git('commit','-qm','fixture source X')
        base=self.git('rev-parse','HEAD').decode().strip()
        baseline=self.root/'baseline.db';self.database=self.root/'project.db'
        connection=sqlite3.connect(baseline)
        connection.executescript((Path(__file__).parent/'fixtures/kata-schema25.sql').read_text())
        connection.execute("INSERT INTO meta(key,value) VALUES('schema_version','25')")
        connection.execute("INSERT INTO projects(uid,name) VALUES('00000000000000000000000000','.kata-system')")
        connection.commit();connection.close();shutil.copyfile(baseline,self.database)
        connection=sqlite3.connect(self.database)
        self.uid='00000000000000000000000001'
        connection.execute("INSERT INTO projects(uid,name) VALUES(?,'private-map')",(self.uid,))
        tasks={};self.definitions={}
        for index,task in enumerate([str(value) for value in range(44,55)]+['53.0','53.A','53.B'],start=10):
            pins={field:{'path':'docs/'+field+'.md','blob':self.git('rev-parse',base+':docs/'+field+'.md').decode().strip(),
                         'sha256':hashlib.sha256((self.repo/'docs'/f'{field}.md').read_bytes()).hexdigest()}
                  for field in ('spec','plan')}
            definition={'schema_version':1,'task_id':task,'source_commit':base,'goal':'Private scoped fixture '+task,
                        'spec':pins['spec'],'plan':pins['plan'],'dependencies':[]}
            definition['revision']=content_digest(definition);self.definitions[task]=definition
            issue_uid=f'{index:026d}'
            connection.execute('INSERT INTO issues(uid,project_id,short_id,title,body,author,metadata) VALUES(?,2,?,?,?,?,?)',
                (issue_uid,str(index).rjust(4,'0'),'private task '+task,'private acceptance','oracle',
                 json.dumps({'sureal_task':task,'sureal_definition':definition})))
            tasks[task]={'issue_uid':issue_uid,'definition_revision':definition['revision'],**pins,'dependencies':[]}
        connection.commit();connection.close()
        (self.repo/'.kata.toml').write_text('project = "'+self.uid+'"\n')
        folder=self.repo/'docs/research';folder.mkdir()
        mapping={'schema_version':1,'project':{'id':2,'uid':self.uid,'name':'private-map'},
                 'binding':{'path':'.kata.toml','sha256':hashlib.sha256((self.repo/'.kata.toml').read_bytes()).hexdigest()},
                 'source_commit':base,'tasks':tasks}
        (folder/'kata-task-map.json').write_text(json.dumps(mapping))
        self.git('add','.kata.toml','docs/research');self.git('commit','-qm','fixture metadata M')
        candidate=self.git('rev-parse','HEAD').decode().strip()
        self.source=self.root/'raw-M'
        self.materialization=materialize(self.repo,candidate,self.source,self.root/'M-source.json','fixture-only')
        self.admission={'kata':{'db_path':str(self.database),'native_baseline_db':self.ref(baseline)}}
        self.case=self.root/'case';self.case.mkdir()
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps({'schema_version':1,'project_db':self.ref(self.database)}))
        (self.case/'independent-oracle.json').write_text(json.dumps({'schema_version':1,'raw_root':str(self.root),
                                                                  'fixture_manifest':self.ref(manifest)}))

    def git(self,*args):
        return subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(self.repo),*args],capture_output=True,check=True).stdout

    def ref(self,path):
        return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_valid_scoped_M_metadata_pin_is_not_an_absolute_ref_but_raw_binding_is_checked(self):
        reference=self.ref(self.source/'docs/research/kata-task-map.json')
        self.assertEqual(collect_references({'mapping':reference}),[reference])
        self.assertEqual(map_gate(self.case,self.materialization,self.admission)['task_count'],14)

    def test_missing_raw_M_binding_is_refused_despite_metadata_pin(self):
        (self.source/'.kata.toml').unlink()
        with self.assertRaises((ValueError,OSError)):map_gate(self.case,self.materialization,self.admission)

    def test_corrupt_raw_M_binding_is_refused_despite_metadata_pin(self):
        (self.source/'.kata.toml').write_text('project = "wrong"\n')
        with self.assertRaises(ValueError):map_gate(self.case,self.materialization,self.admission)

    def test_incomplete_spec_metadata_does_not_gain_definition_authority(self):
        definition=dict(self.definitions['49']);definition['spec']=dict(definition['spec']);definition['spec'].pop('blob')
        self.assertEqual(collect_references({'schema_version':1,'tasks':[definition]}),[])
        with self.assertRaises((ValueError,KeyError)):verify_definition(definition,self.repo)


if __name__=='__main__':
    unittest.main()
