"""Which target 10-K rows live only in a history block, not in the main submissions file.

Every pinned route that builds a source set from the registrant's main
submissions document - Company Facts, the zero-AI statement routes, the
accession route and the financial route - discovers the target filing among
that document's ``filings.recent`` rows. A target whose row the main document
does not list fails discovery there, whatever else is saved. This lists, for
each company and each target period the historical plan knows, whether the
selected filing's accession is in the main document's recent block, and the
earliest filing date that block covers. Reads saved JSON only; no calls.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/financial-route/measure_target_row_blocks.py
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from vnext.normal_history_plan import plan_historical_sources  # noqa: E402

OUT = Path(__file__).with_name("target-row-blocks.json")
companies = [row["company_id"] for row in csv.DictReader(open(ROOT / "config/company_registry.csv"))]
body = {"record_type": "ISSUE_47_TARGET_ROW_BLOCK_MEASUREMENT", "companies": {},
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
outside = []
for company_id in companies:
    plan = plan_historical_sources(repo_root=ROOT, company_id=company_id, count=5)
    rows = []
    for candidate in plan["target_candidates"]:
        cik = int(candidate.get("reporting_cik") or plan["primary_cik"])
        main = json.loads((ROOT / ("evidence/submissions/CIK%010d.json" % cik)).read_text())
        recent = main["filings"]["recent"]
        filing = candidate.get("current_filing") or {}
        accession = filing.get("accessionNumber")
        row = {"report_end": candidate["report_date"], "reporting_cik": str(cik),
               "accession": accession, "filing_date": filing.get("filingDate"),
               "main_recent_earliest_filing_date": min(recent["filingDate"]),
               "in_main_recent_block": (accession in set(recent["accessionNumber"])
                                        if accession else None)}
        rows.append(row)
        if row["in_main_recent_block"] is False:
            outside.append(company_id + ":" + row["report_end"])
    body["companies"][company_id] = {
        "known_target_periods": rows,
        "frame_target_count": 5,
        "unknown_target_periods": 5 - len(rows)}
body["known_targets_outside_the_main_recent_block"] = outside
OUT.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
print(json.dumps({"outside": outside}, indent=1))
