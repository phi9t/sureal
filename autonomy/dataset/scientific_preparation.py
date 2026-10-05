"""Admit geometry sidecars from successful, fully rehashed independent receipts."""
import json
from pathlib import Path
from evidence.source_snapshot import file_sha256


def verified_sidecar_hashes(destination,components,scene,candidate_hashes):
    root=Path(destination);result={}
    if len(set(components))!=len(components):raise ValueError('duplicate component')
    for component in components:
        if not isinstance(component,str) or Path(component).name!=component or component in ('.','..'):raise ValueError('unsafe component')
        base=root/'evidence'/component;receipt=json.loads((base/'receipt.json').read_text())
        if receipt['component']!=component or receipt['scene']!=scene or receipt['candidate_hashes']!=candidate_hashes:raise ValueError('component receipt identity differs')
        checks=receipt['checks']
        if [c['stage'] for c in checks]!=['decode','independent-check'] or any(type(c['exit_code']) is not int or c['exit_code']!=0 for c in checks):raise ValueError('successful producer/checker commands required')
        manifest_name='sidecars/'+component+'/manifest.json';check_name='evidence/'+component+'/checked/check.json';artifacts=receipt['artifacts']
        if not {manifest_name,check_name}<=set(artifacts):raise ValueError('independent evidence not inventoried')
        for name,expected in artifacts.items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe evidence path')
            actual=file_sha256(root/relative)
            if actual!=expected:raise ValueError('component evidence changed')
        m=json.loads((root/manifest_name).read_text());check=json.loads((root/check_name).read_text())
        if check!=receipt['validation'] or check['status']!='all native identities, scalars and shaped arrays reconciled':raise ValueError('independent validation differs')
        if m['component']!=component or m['scene']!=scene or m['source_sha256']!=receipt['source_sha256'] or check['source_sha256']!=receipt['source_sha256']:raise ValueError('native source identity differs')
        result[component]=artifacts[manifest_name]
    return result
