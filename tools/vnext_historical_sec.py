#!/usr/bin/env python3
"""Plan, acquire and carry Issue #47's historical SEC dependencies.

Purpose: The existing acquisition CLI gates on the current annual period's
dependency discovery, which reaches one year back; the five-year frame needs
four. This reads Issue #47's own declaration instead, and spends only Issue
#47's own allowance - the approval comment on issue 47, registered here and
re-read from GitHub before any request.

Owner commands, in order, on the machine that holds the approved ledger root:

  register-approval --approval-url URL   read the posted approval back from
                                         GitHub and write the allowance files
  acquire [--max-captures N]             capture every due dependency inside
                                         the grants, company by company, until
                                         nothing is left or a stop
  export                                 write the registered acquisition into
                                         evidence/issue47_acquired/ to commit
  run --approval-url URL                 the three above, in that order

``restore --export DIR --out DIR`` is the other end: it rebuilds a data root
from this checkout's baseline plus an export and registers it here.

Call relationships: Developers and the Issue #47 evidence archive call this. It
calls ``scripts/vnext/historical_source_acquisition.py`` for planning and the
allowance, ``scripts/vnext/historical_sec_session.py`` for capture and
``scripts/vnext/historical_source_export.py`` to carry the result.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vnext.historical_sec_session import (  # noqa: E402 - path set above
    live_historical_session)
from vnext.historical_source_acquisition import (  # noqa: E402 - path set above
    HistoricalAcquisitionError, acquisition_allowance, github_comment_reader,
    historical_dependencies, offline_source_plan, register_approval)
from vnext.historical_source_export import (  # noqa: E402 - path set above
    export_acquisition, restore_acquisition)

EXPORT_HINT = ("config/issue47_historical_calls_v1.json "
               "docs/evidence/issue47_history/acquisition-wiring/approval-comment.json "
               "evidence/issue47_acquired")
COMMANDS = ["list", "plan", "capture", "register-approval", "acquire", "export", "run",
            "restore"]


def _companies(args):
    """The companies to acquire for: the grant's own list, in its own order."""
    allowance = acquisition_allowance(repo_root=ROOT, delegation_reader=github_comment_reader)
    granted = list(allowance["scope"]["company_ids"])
    if args.company is None:
        return granted
    if args.company not in granted:
        raise HistoricalAcquisitionError("ISSUE_47_COMPANY_NOT_IN_SCOPE:" + args.company)
    return [args.company]


def _acquire(args):
    """Run the acquisition and keep its summary beside the ledger it spent."""
    from datetime import datetime, timezone
    session = live_historical_session()
    summary = session.acquire(company_ids=_companies(args), years=args.years,
                              max_captures=args.max_captures)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = session.ledger.root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with (runs / (stamp + ".json")).open("x", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=1, sort_keys=True)
    companies = {company: {"passes": item["passes"], "captured": len(item["captured"]),
                           "failed": sum(1 for x in item["captured"]
                                         if x["status"] != "SUCCEEDED"),
                           "outside_grants": len(item["outside_grants"]),
                           "already_claimed": len(item["already_claimed"]),
                           "error": item["error"]}
                 for company, item in summary["companies"].items()}
    return session, {"status": "ACQUISITION_STOPPED" if summary["stop"] else "ACQUISITION_DONE",
                     "stop": summary["stop"], "companies": companies,
                     "calls": summary["calls_this_session"],
                     "cumulative_calls": summary["cumulative"]["counts"],
                     "limits": summary["cumulative"]["limits"],
                     "summary_path": str(runs / (stamp + ".json"))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # ``wiring-receipt`` used to live here, which put the artifact two steps
    # from being usable: build it through this CLI into a file outside the
    # checkout, then copy it to its committed path by hand. It is now one
    # operation in tools/vnext_historical_wiring.py, which installs what it
    # built and then verifies it there.
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--company")
    parser.add_argument("--url")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approval-url")
    parser.add_argument("--max-captures", type=int)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command in ("list", "plan", "capture") and args.company is None:
        parser.error("--company is required for " + args.command)
    if args.command in ("register-approval", "run") and args.approval_url is None:
        parser.error("--approval-url is required for " + args.command)
    if args.command == "restore" and (args.export is None or args.out is None):
        parser.error("--export and --out are required for restore")
    session = None
    try:
        if args.command in ("register-approval", "run"):
            registered = register_approval(repo_root=ROOT, comment_url=args.approval_url,
                                           reader=github_comment_reader)
            result = registered
        if args.command in ("acquire", "run"):
            session, acquired = _acquire(args)
            result = acquired if args.command == "acquire" else {**registered,
                                                                 **acquired}
        if args.command in ("export", "run"):
            allowance = acquisition_allowance(repo_root=ROOT,
                                              delegation_reader=github_comment_reader)
            exported = export_acquisition(ledger_root=allowance["budget_root"])
            result = exported if args.command == "export" else {**result,
                                                                "export": exported}
        if args.command == "restore":
            result = restore_acquisition(export_dir=args.export, out_root=args.out)
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
        elif args.command == "capture":
            if args.url is None:
                parser.error("--url is required for capture")
            # The allowance check happens inside live_historical_session, before
            # any transport is constructed, so there is no path from here to a
            # request while Issue #47 has no allowance of its own. What changed
            # is which layer refuses: the execution chain now exists and is
            # exercised offline, so a refusal here names the missing grant
            # rather than a missing implementation.
            session = live_historical_session()
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
        note = "no session was opened before this refusal"
        if session is not None:
            spent = session.calls_this_session()
            note = ("counted from the slots this session claimed, not from a "
                    "difference in the shared ledger total")
            try:
                cumulative = session.ledger.snapshot()["counts"]
            except Exception as unreadable:  # noqa: BLE001 - reported, not handled
                cumulative = None
                note += "; cumulative unreadable: " + str(unreadable)
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
    if args.command in ("list", "plan", "capture"):
        print(json.dumps({key: result[key] for key in ("status", "calls")
                          if key in result}, sort_keys=True))
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True))
    if args.command in ("export", "run"):
        print("Next: git add " + EXPORT_HINT + " && git commit && git push",
              file=sys.stderr)
    return 3 if result.get("stop") or any(
        item.get("error") for item in result.get("companies", {}).values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
