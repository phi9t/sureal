"""Read-only replay of retained metric reports through strict readers."""
import argparse
from collections import Counter
import json
import re
from pathlib import Path

try:
    from detection.native_detection_adapter import parse_result as parse_detection
    from evidence.projection import score_record_classes as projection_score_record_classes
    from evidence.score_records import LEVEL2_CLASS_KEYS, populated_level2_classes, read_level2_per_class
    from motion.ingestion.strict_metric_reader import parse_result as parse_motion
    from segmentation.strict_metric_reader import parse_result as parse_segmentation
except ModuleNotFoundError:
    from autonomy.detection.native_detection_adapter import parse_result as parse_detection
    from autonomy.evidence.projection import score_record_classes as projection_score_record_classes
    from autonomy.evidence.score_records import LEVEL2_CLASS_KEYS, populated_level2_classes, read_level2_per_class
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

def _json_path(parts):
    return '/'.join(str(part) for part in parts)

def _walk_level2_records(value, path=()):
    if isinstance(value,dict):
        if 'LEVEL2_per_class' in value:
            yield path+('LEVEL2_per_class',), value['LEVEL2_per_class'], value
        for key,child in value.items():
            yield from _walk_level2_records(child,path+(str(key),))
    elif isinstance(value,list):
        for index,child in enumerate(value):
            yield from _walk_level2_records(child,path+(str(index),))

def _score_record_shape(record):
    if not isinstance(record,dict):
        return 'not a JSON object'
    rows=Counter()
    for row in record.values():
        rows[tuple(sorted(str(key) for key in row)) if isinstance(row,dict) else ('not a JSON object',)]+=1
    row_text=', '.join(f"{'/'.join(keys)} x{count}" for keys,count in sorted(rows.items()))
    return f"classes={','.join(sorted(str(key) for key in record))}; rows={row_text}"

def _is_odd_score_record(record):
    return (
        not isinstance(record,dict)
        or not set(str(key) for key in record).issubset(set(LEVEL2_CLASS_KEYS))
        or any(not isinstance(row,dict) or set(row)!={'AP','APH'} for row in record.values())
    )

def _producer_for_score_record(path, parent):
    text=path.as_posix()
    if '/association-runs/' in text:
        return 'association oracle coverage control'
    if '/research-tracker-live-' in text:
        return 'research tracker live fixture'
    if isinstance(parent,dict):
        scope=parent.get('scope')
        if isinstance(scope,str):
            if 'full native GT V3 diagnostic' in scope:
                return 'sustained metrics scorer'
            if 'single-batch training-only overfit diagnostic' in scope:
                return 'populated-class native scorer'
    return 'retained score summary'

def _populated_record_classes(record, parent):
    if isinstance(parent,dict) and 'groundtruth_by_class' in parent:
        classes=populated_level2_classes(parent)
        if set(classes)!=set(LEVEL2_CLASS_KEYS):
            return classes
        return None
    if not isinstance(record,dict):
        return None
    keys=tuple(key for key in LEVEL2_CLASS_KEYS if key in record)
    if keys and set(keys)==set(record) and set(keys)!=set(LEVEL2_CLASS_KEYS):
        return keys
    return None

def _score_consumer_template():
    return {
        'sustained_admission':{
            'class_rule':'all four native LEVEL_2 classes: 1, 2, 3, 4',
            'records':0,'accepted':0,'rejected':0,
        },
        'sustained_contract':{
            'class_rule':'all four native LEVEL_2 classes: 1, 2, 3, 4; reduced APH samples are wrapped as AP=APH before reading',
            'records':0,'accepted':0,'rejected':0,
        },
        'evidence_projection':{
            'class_rule':'classes with positive groundtruth_by_class when present; otherwise all-class points require 1, 2, 3, 4 and summary-only points use their retained key set',
            'records':0,'accepted':0,'rejected':0,
        },
        'fixed_batch_verifier':{
            'class_rule':'all four native LEVEL_2 classes: 1, 2, 3, 4',
            'records':0,'accepted':0,'rejected':0,
        },
    }

