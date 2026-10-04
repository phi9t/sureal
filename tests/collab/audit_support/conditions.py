"""Cause, source-command and fault-boundary evidence, without product imports."""
from __future__ import annotations
import json
from pathlib import Path

from .evidence import json_artifact
from .facts import check_journal, require
from .raw_git import InvalidEvidence, run_git, strict_json


def translate(value, materialization, admission):
    path=Path(value)
    mappings={"/source":materialization["source"],"/experiment":admission["runtime"]["reference_path"],
              "/outputs":admission["runtime"]["native_output_directory"]}
    for alias,target in mappings.items():
        if path==Path(alias) or path.is_relative_to(alias):
            return Path(target)/path.relative_to(alias)
    return path


def option(argv, name):
    require(argv.count(name)==1 and argv.index(name)+1<len(argv),"Exactly one actual "+name+" input required")
    return argv[argv.index(name)+1]


def check_source_command(command, materialization, admission, *, probe=None):
    argv=command["argv"]
    require(len(argv)>=3 and Path(argv[0]).name.startswith("python"),"Actual Python source invocation required")
    script=translate(argv[1],materialization,admission)
    candidates=[Path(materialization["source"])/"scripts/collab.py"]
    if probe:
        candidates.append(Path(materialization["source"])/"scripts/collab_live.py")
    require(script in candidates and script.is_file(),"Actual command not bound to exact candidate entrypoint")
    if script.name=="collab_live.py":
        require("probe" in argv and probe in argv,"Probe argv does not bind actual scenario")
    return argv


def check_refusal_cause(name, probe, before, command, materialization, admission):
    argv=check_source_command(command,materialization,admission)
    if name in {"wrong-root","alias"}:
        configured=json_artifact(probe["admission_input"])
        require(configured["kind"]=="ProjectAdmission","Wrong admission cause fixture")
        invoked=translate(option(argv,"--canonical"),materialization,admission)
        declared=translate(configured["canonical"],materialization,admission)
        require(invoked.resolve()==Path(probe["fixture_root"]).resolve(),"Command canonical not bound to fixture")
        if name=="wrong-root":
            require(invoked.resolve()!=declared.resolve(),"No actual wrong-root cause")
        else:
            require(invoked.resolve()==declared.resolve() and
                    any(part.is_symlink() for part in [invoked,*invoked.parents]),"No actual symlink alias cause")
        require(translate(option(argv,"--admission"),materialization,admission)==Path(probe["admission_input"]["path"]),
                "Recorded admission input not consumed by actual command")
    elif name in {"unpinned-task","branch-only-spec"}:
        authority=json_artifact(probe["authority_input"])
        require(translate(option(argv,"--definitions"),materialization,admission)==Path(probe["authority_input"]["path"]),
                "Recorded definitions not consumed by actual command")
        definitions=authority["tasks"]
        rows=list(definitions.values()) if isinstance(definitions,dict) else definitions
        require(rows,"No actual task definition input")
        repository=Path(probe["fixture_root"])
        if name=="unpinned-task":
            incomplete=any(not isinstance(row,dict) or not row.get("source_commit") or
                any(not isinstance(row.get(key),dict) or not {"path","blob","sha256"}<=set(row[key])
                    for key in ("spec","plan")) for row in rows)
            require(incomplete,"No actual missing authority pin")
        else:
            branch_only=False
            for row in rows:
                source=row["source_commit"]
                run_git(repository,"cat-file","commit",source)
                try:
                    run_git(repository,"merge-base","--is-ancestor",source,before["head"])
                except InvalidEvidence:
                    branch_only=True
            require(branch_only,"Branch-only authority is actually mainline ancestry")
    else:
        invoked=translate(option(argv,"--canonical"),materialization,admission)
        require(invoked.resolve()==Path(probe["fixture_root"]).resolve(),"Actual command bound to another Git fixture")


