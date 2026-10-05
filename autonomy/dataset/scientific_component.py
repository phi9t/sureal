"""Offline command boundary for separate native component production/checking."""
import json
from pathlib import Path
import sys
from .scientific_sidecars import materialize_component
from .scientific_sidecar_validate import validate_component


def main():
    mode,*args=sys.argv[1:]
    if mode=='decode':
        source,component,scene,output,budget=args
        result=materialize_component(Path(source),component,scene,Path(output),int(budget))
        print('PASS decoded native component',component,len(result['rows']),result['output_bytes'])
    elif mode=='validate':
        source,decoded,report=args;destination=Path(report)
        if destination.exists():raise ValueError('validation report already exists')
        result=validate_component(Path(source),Path(decoded))
        destination.write_text(json.dumps(result,indent=2)+'\n')
        print('PASS independent native component',result['rows'],result['arrays'])
    else:raise ValueError('unknown scientific component command')


if __name__=='__main__':main()
