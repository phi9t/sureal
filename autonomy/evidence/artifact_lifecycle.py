"""Immutable artifact hashes and explicit transient release/supersession."""
from pathlib import Path
from evidence.source_snapshot import file_sha256

def admit_artifact(path,digest,releases,superseded,physical_path=None):
 p=Path(physical_path or path)
 if p.exists() and file_sha256(p)==digest:return 'retained immutable'
 if releases.get(str(path))==digest:return 'declared release'
 if digest in superseded:return 'declared supersession'
 raise ValueError(f'Undeclared artifact mutation/removal: {path}')

def load_release_records(path):
 import json
 p=Path(path)
 if not p.exists():return []
 ledger=json.loads(p.read_text())
 if ledger.get('released_only_after_exact_replay_and_all_native_and_literal_audits') is not True:raise ValueError('complete release evidence required')
 records=ledger['released']
 if not isinstance(records,list) or len({entry['path'] for entry in records})!=len(records):raise ValueError('unique release records required')
 return records
