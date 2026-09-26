#!/usr/bin/env python3
"""Single host dispatcher for the executable reconstruction pathway."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from contracts import ROOT, curriculum, module_by_id, sha256_file, validate_run_id, write_json
from reporting import aggregate_report
from reference_runner import run_reference
from runner import run_module
from validator import validate_report, validate_result


def cache_root() -> Path:
    configured = os.environ.get("SURFLO_PATHWAY_CACHE_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".cache" / "surflo" / "3d-pathway"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--emit-plan", action="store_true", help="print dispatch without executing")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    fetch = commands.add_parser("fetch")
    fetch.add_argument("--asset", action="append", dest="assets")
    listing = commands.add_parser("list")
    listing.add_argument("--json", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("--module", required=True)
    run.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    run.add_argument("--run-id")
    validate = commands.add_parser("validate")
    validate.add_argument("--module", required=True)
    validate.add_argument("--run-id", required=True)
    report = commands.add_parser("report")
    report.add_argument("--run-id", required=True)
    all_modules = commands.add_parser("all")
    all_modules.add_argument("--profile", choices=("smoke", "full"), default="full")
    all_modules.add_argument("--run-id")
    reference = commands.add_parser("reference")
    reference.add_argument(
        "--adapter",
        choices=("colmap-sfm", "colmap-mvs", "orb-slam", "depth-anything-v2", "neus-facto"),
        required=True,
    )
    reference.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    reference.add_argument("--run-id")
    return result


def dispatch_plan(args: argparse.Namespace) -> dict[str, object]:
    mode = "networked" if args.command in {"build", "fetch"} else "offline"
    plan: dict[str, object] = {"schema_version": 1, "command": args.command, "network_mode": mode}
    for name in ("adapter", "module", "profile", "run_id"):
        value = getattr(args, name, None)
        if value is not None:
            plan[name] = value
    if getattr(args, "assets", None):
        plan["assets"] = args.assets
    return plan


def list_modules(as_json: bool) -> None:
    modules = [
        {"id": item["id"], "slug": item["slug"], "title": item["title"], "inference": item["inference"]}
        for item in curriculum()["modules"]
    ]
    if as_json:
        print(json.dumps(modules, sort_keys=True))
    else:
        for item in modules:
            print(f"{item['id']}  {item['slug']:<42} {item['title']}")


def write_aggregate(root: Path, run_id: str, require_complete: bool = False) -> Path:
    validate_run_id(run_id)
    run_root = root / "runs" / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(f"unknown run: {run_id}")
    items = []
    for result_path in sorted(run_root.glob("[0-9][0-9]/result.json")):
        result = validate_result(result_path.parent, result_path.parent.name)
        items.append((module_by_id(result["module_id"]), result))
    if not items:
        raise ValueError(f"run has no module results: {run_id}")
    module_ids = [result["module_id"] for _, result in items]
    expected = [module["id"] for module in curriculum()["modules"]]
    complete = module_ids == expected
    if require_complete and not complete:
        raise ValueError(f"complete report requires modules 01..15; found {module_ids}")
    profiles = sorted({result["profile"] for _, result in items})
    path = run_root / "report.md"
    path.write_text(aggregate_report(run_id, items), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "module_ids": module_ids,
        "complete_curriculum": complete,
        "profiles": profiles,
        "measurement_kinds": sorted({result["measurement_kind"] for _, result in items}),
        "metric_families": ["geometry", "rendering", "generative"],
        "assumptions": ["Metrics remain separated by task family.", "Controlled fixtures are not third-party benchmark reproductions."],
        "failure_interpretations": {result["module_id"]: result.get("observations", []) for _, result in items},
        "source_ids": sorted({source for module, _ in items for source in module["sources"]}),
        "report_sha256": sha256_file(path),
    }
    write_json(run_root / "report.json", manifest)
    validate_report(run_root)
    return path


def execute(args: argparse.Namespace) -> int:
    if args.emit_plan:
        print(json.dumps(dispatch_plan(args), sort_keys=True))
        return 0
    if args.command == "list":
        list_modules(args.json)
        return 0
    if args.command == "build":
        return subprocess.call([str(ROOT / "insulas" / "build.sh")])
    if args.command == "fetch":
        command = [sys.executable, str(ROOT / "pipeline" / "fetch.py"), "--cache-root", str(cache_root())]
        for asset in args.assets or []:
            command.extend(["--asset", asset])
        return subprocess.call(command)
    if args.command == "run":
        run_id = args.run_id or time.strftime("pathway-%Y%m%d-%H%M%S", time.gmtime())
        validate_run_id(run_id)
        print(run_module(cache_root(), args.module, args.profile, run_id))
        return 0
    if args.command == "validate":
        validate_run_id(args.run_id)
        module = module_by_id(args.module)
        validate_result(cache_root() / "runs" / args.run_id / module["id"], module["id"])
        print(f"valid: {args.run_id}/{module['id']}")
        return 0
    if args.command == "report":
        print(write_aggregate(cache_root(), args.run_id))
        return 0
    if args.command == "reference":
        run_id = args.run_id or time.strftime("reference-%Y%m%d-%H%M%S", time.gmtime())
        print(run_reference(cache_root(), args.adapter, args.profile, run_id))
        return 0
    if args.command == "all":
        run_id = args.run_id or time.strftime("pathway-%Y%m%d-%H%M%S", time.gmtime())
        validate_run_id(run_id)
        root = cache_root()
        final = root / "runs" / run_id
        if final.exists():
            raise FileExistsError(f"run already exists: {final}")
        staging = root / "all-staging" / f"{run_id}.{uuid.uuid4().hex}"
        staging.mkdir(parents=True)
        try:
            env = os.environ.copy()
            env["SURFLO_PATHWAY_CACHE_ROOT"] = str(staging)
            for module in curriculum()["modules"]:
                subprocess.run(
                    [str(ROOT / "run.sh"), "run", "--module", module["id"], "--profile", args.profile, "--run-id", run_id],
                    cwd=ROOT.parent.parent,
                    env=env,
                    check=True,
                )
            write_aggregate(staging, run_id, require_complete=True)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging / "runs" / run_id, final)
            print(final / "report.md")
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(execute(parser().parse_args()))
    except (FileExistsError, FileNotFoundError, NotImplementedError, subprocess.CalledProcessError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
