"""Read B06 (debt over equity) off each filing's own balance sheet and lease note.

The approved B06 and every successor Spec keep one business definition: the
period-end carrying amount of debt, finance leases included, over the equity of
the same scope. The route reaches it through a seven-stage cascade over the
debt note; this reading does not import any of it and does not read the
published value until the comparison. It reads:

* **debt** - the balance sheet rows whose caption names debt, borrowings or
  commercial paper and not a lease, each by its inline XBRL fact at the period
  end (so the scale is the filing's own);
* **finance leases** - whether the filing carries them inside those rows or
  outside, decided by the filing itself: a debt table with a finance-lease line
  puts them inside; a lease note that classifies finance lease liabilities under
  captions other than debt puts them outside, and then the filing's own
  ``FinanceLeaseLiability`` at the period end is added; an explicit statement
  that the company has no finance leases adds nothing. A filing that answers
  none of these is not read;
* **equity** - the parent's total stockholders' equity row, not total equity
  including noncontrolling interests: the approved definition's divisor is
  shareholders' equity.

Every decision is recorded with the text it rests on, so each position can be
re-derived from the saved filing and this output.

Usage:
    python3 tools/read_debt_to_equity.py --runs-root <flat runs root> \
        --closure sha256:<closure> [--position <company_id>:<period_end> ...]
"""
import argparse
import html
import json
import re
import sys
from decimal import Decimal, getcontext
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/debt-to-equity-read.json"
POSITIONS = ("enphase_energy:2025-12-31", "macys:2026-01-31",
             "paramount_skydance_paramount_global:2025-12-31", "salesforce:2026-01-31")
getcontext().prec = 28
_TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
_ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
_FACT = re.compile(r"<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>", re.S)
_ATTRIBUTE = re.compile(r'([a-zA-Z:\-]+)="([^"]*)"')
_DEBT_CAPTION = re.compile(r"\b(?:debt|borrowings?|commercial paper)\b", re.I)
_EQUITY_CAPTION = re.compile(r"^total (?:parent )?(?:stockholders|shareholders)[’'] equity$", re.I)
_NO_FINANCE_LEASES = re.compile(r"(?:does not have any|has no|did not have any) finance leases", re.I)


