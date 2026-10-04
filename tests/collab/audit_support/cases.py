"""Ticket49 raw fact oracles, independently owned and fail closed."""
from __future__ import annotations
import hashlib
from datetime import datetime
import json
from pathlib import Path
import tomllib

from .evidence import (artifact, command_record, directory_snapshot, git_facts,
                       json_artifact, result_from_command, sqlite_projection,
                       check_native_schema, read_live_project)
from .facts import check_journal, content_digest, require, select_cases
from .raw_git import InvalidEvidence, run_git, sha256, strict_json, verify_materialization, verify_retention
from .runtime import bwrap_options, check_bwrap, check_measurements, rootfs_digest
from .conditions import check_boundary, check_refusal_cause, check_source_command, option, check_ignore_change
from .build import check_build
from .search_index import FTS_TABLES, check_physical_search_closure
from .recovery import reconstruct_queue


REFUSALS = {
    "dirty-tracked":{"DIRTY_SOURCE"}, "dirty-index":{"DIRTY_SOURCE"},
    "untracked":{"DIRTY_SOURCE"}, "wrong-ref":{"SOURCE_UNAVAILABLE","UNADMITTED_SPEC"},
    "wrong-root":{"SOURCE_UNAVAILABLE","UNADMITTED_SPEC","DIRTY_SOURCE"},
    "alias":{"SOURCE_UNAVAILABLE","UNADMITTED_SPEC","DIRTY_SOURCE"},
    "unpinned-task":{"UNADMITTED_SPEC"}, "branch-only-spec":{"UNADMITTED_SPEC"}}
DURABILITY = {"prepared-event","immutable-record","projection","event-fsync",
              "record-fsync","parent-fsync","disk-full","result-fsync"}
CORRUPTION = {"torn-tail","earlier-corruption","input-digest-reuse","fsync-failure"}
RESOURCE_CLOSURE = {"sources.py","command.py","stage.py","kernel_scope.py",
                    "scoped_stage.py","stage_accounting.py","execute_worker.py","process_lifecycle.py"}


def manifest(case: Path) -> dict:
    oracle = strict_json(case/"independent-oracle.json")
    root = Path(oracle["raw_root"])
    require(root.is_absolute() and root.is_dir(),"Actual owned raw fixture root required")
    return json_artifact(oracle["fixture_manifest"])


def source_runtime(case, admission, materialization, **_):
    inputs = strict_json(case/"independent-oracle.json")
    runtime = admission["runtime"]
    require(rootfs_digest(Path(runtime["rootfs_path"]))==runtime["rootfs_sha256"],
            "Actual independently rebuilt rootfs changed")
    lock = json_artifact(runtime["lock"])
    require(lock["rootfs_sha256"]==runtime["rootfs_sha256"],"Rootfs lock identity mismatch")
    require({"pipeline/insula_entry.py","pipeline/runtime_identity.py"}<=set(lock["helpers"]),
            "Frozen additive entry import closure missing")
    for relative,digest in lock["helpers"].items():
        path=Path(relative)
        require(not path.is_absolute() and ".." not in path.parts and
                sha256(Path(runtime["reference_path"])/path)==digest,"Actual frozen reference helper changed")
    source = Path(materialization["source"])
    for key,name in (("dockerfile_sha256","Dockerfile"),("requirements_sha256","requirements.lock")):
        path = source/"experiments/collaboration/runtime"/name
        require(sha256(path)==lock[key],"Candidate additive recipe/lock differs")
    for label in ("pre_source_manifest","post_source_manifest"):
        recorded = json_artifact(inputs[label])
        require(recorded["candidate"]==materialization["candidate"] and
                recorded["tree"]==materialization["tree"] and
                recorded["entries"]==materialization["entries"],"Pre/post raw source manifest mismatch")
    proof = json_artifact(inputs["resource_proof"])
    require(proof["schema_version"]==1 and proof["cap_bytes"]==runtime["cap_bytes"] and
            proof["timeout_seconds"]==runtime["timeout_seconds"],"Exact resource bounds differ")
    original = proof["original_command"]
    output = proof["native_output_directory"]
    check_bwrap(original,runtime["rootfs_path"],materialization["source"],runtime["reference_path"],output)
    options,native_worker = bwrap_options(original)
    separator = original.index("--")
    pins = proof["source_pins"]
    require(RESOURCE_CLOSURE<=set(pins) and set(pins)==set(runtime["resource_sources"]),
            "Complete independently pinned resource import closure required")
    roots = set()
    for name,pin in pins.items():
        for key in ("original","snapshot"):
            path = artifact({"path":pin[key],"sha256":pin["sha256"]})
        admitted = runtime["resource_sources"][name]
        require(admitted["sha256"]==pin["sha256"] and admitted["path"] in
                (pin["original"],pin["snapshot"]),"Resource source admission mismatch")
        artifact(admitted)
        roots.add(Path(pin["snapshot"]).parents[len(Path(name).parts)-1])
    require(len(roots)==1,"One complete frozen resource wrapper root required")
    resource_root = str(roots.pop())
    worker_path = artifact(proof["artifacts"]["worker_resource"])
    worker_output = worker_path.parent
    wrapped = original[:separator]+["--ro-bind",resource_root,"/tmp/resource-layer",
        "--bind",str(worker_output),"/tmp/resource-output","--",native_worker[0],
        "/tmp/resource-layer/execute_worker.py","/tmp/resource-output",*native_worker[1:]]
    require(proof["command"]==wrapped and proof["worker_argv"]==native_worker[1:],
            "Actual resource wrapper argv differs from literal independent reconstruction")
    worker = json.loads(worker_path.read_text())
    require(worker==proof["worker_measurement"],"Actual worker resource bytes differ")
    check_measurements(proof["host_measurement"],worker,wrapped,native_worker[1:],
                       runtime["cap_bytes"],runtime["timeout_seconds"])
    retained_log = artifact(proof["artifacts"]["execution_log"])
    require(proof["artifacts"]["execution_log"]["native_path"]==str(Path(output)/"live.log") and
            sha256(Path(output)/"live.log")==sha256(retained_log),"Native log differs from retained resource log")
    actual = command_record(case/"actual-command.json")
    require(actual["argv"]==wrapped and actual["exit_code"]==0 and
            actual["stdout"]["sha256"]==sha256(retained_log),"Actual wrapped execution/log/exit differs")
    build = json_artifact(inputs["build_manifest"])
    require(build["dockerfile_sha256"]==lock["dockerfile_sha256"] and
            build["requirements_sha256"]==lock["requirements_sha256"] and
            build["rootfs_sha256"]==runtime["rootfs_sha256"],"Actual build recipe/rootfs binds wrong runtime")
    check_build(build,lock,source,Path(runtime["rootfs_path"]),admission)
    return {"rootfs_sha256":runtime["rootfs_sha256"],"scope":proof["host_measurement"]["kernel_scope"]["path"],
            "cap_bytes":runtime["cap_bytes"],"resource_sources":len(pins),"native_log_sha256":sha256(retained_log)}


