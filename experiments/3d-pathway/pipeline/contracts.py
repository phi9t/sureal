"""Shared, dependency-light contracts for the 3D pathway labs."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_FILES = (
    "assets.lock.json", "curriculum.json", "reference-adapters.json", "result.schema.json",
    "shared-scene.json", "sources.json", "terminology.json",
)
IMPLEMENTATION_FILES = (
    "pipeline/cli.py", "pipeline/contracts.py", "pipeline/controlled_suite.py", "pipeline/dynamic.py", "pipeline/generative.py",
    "pipeline/labs.py", "pipeline/math3d.py", "pipeline/reporting.py", "pipeline/runner.py",
    "pipeline/surflo_endpoint.py", "pipeline/validator.py",
)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json(value))


def ensure_finite(value: Any, location: str = "root") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite number at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            ensure_finite(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            ensure_finite(child, f"{location}[{index}]")


def curriculum() -> dict[str, Any]:
    return load_json(ROOT / "curriculum.json")


def reference_adapter_name(record: dict[str, Any]) -> str:
    """Return the dispatcher name declared by one registry record."""
    command = str(record.get("command", ""))
    match = re.search(r"(?:^|\s)--adapter\s+([a-z0-9-]+)(?:\s|$)", command)
    if match is None:
        raise ValueError(f"reference adapter command has no --adapter name: {record.get('id')}")
    return match.group(1)


def reference_adapters(*, landed_only: bool = False) -> list[dict[str, Any]]:
    records = load_json(ROOT / "reference-adapters.json").get("adapters", [])
    if not isinstance(records, list):
        raise ValueError("reference adapter registry is malformed")
    selected = [
        record
        for record in records
        if isinstance(record, dict)
        and (not landed_only or record.get("status") == "landed")
    ]
    names = [reference_adapter_name(record) for record in selected]
    if len(names) != len(set(names)):
        raise ValueError("reference adapter dispatcher names are not unique")
    return selected


def landed_reference_adapter_names() -> list[str]:
    return [reference_adapter_name(record) for record in reference_adapters(landed_only=True)]


def full_acceptance_status(
    module_ids: list[str],
    expected_module_ids: list[str],
    module_profiles: list[str],
    reference_names: list[str],
    expected_reference_names: list[str],
    reference_profiles: list[str],
) -> bool:
    """Return true only for the complete, all-full module and reference suite."""
    return (
        module_ids == expected_module_ids
        and module_profiles == ["full"]
        and reference_names == expected_reference_names
        and reference_profiles == ["full"]
    )


def reference_adapter_by_name(adapter: str) -> dict[str, Any]:
    for record in reference_adapters():
        if reference_adapter_name(record) == adapter:
            return record
    raise ValueError(f"unknown reference adapter: {adapter}")


def module_by_id(module_id: str) -> dict[str, Any]:
    normalized = f"{int(module_id):02d}" if module_id.isdigit() else module_id
    for module in curriculum()["modules"]:
        if module["id"] == normalized or module["slug"] == module_id:
            return module
    raise ValueError(f"unknown module: {module_id}")


def validate_run_id(run_id: str) -> str:
    """Accept a portable single path component and reject traversal outright."""
    if run_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run ID must be one safe path component (letters, digits, dot, underscore, hyphen)")
    return run_id


def selected_gpu_device(*, require_health: bool = True) -> str:
    """Choose one physical GPU, excluding devices whose driver requests a reset."""
    explicit = os.environ.get("SURFLO_PATHWAY_GPU_DEVICE")
    if explicit is not None:
        if re.fullmatch(r"[0-9]+", explicit) is None:
            raise ValueError("SURFLO_PATHWAY_GPU_DEVICE must be one numeric GPU index")
    if not require_health:
        return explicit if explicit is not None else "0"
    executable = shutil.which("nvidia-smi")
    if executable is None:
        raise ValueError("nvidia-smi is unavailable; cannot select a healthy GPU")
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=index,gpu_recovery_action",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("nvidia-smi timed out while selecting a healthy GPU") from error
    if completed.returncode != 0:
        raise ValueError("nvidia-smi could not report GPU recovery state")
    devices: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 2 and fields[0].isdigit() and fields[0] not in devices:
            devices[fields[0]] = fields[1]
    if explicit is not None:
        if explicit not in devices:
            raise ValueError(
                f"SURFLO_PATHWAY_GPU_DEVICE={explicit} was not reported by nvidia-smi"
            )
        if devices[explicit].lower() not in {"none", "n/a"}:
            raise ValueError(
                f"SURFLO_PATHWAY_GPU_DEVICE={explicit} requires a reset: "
                f"{devices[explicit]}"
            )
        return explicit
    for index, recovery_action in devices.items():
        if recovery_action.lower() in {"none", "n/a"}:
            return index
    raise ValueError("no GPU is usable without a reset")


def validate_json_schema_instance(instance: Any, schema: dict[str, Any], location: str = "root") -> None:
    """Validate the dependency-free subset used by the tracked result/report schemas."""
    for index, branch in enumerate(schema.get("allOf", [])):
        validate_json_schema_instance(instance, branch, f"{location}.allOf[{index}]")
    if "if" in schema:
        try:
            validate_json_schema_instance(instance, schema["if"], f"{location}.if")
        except ValueError:
            conditional = schema.get("else")
            suffix = "else"
        else:
            conditional = schema.get("then")
            suffix = "then"
        if conditional is not None:
            validate_json_schema_instance(instance, conditional, f"{location}.{suffix}")
    if "const" in schema and instance != schema["const"]:
        raise ValueError(f"schema const mismatch at {location}")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValueError(f"schema enum mismatch at {location}")
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "number": (int, float), "integer": int}
    if expected in types and not isinstance(instance, types[expected]):
        raise ValueError(f"schema type mismatch at {location}: expected {expected}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValueError(f"schema minimum mismatch at {location}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValueError(f"schema maximum mismatch at {location}")
    if isinstance(instance, str) and "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
        raise ValueError(f"schema pattern mismatch at {location}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0) or len(instance) > schema.get("maxItems", len(instance)):
            raise ValueError(f"schema item-count mismatch at {location}")
        if "items" in schema:
            for index, child in enumerate(instance):
                validate_json_schema_instance(child, schema["items"], f"{location}[{index}]")
    if isinstance(instance, dict):
        missing = set(schema.get("required", [])) - set(instance)
        if missing:
            raise ValueError(f"schema missing keys at {location}: {sorted(missing)}")
        for key, child_schema in schema.get("properties", {}).items():
            if key in instance:
                validate_json_schema_instance(instance[key], child_schema, f"{location}.{key}")
