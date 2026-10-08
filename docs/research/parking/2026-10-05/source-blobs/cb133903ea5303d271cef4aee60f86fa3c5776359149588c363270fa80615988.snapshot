"""Project/source admission; runtime authority stays distinct from source cleanliness."""
import json
import hashlib
from pathlib import Path, PurePosixPath
import tomllib

from .contracts import JsonObject, Project, Refusal, TaskBrief, TaskDefinition, canonical, digest, loads
from .git_workspace import GitWorkspace, admitted_source, physical, run_git, sha
from .store import Store, _write


def artifact(reference: JsonObject) -> bytes:
    try:
        path = physical(Path(reference["path"]))
        if not path.is_file() or sha(path) != reference["sha256"]:
            raise ValueError("artifact differs")
        return path.read_bytes()
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise Refusal("VERIFICATION_INCOMPLETE", "pinned admission artifact unavailable or changed") from error


def _audit(admission: JsonObject, facts: JsonObject) -> None:
    gate = loads(artifact(admission["gate_admission"]))
    report = loads(artifact(admission["gate_audit"]))
    if (gate.get("kind") != "GateAdmission" or report.get("kind") != "independent-collaboration-audit"
            or report.get("ticket") != "49" or report.get("phase") != "gate"
            or report.get("candidate_role") != "implementation" or report.get("status") != "pass"
            or report.get("accepted") is not True or report.get("phase_complete") is not True
            or report.get("candidate") != gate["source"]["candidate"]
            or report.get("tree") != gate["source"]["tree"]
            or report.get("gate_admission_sha256") != admission["gate_admission"]["sha256"]
            or report.get("coverage_sha256") != gate["coverage"]["sha256"]
            or report.get("materialization_sha256") != gate["source"]["materialization_sha256"]
            or report.get("auditor", {}).get("candidate") != gate["auditor"]["candidate"]):
        raise Refusal("VERIFICATION_INCOMPLETE", "independent implementation gate context incomplete")
    source = gate["source"]["candidate"]
    if run_git(Path(facts["root"]), "merge-base", source, facts["head"], tool_pin=admission["tools"].get("git")).decode().strip() != source:
        raise Refusal("UNADMITTED_SPEC", "accepted controller source is not on mainline")
    coverage = loads(artifact(gate["coverage"]))
    required = {case["id"] for case in coverage["cases"]["49"] if case["phase"] == "gate"
                and any(role in {"implementation", "all"} for role in case["candidate_roles"])}
    if not required or set(report.get("cases", {})) != required:
        raise Refusal("VERIFICATION_INCOMPLETE", "complete independent gate cases required")
    for case in report["cases"].values():
        if not case.get("raw_artifacts"):
            raise Refusal("VERIFICATION_INCOMPLETE", "raw independently reopened evidence required")
        for reference in case["raw_artifacts"]:
            artifact(reference)
    artifact(gate["auditor"]["materialization"])
    artifact(gate["auditor"]["review"])
    artifact(gate["runtime"]["lock"])
    for reference in gate["runtime"]["resource_sources"].values():
        artifact(reference)
    if admission["runtime"] != gate["runtime"]:
        raise Refusal("VERIFICATION_INCOMPLETE", "project/runtime gate pins differ")


