"""Only exact reviewed metadata pins resolve against their verified source."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from audit_support.raw_git import materialize, retain
from audit_support.verification import collect_references


class SourceReviewPinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a49-reviewed-pins-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Oracle fixture')
        self.git('config','user.email','oracle@localhost')
        (self.repo/'base').write_text('base')
        self.git('add','.');self.git('commit','-qm','base')
        parent=self.git('rev-parse','HEAD').decode().strip()
        (self.repo/'.kata.toml').write_text('version = 1\n\n[project]\nname = "sureal"\n')
        binding_sha=self.ref(self.repo/'.kata.toml')['sha256']
        entries={'issue_uid':'fixture-issue','definition_revision':'a'*64,
                 'spec':{'path':'docs/spec.md','blob':'b'*40,'sha256':'c'*64},
                 'plan':{'path':'docs/plan.md','blob':'d'*40,'sha256':'e'*64},'dependencies':[]}
        folder=self.repo/'docs/research';folder.mkdir(parents=True)
        mapping={'schema_version':1,'project':{'id':2,'uid':'fixture-project','name':'sureal'},
                 'source_commit':parent,'binding':{'path':'.kata.toml','sha256':binding_sha},
                 'tasks':{'49':entries}}
        (folder/'kata-task-map.json').write_text(json.dumps(mapping,sort_keys=True))
        self.git('add','.');self.git('commit','-qm','metadata')
        candidate=self.git('rev-parse','HEAD').decode().strip()
        retained=retain(self.repo,candidate,self.root/'retained','fixture-auditor')
        self.receipt=self.root/'materialization.json'
        source=materialize(Path(retained['repository']),candidate,self.root/'source',self.receipt,'fixture-auditor')
        self.source=Path(source['source'])
        self.value={'schema_version':1,'kind':'independent-metadata-source-review',
            'candidate_role':'metadata','candidate':candidate,'parent':source['parent'],'tree':source['tree'],
            'source':source['source'],'materialization':self.ref(self.receipt),
            'retention':self.ref(self.root/'retained/retention.json'),
            'scope_review':{'binding':{'path':'.kata.toml','sha256':binding_sha,
                'project_name':'sureal','version':1},
                'task_map':{'path':'docs/research/kata-task-map.json',
                    'sha256':self.ref(self.source/'docs/research/kata-task-map.json')['sha256'],
                    'source_commit':parent,'task_count':1,
                    'fixed_entry_keys':['issue_uid','definition_revision','spec','plan','dependencies'],
                    'no_mutable_owner_status_labels_in_git':True}}}

    def git(self,*args):
        return subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(self.repo),*args],
                              check=True,capture_output=True).stdout

    def ref(self,path):
        return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_source_review_relative_pins_reopen_actual_verified_source_files(self):
        refs=collect_references(self.value)
        self.assertIn(self.ref(self.source/'.kata.toml'),refs)
        self.assertIn(self.ref(self.source/'docs/research/kata-task-map.json'),refs)
        self.assertIn(self.ref(self.receipt),refs)

    def test_wrong_source_candidate_parent_tree_or_materialization_refuses(self):
        for key,bad in [('source',str(self.repo)),('candidate','f'*40),('parent','f'*40),
                        ('tree','f'*40),('materialization',{'path':str(self.root/'missing.json'),'sha256':'a'*64})]:
            with self.subTest(key=key):
                value=copy.deepcopy(self.value);value[key]=bad
                with self.assertRaises(ValueError):collect_references(value)

    def test_metadata_pin_path_hash_type_and_semantic_changes_refuse(self):
        changes=[('binding','path','../.kata.toml'),('binding','path','/tmp/.kata.toml'),
            ('binding','path','./.kata.toml'),('binding','path',None),
            ('binding','sha256','a'*64),('binding','sha256',123),
            ('binding','project_name','foreign'),('binding','version',True),
            ('task_map','path','docs/research/../kata-task-map.json'),
            ('task_map','sha256','a'*64),('task_map','source_commit','f'*40),
            ('task_map','task_count',True),('task_map','task_count',2),
            ('task_map','fixed_entry_keys',['issue_uid']),
            ('task_map','no_mutable_owner_status_labels_in_git',False)]
        for kind,key,bad in changes:
            with self.subTest(kind=kind,key=key,bad=bad):
                value=copy.deepcopy(self.value);value['scope_review'][kind][key]=bad
                with self.assertRaises(ValueError):collect_references(value)

    def test_missing_or_corrupt_materialized_binding_and_map_refuse(self):
        for relative in ['.kata.toml','docs/research/kata-task-map.json']:
            path=self.source/relative;original=path.read_bytes()
            for corrupt in [False,True]:
                with self.subTest(relative=relative,corrupt=corrupt):
                    if corrupt:path.write_bytes(b'changed')
                    else:path.unlink()
                    try:
                        with self.assertRaises(ValueError):collect_references(self.value)
                    finally:path.write_bytes(original)

    def test_extra_nested_missing_and_corrupt_absolute_refs_cannot_hide(self):
        raw=self.root/'raw';raw.write_bytes(b'actual')
        good=self.ref(raw)
        for kind in ['binding','task_map']:
            value=copy.deepcopy(self.value);value['scope_review'][kind]['extra']={'raw':good}
            self.assertIn(good,collect_references(value))
            raw.write_bytes(b'changed')
            with self.assertRaises(ValueError):collect_references(value)
            raw.unlink()
            with self.assertRaises(ValueError):collect_references(value)
            raw.write_bytes(b'actual')

    def test_unknown_review_schema_kind_or_descriptor_position_is_not_suppressed(self):
        for field,bad in [('schema_version',2),('candidate_role','implementation'),
                          ('kind','unrecognized-source-review')]:
            value=copy.deepcopy(self.value);value[field]=bad
            with self.assertRaises(ValueError):collect_references(value)
        value=copy.deepcopy(self.value)
        value['scope_review']['unknown_pin']=value['scope_review'].pop('binding')
        with self.assertRaises(ValueError):collect_references(value)
        for name in ['binding','task_map']:
            value=copy.deepcopy(self.value);value['scope_review'][name]=[]
            with self.assertRaises(ValueError):collect_references(value)


if __name__=='__main__':
    unittest.main()
