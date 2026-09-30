"""Which revenue concept each B02 component used, and what each filing tags.

B02 is revenue growth: (Revenue_t - Revenue_t-1) / Revenue_t-1. The approved
branch picks the current and the prior revenue independently, each the first
approved concept its own filing tags. This lists, for every B02 run under a
runs root, the concept each claim used; and, for the filings of every run
whose two claims use different concepts, every undimensioned revenue fact the
filing tags (tools/read_statement_facts.parse_facts over the saved bytes, read
from the checkout or the acquisition's export).

Usage:
    python3 docs/evidence/issue47_history/b02-revenue-concept/measure.py \
        --runs-root <flat runs root> --output <measured.json>
Zero SEC or model calls.
"""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "scripts"))

from acceptance_readings import saved_bytes  # noqa: E402
from read_statement_facts import consolidate, document_text, parse_facts  # noqa: E402

CHAIN = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
         "RevenueFromContractWithCustomerIncludingAssessedTax")


def claims_of(run):
    """The deterministic claims a B02 run's records hold: concept, period, accession, value."""
    found = []
    for line in (run / "records.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "DETERMINISTIC_VERIFIED_CLAIM":
            locator = record["locator"]
            found.append({"concept": locator["concept"], "period_start": locator["period_start"],
                          "period_end": locator["period_end"],
                          "accession": record["attributes"]["accession"],
                          "value": record["value"]})
    return found


def revenue_facts(document):
    """Every undimensioned chain concept the document tags, by duration period."""
    facts, _ = parse_facts(document_text(saved_bytes(repo_root=REPO, relative=document)))
    table = {}
    for concept in CHAIN:
        for (start, end, instant), entries in sorted(facts.get(concept, {}).items()):
            if instant:
                continue
            value, problem = consolidate(entries)
            table.setdefault(concept, {})[start + ".." + end] = (
                str(value) if problem is None else problem)
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True,
                        help="JSON {accession: saved document path} for the filings to list")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    documents = json.loads(arguments.documents.read_text(encoding="utf-8"))
    runs, mixed = {}, []
    for run in sorted(arguments.runs_root.glob("run-*-B02")):
        claims = claims_of(run)
        runs[run.name] = [claim["concept"] for claim in claims]
        if len({claim["concept"] for claim in claims}) > 1:
            current, prior = sorted(claims, key=lambda claim: claim["period_end"], reverse=True)
            growth = (Decimal(current["value"]) - Decimal(prior["value"])) / Decimal(prior["value"])
            mixed.append({"run": run.name, "current": current, "prior": prior,
                          "growth_from_these_claims": str(growth)})
    filings = {accession: {"document": path, "revenue_facts": revenue_facts(path)}
               for accession, path in sorted(documents.items())}
    body = {"record_type": "ISSUE_47_B02_REVENUE_CONCEPT_MEASUREMENT",
            "b02_runs": len(runs), "runs_whose_two_claims_use_different_concepts": mixed,
            "filings": filings, "calls": {"sec": 0, "provider": 0}}
    arguments.output.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"b02_runs": len(runs), "mixed": [item["run"] for item in mixed]}))


if __name__ == "__main__":
    main()
