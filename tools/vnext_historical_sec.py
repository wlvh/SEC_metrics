#!/usr/bin/env python3
"""Plan, acquire and carry Issue #47's historical SEC dependencies.

Purpose: The existing acquisition CLI gates on the current annual period's
dependency discovery, which reaches one year back; the five-year frame needs
four. This reads Issue #47's own declaration instead, and spends only Issue
#47's own allowance - the approval comment on issue 47, registered here and
re-read from GitHub before any request.

Commands, in order, on the host that holds the approved ledger root - since
the owner decided to run it there, the executor's cloud container:

  register-approval --approval-url URL   read the posted approval back from
                                         GitHub and write the allowance files
  register-extension --approval-url URL  read the owner's extension of that
                                         approval back from GitHub and write its
                                         files; acquire and resume then use it
                                         (historical_sec_extension)
  start                                  write the ledger's local start record
                                         and print the marker comment to post
                                         on issue 47; nothing is requested
                                         until that marker is on GitHub
  acquire [--company C] [--max-captures N]
                                         capture every due dependency inside
                                         the grants, company by company, until
                                         nothing is left or a stop
  export                                 write the registered acquisition into
                                         evidence/issue47_acquired/ to commit
  run --approval-url URL                 register, acquire and export in that
                                         order (the start must already be
                                         published)

``restore --export DIR --out DIR`` is the other end: it rebuilds a data root
from this checkout's baseline plus an export and registers it here.

``resume --in-flight-company C [...] --decision-text T --decision-received-at W``
is for a host that lost the ledger root after an export was pushed: it rebuilds
the ledger from the branch's export, charges what the lost host may have spent
after it (the due rows of the companies it could have been acquiring) and
prints the resume marker to post on issue 47. Resuming is the owner's decision;
``T`` and ``W`` are that decision as the executor transcribed it. Nothing is
requested until the marker is on GitHub.

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
    live_historical_session, start_ledger)
from vnext.historical_source_acquisition import (  # noqa: E402 - path set above
    HistoricalAcquisitionError, acquisition_allowance, historical_dependencies,
    live_github_reader, offline_source_plan, register_approval)
from vnext.historical_source_export import (  # noqa: E402 - path set above
    export_acquisition, restore_acquisition)

EXPORT_HINT = ("config/issue47_historical_calls_v1.json "
               "docs/evidence/issue47_history/acquisition-wiring/approval-comment.json "
               "evidence/issue47_acquired")
EXTENSION_HINT = ("config/issue47_historical_calls_v1_extension_1.json "
                  "docs/evidence/issue47_history/acquisition-extension/approval-comment.json")
COMMANDS = ["list", "plan", "capture", "register-approval", "register-extension", "start",
            "acquire", "export", "run", "restore", "resume"]


def _effective_allowance(reader):
    """The first approval, verified, extended by the owner's extension where one is registered."""
    from vnext.historical_sec_extension import acquisition_extension, extended_allowance
    allowance = acquisition_allowance(repo_root=ROOT, delegation_reader=reader)
    return extended_allowance(allowance=allowance, extension=acquisition_extension(
        repo_root=ROOT, allowance=allowance, delegation_reader=reader))


def _companies(args):
    """The companies to acquire for: the grant's own list, in its own order."""
    allowance = _effective_allowance(live_github_reader())
    granted = list(allowance["scope"]["company_ids"])
    if args.company is None:
        return granted
    if args.company not in granted:
        raise HistoricalAcquisitionError("ISSUE_47_COMPANY_NOT_IN_SCOPE:" + args.company)
    return [args.company]


def _summary_text(summary):
    """The run summary as JSON text, complete or not at all.

    Serialized before any file is opened: the first live run opened the file
    first, and the ledger snapshot's request digests are a set, so json
    failed half way and left a truncated summary beside the ledger. A set is
    written as its sorted list; any other value json cannot write is still an
    error, raised before anything is written.
    """
    def plain(value):
        if isinstance(value, (set, frozenset)):
            return sorted(value)
        raise TypeError("ISSUE_47_SUMMARY_VALUE_IS_NOT_JSON:" + type(value).__name__)
    return json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True, default=plain)


def _acquire(args):
    """Run the acquisition and keep its summary beside the ledger it spent."""
    from datetime import datetime, timezone
    session = live_historical_session(branch_tip=_branch_tip)
    summary = session.acquire(company_ids=_companies(args), years=args.years,
                              max_captures=args.max_captures)
    text = _summary_text(summary)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = session.ledger.root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with (runs / (stamp + ".json")).open("x", encoding="utf-8") as file:
        file.write(text)
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