def clean_refusals(case, admission, materialization, **_):
    data = manifest(case)
    require(REFUSALS.keys()<=data["scenarios"].keys(),"Missing dirty/ref/path refusal scenarios")
    facts = {}
    for name,reasons in REFUSALS.items():
        probe = data["scenarios"][name]
        before = json_artifact(probe["pre_git_facts_path"])
        after = json_artifact(probe["post_git_facts_path"])
        require(before==after and after==git_facts(Path(probe["fixture_root"])),
                "Refusal mutated Git source/ref or recorded post facts are false")
        command = command_record(artifact(probe["actual_command_path"]))
        check_refusal_cause(name,probe,before,command,materialization,admission)
        result = result_from_command(command)
        require(result["outcome"]=="refused" and result.get("reason") in reasons,
                "Wrong actual refusal outcome/reason for "+name)
        status = bytes.fromhex(before["status_z_hex"])
        if name=="dirty-tracked":
            require(b" M " in status,"No actual tracked modification fixture")
        elif name=="dirty-index":
            require(any(line[:1] in (b"A",b"M",b"D") for line in status.split(b"\0")),
                    "No actual dirty index fixture")
        elif name=="untracked":
            require(b"?? " in status,"No actual untracked fixture")
        elif name=="wrong-ref":
            require(before["ref"]!="refs/heads/phi9t/mainline","Wrong-ref fixture uses admitted ref")
        if "after_state" in probe:
            state = directory_snapshot(probe["after_state"])
            journal = check_journal(state,allow_incomplete=True)
            for path in (state/"records").glob("*.json"):
                record = strict_json(path)
                require(record.get("kind") not in ("launch","start","turn-start","ref-update"),
                        "Refusal caused dispatch/ref effect")
        facts[name] = {"reason":result["reason"],"head":after["head"],"refs":after["refs"]}
    return facts


def fault_records(reference, scenario, errno=None):
    lines = [json.loads(line) for line in artifact(reference).read_text().splitlines() if line.strip()]
    require(lines and any(line.get("boundary")==scenario and line.get("event") in
                         {"raised","interrupted"} for line in lines),"Actual injected fault boundary absent")
    if errno is not None:
        require(any(line.get("boundary")==scenario and line.get("errno")==errno for line in lines),
                "Actual expected I/O errno absent")


def durable(case, admission, materialization, **_):
    data = manifest(case)
    require(DURABILITY<=set(data["scenarios"]),"Missing durability boundaries")
    admitted_device = admission["state_filesystem"]["device"]
    require(Path(admission["state_filesystem"]["path"]).stat().st_dev==admitted_device,
            "Configured state filesystem device changed")
    facts = {}
    for name in sorted(DURABILITY):
        probe = data["scenarios"][name]
        before = directory_snapshot(probe["before_state"])
        interrupted = directory_snapshot(probe["interrupted_state"])
        after = directory_snapshot(probe["after_state"])
        require(before.stat().st_dev==interrupted.stat().st_dev==after.stat().st_dev==admitted_device,
                "Durability tested on another filesystem")
        fault_records(probe["fault_log"],name,28 if name=="disk-full" else 5 if "fsync" in name else None)
        operation = command_record(artifact(probe["actual_command_path"]))
        argv=check_source_command(operation,materialization,admission,probe=name)
        require(option(argv,"--operation-id")==probe["operation_id"],"Fault trace not bound to invoked operation")
        trace=[json.loads(line) for line in artifact(probe["fault_log"]).read_text().splitlines() if line]
        pending=check_boundary(before,interrupted,name,probe["operation_id"],trace)
        require(operation["exit_code"]!=0,"Injected failure incorrectly reported successful operation")
        recovered = result_from_command(command_record(artifact(probe["reconcile_command_path"])))
        if name=="result-fsync":
            require(recovered["outcome"] in {"refused","unknown"},"Unfsynced result was promoted to success")
        try:
            derived = check_journal(after)
        except (InvalidEvidence,OSError):
            require(recovered["outcome"] in {"refused","unknown"},"Corrupt state was projected as success")
            derived = {"refused":True}
        else:
            require(recovered["outcome"] in {"ok","refused","unknown"},"Invalid recovery result")
            for effect in pending["unresolved_effects"]:
                if effect in derived["results"]:
                    result = strict_json(after/"records"/(derived["results"][effect]+".json"))
                    require(result["facts"]["outcome"]!="ok","Intent alone manufactured successful effect")
        facts[name] = derived
    holder = command_record(artifact(data["lock_holder_command"]))
    contender = command_record(artifact(data["lock_contender_command"]))
    check_source_command(holder,materialization,admission,probe="lock-holder")
    check_source_command(contender,materialization,admission,probe="lock-contender")
    result = result_from_command(contender)
    events = json_artifact(data["lock_events"])["events"]
    acquired = [x for x in events if x["event"]=="acquired"]
    released = [x for x in events if x["event"]=="released"]
    require(len(acquired)==len(released)==1,"Actual exclusive holder lifecycle absent")
    first,last = acquired[0],released[0]
    require(first["device"]==admitted_device and first["device"]==last["device"] and
            first["inode"]==last["inode"] and first["pid"]==last["pid"] and
            first["timestamp_ms"]<=contender["started_ms"]<=contender["ended_ms"]<=last["timestamp_ms"],
            "Second controller did not actually contend while lock held")
    require(holder["exit_code"]==0 and result["outcome"]=="refused" and
            result.get("reason") in {"OWNER_CONFLICT","UNKNOWN_EFFECT"},"Actual lock contender not refused")
    require(Path(first["path"]).stat().st_dev==first["device"] and
            Path(first["path"]).stat().st_ino==first["inode"],"Lock device/inode changed")
    return {"boundaries":facts,"lock_device":first["device"],"lock_inode":first["inode"]}


