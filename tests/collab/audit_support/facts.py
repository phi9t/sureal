"""Independent literal record-chain and coverage validation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from .raw_git import InvalidEvidence, strict_json


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidEvidence(reason)


def content_digest(value: object) -> str:
    def inspect(part):
        if type(part) in (float,):
            raise InvalidEvidence("Floats forbidden in canonical records")
        if isinstance(part, dict):
            require(all(isinstance(key, str) for key in part), "Non-string canonical key")
            if "schema_version" in part:
                require(type(part["schema_version"]) is int and part["schema_version"] == 1,
                        "Unknown canonical schema")
            for child in part.values():
                inspect(child)
        elif isinstance(part, list):
            for child in part:
                inspect(child)
        else:
            require(part is None or type(part) in (int, str, bool), "Non-JSON canonical value")
    inspect(value)
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def parse_record(data: bytes) -> dict:
    def pairs(items):
        output = {}
        for key, value in items:
            require(key not in output, "Duplicate record key")
            output[key] = value
        return output
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               InvalidEvidence("Invalid JSON number")))
    except (ValueError, UnicodeError) as error:
        raise InvalidEvidence("Invalid canonical record") from error
    require(isinstance(value, dict) and type(value.get("schema_version")) is int and
            value["schema_version"] == 1, "Canonical schema_version1 required")
    content_digest(value)
    return value


def select_cases(coverage: dict, ticket: str, phase: str, role: str) -> list[dict]:
    require(role in coverage["ticket_roles"].get(ticket, []), "Unlisted candidate role")
    require(phase in {"gate", "post-landing", "closure"}, "Unknown acceptance phase")
    selected = [case for case in coverage["cases"].get(ticket, []) if
                case["phase"] == phase and
                ("all" in case["candidate_roles"] or role in case["candidate_roles"])]
    require(bool(selected), "Empty matching ticket/phase/role refuses")
    require(len({item["id"] for item in selected}) == len(selected), "Duplicate coverage cases")
    return selected


def check_journal(state: Path, *, allow_incomplete: bool = False) -> dict:
    """Derive the projection and unresolved effects from raw validated chain bytes."""
    require(state.is_absolute() and state.is_dir() and not state.is_symlink(),
            "Actual regular absolute state directory required")
    events_path = state / "events.jsonl"
    raw = events_path.read_bytes() if events_path.exists() else b""
    require(events_path.exists() or allow_incomplete,"Raw journal absent")
    sequence = 0; previous = None; effects = {}; results = {}; effect_records = {}
    uncommitted_results = {}
    torn = None
    lines = raw.splitlines(keepends=True)
    for position, line in enumerate(lines):
        if not line.endswith(b"\n"):
            require(position == len(lines)-1 and allow_incomplete, "Torn journal tail unresolved")
            torn = hashlib.sha256(line).hexdigest()
            break
        event = parse_record(line)
        require(set(event) == {"schema_version","sequence","previous","event","operation_id",
                               "record_id","record","sha256"}, "Unexpected event fields")
        require(type(event["sequence"]) is int and event["sequence"] == sequence+1 and
                event["previous"] == previous, "Journal chain order corruption")
        actual = content_digest({key:value for key,value in event.items() if key != "sha256"})
        require(event["sha256"] == actual, "Event digest corruption")
        record = event["record"]
        require(isinstance(record, dict) and content_digest(record) == event["record_id"],
                "Embedded immutable record digest mismatch")
        require(record.get("operation_id") == event["operation_id"], "Operation identity mismatch")
        record_path = state / "records" / (event["record_id"]+".json")
        if record_path.exists():
            require(not record_path.is_symlink() and
                    parse_record(record_path.read_bytes()) == record, "Immutable record changed")
        else:
            require(allow_incomplete, "Immutable record missing")
        if event["event"] == "prepared":
            require(set(record) == {"schema_version","record_type","operation_id","step_name",
                                   "kind","inputs","input_digest","state"}, "Invalid Effect fields")
            require(record["record_type"] == "Effect" and record["state"] == "prepared" and
                    record["input_digest"] == content_digest(record["inputs"]), "Invalid prepared effect")
            require(isinstance(record["operation_id"],str) and isinstance(record["step_name"],str) and
                    "\0" not in record["operation_id"] and "\0" not in record["step_name"],
                    "Invalid effect compound identity")
            key = record["operation_id"]+"\0"+record["step_name"]
            require(key not in effects, "Duplicate prepared effect")
            effects[key] = event["record_id"]
            effect_records[event["record_id"]] = record
        elif event["event"] == "result":
            require(set(record) == {"schema_version","record_type","operation_id","effect_id","facts"},
                    "Invalid result fields")
            effect_id = record["effect_id"]
            require(record["record_type"] == "EffectResult" and effect_id in effect_records and
                    effect_id not in results and effect_id not in uncommitted_results and
                    effect_records[effect_id]["operation_id"] == record["operation_id"],
                    "Result does not resolve exactly one preceding effect")
            require(record["facts"].get("outcome") in {"ok","refused","unknown"}, "Invalid result outcome")
            # An unfsynced result event can survive without its immutable record.
            # Its asserted outcome is not durable external-effect evidence.
            if record_path.exists():
                results[effect_id] = event["record_id"]
            else:
                uncommitted_results[effect_id] = event["record_id"]
        else:
            raise InvalidEvidence("Unknown journal event")
        sequence = event["sequence"]; previous = event["sha256"]
    derived = {"schema_version":1,"head":previous,"sequence":sequence,"effects":effects,"results":results}
    projection_path = state / "current.json"
    if not allow_incomplete:
        require(strict_json(projection_path) == derived, "Projection does not equal validated journal")
    return {**derived,"unresolved_effects":sorted(set(effects.values())-set(results)),
            "uncommitted_results":uncommitted_results,"torn_tail_sha256":torn}