def _score_rejection(report, consumer, path, json_path, classes, specs, error):
    report['consumers'][consumer]['rejected']+=1
    report['rejections'].append({
        'consumer':consumer,
        'path':_reported_path(path,specs),
        'json_path':_json_path(json_path),
        'classes':list(classes),
        'reason':str(error),
    })

def _replay_score_record(report, consumer, path, json_path, record, classes, specs, consumed_level2_records):
    report['consumers'][consumer]['records']+=1
    consumed_level2_records.add((Path(path).resolve(),tuple(json_path)))
    try:
        read_level2_per_class(record,classes=classes)
    except ValueError as error:
        _score_rejection(report,consumer,path,json_path,classes,specs,error)
    else:
        report['consumers'][consumer]['accepted']+=1

def _replay_aph_sample(report, path, json_path, sample, specs):
    report['consumers']['sustained_contract']['records']+=1
    record={key:{'AP':value,'APH':value} for key,value in sample['APH'].items()}
    try:
        read_level2_per_class(record,classes=LEVEL2_CLASS_KEYS)
    except ValueError as error:
        _score_rejection(report,'sustained_contract',path,json_path,LEVEL2_CLASS_KEYS,specs,error)
    else:
        report['consumers']['sustained_contract']['accepted']+=1

def _load_json(path):
    if not isinstance(path,(str,Path)):
        return None
    try:
        return json.loads(Path(path).read_text())
    except (OSError,UnicodeDecodeError,json.JSONDecodeError):
        return None

def _registry_result_paths(repo):
    registry_path=Path(repo)/'autonomy/research/experiment-registry.json'
    registry=_load_json(registry_path)
    if not isinstance(registry,dict):
        return []
    paths=[]
    for run in registry.get('runs',[]):
        if isinstance(run,dict) and run.get('results'):
            paths.append(Path(repo)/'autonomy'/run['results'])
    return paths

def _fixed_batch_result_paths(repo):
    research=Path(repo)/'autonomy/research'
    return [
        path for path in [
            research/'tier1-overfit20261002b-results.json',
            research/'advanced-expanded20261002a-results.json',
        ] if path.exists()
    ]

def _record_references_in_file(path):
    value=_load_json(path)
    if value is None:
        return []
    return [(json_path,record,parent) for json_path,record,parent in _walk_level2_records(value)]

def _replay_projection_scores(report, repo, specs, consumed_level2_records):
    for result_path in _registry_result_paths(repo):
        for json_path,record,parent in _record_references_in_file(result_path):
            classes=projection_score_record_classes(parent)
            _replay_score_record(report,'evidence_projection',result_path,json_path,record,classes,specs,consumed_level2_records)

def _replay_fixed_batch_scores(report, repo, specs, consumed_level2_records):
    for result_path in _fixed_batch_result_paths(repo):
        result=_load_json(result_path)
        if not isinstance(result,dict):
            continue
        for json_path,record,_ in _walk_level2_records(result):
            _replay_score_record(report,'fixed_batch_verifier',result_path,json_path,record,LEVEL2_CLASS_KEYS,specs,consumed_level2_records)
        for case in result.get('cases',{}).values():
            if not isinstance(case,dict):
                continue
            control_path=case.get('terminal_GPU_equivalence_receipt')
            if control_path:
                control=_load_json(control_path)
                if isinstance(control,dict):
                    try:
                        record=control['validation']['inherited_native_LEVEL2_per_class']
                    except (KeyError,TypeError):
                        pass
                    else:
                        _replay_score_record(report,'fixed_batch_verifier',Path(control_path),('validation','inherited_native_LEVEL2_per_class'),record,LEVEL2_CLASS_KEYS,specs,consumed_level2_records)
            if case.get('status') not in ['sustained native overfit','failed to overfit by 10000 updates']:
                continue
            for reference in case.get('verification_receipts',[]):
                receipt_path=reference.get('receipt') if isinstance(reference,dict) else None
                receipt=_load_json(receipt_path) if receipt_path else None
                if not isinstance(receipt,dict) or '-score-' not in receipt.get('name',receipt.get('stage','')):
                    continue
                try:
                    record=receipt['validation']['LEVEL2_per_class']
                except (KeyError,TypeError):
                    continue
                _replay_score_record(report,'fixed_batch_verifier',Path(receipt_path),('validation','LEVEL2_per_class'),record,LEVEL2_CLASS_KEYS,specs,consumed_level2_records)

