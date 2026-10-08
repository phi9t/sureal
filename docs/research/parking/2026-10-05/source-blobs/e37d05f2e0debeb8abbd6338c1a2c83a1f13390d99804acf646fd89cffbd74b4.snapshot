"""Durable intent/result journal; surviving intent never implies effect success."""
from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import threading
import uuid

from .contracts import Effect, JsonObject, Refusal, Result, canonical, digest, loads


def _directory_sync(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _regular(path: Path) -> None:
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise Refusal("UNKNOWN_EFFECT", "state paths must not traverse aliases")


def _mkdir(path: Path) -> None:
    _regular(path)
    if path.exists():
        if not path.is_dir():
            raise Refusal("UNKNOWN_EFFECT", "state directory is not regular")
        return
    _mkdir(path.parent)
    path.mkdir(mode=0o700)
    _directory_sync(path.parent)


def _write(path: Path, data: bytes, *, immutable: bool = False) -> None:
    _regular(path)
    if immutable and path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise Refusal("UNKNOWN_EFFECT", "immutable state record changed")
        return
    temporary = path.parent / ("." + path.name + ".pending-" + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _directory_sync(path.parent)
    except BaseException:
        # Pending bytes survive failure for explicit reconciliation/disposition.
        raise


class Store:
    def __init__(self, state: Path, *, create: bool = True):
        self.state = Path(state).absolute()
        _regular(self.state)
        self._readonly = not create
        if create:
            _mkdir(self.state)
        elif not self.state.is_dir():
            raise Refusal("SOURCE_UNAVAILABLE", "existing project state required")
        for name in ("records", "incidents"):
            path = self.state / name
            _regular(path)
            if create:
                _mkdir(path)
            elif not path.is_dir():
                raise Refusal("UNKNOWN_EFFECT", "project state layout is incomplete")
        self._mutex = threading.RLock()
        self._local = threading.local()

    @contextmanager
    def locked(self):
        if not self._mutex.acquire(blocking=False):
            raise Refusal("OWNER_CONFLICT", "another controller owns the state lock")
        depth = getattr(self._local, "depth", 0)
        fd = None
        try:
            if depth == 0:
                lock = self.state / "project.lock"
                _regular(lock)
                flags = os.O_RDONLY if self._readonly else os.O_CREAT | os.O_RDWR
                fd = os.open(lock, flags | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
                if os.fstat(fd).st_nlink != 1:
                    raise Refusal("UNKNOWN_EFFECT", "state lock has an alias")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise Refusal("OWNER_CONFLICT", "another controller owns the state lock") from error
            self._local.depth = depth + 1
            yield self
        finally:
            self._local.depth = depth
            if fd is not None:
                os.close(fd)
            self._mutex.release()

    def _events(self, *, repair: bool = False) -> list[JsonObject]:
        path = self.state / "events.jsonl"
        _regular(path)
        if not path.exists():
            return []
        raw = path.read_bytes()
        tail = b""
        if raw and not raw.endswith(b"\n"):
            split = raw.rfind(b"\n") + 1
            raw, tail = raw[:split], raw[split:]
        events = []
        previous = None
        for line in raw.splitlines():
            try:
                event = loads(line)
                claimed = event["sha256"]
                payload = {key: value for key, value in event.items() if key != "sha256"}
                valid = (event["sequence"] == len(events) + 1 and event["previous"] == previous
                         and digest(payload) == claimed and digest(event["record"]) == event["record_id"]
                         and event["operation_id"] == event["record"]["operation_id"]
                         and event["event"] in {"prepared", "result"})
                if not valid:
                    raise ValueError("journal identity/chain mismatch")
            except (Refusal, KeyError, TypeError, ValueError) as error:
                raise Refusal("UNKNOWN_EFFECT", "earlier journal corruption holds mutation") from error
            events.append(event)
            previous = claimed
        if tail:
            if not repair:
                raise Refusal("UNKNOWN_EFFECT", "torn trailing journal requires reconciliation")
            _write(self.state / "incidents" / (hashlib.sha256(tail).hexdigest() + ".tail"), tail, immutable=True)
            _write(path, raw)
        return events

    def _projection(self, events: list[JsonObject], *, restore: bool = False) -> JsonObject:
        effects = {}
        results = {}
        for event in events:
            record = event["record"]
            path = self.state / "records" / (event["record_id"] + ".json")
            _regular(path)
            expected = canonical(record) + b"\n"
            if path.exists():
                if path.read_bytes() != expected:
                    raise Refusal("UNKNOWN_EFFECT", "retained immutable record is corrupt")
            elif restore and event["event"] == "prepared":
                _write(path, expected, immutable=True)
            else:
                raise Refusal("UNKNOWN_EFFECT", "missing record requires journal reconciliation")
            if event["event"] == "prepared":
                if record.get("record_type") != "Effect" or record.get("state") != "prepared":
                    raise Refusal("UNKNOWN_EFFECT", "invalid prepared record")
                if digest(record["inputs"]) != record["input_digest"]:
                    raise Refusal("UNKNOWN_EFFECT", "intent inputs changed")
                key = record["operation_id"] + "\0" + record["step_name"]
                if key in effects:
                    raise Refusal("UNKNOWN_EFFECT", "duplicate effect intent")
                effects[key] = event["record_id"]
            else:
                effect_id = record.get("effect_id")
                if (record.get("record_type") != "EffectResult" or effect_id not in effects.values()
                        or effect_id in results):
                    raise Refusal("UNKNOWN_EFFECT", "result has no unique prior intent")
                intent = self.read(effect_id)
                if record["operation_id"] != intent["operation_id"]:
                    raise Refusal("UNKNOWN_EFFECT", "result operation mismatch")
                if record.get("facts", {}).get("outcome") not in {"ok", "refused", "unknown"}:
                    raise Refusal("UNKNOWN_EFFECT", "result outcome missing")
                results[effect_id] = event["record_id"]
        return {"schema_version": 1, "sequence": len(events), "head": events[-1]["sha256"] if events else None,
                "effects": effects, "results": results}

    def _append(self, event_kind: str, record: JsonObject) -> str:
        if self._readonly:
            raise Refusal("SCOPE_CONFLICT", "read-only observer cannot mutate project state")
        events = self._events()
        self._projection(events)
        record_id = digest(record)
        payload = {"schema_version": 1, "sequence": len(events) + 1,
                   "previous": events[-1]["sha256"] if events else None, "event": event_kind,
                   "operation_id": record["operation_id"], "record_id": record_id, "record": record}
        event = {**payload, "sha256": digest(payload)}
        path = self.state / "events.jsonl"
        _regular(path)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "ab") as stream:
            stream.write(canonical(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        _directory_sync(self.state)
        _write(self.state / "records" / (record_id + ".json"), canonical(record) + b"\n", immutable=True)
        _write(self.state / "current.json", canonical(self._projection([*events, event])) + b"\n")
        return record_id

    def read(self, record_id: str) -> JsonObject:
        if (not isinstance(record_id, str) or len(record_id) != 64
                or any(char not in "0123456789abcdef" for char in record_id)):
            raise Refusal("USAGE_ERROR", "record identity must be SHA256")
        path = self.state / "records" / (record_id + ".json")
        _regular(path)
        try:
            raw = path.read_bytes()
            record = loads(raw)
            if digest(record) != record_id or canonical(record) + b"\n" != raw:
                raise ValueError("immutable record identity mismatch")
            return record
        except (OSError, Refusal, ValueError) as error:
            raise Refusal("UNKNOWN_EFFECT", "immutable record unavailable or corrupt") from error

    def prepare(self, kind: str, inputs: JsonObject, operation_id: str) -> Effect:
        if any(not isinstance(value, str) or not value or "\0" in value for value in (kind, operation_id)):
            raise Refusal("USAGE_ERROR", "nonempty effect and operation identities required")
        input_digest = digest(inputs)
        with self.locked():
            events = self._events()
            projection = self._projection(events)
            existing = projection["effects"].get(operation_id + "\0" + kind)
            if existing:
                payload = self.read(existing)
                if payload["input_digest"] != input_digest:
                    raise Refusal("CANDIDATE_MISMATCH", "operation reused with different inputs")
                return Effect(operation_id, kind, kind, payload["inputs"], input_digest, existing)
            payload = {"schema_version": 1, "record_type": "Effect", "operation_id": operation_id,
                       "step_name": kind, "kind": kind, "inputs": inputs, "input_digest": input_digest,
                       "state": "prepared"}
            record_id = self._append("prepared", payload)
            return Effect(operation_id, kind, kind, loads(canonical(inputs)), input_digest, record_id)

    def record(self, effect: Effect, facts: JsonObject) -> Result:
        canonical(facts)
        if facts.get("outcome") not in {"ok", "refused", "unknown"}:
            raise Refusal("USAGE_ERROR", "observed result outcome required")
        with self.locked():
            projection = self._projection(self._events())
            intent = self.read(effect.record_id)
            if (projection["effects"].get(effect.operation_id + "\0" + effect.step_name) != effect.record_id
                    or intent["input_digest"] != effect.input_digest
                    or digest(effect.inputs) != effect.input_digest):
                raise Refusal("CANDIDATE_MISMATCH", "effect does not match retained intent")
            payload = {"schema_version": 1, "record_type": "EffectResult", "operation_id": effect.operation_id,
                       "effect_id": effect.record_id, "facts": facts}
            existing = projection["results"].get(effect.record_id)
            if existing:
                if self.read(existing) != payload:
                    raise Refusal("CANDIDATE_MISMATCH", "result already recorded with different facts")
                record_id = existing
            else:
                record_id = self._append("result", payload)
            return Result(effect.operation_id, facts["outcome"], record_id, facts.get("reason"), facts.get("evidence", {}))

    def reconcile_journal(self) -> Result:
        if self._readonly:
            raise Refusal("SCOPE_CONFLICT", "read-only observer cannot reconcile state")
        with self.locked():
            events = self._events(repair=True)
            projection = self._projection(events, restore=True)
            _write(self.state / "current.json", canonical(projection) + b"\n")
            return Result("journal-reconcile", "ok", evidence=projection)
