"""Produce the two single-coordinate readings: Salesforce's B12 and Paramount's C03.

* B12 is read from the filing's own inline XBRL: the undimensioned
  us-gaap:RevenueRemainingPerformanceObligation at the period-end instant.
  The facts of the same concept that are not that - another instant, or a
  dimensioned portion such as an acquired business's share - are listed with
  why they are not taken.
* Paramount's C03 is read off the Summary Compensation Table in its 10-K/A:
  the officer's row for the year, each column named by the table's own header,
  and the row's components required to sum to its total.

Both replace readings whose code was never committed. The narrative keys each
reading already carries are kept; what the reader owns is regenerated.

Usage:
    python3 tools/read_single_facts.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import html
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

RPO = "docs/evidence/issue47_history/content-acceptance/rpo-read.json"
COMPENSATION = "docs/evidence/issue47_history/content-acceptance/paramount-compensation-table-read.json"
_DASHES = {"—", "–", "-"}


def _plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def read_instant_fact(*, text, concept, period_end):
    """The undimensioned value of ``concept`` at the ``period_end`` instant.

    Returns:
        ``(value or None, not_taken)``; every other fact of the concept is in
        ``not_taken`` with its instant and members.
    """
    from read_governance_facts import contexts_of
    contexts = contexts_of(text)
    taken, not_taken = set(), []
    for tag in re.finditer(r"<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>", text, re.S):
        attributes = dict(re.findall(r"([a-zA-Z:\-]+)=\"([^\"]*)\"", tag.group(1)))
        if attributes.get("name") != concept:
            continue
        context = contexts.get(attributes.get("contextRef"))
        shown = _plain(tag.group(2)).replace(",", "")
        try:
            value = Decimal(shown) * Decimal(10) ** int(attributes.get("scale", "0") or 0)
        except InvalidOperation:
            not_taken.append({"shown": shown, "why": "NOT_A_NUMBER"})
            continue
        if context is None:
            continue
        if context["end"] == period_end and context["start"] is None and not context["members"]:
            taken.add(value)
        else:
            not_taken.append({"value": str(value), "instant": context["end"],
                              "members": context["members"]})
    unique = {entry["value"] + "|" + entry["instant"] + "|" + ",".join(entry["members"]): entry
              for entry in not_taken if "value" in entry}
    return (taken.pop() if len(taken) == 1 else None), sorted(
        unique.values(), key=lambda entry: (entry["instant"], entry["members"]))


def read_compensation_row(*, text, officer, year):
    """The officer's Summary Compensation Table row for the year.

    Returns:
        ``{"columns": {header: value}, "total": value, "sums": bool}`` or None.
    """
    rows = [_plain(row) for row in re.findall(r"<tr\b.*?</tr>", text, re.S | re.I)]
    for index, row in enumerate(rows):
        if not ("Name and Principal Position" in row and "Year" in row and "Total" in row):
            continue
        # Column labels are the ones after "Year", each followed by "($)".
        headers = [label.strip() for label in re.findall(
            r"([A-Z][A-Za-z\- ]*?) \(\$\)", row.split(" Year ", 1)[1])]
        for candidate in rows[index + 1:]:
            if not candidate.startswith(officer):
                continue
            after = candidate.split(" " + year + " ", 1)
            if len(after) != 2:
                continue
            cells = after[1].split()
            if len(cells) != len(headers):
                return None
            values = [Decimal(0) if cell in _DASHES else Decimal(cell.replace(",", ""))
                      for cell in cells]
            columns = dict(zip(headers, values))
            total = columns.pop("Total")
            return {"columns": columns, "total": total,
                    "sums": sum(columns.values()) == total}
    return None


def _identity(*, index, closure, company_id, metric_id, period_end, published, document):
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    accession, _ = accession_of_document(repo_root=REPO, document=document)
    identity, refusal = identity_for(
        position={"company_id": company_id, "metric_id": metric_id, "period_end": period_end,
                  "published": published, "reading_filings": [accession],
                  "reading_window": None, "filings_are_the_whole_set": False},
        index=index, closure=closure)
    if refusal is not None:
        raise SystemExit("IDENTITY_NOT_RECORDED:" + company_id + ":" + metric_id + ":" + refusal)
    identity["established_by"] = "RECORDED_AT_READING_TIME"
    return identity


def main():
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)

    def published(company_id, metric_id, period_end):
        result = select_receipt(found=index.get((company_id, metric_id, period_end), []),
                                closure=arguments.closure)["result"]
        return None if result is None or result.get("value") is None else str(result["value"])

    rpo = json.loads((REPO / RPO).read_text(encoding="utf-8"))
    document = ("evidence/accession_materials/salesforce_1108524_000110852426000060/"
                + rpo["read_from"]["document"])
    value, not_taken = read_instant_fact(
        text=(REPO / document).read_text(encoding="utf-8-sig", errors="replace"),
        concept="us-gaap:RevenueRemainingPerformanceObligation", period_end=rpo["period_end"])
    shown = published(rpo["company_id"], rpo["metric_id"], rpo["period_end"])
    rpo.update({"reader": "tools/read_single_facts.py", "published": shown,
                "read": None if value is None else str(int(value)),
                "facts_not_taken": not_taken,
                "verdict": ("NOT_READ" if value is None
                            else "MATCH" if value == Decimal(shown) else "DIFFERS")})
    rpo["checked_identity"] = _identity(index=index, closure=arguments.closure,
                                        company_id=rpo["company_id"],
                                        metric_id=rpo["metric_id"],
                                        period_end=rpo["period_end"], published=shown,
                                        document=document)
    (REPO / RPO).write_text(json.dumps(rpo, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    print("B12", rpo["verdict"], rpo["read"])

    compensation = json.loads((REPO / COMPENSATION).read_text(encoding="utf-8"))
    row = read_compensation_row(
        text=(REPO / compensation["document"]).read_text(encoding="utf-8-sig", errors="replace"),
        officer="David Ellison", year="2025")
    shown = published(compensation["company_id"], "C03", compensation["period_end"])
    names = {"Salary": "salary", "Bonus": "bonus", "Stock Awards": "stock_awards",
             "Non-Equity Incentive Plan Compensation": "non_equity_incentive_plan_compensation",
             "All Other Compensation": "all_other_compensation"}
    compensation.update({
        "reader": "tools/read_single_facts.py", "published": shown,
        "components": {names[k]: str(v) for k, v in row["columns"].items()} if row else None,
        "components_sum_to_the_total": row["sums"] if row else None,
        "total_read": str(row["total"]) if row else None,
        "verdict": ("NOT_READ" if row is None or not row["sums"]
                    else "MATCH" if row["total"] == Decimal(shown) else "DIFFERS")})
    compensation["checked_identity"] = _identity(
        index=index, closure=arguments.closure, company_id=compensation["company_id"],
        metric_id="C03", period_end=compensation["period_end"], published=shown,
        document=compensation["document"])
    (REPO / COMPENSATION).write_text(json.dumps(compensation, indent=1, sort_keys=True,
                                                ensure_ascii=False) + "\n", encoding="utf-8")
    print("C03", compensation["verdict"], compensation["total_read"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
