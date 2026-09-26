#!/usr/bin/env python3
"""Fault injections for the SEC allowance proposal's not-yet-declarable checks.

tools/propose_historical_allowance.py does not write the proposal when the
plan's statement of what the grants do with targets a catalog does not reach
yet differs from the gate's answers (THE_GRANTS_DO_NOT_MEAN_WHAT_THE_PLAN_SAYS),
or when one class gets different answers for different unreached targets
(NOT_YET_DECLARABLE_ANSWER_DIFFERS_BY_TARGET). Each injection breaks one side
and must be refused by the check it targets. The script before this one
printed exit statuses and last lines for a person to read and exited 0 whatever
they were; this one decides:

  control    exit 0, nothing on stderr, and a proposal byte-identical to the
             committed one, which also shows the redirection below changes
             nothing;
  injection  exit 1, nothing on stdout, stderr exactly the SystemExit message
             of the targeted check, and no proposal written. A traceback - a
             syntax, import or any other error, which also exits 1 - or a
             refusal by a different check does not count.

A timeout fails its case. Any failing case, or a change to the committed
proposal, plan or tool during the run, makes the script exit 1. An edit that
does not apply exactly once, or does not compile, exits 2 before anything runs:
nothing was tested.

--bypass-target-check also disables, in each injection, the check it targets.
The script must then exit 1; that is the control for the judgement itself.

Isolation: nothing in the checkout is written. The tool's source is edited in
memory and run in a subprocess with __file__ set to the real tool, so it reads
the real repository, but its one read of the plan and its one write into the
checkout are redirected into a temporary directory that holds the edited plan
and receives any proposal; bytecode caching is off in the subprocess. The
directory is removed on normal exit, on an error, and on SIGINT, SIGTERM or
SIGHUP, with the running tool killed first. SIGKILL leaves it behind in the
system temp directory, outside the checkout.

Zero SEC or provider calls. Run: python3 <this file> [--bypass-target-check]
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOL = REPO / "tools/propose_historical_allowance.py"
PLAN = REPO / "docs/evidence/issue47_history/acquisition-plan.json"
PROPOSAL = REPO / "docs/evidence/issue47_history/acquisition-wiring/proposed-allowance.json"
# The tool's only read of the plan and its only write into the checkout.
PLAN_READ = '(REPO / "docs/evidence/issue47_history/acquisition-plan.json")'
PROPOSAL_WRITE = ('(REPO / "docs/evidence/issue47_history/acquisition-wiring/'
                  'proposed-allowance.json")')
CONSISTENCY = "THE_GRANTS_DO_NOT_MEAN_WHAT_THE_PLAN_SAYS"
UNIFORMITY = "NOT_YET_DECLARABLE_ANSWER_DIFFERS_BY_TARGET"
DISABLE = {CONSISTENCY: ("if stated != not_yet_declarable:", "if False:"),
           UNIFORMITY: ("    if mixed:", "    if False:")}
BANK = "jpmorgan_chase"
A_GRANT_WINDOW = ('     "dependency_classes": ["ACCESSION_INSTANCE_DISCOVERY", '
                  '"ANNUAL_PERIOD_IDENTITY"],\n'
                  '     "earliest_report_end": WINDOW[0], "latest_report_end": WINDOW[1]},')
TIMEOUT_SECONDS = 1200
RUNNER = ("import sys\n"
          "exec(compile(sys.stdin.read(), sys.argv[2], 'exec'),\n"
          "     {'__name__': '__main__', '__file__': sys.argv[1]})\n")


class HarnessError(Exception):
    """An edit that does not apply or compile: nothing would be tested."""


def _once(text, old, new, what):
    found = text.count(old)
    if found != 1:
        raise HarnessError("INJECTION_DID_NOT_APPLY:%s: target found %d times" % (what, found))
    return text.replace(old, new)


def _dumps(value):
    return json.dumps(value, sort_keys=True)


def _last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1][:160] if lines else ""


def cases(plan_bytes):
    """The control and the three injections, each with the refusal it expects.

    The expected messages are derived from the plan's own statement, which the
    control shows is the gate's answer when nothing is broken.
    """
    plan = json.loads(plan_bytes)
    stated = plan["revision_5"]["not_yet_declarable"]
    if not stated.get(BANK, {}).get("admitted_once_declarable"):
        raise HarnessError("PRECONDITION: the plan states no admitted class for an "
                           "unreached %s target; the injections assume one" % BANK)
    granted = sorted(stated[BANK]["admitted_once_declarable"])
    everything_outside = {company: {"targets": entry["targets"], "admitted_once_declarable": [],
                                    "outside_every_grant": sorted(entry["admitted_once_declarable"]
                                                                  + entry["outside_every_grant"])}
                          for company, entry in stated.items()}
    old_meaning = json.loads(plan_bytes)
    old_meaning["revision_5"]["not_yet_declarable"] = everything_outside
    return [
        {"name": "CONTROL", "plan": plan_bytes, "edits": [], "check": None, "refusal": None},
        # The plan states the old meaning: the unreached chains outside every grant.
        {"name": "PLAN_STATES_THE_OLD_MEANING", "check": CONSISTENCY, "edits": [],
         "plan": (json.dumps(old_meaning, indent=1, ensure_ascii=False) + "\n").encode("utf-8"),
         "refusal": (CONSISTENCY + ": plan " + _dumps(everything_outside)
                     + " gate " + _dumps(stated))},
        # The annual-chain grant is narrowed to exclude the bank; the text is unchanged.
        {"name": "GRANT_NARROWED_TEXT_UNCHANGED", "check": CONSISTENCY, "plan": plan_bytes,
         "edits": [('{"grant": "A_ANNUAL_CHAIN", "company_ids": EVERYONE,',
                    '{"grant": "A_ANNUAL_CHAIN", "company_ids": OTHERS,')],
         "refusal": (CONSISTENCY + ": plan " + _dumps(stated) + " gate "
                     + _dumps({**stated, BANK: everything_outside[BANK]}))},
        # The annual-chain grant starts a year late, so it covers only some
        # unreached years and the class gets two answers.
        {"name": "GRANT_COVERS_ONLY_SOME_YEARS", "check": UNIFORMITY, "plan": plan_bytes,
         "edits": [(A_GRANT_WINDOW, A_GRANT_WINDOW.replace(
             '"earliest_report_end": WINDOW[0]',
             '"earliest_report_end": str(int(WINDOW[0][:4]) + 1) + WINDOW[0][4:]'))],
         "refusal": UNIFORMITY + ":" + BANK + ":" + ",".join(granted)},
    ]


def prepare(case, tool_source, directory, bypass):
    """The case's plan file and edited source, or HarnessError."""
    case_dir = directory / case["name"]
    case_dir.mkdir()
    plan_path, proposal_path = case_dir / "plan.json", case_dir / "proposal.json"
    plan_path.write_bytes(case["plan"])
    source = _once(tool_source, PLAN_READ, "Path(%r)" % str(plan_path), "plan read")
    source = _once(source, PROPOSAL_WRITE, "Path(%r)" % str(proposal_path), "proposal write")
    edits = list(case["edits"])
    if bypass and case["check"]:
        edits.append(DISABLE[case["check"]])
    for old, new in edits:
        source = _once(source, old, new, case["name"])
    try:
        compile(source, case["name"], "exec")
    except SyntaxError as error:
        raise HarnessError("INJECTED_SOURCE_DOES_NOT_COMPILE:%s: %s" % (case["name"], error))
    return {**case, "dir": case_dir, "source": source, "proposal": proposal_path}