def check_boundary(before, interrupted, name, operation_id, trace):
    require(trace and [line.get("sequence") for line in trace]==list(range(1,len(trace)+1)),
            "Ordered actual boundary trace required")
    require(all(line.get("operation_id")==operation_id for line in trace),"Fault trace belongs to another operation")
    relevant=[line for line in trace if line.get("boundary")==name]
    require(len(relevant)>=2 and relevant[0].get("event")=="call" and
            relevant[-1].get("event") in {"raised","interrupted"},"Fault was not an actual ordered call/raise")
    errno=28 if name=="disk-full" else 5 if "fsync" in name or name=="fsync-failure" else None
    if errno is not None:
        require(relevant[-1].get("event")=="raised" and relevant[-1].get("errno")==errno,
                "Actual boundary I/O error missing")
    first=check_journal(before,allow_incomplete=True)
    partial=check_journal(interrupted,allow_incomplete=True)
    old=(before/"events.jsonl").read_bytes() if (before/"events.jsonl").exists() else b""
    current=(interrupted/"events.jsonl").read_bytes() if (interrupted/"events.jsonl").exists() else b""
    require(current.startswith(old),"Boundary injection destroyed earlier committed history")
    require(partial["sequence"]>=first["sequence"] and
            all(partial["effects"].get(key)==value for key,value in first["effects"].items()) and
            all(partial["results"].get(key)==value for key,value in first["results"].items()),
            "Boundary injection changed existing effects/results")
    if name=="disk-full":
        require(relevant[0].get("relative_path")=="events.jsonl","ENOSPC not bound to journal append")
        return partial
    if name in {"result-fsync","fsync-failure"}:
        require(partial["sequence"]==first["sequence"]+1 and partial["effects"]==first["effects"] and
                partial["results"]==first["results"],"Failed result fsync changed committed effects/results")
        added=set(partial["uncommitted_results"])-set(first["uncommitted_results"])
        require(len(added)==1,"Failed result fsync must leave exactly one missing immutable result")
        effect_id=added.pop()
        require(effect_id in first["unresolved_effects"],"Result fault has no earlier unresolved intent")
        event=json.loads(current.splitlines()[-1])
        require(event["operation_id"]==operation_id and event["event"]=="result" and
                event["record"]["effect_id"]==effect_id and event["record"]["facts"]["outcome"]=="ok",
                "Fault not bound to actual success-asserting result event")
        require(strict_json(interrupted/"current.json")==strict_json(before/"current.json"),
                "Failed result fsync published current projection")
        return partial
    require(partial["sequence"]==first["sequence"]+1,"Named durable boundary never wrote exactly one prepared event")
    new=set(partial["effects"].values())-set(first["effects"].values())
    require(len(new)==1 and not(set(partial["results"])-set(first["results"])),
            "Boundary did not preserve exactly one unresolved prepared intent")
    record_id=new.pop()
    events=[json.loads(line) for line in current.splitlines()]
    require(events[-1]["operation_id"]==operation_id,"Prepared raw event belongs to different fault operation")
    exists=(interrupted/"records"/(record_id+".json")).is_file()
    if name in {"prepared-event","event-fsync","record-fsync","fsync-failure"}:
        require(not exists,"Interrupted boundary already published immutable record")
    elif name in {"immutable-record","parent-fsync","projection"}:
        require(exists,"Named immutable/projection boundary did not publish record")
    projection=interrupted/"current.json"
    if name=="projection":
        require(strict_json(projection)=={key:partial[key] for key in
                ("schema_version","head","sequence","effects","results")},"Projection boundary not actually reached")
    elif projection.exists():
        require(strict_json(projection)["sequence"]==first["sequence"],"Earlier boundary incorrectly published current projection")
    return partial


def check_ignore_change(old: bytes, new: bytes):
    lines=new.splitlines(keepends=True)
    additions=[line for line in lines if line.rstrip(b"\n")==b".kata.local.toml"]
    require(len(additions)==1 and b".kata.local.toml" not in old.splitlines(),
            "Metadata must add exactly one new authorized local-binding ignore line")
    preserved=b"".join(line for line in lines if line not in additions)
    require(preserved==old or (old and not old.endswith(b"\n") and preserved==old+b"\n"),
            "Metadata reordered, removed or changed existing ignore bytes")
