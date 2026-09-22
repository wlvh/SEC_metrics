#!/usr/bin/env python3
"""Produce Issue #47's offline acquisition-wiring receipt in one operation.

Purpose: a live grant for Issue #47 must name a receipt proving the
acquisition chain was exercised offline first, and that receipt must still be
true of the tree it is read against. Producing it used to be a sequence a
person had to get right: keep two selector lists in the business module in
step with the suite, run a builder through the acquisition CLI, write the
result outside the checkout, copy it in, and commit in the right order. Six
times in this issue the artifact went stale because one of those steps was
skipped, and the module carried 200 lines of test machinery so that it could
not be loaded where the test package is absent.

This is the whole flow and the only supported way to produce the artifact:

1. drive the chain over a recorded response;
2. read the suite to find every case it declares, rather than listing them;
3. run everything except the cases that read the receipt being produced;
4. seal and install the receipt at its committed path;
5. run the cases that read the receipt, against the installed file.

A failure at any step leaves whatever was installed before untouched, so a
failed run releases nothing. ``--check`` answers the cheaper question - is the
installed artifact still true of this tree, and does it still account for
every case the suite declares - without rebuilding.

Call relationships: developers, the Issue #47 evidence archive and CI call
this. It calls ``scripts/vnext/historical_sec_session.py`` for the chain and
the seal, and runs ``tests/vnext/test_historical_sec_session.py`` in a
separate process.
"""
import argparse
import importlib
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# The repository root as well, because reading the suite is this tool's job.
# The business module deliberately cannot do this: it has to load where there
# is no test package at all, which is asserted from the suite itself.
sys.path.insert(0, str(ROOT))

from vnext.canonical import atomic_write_bytes  # noqa: E402 - path set above
from vnext.historical_sec_session import (  # noqa: E402 - path set above
    REQUIRED_WIRING_EVIDENCE, execute_recorded_chain, seal_wiring_receipt,
    verify_offline_wiring)

SUITE_MODULE = "tests.vnext.test_historical_sec_session"
RECEIPT_PATH = ("docs/evidence/issue47_history/acquisition-wiring/"
                "offline-wiring-receipt.json")
# Where the candidate sits while it is being checked. It has to be inside the
# repository because the gate resolves paths against the repository root, and
# it must not be the installed path: an artifact at any other path confers
# nothing, because a grant names the installed path and nothing else.
CANDIDATE_PREFIX = "_candidate-"
# How the second phase is told which file to check. A committed default would
# mean the cases read whatever is already installed, which is the one file the
# run has not produced.
RECEIPT_PATH_VARIABLE = "ISSUE_47_WIRING_RECEIPT_PATH"
# The one list that cannot be derived, and the reason it is a list: these
# classes read the receipt this run produces, so running them before it exists
# would fail: before the install there is either no receipt or a receipt for
# the previous tree, and a phase that required the committed artifact to be
# current would make rebuilding it impossible after any change. Running them
# inside phase one would also make the evidence circular. They are named with
# the reason rather than quietly absent, because the defect this replaced was
# an absence nobody could see. Everything else is found by reading the module,
# so an ordinary new test needs no edit here and none in the business module.
RECEIPT_DEPENDENT = ("AGrantMustBindToAWiringReceiptThatIsStillTrue",
                     "DeletingEvidenceMustNotReduceTheCheck",
                     "TheBusinessModuleLoadsWhereNoTestPackageExists")
WHY_EXCLUDED = ("they read the receipt this run produces, so running them "
                "inside the run that produces it would make the evidence "
                "circular; they run afterwards against the installed file")
HOW_CHOSEN = ("read from " + SUITE_MODULE + " by enumerating the TestCase "
              "subclasses it declares, minus the receipt-dependent names, so "
              "an added test is covered without editing any list")
# A directory listing shaped like the one the declared dependency returns. The
# chain is what is under test here, not the parsing of a particular body.
FIXTURE_BODY = json.dumps({"directory": {"item": [],
                                         "name": "recorded-wiring-fixture"}}).encode()