def _plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _contexts(text):
    found = {}
    for match in re.finditer(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', text, re.S):
        body = match.group(2)
        instant = re.search(r"<xbrli:instant>([^<]+)</xbrli:instant>", body)
        found[match.group(1)] = {"instant": instant.group(1) if instant else None,
                                 "dimensional": "Member" in body}
    return found


def _value(attributes, shown):
    number = Decimal(_plain(shown).replace(",", "") or "0") if not attributes.get(
        "format", "").endswith("fixed-zero") else Decimal(0)
    number *= Decimal(10) ** int(attributes.get("scale", "0") or 0)
    return -number if attributes.get("sign") == "-" else number


def _row_fact(row, contexts, period_end):
    """The row's undimensioned fact at the period end, with its concept."""
    for match in _FACT.finditer(row):
        attributes = dict(_ATTRIBUTE.findall(match.group(1)))
        context = contexts.get(attributes.get("contextRef"), {})
        if context.get("instant") == period_end and not context.get("dimensional"):
            return attributes.get("name"), _value(attributes, match.group(2))
    return None, None


def balance_sheet(*, text, period_end):
    """Debt rows and the parent equity row of the statement of financial position."""
    contexts = _contexts(text)
    for table in _TABLE.findall(text):
        rows = _ROW.findall(table)
        captions = [_plain(row) for row in rows]
        joined = " | ".join(captions)
        if not (re.search(r"total liabilities", joined, re.I)
                and re.search(r"equity", joined, re.I)):
            continue
        debt, equity = [], None
        for row, caption in zip(rows, captions):
            label = re.split(r"\s[\$\d(—–-]", caption + " ", maxsplit=1)[0].strip()
            concept, value = _row_fact(row, contexts, period_end)
            if value is None:
                continue
            if _DEBT_CAPTION.search(label) and "lease" not in label.lower():
                debt.append({"caption": label, "concept": concept, "value": str(value)})
            elif _EQUITY_CAPTION.match(label):
                equity = {"caption": label, "concept": concept, "value": str(value)}
        if debt and equity:
            return {"debt_rows": debt, "equity_row": equity}
    return None


def finance_leases(*, text, period_end):
    """Where the filing puts its finance leases, in its own words."""
    contexts = _contexts(text)
    for table in _TABLE.findall(text):
        captions = [_plain(row) for row in _ROW.findall(table)]
        for caption in captions:
            if re.match(r"(?:obligations under )?finance leases?\b.*\d", caption, re.I) and any(
                    re.search(r"total debt", other, re.I) for other in captions):
                return {"treatment": "INSIDE_THE_DEBT_ROWS", "evidence": caption, "add": "0"}
    for table in _TABLE.findall(text):
        captions = [_plain(row) for row in _ROW.findall(table)]
        classified = []
        for index, caption in enumerate(captions):
            # "Finance (a) Accounts payable and accrued liabilities $ 2" - one row per class.
            # The asset row ("Finance lease assets (a) Right of Use Assets") is
            # not a classification of the liability, and is the one row skipped.
            match = re.match(r"finance(?: \(\w\))? (.+?) \$? ?[\d(]", caption, re.I)
            if match and not match.group(1).lower().startswith("lease"):
                classified.append(match.group(1).strip())
            # "Finance leases:" followed by the captions its liabilities sit under.
            if re.match(r"finance leases:?$", caption, re.I):
                for following in captions[index + 1:]:
                    if re.match(r"total finance lease liabilities", following, re.I):
                        break
                    if re.search(r"liabilit", following, re.I):
                        classified.append(re.split(r" \$? ?[\d(]", following)[0].strip())
        if classified:
            inside = [c for c in classified if _DEBT_CAPTION.search(c)]
            if inside:
                return {"treatment": "INSIDE_THE_DEBT_ROWS", "evidence": classified, "add": "0"}
            total = None
            for match in _FACT.finditer(text):
                attributes = dict(_ATTRIBUTE.findall(match.group(1)))
                context = contexts.get(attributes.get("contextRef"), {})
                if (attributes.get("name") == "us-gaap:FinanceLeaseLiability"
                        and context.get("instant") == period_end and not context.get("dimensional")):
                    total = _value(attributes, match.group(2))
            if total is None:
                return None
            return {"treatment": "OUTSIDE_THE_DEBT_ROWS", "evidence": classified,
                    "add": str(total), "concept": "us-gaap:FinanceLeaseLiability"}
    statement = _NO_FINANCE_LEASES.search(_plain(text))
    if statement:
        return {"treatment": "NONE", "evidence": statement.group(0), "add": "0"}
    return None


def read_filing(*, text, period_end):
    """The ratio the filing's own statements give, or why there is none."""
    sheet = balance_sheet(text=text, period_end=period_end)
    leases = finance_leases(text=text, period_end=period_end)
    if sheet is None or leases is None:
        return {"read": None, "why": "BALANCE_SHEET_NOT_FOUND" if sheet is None
                else "FINANCE_LEASE_TREATMENT_NOT_STATED", "balance_sheet": sheet,
                "finance_leases": leases}
    debt = sum(Decimal(row["value"]) for row in sheet["debt_rows"]) + Decimal(leases["add"])
    equity = Decimal(sheet["equity_row"]["value"])
    return {"read": None if equity <= 0 else str(debt / equity),
            "why": "EQUITY_NOT_POSITIVE" if equity <= 0 else None,
            "total_debt": str(debt), "equity": str(equity),
            "balance_sheet": sheet, "finance_leases": leases}


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
    parser.add_argument("--position", action="append")
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    body = {}
    for key in arguments.position or POSITIONS:
        company_id, period_end = key.split(":")
        selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                             report_end=period_end)
        prepared = prepare_historical_annual_input(repo_root=REPO, company_id=company_id,
                                                   period_selection=selection)
        document = prepared["original_input"]["table_input"]["source_repo_relative_path"]
        text = (REPO / document).read_text(encoding="utf-8-sig", errors="replace")
        row = read_filing(text=text, period_end=period_end)
        result = select_receipt(found=index.get((company_id, "B06", period_end), []),
                                closure=arguments.closure)["result"]
        published = None if result is None or result.get("value") is None else str(result["value"])
        row.update(company_id=company_id, period_end=period_end, document=document,
                   published=published,
                   verdict=("NO_PUBLISHED_VALUE" if published is None
                            else "NOT_READ" if row["read"] is None
                            else "MATCH" if Decimal(row["read"]) == Decimal(published)
                            else "DIFFERS"))
        if published is not None:
            accession, _ = accession_of_document(repo_root=REPO, document=document)
            identity, refusal = identity_for(
                position={"company_id": company_id, "metric_id": "B06", "period_end": period_end,
                          "published": published, "reading_filings": [accession],
                          "reading_window": None, "filings_are_the_whole_set": False},
                index=index, closure=arguments.closure)
            if refusal is not None:
                raise SystemExit("IDENTITY_NOT_RECORDED:" + key + ":" + refusal)
            identity["established_by"] = "RECORDED_AT_READING_TIME"
            row["checked_identity"] = identity
        # Labelled as the other readings label a position, so an acceptance
        # id reads CONTENT_B06_MACYS_2026 rather than carrying the key's colon.
        body[company_id.split("_")[0] + "-" + period_end[:4]] = row
        print(key, row["verdict"], row["read"], row["published"], flush=True)
    (REPO / OUT).write_text(json.dumps(
        {"record_type": "ISSUE_47_B06_BALANCE_SHEET_READING",
         "reader": "tools/read_debt_to_equity.py", "requirement_closure_hash": arguments.closure,
         "definition": "period-end carrying debt, finance leases included, over the parent's "
                       "stockholders' equity (02_指标定义 B06; catalog/r5/B06_*_v4..v6 keep it)",
         "per_position": body, "calls": {"provider": 0, "paid": 0, "sec": 0}},
        indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