def _sustained_state_paths(repo):
    research=Path(repo)/'autonomy/research'
    paths=[]
    for live_path in sorted(research.glob('balanced16-sustained-*-live.json')):
        live=_load_json(live_path)
        if not isinstance(live,dict):
            continue
        for case in live.get('cases',{}).values():
            if isinstance(case,dict) and case.get('case_directory'):
                state=Path(case['case_directory'])/'state.json'
                if state.exists():
                    paths.append(state)
    return paths

def _replay_sustained_scores(report, repo, specs, consumed_level2_records):
    for state_path in _sustained_state_paths(repo):
        state=_load_json(state_path)
        if not isinstance(state,dict):
            continue
        for index,record_state in enumerate(state.get('records',[])):
            if not isinstance(record_state,dict):
                continue
            sample=record_state.get('sample')
            if isinstance(sample,dict) and 'APH' in sample:
                _replay_aph_sample(report,state_path,('records',str(index),'sample','APH'),sample,specs)
            final=_load_json(record_state.get('final_path'))
            if not isinstance(final,dict):
                continue
            score_ref=(final.get('stage_receipts') or {}).get('score')
            if not isinstance(score_ref,dict):
                continue
            receipt=_load_json(score_ref.get('path'))
            if not isinstance(receipt,dict):
                continue
            score_path=Path(receipt.get('output_directory',''))/'check.json'
            score=_load_json(score_path)
            if isinstance(score,dict) and 'LEVEL2_per_class' in score:
                _replay_score_record(report,'sustained_admission',score_path,('LEVEL2_per_class',),score['LEVEL2_per_class'],LEVEL2_CLASS_KEYS,specs,consumed_level2_records)

def score_record_replay_roots(roots, root_labels=None, repo=None):
    repo=Path(__file__).resolve().parents[2] if repo is None else Path(repo)
    specs=_root_specs(roots,root_labels,repo)
    report={'roots':[label for _,label in specs],
            'inventory':{'files':0,'records':0,'shapes':{}},
            'text_mentions':{'json_files':0},
            'consumers':_score_consumer_template(),
            'populated_class_records':{'records':0,'accepted':0,'rejected':0},
            'rejections':[],
            'unconsumed_records':0,
            'unconsumed_malformed_records':0,
            'unconsumed_odd_records':[]}
    inventory=[]
    for root,_ in specs:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*.json')):
            try:
                if 'LEVEL2_per_class' in path.read_text(errors='replace'):
                    report['text_mentions']['json_files']+=1
            except OSError:
                pass
            entries=_record_references_in_file(path)
            if not entries:
                continue
            report['inventory']['files']+=1
            for json_path,record,parent in entries:
                inventory.append((path,json_path,record,parent))
                shape=_score_record_shape(record)
                report['inventory']['records']+=1
                report['inventory']['shapes'][shape]=report['inventory']['shapes'].get(shape,0)+1
                classes=_populated_record_classes(record,parent)
                if classes is not None:
                    report['populated_class_records']['records']+=1
                    try:
                        read_level2_per_class(record,classes=classes)
                    except ValueError as error:
                        report['populated_class_records']['rejected']+=1
                        report['rejections'].append({
                            'consumer':'populated_class_producer',
                            'path':_reported_path(path,specs),
                            'json_path':_json_path(json_path),
                            'classes':list(classes),
                            'reason':str(error),
                        })
                    else:
                        report['populated_class_records']['accepted']+=1
    consumed_level2_records=set()
    _replay_projection_scores(report,repo,specs,consumed_level2_records)
    _replay_fixed_batch_scores(report,repo,specs,consumed_level2_records)
    _replay_sustained_scores(report,repo,specs,consumed_level2_records)
    for path,json_path,record,parent in inventory:
        if (Path(path).resolve(),tuple(json_path)) in consumed_level2_records:
            continue
        report['unconsumed_records']+=1
        if _is_odd_score_record(record):
            report['unconsumed_malformed_records']+=1
            report['unconsumed_odd_records'].append({
                'path':_reported_path(path,specs),
                'json_path':_json_path(json_path),
                'shape':_score_record_shape(record),
                'producer':_producer_for_score_record(path,parent),
                'consumed_by_migrated_reader':False,
            })
    return report

