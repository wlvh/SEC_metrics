#!/usr/bin/env python3
"""Check Marriott annual filing identity and prepare inputs without execution."""
import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sec_http import write_immutable_bytes
from vnext.annual_candidate import _output_root, prepare_candidate_plan
from vnext.annual_update import check_annual_update
from vnext.batch_workflow import BatchWorkflowError
from vnext.publication import PublicationError


def _external_file(path):
    _output_root(path.absolute().parent)
    if path.is_symlink() or path.exists():
        raise ValueError("OUTPUT_FILE_ALREADY_EXISTS_OR_ALIAS")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-run", type=Path, help="Existing successful native B10 Run; never a discovery checkpoint")
    parser.add_argument("--output", type=Path, help="New external JSON file; also prints JSON")
    parser.add_argument("--refresh", choices=("none", "submissions", "missing"), default="none",
                        help="Real SEC I/O only with separate owner permission; default is local")
    parser.add_argument("--sec-request-limit", type=int, default=0,
                        help="0 offline; exactly 1 for submissions; 1..3 for conditional missing sources, retry=0")
    parser.add_argument("--candidate-output-root", type=Path, help="Optionally build an existing unapproved plan only for INPUT_READY")
    parser.add_argument("--candidate-plan-file", type=Path, help="New external plan file, consumable by the existing candidate CLI")
    args = parser.parse_args(argv)
    report = None
    try:
        if args.output:
            _external_file(args.output)
        if bool(args.candidate_output_root) != bool(args.candidate_plan_file):
            raise ValueError("CANDIDATE_OUTPUT_ROOT_AND_PLAN_FILE_REQUIRED_TOGETHER")
        if args.candidate_plan_file:
            _external_file(args.candidate_plan_file)
            _output_root(args.candidate_output_root)
            if args.output and args.output.absolute() == args.candidate_plan_file.absolute():
                raise ValueError("OUTPUT_PATHS_OVERLAP")
        report = check_annual_update(repo_root=REPO_ROOT, candidate_run=args.candidate_run,
            refresh=args.refresh, sec_request_limit=args.sec_request_limit)
        if args.candidate_plan_file and report["status"] == "INPUT_READY":
            try:
                pending = prepare_candidate_plan(output_root=args.candidate_output_root,
                    fiscal_year=report["prepared_input"]["table_input"]["target_period"]["fiscal_year"])
                if pending["prepared_input"] != report["prepared_input"]:
                    raise ValueError("CANDIDATE_INPUT_CHANGED")
                write_immutable_bytes(path=args.candidate_plan_file, content=(json.dumps(pending, ensure_ascii=False, indent=2) + "\n").encode())
                report["candidate_plan"] = {"path": str(args.candidate_plan_file), "plan_id": pending["plan_id"], "authorization": "NOT_ISSUED"}
            except (ValueError, OSError) as error:
                report["candidate_plan"] = {"status": "BLOCKED", "error": str(error), "authorization": "NOT_ISSUED"}
        raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
        if args.output:
            write_immutable_bytes(path=args.output, content=raw)
        print(raw.decode(), end="")
        return 0 if report["status"] in {"NO_NEW_ANNUAL_FILING", "INPUT_READY"} else 2
    except (ValueError, KeyError, TypeError, OSError, BatchWorkflowError, PublicationError) as error:
        failure = {"status": "CHECK_FAILED", "error": str(error), "execution": "NOT_EXECUTED"}
        if report is not None:
            failure["check_result"] = report
        print(json.dumps(failure, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