def corruption(case, admission, materialization, **_):
    data = manifest(case)
    require(CORRUPTION<=set(data["scenarios"]),"Missing journal corruption scenarios")
    facts = {}
    for name in sorted(CORRUPTION):
        probe = data["scenarios"][name]
        before = directory_snapshot(probe["interrupted_state"])
        after = directory_snapshot(probe["after_state"])
        initial=directory_snapshot(probe["before_state"])
        original=check_journal(initial,allow_incomplete=True)
        require(original["sequence"]>0,"Corruption fixture has no earlier valid committed history")
        command=command_record(artifact(probe["reconcile_command_path"]))
        check_source_command(command,materialization,admission,probe=name)
        result = result_from_command(command)
        if name=="torn-tail":
            prefix = check_journal(before,allow_incomplete=True)
            require(prefix["head"]==original["head"] and prefix["sequence"]==original["sequence"],
                    "Torn fixture changed earlier valid history")
            require(prefix["torn_tail_sha256"] is not None,"Fixture has no torn tail")
            derived = check_journal(after)
            tail = after/"incidents"/(prefix["torn_tail_sha256"]+".tail")
            require(tail.is_file() and sha256(tail)==prefix["torn_tail_sha256"],"Original torn bytes not retained")
            require(derived["sequence"]==prefix["sequence"] and derived["head"]==prefix["head"] and
                    derived["effects"]==prefix["effects"] and derived["results"]==prefix["results"],
                    "Torn tail recovery invented or lost history")
        elif name=="earlier-corruption":
            try:
                check_journal(before,allow_incomplete=True)
            except InvalidEvidence:
                pass
            else:
                raise InvalidEvidence("Earlier corruption fixture is actually valid")
            require(result["outcome"] in {"refused","unknown"} and
                    (before/"events.jsonl").read_bytes()==(after/"events.jsonl").read_bytes(),
                    "Earlier history corruption silently mutated or accepted")
        elif name=="input-digest-reuse":
            first = check_journal(before); second = check_journal(after)
            require(first==second and result["outcome"]=="refused","Operation-ID input mismatch was replayed")
            requested = json_artifact(probe["requested_inputs"])
            records = [strict_json(path) for path in (before/"records").glob("*.json")]
            require(any(record.get("record_type")=="Effect" and
                        record["input_digest"]!=content_digest(requested) for record in records),
                    "Reuse fixture did not change canonical inputs")
        else:
            fault_records(probe["fault_log"],name,5)
            trace=[json.loads(line) for line in artifact(probe["fault_log"]).read_text().splitlines() if line]
            check_boundary(initial,before,name,probe["operation_id"],trace)
            require(result["outcome"] in {"refused","unknown"},"Failed fsync projects success")
            check_journal(after,allow_incomplete=True)
        facts[name] = {"outcome":result["outcome"],"journal_sha256":sha256(after/"events.jsonl")}
    return facts


def selected_projection(database: dict, uid: str) -> dict:
    projects = [row for row in database["projects"] if row["uid"]==uid]
    require(len(projects)==1,"Selected project missing or duplicated")
    project = projects[0]
    issues = [row for row in database["issues"] if row["project_id"]==project["id"]]
    issue_uids = {row["uid"] for row in issues}
    links = [row for row in database["links"] if
             row["from_issue_uid"] in issue_uids or row["to_issue_uid"] in issue_uids]
    require(all(row["from_issue_uid"] in issue_uids and row["to_issue_uid"] in issue_uids for row in links),
            "Cross-project links cannot enter scoped queue recovery")
    # Numeric PKs and export/import revision bookkeeping may differ; scientific task data may not.
    public = [{key:value for key,value in row.items() if key not in {"id","project_id"}} for row in issues]
    relations = [(row["from_issue_uid"],row["to_issue_uid"],row["type"]) for row in links]
    return {"project_uid":project["uid"],"project_name":project["name"],
            "issues":sorted(public,key=lambda row:row["uid"]),"links":sorted(relations)}


