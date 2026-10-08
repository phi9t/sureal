"""Publish one closed scientific-processing directory, then optionally release it."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from fnmatch import fnmatchcase
from pathlib import Path

from evidence.source_snapshot import (
    file_sha256,
    is_regular_file,
    require_regular_file,
    snapshot_target_and_materialize,
    verify_or_materialize_receipt_sources,
)
from insula.entry import launch_plan
from insula.runtime_identity import verify_rootfs
from resources.backend import resource_cpu_root_for
from resources.resource_archive import DEFAULT_LIMIT, create_archive, safe_name, verify_archive
from resources.resource_rehydrate import rehydrate_archive
from resources.resource_release_plan import release_plan
from retention.publisher_runtime import admitted_host_sources


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = Path.home() / ".cache/waystone/waymo-perception"
SCIENTIFIC_PROCESSING = CACHE_ROOT / "scientific-processing"
WAYSTONE_CLI = Path.home() / "workspace/waystone/scripts/waystone"
SNAPSHOT_TARGET = "//autonomy/retention:publish_scientific_directory"
REQUIRED_CHUNK_STAGES = [
    "create-live",
    "archive-put",
    "archive-get",
    "manifest-put",
    "manifest-get",
    "verify-live",
    "rehydrate-live",
]
REQUIRED_RELEASE_STAGES = REQUIRED_CHUNK_STAGES + [
    "independent",
    "release-plan",
    "release-completed",
]
PROTECTED_NAMES = frozenset(
    [
        "balanced16-native-v2",
        "balanced16-physical-v2",
        "balanced16-labels-v2",
        "cohort16-baseline-balanced20261002a",
        "balanced16-sustained-baseline-controller20261003a",
        "balanced16-camera-previews-v2",
        "balanced16-selection.candidate.json",
        "balanced16-sustained.candidate.json",
        "motion-current-geometry-audit-v3",
    ]
)
PROTECTED_PATTERNS = (
    "balanced16-sustained-*",
    "resource-retention-balanced16-sustained-baseline-controller20261003a-shared-*",
    "resource-retention-balanced16-sustained-*",
)
HOST_SOURCE_REQUIRED = (
    "retention/publish_scientific_directory.py",
    "retention/publisher_runtime.py",
    "resources/backend.py",
    "resources/resource_archive.py",
    "resources/resource_archive_cli.py",
    "resources/resource_rehydrate.py",
    "resources/resource_release_plan.py",
    "evidence/source_snapshot.py",
    "insula/entry.py",
    "insula/runtime_identity.py",
)
AUTHENTICATION_MARKERS = (
    "authentication",
    "authenticate",
    "authorization",
    "credential",
    "forbidden",
    "gss",
    "kerberos",
    "permission denied",
    "ticket",
    "token",
    "unauthorized",
)
MISSING_MARKERS = (
    "does not exist",
    "filenotfound",
    "file not found",
    "no such file",
    "not found",
    "not_exist",
)
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FOUND_ITEMS = re.compile(r"\bFound\s+([0-9]+)\s+items\b")


def _safe_component(value, what):
    if not isinstance(value, str) or not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"safe {what} required")
    return value


def _is_relative_to(path, parent):
    try:
        Path(path).relative_to(parent)
    except ValueError:
        return False
    return True


def _require_case_root(case, root, scientific_processing):
    case = _safe_component(case, "case")
    if case in PROTECTED_NAMES or any(fnmatchcase(case, pattern) for pattern in PROTECTED_PATTERNS):
        raise ValueError("protected scientific-processing entry: " + case)
    root = Path(root)
    scientific_processing = Path(scientific_processing)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular source directory required")
    if root.name != case or root.parent.resolve() != scientific_processing.resolve():
        raise ValueError("--root must be the named direct child of scientific-processing")
    return root, scientific_processing


def _require_evidence_root(evidence, scientific_processing):
    evidence = Path(evidence)
    scientific_processing = Path(scientific_processing).resolve()
    resolved = evidence.resolve(strict=False)
    if resolved == scientific_processing or _is_relative_to(resolved, scientific_processing):
        raise ValueError("--evidence must be outside scientific-processing")
    evidence.mkdir(parents=True, exist_ok=True)
    if evidence.is_symlink() or not evidence.is_dir():
        raise ValueError("regular evidence directory required")
    return evidence


def _line_names_uri(line, uri):
    stripped = line.strip()
    if not stripped or stripped.startswith("Found "):
        return False
    parts = stripped.split()
    return bool(parts and parts[-1] == uri)


def _hdfs_ls_indicates_existing_object(uri, exit_code, output):
    if exit_code == 0:
        counts = [int(match.group(1)) for match in FOUND_ITEMS.finditer(output)]
        if counts:
            return any(count >= 1 for count in counts)
        if any(_line_names_uri(line, uri) for line in output.splitlines()):
            return True
        raise RuntimeError("could not parse HDFS object preflight listing: " + uri)
    lowered = output.lower()
    if any(marker in lowered for marker in AUTHENTICATION_MARKERS):
        raise RuntimeError("could not prove HDFS object absence: " + uri)
    if any(marker in lowered for marker in MISSING_MARKERS):
        return False
    raise RuntimeError("could not prove HDFS object absence: " + uri)


def _source_inventory(root):
    records = []
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        safe_name(relative)
        if path.is_symlink():
            raise ValueError("regular source files without symlinks required")
        if path.is_dir():
            continue
        if not is_regular_file(path):
            raise ValueError("regular source files required")
        file = require_regular_file(path)
        records.append(
            {
                "path": relative,
                "bytes": file.stat().st_size,
                "sha256": file_sha256(file),
            }
        )
    if not records:
        raise ValueError("closed scientific directory must contain files")
    return records


def _chunks(records, max_bytes):
    chunks = []
    current = []
    size = 0
    for record in records:
        if record["bytes"] > max_bytes:
            raise ValueError("single source file exceeds archive bound")
        if current and size + record["bytes"] > max_bytes:
            chunks.append(current)
            current = []
            size = 0
        current.append(record)
        size += record["bytes"]
    if current:
        chunks.append(current)
    return chunks


def _freeze_host_sources(repository, destination):
    repository = Path(repository)
    if not all(is_regular_file(repository / name) for name in HOST_SOURCE_REQUIRED):
        raise ValueError("complete regular host source closure required")
    return snapshot_target_and_materialize(SNAPSHOT_TARGET, destination, repo_root=repository.parent)


def _validate_host_sources(repository, pins):
    required = (
        {"autonomy/" + name for name in HOST_SOURCE_REQUIRED}
        if pins.get("schema_version") == 2
        else set(HOST_SOURCE_REQUIRED)
    )
    if not required <= set(pins.get("source_pins", {})):
        raise ValueError("complete host execution source bindings required")
    return verify_or_materialize_receipt_sources(
        pins,
        pins["source_snapshot_root"],
        env_var="SUREAL_SOURCE_SNAPSHOT_STORE",
    )


def _admit_host_sources(receipt_path, current_package, destination):
    return admitted_host_sources(
        receipt_path,
        current_package,
        destination,
        _freeze_host_sources,
        _validate_host_sources,
    )


class WaystoneClient:
    def __init__(self, cli=WAYSTONE_CLI, *, auth_source="token-file", runner=None, before_run=None, tool_pins=None):
        if auth_source != "token-file":
            raise ValueError("--auth-source token-file is required")
        self.cli = Path(cli)
        self.auth_source = auth_source
        self.runner = runner
        self.before_run = before_run or (lambda: None)
        self.tool_pins = dict(tool_pins or {})

    def _command(self, arguments, timeout):
        auth = ["--auth-source", self.auth_source] if arguments[0] in {"ls", "put", "get"} else []
        return [
            str(self.cli),
            "--error-format",
            "json",
            "--command-timeout-secs",
            str(timeout),
            *auth,
            *arguments,
        ]

    def _run(self, arguments, label, evidence_dir, *, timeout=300, check=True):
        self.before_run()
        for path, digest in self.tool_pins.items():
            if file_sha256(path) != digest:
                raise ValueError("waystone tool changed")
        evidence_dir = Path(evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(arguments, timeout)
        if self.runner is not None:
            result = self.runner(command, capture_output=True, text=True, timeout=timeout + 5, check=False)
        else:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout + 5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                result = subprocess.CompletedProcess(command, 124, stdout, stderr)
            else:
                result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        log = evidence_dir / (label + ".log")
        log.write_text(str(result.stdout or "") + str(result.stderr or ""))
        if check and result.returncode != 0:
            raise RuntimeError("waystone command failed: " + label)
        return result.stdout or "", {
            "stage": label,
            "command": command,
            "exit_code": result.returncode,
            "log_sha256": file_sha256(log),
        }

    def layout_profile(self, evidence_dir):
        stdout, _ = self._run(["layout-profile", "--project", "sureal", "--json"], "layout", evidence_dir, timeout=30)
        layout = json.loads(stdout)
        if layout.get("project") != "sureal":
            raise ValueError("sureal waystone layout required")
        return layout

    def authenticated_read(self, uri, evidence_dir):
        _, receipt = self._run(["ls", uri], "authenticated-read", evidence_dir, timeout=30)
        return receipt

    def _exists(self, uri, evidence_dir, label):
        stdout, receipt = self._run(["ls", uri], label, evidence_dir, timeout=30, check=False)
        log = Path(evidence_dir) / (label + ".log")
        output = stdout
        if log.exists():
            output = (output + "\n" + log.read_text()).strip()
        return _hdfs_ls_indicates_existing_object(uri, receipt["exit_code"], output)

    def put_new(self, source, uri, stage, evidence_dir):
        if self._exists(uri, evidence_dir, stage + "-preflight"):
            raise FileExistsError("HDFS object already exists: " + uri)
        _, receipt = self._run(["put", "--mkdir-parents", str(source), uri], stage, evidence_dir)
        if receipt["exit_code"] != 0:
            raise RuntimeError("waystone put failed: " + stage)
        return receipt

    def get(self, uri, destination, stage, evidence_dir):
        _, receipt = self._run(["get", uri, str(destination)], stage, evidence_dir)
        if receipt["exit_code"] != 0:
            raise RuntimeError("waystone get failed: " + stage)
        return receipt


def _waystone_tool_pins(cli=WAYSTONE_CLI):
    cli = Path(cli)
    waystone = cli.parents[1]
    pins = {str(cli): file_sha256(cli)}
    for relative in [
        "rust/target/debug/waystone",
        "native/libhdfs_client/dist/lib/libhdfs_client.so",
        "native/libhdfs_client/dist/bin/hdfs.bin",
    ]:
        pins[str(waystone / relative)] = file_sha256(waystone / relative)
    return pins


class DirectArchiveRunner:
    def run(self, mode, input_dir, source_root, output_dir, evidence_dir, *, max_bytes):
        input_dir = Path(input_dir)
        source_root = Path(source_root)
        output_dir = Path(output_dir)
        evidence_dir = Path(evidence_dir)
        output_dir.mkdir(exist_ok=False)
        job = json.loads((input_dir / "job.json").read_text())
        if mode == "create":
            for name, digest in job["source_sha256"].items():
                if file_sha256(source_root / name) != digest:
                    raise ValueError("source payload differs")
            manifest = create_archive(source_root, job["source_sha256"], output_dir / "archive.tar.gz", max_bytes=max_bytes)
            (output_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2))
            check = verify_archive(output_dir / "archive.tar.gz", manifest, max_bytes=max_bytes)
        elif mode in {"verify", "rehydrate"}:
            if file_sha256(source_root / "manifest.json") != job["manifest_sha256"]:
                raise ValueError("manifest readback differs")
            manifest = json.loads((source_root / "manifest.json").read_text())
            check = verify_archive(source_root / "archive.tar.gz", manifest, max_bytes=max_bytes)
            if mode == "rehydrate":
                check = rehydrate_archive(
                    source_root / "archive.tar.gz",
                    manifest,
                    output_dir / "restored",
                    max_bytes=max_bytes,
                )
        else:
            raise ValueError("unknown archive operation")
        (output_dir / "check.json").write_text(json.dumps(check, indent=2))
        (output_dir / "live.log").write_text("PASS archive " + mode + "\n")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_dir / "check.json", evidence_dir / "check.json")
        shutil.copyfile(output_dir / "live.log", evidence_dir / "live.log")
        return {
            "stage": {"create": "create-live", "verify": "verify-live", "rehydrate": "rehydrate-live"}[mode],
            "command": ["python", "/experiment/resources/resource_archive_cli.py", mode],
            "exit_code": 0,
            "validation": check,
            "artifacts": {str(path): file_sha256(path) for path in sorted(evidence_dir.iterdir())},
        }


class InsulaArchiveRunner:
    def __init__(self, rootfs, source_tree, source_pins, validate_sources):
        self.rootfs = Path(rootfs)
        self.source_tree = Path(source_tree)
        self.source_pins = dict(source_pins)
        self.validate_sources = validate_sources

    def run(self, mode, input_dir, source_root, output_dir, evidence_dir, *, max_bytes):
        del max_bytes
        self.validate_sources()
        input_dir = Path(input_dir)
        source_root = Path(source_root)
        output_dir = Path(output_dir)
        evidence_dir = Path(evidence_dir)
        output_dir.mkdir(exist_ok=False)
        command = launch_plan(
            self.rootfs,
            self.source_tree,
            source_root,
            output_dir,
            ["python", "/experiment/resources/resource_archive_cli.py", mode],
        )
        separator = command.index("--")
        command[separator:separator] = ["--ro-bind", str(input_dir), "/tmp/inputs"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output_dir / "live.log").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise RuntimeError("live archive operation failed: " + str(output_dir / "live.log"))
        for path, digest in self.source_pins.items():
            if file_sha256(path) != digest:
                raise ValueError("staged source changed")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output_dir / "check.json", evidence_dir / "check.json")
        shutil.copyfile(output_dir / "live.log", evidence_dir / "live.log")
        return {
            "stage": {"create": "create-live", "verify": "verify-live", "rehydrate": "rehydrate-live"}[mode],
            "command": command,
            "exit_code": 0,
            "validation": json.loads((output_dir / "check.json").read_text()),
            "artifacts": {str(path): file_sha256(path) for path in sorted(evidence_dir.iterdir())},
        }


class InsulaIndependentRunner:
    def __init__(self, rootfs, source_tree, source_pins, validate_sources):
        self.rootfs = Path(rootfs)
        self.source_tree = Path(source_tree)
        self.source_pins = dict(source_pins)
        self.validate_sources = validate_sources

    def run(self, source_root, chunks, output_dir, *, max_bytes):
        self.validate_sources()
        output_dir = Path(output_dir)
        input_dir = output_dir.parent / "independent-input"
        input_dir.mkdir(exist_ok=False)
        chunk_root = input_dir / "chunks"
        chunk_root.mkdir()
        for index, chunk in enumerate(chunks):
            target = chunk_root / str(index)
            target.mkdir()
            shutil.copyfile(chunk["downloaded_archive"], target / "archive.tar.gz")
            (target / "manifest.json").write_text(json.dumps(chunk["manifest"], sort_keys=True, indent=2))
        (input_dir / "job.json").write_text(
            json.dumps({"chunks": len(chunks), "max_bytes": max_bytes}, sort_keys=True)
        )
        output_dir.mkdir(exist_ok=False)
        command = launch_plan(
            self.rootfs,
            self.source_tree,
            source_root,
            output_dir,
            ["python", "/experiment/retention/publish_scientific_directory.py", "--independent-audit"],
        )
        separator = command.index("--")
        command[separator:separator] = [
            "--ro-bind",
            str(input_dir),
            "/tmp/inputs",
            "--setenv",
            "PYTHONPATH",
            "/experiment",
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (output_dir / "live.log").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            raise RuntimeError("independent scientific directory audit failed: " + str(output_dir / "live.log"))
        for path, digest in self.source_pins.items():
            if file_sha256(path) != digest:
                raise ValueError("staged source changed")
        return {
            "stage": "independent",
            "command": command,
            "exit_code": 0,
            "validation": json.loads((output_dir / "check.json").read_text()),
            "artifacts": {str(path): file_sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
            "inputs": {str(path): file_sha256(path) for path in sorted(input_dir.rglob("*")) if path.is_file()},
        }

    def __call__(self, source_root, chunks, output_dir, *, max_bytes):
        return self.run(source_root, chunks, output_dir, max_bytes=max_bytes)


def _default_live_runners(run_dir, cache_root, host_pins, admitted_package):
    source = run_dir / "source"
    source.mkdir()
    for folder in ("resources", "evidence", "insula", "retention"):
        shutil.copytree(admitted_package / folder, source / folder, ignore=shutil.ignore_patterns("__pycache__"))
    source_pins = {str(path): file_sha256(path) for path in sorted(source.rglob("*")) if path.is_file()}
    rootfs = resource_cpu_root_for(None, cache_root)
    runtime = json.loads(Path(str(rootfs) + ".lock.json").read_text())
    verify_rootfs(rootfs, runtime["rootfs_sha256"])

    def validate_sources():
        _validate_host_sources(admitted_package, host_pins)

    return (
        InsulaArchiveRunner(rootfs, source, source_pins, validate_sources),
        InsulaIndependentRunner(rootfs, source, source_pins, validate_sources),
        runtime,
        source_pins,
    )


def _independent_restore(source_root, chunks, output_dir, *, max_bytes):
    output_dir = Path(output_dir)
    restored = output_dir / "restored"
    restored.mkdir(parents=True, exist_ok=False)
    for index, chunk in enumerate(chunks):
        destination = restored / str(index)
        rehydrate_archive(
            chunk["downloaded_archive"],
            chunk["manifest"],
            destination,
            max_bytes=max_bytes,
        )
    source = {record["path"]: record for record in _source_inventory(source_root)}
    recovered = {}
    for path in sorted(restored.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink() or not is_regular_file(path):
            raise ValueError("independent restore contains nonregular file")
        relative = path.relative_to(restored).as_posix()
        _, member = relative.split("/", 1)
        recovered[member] = {
            "path": member,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    if recovered != source:
        raise ValueError("independent restored inventory differs")
    check = {
        "exact_restored_inventory": True,
        "members": len(recovered),
        "payload_bytes": sum(record["bytes"] for record in recovered.values()),
    }
    (output_dir / "check.json").write_text(json.dumps(check, indent=2))
    (output_dir / "live.log").write_text("PASS independent scientific directory retention\n")
    return {
        "stage": "independent",
        "command": ["python", "-m", "retention.publish_scientific_directory", "independent"],
        "exit_code": 0,
        "validation": check,
        "artifacts": {str(path): file_sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
    }


def _independent_audit_cli():
    input_dir = Path("/tmp/inputs")
    job = json.loads((input_dir / "job.json").read_text())
    chunks = []
    for index in range(job["chunks"]):
        chunk_dir = input_dir / "chunks" / str(index)
        chunks.append(
            {
                "downloaded_archive": chunk_dir / "archive.tar.gz",
                "manifest": json.loads((chunk_dir / "manifest.json").read_text()),
            }
        )
    _independent_restore("/source", chunks, "/outputs", max_bytes=job["max_bytes"])
    print("PASS independent scientific directory retention", flush=True)


def _safe_release(root, plan):
    root = Path(root).resolve()
    verified = []
    for entry in plan:
        path = Path(entry["local_path"])
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError("release plan path escapes --root")
        file = require_regular_file(path)
        if file.stat().st_size != entry["bytes"] or file_sha256(file) != entry["sha256"]:
            raise ValueError("release plan source changed")
        verified.append((file, entry))
    for file, _ in verified:
        file.unlink()
    return [entry for _, entry in verified]


def publish(
    *,
    case,
    root,
    hdfs_namespace,
    evidence,
    host_source_receipt=None,
    auth_source="token-file",
    release=False,
    scientific_processing=SCIENTIFIC_PROCESSING,
    waystone=None,
    archive_runner=None,
    independent_runner=None,
    host_source_admitter=_admit_host_sources,
    release_planner=release_plan,
    identifier=None,
    max_bytes=DEFAULT_LIMIT,
):
    if auth_source != "token-file":
        raise ValueError("--auth-source token-file is required")
    hdfs_namespace = _safe_component(hdfs_namespace, "HDFS namespace")
    root, scientific_processing = _require_case_root(case, root, scientific_processing)
    evidence = _require_evidence_root(evidence, scientific_processing)
    inventory = _source_inventory(root)
    identifier = identifier or (case + "-" + uuid.uuid4().hex)
    run_dir = evidence / ("hdfs-retention-" + identifier)
    run_dir.mkdir(exist_ok=False)
    host_pins, admitted_package = host_source_admitter(host_source_receipt, PACKAGE_ROOT, run_dir / "host-source")
    waystone_tool_pins = {}
    if waystone is None:
        waystone_tool_pins = _waystone_tool_pins()

        def validate_external():
            _validate_host_sources(admitted_package, host_pins)

        waystone = WaystoneClient(auth_source=auth_source, before_run=validate_external, tool_pins=waystone_tool_pins)
    runtime_lock = {"mode": "direct-archive-runner"}
    source_pins = {}
    if archive_runner is None:
        archive_runner, independent_runner, runtime_lock, source_pins = _default_live_runners(
            run_dir,
            scientific_processing.parent,
            host_pins,
            admitted_package,
        )
    elif independent_runner is None:
        independent_runner = _independent_restore
    layout = waystone.layout_profile(run_dir)
    remote = layout["paths"]["runs"].rstrip("/") + "/" + hdfs_namespace + "/" + identifier
    authenticated_read = waystone.authenticated_read(layout["project_root"], run_dir)
    (run_dir / "expected.json").write_text(json.dumps({"members": inventory}, sort_keys=True, indent=2))
    publication = {
        "schema_version": 1,
        "case": case,
        "root": str(root),
        "hdfs_namespace": hdfs_namespace,
        "closure_complete": True,
        "source_admission_complete": True,
        "host_source_pins": host_pins,
        "source_inventory_sha256": file_sha256(run_dir / "expected.json"),
        "manifest_readback_exact": False,
        "runtime_lock": runtime_lock,
        "source_pins": source_pins,
        "waystone_tool_sha256": waystone_tool_pins,
        "authenticated_read": authenticated_read,
        "chunks": [],
        "stage_receipts": [],
    }
    local_chunks = []
    for index, records in enumerate(_chunks(inventory, max_bytes)):
        chunk_dir = run_dir / str(index)
        inputs = chunk_dir / "input"
        inputs.mkdir(parents=True)
        job = {"source_sha256": {record["path"]: record["sha256"] for record in records}, "max_bytes": max_bytes}
        (inputs / "job.json").write_text(json.dumps(job, sort_keys=True))
        packed = chunk_dir / "packed"
        checks = [archive_runner.run("create", inputs, root, packed, chunk_dir / "create-proof", max_bytes=max_bytes)]
        manifest = json.loads((packed / "manifest.json").read_text())
        digest = manifest["archive_sha256"]
        uri = remote + "/" + digest
        download = chunk_dir / "download"
        download.mkdir()
        checks.append(waystone.put_new(packed / "archive.tar.gz", uri + "/archive.tar.gz", "archive-put", chunk_dir))
        checks.append(waystone.get(uri + "/archive.tar.gz", download / "archive.tar.gz", "archive-get", chunk_dir))
        if file_sha256(download / "archive.tar.gz") != digest:
            raise ValueError("archive readback differs")
        checks.append(waystone.put_new(packed / "manifest.json", uri + "/manifest.json", "manifest-put", chunk_dir))
        checks.append(waystone.get(uri + "/manifest.json", download / "manifest.json", "manifest-get", chunk_dir))
        manifest_sha = file_sha256(packed / "manifest.json")
        if file_sha256(download / "manifest.json") != manifest_sha:
            raise ValueError("manifest readback differs")
        job["manifest_sha256"] = manifest_sha
        (inputs / "job.json").write_text(json.dumps(job, sort_keys=True))
        checks.append(archive_runner.run("verify", inputs, download, chunk_dir / "verify", chunk_dir / "verify-proof", max_bytes=max_bytes))
        checks.append(
            archive_runner.run("rehydrate", inputs, download, chunk_dir / "rehydrate", chunk_dir / "rehydrate-proof", max_bytes=max_bytes)
        )
        if [check["stage"] for check in checks] != REQUIRED_CHUNK_STAGES:
            raise ValueError("unexpected chunk stage order")
        chunk = {
            "archive_hdfs_uri": uri + "/archive.tar.gz",
            "manifest_hdfs_uri": uri + "/manifest.json",
            "manifest_sha256": manifest_sha,
            "manifest": manifest,
            "checks": checks,
        }
        publication["chunks"].append(chunk)
        local_chunks.append({"downloaded_archive": download / "archive.tar.gz", "manifest": manifest})
        (run_dir / "in-progress.json").write_text(json.dumps(publication, indent=2))
    publication["manifest_readback_exact"] = True
    if release:
        publication["stage_receipts"].append(independent_runner(root, local_chunks, run_dir / "independent", max_bytes=max_bytes))
        plan = release_planner(root, publication)
        publication["release_plan"] = plan
        publication["stage_receipts"].append(
            {"stage": "release-plan", "command": ["resources.resource_release_plan.release_plan", str(root)], "exit_code": 0, "planned_count": len(plan)}
        )
        receipt = run_dir / "verified-publication.json"
        receipt.write_text(json.dumps(publication, indent=2))
        released = _safe_release(root, plan)
        completed = {
            "publication_receipt_sha256": file_sha256(receipt),
            "released_count": len(released),
            "released": released,
        }
        completed_path = run_dir / "release-completed.json"
        completed_path.write_text(json.dumps(completed, indent=2))
        publication["stage_receipts"].append(
            {
                "stage": "release-completed",
                "command": ["unlink", "release-plan-paths-only"],
                "exit_code": 0,
                "release_completed_sha256": file_sha256(completed_path),
            }
        )
    receipt = run_dir / "verified-publication.json"
    receipt.write_text(json.dumps(publication, indent=2))
    print("ADMITTED HDFS scientific directory retention", receipt, "local release", release, flush=True)
    return publication


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--independent-audit"]:
        _independent_audit_cli()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--hdfs-namespace", required=True)
    parser.add_argument("--auth-source", default="token-file", choices=["token-file"])
    parser.add_argument("--host-source-receipt", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args(argv)
    publish(
        case=args.case,
        root=args.root,
        hdfs_namespace=args.hdfs_namespace,
        evidence=args.evidence,
        auth_source=args.auth_source,
        host_source_receipt=args.host_source_receipt,
        release=args.release,
    )


if __name__ == "__main__":
    main()
