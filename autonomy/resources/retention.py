"""Bounded, measured HDFS preservation; never deletes model checkpoints."""
import errno,json,os,re,shutil,signal,subprocess,uuid
from pathlib import Path
from cohort.sustained_controller_backend import C,W,P
from pipeline.insula_entry import launch_plan
from pipeline.runtime_identity import verify_rootfs
from tier1.admission import reserve_write
from resources.sources import regular,sha,validate_sources
from resources.stage import run_stage,validate_proof,write_new,require_separate
from resources.retention_audit import validate_union,LIMIT


def partition(inventory,limit=LIMIT):
    if not inventory or type(limit) is not int or not 0<limit<=LIMIT:raise ValueError('nonempty bounded resource inventory required')
    chunks=[];current=[];size=0
    for name in sorted(inventory):
        length=inventory[name]['bytes']
        if type(length) is not int or not 0<=length<=limit:raise ValueError('resource member exceeds archive limit')
        if current and size+length>limit:chunks.append(current);current=[];size=0
        current.append(name);size+=length
    if current:chunks.append(current)
    return chunks


def stage_member(entry,target,budget_root):
    """Copy only EXDEV inputs, charging new bytes to scientific staging."""
    source=Path(entry['path']);target=Path(target);budget_root=Path(budget_root)
    if (not regular(source) or sha(source)!=entry['sha256'] or source.stat().st_size!=entry['bytes'] or
        type(entry['bytes']) is not int or not 0<=entry['bytes']<=LIMIT or target.exists() or
        not target.is_relative_to(budget_root) or any(p.is_symlink() for p in [target,*target.parents])):
        raise ValueError('exact bounded source and fresh scientific staging destination required')
    storage='hardlinked'
    try:os.link(source,target)
    except OSError as error:
        if error.errno!=errno.EXDEV:raise
        reserve_write(budget_root,entry['bytes']);shutil.copyfile(source,target);target.chmod(0o444);storage='copied'
    if target.stat().st_size!=entry['bytes'] or sha(target)!=entry['sha256']:
        raise ValueError('staged resource member differs from original input')
    return {'storage':storage,'bytes':entry['bytes'],'sha256':entry['sha256']}