def queue_restore(case, admission=None, reconstruction_root=None, **_):
    data = manifest(case)
    source = sqlite_projection(data["source_db"])
    restored = sqlite_projection(data["restored_db"])
    baseline = sqlite_projection(data["native_baseline_db"])
    if admission is not None:
        for database in (source,restored,baseline):
            check_native_schema(database,admission)
    uid = data["selected_project_uid"]
    chosen = selected_projection(source,uid)
    actual = selected_projection(restored,uid)
    require(chosen==actual,"Restored queue issue/metadata/dependency projection differs")
    native_uid="00000000000000000000000000"
    require(len(baseline["projects"])==1 and baseline["projects"][0]["id"]==1 and
            baseline["projects"][0]["uid"]==native_uid and baseline["projects"][0]["name"]==".kata-system" and
            not baseline["issues"] and not baseline["links"],"Actual empty native baseline sentinel missing")
    if "metadata" in baseline["projects"][0]:
        require(json.loads(baseline["projects"][0]["metadata"])=={},"Native sentinel metadata contains payload")
    native=[row for row in restored["projects"] if row["uid"]==native_uid]
    require(len(native)==1,"Mandatory native sentinel missing or duplicated")
    volatile={"id","created_at","updated_at"}
    require(type(native[0]["id"]) is int and native[0]["id"]>0 and
            len({row["id"] for row in restored["projects"]})==len(restored["projects"]),
            "Native sentinel numeric identity invalid or collides")
    require({k:v for k,v in native[0].items() if k not in volatile}==
            {k:v for k,v in baseline["projects"][0].items() if k not in volatile},
            "Mandatory native sentinel payload changed during restore")
    for row in (native[0],baseline["projects"][0]):
        for field in {"created_at","updated_at"} & row.keys():
            value=row[field]
            require(isinstance(value,str) and value.endswith("Z") and
                    datetime.fromisoformat(value.removesuffix("Z")+"+00:00").utcoffset().total_seconds()==0,
                    "Native sentinel initialization timestamp is invalid")
    require(any(row["uid"] not in {uid,native_uid} for row in source["projects"]),
            "No foreign-project exclusion control in source fixture")
    require({row["uid"] for row in restored["projects"]}=={uid,native_uid} and
            {row["uid"] for row in restored["issues"]}=={row["uid"] for row in chosen["issues"]},
            "Foreign project/issue rows restored")
    require(all(row["from_issue_uid"] in {i["uid"] for i in chosen["issues"]} and
                row["to_issue_uid"] in {i["uid"] for i in chosen["issues"]} for row in restored["links"]),
            "Foreign relations restored")
    require(scope_search_projection(source,uid)==scope_search_projection(restored,uid),
            "Restored project search semantics differ from selected source issues/comments")
    require(restored["meta"].get("instance_uid") and restored["meta"]["instance_uid"]!=source["meta"].get("instance_uid"),
            "Restore reused source instance ownership")
    exported = artifact(data["export"]).read_bytes()
    require(uid.encode() in exported,"Actual project export does not contain selected UID")
    foreign = {row["uid"] for row in source["projects"] if row["uid"]!=uid} | {
               row["uid"] for row in source["issues"] if row["uid"] not in {i["uid"] for i in chosen["issues"]}}
    require(all(value.encode() not in exported for value in foreign),"Actual export leaked foreign UIDs")
    export = command_record(artifact(data["actual_export_command"]))
    import_ = command_record(artifact(data["actual_import_command"]))
    require(export["exit_code"]==import_["exit_code"]==0,"Actual export/import failed")
    selected_id = next(row["id"] for row in source["projects"] if row["uid"]==uid)
    require("--project-id" in export["argv"] and export["argv"][export["argv"].index("--project-id")+1]==str(selected_id),
            "Actual export was not project-scoped")
    require("--new-instance" in import_["argv"] and "--force" not in import_["argv"] and
            "--target" in import_["argv"] and import_["argv"][import_["argv"].index("--target")+1]==data["restored_db"]["path"],
            "Actual restore not scoped to fresh isolated target")
    require("--input" in import_["argv"] and
            import_["argv"][import_["argv"].index("--input")+1]==data["export"]["path"],
            "Actual restored input differs from retained export")
    recovery=None;receipt=None
    if restored['search_index'] is not None:
        require(admission is not None and reconstruction_root is not None,
                'Native physical closure requires admitted tool and fresh audit-owned replay root')
        tool=admission['tools']['kata']
        require(export['argv'][0]==import_['argv'][0]==str(artifact(tool)),
                'Source export/import tool differs from independently pinned native executable')
        recovery,receipt=reconstruct_queue(data['export'],tool,Path(reconstruction_root),admission['authors']['auditor'])
        require(recovery['meta']['instance_uid'] not in
                {source['meta']['instance_uid'],restored['meta']['instance_uid']},
                'Independent native reconstruction reused existing instance identity')
        check_native_schema(recovery,admission)
    check_auxiliary_closure(source,restored,baseline,uid,recovery)
    return {"project_uid":uid,"issue_uids":sorted(row["uid"] for row in chosen["issues"]),
            "links":actual["links"],"restored_instance_uid":restored["meta"]["instance_uid"],
            "search_index_sha256":content_digest(scope_search_projection(restored,uid)),
            'independent_native_reconstruction':receipt}


