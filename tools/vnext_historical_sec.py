#!/usr/bin/env python3
"""Plan or capture one Issue #47 historical SEC dependency against its own scope.

Purpose: The existing acquisition CLI gates on the current annual period's
dependency discovery, which reaches one year back; the five-year frame needs
four. This reads Issue #47's own declaration instead. ``capture`` still
refuses, but now at the allowance rather than at a missing implementation:
the execution chain exists and is exercised offline with recorded responses,
and Issue #47 has no SEC allowance of its own while Issue #28's is bound to
another requirement and another scope.

Call relationships: Developers and the Issue #47 evidence archive call this. It
calls ``scripts/vnext/historical_source_acquisition.py`` for planning and
``scripts/vnext/historical_sec_session.py`` for capture.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.historical_sec_session import (  # noqa: E402 - path set above
    build_offline_wiring_receipt, live_historical_session)
from vnext.historical_source_acquisition import (  # noqa: E402 - path set above
    HistoricalAcquisitionError, historical_dependencies, offline_source_plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",
                        choices=["list", "plan", "capture", "wiring-receipt"])
    parser.add_argument("--company")
    parser.add_argument("--url")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.command != "wiring-receipt" and args.company is None:
        parser.error("--company is required for " + args.command)
    summary = None
    session = None
    before_sec = 0
    try:
        if args.command == "wiring-receipt":
            # Produced by driving the chain, not by describing it. A grant
            # names this receipt, so writing one without running is the thing
            # the receipt exists to prevent.
            body = json.dumps({"directory": {"item": [],
                                             "name": "recorded-wiring-fixture"}}).encode()
            with tempfile.TemporaryDirectory(prefix="issue47-wiring-") as scratch:
                result = build_offline_wiring_receipt(root=Path(scratch) / "ledger",
                                                      response=body)
            # The written file is the sealed receipt verbatim. Adding a status
            # key here would change the bytes the seal covers, so the summary
            # below is built separately rather than merged into the record.
            summary = {"status": "OFFLINE_WIRING_VERIFIED", "calls": result["calls"]}
        elif args.command == "list":
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
            if args.url is None:
                parser.error("--url is required for capture")
            # The allowance check happens inside live_historical_session, before
            # any transport is constructed, so there is no path from here to a
            # request while Issue #47 has no allowance of its own. What changed
            # is which layer refuses: the execution chain now exists and is
            # exercised offline, so a refusal here names the missing grant
            # rather than a missing implementation.
            session = live_historical_session()
            before_sec = session.ledger.snapshot()["counts"][2]
            result = session.capture(company_id=args.company, url=args.url,
                                     years=args.years)
    except HistoricalAcquisitionError as error:
        # Not every refusal happens before a request. The receipt checks run
        # after the transport, so reporting a flat [0, 0, 0] for any failure
        # would under-report a call that had already gone out - and an
        # under-reported call is exactly what makes a cumulative ceiling
        # untrustworthy. Read the ledger instead of assuming.
        # Two different numbers, so two fields. `calls` is what this invocation
        # spent, which is what a caller adds up; `cumulative_calls` is the
        # ledger's running total, which a caller must not add to anything. The
        # previous version put the cumulative total into `calls` on the failure
        # branch and the per-invocation count on the success branch, so the
        # same field meant two things depending on the outcome.
        spent, cumulative = [0, 0, 0], None
        note = "no ledger was opened before this refusal"
        if session is not None:
            try:
                state = session.ledger.snapshot()
                cumulative = state["counts"]
                spent = [0, 0, 0] if not session.ledger.live else [
                    0, 0, 1 if state["counts"][2] > before_sec else 0]
                note = ("read from this issue's ledger after the refusal; "
                        + str(len(state["blocked"])) + " slot(s) unresolved")
            except Exception as unreadable:  # noqa: BLE001 - reported, not handled
                spent, note = None, "ledger unreadable after the refusal: " + str(unreadable)
        print(json.dumps({"status": "REFUSED", "reason": str(error), "calls": spent,
                          "cumulative_calls": cumulative, "calls_source": note},
                         sort_keys=True), file=sys.stderr)
        return 2
    if args.output is not None:
        output = args.output.resolve()
        if output.exists() or ROOT in output.parents or output == ROOT:
            parser.error("Output must be a new file outside the code checkout")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=1, sort_keys=True)
    if summary is None:
        summary = {key: result[key] for key in ("status", "calls") if key in result}
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
