#!/usr/bin/env python3
"""Prepare ordinary saved-source candidates in one fresh external directory."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from sec_http import write_immutable_bytes
from vnext.canonical import content_hash
from vnext.normal_annual_input import _registry_rows
from vnext.normal_run_v3 import install_normal_inputs, create_normal_run, POLICY_PATH
from vnext.ordinary_projection import render_ordinary_run


METRICS = tuple(json.loads((ROOT / POLICY_PATH).read_text())["metric_ids"])


def _write(path, value):
    write_immutable_bytes(path=path,
        content=(json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def _new_external_root(path):
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Output must be a new absolute external directory")
    target = path.resolve()
    if target == ROOT or ROOT in target.parents:
        raise ValueError("Candidate output cannot be inside the source checkout")
    if target.exists() or any((p / "outputs/active_publication.json").exists()
                              for p in [target, *target.parents]):
        raise ValueError("Output already exists or belongs to a publication workspace")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--company", action="append",
                        help="Configured company ID; repeat to select several; default all ten")
    parser.add_argument("--metric", action="append", choices=METRICS,
                        help="Repeat to select several; default all installed normal candidate metrics")
    parser.add_argument("--freeze", action="store_true",
                        help="Freeze only when the installed successor policy explicitly enables it; draft runs remain OPEN")
    args = parser.parse_args(argv)
    companies = [row["company_id"] for row in _registry_rows(repo_root=ROOT)]
    selected = args.company or companies
    metrics = args.metric or list(METRICS)
    if (len(selected) != len(set(selected)) or set(selected) - set(companies)
            or len(metrics) != len(set(metrics))):
        parser.error("Companies and metrics must be unique configured values")
    try:
        output = _new_external_root(args.output_root)
    except ValueError as error:
        parser.error(str(error))
    output.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    _write(output / "request.json", {"companies": selected, "metrics": metrics,
        "started_at_utc": started, "source": "PREEXISTING_SAVED_ACQUISITIONS_ONLY",
        "production_authorized": False, "new_calls": {"provider": 0, "paid": 0, "sec": 0}})
    coordinates = []
    for company in selected:
        data = output / "data" / company
        for metric in metrics:
            run = output / "runs" / company / metric
            row = {"company_id": company, "metric_id": metric,
                   "run_path": run.relative_to(output).as_posix(),
                   "data_path": data.relative_to(output).as_posix()}
            try:
                install_normal_inputs(data_root=data, company_id=company, metric_id=metric)
                result = create_normal_run(data_root=data, run_dir=run,
                    company_id=company, metric_id=metric, freeze=args.freeze)
                native = result["result"]
                accepted_status = "FROZEN_CANDIDATE" if result["manifest"]["status"] == "FROZEN" else "OPEN_CANDIDATE"
                row.update(status=accepted_status if native["publication"] == "PUBLISHED" else "WITHHELD_CANDIDATE",
                    run_id=result["manifest"]["run_id"], run_status=result["manifest"]["status"],
                    result=native, target_period=result["manifest"]["target_period"],
                    public_row_status="NOT_PREPARED", production_authorized=False)
                if result.get("selection") is not None:
                    selection = result["selection"]
                    relative = "selections/" + company + "-" + metric + ".json"
                    _write(output / relative, selection)
                    row.update(selection_path=relative, selection_hash=content_hash(value=selection),
                        selection_summary={k: selection[k] for k in
                            ("reason_code", "reason", "classification", "category", "reasons", "details")
                            if k in selection})
                if native["publication"] == "PUBLISHED" or metric not in {"D01", "C02", "D02"}:
                    try:
                        rendered = render_ordinary_run(data_root=data, run_dir=run, frozen=args.freeze)
                        target = output / "rows" / company / metric
                        target.mkdir(parents=True)
                        for name, raw in rendered["files"].items():
                            write_immutable_bytes(path=target / name, content=raw)
                        _write(target / "receipt.json", rendered["receipt"])
                        row["public_row_status"] = "CANDIDATE_ROW_PREPARED"
                    except Exception as error:
                        row.update(public_row_status="PROJECTION_FAILED", projection_error=str(error))
                        diagnostic = output / "diagnostics" / (company + "-" + metric + "-projection.txt")
                        write_immutable_bytes(path=diagnostic, content=traceback.format_exc().encode())
            except Exception as error:
                row.update(status="INPUT_OR_EXECUTION_FAILED", error_type=type(error).__name__, error=str(error),
                           category=getattr(error, "category", "UNCLASSIFIED_EXECUTION_FAILURE"),
                           production_authorized=False)
                diagnostic = output / "diagnostics" / (company + "-" + metric + ".txt")
                write_immutable_bytes(path=diagnostic, content=traceback.format_exc().encode())
            coordinates.append(row)
            _write(output / "coordinates" / (company + "-" + metric + ".json"), row)
            print(json.dumps({k: row[k] for k in ("company_id", "metric_id", "status")}), flush=True)
    gaps = [row for row in coordinates if row["status"] not in {"FROZEN_CANDIDATE", "OPEN_CANDIDATE"}
            or row.get("public_row_status") == "PROJECTION_FAILED"]
    complete_status = "CANDIDATES_READY" if args.freeze else "OPEN_CANDIDATES_READY"
    report = {"record_type": "NORMAL_SAVED_CANDIDATE_BATCH", "status": "COMPLETED_WITH_GAPS" if gaps else complete_status,
        "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_coordinate_count": len(selected) * len(metrics), "coordinates": coordinates,
        "full_issue_acceptance": False, "production_authorized": False,
        "new_calls": {"provider": 0, "paid": 0, "sec": 0},
        "limits": ["Saved sources do not prove current SEC freshness", "Rows are not a complete publication",
                   "Unimplemented and withheld coordinates remain explicit"]}
    _write(output / "summary.json", report)
    return 2 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