def scope_search_projection(database,uid):
    facts=database["search_index"]
    if facts is None:
        return None
    project=next(row for row in database["projects"] if row["uid"]==uid)
    issues={row["id"]:row["uid"] for row in database["issues"] if row["project_id"]==project["id"]}
    return {"documents":sorted(issues[doc] for doc in facts["documents"] if doc in issues),
            "instances":sorted([term,issues[doc],column,offset] for term,doc,column,offset in facts["instances"]
                               if doc in issues),
            "document_sizes":sorted([issues[doc],size] for doc,size in facts["document_sizes"] if doc in issues),
            "config":facts["config"]}


def check_auxiliary_closure(source,restored,baseline,uid,independent_recovery=None):
    project=next(row for row in source["projects"] if row["uid"]==uid)
    target=next(row for row in restored["projects"] if row["uid"]==uid)
    require({k:v for k,v in project.items() if k!="id"}==
            {k:v for k,v in target.items() if k!="id"},"Selected project metadata changed during restore")
    source_issues={row["id"]:row["uid"] for row in source["issues"] if row["project_id"]==project["id"]}
    target_issues={row["id"]:row["uid"] for row in restored["issues"] if row["project_id"]==target["id"]}
    def belongs(row,pid,issues):
        checked=False
        for key in ("project_id","issue_id","related_issue_id","from_issue_id","to_issue_id"):
            value=row.get(key)
            if value is None:
                continue
            checked=True
            if key=="project_id" and value!=pid:
                return False
            if key!="project_id" and value not in issues:
                return False
        return checked
    def normalize(row,pid,issues):
        result={key:value for key,value in row.items() if key!="id"}
        for key in ("project_id","issue_id","related_issue_id","from_issue_id","to_issue_id"):
            if result.get(key) is not None:
                result[key]=uid if key=="project_id" else issues[result[key]]
        return result
    # Source segments contain other projects and historical updates. Recovered
    # segments instead must exactly match a separately executed fresh import,
    # including current shadow rows with search-invisible deleted payload.
    check_physical_search_closure(restored,independent_recovery)
    ignored={"projects","issues","links","meta"}|FTS_TABLES
    for table,rows in restored["tables"].items():
        if table in ignored:
            continue
        base=baseline["tables"].get(table,[])
        new=[row for row in rows if row not in base]
        require(all(belongs(row,target["id"],target_issues) for row in new),
                "Unbound/foreign auxiliary restored row: "+table)
        selected=[row for row in source["tables"].get(table,[]) if belongs(row,project["id"],source_issues)]
        actual=[normalize(row,target["id"],target_issues) for row in new]
        expected=[normalize(row,project["id"],source_issues) for row in selected]
        require(sorted(actual,key=lambda row:json.dumps(row,sort_keys=True))==
                sorted(expected,key=lambda row:json.dumps(row,sort_keys=True)),
                "Selected auxiliary row closure differs: "+table)


def issue_definitions(database, uid):
    selected = selected_projection(database,uid)
    definitions = {}
    for issue in selected["issues"]:
        metadata = json.loads(issue["metadata"])
        if "sureal_task" not in metadata:
            continue
        task = metadata["sureal_task"]
        require(task not in definitions,"Duplicate stable task issue")
        definition = metadata["sureal_definition"]
        if isinstance(definition,str):
            definition = json.loads(definition)
        require(definition["task_id"]==task and
                definition["revision"]==content_digest({k:v for k,v in definition.items() if k!="revision"}),
                "Stored definition task/revision invalid")
        definitions[task] = {"issue_uid":issue["uid"],"definition":definition}
    return definitions


def verify_definition(definition, repository):
    require(type(definition["schema_version"]) is int and definition["schema_version"]==1,
            "Unsupported task definition schema")
    for field in ("spec","plan"):
        pin = definition[field]
        require(pin["path"].startswith("docs/") and ".." not in Path(pin["path"]).parts,
                "Task authority path outside committed docs")
        actual = run_git(repository,"rev-parse",definition["source_commit"]+":"+pin["path"]).decode().strip()
        raw = run_git(repository,"cat-file","blob",actual)
        require(actual==pin["blob"] and hashlib.sha256(raw).hexdigest()==pin["sha256"],
                "Task spec/plan blob/content identity false")


