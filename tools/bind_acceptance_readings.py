"""Record, in each reading, the business identity of the result it checked.

An acceptance says: this reading compared this published value against the
filing and found it right. The register used to take the rest of that
statement - the window, unit, scope, filing and meaning the value was measured
under - from whatever results it was generated against. So an unchanged reading
regenerated against a batch whose result had moved to another unit or scope
granted the new one. The identity is a property of what was read, and it
belongs in the reading.

Readings written before they recorded it are bound here, once:

1. the coordinate is looked up through the same receipt reader and version
   selection the coverage frame uses - one named Requirement closure, receipts
   whose manifests hash to their files, no directory-order choice;
2. the selected result's value must be the value the reading compared;
3. what the reading itself names must agree with the result - the filing it
   opened (or, for an event window, the whole filing set it enumerated) and
   the window, where it recorded one;
4. only then is the result's identity written into the reading, marked
   BOUND_AFTER_THE_READING with the closure, run and result it came from and
   the checks that ran.

An identity already in a reading is never overwritten. A batch that disagrees
with it is reported, which is the case this exists for: moving the identity to
follow a result is the defect being removed.

Usage:
    python3 tools/bind_acceptance_readings.py --runs-root <flat runs root> \
        --closure sha256:<requirement closure the batch ran under> [--dry-run]
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

import acceptance_readings as readings  # noqa: E402
from vnext.historical_coverage import (ACCEPTANCE_IDENTITY_FIELDS,  # noqa: E402
                                       select_receipt)
from vnext.historical_run_receipts import collect_run_receipts, index_receipts  # noqa: E402

REPORT = "docs/evidence/issue47_history/acceptance-binding/reading-identity-binding.json"


def _compared_value(*, published, value):
    """The result's value in the form the reading recorded it."""
    value = str(value)
    if str(published).startswith("sha256:"):
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
    return value


def identity_for(*, position, index, closure):
    """The identity to record for one position, or the reason there is none.

    Returns:
        ``(identity, None)`` or ``(None, refusal)``.
    """
    key = (position["company_id"], position["metric_id"], position["period_end"])
    selection = select_receipt(found=index.get(key, []), closure=closure)
    if selection["ambiguity"] is not None:
        return None, "RESULT_SELECTION_AMBIGUOUS:" + selection["ambiguity"]
    result, receipt = selection["result"], selection["receipt"]
    if result is None:
        return None, "NO_RESULT_UNDER_THE_NAMED_CLOSURE"
    compared = _compared_value(published=position["published"], value=result["value"])
    if compared != str(position["published"]):
        return None, "RESULT_VALUE_IS_NOT_THE_VALUE_THE_READING_COMPARED"
    checks, unnamed = ["value"], []
    named, bound = set(position["reading_filings"]), set(result.get("filings") or ())
    if not bound:
        return None, "RESULT_NAMES_NO_FILING"
    if not named:
        unnamed.append("filings")
    elif position["filings_are_the_whole_set"]:
        if named != bound:
            return None, ("READING_AND_RESULT_ENUMERATE_DIFFERENT_FILINGS:"
                          + ",".join(sorted(named ^ bound)))
        checks.append("filings_equal_the_whole_set_the_reading_enumerated")
    else:
        if not named <= bound:
            return None, ("READING_OPENED_A_FILING_THE_RESULT_DOES_NOT_NAME:"
                          + ",".join(sorted(named - bound)))
        checks.append("filings_contain_the_filing_the_reading_opened")
    if position["reading_window"] is None:
        unnamed.append("window")
    elif position["reading_window"] != [result["period_start"], result["period_end"]]:
        return None, "READING_AND_RESULT_DISAGREE_ON_THE_WINDOW"
    else:
        checks.append("window")
    identity = {field: result.get(field) for field in ACCEPTANCE_IDENTITY_FIELDS}
    identity["filings"] = sorted(bound)
    identity["entities"] = sorted(set(result.get("entities") or ()))
    identity.update({
        "established_by": "BOUND_AFTER_THE_READING",
        "bound_from": {"requirement_closure_hash": receipt["requirement_closure_hash"],
                       "run_id": receipt["run_id"], "result_id": result["result_id"]},
        "checked_against_the_reading": checks,
        "not_named_by_the_reading": unnamed})
    return identity, None


def bind(*, repo_root: Path, runs_root: Path, closure: str, dry_run: bool = False):
    """Bind every unbound position under ``repo_root``; never overwrite one.

    Returns:
        The binding report. With ``dry_run`` nothing is written.
    """
    collected = collect_run_receipts(runs_root=runs_root)
    index = index_receipts(receipts=collected["receipts"])
    outcome = collections.Counter()
    report = {"record_type": "READING_IDENTITY_BINDING", "schema_version": 1,
              "requirement_closure_hash": closure,
              "run_receipts_read": len(collected["receipts"]),
              "unreadable_run_directories": collected["unreadable"],
              "positions": []}
    for path in readings.READINGS:
        body, options = readings.load(repo_root=repo_root, path=path)
        changed = False
        for position in readings.positions(repo_root=repo_root, path=path, body=body):
            entry = {"reading": path, "label": position["label"],
                     "metric_id": position["metric_id"], "verdict": position["verdict"]}
            identity, refusal = identity_for(position=position, index=index, closure=closure)
            existing = position["slot"].get("checked_identity")
            if existing is not None:
                same = identity is not None and all(
                    existing.get(field) == identity[field]
                    for field in ACCEPTANCE_IDENTITY_FIELDS)
                entry["outcome"] = ("ALREADY_RECORDED_AND_THE_BATCH_AGREES" if same
                                    else "ALREADY_RECORDED_AND_THE_BATCH_DIFFERS")
                entry["established_by"] = existing.get("established_by")
                entry["bound_from"] = existing.get("bound_from")
                entry["batch_refusal"] = refusal
            elif refusal is not None:
                entry["outcome"] = "NOT_BOUND"
                entry["refusal"] = refusal
            else:
                position["slot"]["checked_identity"] = identity
                changed = True
                entry["outcome"] = "BOUND"
                entry["checked_against_the_reading"] = identity["checked_against_the_reading"]
                entry["not_named_by_the_reading"] = identity["not_named_by_the_reading"]
            outcome[entry["outcome"]] += 1
            report["positions"].append(entry)
        if changed and not dry_run:
            readings.dump(repo_root=repo_root, path=path, body=body, options=options)
    report["outcomes"] = dict(sorted(outcome.items()))
    report["refusals"] = dict(sorted(collections.Counter(
        entry["refusal"].split(":")[0] for entry in report["positions"]
        if entry.get("refusal")).items()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    report = bind(repo_root=REPO, runs_root=arguments.runs_root,
                  closure=arguments.closure, dry_run=arguments.dry_run)
    if not arguments.dry_run:
        (REPO / REPORT).parent.mkdir(parents=True, exist_ok=True)
        (REPO / REPORT).write_text(json.dumps(report, indent=1, sort_keys=True,
                                              ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"outcomes": report["outcomes"], "refusals": report["refusals"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
