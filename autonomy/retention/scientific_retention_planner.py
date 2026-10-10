"""Plan dry-run-first cleanup for scientific-processing children."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from evidence.source_snapshot import file_sha256
from resources.scientific_budget import SCIENTIFIC_WORKING_CAP_BYTES
from retention.publish_scientific_directory import (
    CACHE_ROOT,
    PACKAGE_ROOT,
    PROTECTED_NAMES,
    PROTECTED_PATTERNS,
    SCIENTIFIC_PROCESSING,
)


CLASS_PROTECTED = "protected"
CLASS_LIVE_REFERENCED = "live-referenced"
CLASS_RELEASED_LEFTOVERS = "released-with-leftovers"
CLASS_PUBLISHED_UNRELEASED = "published-but-not-released"
CLASS_UNPUBLISHED = "unpublished"
CLASS_STRAY_LOG = "stray-log"
RELEASE_NAMESPACE = "perception-closed-scientific-processing"


@dataclass(frozen=True)
class Reference:
    child: str
    path: Path
    kind: str


@dataclass(frozen=True)
class ReleaseEntry:
    path: Path
    sha256: str
    bytes: int
    receipt: Path


@dataclass(frozen=True)
class ChildPlan:
    name: str
    path: Path
    classification: str
    reason: str
    evidence: str
    bytes: int
    reclaimable_bytes: int
    projected_total_bytes: int
    release_command: str | None = None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def inode_unique_bytes(root: Path) -> int:
    root = Path(root)
    if root.is_symlink():
        raise ValueError("scientific payload entries must not be symlinks: " + str(root))
    if root.is_file():
        return root.stat().st_size
    if not root.is_dir():
        return 0
    seen: set[tuple[int, int]] = set()
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("scientific payload entries must not be symlinks: " + str(path))
        if not path.is_file():
            continue
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        if key not in seen:
            seen.add(key)
            total += stat.st_size
    return total


def _payload_bytes_excluding(root: Path, excluded: Iterable[Path]) -> int:
    root = Path(root)
    excluded_resolved = [Path(path).resolve(strict=False) for path in excluded]
    seen: set[tuple[int, int]] = set()
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("scientific payload entries must not be symlinks: " + str(path))
        if not path.is_file():
            continue
        resolved = path.resolve(strict=False)
        if any(resolved == candidate or _is_relative_to(resolved, candidate) for candidate in excluded_resolved):
            continue
        stat = path.stat()
        key = (stat.st_dev, stat.st_ino)
        if key not in seen:
            seen.add(key)
            total += stat.st_size
    return total


def _json_files(root: Path) -> Iterable[Path]:
    root = Path(root)
    if root.is_file() and root.suffix == ".json":
        yield root
    elif root.is_dir():
        yield from sorted(root.rglob("*.json"))


def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _strings(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _child_from_reference(value: str, scientific_processing: Path, children: set[str]) -> str | None:
    marker = "scientific-processing/"
    if marker in value:
        tail = value.split(marker, 1)[1].lstrip("/")
        name = tail.split("/", 1)[0]
        return name if name in children else None
    path = Path(value)
    if path.is_absolute():
        try:
            relative = path.relative_to(scientific_processing)
        except ValueError:
            return None
        parts = relative.parts
        return parts[0] if parts and parts[0] in children else None
    if value.startswith(marker):
        name = value[len(marker) :].lstrip("/").split("/", 1)[0]
        return name if name in children else None
    return None


def _child_from_run_id(run_id: str, children: set[str]) -> str | None:
    if run_id in children:
        return run_id
    matches = [name for name in children if run_id.startswith(name + "-") or run_id.startswith(name + "_")]
    return sorted(matches, key=len, reverse=True)[0] if matches else None


def _publication_child_from_receipt(receipt: Path, data, children: set[str]) -> str | None:
    parent = receipt.parent.name
    for prefix in ("hdfs-retention-", "blob-publication-"):
        if parent.startswith(prefix):
            child = _child_from_run_id(parent[len(prefix) :], children)
            if child is not None:
                return child
    for value in _strings(data):
        if not value.endswith("/manifest.json"):
            continue
        parts = value.split("/")
        if len(parts) >= 5 and parts[0] in {"runs", "checkpoints"}:
            child = _child_from_run_id(parts[2], children)
            if child is not None:
                return child
    return None


def _reference_kind(path: Path, cache_root: Path) -> str:
    parts = path.parts
    if path.name == "state.json" and "insula" in parts:
        return "state"
    if path.name.endswith("-admitted.json"):
        return "admission"
    if path.name in {"verified-publication.json", "release-completed.json"} and any(
        part.startswith("hdfs-retention-") or part.startswith("blob-publication-") for part in parts
    ):
        return "retention"
    if path.name in {"verified-publication.json", "release-completed.json"} and _is_relative_to(path.resolve(strict=False), cache_root.resolve(strict=False) / "insula"):
        return "retention"
    return "receipt"


def collect_references(scientific_processing: Path, receipt_roots: Sequence[Path], cache_root: Path) -> dict[str, list[Reference]]:
    children = {path.name for path in _children(scientific_processing)}
    references: dict[str, list[Reference]] = {name: [] for name in children}
    for root in receipt_roots:
        if Path(root).resolve(strict=False) == scientific_processing.resolve(strict=False) or _is_relative_to(
            Path(root).resolve(strict=False), scientific_processing.resolve(strict=False)
        ):
            continue
        for path in _json_files(Path(root)):
            data = _load_json(path)
            if data is None:
                continue
            kind = _reference_kind(path, cache_root)
            for value in _strings(data):
                child = _child_from_reference(value, scientific_processing, children)
                if child is not None:
                    references[child].append(Reference(child, path, kind))
                    break
    return references


def _children(scientific_processing: Path) -> list[Path]:
    root = Path(scientific_processing)
    if not root.is_dir():
        return []
    return sorted(root.iterdir(), key=lambda path: path.name)


def _is_protected(name: str) -> bool:
    return name in PROTECTED_NAMES or any(fnmatchcase(name, pattern) for pattern in PROTECTED_PATTERNS)


def _release_completed_files(receipt_roots: Sequence[Path]) -> list[Path]:
    found = []
    for root in receipt_roots:
        found.extend(path for path in _json_files(Path(root)) if path.name == "release-completed.json")
    return sorted(set(found))


def _verified_publication_files(receipt_roots: Sequence[Path]) -> list[Path]:
    found = []
    for root in receipt_roots:
        found.extend(path for path in _json_files(Path(root)) if path.name == "verified-publication.json")
    return sorted(set(found))


def _release_entries(data, receipt: Path) -> list[ReleaseEntry]:
    entries = []
    released = data.get("released", []) if isinstance(data, Mapping) else []
    if not isinstance(released, list):
        return []
    for entry in released:
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("local_path") or entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("bytes")
        if not isinstance(value, str) or not isinstance(digest, str) or len(digest) != 64 or type(size) is not int:
            continue
        entries.append(ReleaseEntry(Path(value), digest, size, receipt))
    return entries


def collect_release_entries(scientific_processing: Path, receipt_roots: Sequence[Path]) -> dict[str, list[ReleaseEntry]]:
    children = {path.name for path in _children(scientific_processing)}
    releases: dict[str, list[ReleaseEntry]] = {name: [] for name in children}
    for receipt in _release_completed_files(receipt_roots):
        data = _load_json(receipt)
        if data is None:
            continue
        verified = receipt.with_name("verified-publication.json")
        expected = data.get("publication_receipt_sha256") if isinstance(data, Mapping) else None
        if isinstance(expected, str) and verified.is_file() and file_sha256(verified) != expected:
            continue
        for entry in _release_entries(data, receipt):
            child = _child_for_path(entry.path, scientific_processing, children)
            if child is not None:
                releases[child].append(entry)
    return releases


def collect_publications(scientific_processing: Path, receipt_roots: Sequence[Path]) -> dict[str, list[Path]]:
    children = {path.name for path in _children(scientific_processing)}
    published: dict[str, list[Path]] = {name: [] for name in children}
    for receipt in _verified_publication_files(receipt_roots):
        data = _load_json(receipt)
        if data is None:
            continue
        child = _publication_child_from_receipt(receipt, data, children)
        if child is not None:
            published[child].append(receipt)
            continue
        for value in _strings(data):
            child = _child_from_reference(value, scientific_processing, children)
            if child is not None:
                published[child].append(receipt)
                break
    return published


def _child_for_path(path: Path, scientific_processing: Path, children: set[str]) -> str | None:
    try:
        relative = path.resolve(strict=False).relative_to(scientific_processing.resolve(strict=False))
    except ValueError:
        return None
    return relative.parts[0] if relative.parts and relative.parts[0] in children else None


def _first_path(paths: Iterable[Path]) -> str:
    return str(sorted(set(map(Path, paths)))[0])


def _release_command(path: Path, cache_root: Path) -> str:
    evidence = cache_root / "insula"
    return (
        "python3 -m retention.publish_scientific_directory "
        f"--case {path.name} --root {path} --hdfs-namespace {RELEASE_NAMESPACE} "
        f"--evidence {evidence} --release"
    )


def plan(
    *,
    scientific_processing: Path = SCIENTIFIC_PROCESSING,
    cache_root: Path = CACHE_ROOT,
    receipt_roots: Sequence[Path] | None = None,
    budget_bytes: int = SCIENTIFIC_WORKING_CAP_BYTES,
) -> list[ChildPlan]:
    del budget_bytes
    scientific_processing = Path(scientific_processing)
    cache_root = Path(cache_root)
    receipt_roots = tuple(receipt_roots or default_receipt_roots(cache_root))
    current_total = inode_unique_bytes(scientific_processing) if scientific_processing.is_dir() else 0
    references = collect_references(scientific_processing, receipt_roots, cache_root)
    release_entries = collect_release_entries(scientific_processing, receipt_roots)
    publications = collect_publications(scientific_processing, receipt_roots)
    plans = []
    for child in _children(scientific_processing):
        size = inode_unique_bytes(child)
        live_refs = [ref for ref in references.get(child.name, []) if ref.kind != "retention"]
        releases = release_entries.get(child.name, [])
        published = publications.get(child.name, [])
        if _is_protected(child.name):
            classification = CLASS_PROTECTED
            reason = "imported protected scientific-processing policy"
            evidence = "retention.publish_scientific_directory"
            reclaimable = 0
            release_command = None
        elif live_refs:
            classification = CLASS_LIVE_REFERENCED
            evidence_ref = sorted(live_refs, key=lambda ref: str(ref.path))[0]
            reason = evidence_ref.kind + " reference"
            evidence = str(evidence_ref.path)
            reclaimable = 0
            release_command = None
        elif releases:
            classification = CLASS_RELEASED_LEFTOVERS
            reason = "release-completed receipt exists"
            evidence = _first_path(entry.receipt for entry in releases)
            reclaimable = sum(entry.bytes for entry in releases if entry.path.exists())
            release_command = None
        elif published:
            classification = CLASS_PUBLISHED_UNRELEASED
            reason = "verified publication has no release-completed receipt"
            evidence = _first_path(published)
            reclaimable = 0
            release_command = _release_command(child, cache_root)
        elif child.is_file() and child.suffix == ".log":
            classification = CLASS_STRAY_LOG
            reason = "top-level log is not a scientific run"
            evidence = str(child)
            reclaimable = size
            release_command = None
        else:
            classification = CLASS_UNPUBLISHED
            reason = "no live reference or retention receipt found"
            evidence = "scan roots: " + ", ".join(str(root) for root in receipt_roots)
            reclaimable = 0
            release_command = None
        projected = current_total - reclaimable
        plans.append(
            ChildPlan(
                name=child.name,
                path=child,
                classification=classification,
                reason=reason,
                evidence=evidence,
                bytes=size,
                reclaimable_bytes=reclaimable,
                projected_total_bytes=max(projected, 0),
                release_command=release_command,
            )
        )
    return plans


def default_receipt_roots(cache_root: Path = CACHE_ROOT) -> tuple[Path, ...]:
    return (Path(cache_root) / "insula", PACKAGE_ROOT / "research")


def _eligible_delete_paths(child_plan: ChildPlan, releases: Sequence[ReleaseEntry]) -> list[Path]:
    if child_plan.classification == CLASS_STRAY_LOG:
        return [child_plan.path]
    if child_plan.classification != CLASS_RELEASED_LEFTOVERS:
        return []
    paths = []
    for entry in releases:
        if not entry.path.exists():
            continue
        if entry.path.stat().st_size != entry.bytes or file_sha256(entry.path) != entry.sha256:
            raise ValueError("released leftover digest differs: " + str(entry.path))
        paths.append(entry.path)
    return paths


def _require_apply_path(path: Path, scientific_processing: Path, evidence_roots: Sequence[Path]) -> None:
    resolved = path.resolve(strict=False)
    scientific_processing = Path(scientific_processing).resolve(strict=False)
    if resolved == scientific_processing or not _is_relative_to(resolved, scientific_processing):
        raise ValueError("refusing to delete outside scientific-processing: " + str(path))
    for evidence_root in evidence_roots:
        evidence = Path(evidence_root).resolve(strict=False)
        if resolved == evidence or _is_relative_to(resolved, evidence):
            raise ValueError("refusing to delete evidence root contents: " + str(path))


def apply_plan(
    plans: Sequence[ChildPlan],
    *,
    scientific_processing: Path = SCIENTIFIC_PROCESSING,
    cache_root: Path = CACHE_ROOT,
    receipt_roots: Sequence[Path] | None = None,
    receipt_dir: Path | None = None,
    lock_path: Path | None = None,
) -> Path:
    scientific_processing = Path(scientific_processing)
    cache_root = Path(cache_root)
    receipt_roots = tuple(receipt_roots or default_receipt_roots(cache_root))
    releases = collect_release_entries(scientific_processing, receipt_roots)
    references = collect_references(scientific_processing, receipt_roots, cache_root)
    child_names = {path.name for path in _children(scientific_processing)}
    if receipt_dir is None:
        receipt_dir = cache_root / "insula" / "scientific-retention-planner"
    receipt_dir = Path(receipt_dir)
    if receipt_dir.resolve(strict=False) == scientific_processing.resolve(strict=False) or _is_relative_to(
        receipt_dir.resolve(strict=False), scientific_processing.resolve(strict=False)
    ):
        raise ValueError("apply receipt must be outside scientific-processing")
    if lock_path is None:
        lock_path = cache_root / "insula" / "architecture-experiments.lock"
    from retention.sustained_controller_lock import acquire_experiment_lock

    deleted = []
    with acquire_experiment_lock(lock_path):
        for child_plan in plans:
            paths = _eligible_delete_paths(child_plan, releases.get(child_plan.name, []))
            if not paths:
                continue
            for path in paths:
                _require_apply_path(path, scientific_processing, receipt_roots + (receipt_dir,))
                child = _child_for_path(path, scientific_processing, child_names)
                if child is None:
                    raise ValueError("refusing to delete outside a direct scientific child: " + str(path))
                if _is_protected(child):
                    raise ValueError("refusing to delete protected scientific child: " + child)
                if any(ref.kind != "retention" for ref in references.get(child, [])):
                    raise ValueError("refusing to delete referenced scientific child: " + child)
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted.append({"path": str(path), "class": child_plan.classification})
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt = receipt_dir / ("retention-plan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "scientific_processing": str(scientific_processing),
                    "deleted": deleted,
                    "scope": "stray logs and digest-verified released leftovers only",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    return receipt


def summary(plans: Sequence[ChildPlan], *, total_bytes: int, budget_bytes: int = SCIENTIFIC_WORKING_CAP_BYTES, top: int = 20) -> str:
    counts: dict[str, int] = {}
    bytes_by_class: dict[str, int] = {}
    reclaimable = 0
    for child in plans:
        counts[child.classification] = counts.get(child.classification, 0) + 1
        bytes_by_class[child.classification] = bytes_by_class.get(child.classification, 0) + child.bytes
        reclaimable += child.reclaimable_bytes
    projected = max(total_bytes - reclaimable, 0)
    lines = [
        f"working_total_bytes={total_bytes} ({_human(total_bytes)})",
        f"working_cap_bytes={budget_bytes} ({_human(budget_bytes)})",
        f"projected_after_eligible_cleanup_bytes={projected} ({_human(projected)})",
        f"eligible_reclaimable_bytes={reclaimable} ({_human(reclaimable)})",
        "classes:",
    ]
    for name in sorted(counts):
        lines.append(f"  {name}: count={counts[name]} bytes={bytes_by_class[name]} ({_human(bytes_by_class[name])})")
    lines.append("top_entries:")
    for child in sorted(plans, key=lambda item: item.bytes, reverse=True)[:top]:
        line = (
            f"  {child.name}: class={child.classification} bytes={child.bytes} ({_human(child.bytes)}) "
            f"reclaimable={child.reclaimable_bytes} evidence={child.evidence} reason={child.reason}"
        )
        lines.append(line)
        if child.release_command:
            lines.append("    release_command=" + child.release_command)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--scientific-processing", type=Path, default=None)
    parser.add_argument("--receipt-root", type=Path, action="append")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--apply", action="store_true", help="delete eligible stray logs and released leftovers")
    parser.add_argument("--receipt-dir", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    scientific_processing = args.scientific_processing or args.cache_root / "scientific-processing"
    receipt_roots = tuple(args.receipt_root) if args.receipt_root else default_receipt_roots(args.cache_root)
    plans = plan(
        scientific_processing=scientific_processing,
        cache_root=args.cache_root,
        receipt_roots=receipt_roots,
    )
    total = inode_unique_bytes(scientific_processing) if Path(scientific_processing).is_dir() else 0
    print(summary(plans, total_bytes=total, top=args.top))
    if args.apply:
        receipt = apply_plan(
            plans,
            scientific_processing=scientific_processing,
            cache_root=args.cache_root,
            receipt_roots=receipt_roots,
            receipt_dir=args.receipt_dir,
        )
        print("apply_receipt=" + str(receipt), file=sys.stderr)
    else:
        print("dry run; pass --apply only after an explicit cleanup decision", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
