"""Freeze and run the final read-only extended verifier in locked Insula."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from tier1.storage import sha
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True);parser.add_argument('--version',required=True);a=parser.parse_args();assert a.version.isalnum()
 C=Path.home()/'.cache/waystone/waymo-perception';R=C/'insula'/('advanced-closure-'+a.version);R.mkdir();source=R/'source';source.mkdir()
 for folder in ['advanced','pipeline','gpu','tier1']:shutil.copytree(P/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__'))
 pins={str(p):sha(p) for p in source.rglob('*') if p.is_file()};candidate=R/'candidate.json';shutil.copy(a.results,candidate);marker=R/'marker';marker.write_text('offline');out=P.parents[1]/'.scratch'/('advanced-closure-'+a.version+'-output');out.mkdir();root=C/'gpu-rootfs';runtime=json.loads(Path(str(root)+'.lock.json').read_text());verify_rootfs(root,runtime['rootfs_sha256']);command=launch_plan(root,source,C,out,['/opt/waymo/bin/python','/experiment/advanced/offline_closure.py']);index=command.index('--');command[index:index]=['--ro-bind',str(candidate),'/tmp/candidate.json','--ro-bind',str(marker),'/tmp/offline-verifier'];result=subprocess.run(command,capture_output=True,text=True,timeout=300);(out/'live.log').write_text(result.stdout+result.stderr);assert result.returncode==0,result.stderr;assert all(sha(path)==digest for path,digest in pins.items())
 receipt={'checks':[{'command':command,'exit_code':0}],'candidate_sha256':sha(candidate),'source_sha256':pins,'runtime_lock':runtime,'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in out.iterdir() if p.is_file()}};(P/'research'/('advanced-closure-'+a.version+'-verified.json')).write_text(json.dumps(receipt,indent=2));print(result.stdout,flush=True)
if __name__=='__main__':main()