def _branch_tip():
    """The tip of this checkout's upstream branch, fetched now: its commit and its export index.

    Read through git rather than the GitHub reader, which reads only issue-47
    comments. A checkout with no upstream, a fetch that fails, or a HEAD that
    does not contain the tip is a refusal: nothing guesses which export is the
    latest. The index is None where the tip carries no export yet.
    """
    import subprocess
    from vnext.historical_source_export import EXPORT_DIRECTORY, INDEX_NAME

    def git(*arguments, text=True):
        run = subprocess.run(["git", "-C", str(ROOT), *arguments], capture_output=True,
                             text=text, timeout=600)
        if run.returncode != 0:
            raise HistoricalAcquisitionError(
                "ISSUE_47_RESUME_BRANCH_UNREADABLE:git " + " ".join(arguments) + ": "
                + (run.stderr if text else run.stderr.decode("utf-8", "replace"))[-300:])
        return run.stdout

    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}").strip()
    remote, _, branch = upstream.partition("/")
    git("fetch", remote, branch)
    tip = git("rev-parse", upstream).strip()
    contained = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", tip,
                                "HEAD"], capture_output=True, timeout=60).returncode
    if contained != 0:
        raise HistoricalAcquisitionError(
            "ISSUE_47_CHECKOUT_BEHIND_THE_BRANCH_TIP:HEAD does not contain " + upstream + " at "
            + tip + "; bring the checkout to the tip before resuming or acquiring")
    from vnext.historical_sec_extension import EXTENSION_FILES

    def blob(relative):
        path = upstream + ":" + relative
        present = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", path],
                                 capture_output=True, timeout=60).returncode == 0
        return git("show", path, text=False) if present else None

    # The extension's files as the tip carries them: a request under an
    # extension is made only once the branch carries it (the live path
    # compares these with the checkout's).
    return {"commit": tip, "export_index": blob(EXPORT_DIRECTORY + "/" + INDEX_NAME),
            "extension_files": {relative: blob(relative) for relative in EXTENSION_FILES}}


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
    parser.add_argument("--in-flight-company", action="append")
    parser.add_argument("--decision-text")
    parser.add_argument("--decision-received-at")
    parser.add_argument('--runtime-ledger-root', type=Path,
                        help='Verified location recovery of the same ledger; never start a new budget')
    parser.add_argument('--known-capture-url', help='Owner-reviewed single capture for a complete saved export')
    parser.add_argument('--known-capture-company')
    parser.add_argument('--wiring-receipt', help='Successor offline receipt for the limited known-export resume')
    args = parser.parse_args(argv)
    if args.command in ("list", "plan", "capture") and args.company is None:
        parser.error("--company is required for " + args.command)
    if args.command in ("register-approval", "register-extension", "run") \
            and args.approval_url is None:
        parser.error("--approval-url is required for " + args.command)
    if args.command == "restore" and (args.export is None or args.out is None):
        parser.error("--export and --out are required for restore")
    if args.runtime_ledger_root is not None and args.command not in {'resume', 'capture', 'export'}:
        parser.error('--runtime-ledger-root only supports resume/capture/export, never start or acquire')
    if args.command == "resume" and (not (args.in_flight_company or args.known_capture_url) or not args.decision_text
                                     or not args.decision_received_at):
        parser.error("--in-flight-company, --decision-text and --decision-received-at are "
                     "required for resume")
    session = None
    try:
        if args.command in ("register-approval", "run"):
            registered = register_approval(repo_root=ROOT, comment_url=args.approval_url,
                                           reader=live_github_reader())
            result = registered
        if args.command == "register-extension":
            from vnext.historical_sec_extension import register_extension
            reader = live_github_reader()
            result = register_extension(
                repo_root=ROOT, comment_url=args.approval_url, reader=reader,
                allowance=acquisition_allowance(repo_root=ROOT, delegation_reader=reader))
        if args.command == "start":
            reader = live_github_reader()
            result = start_ledger(allowance=acquisition_allowance(
                repo_root=ROOT, delegation_reader=reader), reader=reader)
        if args.command == "resume":
            from vnext.historical_sec_resume import resume_ledger
            reader = live_github_reader()
            allowance = _effective_allowance(reader)
            known = None
            if args.known_capture_url:
                if not (args.runtime_ledger_root and args.known_capture_company and args.wiring_receipt):
                    parser.error('Known single capture requires runtime location, company and successor wiring receipt')
                from vnext.historical_source_acquisition import _typed_budget_root
                _typed_budget_root(str(args.runtime_ledger_root))
                allowance = {**allowance, 'runtime_ledger_root': str(args.runtime_ledger_root)}
                known = {'company_id': args.known_capture_company, 'source_url': args.known_capture_url,
                         'wiring_receipt_path': args.wiring_receipt}
            tip = _branch_tip()
            result = resume_ledger(
                allowance=allowance,
                reader=reader, checkout=ROOT, in_flight_company_ids=args.in_flight_company or [],
                decision={"text": args.decision_text,
                          "received_at": args.decision_received_at},
                branch_export_index=tip["export_index"], branch_tip_commit=tip["commit"], known_capture=known)
        if args.command in ("acquire", "run"):
            session, acquired = _acquire(args)
            result = acquired if args.command == "acquire" else {**registered,
                                                                 **acquired}
        if args.command in ("export", "run"):
            allowance = acquisition_allowance(repo_root=ROOT,
                                              delegation_reader=live_github_reader())
            exported = export_acquisition(ledger_root=args.runtime_ledger_root or allowance["budget_root"])
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
            session = live_historical_session(branch_tip=_branch_tip,
                                              runtime_ledger_root=args.runtime_ledger_root)
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
    if args.command == "register-extension":
        print("Next: git add " + EXTENSION_HINT + " && git commit && git push",
              file=sys.stderr)
    return 3 if result.get("stop") or any(
        item.get("error") for item in result.get("companies", {}).values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
