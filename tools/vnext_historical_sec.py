#!/usr/bin/env python3
"""Plan one Issue #47 historical SEC dependency, offline, against its own scope.

Purpose: The existing acquisition CLI gates on the current annual period's
dependency discovery, which reaches one year back; the five-year frame needs
four. This reads Issue #47's own declaration instead. ``capture`` refuses,
because Issue #47 has no SEC allowance of its own and Issue #28's is bound to
another requirement and another scope.

Call relationships: Developers and the Issue #47 evidence archive call this. It
calls ``scripts/vnext/historical_source_acquisition.py``.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.historical_source_acquisition import (  # noqa: E402 - path set above
    HistoricalAcquisitionError, acquisition_allowance, historical_dependencies,
    offline_source_plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "plan", "capture"])
    parser.add_argument("--company", required=True)
    parser.add_argument("--url")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            rows = historical_dependencies(repo_root=ROOT, company_id=args.company,
                                           years=args.years)
            result = {"status": "OFFLINE_DEPENDENCY_LIST", "company_id": args.company,
                      "count": len(rows), "dependencies": rows, "calls": [0, 0, 0]}
        elif args.command == "plan":
            if args.url is None:
                parser.error("--url is required for plan")
            result = offline_source_plan(repo_root=ROOT, company_id=args.company,
                                         url=args.url, years=args.years)
        else:
            # Reached only to be refused. The allowance check comes before any
            # transport is constructed, so there is no path from here to a
            # request while Issue #47 has no allowance of its own.
            acquisition_allowance(repo_root=ROOT)
            raise HistoricalAcquisitionError(
                "ISSUE_47_SEC_EXECUTION_NOT_WIRED:an allowance exists but the "
                "execution path is added with the grant, not before it")
    except HistoricalAcquisitionError as error:
        print(json.dumps({"status": "REFUSED", "reason": str(error), "calls": [0, 0, 0]},
                         sort_keys=True), file=sys.stderr)
        return 2
    if args.output is not None:
        output = args.output.resolve()
        if output.exists() or ROOT in output.parents or output == ROOT:
            parser.error("Output must be a new file outside the code checkout")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({key: result[key] for key in ("status", "calls")
                      if key in result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
