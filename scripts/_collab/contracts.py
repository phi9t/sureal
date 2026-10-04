"""Versioned, deterministic records and explicit failure envelopes."""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Literal

JsonObject = dict[str, object]


class Refusal(RuntimeError):
    def __init__(self, reason: str, detail: str, evidence: JsonObject | None = None, *, outcome: str = "refused"):
        if outcome not in {"refused", "unknown"}:
            raise ValueError("refusal or uncertain-effect outcome required")
        self.outcome = outcome
        self.reason = reason
        self.detail = detail
        self.evidence = evidence or {}
        super().__init__(detail)


def _validate(value: object) -> None:
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise Refusal("USAGE_ERROR", "record keys must be strings")
        if "schema_version" in value and (type(value["schema_version"]) is not int or value["schema_version"] != 1):
            raise Refusal("USAGE_ERROR", "unknown record schema")
        for child in value.values():
            _validate(child)
    elif isinstance(value, list):
        for child in value:
            _validate(child)
    elif type(value) not in {str, int, bool, type(None)}:
        raise Refusal("USAGE_ERROR", "digested records require integer values, not floats")


def canonical(value: JsonObject) -> bytes:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise Refusal("USAGE_ERROR", "versioned object required")
    _validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: JsonObject) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def loads(raw: str | bytes) -> JsonObject:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refusal("USAGE_ERROR", "duplicate JSON key")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs)
        canonical(result)
        return result
    except (ValueError, UnicodeError, TypeError) as error:
        raise Refusal("USAGE_ERROR", "invalid protocol JSON") from error


@dataclass(frozen=True)
class Result:
    operation_id: str
    outcome: Literal["ok", "refused", "unknown"]
    record_id: str | None = None
    reason: str | None = None
    evidence: JsonObject = field(default_factory=dict)

    def wire(self) -> JsonObject:
        return {"schema_version": 1, "operation_id": self.operation_id, "outcome": self.outcome,
                "record_id": self.record_id, "reason": self.reason, "evidence": self.evidence}


@dataclass(frozen=True)
class Effect:
    operation_id: str
    step_name: str
    kind: str
    inputs: JsonObject
    input_digest: str
    record_id: str
    state: str = "prepared"


@dataclass(frozen=True)
class Project:
    project_id: str
    canonical: Path
    state: Path
    common_git_dir: Path
    ref: str
    transition_base: str
    publication: JsonObject
    kata: JsonObject
    tools: JsonObject
    runtime: JsonObject
    authority: JsonObject
    admission_digest: str
    capacity: int = 2


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    source_commit: str
    spec: JsonObject
    plan: JsonObject
    goal: str
    dependencies: tuple[str, ...]
    revision: str


@dataclass(frozen=True)
class TaskBrief:
    task_id: str
    issue_uid: str
    base: str
    definition: TaskDefinition
    brief_digest: str
    allowed_writes: tuple[str, ...]
    exclusions: tuple[str, ...]
    resources: JsonObject
    checks: JsonObject
    retention: JsonObject
    dependency_closures: JsonObject


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    task_id: str
    generation: str
    actor: str
    seat: int
    brief_digest: str
    base: str
    workspace: Path
    branch: str
    output: Path
    session_id: str | None
    thread_id: str | None
    runtime: JsonObject
    acknowledgement: JsonObject
    state: str
    effects: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    task_id: str
    brief_digest: str
    attempt_id: str
    generation: str
    commit: str
    tree: str
    parent: str
    report: JsonObject
    retention: JsonObject
    source: JsonObject
    submitted_ms: int


@dataclass(frozen=True)
class Verification:
    verification_id: str
    candidate: Candidate
    context: JsonObject
    commands: JsonObject
    artifacts: JsonObject
    findings: JsonObject
    disposition: str


@dataclass(frozen=True)
class Closure:
    task_id: str
    base: str
    commit: str
    tree: str
    acceptance: JsonObject
    integration: JsonObject
    publication: JsonObject
    retention: JsonObject
    cleanup: JsonObject
    kata_close: JsonObject


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    observed_ms: int
    sources: JsonObject
    workers: JsonObject
    tasks: JsonObject
    incidents: JsonObject


@dataclass(frozen=True)
class MaterializationReceipt:
    commit: str
    tree: str
    parent: str
    source: Path
    entries: JsonObject
    gitlinks: JsonObject
    owner: str
    source_digest: str
