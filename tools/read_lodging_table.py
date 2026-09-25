"""Read B10 (occupancy) and B11 (RevPAR) off the filing's lodging statistics table.

The route builds a production table grid and matches a frozen scope contract
against it. This reads the same filing without that grid builder: the document
is split into its <table> elements, the one naming the frozen scope literal
"Comparable Systemwide Properties" and holding a "Worldwide" row is kept -
exactly one does in each year, and a year where that is not so is not read -
tags are stripped, and the row's RevPAR and occupancy are read off its text.
B10 is the occupancy percentage as a ratio, B11 the RevPAR in dollars.

It replaces a reading whose code was never committed.

Usage:
    python3 tools/read_lodging_table.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import html
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/lodging-table-read.json"
SCOPE = "Comparable Systemwide Properties"
CASES = [("marriott_international", "2025-12-31", "marriott-2025"),
         ("marriott_international", "2024-12-31", "marriott-2024"),
         ("marriott_international", "2023-12-31", "marriott-2023")]
_TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
_ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)


def _plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def read_table(text):
    """The scope section's Worldwide row, or why there is none.

    Marriott's table holds two sections, each with a Worldwide row: company-
    operated properties first, then the scope literal's systemwide ones. The
    row read is the first Worldwide row after the row naming the scope. Its
    columns are RevPAR, its change, occupancy, its change, average daily rate
    and its change; RevPAR is the first dollar figure and occupancy the second
    percentage, and the row is recorded up to that percentage.

    Returns:
        ``(read, tables_matching_scope)``; ``read`` is None unless exactly one
        table names the scope literal with a Worldwide row after it.
    """
    matching = []
    for ordinal, table in enumerate(_TABLE.findall(text)):
        rows = [_plain(row) for row in _ROW.findall(table)]
        after = [index for index, row in enumerate(rows) if row.startswith(SCOPE)]
        if not after:
            continue
        worldwide = [row for row in rows[after[0] + 1:] if row.startswith("Worldwide")]
        if worldwide:
            matching.append((ordinal, worldwide[0]))
    if len(matching) != 1:
        return None, len(matching)
    ordinal, row = matching[0]
    revpar = re.search(r"\$\s*([0-9][0-9,]*\.[0-9]+)", row)
    percentages = list(re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*%", row))
    if revpar is None or len(percentages) < 2:
        return None, len(matching)
    return ({"table_ordinal": ordinal, "row_text": row[:percentages[1].end()],
             "revpar": revpar.group(1).replace(",", ""),
             "occupancy_percent": percentages[1].group(1)}, 1)


def verdicts(*, read, published):
    """B10 and B11 against what was published."""
    rows = {}
    values = {"B10": (Decimal(read["occupancy_percent"]) / 100) if read else None,
              "B11": Decimal(read["revpar"]) if read else None}
    for metric, value in values.items():
        shown = published.get(metric)
        rows[metric] = {"published": shown,
                        "read": None if value is None else (
                            str(value.normalize()) if metric == "B10" else read["revpar"]),
                        "verdict": ("NO_PUBLISHED_VALUE" if shown is None
                                    else "NOT_READ" if value is None
                                    else "MATCH" if value == Decimal(shown) else "DIFFERS")}
    return rows


def main():
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    from vnext.normal_period_selection import resolve_period_selection
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    body = {}
    for company_id, report_end, label in CASES:
        selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                             report_end=report_end)
        prepared = prepare_historical_annual_input(repo_root=REPO, company_id=company_id,
                                                   period_selection=selection)
        document = prepared["original_input"]["table_input"]["source_repo_relative_path"]
        read, matching = read_table((REPO / document).read_text(encoding="utf-8-sig",
                                                                 errors="replace"))
        published = {}
        for metric in ("B10", "B11"):
            result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                    closure=arguments.closure)["result"]
            published[metric] = (None if result is None or result.get("value") is None
                                 else str(result["value"]))
        entry = {"document": document, "read": read, "tables_matching_scope": matching,
                 **verdicts(read=read, published=published)}
        accession, _ = accession_of_document(repo_root=REPO, document=document)
        for metric in ("B10", "B11"):
            if entry[metric]["published"] is None:
                continue
            identity, refusal = identity_for(
                position={"company_id": company_id, "metric_id": metric,
                          "period_end": report_end, "published": entry[metric]["published"],
                          "reading_filings": [accession], "reading_window": None,
                          "filings_are_the_whole_set": False},
                index=index, closure=arguments.closure)
            if refusal is not None:
                raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":" + refusal)
            identity["established_by"] = "RECORDED_AT_READING_TIME"
            entry[metric]["checked_identity"] = identity
        body[label] = entry
        print(label, entry["B10"]["verdict"], entry["B11"]["verdict"], flush=True)
    (REPO / OUT).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