class WiringBuildError(RuntimeError):
    """The receipt could not be produced, so nothing may be released."""


def declared_cases(module_name=SUITE_MODULE):
    """Every TestCase the suite module declares, read from the module itself.

    Declared by *this* module, not inherited: a base class imported from
    somewhere else is not one of this suite's cases, and counting it would
    make the accounting in the receipt disagree with what actually ran.
    """
    module = importlib.import_module(module_name)
    return sorted(name for name, value in inspect.getmembers(module, inspect.isclass)
                  if issubclass(value, unittest.TestCase)
                  and value.__module__ == module.__name__)


def split_cases(*, declared, receipt_dependent=RECEIPT_DEPENDENT):
    """Partition the declared cases into the two phases, or refuse.

    A name in ``receipt_dependent`` that the suite does not declare is a
    refusal rather than a silent drop. Renaming an excluded class would
    otherwise shrink the exclusion set to nothing and look like an
    improvement, while the class it named stopped running in either phase.
    """
    unknown = sorted(set(receipt_dependent) - set(declared))
    if unknown:
        raise WiringBuildError(
            "ISSUE_47_WIRING_EXCLUSION_NAMES_NO_CASE:" + ",".join(unknown))
    first = [name for name in declared if name not in set(receipt_dependent)]
    if not first:
        raise WiringBuildError("ISSUE_47_WIRING_FIRST_PHASE_IS_EMPTY")
    return first, sorted(set(receipt_dependent))


def run_cases(names, *, receipt_path=None):
    """Run the named cases in a fresh process and report what happened.

    A subprocess rather than an in-process loader: it is the same command a
    person runs, it starts from the repository root so the test package is
    importable, and it cannot be influenced by whatever this process has
    already imported.

    ``receipt_path`` names the file the receipt-reading cases must check. In
    phase two that is this run's candidate, never the installed artifact:
    checking the installed one would answer a question about the previous run.
    """
    selectors = [SUITE_MODULE + "." + name for name in names]
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if receipt_path is not None:
        environment[RECEIPT_PATH_VARIABLE] = receipt_path
    done = subprocess.run([sys.executable, "-m", "unittest", *selectors],
                          cwd=str(ROOT), capture_output=True, encoding="utf-8",
                          env=environment, timeout=3600)
    tail = (done.stderr or "") + (done.stdout or "")
    ran = re.search(r"^Ran (\d+) tests?", tail, re.MULTILINE)
    failures = re.search(r"failures=(\d+)", tail)
    errors = re.search(r"errors=(\d+)", tail)
    return {"tests_run": int(ran.group(1)) if ran else 0,
            "failures": int(failures.group(1)) if failures else 0,
            "errors": int(errors.group(1)) if errors else 0,
            "return_code": done.returncode,
            "passed": done.returncode == 0 and bool(ran),
            "tail": tail[-2000:]}


def build(*, runner=run_cases, collector=declared_cases):
    """Drive the chain, run phase one, and return the sealed receipt.

    Nothing is written here. The caller installs, so a phase-one failure
    cannot leave a half-built artifact behind.
    """
    declared = collector()
    first, excluded = split_cases(declared=declared)
    with tempfile.TemporaryDirectory(prefix="issue47-wiring-") as scratch:
        chain = execute_recorded_chain(root=Path(scratch) / "ledger",
                                       response=FIXTURE_BODY)
    outcome = runner(first)
    if not outcome["passed"]:
        raise WiringBuildError("ISSUE_47_WIRING_FIRST_PHASE_DID_NOT_PASS:"
                               + outcome.get("tail", "")[-1200:])
    run = {"classes_declared": declared, "classes_run": first,
           "classes_excluded": excluded, "why_excluded": WHY_EXCLUDED,
           "how_the_set_was_chosen": HOW_CHOSEN,
           "tests_run": outcome["tests_run"], "failures": outcome["failures"],
           "errors": outcome["errors"], "return_code": outcome["return_code"],
           "passed": outcome["passed"]}
    return seal_wiring_receipt(chain=chain, verification_run=run)