def admit_project(canonical_root: Path, state: Path, admission: JsonObject, *, operation_id: str | None = None) -> Project:
    canonical(admission)
    root, state = physical(canonical_root), physical(state)
    if admission.get("kind") != "ProjectAdmission":
        raise Refusal("UNADMITTED_SPEC", "fixture GateAdmission cannot initialize a real project")
    if str(root) != admission.get("canonical") or str(state) != admission.get("state"):
        raise Refusal("DIRTY_SOURCE", "exact canonical/state paths required")
    if root == state or root in state.parents or state in root.parents:
        raise Refusal("DIRTY_SOURCE", "runtime state must be outside canonical source")
    if admission.get("capacity") != 2 or admission.get("ref") != "refs/heads/phi9t/mainline":
        raise Refusal("UNADMITTED_SPEC", "two-seat Sureal integration contract required")
    facts = admitted_source(root, admission["ref"], admission["transition_base"], tool_pin=admission.get("tools", {}).get("git"))
    if facts["common_git_dir"] != admission.get("common_git_dir"):
        raise Refusal("DIRTY_SOURCE", "common Git directory differs")
    try:
        _audit(admission, facts)
        for pin in admission["tools"].values():
            artifact(pin)
        if not {"git", "python", "kata", "codex", "bwrap", "systemd_run"} <= set(admission["tools"]):
            raise Refusal("SOURCE_UNAVAILABLE", "complete actual tool pins required")
        if not admission["authority"].get("lead") or admission["authority"].get("ref") != admission["ref"]:
            raise Refusal("UNADMITTED_SPEC", "explicit integration delegation required")
        project = Project(admission["project_id"], root, state, Path(facts["common_git_dir"]), admission["ref"],
                          facts["head"], admission["publication"], admission["kata"], admission["tools"],
                          admission["runtime"], admission["authority"], digest(admission))
    except (KeyError, TypeError) as error:
        raise Refusal("UNADMITTED_SPEC", "incomplete project admission") from error
    # Kata identity is read and compared before any state initialization.
    from .kata import Kata
    Kata(project).identity()
    store = Store(state)
    inputs = {"schema_version": 1, "admission_digest": digest(admission), "source": facts}
    effect = store.prepare("project-init", inputs, operation_id or "init-" + digest(admission))
    project_file = state / "project.json"
    try:
        project_bytes = canonical(admission) + b"\n"
        project_sha256 = hashlib.sha256(project_bytes).hexdigest()
        _write(project_file, project_bytes, immutable=True)
        if sha(project_file) != project_sha256:
            raise Refusal("UNKNOWN_EFFECT", "project publication bytes changed")
        store.record(effect, {"schema_version": 1, "outcome": "ok", "evidence": {"project_sha256": project_sha256}})
    except (Refusal, OSError) as error:
        raise Refusal("UNKNOWN_EFFECT", "project initialization acknowledgement requires reconciliation",
                      {"record_id": effect.record_id, "project": str(project_file),
                       "cause": getattr(error, "reason", type(error).__name__)}, outcome="unknown") from error
    return project


def load_project(state: Path) -> Project:
    state = physical(state)
    admission = loads((state / "project.json").read_bytes())
    store = Store(state, create=False)
    with store.locked():
        projection = store._projection(store._events())
        accepted = []
        for effect_id, result_id in projection["results"].items():
            intent, result = store.read(effect_id), store.read(result_id)
            if (intent["kind"] == "project-init" and intent["inputs"].get("admission_digest") == digest(admission)
                    and result["facts"].get("outcome") == "ok"
                    and result["facts"].get("evidence", {}).get("project_sha256") == sha(state / "project.json")):
                accepted.append(effect_id)
        if not accepted:
            raise Refusal("UNKNOWN_EFFECT", "project initialization result requires reconciliation")
    if admission.get("kind") != "ProjectAdmission" or admission.get("state") != str(state):
        raise Refusal("UNKNOWN_EFFECT", "project identity changed")
    return Project(admission["project_id"], Path(admission["canonical"]), state, Path(admission["common_git_dir"]),
                   admission["ref"], admission["transition_base"], admission["publication"], admission["kata"],
                   admission["tools"], admission["runtime"], admission["authority"], digest(admission))


