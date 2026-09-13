#!/usr/bin/env python3
"""Inspect saved annual inputs or discover their source dependencies."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from sec_http import write_immutable_bytes
from vnext.normal_annual_input import inspect_saved_annual_inputs
from vnext.normal_source_requirements import inspect_source_requirements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT,
                        help="Saved registry and request ledger root; read only")
    parser.add_argument("--discover-sources", action="store_true",
                        help="List known annual, proxy and fiscal 8-K source dependencies; no fetch")
    parser.add_argument("--company", action="append",
                        help="Configured company id; discovery or processing, default all ten")
    parser.add_argument("--process", action="store_true",help="Check saved inputs and maintain ordinary candidate history; no fetch or publication")
    parser.add_argument("--state-root",type=Path,help="Persistent external update state; required with --process")
    parser.add_argument("--metric",action="append",help="Metric id for processing; default all current ordinary routes")
    parser.add_argument("--output", type=Path,
                        help="Optional new file outside the source checkout")
    args = parser.parse_args(argv)
    if args.process and args.discover_sources:parser.error("Choose processing or source discovery")
    if args.process != (args.state_root is not None):parser.error("--process requires --state-root")
    if args.metric and not args.process:parser.error("--metric requires --process")
    if args.company and not (args.discover_sources or args.process):
        parser.error("--company requires --discover-sources or --process")
    if args.output:
        target = args.output.resolve()
        if target == ROOT or ROOT in target.parents or args.output.is_symlink():
            parser.error("output must be a new external file")
        if target.exists() or any((p / "outputs/active_publication.json").exists()
                                  for p in target.parents):
            parser.error("output exists or belongs to a publication workspace")
    if args.process:
        from vnext.ordinary_update_cycle import run_once
        from vnext.normal_annual_input import _registry_rows
        from vnext.normal_run_v3 import _policy
        companies=[c['company_id'] for c in _registry_rows(repo_root=ROOT)]
        selected=args.company or companies;metrics=args.metric or _policy(ROOT)['metric_ids']
        if len(selected)!=len(set(selected)) or set(selected)-set(companies):parser.error("Companies must be unique configured values")
        results=[]
        for company in selected:
            try:
                outcome=run_once(state_root=args.state_root.resolve()/company,source_root=args.data_root.resolve(),company_id=company,metric_ids=metrics)
                results.append({'company_id':company,**outcome})
            except Exception as error:results.append({'company_id':company,'status':'UPDATE_BLOCKED','error_type':type(error).__name__,'reason':str(error)})
        report={'record_type':'ORDINARY_SAVED_UPDATE_CHECK','companies':results,'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
    else:report = (inspect_source_requirements(repo_root=args.data_root.resolve(),company_ids=args.company)
              if args.discover_sources else inspect_saved_annual_inputs(repo_root=args.data_root.resolve()))
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output:
        write_immutable_bytes(path=args.output, content=raw)
    print(raw.decode(), end="")
    failed = (any(c['status'] not in {'CANDIDATE_READY','NO_SOURCE_CONTENT_CHANGE'} for c in report['companies']) if args.process else
              any(c["status"] != "SAVED_SOURCE_DEPENDENCIES_AVAILABLE" for c in report["companies"])
              if args.discover_sources else any(c["status"] == "INPUT_BLOCKED" for c in report["companies"]))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
