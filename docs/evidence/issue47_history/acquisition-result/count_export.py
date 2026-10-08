"""What the approved SEC allowance bought, read from the committed export alone.

Usage: python3 count_export.py > measured.json

Every ledger slot in ``evidence/issue47_acquired`` is one real request: its
plan names the company, the declared dependency and why it was fetched, its
terminal the outcome. The count the allowance was charged is the slots plus the
reserve recorded when the ledger was lost with its container (09-29), which
covers requests that may have been sent and never recorded. Reads committed
bytes only; zero calls.
"""
import collections
import json
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EXPORT = REPO / "evidence" / "issue47_acquired"


def main():
    index = json.loads((EXPORT / "export.json").read_text(encoding="utf-8"))
    state = tarfile.open(EXPORT / index["state_archive"]["name"])
    slots = sorted({name.split("/")[2] for name in state.getnames()
                    if name.startswith("ledger/calls/")})
    by_company = collections.defaultdict(collections.Counter)
    by_class = collections.defaultdict(collections.Counter)
    failures = []
    for slot in slots:
        plan = json.load(state.extractfile("ledger/calls/%s/sec-plan.json" % slot))
        terminal = json.load(state.extractfile("ledger/calls/%s/terminal.json" % slot))
        dependency = plan["source_dependency"]
        company = plan["company_id"]
        by_company[company][terminal["status"]] += 1
        by_class[company][dependency["dependency_class"] + ":" + dependency["acquisition_kind"]] += 1
        if terminal["status"] != "SUCCEEDED":
            failures.append({"slot": slot, "company_id": company,
                             "url": plan["request"]["url"], "status": terminal["status"],
                             "counts": terminal["counts"]})
    resumes = [json.loads(line) for line in
               state.extractfile("ledger/resumes.jsonl").read().decode("utf-8").splitlines() if line]
    reserve = sum(item["lost_segment"]["reserve_sec_calls"] for item in resumes)
    result = {
        "export_id": index["export_id"],
        "approval_cap": index["approval"]["maximum_additional_provider_paid_sec_calls"],
        "slots": len(slots),
        "slot_outcomes": dict(collections.Counter(
            status for counter in by_company.values() for status in counter.elements())),
        "reserve_from_the_lost_ledger": reserve,
        "charged": len(slots) + reserve,
        "by_company": {company: dict(counter) for company, counter in sorted(by_company.items())},
        "by_company_and_dependency": {company: dict(sorted(counter.items()))
                                      for company, counter in sorted(by_class.items())},
        "failures": failures,
    }
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