def read_task_definition(project: Project, task_id: str, source_commit: str,
                         definition: JsonObject | None = None) -> TaskDefinition:
    git_pin = project.tools.get("git")
    facts = GitWorkspace.inspect(project.canonical, tool_pin=git_pin)
    if facts["ref"] != project.ref or facts["status_z_hex"]:
        raise Refusal("DIRTY_SOURCE", "definitions must be read from clean mainline")
    if run_git(project.canonical, "merge-base", source_commit, facts["head"], tool_pin=git_pin).decode().strip() != source_commit:
        raise Refusal("UNADMITTED_SPEC", "definition source is not landed mainline history")
    if definition is None:
        raise Refusal("UNADMITTED_SPEC", "reviewed definition manifest required before task map exists")
    canonical(definition)
    if definition.get("task_id") != task_id or definition.get("source_commit") != source_commit:
        raise Refusal("UNADMITTED_SPEC", "task/source identity differs")
    for key in ("spec", "plan"):
        pin = definition.get(key, {})
        relative = PurePosixPath(pin.get("path", ""))
        if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2
                or relative.parts[0] != "docs" or relative.suffix != ".md"):
            raise Refusal("UNADMITTED_SPEC", "definition path must stay in admitted source")
        blob = run_git(project.canonical, "rev-parse", source_commit + ":" + str(relative), tool_pin=git_pin).decode().strip()
        current_blob = run_git(project.canonical, "rev-parse", facts["head"] + ":" + str(relative), tool_pin=git_pin).decode().strip()
        raw = run_git(project.canonical, "cat-file", "blob", blob, tool_pin=git_pin)
        import hashlib
        if blob != current_blob or blob != pin.get("blob") or hashlib.sha256(raw).hexdigest() != pin.get("sha256"):
            raise Refusal("UNADMITTED_SPEC", "exact definition blob/content identity differs")
    revision = digest({key: value for key, value in definition.items() if key != "revision"})
    if definition.get("revision", revision) != revision:
        raise Refusal("UNADMITTED_SPEC", "definition revision digest differs")
    return TaskDefinition(task_id, source_commit, definition["spec"], definition["plan"],
                          definition["goal"], tuple(definition["dependencies"]), revision)


def admit_task(project: Project, task_id: str, brief: JsonObject) -> TaskBrief:
    canonical(brief)
    admitted_source(project.canonical, project.ref, brief["base"], tool_pin=project.tools.get("git"))
    definition = read_task_definition(project, task_id, brief["definition"]["source_commit"], brief["definition"])
    for scope in [*brief["allowed_writes"], *brief.get("exclusions", [])]:
        path = PurePosixPath(scope)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] in {".git", ".worktrees"}:
            raise Refusal("SCOPE_CONFLICT", "worker scope escapes source")
    mapping = loads(run_git(project.canonical, "show", brief["base"] + ":docs/research/kata-task-map.json", tool_pin=project.tools.get("git")))
    binding_bytes = run_git(project.canonical, "show", brief["base"] + ":.kata.toml", tool_pin=project.tools.get("git"))
    try:
        binding = tomllib.loads(binding_bytes.decode())
    except (UnicodeError, ValueError) as error:
        raise Refusal("UNADMITTED_SPEC", "committed Kata binding is invalid") from error
    if (mapping.get("project") != {"id": project.kata["project_id"], "uid": project.kata["project_uid"],
                                  "name": project.kata["name"]} or
            mapping.get("binding") != {"path": ".kata.toml", "sha256": hashlib.sha256(binding_bytes).hexdigest()} or
            binding.get("version") != 1 or binding.get("project", {}).get("name") != project.kata["name"]):
        raise Refusal("UNADMITTED_SPEC", "committed map/binding identifies a different project")
    entry = mapping.get("tasks", {}).get(task_id)
    if (not entry or entry.get("issue_uid") != brief["issue_uid"]
            or entry.get("definition_revision") != definition.revision or entry.get("spec") != definition.spec
            or entry.get("plan") != definition.plan or entry.get("dependencies") != list(definition.dependencies)):
        raise Refusal("UNADMITTED_SPEC", "committed task/issue map is not admitted")
    for dependency in definition.dependencies:
        if dependency not in brief.get("dependency_closures", {}):
            raise Refusal("DEPENDENCY_OPEN", "predecessor independent closure evidence required")
        closure = loads(artifact(brief["dependency_closures"][dependency]))
        if (closure.get("kind") != "independent-collaboration-audit" or closure.get("ticket") != dependency
                or closure.get("phase") != "closure" or closure.get("status") != "pass"
                or closure.get("accepted") is not True or closure.get("phase_complete") is not True
                or not closure.get("candidate") or not closure.get("cases")):
            raise Refusal("DEPENDENCY_OPEN", "predecessor needs independently accepted complete closure")
        for case in closure["cases"].values():
            if not case.get("raw_artifacts"):
                raise Refusal("DEPENDENCY_OPEN", "predecessor closure has no reopened raw evidence")
            for reference in case["raw_artifacts"]:
                artifact(reference)
    return TaskBrief(task_id, brief["issue_uid"], brief["base"], definition, digest(brief),
                     tuple(brief["allowed_writes"]), tuple(brief.get("exclusions", [])), brief["resources"],
                     brief["checks"], brief["retention"], brief.get("dependency_closures", {}))
