"""Runtime source receipt helpers for retention publishers."""
import json,shutil
from pathlib import Path
from evidence.source_snapshot import read_receipt,source_snapshot_member_path,source_snapshot_package_root


def admitted_host_sources(receipt_path,current_package,destination,freeze_host_sources,validate_host_sources):
 current_package=Path(current_package)
 if receipt_path is None:
  receipt=freeze_host_sources(current_package,destination)
  return receipt,current_package
 receipt=read_receipt(Path(receipt_path))
 if not isinstance(receipt,dict):raise ValueError('host source receipt object required')
 validate_host_sources(current_package,receipt)
 package=source_snapshot_package_root(receipt)
 if package.resolve()!=current_package.resolve():raise ValueError('publisher must run from admitted host source package root')
 return receipt,package


def stage_audit_source(receipt,destination_root,audit_relative):
 source=source_snapshot_member_path(receipt,audit_relative)
 destination=Path(destination_root)/audit_relative
 destination.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(source,destination)
 return destination
