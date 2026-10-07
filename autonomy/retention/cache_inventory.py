"""Freeze an exact native cache inventory from its independent admissions."""
import json
from pathlib import Path,PurePosixPath
from evidence.source_snapshot import file_sha256,require_regular_file

sha=file_sha256

def freeze_cache_inventory(root,admissions):
 root=Path(root)
 if root.is_symlink() or not root.is_dir():raise ValueError('regular cache root required')
 admissions=list(map(Path,admissions))
 if not admissions or len(set(admissions))!=len(admissions):raise ValueError('unique independent admissions required')
 expected={};parents={};receipts=set()
 for admission in admissions:
  try:require_regular_file(admission)
  except ValueError as error:raise ValueError('regular independent admission required') from error
  record=json.loads(admission.read_text());receipt=Path(record['receipt'])
  if not receipt.is_relative_to(root) or receipt.name!='receipt.json' or receipt in receipts:raise ValueError('unique cache-local admitted receipt required')
  try:require_regular_file(receipt)
  except ValueError as error:raise ValueError('unique cache-local admitted receipt required') from error
  if sha(receipt)!=record['receipt_sha256']:raise ValueError('original cache receipt changed')
  receipts.add(receipt);parents[str(admission)]=sha(admission)
  original=json.loads(receipt.read_text())
  if not original['artifacts']:raise ValueError('complete original payload admission required')
  for name,digest in original['artifacts'].items():
   relative=PurePosixPath(name)
   if relative.is_absolute() or '..' in relative.parts or str(relative)!=name:raise ValueError('unsafe original artifact path')
   path=receipt.parent/name
   try:require_regular_file(path)
   except ValueError as error:raise ValueError('original admitted cache payload changed') from error
   if sha(path)!=digest:raise ValueError('original admitted cache payload changed')
   key=str(path.relative_to(root))
   if key in expected:raise ValueError('duplicate cache artifact admission')
   expected[key]=digest
  expected[str(receipt.relative_to(root))]=sha(receipt)
 inventory={}
 for path in root.rglob('*'):
  if path.is_symlink():raise ValueError('cache symlink refused')
  if path.is_file():inventory[str(path.relative_to(root))]=sha(path)
 if inventory!=expected:raise ValueError('cache inventory differs from complete independent admissions')
 return {'source_sha256':inventory,'parent_receipts':parents}
