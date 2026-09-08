#!/usr/bin/env python3
"""Plan or explicitly execute one approved, isolated ordinary B10 candidate."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vnext.annual_candidate import (prepare_candidate_plan, expected_owner_approval,
    expected_activation_approval, verify_candidate_authorization, execute_candidate)
from vnext.canonical import atomic_write_json, strict_json_file


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Offline only; creates no approval")
    plan.add_argument("--output-root", required=True, type=Path)
    plan.add_argument("--fiscal-year", type=int)
    plan.add_argument("--plan-file", required=True, type=Path)
    execute = sub.add_parser("execute", help="Requires two real owner PR comments; NEVER a development test")
    execute.add_argument("--plan-file", required=True, type=Path)
    execute.add_argument("--activation-comment", required=True)
    execute.add_argument("--owner-comment", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            from vnext.annual_candidate import _output_root
            _output_root(args.plan_file.absolute().parent)
            if args.plan_file.is_symlink():
                raise ValueError("CANDIDATE_PLAN_FILE_ALIAS_FORBIDDEN")
            pending = prepare_candidate_plan(output_root=args.output_root, fiscal_year=args.fiscal_year)
            if args.plan_file.exists() and strict_json_file(path=args.plan_file) != pending:
                raise ValueError("CANDIDATE_PLAN_FILE_ALREADY_EXISTS")
            atomic_write_json(path=args.plan_file, value=pending)
            result = {"plan": pending, "activation_approval_template": expected_activation_approval(pending),
                      "execution_approval_template": expected_owner_approval(pending), "authorization": "NOT_ISSUED"}
        else:
            pending = strict_json_file(path=args.plan_file)
            authorization = verify_candidate_authorization(plan=pending,
                activation_url=args.activation_comment, owner_url=args.owner_comment)
            result = execute_candidate(plan=pending, authorization=authorization)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(json.dumps({"status":"BLOCKED_OR_FAILED","reason":str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