def score_record_markdown_report(report):
    lines=[
        '# Strict score-record replay report',
        '',
        'Read-only roots:',
    ]
    lines.extend(f'- `{root}`' for root in report['roots'])
    lines.extend([
        '',
        '## Inventory',
        '',
        f"- JSON files mentioning `LEVEL2_per_class`: {report['text_mentions']['json_files']}",
        f"- Parsed JSON files containing `LEVEL2_per_class` records: {report['inventory']['files']}",
        f"- `LEVEL2_per_class` records: {report['inventory']['records']}",
        '',
        '### Shapes',
        '',
    ])
    for shape,count in sorted(report['inventory']['shapes'].items(),key=lambda item:(-item[1],item[0])):
        lines.append(f"- {count}: `{shape}`")
    lines.extend(['','## Consumer Replay',''])
    for consumer,data in report['consumers'].items():
        lines.extend([
            f"### {consumer}",
            '',
            f"- Class rule: {data['class_rule']}",
            f"- Records replayed: {data['records']}",
            f"- Accepted: {data['accepted']}",
            f"- Rejected: {data['rejected']}",
            '',
        ])
    lines.extend([
        '## Populated-Class Producer Compatibility',
        '',
        '- These are retained score records whose containing object has `groundtruth_by_class`; they are replayed with classes whose counts are greater than zero.',
        f"- Records replayed: {report['populated_class_records']['records']}",
        f"- Accepted: {report['populated_class_records']['accepted']}",
        f"- Rejected: {report['populated_class_records']['rejected']}",
        '',
        '## Consumed Rejections',
        '',
    ])
    if report['rejections']:
        for rejection in report['rejections']:
            lines.append(f"- `{rejection['consumer']}` `{rejection['path']}` `{rejection['json_path']}` classes={rejection['classes']}: {rejection['reason']}")
    else:
        lines.append('- None')
    lines.extend([
        '',
        '## Unconsumed Odd Records',
        '',
        f"- Unconsumed `LEVEL2_per_class` records: {report['unconsumed_records']}",
        f"- Unconsumed odd-shaped records: {report['unconsumed_malformed_records']}",
        '',
    ])
    if report['unconsumed_odd_records']:
        for entry in report['unconsumed_odd_records']:
            lines.append(f"- `{entry['path']}` `{entry['json_path']}`: {entry['shape']}; producer: {entry['producer']}; consumed by migrated reader: no")
    else:
        lines.append('- None')
    lines.extend([
        '',
        '## Compatibility Decision',
        '',
        '- Sustained admission, sustained contract and fixed-batch verifier require all four native LEVEL_2 classes because their retained inputs are all-class gates.',
        '- Evidence projection accepts populated-class records only when the consumer context names that populated set via `groundtruth_by_class`; all-class gate points still require all four classes.',
        '- Old mis-keyed range entries under `metrics` are tolerated here only because these migrated readers read `LEVEL2_per_class`, not the historical range rows.',
        '- The odd retained records above are not consumed by any migrated reader, so the score-record reader was not loosened for them.',
    ])
    return '\n'.join(lines)+'\n'

def write_score_record_report(report, output_dir):
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    (output/'score-record-replay.md').write_text(score_record_markdown_report(report))

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
    parser.add_argument('--score-records',action='store_true')
    parser.add_argument('--output',default=str(repo/'docs/strict-metrics'))
    parser.add_argument('roots',nargs='*',
                        default=[str(_CACHE_ROOT),str(repo/'autonomy/research')])
    args=parser.parse_args(argv)
    specs=_root_specs([Path(root) for root in args.roots],repo=repo)
    if args.score_records:
        report=score_record_replay_roots([root for root,_ in specs],[label for _,label in specs],repo=repo)
        write_score_record_report(report,args.output)
    else:
        report=replay_roots([root for root,_ in specs],[label for _,label in specs])
        write_report(report,args.output)
    return 1 if report['rejections'] else 0

if __name__=='__main__':
    raise SystemExit(main())