def publish_bundle(backend,kind,inventory):
    """Preserve a supplied exact inventory; native admission stays separate."""
    backend.guard()
    if kind not in {'shared','checkpoint'}:raise ValueError('declared resource bundle kind required')
    chunks=partition(inventory);identifier=backend.R.name+'-'+kind+'-'+uuid.uuid4().hex
    root=C/'insula'/('resource-retention-'+identifier);require_separate(backend.output,root);root.mkdir()
    pins=backend.resource_identity['source_pins'];code=validate_sources(P/'resources',pins)
    execution=root/'execution';execution.mkdir();shutil.copytree(code,execution/'resources');(execution/'advanced').mkdir()
    library=Path(backend.host_pins['source_snapshot_root'])/'advanced/archive.py';library_sha=backend.host_pins['source_pins']['advanced/archive.py']
    shutil.copyfile(library,execution/'advanced/archive.py')
    temp=W/('resource-retention-'+identifier);temp.mkdir();raw=temp/'raw';raw.mkdir()
    def guard():
        backend.guard();validate_sources(P/'resources',pins)
        if not regular(library) or sha(library)!=library_sha:raise ValueError('pinned archive library changed')
        if sha(execution/'advanced/archive.py')!=library_sha:raise ValueError('executed archive helper changed')
        for name,digest in pins['source_pins'].items():
            if sha(execution/'resources'/name)!=digest:raise ValueError('executed resource package changed')
        for entry in inventory.values():
            if not regular(Path(entry['path'])) or sha(entry['path'])!=entry['sha256'] or Path(entry['path']).stat().st_size!=entry['bytes']:
                raise ValueError('exact resource source inventory changed')
    guard()
    staging={}
    for name,entry in inventory.items():
        from advanced.archive import safe_name
        safe_name(name);target=raw/name;target.parent.mkdir(parents=True,exist_ok=True);staging[name]=stage_member(entry,target,W)
    write_new(root/'staging.json',staging)
    expected=root/'expected.json';write_new(expected,inventory)
    runtime_root=C/'insula/rootfs-v2';runtime=json.loads(Path(str(runtime_root)+'.lock.json').read_text());verify_rootfs(runtime_root,runtime['rootfs_sha256'])
    masked={'experiment','source','outputs','dev','proc','tmp'}
    entries=sorted(runtime_root.iterdir(),key=lambda p:p.name)
    audit_bindings=[item for path in entries if path.name not in masked for item in ['--ro-bind',str(path),'/'+path.name]]
    audit_namespace={'private_tmpfs_root':True,'source_rootfs_sha256':runtime['rootfs_sha256'],
                     'readonly_entry_bindings':audit_bindings,'masked_role_entries':[p.name for p in entries if p.name in masked],
                     'source_entry_types':{p.name:{'kind':'symlink' if p.is_symlink() else 'directory' if p.is_dir() else 'file',
                                                  'symlink_target':os.readlink(p) if p.is_symlink() else None} for p in entries},
                     'scope':'readonly rootfs source entries over a private root; symlink source entries dereference to mounts; native roles override their original stubs'}
    cli=Path.home()/'workspace/waystone/scripts/waystone';tools={str(cli):sha(cli)}
    for relative in ['rust/target/debug/waystone','native/libhdfs_client/dist/lib/libhdfs_client.so','native/libhdfs_client/dist/bin/hdfs.bin']:
        path=cli.parents[1]/relative;tools[str(path)]=sha(path)
    operations=[]
    def external(arguments,label,timeout=300):
        guard()
        if any(sha(path)!=digest for path,digest in tools.items()):raise ValueError('Waystone tool changed')
        command=[str(cli),'--error-format','json','--command-timeout-secs',str(timeout),*(['--auth-source','token-file'] if arguments[0] in {'ls','put','get'} else []),*arguments]
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        try:stdout,_=child.communicate(timeout=timeout+5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);stdout,_=child.communicate();(root/(label+'.log')).write_text(stdout);raise RuntimeError('bounded HDFS transfer timed out')
        log=root/(label+'.log');log.write_text(stdout)
        if child.returncode:raise RuntimeError('HDFS transfer failed; original resource/model data retained')
        record={'stage':label,'command':command,'exit_code':0,'log_path':str(log),'log_sha256':sha(log)};operations.append(record);guard();return stdout,record
    layout=json.loads(external(['layout-profile','--project','sureal','--json'],'layout',30)[0])
    if layout['project']!='sureal':raise ValueError('expected HDFS project required')
    prefix=layout['paths']['runs'].rstrip('/')+'/perception-resource-closures/'+identifier
    external(['ls',layout['project_root']],'authenticated-read',30)
    proofs=root/'proofs';proofs.mkdir()
    pub={'schema_version':1,'kind':kind,'hdfs_prefix':prefix,'source_inventory':inventory,'source_inventory_sha256':sha(expected),
         'resource_identity_sha256':backend.resource_identity_sha256,'native_manifest_sha256':backend.manifest_sha,
         'resource_source_pins':pins,'resource_source_directory':str(P/'resources'),'execution_directory':str(execution),
         'runtime_lock':runtime,'rootfs_path':str(runtime_root),'audit_runtime_namespace':audit_namespace,
         'waystone_tool_sha256':tools,'archive_library':{'path':str(library),'sha256':library_sha},'chunks':[]}
    def live(script,mode,inputdir,source,out,label,extra=()):
        guard();out.mkdir();command=launch_plan(runtime_root,execution,source,out,['python','/experiment/resources/'+script,*([mode] if mode else [])])
        if script=='retention_audit.py':
            # A whole readonly root cannot create absent absolute evidence
            # mountpoints. Private root + readonly entries preserves runtime
            # bytes while leaving namespace scaffolding writable. Original
            # role stubs are masked by the exact launch_plan role mounts.
            index=command.index('--ro-bind')
            if command[index:index+3]!=['--ro-bind',str(runtime_root),'/']:raise ValueError('expected runtime root mount required')
            command[index:index+3]=audit_bindings
        at=command.index('--')
        command[at:at]=['--ro-bind',str(inputdir),'/tmp/inputs','--ro-bind',str(library),'/tmp/resource-archive.py',*extra]
        with (out/'live.log').open('w') as stream:run_stage(command,execution,dict(os.environ),stream,300,code=code,current_sources=P/'resources',source_pins=pins,evidence_directory=proofs/label,native_output=out,cap_bytes=16*1024**3)
        proof=proofs/label/'resource-admitted.json';value=json.loads(proof.read_text());validate_proof(value,command,P/'resources',pins,out,16*1024**3,300)
        retained=root/label;retained.mkdir()
        for filename in ['check.json','live.log']:shutil.copyfile(out/filename,retained/filename)
        guard();return {'stage':label.split('-',1)[-1] if label[0].isdigit() else label,'command':command,'exit_code':0,'resource_proof_path':str(proof),'resource_proof_sha256':sha(proof),'input_directory':str(inputdir),'input_hashes':{str(p):sha(p) for p in inputdir.iterdir()},'validation':json.loads((out/'check.json').read_text()),'artifacts':{str(p):sha(p) for p in retained.iterdir()}}
    for index,names in enumerate(chunks):
        total=sum(inventory[name]['bytes'] for name in names);reserve_write(W,3*(total+len(names)*4096+10240)+2*1024**2)
        directory=temp/str(index);directory.mkdir();inputs=root/str(index);inputs.mkdir();job={'source_sha256':{name:inventory[name]['sha256'] for name in names},'max_bytes':LIMIT,'archive_module_path':'/tmp/resource-archive.py','archive_module_sha256':library_sha}
        create_inputs=inputs/'create';create_inputs.mkdir();write_new(create_inputs/'job.json',job)
        checks=[live('archive_worker.py','create',create_inputs,raw,directory/'packed',f'{index}-create-live')]
        manifest=json.loads((directory/'packed/manifest.json').read_text());uri=prefix+'/'+manifest['archive_sha256'];download=directory/'download';download.mkdir()
        for filename,tag in [('archive.tar.gz','archive'),('manifest.json','manifest')]:
            checks.append(external(['put','--mkdir-parents',str(directory/'packed'/filename),uri+'/'+filename],f'{index}-{tag}-put')[1]);checks[-1]['stage']=tag+'-put'
            checks.append(external(['get',uri+'/'+filename,str(download/filename)],f'{index}-{tag}-get')[1]);checks[-1]['stage']=tag+'-get'
            if sha(download/filename)!=sha(directory/'packed'/filename):raise ValueError('exact HDFS resource readback required')
        job['manifest_sha256']=sha(download/'manifest.json')
        for mode in ['verify','rehydrate']:
            task=inputs/mode;task.mkdir();write_new(task/'job.json',job);checks.append(live('archive_worker.py',mode,task,download,directory/mode,f'{index}-{mode}-live'))
        shutil.copyfile(directory/'packed/manifest.json',inputs/'manifest.json');shutil.copyfile(download/'manifest.json',inputs/'readback.json')
        pub['chunks'].append({'manifest':manifest,'manifest_sha256':job['manifest_sha256'],'manifest_path':str(inputs/'manifest.json'),'readback_path':str(inputs/'readback.json'),'archive_hdfs_uri':uri+'/archive.tar.gz','manifest_hdfs_uri':uri+'/manifest.json','checks':checks})
        write_new(root/(str(index)+'-completed.json'),pub['chunks'][-1])
        # Only these fresh measured archive/readback/recovery temporaries retire.
        # Source hardlinks and every model checkpoint remain intact.
        release={str(path):sha(path) for path in directory.rglob('*') if path.is_file()};write_new(root/(str(index)+'-temporary-release.json'),release);guard();shutil.rmtree(directory)
        print('ADMITTED resource archive recovery',kind,index+1,len(chunks),flush=True)
    global_path=root/'publication-manifest.json';write_new(global_path,pub);external(['put','--mkdir-parents',str(global_path),prefix+'/publication-manifest.json'],'publication-manifest-put');readback=root/'publication-readback.json';external(['get',prefix+'/publication-manifest.json',str(readback)],'publication-manifest-get')
    if sha(global_path)!=sha(readback):raise ValueError('resource global manifest readback differs')
    pub.update({'manifest_readback_exact':True,'publication_manifest_hdfs_uri':prefix+'/publication-manifest.json','publication_manifest_sha256':sha(readback)})
    validate_union(pub,inventory,json.loads(readback.read_text()),raw)
    audit_inputs=root/'audit-input';audit_inputs.mkdir();write_new(audit_inputs/'publication.json',pub);shutil.copyfile(expected,audit_inputs/'expected.json');shutil.copyfile(readback,audit_inputs/'readback.json')
    extra=['--tmpfs','/data02','--ro-bind',str(root),str(root),'--ro-bind',str(backend.R),str(backend.R),
           '--ro-bind',str(P/'resources'),str(P/'resources')]
    audit=live('retention_audit.py',None,audit_inputs,raw,temp/'independent','independent',extra)
    if audit['validation']['whole_member_union_exact'] is not True:raise ValueError('independent whole resource recovery required')
    pub['independent_admission']=audit;receipt=root/'verified-publication.json';write_new(receipt,pub);guard()
    # These are newly created aliases/copies and audit outputs, never original
    # cohort inputs, installed drivers, or a retained model checkpoint.
    release={str(path):sha(path) for path in temp.rglob('*') if path.is_file()}
    write_new(root/'staging-temporary-release.json',release);shutil.rmtree(temp);guard()
    return {'path':str(receipt),'sha256':sha(receipt),'hdfs_manifest_uri':pub['publication_manifest_hdfs_uri'],'kind':kind}
