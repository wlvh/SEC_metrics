#!/usr/bin/env python3
"""Run fixed-code annual candidates; inputs are data, not Git commits."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vnext import annual_runtime as runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("initialize")
    seed.add_argument("--data-root", type=Path, required=True)
    proposal = commands.add_parser("stage-proposal")
    proposal.add_argument("--data-root", type=Path, required=True)
    proposal.add_argument("--stage-root", type=Path, required=True)
    proposal.add_argument("--baseline-run", type=Path, required=True)
    proposal.add_argument("--review-file", type=Path, required=True)
    proposal.add_argument("--repair-evidence", type=Path, required=True)
    proposal.add_argument("--repair-ordinal", type=int, choices=[1, 2], default=1)
    run = commands.add_parser("run")
    run.add_argument("--approval-url", required=True)
    for command in (seed, proposal, run):
        command.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args(argv)
    output = runtime._external(args.output_json)
    if output.exists():
        parser.error("Output already exists; choose a new evidence file")
    try:
        with redirect_stdout(sys.stderr):
            if args.command == "initialize":
                result = runtime.initialize_data_root(data_root=args.data_root)
            elif args.command == "stage-proposal":
                result = runtime.stage_proposal(
                    data_root=args.data_root,
                    stage_root=args.stage_root,
                    baseline_run=args.baseline_run,
                    review_path=args.review_file,
                    repair_evidence_path=args.repair_evidence,
                    repair_ordinal=args.repair_ordinal,
                )
            else:
                result = runtime.run_update(approval_url=args.approval_url)
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
        result = {
            "status": "STAGE_STOPPED",
            "error": str(error),
            "error_type": type(error).__name__,
            "execution": "NOT_CONFIRMED",
            "provider_paid_sec_calls": [None, None, 0],
            "note": "Inspect permanent stage slot and WB-3 evidence; no automatic retry.",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        0
        if result.get("status")
        in {"SAVED_INPUTS_COPIED", "CANDIDATE_UPDATE_SUCCEEDED", "NO_NEW_ANNUAL_FILING"}
        or args.command == "stage-proposal"
        and "stage_id" in result
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
