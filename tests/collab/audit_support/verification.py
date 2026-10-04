"""Authority binding and complete independently derived milestone audit."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import time

from .cases import ORACLES
from .evidence import artifact, command_record, json_artifact, nested_references
from .facts import content_digest, require, select_cases
from .raw_git import (InvalidEvidence, run_git, sha256, strict_json,
                      verify_materialization, verify_retention, write_new)


def collect_references(value, *, visited=None):
    visited=set() if visited is None else visited
    output=[]
    for ref in nested_references(value):
        key=(ref["path"],ref["sha256"])
        if key in visited:
            continue
        visited.add(key);output.append(ref)
        path=Path(ref["path"])
        if path.suffix==".json":
            # Native Kata/tool stdout is raw JSON without our protocol schema.
            # Spec/blob pins and source entries are authority data, not file references.
            content=json.loads(path.read_text())
            output.extend(collect_references(content,visited=visited))
    return output


def validate_authority(admission_path, materialization_path, candidate):
    admission=strict_json(admission_path)
    require(admission.get("kind")=="GateAdmission","Independent GateAdmission kind required")
    content_digest(admission)
    require(shutil.which("git")==str(artifact(admission["tools"]["git"])),
            "Actual independent raw Git tool differs from admitted executable")
    materialization=verify_materialization(materialization_path,candidate)
    pin=admission["source"]
    require(all(pin[key]==materialization[key] for key in ("candidate","parent","tree")) and
            pin["materialization_sha256"]==sha256(materialization_path),"Exact GateAdmission source binding mismatch")
    retained=verify_retention(artifact(pin["retention"]),candidate)
    require(retained["kind"]=="raw-retention" and retained["candidate"]==candidate and
            retained["repository"]==materialization["repository"],"Materialization not bound to retained cold Git objects")
    artifact({"path":retained["pack_path"],"sha256":retained["pack_sha256"]})
    run_git(Path(retained["repository"]),"fsck","--full","--no-reflogs")
    auditor=admission["auditor"]
    auditor_receipt=artifact(auditor["materialization"])
    auditor_source=verify_materialization(auditor_receipt,auditor["candidate"])
    require(str(Path(__file__).resolve().parents[3])==auditor_source["source"] and
            auditor.get("source")==auditor_source["source"],"Auditor must run from independently admitted exact source")
    review=json_artifact(auditor["review"])
    authors=admission["authors"]
    require(set(authors)=={"producer","auditor","reviewer"} and len(set(authors.values()))==3 and
            all(isinstance(value,str) and value for value in authors.values()),"Independent author/reviewer identity missing")
    require(review["candidate"]==auditor["candidate"] and review["verdict"]=="pass" and
            review["reviewer"]==authors["reviewer"] and review["author"]==authors["auditor"],
            "Independent auditor review provenance mismatch")
    coverage_path=artifact(admission["coverage"])
    require(sha256(Path(auditor_source["source"])/"docs/collaboration/coverage.json")==sha256(coverage_path),
            "Coverage differs from independently admitted oracle authority")
    coverage=strict_json(coverage_path)
    changed=run_git(Path(materialization["repository"]),"diff","--name-only","-z",
                    materialization["parent"],candidate).split(b"\0")
    protected=("tests/collab/audit_live.py","tests/collab/audit_support/","docs/collaboration/coverage.json",
               "docs/collaboration/checks/")
    require(all(not any(path.decode()==prefix or path.decode().startswith(prefix) for prefix in protected)
                for path in changed if path),"Producer changed independently admitted auditor/coverage authority")
    return admission,materialization,coverage,auditor_source


def audit(*,ticket,phase,role,candidate,materialization_path,admission_path,evidence,output,case_only=None):
    started=int(time.time()*1000)
    report={"schema_version":1,"kind":"independent-collaboration-audit","ticket":ticket,
            "phase":phase,"candidate_role":role,"candidate":candidate,"status":"fail",
            "accepted":False,"phase_complete":False,"cases":{},"started_ms":started}
    try:
        require(ticket=="49","A49 has no admitted future-ticket oracles")
        admission,materialization,coverage,auditor_source=validate_authority(
            admission_path,materialization_path,candidate)
        report.update({"parent":materialization["parent"],"tree":materialization["tree"],
            "materialization_sha256":sha256(materialization_path),"gate_admission_sha256":sha256(admission_path),
            "materialization":{"path":str(materialization_path),"sha256":sha256(materialization_path)},
            "gate_admission":{"path":str(admission_path),"sha256":sha256(admission_path)},
            "coverage_sha256":admission["coverage"]["sha256"],"auditor":{
                "candidate":admission["auditor"]["candidate"],
                "materialization_sha256":admission["auditor"]["materialization"]["sha256"],
                "review_sha256":admission["auditor"]["review"]["sha256"]}})
        selected=select_cases(coverage,ticket,phase,role)
        if case_only:
            selected=[case for case in selected if case["id"]==case_only]
            require(len(selected)==1,"Case outside authoritative phase/role")
        require(evidence.is_absolute() and evidence.is_dir(),"Actual absolute evidence directory required")
        expected_context={key:report[key] for key in ("ticket","phase","candidate_role","candidate","parent",
                            "tree","materialization_sha256","gate_admission_sha256")}
        for case in selected:
            case_dir=evidence/"cases"/case["id"]
            refs=[]
            for relative in case["required_raw_evidence"]:
                path=evidence/relative
                require(path.is_file() and not path.is_symlink(),"Missing required raw evidence: "+relative)
                refs.append({"path":str(path),"sha256":sha256(path)})
            context_paths=[case_dir/name for name in ("context.json","candidate-role-context.json","candidate-context.json")
                           if (case_dir/name).is_file()]
            require(context_paths,"Missing actual candidate/role context")
            context=strict_json(context_paths[0])
            require(all(context.get(key)==value for key,value in expected_context.items()),
                    "Exact per-case source/phase/role context mismatch")
            for path in case_dir.glob("*.json"):
                value=strict_json(path)
                refs.extend(collect_references(value))
            if (case_dir/"actual-command.json").is_file():
                command=command_record(case_dir/"actual-command.json")
                if (case_dir/"execution.log").is_file():
                    require(sha256(case_dir/"execution.log")==command["stdout"]["sha256"],
                            "Case execution.log differs from actual stdout")
            require(case["id"] in ORACLES,"No independently implemented oracle for required case")
            facts=ORACLES[case["id"]](case_dir,admission=admission,materialization=materialization,
                                      role=role,phase=phase)
            report["cases"][case["id"]]={"derived_facts":facts,
                "raw_artifacts":sorted({(ref["path"],ref["sha256"]) for ref in refs})}
            report["cases"][case["id"]]["raw_artifacts"]=[{"path":path,"sha256":digest}
                for path,digest in report["cases"][case["id"]]["raw_artifacts"]]
        # Cooperative host integrity is checked again after every external/readback oracle.
        verify_materialization(materialization_path,candidate)
        verify_materialization(artifact(admission["auditor"]["materialization"]),admission["auditor"]["candidate"])
        report.update(status="partial" if case_only else "pass",accepted=not bool(case_only),
                      phase_complete=not bool(case_only))
        exit_code=0
    except (InvalidEvidence,OSError,KeyError,TypeError,ValueError,IndexError) as error:
        report["reason"]=str(error)
        report["error_type"]=type(error).__name__
        exit_code=2
    report["ended_ms"]=int(time.time()*1000)
    write_new(output,report)
    return report,exit_code
