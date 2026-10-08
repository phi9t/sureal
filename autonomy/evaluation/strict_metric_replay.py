"""Read-only replay of retained metric reports through strict readers."""
import argparse
import json
import re
from pathlib import Path

try:
    from detection.native_detection_adapter import parse_result as parse_detection
    from motion.ingestion.strict_metric_reader import parse_result as parse_motion
    from segmentation.strict_metric_reader import parse_result as parse_segmentation
except ModuleNotFoundError:
    from autonomy.detection.native_detection_adapter import parse_result as parse_detection
    from autonomy.motion.ingestion.strict_metric_reader import parse_result as parse_motion
    from autonomy.segmentation.strict_metric_reader import parse_result as parse_segmentation

MISKEYED_RANGE_RE=re.compile(r'^(?:30|50|\+inf)\)_LEVEL_[12]$')
_CACHE_ROOT=Path.home()/'.cache/waystone/waymo-perception'

def _read_text(path):
    return path.read_text(errors='replace')

def _is_detection_stdout(text):
    return '[mAP ' in text and '[mAPH ' in text and 'examples found.' in text

def _is_segmentation_stdout(text):
    return 'miou=' in text and 'frames found in prediction.' in text

def _is_motion_report(value):
    return (isinstance(value,dict) and isinstance(value.get('metrics'),dict)
            and isinstance(value['metrics'].get('metricsBundles'),list)
            and isinstance(value.get('counts'),list))

def _has_miskeyed_range_metrics(value):
    if isinstance(value,dict):
        metrics=value.get('metrics')
        if isinstance(metrics,dict) and any(MISKEYED_RANGE_RE.fullmatch(str(key)) for key in metrics):
            return True
        return any(_has_miskeyed_range_metrics(child) for child in value.values())
    if isinstance(value,list):
        return any(_has_miskeyed_range_metrics(child) for child in value)
    return False

def _known_root_label(root, repo):
    resolved=root.resolve()
    if resolved==_CACHE_ROOT.resolve():
        return '<cache>'
    if resolved==(repo/'autonomy/research').resolve():
        return 'autonomy/research'
    return None

def _root_specs(roots, root_labels=None, repo=None):
    repo=Path(__file__).resolve().parents[2] if repo is None else Path(repo)
    roots=[Path(root) for root in roots]
    if root_labels is not None and len(root_labels)!=len(roots):
        raise ValueError('root label count must match roots')
    specs=[]
    for index,root in enumerate(roots):
        label=root_labels[index] if root_labels is not None else _known_root_label(root,repo)
        specs.append((root,label or f'<root{index}>'))
    return specs

def _reported_path(path, specs):
    resolved=path.resolve()
    for root,label in specs:
        try:
            relative=resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return label if str(relative)=='.' else f'{label}/{relative.as_posix()}'
    raise ValueError('metric report path is outside replay roots')

def _record_rejection(report, kind, path, specs, error):
    report['rejections'].append({'kind':kind,'path':_reported_path(path,specs),'reason':str(error)})

def _scan_stdout(path, report, specs):
    text=_read_text(path)
    stderr_path=path.with_name('metrics.stderr')
    stderr=_read_text(stderr_path) if stderr_path.exists() else ''
    if _is_detection_stdout(text):
        report['counts']['detection']+=1
        try:
            parsed=parse_detection(0,text,stderr)
        except ValueError as error:
            _record_rejection(report,'detection',path,specs,error)
        else:
            for key,count in parsed['diagnostics'].items():
                report['detection_diagnostics'][key]=report['detection_diagnostics'].get(key,0)+count
    elif _is_segmentation_stdout(text):
        report['counts']['segmentation']+=1
        try:
            if stderr.strip():
                raise ValueError('segmentation metric stderr emitted diagnostics')
            parse_segmentation(text)
        except ValueError as error:
            _record_rejection(report,'segmentation',path,specs,error)

def _scan_json(path, report, specs):
    try:
        value=json.loads(path.read_text())
    except (UnicodeDecodeError,json.JSONDecodeError):
        return
    if path.name=='check.json' and _has_miskeyed_range_metrics(value):
        report['miskeyed_check_json_files']+=1
        report['miskeyed_check_json_paths'].append(_reported_path(path,specs))
    if _is_motion_report(value):
        report['counts']['motion']+=1
        try:
            parse_motion(value)
        except ValueError as error:
            _record_rejection(report,'motion',path,specs,error)

def replay_roots(roots, root_labels=None):
    specs=_root_specs(roots,root_labels)
    report={'roots':[label for _,label in specs],
            'counts':{'detection':0,'segmentation':0,'motion':0},
            'rejections':[],
            'detection_diagnostics':{},
            'miskeyed_check_json_files':0,
            'miskeyed_check_json_paths':[]}
    for root,_ in specs:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            if path.name=='metrics.stdout':
                _scan_stdout(path,report,specs)
            elif path.suffix=='.json':
                _scan_json(path,report,specs)
    return report

def markdown_report(report):
    lines=[
        '# Strict metric replay report',
        '',
        'Read-only roots:',
    ]
    lines.extend(f'- `{root}`' for root in report['roots'])
    lines.extend([
        '',
        '## Counts',
        '',
        f"- Detection metric reports: {report['counts']['detection']}",
        f"- Segmentation metric reports: {report['counts']['segmentation']}",
        f"- Motion metric reports: {report['counts']['motion']}",
        f"- Retained check.json files with mis-keyed range metric entries: {report['miskeyed_check_json_files']}",
        '',
        '## Detection Diagnostics',
        '',
    ])
    if report['detection_diagnostics']:
        lines.extend(f"- `{key}`: {value}" for key,value in sorted(report['detection_diagnostics'].items()))
    else:
        lines.append('- None')
    lines.extend(['','## Rejections',''])
    if report['rejections']:
        for rejection in report['rejections']:
            lines.append(f"- `{rejection['kind']}` `{rejection['path']}`: {rejection['reason']}")
    else:
        lines.append('- None')
    lines.extend(['','## Mis-Keyed Check JSON Paths',''])
    if report['miskeyed_check_json_paths']:
        lines.extend(f"- `{path}`" for path in report['miskeyed_check_json_paths'])
    else:
        lines.append('- None')
    return '\n'.join(lines)+'\n'

def write_report(report, output_dir):
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    (output/'replay-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (output/'replay-report.md').write_text(markdown_report(report))

def main(argv=None):
    repo=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(repo/'docs/strict-metrics'))
    parser.add_argument('roots',nargs='*',
                        default=[str(_CACHE_ROOT),str(repo/'autonomy/research')])
    args=parser.parse_args(argv)
    specs=_root_specs([Path(root) for root in args.roots],repo=repo)
    report=replay_roots([root for root,_ in specs],[label for _,label in specs])
    write_report(report,args.output)
    return 1 if report['rejections'] else 0

if __name__=='__main__':
    raise SystemExit(main())