def run(case, timeout=TIMEOUT_SECONDS):
    """The tool's completed process for this case, or None on timeout."""
    try:
        return subprocess.run(
            [sys.executable, "-c", RUNNER, str(TOOL), "<tool edited for %s>" % case["name"]],
            input=case["source"], capture_output=True, text=True, timeout=timeout,
            cwd=case["dir"], env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return None


def judge(case, result, committed):
    """Every way this case failed; empty when it passed."""
    problems = []
    if result is None:
        problems.append("timed out")
    elif case["refusal"] is None:
        if result.returncode != 0:
            problems.append("exit %d, expected 0: %s" % (result.returncode,
                                                         _last_line(result.stderr)))
        elif result.stderr:
            problems.append("wrote to stderr: " + _last_line(result.stderr))
        if not case["proposal"].exists():
            problems.append("wrote no proposal")
        elif case["proposal"].read_bytes() != committed:
            problems.append("its proposal differs from the committed one")
    else:
        if result.returncode != 1:
            problems.append("exit %d, expected 1" % result.returncode)
        if result.stderr.rstrip("\n") != case["refusal"]:
            problems.append("not refused by %s: stderr ends %r"
                            % (case["check"], _last_line(result.stderr)))
        if result.stdout.strip():
            problems.append("printed its summary, so it ran past its checks")
    if case["refusal"] is not None and case["proposal"].exists():
        problems.append("wrote a proposal")
    if PROPOSAL.read_bytes() != committed:
        problems.append("the committed proposal changed")
    return problems


def _stop(signum, frame):
    raise SystemExit(128 + signum)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bypass-target-check", action="store_true",
                        help="disable each injection's targeted check; must exit 1")
    args = parser.parse_args()
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, _stop)
    before = {path: path.read_bytes() for path in (TOOL, PLAN, PROPOSAL)}
    if args.bypass_target_check:
        print("BYPASS: each injection's targeted check is disabled; this run must exit 1",
              flush=True)
    failed = []
    with tempfile.TemporaryDirectory(prefix="issue47-injections-") as directory:
        try:
            prepared = [prepare(case, before[TOOL].decode("utf-8"), Path(directory),
                                args.bypass_target_check) for case in cases(before[PLAN])]
        except HarnessError as error:
            print(error, flush=True)
            return 2
        for case in prepared:
            problems = judge(case, run(case), before[PROPOSAL])
            print(("FAIL %s: %s" % (case["name"], "; ".join(problems))) if problems
                  else ("PASS %s: %s" % (case["name"], case["check"] or "proposal reproduced")),
                  flush=True)
            if problems:
                failed.append(case["name"])
    changed = [str(path.relative_to(REPO)) for path, data in before.items()
               if path.read_bytes() != data]
    if changed:
        print("FAIL CHECKOUT: changed during the run: " + ", ".join(changed))
        failed.append("CHECKOUT")
    print("ALL_CASES_PASSED" if not failed else "CASES_FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
