import json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from tracking import publish
from tracking.journal import append_entry
class PublicationIsolationTests(unittest.TestCase):
 def test_journal_publication_does_not_replace_experiment_result_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);home=root/'home';project=root/'project';research=project/'research';research.mkdir(parents=True);(research/'journal-evidence').mkdir();(home/'.cache/waystone/waymo-perception/insula').mkdir(parents=True)
   for name in ['experiment-registry.json','experiments.json']:(research/name).write_text('{}')
   for name in ['experiment-tracker.md','research-journal.md']:(research/name).write_text('snapshot')
   append_entry(research/'research-journal.jsonl','observation',['fixture'],'Verified fixture',[])
   result_receipt=research/'tier1-results-hdfs-verified.json';result_receipt.write_text('{"original_result":true}');original=result_receipt.read_bytes()
   waystone=home/'workspace/waystone'
   for name in ['scripts/waystone','rust/target/debug/waystone','native/libhdfs_client/dist/lib/libhdfs_client.so','native/libhdfs_client/dist/bin/hdfs.bin']:
    path=waystone/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture tool')
   remote={}
   class Process:
    returncode=0
    def __init__(self,command,**kwargs):
     if 'put' in command:remote[command[-1]]=Path(command[-2]).read_bytes()
     elif 'get' in command:Path(command[-1]).write_bytes(remote[command[-2]])
    def communicate(self,timeout=None):return '',''
   layout=types.SimpleNamespace(stdout=json.dumps({'paths':{'runs':'hdfs://fixture/runs/'}}))
   with patch.object(publish,'P',project),patch('tracking.publish.Path.home',return_value=home),patch('tracking.publish.subprocess.run',return_value=layout),patch('tracking.publish.subprocess.Popen',Process):publish.main()
   self.assertEqual(result_receipt.read_bytes(),original)
   receipt=json.loads((research/'research-journal-hdfs-verified.json').read_text());self.assertTrue(receipt['all_results_uploaded_and_readback_exact']);self.assertEqual(len(receipt['files']),5)
if __name__=='__main__':unittest.main()
