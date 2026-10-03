"""Separate offline producer/checker commands with externally supplied provenance."""
import json,sys
from pathlib import Path
from .scientific_reconstruction import reconstruct_scene
from .scientific_scene_validate import validate_scene


def main():
    mode,source,sidecars,provenance,records,argument=sys.argv[1:]
    source,sidecars,records=map(Path,(source,sidecars,records))
    hashes=json.loads(Path(provenance).read_text())
    if mode=='reconstruct':
        r=reconstruct_scene(source,sidecars,records,int(argument),verified_manifest_hashes=hashes)
        print('PASS reconstructed native scene',len(r['rows']),r['points'])
    elif mode=='validate':
        output=Path(argument)
        if output.exists():raise ValueError('independent validation output already exists')
        r=validate_scene(source,sidecars,records,verified_manifest_hashes=hashes)
        with output.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
        print('PASS independently validated native scene',r['records'],r['points'])
    else:raise ValueError('unknown scientific scene command')


if __name__=='__main__':main()
