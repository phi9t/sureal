#!/usr/bin/env python3
"""Create validated runs in staging directories and promote them atomically."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import tempfile


RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def begin_run(
    runs_root: Path, run_id: str, *, overwrite: bool
) -> tuple[Path, Path]:
    runs_root = Path(runs_root)
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"unsafe run id: {run_id!r}")
    runs_root.mkdir(parents=True, exist_ok=True)
    final = runs_root / run_id
    if final.exists() and not overwrite:
        raise FileExistsError(
            f"completed run already exists: {final}; pass --overwrite to replace it"
        )
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}.tmp-", dir=runs_root))
    return temporary, final


def promote_run(
    temporary: Path, final: Path, *, validated: bool, overwrite: bool
) -> None:
    temporary = Path(temporary)
    final = Path(final)
    if not validated:
        raise RuntimeError("refusing to promote a run before validation succeeds")
    if not temporary.is_dir():
        raise FileNotFoundError(f"staging run does not exist: {temporary}")
    if final.exists() and not overwrite:
        raise FileExistsError(f"completed run already exists: {final}")

    backup: Path | None = None
    if final.exists():
        backup = final.with_name(f".{final.name}.old-{os.getpid()}")
        if backup.exists():
            raise FileExistsError(f"promotion backup already exists: {backup}")
        final.rename(backup)
    try:
        temporary.rename(final)
    except Exception:
        if backup is not None and not final.exists():
            backup.rename(final)
        raise
    if backup is not None:
        shutil.rmtree(backup)
