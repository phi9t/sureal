#!/usr/bin/env python3
"""Archive closed original payloads, admit recipes, run and close expanded matrix."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[1];C=Path.home()/'.cache/waystone/waymo-perception'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='expanded20261002a');parser.add_argument('--admission-version',default='v2');args=parser.parse_args();assert args.run_id.isalnum() and args.admission_version.isalnum()
 original=P/'research/tier1-overfit20261002b-results.json';closure=P/'research/tier1-closure-live-final-v4-verified.json';result=json.loads(original.read_text());assert result['finished']
 logs=C/'insula'/('expanded-controller-'+args.run_id);logs.mkdir(exist_ok=True)
 def stage(name,command):
  print('RUN',name,flush=True)
  with (logs/(name+'.log')).open('a') as output:subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,check=True)
  print('ADMITTED',name,flush=True)
 for name,case in result['cases'].items():
  if case['status']=='exact observation equivalence control':continue
  retained=list((C/'insula').glob('hdfs-retention-tier1-overfit20261002b-'+name+'-*/release-completed.json'))
  if retained:
   for path in retained:
    record=json.loads(path.read_text());publication_path=path.with_name('verified-publication.json')
    with publication_path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==record['publication_receipt_sha256']
    publication=json.loads(publication_path.read_text());assert publication['manifest_readback_exact'] and publication['closure_complete']
   print('REUSED verified HDFS retention',name,flush=True);continue
  stage('archive-'+name,['python',str(P/'advanced/publish.py'),'--results',str(original),'--closure',str(closure),'--case',name,'--release'])
 admission=P/'research/advanced-native-admission-verified.json'
 if admission.exists():shutil.copy(admission,admission.with_name('advanced-native-admission-before-'+args.admission_version+'.json'))
 stage('native-admission',['python',str(P/'advanced/admit.py'),'--version',args.admission_version])
 stage('train',['python',str(P/'advanced/run.py'),'--run-id',args.run_id])
 extended=P/'research'/('advanced-'+args.run_id+'-results.json');matrix=json.loads(extended.read_text());assert matrix['finished'] and len(matrix['cases'])==8;assert all(case['status'] in ['sustained native overfit','failed to overfit by 10000 updates'] for case in matrix['cases'].values()),[(name,case['status']) for name,case in matrix['cases'].items()]
 stage('closure',['python',str(P/'advanced/close.py'),'--results',str(extended),'--version',args.run_id])
 stage('tracking',['python',str(P/'tracking/cli.py'),'refresh'])
 stage('journal-hdfs',['python',str(P/'tracking/publish.py')])
 print('PASS expanded matrix and live closure',extended,flush=True)
if __name__=='__main__':main()
