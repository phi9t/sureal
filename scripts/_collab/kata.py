"""Installed Kata adapter with pinned identities and separate observed effects."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from .admission import read_task_definition
from .contracts import JsonObject, Project, Refusal, Result, TaskDefinition, canonical, digest
from .git_workspace import physical, sha
from .store import Store, _write


def definition_record(definition: TaskDefinition) -> JsonObject:
    return {"schema_version": 1, "task_id": definition.task_id, "source_commit": definition.source_commit,
            "spec": definition.spec, "plan": definition.plan, "goal": definition.goal,
            "dependencies": list(definition.dependencies), "revision": definition.revision}


class Kata:
    def __init__(self, project: Project):
        self.project = project
        pin = project.tools["kata"]
        self.binary = physical(Path(pin["path"]))
        if sha(self.binary) != pin["sha256"]:
            raise Refusal("SOURCE_UNAVAILABLE", "Kata executable identity changed")
        self.environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}
        if project.kata.get("home"):
            self.environment["KATA_HOME"] = str(physical(Path(project.kata["home"])))
        self.actor = project.authority["lead"]
        if not self.actor.startswith("sureal/"):
            raise Refusal("UNADMITTED_SPEC", "distinct Sureal actor required")

    def _argv(self, arguments: list[str], actor: str | None = None) -> list[str]:
        return [str(self.binary), "--json", "--as", actor or self.actor,
                "--workspace", str(self.project.canonical), "--project", self.project.kata["name"], *arguments]

    def _call(self, arguments: list[str], *, actor: str | None = None, log: Path | None = None) -> JsonObject:
        if sha(self.binary) != self.project.tools["kata"]["sha256"]:
            raise Refusal("SOURCE_UNAVAILABLE", "Kata executable identity changed before call")
        argv = self._argv(arguments, actor)
        started = time.time_ns() // 1_000_000
        try:
            result = subprocess.run(argv, cwd=self.project.canonical, env=self.environment,
                                    capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Refusal("UNKNOWN_EFFECT" if log else "SOURCE_UNAVAILABLE", "Kata transport did not complete") from error
        ended = time.time_ns() // 1_000_000
        if log:
            log.mkdir(parents=True, exist_ok=False)
            _write(log / "stdout", result.stdout)
            _write(log / "stderr", result.stderr)
            _write(log / "actual-command.json", canonical({"schema_version": 1, "argv": argv,
                   "cwd": str(self.project.canonical),
                   "environment": {key: self.environment[key] for key in ("KATA_HOME",) if key in self.environment},
                   "exit_code": result.returncode,
                   "started_ms": started, "ended_ms": ended,
                   "stdout": {"path": str(log / "stdout"), "sha256": sha(log / "stdout")},
                   "stderr": {"path": str(log / "stderr"), "sha256": sha(log / "stderr")}}) + b"\n")
        if result.returncode:
            raise Refusal("UNKNOWN_EFFECT" if log else "SOURCE_UNAVAILABLE", "Kata command refused or failed",
                          {"argv": argv, "exit_code": result.returncode, "log": str(log) if log else None})
        if arguments[0] == "export" and not result.stdout:
            # Installed0.14.3 emits no envelope for --output. This is a local
            # observation of the actual file, not a fabricated daemon response.
            output = physical(Path(arguments[arguments.index("--output") + 1]))
            if not output.is_file():
                raise Refusal("UNKNOWN_EFFECT", "successful export has no actual output")
            return {"kata_api_version": 1, "observed_export": {"path": str(output), "sha256": sha(output)}}
        try:
            response = json.loads(result.stdout)
        except (ValueError, UnicodeError) as error:
            raise Refusal("UNKNOWN_EFFECT" if log else "SOURCE_UNAVAILABLE", "Kata result envelope unavailable") from error
        if response.get("kata_api_version") != 1:
            raise Refusal("SOURCE_UNAVAILABLE", "unprobed Kata API version")
        return response

    def identity(self) -> JsonObject:
        health = self._call(["health"])
        expected = self.project.kata
        for field in ("db_path", "schema_version", "api_schema_version", "version", "started_at"):
            pin = "database_schema_version" if field == "schema_version" else field
            if health.get(field) != expected.get(pin):
                raise Refusal("SOURCE_UNAVAILABLE", "Kata daemon capability/identity differs", {"field": field})
        if health.get("ok") is not True:
            raise Refusal("SOURCE_UNAVAILABLE", "Kata daemon is not healthy")
        rows = self._call(["projects", "list"])["projects"]
        matches = [row for row in rows if row["uid"] == expected["project_uid"]]
        if (len(matches) != 1 or matches[0]["id"] != expected["project_id"]
                or matches[0]["name"] != expected["name"]):
            raise Refusal("SOURCE_UNAVAILABLE", "Kata shared project identity differs")
        return {"schema_version": 1, "project_id": expected["project_id"], "project_uid": expected["project_uid"],
                "db_path": expected["db_path"], "version": health["version"]}

    def _issue(self, response: JsonObject) -> JsonObject:
        issue = response.get("issue", {})
        if (issue.get("project_id") != self.project.kata["project_id"]
                or issue.get("project_uid") != self.project.kata["project_uid"]):
            raise Refusal("SOURCE_UNAVAILABLE", "issue belongs to a different project")
        return issue

    def read_issue(self, uid: str) -> JsonObject:
        self.identity()
        response = self._call(["show", uid])
        issue = self._issue(response)
        if issue["uid"] != uid:
            raise Refusal("SOURCE_UNAVAILABLE", "exact issue UID required")
        return response

    def _prior(self, kind: str, operation_id: str) -> bool:
        if not self.project.state.exists():
            return False
        store = Store(self.project.state, create=False)
        with store.locked():
            return operation_id + "\0" + kind in store._projection(store._events())["effects"]

    @staticmethod
    def _record_result(store, effect, facts, log):
        # An external effect has already happened or been observed. Failure to
        # persist its acknowledgement cannot become a precondition refusal.
        try:
            return store.record(effect, facts)
        except (Refusal, OSError) as error:
            raise Refusal("UNKNOWN_EFFECT", "external result acknowledgement requires reconciliation",
                          {"record_id": effect.record_id, "log": str(log),
                           "cause": getattr(error, "reason", type(error).__name__)}, outcome="unknown") from error

    def _current_definition(self, definition, *, after_effect=False):
        try:
            return read_task_definition(self.project, definition.task_id, definition.source_commit,
                                        definition_record(definition))
        except (Refusal, OSError) as error:
            if not after_effect:
                raise
            raise Refusal("UNKNOWN_EFFECT", "task source changed during external import; reconcile retained effects",
                          {"task_id": definition.task_id, "definition_revision": definition.revision,
                           "cause": getattr(error, "reason", type(error).__name__)}, outcome="unknown") from error

    def _effect(self, kind: str, arguments: list[str], inputs: JsonObject, operation_id: str,
                actor: str | None = None, observe=None) -> JsonObject:
        self.identity()
        store = Store(self.project.state)
        with store.locked():
            projection = store._projection(store._events())
            prior = projection["effects"].get(operation_id + "\0" + kind)
            effect = store.prepare(kind, inputs, operation_id)
            completed = projection["results"].get(effect.record_id)
        if completed:
            facts = store.read(completed)["facts"]
            if facts["outcome"] != "ok":
                if facts["outcome"] != "unknown" or observe is None:
                    raise Refusal("UNKNOWN_EFFECT", "prior effect requires actual-state reconciliation", {"record_id": completed})
                # Preserve the original uncertain result. A distinct durable
                # reconciliation records fresh observations without repeating
                # the native mutation or rewriting its historical receipt.
                actual = observe()
                if actual is None:
                    raise Refusal("UNKNOWN_EFFECT", "uncertain effect is not proven by actual state", {"record_id": completed})
                reconciliation = store.prepare("kata-reconcile", {"schema_version": 1,
                    "effect_id": effect.record_id, "unknown_result": completed}, "reconcile-" + completed)
                with store.locked():
                    accepted = store._projection(store._events())["results"].get(reconciliation.record_id)
                if accepted:
                    accepted_facts = store.read(accepted)["facts"]
                    if accepted_facts.get("outcome") != "ok":
                        raise Refusal("UNKNOWN_EFFECT", "prior reconciliation is not acknowledged")
                    reference = accepted_facts.get("evidence", {}).get("response", {})
                    if sha(Path(reference["path"])) != reference.get("sha256"):
                        raise Refusal("UNKNOWN_EFFECT", "retained reconciliation evidence changed")
                    return actual
                log = self.project.state / "commands" / (reconciliation.record_id + "-" + uuid.uuid4().hex)
                log.mkdir(parents=True, exist_ok=False)
                path = log / "reconciled-response.json"
                _write(path, json.dumps(actual, sort_keys=True).encode() + b"\n")
                self._record_result(store, reconciliation, {"schema_version": 1, "outcome": "ok", "evidence": {
                    "reconciles": effect.record_id, "unknown_result": completed,
                    "response": {"path": str(path), "sha256": sha(path)}}}, log)
                return actual
            reference = facts["evidence"]["response"]
            raw = Path(reference["path"])
            if sha(raw) != reference["sha256"]:
                raise Refusal("UNKNOWN_EFFECT", "retained effect response changed")
            response = json.loads(raw.read_bytes())
            if observe is not None:
                actual = observe()
                if actual is None:
                    raise Refusal("UNKNOWN_EFFECT", "accepted effect no longer matches actual external state")
                return actual
            return response
        log = self.project.state / "commands" / (effect.record_id + "-" + uuid.uuid4().hex)
        if prior:
            response = observe() if observe else None
            if response is None:
                raise Refusal("UNKNOWN_EFFECT", "prepared external effect needs actual-state reconciliation",
                              {"record_id": effect.record_id})
            log.mkdir(parents=True, exist_ok=False)
            _write(log / "reconciled-response.json", json.dumps(response, sort_keys=True).encode() + b"\n")
            path = log / "reconciled-response.json"
        else:
            try:
                response = self._call(arguments, actor=actor, log=log)
                if observe is not None:
                    readback = observe()
                    if readback is None:
                        raise Refusal("UNKNOWN_EFFECT", "external effect readback differs from intent")
                    response = readback
                path = log / "observed-response.json"
                _write(path, json.dumps(response, sort_keys=True).encode() + b"\n")
            except (Refusal, OSError) as error:
                evidence = getattr(error, "evidence", {"error_type": type(error).__name__})
                self._record_result(store, effect, {"schema_version": 1, "outcome": "unknown", "reason": "UNKNOWN_EFFECT",
                                                  "evidence": evidence}, log)
                raise Refusal("UNKNOWN_EFFECT", getattr(error, "detail", "external acknowledgement failed"),
                              evidence, outcome="unknown") from error
        self._record_result(store, effect, {"schema_version": 1, "outcome": "ok", "evidence": {
            "response": {"path": str(path), "sha256": sha(path)}, "reconciled": bool(prior)}}, log)
        return response

    def _definitions(self) -> dict[str, JsonObject]:
        self.identity()
        issues = self._call(["list", "--status", "all", "--limit", "0"])["issues"]
        rows = {}
        for issue in issues:
            task_id = issue.get("metadata", {}).get("sureal_task")
            if task_id:
                if task_id in rows:
                    raise Refusal("OWNER_CONFLICT", "multiple issue UIDs for one stable task")
                if issue.get("project_uid") != self.project.kata["project_uid"]:
                    raise Refusal("SOURCE_UNAVAILABLE", "foreign project row in queue")
                rows[task_id] = issue
        return rows

    def import_tasks(self, tasks: list[TaskDefinition]) -> Result:
        definitions = {task.task_id: task for task in tasks}
        if len(definitions) != len(tasks):
            raise Refusal("UNADMITTED_SPEC", "duplicate stable task definition")
        for task in tasks:
            self._current_definition(task)
        rows = self._definitions()
        ordered = []
        remaining = dict(definitions)
        while remaining:
            ready = [task_id for task_id, definition in remaining.items()
                     if all(dependency in rows or dependency in ordered for dependency in definition.dependencies)]
            if not ready:
                raise Refusal("DEPENDENCY_OPEN", "cyclic or missing imported task dependency")
            for task_id in ready:
                ordered.append(task_id)
                del remaining[task_id]
        imported = {}
        for task_id in ordered:
            definition = definitions[task_id]
            desired = definition_record(definition)
            if task_id not in rows:
                def existing(task_id=task_id, definition=definition):
                    found = self._definitions().get(task_id)
                    observed = self.read_issue(found["uid"]) if found else None
                    self._current_definition(definition, after_effect=True)
                    return observed
                created = self._effect("kata-create", ["create", definition.goal + " [" + task_id + "]",
                    "--body", "Acceptance is pinned in sureal_definition; task labels do not prove completion.",
                    "--idempotency-key", "sureal/" + self.project.kata["project_uid"] + "/" + task_id,
                    "--meta", "sureal_task=" + task_id],
                    {"schema_version": 1, "task_id": task_id, "title": definition.goal + " [" + task_id + "]",
                     "project_uid": self.project.kata["project_uid"]},
                    "import-create-" + task_id, observe=existing)
                rows[task_id] = self._issue(created)
            uid = rows[task_id]["uid"]
            current = self.read_issue(uid)
            if current["issue"].get("metadata", {}).get("sureal_definition") != desired:
                revision = str(current["issue"]["revision"])
                def definition_readback(uid=uid, desired=desired, definition=definition):
                    observed = self.read_issue(uid)
                    self._current_definition(definition, after_effect=True)
                    return observed if observed["issue"].get("metadata", {}).get("sureal_definition") == desired else None
                self._effect("kata-definition", ["meta", "set", uid, "sureal_definition", canonical(desired).decode(),
                    "--json-value", "--if-match", revision],
                    {"schema_version": 1, "issue_uid": uid, "revision": revision, "definition": desired},
                    "definition-" + definition.revision, observe=definition_readback)
            desired_dependencies = {rows[dependency]["uid"] for dependency in definition.dependencies}
            current = self.read_issue(uid)
            actual_dependencies = {link["from"]["uid"] for link in current.get("links", [])
                                   if link["type"] == "blocks" and link["to"]["uid"] == uid}
            for add, dependencies in ((True, desired_dependencies - actual_dependencies),
                                      (False, actual_dependencies - desired_dependencies)):
                for dependency in sorted(dependencies):
                    def edge_readback(uid=uid, dependency=dependency, add=add, definition=definition):
                        observed = self.read_issue(uid)
                        self._current_definition(definition, after_effect=True)
                        found = any(link["type"] == "blocks" and link["to"]["uid"] == uid
                                    and link["from"]["uid"] == dependency for link in observed.get("links", []))
                        return observed if found == add else None
                    self._effect("kata-dependency", ["edit", uid, "--blocked-by" if add else "--remove-blocked-by", dependency],
                        {"schema_version": 1, "issue_uid": uid, "dependency_uid": dependency, "present": add},
                        "edge-" + definition.revision + "-" + dependency + "-" + str(add), observe=edge_readback)
            imported[task_id] = {"issue_uid": uid, "definition_revision": definition.revision,
                                 "spec": definition.spec, "plan": definition.plan,
                                 "dependencies": list(definition.dependencies)}
        for definition in tasks:
            self._current_definition(definition, after_effect=True)
        return Result("import-" + digest({"schema_version": 1, "tasks": imported}), "ok", evidence={"tasks": imported})

    def claim(self, uid: str, actor: str) -> JsonObject:
        if not actor.startswith("sureal/"):
            raise Refusal("UNADMITTED_SPEC", "attempt actor required")
        current = self.read_issue(uid)
        if current["issue"].get("owner") not in {None, "", actor}:
            raise Refusal("OWNER_CONFLICT", "task already owned")
        def observed():
            result = self.read_issue(uid)
            return result if result["issue"].get("owner") == actor else None
        return self._effect("kata-claim", ["claim", uid], {"schema_version": 1, "issue_uid": uid, "actor": actor},
                            "claim-" + uid + "-" + actor, actor=actor, observe=observed)

    def assign(self, uid: str, revision: str, assignment: JsonObject) -> JsonObject:
        canonical(assignment)
        current = self.read_issue(uid)
        actor = assignment.get("actor")
        inputs = {"schema_version": 1, "issue_uid": uid, "revision": revision, "assignment": assignment}
        operation_id = "assignment-" + digest(inputs)
        if current["issue"].get("owner") != actor or (str(current["issue"]["revision"]) != revision
                and not self._prior("kata-assignment", operation_id)):
            raise Refusal("OWNER_CONFLICT", "assignment actor/revision differs")
        def observed():
            result = self.read_issue(uid)
            issue = result["issue"]
            return result if issue.get("owner") == actor and issue.get("metadata", {}).get("sureal_assignment") == assignment else None
        return self._effect("kata-assignment", ["meta", "set", uid, "sureal_assignment", canonical(assignment).decode(),
                            "--json-value", "--if-match", revision], inputs, operation_id,
                            actor=actor, observe=observed)

    def release(self, uid: str, actor: str) -> JsonObject:
        current = self.read_issue(uid)
        operation_id = "release-" + uid + "-" + actor
        if (current["issue"].get("owner") != actor and
                (current["issue"].get("owner") or not self._prior("kata-release", operation_id))):
            raise Refusal("OWNER_CONFLICT", "only the exact current owner can release")
        def observed():
            result = self.read_issue(uid)
            return result if not result["issue"].get("owner") else None
        return self._effect("kata-release", ["unassign", uid], {"schema_version": 1, "issue_uid": uid, "actor": actor},
                            operation_id, actor=actor, observe=observed)

    def comment(self, uid: str, body: str) -> JsonObject:
        self.read_issue(uid)
        inputs = {"schema_version": 1, "issue_uid": uid, "body": body}
        return self._effect("kata-comment", ["comment", uid, body], inputs, "comment-" + digest(inputs))

    def export(self, project_id: int, output: Path) -> JsonObject:
        self.identity()
        output = physical(output)
        operation_id = "export-" + digest({"schema_version": 1, "project_id": project_id, "output": str(output)})
        if (project_id != self.project.kata["project_id"]
                or (output.exists() and not self._prior("kata-export", operation_id))
                or output == self.project.canonical or self.project.canonical in output.parents):
            raise Refusal("SCOPE_CONFLICT", "fresh project-only export outside canonical required")
        response = self._effect("kata-export", ["export", "--project-id", str(project_id),
            "--allow-running-daemon", "--output", str(output)],
            {"schema_version": 1, "project_id": project_id, "output": str(output)},
            operation_id)
        if not output.is_file():
            raise Refusal("UNKNOWN_EFFECT", "Kata export output is missing")
        if response.get("observed_export", {}).get("sha256") != sha(output):
            raise Refusal("UNKNOWN_EFFECT", "retained exported bytes changed")
        return {"schema_version": 1, "path": str(output), "sha256": sha(output), "response": response}
