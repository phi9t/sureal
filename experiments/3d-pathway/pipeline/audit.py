#!/usr/bin/env python3
"""Audit source metadata, survey citations, terminology, and local asset locks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

from contracts import ROOT, load_json, sha256_file


CITATION = re.compile(r"\[([a-z0-9][a-z0-9-]*)\]\((https://[^)]+)\)")


def audit_text(text: str, known_sources: dict[str, str], forbidden_patterns: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for source_id, url in CITATION.findall(text):
        if source_id not in known_sources:
            errors.append(f"unknown citation: {source_id}")
        elif known_sources[source_id] != url:
            errors.append(f"citation URL mismatch for {source_id}: {url}")
    lowered = text.lower()
    for pattern in forbidden_patterns:
        if pattern.lower() in lowered:
            errors.append(f"forbidden terminology: {pattern}")
    return errors


def _online_check(url: str) -> str | None:
    try:
        request = Request(url, headers={"User-Agent": "surflo-pathway-audit/1"})
        with urlopen(request, timeout=20) as response:
            if response.status >= 400:
                return f"HTTP {response.status}: {url}"
    except Exception as error:  # network errors are reported, never hidden
        return f"unreachable source {url}: {type(error).__name__}: {error}"
    return None


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _image_lock_errors(name: str, lock: dict[str, str], dockerfile_text: str) -> list[str]:
    errors: list[str] = []
    image_refs = []
    for line in dockerfile_text.splitlines():
        match = re.match(r"^FROM\s+(\S+)", line, flags=re.IGNORECASE)
        if match:
            image_refs.append(match.group(1))
    expected_base = f"{lock['base_image']}@sha256:{lock['base_image_digest']}"
    if not image_refs or image_refs[0] != expected_base:
        errors.append(f"Insula base image lock mismatch: {name}")
    runtime_keys = {"runtime_image", "runtime_image_digest"}
    present_runtime_keys = runtime_keys & set(lock)
    if present_runtime_keys and present_runtime_keys != runtime_keys:
        errors.append(f"Insula runtime image lock is incomplete: {name}")
    elif present_runtime_keys:
        expected_runtime = f"{lock['runtime_image']}@sha256:{lock['runtime_image_digest']}"
        if expected_runtime not in image_refs[1:]:
            errors.append(f"Insula runtime image lock mismatch: {name}")
    source_commit = lock.get("colmap_source_commit")
    if source_commit and not re.search(
        rf"^ARG\s+COLMAP_GIT_COMMIT={re.escape(source_commit)}$",
        dockerfile_text,
        flags=re.MULTILINE,
    ):
        errors.append(f"Insula COLMAP source lock mismatch: {name}")
    return errors


def _crossref_check(source: dict[str, object]) -> str | None:
    url = str(source["primary_url"])
    prefix = "https://doi.org/"
    if not url.startswith(prefix):
        return None
    try:
        request = Request(
            f"https://api.crossref.org/works/{quote(url.removeprefix(prefix), safe='')}",
            headers={"User-Agent": "surflo-pathway-audit/1"},
        )
        with urlopen(request, timeout=20) as response:
            message = json.load(response)["message"]
        remote_title = " ".join(message.get("title", []))
        if _normalized(str(source["title"])) != _normalized(remote_title):
            return f"Crossref title mismatch: registry={source['title']!r}, remote={remote_title!r}"
        remote_surnames = {_normalized(item.get("family", "")) for item in message.get("author", [])}
        registry_surnames = {_normalized(str(name).split()[-1]) for name in source["authors"]}  # type: ignore[index]
        if not registry_surnames <= remote_surnames:
            return f"Crossref author mismatch: missing {sorted(registry_surnames - remote_surnames)}"
    except Exception as error:
        return f"Crossref metadata unavailable: {type(error).__name__}: {error}"
    return None


def audit(online: bool) -> dict[str, object]:
    errors: list[str] = []
    curriculum = load_json(ROOT / "curriculum.json")
    registry = load_json(ROOT / "sources.json")
    assets = load_json(ROOT / "assets.lock.json")
    terminology = load_json(ROOT / "terminology.json")
    survey_path = ROOT.parent.parent / "docs" / "3d-reconstruction-pathway.md"
    if not survey_path.is_file():
        errors.append(f"missing survey: {survey_path}")
        survey = ""
    else:
        survey = survey_path.read_text(encoding="utf-8")

    sources = registry.get("sources", [])
    source_ids = [item.get("id") for item in sources]
    if len(source_ids) != len(set(source_ids)):
        errors.append("source IDs are not unique")
    known: dict[str, str] = {}
    for source in sources:
        source_id = source.get("id")
        missing = [key for key in ("id", "title", "authors", "year", "venue", "primary_url", "themes", "claims") if not source.get(key)]
        if missing:
            errors.append(f"source {source_id or '<missing>'} missing {missing}")
            continue
        if source["year"] > 2026:
            errors.append(f"source after cutoff year: {source_id}")
        if not source["primary_url"].startswith("https://"):
            errors.append(f"non-HTTPS primary URL: {source_id}")
        known[source_id] = source["primary_url"]
    caveats = " ".join(item.get("credit_caveat", "") for item in sources).lower()
    for history in ("bundle adjustment", "splatting"):
        if history not in caveats:
            errors.append(f"missing historical credit caveat: {history}")

    modules = curriculum.get("modules", [])
    if [item.get("id") for item in modules] != [f"{index:02d}" for index in range(1, 16)]:
        errors.append("curriculum module IDs are not exactly 01..15")
    for module in modules:
        for source_id in module.get("sources", []):
            if source_id not in known:
                errors.append(f"module {module.get('id')} references unknown source {source_id}")
            elif f"[{source_id}]({known[source_id]})" not in survey:
                errors.append(f"module {module.get('id')} source absent from survey: {source_id}")

    forbidden = [pattern for guardrail in terminology["guardrails"] for pattern in guardrail["forbidden_patterns"]]
    errors.extend(audit_text(survey, known, forbidden))

    for asset in assets.get("assets", []):
        if not re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", "")):
            errors.append(f"invalid SHA-256 for asset {asset.get('id')}")
            continue
        if asset["mode"] in {"generated", "repository"}:
            path = (ROOT / asset["source"]).resolve()
            if not path.is_file():
                errors.append(f"missing local asset {asset['id']}: {path}")
            elif sha256_file(path) != asset["sha256"]:
                errors.append(f"local asset hash mismatch: {asset['id']}")
        elif asset["mode"] == "download":
            for key in ("digest_status", "archive_format", "extraction", "consumers"):
                if not asset.get(key):
                    errors.append(f"download asset {asset['id']} missing {key}")

    locks = load_json(ROOT / "insulas" / "locks.json")["insulas"]
    for name, lock in locks.items():
        dockerfile = ROOT / "insulas" / name / "Dockerfile"
        if not dockerfile.is_file() or sha256_file(dockerfile) != lock["dockerfile_sha256"]:
            errors.append(f"Insula Dockerfile hash mismatch: {name}")
            continue
        errors.extend(_image_lock_errors(name, lock, dockerfile.read_text(encoding="utf-8")))

    adapters = load_json(ROOT / "reference-adapters.json").get("adapters", [])
    if not adapters:
        errors.append("reference adapter registry is empty")
    for adapter in adapters:
        if adapter.get("status") not in {"landed", "not_landed"}:
            errors.append(f"invalid reference adapter status: {adapter.get('id')}")
        if adapter.get("status") == "landed" and not adapter.get("command"):
            errors.append(f"landed reference adapter lacks a command: {adapter.get('id')}")

    if online:
        for source_id, url in known.items():
            issue = _online_check(url)
            if issue:
                errors.append(f"{source_id}: {issue}")
            source = next(item for item in sources if item["id"] == source_id)
            metadata_issue = _crossref_check(source)
            if metadata_issue:
                errors.append(f"{source_id}: {metadata_issue}")
        for asset in assets.get("assets", []):
            if asset["mode"] == "download":
                issue = _online_check(asset["source"])
                if issue:
                    errors.append(f"asset {asset['id']}: {issue}")

    return {
        "schema_version": 1,
        "mode": "online" if online else "offline",
        "modules": len(modules),
        "sources": len(sources),
        "assets": len(assets.get("assets", [])),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--online", action="store_true")
    args = parser.parse_args()
    result = audit(online=args.online)
    print(json.dumps(result, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