def fixture_import(case, materialization, admission, **_):
    data = manifest(case); uid = data["selected_project_uid"]
    before_facts=json_artifact(data["definition_pre_git_facts"])
    after_facts=json_artifact(data["definition_post_git_facts"])
    retained=verify_retention(artifact(data["definition_retention"]),after_facts["head"])
    definition_repository=Path(retained["repository"])
    require(after_facts==git_facts(Path(data["definition_repository"])) and
            all(before_facts[key]==after_facts[key] for key in ("root","common_git_dir","ref")) and
            before_facts["ref"]=="refs/heads/phi9t/mainline" and
            before_facts["status_z_hex"]==after_facts["status_z_hex"]=="",
            "Definition revision not proven on an owned clean fixture mainline")
    run_git(definition_repository,"merge-base","--is-ancestor",before_facts["head"],after_facts["head"])
    first_db = sqlite_projection(data["first_db"])
    second_db = sqlite_projection(data["second_db"])
    revised_db = sqlite_projection(data["revised_db"])
    for database in (first_db,second_db,revised_db):
        check_native_schema(database,admission)
    first = issue_definitions(first_db,uid); second = issue_definitions(second_db,uid)
    revised = issue_definitions(revised_db,uid)
    expected = json_artifact(data["definitions"])["tasks"]
    require(first and set(first)==set(expected)==set(second)==set(revised),"Fixture task union differs")
    require(first==second,"Repeated import duplicated or rewrote pinned issues")
    require({task:record["issue_uid"] for task,record in first.items()}==
            {task:record["issue_uid"] for task,record in revised.items()},"Revision created replacement issue UID")
    changed = [task for task in first if first[task]["definition"]!=revised[task]["definition"]]
    require(changed,"Revision control did not actually change any definition")
    for task,record in first.items():
        require(record["definition"]==expected[task],"Actual stored task definition differs from admitted source")
        verify_definition(record["definition"],definition_repository)
        run_git(definition_repository,"merge-base","--is-ancestor",record["definition"]["source_commit"],before_facts["head"])
    for record in revised.values():
        verify_definition(record["definition"],definition_repository)
        run_git(definition_repository,"merge-base","--is-ancestor",record["definition"]["source_commit"],after_facts["head"])
    for database,definitions in ((first_db,first),(second_db,second),(revised_db,revised)):
        expected_edges = {(definitions[dep]["issue_uid"],definitions[task]["issue_uid"],"blocks")
                          for task,value in definitions.items() for dep in value["definition"]["dependencies"]}
        actual_edges = {tuple(edge) for edge in selected_projection(database,uid)["links"] if edge[2]=="blocks"}
        require(expected_edges==actual_edges,"Actual blocked-by links differ from task dependencies")
    require(artifact(data["old_brief_before"]).read_bytes()==artifact(data["old_brief_after"]).read_bytes(),
            "Already-running old brief was silently rewritten")
    require(sqlite_projection(data["status_before_db"])["tables"]==
            sqlite_projection(data["status_after_db"])["tables"],"Read-only status mutated Kata tables")
    if "status_before_state" in data:
        before = json_artifact(data["status_before_state"])
        after = json_artifact(data["status_after_state"])
        require(before["files"]==after["files"],"Read-only status mutated controller state")
        directory_snapshot(data["status_before_state"]);directory_snapshot(data["status_after_state"])
    commands = [command_record(artifact(ref)) for ref in data["commands"]]
    require(len(commands)>=5 and all(command["exit_code"]==0 for command in commands),
            "Actual import/revision/status command effects incomplete")
    require(any("--if-match" in command["argv"] for command in commands),
            "Revision control did not use actual conditional metadata assignment")
    return {"task_uids":{task:value["issue_uid"] for task,value in first.items()},"revised_tasks":changed}


def map_gate(case, materialization, admission, **_):
    data=manifest(case)
    repository=Path(materialization["repository"])
    parent=materialization["parent"];candidate=materialization["candidate"]
    changed=run_git(repository,"diff","--name-only","-z",parent,candidate).split(b"\0")
    paths={path.decode() for path in changed if path}
    require(paths and paths<={".kata.toml",".gitignore","docs/research/kata-task-map.json"},
            "Metadata candidate escapes binding/map-only scope")
    entries={entry["path"]:entry for entry in materialization["entries"]}
    require(all(entries.get(path,{}).get("mode")=="100644" for path in paths),
            "Metadata type/mode changes are not authorized")
    source=Path(materialization["source"])
    if ".gitignore" in paths:
        require(run_git(repository,"ls-tree",parent,"--",".gitignore").startswith(b"100644 blob "),
                "Metadata changed existing ignore path type")
        check_ignore_change(run_git(repository,"show",parent+":.gitignore"),(source/".gitignore").read_bytes())
    mapping=strict_json(source/"docs/research/kata-task-map.json")
    require(set(mapping)=={"schema_version","project","binding","source_commit","tasks"},
            "Mutable queue/owner/status cannot enter task map")
    require(mapping["source_commit"]==parent and mapping["binding"]["path"]==".kata.toml" and
            mapping["binding"]["sha256"]==sha256(source/".kata.toml"),"Actual binding/source pin differs")
    binding=tomllib.loads((source/".kata.toml").read_text())
    def scalars(value):
        if isinstance(value,dict):
            return [item for child in value.values() for item in scalars(child)]
        if isinstance(value,list):
            return [item for child in value for item in scalars(child)]
        return [value]
    require(mapping["project"]["uid"] in scalars(binding) or mapping["project"]["name"] in scalars(binding),
            "Actual parsed Kata binding does not identify project")
    database=sqlite_projection(data["project_db"])
    check_native_schema(database,admission)
    require(selected_projection(read_live_project(Path(admission["kata"]["db_path"]),mapping["project"]["uid"]),
                                mapping["project"]["uid"])==selected_projection(database,mapping["project"]["uid"]),
            "Actual selected live project differs from retained scoped snapshot")
    actual=issue_definitions(database,mapping["project"]["uid"])
    project=next(row for row in database["projects"] if row["uid"]==mapping["project"]["uid"])
    require(all(project[key]==mapping["project"][key] for key in ("id","uid","name")),
            "Live project identity differs from map")
    required={str(value) for value in range(44,55)}|{"53.0","53.A","53.B"}
    require(set(mapping["tasks"])==required and required<=set(actual),"Required initial task import incomplete")
    for task,entry in mapping["tasks"].items():
        require(set(entry)=={"issue_uid","definition_revision","spec","plan","dependencies"},
                "Task map contains mutable state or missing authority")
        record=actual[task];definition=record["definition"]
        require(entry["issue_uid"]==record["issue_uid"] and
                entry["definition_revision"]==definition["revision"] and
                all(entry[field]==definition[field] for field in ("spec","plan","dependencies")) and
                definition["source_commit"]==parent,"Actual issue/spec/plan pin differs from map")
        verify_definition(definition,repository)
    expected_edges={(actual[dep]["issue_uid"],actual[task]["issue_uid"],"blocks")
                    for task in required for dep in actual[task]["definition"]["dependencies"]}
    observed_edges={tuple(edge) for edge in selected_projection(database,project["uid"])["links"] if edge[2]=="blocks"}
    require(expected_edges==observed_edges,"Live project dependencies differ from committed map")
    return {"map_sha256":sha256(source/"docs/research/kata-task-map.json"),
            "binding_sha256":sha256(source/".kata.toml"),"project_uid":project["uid"],"task_count":len(required)}