def _write(path, receipt):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=1,
                               sort_keys=True) + "\n", encoding="utf-8")


def build_and_install(*, receipt_path=RECEIPT_PATH, runner=run_cases,
                      collector=declared_cases):
    """The one operation: build, check the candidate, then install it.

    The order is load-bearing. An earlier version installed first and restored
    the previous bytes if the second phase failed, which left a window where
    the gate and ``--check`` accepted a receipt that was still being checked -
    and a process killed inside that window left the unchecked artifact in
    place, because the code that would have put the old one back never ran.
    An external review measured all three cases.

    So nothing is written to the installed path until every check has passed.
    The candidate lives beside it under a different name, the second phase is
    told to check that name, and the install is one atomic replacement. A
    failure or a kill leaves the previous bytes, or no file where there was
    none, without any code having to run to make that true.
    """
    receipt = build(runner=runner, collector=collector)
    target = ROOT / receipt_path
    replaced = target.exists()
    candidate_relative = receipt_path.rsplit("/", 1)[0] + "/" + CANDIDATE_PREFIX \
        + receipt_path.rsplit("/", 1)[1]
    candidate = ROOT / candidate_relative
    try:
        _write(candidate, receipt)
        outcome = runner(list(receipt["verification_run"]["classes_excluded"]),
                         receipt_path=candidate_relative)
        if not outcome["passed"]:
            raise WiringBuildError("ISSUE_47_WIRING_SECOND_PHASE_DID_NOT_PASS:"
                                   + outcome.get("tail", "")[-1200:])
        atomic_write_bytes(path=target, content=candidate.read_bytes())
    finally:
        # A stray candidate is inert - no grant names it - but leaving one
        # behind would show up as an untracked file and read like an artifact.
        candidate.unlink(missing_ok=True)
    return {"status": "OFFLINE_WIRING_VERIFIED", "calls": receipt["calls"],
            "receipt_path": receipt_path, "receipt_id": receipt["receipt_id"],
            "replaced_an_existing_receipt": replaced,
            "checked_before_install_at": candidate_relative,
            "classes_declared": len(receipt["verification_run"]["classes_declared"]),
            "tests_run_before_install": receipt["verification_run"]["tests_run"],
            "tests_run_against_the_candidate": outcome["tests_run"],
            "evidence_files": len(REQUIRED_WIRING_EVIDENCE)}


def check(*, receipt_path=RECEIPT_PATH, collector=declared_cases):
    """Is the installed artifact still true of this tree, without rebuilding.

    ``verify_offline_wiring`` answers it for the hashes and for the record's
    internal accounting. The suite comparison is the part only a caller with
    the test package can do, and it is the one that catches the common case:
    a test was added, so the declared set moved and the receipt describes a
    suite that is no longer this one. The hash over the suite file catches
    that too - this names it.
    """
    receipt = verify_offline_wiring(receipt_path=receipt_path)
    declared = collector()
    recorded = list(receipt["verification_run"]["classes_declared"])
    if sorted(recorded) != declared:
        raise WiringBuildError(
            "ISSUE_47_WIRING_SUITE_MOVED:added="
            + ",".join(sorted(set(declared) - set(recorded))) + ";gone="
            + ",".join(sorted(set(recorded) - set(declared))))
    return {"status": "OFFLINE_WIRING_CURRENT", "receipt_path": receipt_path,
            "receipt_id": receipt["receipt_id"], "calls": receipt["calls"],
            "classes_declared": len(declared)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the installed receipt without rebuilding")
    parser.add_argument("--receipt-path", default=RECEIPT_PATH)
    args = parser.parse_args(argv)
    try:
        summary = (check(receipt_path=args.receipt_path) if args.check
                   else build_and_install(receipt_path=args.receipt_path))
    except Exception as error:  # noqa: BLE001 - reported, not handled
        print(json.dumps({"status": "REFUSED", "reason": str(error),
                          "calls": [0, 0, 0],
                          "artifact_released": False}, sort_keys=True),
              file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
