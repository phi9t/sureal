"""Reopen immutable artifact references and actual command/result bytes."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from .facts import require, parse_record
from .raw_git import InvalidEvidence, run_git, sha256, strict_json


def artifact(reference: dict) -> Path:
    require(isinstance(reference,dict) and "path" in reference and "sha256" in reference,
            "Actual immutable artifact reference required")
    path = Path(reference["path"])
    require(path.is_absolute() and path.is_file() and not path.is_symlink(),
            "Actual absolute regular artifact required")
    require(sha256(path)==reference["sha256"],"Raw artifact digest changed: "+str(path))
    return path


def json_artifact(reference: dict) -> dict:
    return strict_json(artifact(reference))


def nested_references(value) -> list[dict]:
    found = []
    if isinstance(value,dict):
        if "path" in value and "sha256" in value and not {"blob","oid"}.intersection(value):
            path = artifact(value)
            found.append({"path":str(path),"sha256":value["sha256"]})
        else:
            for child in value.values():
                found.extend(nested_references(child))
    elif isinstance(value,list):
        for child in value:
            found.extend(nested_references(child))
    return found


def command_record(path: Path) -> dict:
    command = strict_json(path)
    require(isinstance(command["argv"],list) and command["argv"] and
            all(isinstance(x,str) and x for x in command["argv"]),"Literal actual argv required")
    require(Path(command["cwd"]).is_absolute(),"Actual absolute cwd required")
    require(type(command["exit_code"]) is int and type(command["started_ms"]) is int and
            type(command["ended_ms"]) is int and command["ended_ms"]>=command["started_ms"],
            "Actual exit/time records required")
    artifact(command["stdout"]); artifact(command["stderr"])
    if "timeout_ms" in command:
        require(type(command["timeout_ms"]) is int and command["timeout_ms"]>0 and
                command["ended_ms"]-command["started_ms"]<=command["timeout_ms"],
                "Command timeout bound exceeded")
    return command


def result_from_command(command: dict) -> dict:
    path = artifact(command["stdout"])
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    require(len(lines)==1,"One bounded operation envelope required")
    try:
        value = parse_record(lines[0].encode())
    except ValueError as error:
        raise InvalidEvidence("Actual command envelope absent") from error
    require(isinstance(value,dict) and value.get("schema_version")==1 and
            value.get("outcome") in {"ok","refused","unknown"},"Invalid operation result envelope")
    expected = {"ok":0,"refused":2,"unknown":3}
    require(command["exit_code"]==expected[value["outcome"]],"Inner actual exit/envelope disagreement")
    return value


def git_facts(root: Path) -> dict:
    root = root.resolve()
    def text(*args):
        return run_git(root,*args).decode().strip()
    common = text("rev-parse","--path-format=absolute","--git-common-dir")
    index = Path(text("rev-parse","--path-format=absolute","--git-path","index"))
    refs = {}
    for line in text("for-each-ref","--format=%(refname) %(objectname)").splitlines():
        name,oid = line.split(" ",1); refs[name] = oid
    return {"schema_version":1,"root":str(root),"common_git_dir":common,
            "ref":text("symbolic-ref","-q","HEAD"),"head":text("rev-parse","HEAD"),
            "tree":text("rev-parse","HEAD^{tree}"),"index_sha256":sha256(index) if index.is_file() else None,
            "refs":refs,"status_z_hex":run_git(root,"status","--porcelain=v1","-z",
                "--untracked-files=all").hex(),"ignored_z_hex":run_git(root,"status","--porcelain=v1",
                "-z","--untracked-files=all","--ignored").hex(),
            "submodule_status":text("submodule","status","--recursive")}


def directory_snapshot(reference: dict) -> Path:
    manifest = json_artifact(reference)
    root = Path(manifest["root"])
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),"Regular raw snapshot root required")
    actual = {}
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            require(not (Path(directory)/name).is_symlink(),"Snapshot link not admitted")
        for name in files:
            path = Path(directory)/name
            require(path.is_file() and not path.is_symlink(),"Regular snapshot files required")
            actual[path.relative_to(root).as_posix()] = sha256(path)
    require(actual==manifest["files"],"Raw snapshot file union/digests differ")
    if "device" in manifest:
        require(type(manifest["device"]) is int and root.stat().st_dev==manifest["device"],
                "Raw snapshot device identity differs")
    return root


def sqlite_projection(reference: dict) -> dict:
    path = artifact(reference)
    require(not Path(str(path)+"-wal").exists(),"SQLite snapshot must include settled WAL state")
    connection = sqlite3.connect(path.as_uri()+"?mode=ro&immutable=1",uri=True)
    connection.row_factory = sqlite3.Row
    try:
        require(connection.execute("PRAGMA integrity_check").fetchone()[0]=="ok", "Corrupt fixture database")
        projects = [dict(row) for row in connection.execute("SELECT * FROM projects ORDER BY uid")]
        issues = [dict(row) for row in connection.execute("SELECT * FROM issues ORDER BY uid")]
        links = [dict(row) for row in connection.execute(
            "SELECT * FROM links ORDER BY from_issue_uid,to_issue_uid,type")]
        meta = {row["key"]:row["value"] for row in connection.execute("SELECT * FROM meta")}
        require(meta.get("schema_version")=="25", "Pinned installed Kata schema25 required")
        all_tables = {}
        schema={row[0]:row[1] for row in connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name")}
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            name = row[0]
            if name.startswith("sqlite_") or "_fts" in name:
                continue
            require(name.replace("_","").isalnum(),"Unexpected SQL table identifier")
            rows = [dict(item) for item in connection.execute('SELECT * FROM "'+name+'"')]
            if name=="api_tokens":
                require(not rows,"Credential rows forbidden in fixture evidence")
                continue
            all_tables[name] = sorted(rows,key=lambda item:json.dumps(item,sort_keys=True))
        return {"projects":projects,"issues":issues,"links":links,"meta":meta,"tables":all_tables,"sql_schema":schema}
    except sqlite3.Error as error:
        raise InvalidEvidence("Actual supported Kata fixture schema required") from error
    finally:
        connection.close()


def read_live_project(path: Path, uid: str) -> dict:
    """Read only the selected actual project; never select tokens or foreign payloads."""
    connection=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute("BEGIN")
        projects=[dict(row) for row in connection.execute("SELECT * FROM projects WHERE uid=?",(uid,))]
        require(len(projects)==1,"Live admitted project UID missing or duplicate")
        project_id=projects[0]["id"]
        issues=[dict(row) for row in connection.execute("SELECT * FROM issues WHERE project_id=? ORDER BY uid",(project_id,))]
        links=[dict(row) for row in connection.execute(
            "SELECT links.* FROM links JOIN issues a ON links.from_issue_id=a.id "
            "JOIN issues b ON links.to_issue_id=b.id WHERE a.project_id=? OR b.project_id=? "
            "ORDER BY from_issue_uid,to_issue_uid,type",(project_id,project_id))]
        meta={row["key"]:row["value"] for row in connection.execute(
            "SELECT key,value FROM meta WHERE key IN ('schema_version','instance_uid','created_by_version')")}
        return {"projects":projects,"issues":issues,"links":links,"meta":meta}
    except sqlite3.Error as error:
        raise InvalidEvidence("Actual live project readback failed") from error
    finally:
        connection.close()


def check_native_schema(database: dict, admission: dict) -> None:
    baseline=sqlite_projection(admission["kata"]["native_baseline_db"])
    required={"projects","project_aliases","issues","comments","links","issue_labels","events",
              "meta","issue_claims","pending_claim_requests","import_mappings","recurrences"}
    require(required<=set(baseline["tables"]),"Minimal SQLite imitation is not installed Kata baseline")
    require(database["sql_schema"]==baseline["sql_schema"],"Actual database schema differs from installed native baseline")
