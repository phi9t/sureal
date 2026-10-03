"""Bounded resource/input archive using the separately pinned admitted library."""
import hashlib,importlib.util,json,shutil,sys,tarfile
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def process(job,mode,source,output):
    source=Path(source);output=Path(output);module=Path(job['archive_module_path'])
    if (not module.is_absolute() or not module.is_file() or any(p.is_symlink() for p in [module,*module.parents]) or
        sha(module)!=job['archive_module_sha256'] or type(job['max_bytes']) is not int or not 0<job['max_bytes']<=128*1024**2):
        raise ValueError('pinned archive library and bounded resource payload required')
    spec=importlib.util.spec_from_file_location('resource_archive_library',module);library=importlib.util.module_from_spec(spec);spec.loader.exec_module(library)
    if mode=='create':
        for name,digest in job['source_sha256'].items():
            library.safe_name(name)
            if sha(source/name)!=digest:raise ValueError('resource source member changed')
        manifest=library.create_archive(source,job['source_sha256'],output/'archive.tar.gz',max_bytes=job['max_bytes'])
        (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        return library.verify_archive(output/'archive.tar.gz',manifest,max_bytes=job['max_bytes'])
    if mode not in {'verify','rehydrate'}:raise ValueError('declared archive operation required')
    if sha(source/'manifest.json')!=job['manifest_sha256']:raise ValueError('downloaded resource manifest changed')
    manifest=json.loads((source/'manifest.json').read_text());check=library.verify_archive(source/'archive.tar.gz',manifest,max_bytes=job['max_bytes'])
    if {m['path']:m['sha256'] for m in manifest['members']}!=job['source_sha256']:
        raise ValueError('resource archive member union differs from checkpoint')
    if mode=='rehydrate':
        destination=output/'restored';destination.mkdir(exist_ok=False)
        with tarfile.open(source/'archive.tar.gz','r:*') as reader:
            for member in reader:
                target=destination/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                with reader.extractfile(member) as incoming,target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing,length=1024*1024)
                target.chmod(0o444)
        for entry in manifest['members']:
            target=destination/entry['path']
            if target.stat().st_size!=entry['bytes'] or sha(target)!=entry['sha256']:raise ValueError('recovered resource member differs')
        check={**check,'verified_rehydration':True}
    return check


if __name__=='__main__':
    job=json.loads(Path('/tmp/inputs/job.json').read_text())
    result=process(job,sys.argv[1],Path('/source'),Path('/outputs'))
    Path('/outputs/check.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS resource archive',sys.argv[1],flush=True)
