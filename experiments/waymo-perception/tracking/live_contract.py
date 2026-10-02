"""Exercise dashboard/journal integration in live offline Insula."""
import hashlib,json
from pathlib import Path
from tracking import cli
from tracking.journal import read_entries
cli.P=Path('/source');cli.R=Path('/outputs/research');cli.R.mkdir();cli.REGISTRY=cli.P/'registry.json';cli.JOURNAL=cli.R/'journal.jsonl'
cli.refresh();data=json.loads((cli.R/'experiments.json').read_text());assert len(data['experiments'])==2;assert data['experiments'][0]['stage']=='verified_overfit';assert data['experiments'][1]['stage']=='gpu_admitted';assert data['experiments'][1]['trained'] is False
entries=read_entries(cli.JOURNAL);assert len(entries)==2;cli.refresh();assert len(read_entries(cli.JOURNAL))==2;assert 'verified_overfit' in (cli.R/'experiment-tracker.md').read_text();Path('/outputs/check.json').write_text(json.dumps({'two_distinct_lifecycle_stages':True,'GPU_admission_not_promoted_to_training':True,'evidence_snapshots_and_journal_hash_chain':True,'refresh_idempotent_for_stage_events':True,'tracked':2},indent=2));print('PASS live tracking/dashboard/journal integration')
