#!/usr/bin/env python3
"""Independently admitted auditor entrypoint. Never imports product modules."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True

from audit_support.raw_git import InvalidEvidence, materialize, retain, verify_materialization
from audit_support.verification import audit
from audit_support.recovery import reconstruct_queue


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("materialize")
    for name in ("repository", "candidate", "source", "receipt", "owner"):
        create.add_argument("--" + name, required=True)
    check = commands.add_parser("verify-materialization")
    check.add_argument("--receipt", required=True)
    check.add_argument("--candidate", required=True)
    keep = commands.add_parser("retain")
    for name in ("repository", "candidate", "output", "owner"):
        keep.add_argument("--" + name, required=True)
    recover=commands.add_parser('reconstruct-queue')
    for name in ('export','export-sha256','kata','kata-sha256','output','owner'):
        recover.add_argument('--'+name,required=True)
    gate = commands.add_parser("audit")
    for name in ("ticket","phase","candidate","candidate-role","materialization",
                 "gate-admission","evidence","output"):
        gate.add_argument("--"+name,required=True)
    gate.add_argument("--case")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("--"):
        argv.insert(0,"audit")
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            value,code=audit(ticket=args.ticket,phase=args.phase,role=args.candidate_role,
                candidate=args.candidate,materialization_path=Path(args.materialization),
                admission_path=Path(args.gate_admission),evidence=Path(args.evidence),
                output=Path(args.output),case_only=args.case)
            print(json.dumps({"schema_version":1,"status":value["status"],"accepted":value["accepted"],
                              "report":str(Path(args.output)),"reason":value.get("reason")},sort_keys=True))
            return code
        if args.command=='reconstruct-queue':
            _,receipt=reconstruct_queue({'path':args.export,'sha256':args.export_sha256},
                {'path':args.kata,'sha256':args.kata_sha256},Path(args.output),args.owner)
            print(json.dumps({'schema_version':1,'outcome':'ok','reconstruction':receipt},sort_keys=True))
            return 0
        if args.command == "materialize":
            value = materialize(Path(args.repository), args.candidate, Path(args.source),
                                Path(args.receipt), args.owner)
        elif args.command == "retain":
            value = retain(Path(args.repository), args.candidate, Path(args.output), args.owner)
        else:
            value = verify_materialization(Path(args.receipt), args.candidate)
        print(json.dumps({"schema_version": 1, "outcome": "ok", "candidate": value["candidate"],
                          "tree": value["tree"]}, sort_keys=True))
        return 0
    except (InvalidEvidence, OSError, KeyError, UnicodeError, ValueError) as error:
        print(json.dumps({"schema_version": 1, "outcome": "refused", "reason": str(error)}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