def accepted_report(reference, *, candidate, role, phase, admission=None):
    value=json_artifact(reference)
    require(value.get("kind")=="independent-collaboration-audit" and value.get("ticket")=="49" and
            value.get("phase")==phase and value.get("candidate_role")==role and
            value.get("candidate")==candidate and value.get("accepted") is True and
            value.get("status")=="pass" and value.get("phase_complete") is True,
            "No complete independently accepted matching prior phase")
    require(value["cases"],"Empty flag-only report is not phase acceptance")
    require(admission is not None,"Prior audit receipt must be explicitly independently admitted")
    prior=admission["prior_acceptances"][role][phase]
    require(prior==reference,"Prior acceptance digest not admitted by lead authority")
    coverage=json_artifact(admission["coverage"])
    required=select_cases(coverage,"49",phase,role)
    require(set(value["cases"])=={case["id"] for case in required},"Prior phase coverage incomplete")
    require(value["coverage_sha256"]==admission["coverage"]["sha256"] and
            value["auditor"]["candidate"]==admission["auditor"]["candidate"] and
            value["auditor"]["materialization_sha256"]==admission["auditor"]["materialization"]["sha256"] and
            value["auditor"]["review_sha256"]==admission["auditor"]["review"]["sha256"],
            "Prior phase auditor/oracle/review authority differs")
    source=verify_materialization(artifact(value["materialization"]),candidate)
    original=json_artifact(value["gate_admission"])
    require(value["materialization_sha256"]==value["materialization"]["sha256"] and
            value["gate_admission_sha256"]==value["gate_admission"]["sha256"] and
            all(value[key]==source[key] for key in ("candidate","parent","tree")) and
            all(original["source"][key]==source[key] for key in ("candidate","parent","tree")) and
            original["source"]["materialization_sha256"]==value["materialization_sha256"],
            "Prior phase exact source/admission binding differs")
    verify_retention(artifact(original["source"]["retention"]),candidate)
    for expected in required:
        refs=value["cases"][expected["id"]]["raw_artifacts"]
        require(refs,"Prior case has no raw artifacts")
        for path in expected["required_raw_evidence"]:
            require(any(Path(ref["path"]).as_posix().endswith("/"+path) for ref in refs),
                    "Prior phase missing required raw artifact "+path)
    for case in value["cases"].values():
        for ref in case["raw_artifacts"]:
            artifact(ref)
    return value


def post_landing(case, admission, materialization, role, **_):
    data=manifest(case)
    candidate=materialization["candidate"]
    gate=accepted_report(data["accepted_gate_audit"],candidate=candidate,role=role,phase="gate",admission=admission)
    require(gate["tree"]==materialization["tree"] and gate["parent"]==materialization["parent"],
            "Prior gate context does not bind actual retained candidate")
    integration=admission["integration"]
    actual=git_facts(Path(integration["canonical"]))
    recorded=json_artifact(data["git_facts"])
    require(actual==recorded and actual["head"]==candidate and actual["tree"]==materialization["tree"] and
            actual["ref"]==integration["ref"] and actual["status_z_hex"]=="",
            "Actual post landing canonical source/ref/tree/index/cleanliness mismatch")
    disposition=json_artifact(data["ignored_disposition"])
    require(disposition["ignored_z_hex"]==actual["ignored_z_hex"] and
            disposition["submodule_status"]==actual["submodule_status"],
            "Ignored/submodule disposition missing or changed")
    prepared=json_artifact(data["prepared_landing"])
    require(prepared["base"]==materialization["parent"] and prepared["candidate"]==candidate and
            prepared["tree"]==materialization["tree"] and prepared["canonical"]==integration["canonical"],
            "Actual conditional landing intent differs")
    before=json_artifact(data["pre_git_facts"])
    require(before["head"]==materialization["parent"] and before["ref"]==actual["ref"] and
            before["status_z_hex"]=="","No actual clean exact-base landing precondition")
    landing=command_record(artifact(data["landing_command"]))
    require(landing["exit_code"]==0 and "--ff-only" in landing["argv"] and candidate in landing["argv"],
            "Actual exact fast-forward-only command missing")
    remote=None
    if integration["publication_policy"]=="required":
        publication=command_record(artifact(data["publication_command"]))
        require(publication["exit_code"]==0 and integration["remote"] in publication["argv"] and
                integration["remote_ref"] in publication["argv"] and "ls-remote" in publication["argv"],
                "Actual configured remote readback missing")
        stdout=artifact(publication["stdout"]).read_text().splitlines()
        require(stdout==[candidate+"\t"+integration["remote_ref"]],"Published remote/ref differs from candidate")
        remote=run_git(Path(integration["canonical"]),"ls-remote",integration["remote"],integration["remote_ref"]).decode().strip()
        require(remote==candidate+"\t"+integration["remote_ref"],"Fresh independent publication readback differs")
    else:
        require(integration["publication_policy"]=="local-only","Unknown publication policy")
    if role=="metadata":
        code=data["code_candidate"]
        run_git(Path(materialization["repository"]),"merge-base","--is-ancestor",code,candidate)
        require(sha256(Path(integration["canonical"])/".kata.toml")==
                sha256(Path(materialization["source"])/".kata.toml"),"Actual landed binding differs")
    return {"head":candidate,"tree":actual["tree"],"ref":actual["ref"],"remote_readback":remote}


