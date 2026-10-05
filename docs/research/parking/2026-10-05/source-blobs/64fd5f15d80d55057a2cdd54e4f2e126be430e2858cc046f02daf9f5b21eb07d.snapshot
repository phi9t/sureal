"""An explicitly pinned historical auditor can prove a complete prior phase."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from audit_support.cases import accepted_report
from audit_support.raw_git import materialize, retain


class PriorAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a49-prior-authority-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.repo.mkdir()
        self.git('init','-q');self.git('config','user.name','Oracle fixture')
        self.git('config','user.email','oracle@localhost')
        (self.repo/'base').write_text('base')
        self.git('add','base');self.git('commit','-qm','base')
        self.coverage={'schema_version':1,'ticket_roles':{'49':['implementation']},'cases':{'49':[{'id':'independent-case',
            'phase':'gate','candidate_roles':['implementation'],
            'required_raw_evidence':['cases/independent-case/context.json']}]}}
        folder=self.repo/'docs/collaboration';folder.mkdir(parents=True)
        (folder/'coverage.json').write_text(json.dumps(self.coverage))
        self.git('add','docs');self.git('commit','-qm','old auditor snapshot')
        old=self.git('rev-parse','HEAD').decode().strip()
        old_retention=retain(self.repo,old,self.root/'old-retained','fixture-auditor')
        old_materialization=self.root/'old-materialization.json'
        old_source=materialize(Path(old_retention['repository']),old,self.root/'old-source',old_materialization,'fixture-auditor')
        self.authors={'producer':'fixture-producer','auditor':'fixture-auditor','reviewer':'fixture-reviewer'}
        review=self.root/'old-review.json'
        self.write(review,{'kind':'independent-auditor-source-review','candidate':old,'parent':old_source['parent'],
            'tree':old_source['tree'],'source':old_source['source'],'author':self.authors['auditor'],
            'reviewer':self.authors['reviewer'],'verdict':'pass','materialization':self.ref(old_materialization),
            'retention':self.ref(self.root/'old-retained/retention.json')})
        self.old_auditor={'candidate':old,'source':old_source['source'],
            'materialization':self.ref(old_materialization),'review':self.ref(review)}
        (self.repo/'producer').write_text('producer X')
        self.git('add','producer');self.git('commit','-qm','producer snapshot')
        self.candidate=self.git('rev-parse','HEAD').decode().strip()
        producer_retention=retain(self.repo,self.candidate,self.root/'producer-retained','fixture-producer')
        self.source_path=self.root/'producer-materialization.json'
        source=materialize(Path(producer_retention['repository']),self.candidate,self.root/'producer-source',self.source_path,'fixture-producer')
        self.coverage_ref=self.ref(Path(old_source['source'])/'docs/collaboration/coverage.json')
        original=self.root/'original-admission.json'
        self.original={'kind':'GateAdmission','auditor':self.old_auditor,'authors':self.authors,
            'coverage':self.coverage_ref,'source':{'candidate':self.candidate,'parent':source['parent'],
             'tree':source['tree'],'materialization_sha256':self.ref(self.source_path)['sha256'],
             'retention':self.ref(self.root/'producer-retained/retention.json')}}
        self.write(original,self.original)
        self.raw=self.root/'cases/independent-case/context.json';self.raw.parent.mkdir(parents=True)
        self.write(self.raw,{'ticket':'49','phase':'gate','candidate_role':'implementation',
            'candidate':self.candidate,'parent':source['parent'],'tree':source['tree']})
        self.report_path=self.root/'old-gate.json'
        self.report={'kind':'independent-collaboration-audit','ticket':'49','phase':'gate',
            'candidate_role':'implementation','candidate':self.candidate,'parent':source['parent'],'tree':source['tree'],
            'accepted':True,'status':'pass','phase_complete':True,'coverage_sha256':self.coverage_ref['sha256'],
            'auditor':{'candidate':old,'materialization_sha256':self.ref(old_materialization)['sha256'],
                       'review_sha256':self.ref(review)['sha256']},
            'materialization':self.ref(self.source_path),'materialization_sha256':self.ref(self.source_path)['sha256'],
            'gate_admission':self.ref(original),'gate_admission_sha256':self.ref(original)['sha256'],
            'cases':{'independent-case':{'raw_artifacts':[self.ref(self.raw)],'derived_facts':{'fixture_only':True}}}}
        self.write(self.report_path,self.report)
        report_ref=self.ref(self.report_path)
        self.admission={'auditor':{'candidate':'4'*40},'authors':self.authors,'coverage':self.coverage_ref,
            'prior_acceptances':{'implementation':{'gate':report_ref}},
            'prior_auditor_authorities':{report_ref['sha256']:{'schema_version':1,'auditor':self.old_auditor,
                                                            'authors':self.authors,'coverage':self.coverage_ref}}}

    def git(self,*args):
        return subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(self.repo),*args],check=True,capture_output=True).stdout

    def ref(self,path):
        return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def write(self,path,value):
        path.write_text(json.dumps({'schema_version':1,**value},sort_keys=True)+'\n')

    def accepted(self):
        return accepted_report(self.ref(self.report_path),candidate=self.candidate,role='implementation',phase='gate',admission=self.admission)

    def test_explicit_historical_snapshot_accepts_complete_unchanged_prior_phase(self):
        self.assertEqual(self.accepted()['candidate'],self.candidate)

    def test_cross_auditor_without_explicit_original_authority_is_refused(self):
        del self.admission['prior_auditor_authorities']
        with self.assertRaises(ValueError):self.accepted()

    def test_wrong_historical_review_or_source_identity_is_refused(self):
        for field in ('candidate','source'):
            admission=copy.deepcopy(self.admission)
            key=self.ref(self.report_path)['sha256']
            self.admission['prior_auditor_authorities'][key]['auditor'][field]='wrong'
            with self.assertRaises(ValueError):self.accepted()
            self.admission=admission

    def test_changed_original_raw_artifact_still_refuses_prior_phase(self):
        self.raw.write_text('{"changed":true}')
        with self.assertRaises(ValueError):self.accepted()

    def test_missing_original_reviewer_is_refused(self):
        Path(self.old_auditor['review']['path']).unlink()
        with self.assertRaises(ValueError):self.accepted()

    def test_missing_original_cold_pack_refuses_even_with_existing_source_repository(self):
        data=json.loads((self.root/'old-retained/retention.json').read_text())
        Path(data['pack_path']).unlink()
        with self.assertRaises(ValueError):self.accepted()

    def test_incomplete_prior_coverage_is_refused_even_with_pinned_original_authority(self):
        self.report['cases']={};self.write(self.report_path,self.report)
        ref=self.ref(self.report_path)
        self.admission['prior_acceptances']['implementation']['gate']=ref
        self.admission['prior_auditor_authorities'][ref['sha256']]={
            'schema_version':1,'auditor':self.old_auditor,'authors':self.authors,'coverage':self.coverage_ref}
        with self.assertRaises(ValueError):self.accepted()


if __name__=='__main__':
    unittest.main()