def closeout(case, admission, materialization, role, **_):
    data=manifest(case)
    code=data["code_candidate"];mapping=data["map_candidate"]
    require(materialization["candidate"]==({"implementation":code,"metadata":mapping}[role]),
            "Closure exact source role differs")
    phase_refs=data["accepted_phases"]
    require(set(phase_refs)=={"implementation","metadata"},"Both bootstrap roles need complete acceptance")
    prior_reports={}
    for prior_role,candidate in (("implementation",code),("metadata",mapping)):
        require(set(phase_refs[prior_role])=={"gate","post-landing"},"Bootstrap phase acceptance incomplete")
        for phase in ("gate","post-landing"):
            prior_reports[(prior_role,phase)]=accepted_report(phase_refs[prior_role][phase],
                candidate=candidate,role=prior_role,phase=phase,admission=admission)
    retained={}
    for ref in data["retention"]:
        identity=json_artifact(ref)["candidate"]
        require(identity not in retained,"Duplicate closure retention identity")
        retained[identity]=verify_retention(artifact(ref),identity)
    require({code,mapping}<=set(retained),"Bootstrap code/map raw objects not retained")
    # M's pack contains X and M. X's immutable earlier pack cannot contain M.
    repository=Path(retained[mapping]["repository"])
    run_git(repository,"merge-base","--is-ancestor",code,mapping)
    mapping_source=verify_materialization(artifact(prior_reports[("metadata","gate")]["materialization"]),mapping)
    require(mapping_source["repository"]==str(repository),"Closure map source differs from retained M pack")
    mapped=strict_json(Path(mapping_source["source"])/"docs/research/kata-task-map.json")
    require(mapped["source_commit"]==mapping_source["parent"] and
            mapped["binding"]["path"]==".kata.toml" and mapped["binding"]["sha256"]==
            sha256(Path(mapping_source["source"])/".kata.toml"),"Closure raw M binding differs")
    project=sqlite_projection(data["project_db"])
    uid=data["selected_project_uid"]
    require(uid==mapped["project"]["uid"]==admission["kata"]["project_uid"],
            "Closure project is not the admitted committed M project")
    check_native_schema(project,admission)
    require(selected_projection(read_live_project(Path(admission["kata"]["db_path"]),uid),uid)==
            selected_projection(project,uid),"Actual live close/readback differs from retained scoped snapshot")
    definitions=issue_definitions(project,uid)
    definition=definitions["49"]["definition"];entry=mapped["tasks"]["49"]
    require(entry["issue_uid"]==definitions["49"]["issue_uid"] and
            entry["definition_revision"]==definition["revision"] and
            all(entry[key]==definition[key] for key in ("spec","plan","dependencies")) and
            definition["source_commit"]==mapped["source_commit"],"Closed issue definition differs from exact M map")
    verify_definition(definition,repository)
    task=next(row for row in selected_projection(project,uid)["issues"] if row["uid"]==definitions["49"]["issue_uid"])
    require(task["status"]=="closed" and task.get("closed_at"),"Actual49 issue not closed/read back")
    close=command_record(artifact(data["close_command"]))
    require(close["exit_code"]==0 and "close" in close["argv"] and
            definitions["49"]["issue_uid"] in close["argv"],"Actual evidence-backed Kata close command missing")
    context=json_artifact(data["kata_context"])
    require(all(context[key]==admission["kata"][key] for key in ("home","db_path","project_uid")) and
            context["workspace"]==admission["integration"]["canonical"],"Actual Kata closure context differs")
    health=json.loads(artifact(context["health"]).read_text())
    require(health["db_path"]==context["db_path"],"Actual daemon health points at different queue")
    require(close["argv"][0]==str(artifact(admission["tools"]["kata"])) and
            close["environment"]["KATA_HOME"]==context["home"] and
            close["cwd"]==context["workspace"],"Actual close command tool/home/workspace differs")
    bootstrap=command_record(artifact(data["bootstrap_command"]))
    require(bootstrap["exit_code"]==0 and "init" in bootstrap["argv"] and
            "--project" in bootstrap["argv"] and "--workspace" in bootstrap["argv"],
            "Actual manual bootstrap intent/command absent")
    intent=json_artifact(data["bootstrap_intent"])
    require(intent["workspace"]==option(bootstrap["argv"],"--workspace")==context["workspace"] and
            option(bootstrap["argv"],"--project") in {mapped["project"]["name"],uid},
            "Actual bootstrap workspace differs from prepared intent")
    integration=admission["integration"]
    actual=git_facts(Path(integration["canonical"]))
    require(actual["head"]==mapping and actual["ref"]==integration["ref"] and actual["status_z_hex"]=="",
            "Closure canonical map/source state differs")
    return {"closed_issue_uid":task["uid"],"project_uid":uid,"code_candidate":code,"map_candidate":mapping,
            "canonical_head":actual["head"],"closed_at":task["closed_at"]}


ORACLES={"exact-source-and-rootfs":source_runtime,"real-state-fs-durability":durable,
         "clean-ref-and-path-refusals":clean_refusals,"journal-corruption":corruption,
         "scoped-queue-restore":queue_restore,"fixture-import-revision-status":fixture_import,
         "map-M-gate":map_gate,"exact-stage-landing":post_landing,"map-M-landing":post_landing,
         "queue-bootstrap-revision-status":closeout}
