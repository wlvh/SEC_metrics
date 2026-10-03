"""Read the bank's A03, A04, A09, A11, A12 and A13 off its annual report's own tables.

The route runs Issue #28's frozen financial inspectors (and, for the older
reports, #47's older-wording successors), which prove each measure's scope
through glossary, segment, introduction and footnote witnesses. This reads the
same filing without them: the document is split into its <table> elements, each
row into its cells with the tags stripped, and each measure is read from the row
the report names it by, in the column of the target year:

* A04 net interest margin: "Net yield on average interest-earning assets -
  managed basis", a percentage, as a ratio.
* A09 nonaccrual loan ratio: "Firmwide nonaccrual loans to total loans
  outstanding", a percentage, as a ratio.
* A11 assets under management: "Total assets under management", in the scale
  the table's header states.
* A12 average VaR: "Total VaR" in a table whose header splits each year into
  "Avg.", "Min" and "Max" columns; the year's average, in the header's scale.
* A13 international net revenue: "Total international" in the table whose
  first figure column is "Revenue", under the row naming the target year, in
  the header's scale.
* A03 LCR: the "LCR" row under the group named by the registrant (its name as
  the filing's own DEI states it) in the table of average amounts for the
  three months ended on the period's end, and the selected financial data's
  firm LCR average row; both are read and must agree.

The column is found from the table's own header: the row whose cells are years
(or, for A03, the full date of the period's end). Every table that names the
measure and states the target year is read; they must all agree, and a measure
no table states, or tables state differently, is not read.

Usage:
    python3 tools/read_bank_measures.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under> \
        --reading <positions.json reading> --output <path> --source-root <restored root>
"""
import argparse
import calendar
import html
import json
import re
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import reading_cases, saved_bytes  # noqa: E402

METRICS = ("A03", "A04", "A09", "A11", "A12", "A13")
_TABLE = re.compile(r"<table\b.*?</table>", re.S | re.I)
_ROW = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh]\b.*?</t[dh]>", re.S | re.I)
_YEAR = re.compile(r"(?:19|20)[0-9]{2}")
_NUMBER = re.compile(r"\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?")
_SCALES = {"thousands": Decimal(1000), "millions": Decimal(1000000), "billions": Decimal(1000000000)}
_LABELS = {
    "A04": "net yield on average interest-earning assets - managed basis",
    "A09": "firmwide nonaccrual loans to total loans outstanding",
    "A11": "total assets under management",
    "A12": "total var",
    "A13": "total international",
}


def _plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _label(text):
    """A row label with its dashes made one and its footnote marks removed."""
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"(?:\s*\((?:[a-z]|[0-9]{1,2})\))+$", "", text)
    return " ".join(text.split()).casefold()


def tables(text):
    """Each <table> as (ordinal, rows); a row is its non-empty cell texts."""
    found = []
    for ordinal, table in enumerate(_TABLE.findall(text)):
        rows = [[cell for cell in (_plain(c) for c in _CELL.findall(row)) if cell]
                for row in _ROW.findall(table)]
        found.append((ordinal, rows))
    return found


def _numbers(row):
    """The figures in a row after its label; currency and percent signs are cells of their own."""
    return [cell for cell in row[1:] if _NUMBER.fullmatch(cell)]


def _figure(text):
    negative = text.startswith("(")
    value = Decimal(text.strip("()").replace(",", ""))
    return -value if negative else value


def _years(row):
    return [int(cell) for cell in row if _YEAR.fullmatch(cell)]


def _year_column(rows, index, year):
    """The target year's position among the nearest header row of years above the row."""
    for header in reversed(rows[:index]):
        years = _years(header)
        if len(years) >= 2 and years == sorted(years, reverse=True):
            return years.index(year) if year in years else None, len(years)
    return None, 0


def _scale(rows, index):
    words = " ".join(" ".join(row) for row in rows[:index])
    found = {match.casefold() for match in re.findall(r"\bin (thousands|millions|billions)\b", words, re.I)}
    return _SCALES[found.pop()] if len(found) == 1 else None


def _header_text(rows, index):
    return " ".join(" ".join(row) for row in rows[:index])


def _month_day(end):
    return "%s %d" % (calendar.month_name[end.month], end.day)


def _window(kind, rows, index, end):
    """The window the table's own header gives the figure, or None.

    ``annual``: the header names the year ended on the period's month and day.
    ``instant``: the header names that month and day as a date ("December 31,").
    """
    text = _header_text(rows, index)
    if kind == "annual":
        if re.search(r"\byear ended " + _month_day(end) + r"\b", text, re.I) is None:
            return None
        start = date(end.year - 1, end.month, end.day) + timedelta(days=1)
        return [start.isoformat(), end.isoformat()]
    if re.search(r"\b" + _month_day(end) + r",", text) is None:
        return None
    return [end.isoformat(), end.isoformat()]


def read_by_year_label(text, metric, end):
    """A04, A09, A11: the named row's figure in the target year's column, in every table."""
    reads = []
    for ordinal, rows in tables(text):
        for index, row in enumerate(rows):
            if not row or _label(row[0]) != _LABELS[metric]:
                continue
            figures = _numbers(row)
            column, count = _year_column(rows, index, end.year)
            window = _window("annual" if metric == "A04" else "instant", rows, index, end)
            if column is None or len(figures) != count or window is None:
                continue
            figure = _figure(figures[column])
            if metric in ("A04", "A09"):
                value = figure / 100
            else:
                scale = _scale(rows, index)
                if scale is None:
                    continue
                value = figure * scale
            reads.append({"table_ordinal": ordinal, "row": row, "figure": figures[column],
                          "window": window,
                          "value": str(value.normalize() if metric in ("A04", "A09") else value)})
    return reads


def read_average_var(text, end):
    """A12: the year's "Avg." column of the "Total VaR" row in a table split into Avg./Min/Max."""
    reads = []
    for ordinal, rows in tables(text):
        for index, row in enumerate(rows):
            if not row or _label(row[0]) != _LABELS["A12"] or not _numbers(row):
                continue
            column, count = _year_column(rows, index, end.year)
            splits = [header for header in rows[:index] if "Avg." in header]
            window = _window("annual", rows, index, end)
            if column is None or not splits or window is None:
                continue
            split = [cell for cell in splits[-1] if cell in ("Avg.", "Min", "Max")]
            if len(split) != 3 * count or split[:3] != ["Avg.", "Min", "Max"]:
                continue
            figures = _numbers(row)
            scale = _scale(rows, index)
            if len(figures) != len(split) or scale is None:
                continue
            reads.append({"table_ordinal": ordinal, "row": row, "figure": figures[3 * column],
                          "window": window, "value": str(_figure(figures[3 * column]) * scale)})
    return reads


def read_international_revenue(text, end):
    """A13: "Total international" under the target year's row, first figure column "Revenue"."""
    reads = []
    for ordinal, rows in tables(text):
        headers = [index for index, row in enumerate(rows)
                   if len(row) > 1 and row[1].casefold().startswith("revenue")]
        if not headers:
            continue
        window = _window("annual", rows, headers[0] + 1, end)
        # A year row may carry a footnote mark ("2020 (b)").
        groups = [index for index, row in enumerate(rows)
                  if len(row) == 1 and _label(row[0]) == str(end.year)]
        for start in groups:
            later = [index for index, row in enumerate(rows)
                     if index > start and len(row) == 1 and _YEAR.fullmatch(_label(row[0]))]
            stop = min(later, default=len(rows))
            totals = [row for row in rows[start + 1:stop] if row and _label(row[0]) == _LABELS["A13"]]
            scale = _scale(rows, headers[0] + 1)
            if len(totals) != 1 or scale is None or not _numbers(totals[0]) or window is None:
                continue
            figure = _numbers(totals[0])[0]
            reads.append({"table_ordinal": ordinal, "row": totals[0], "figure": figure,
                          "window": window, "value": str(_figure(figure) * scale)})
    return reads


def _name_words(text):
    """A name's words, so "Example & Co" and "Example & Co.:" compare alike."""
    return re.findall(r"[0-9a-z&]+", text.casefold())


def registrant_name(text):
    """The registrant's name as the filing's own DEI states it."""
    found = {_plain(match) for match in re.findall(
        r"<ix:nonNumeric[^>]*name=\"dei:EntityRegistrantName\"[^>]*>(.*?)</ix:nonNumeric>",
        text, re.S)}
    return found.pop() if len(found) == 1 else None


def read_lcr(text, period_end):
    """A03: the quarter-average table's registrant LCR and the selected data's firm LCR average."""
    end = date.fromisoformat(period_end)
    heading = "%s %d, %d" % (calendar.month_name[end.month], end.day, end.year)
    name = registrant_name(text)
    reads = []
    for ordinal, rows in tables(text):
        joined = " ".join(" ".join(row) for row in rows[:4])
        for index, row in enumerate(rows):
            if not row:
                continue
            if (_label(row[0]) == "lcr" and name is not None and "Three months ended" in joined
                    and "Average amount" in joined):
                groups = [prior for prior in rows[:index] if len(prior) == 1 and prior[0].endswith(":")]
                dates = [header for header in rows[:index] if heading in header]
                if not groups or _name_words(groups[-1][0]) != _name_words(name) or not dates:
                    continue
                columns = [cell for cell in dates[-1] if re.fullmatch(r"[A-Z][a-z]+ [0-9]{1,2}, [0-9]{4}", cell)]
                figures = _numbers(row)
                if heading not in columns or len(figures) != len(columns):
                    continue
                figure = figures[columns.index(heading)]
                months = end.month - 2
                start = date(end.year if months > 0 else end.year - 1, months if months > 0 else months + 12, 1)
                reads.append({"table_ordinal": ordinal, "source": "QUARTER_AVERAGE_TABLE", "row": row,
                              "group": groups[-1][0], "figure": figure,
                              "window": [start.isoformat(), end.isoformat()],
                              "value": str((_figure(figure) / 100).normalize())})
            elif re.fullmatch(r"firm liquidity coverage ratio \(.lcr.\) \(average\)", _label(row[0])):
                column, count = _year_column(rows, index, end.year)
                figures = _numbers(row)
                if column is None or len(figures) != count:
                    continue
                reads.append({"table_ordinal": ordinal, "source": "SELECTED_FINANCIAL_DATA", "row": row,
                              "figure": figures[column],
                              "value": str((_figure(figures[column]) / 100).normalize())})
    sources = {item["source"] for item in reads}
    if sources != {"QUARTER_AVERAGE_TABLE", "SELECTED_FINANCIAL_DATA"}:
        return []
    # The selected data's row is the same average; its window is the table's.
    windows = {tuple(item["window"]) for item in reads if "window" in item}
    for item in reads:
        if "window" not in item and len(windows) == 1:
            item["window"] = list(next(iter(windows)))
    return reads


def read_measures(text, period_end):
    """Every metric's reads and the one value and window they agree on, or why there is none."""
    end = date.fromisoformat(period_end)
    reads = {"A03": read_lcr(text, period_end),
             "A04": read_by_year_label(text, "A04", end),
             "A09": read_by_year_label(text, "A09", end),
             "A11": read_by_year_label(text, "A11", end),
             "A12": read_average_var(text, end),
             "A13": read_international_revenue(text, end)}
    out = {}
    for metric, found in reads.items():
        values = sorted({(Decimal(item["value"]), tuple(item["window"])) for item in found})
        out[metric] = {"reads": found,
                       "read": str(values[0][0]) if len(values) == 1 else None,
                       "window": list(values[0][1]) if len(values) == 1 else None,
                       "why_not_read": (None if len(values) == 1
                                        else "NO_TABLE_STATES_IT" if not found
                                        else "TABLES_DISAGREE")}
    return out


def main():
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--reading", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root", type=Path, default=REPO)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    body = {"reader": "tools/read_bank_measures.py", "requirement_closure_hash": arguments.closure,
            "per_position": {}, "calls": {"provider": 0, "paid": 0, "sec": 0}}
    with checkpoint_replayed_once():
        for company_id, report_end, label in reading_cases(arguments.reading):
            selection = resolve_period_selection(repo_root=arguments.source_root,
                                                 company_id=company_id, report_end=report_end)
            prepared = prepare_historical_annual_input(repo_root=arguments.source_root,
                                                       company_id=company_id,
                                                       period_selection=selection)
            document = prepared["original_input"]["table_input"]["source_repo_relative_path"]
            text = saved_bytes(repo_root=REPO, relative=document).decode("utf-8-sig", errors="replace")
            measures = read_measures(text, report_end)
            accession, _ = accession_of_document(repo_root=REPO, document=document)
            entry = {"company_id": company_id, "period_end": report_end, "document": document,
                     "registrant_name": registrant_name(text), "metrics": {}}
            for metric in METRICS:
                result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                        closure=arguments.closure)["result"]
                shown = None if result is None or result.get("value") is None else str(result["value"])
                read = measures[metric]["read"]
                row = {**measures[metric], "published": shown,
                       "verdict": ("NO_PUBLISHED_VALUE" if shown is None else "NOT_READ" if read is None
                                   else "MATCH" if Decimal(read) == Decimal(shown) else "DIFFERS")}
                if shown is not None:
                    identity, refusal = identity_for(
                        position={"company_id": company_id, "metric_id": metric,
                                  "period_end": report_end, "published": shown,
                                  "reading_filings": [accession],
                                  "reading_window": measures[metric]["window"],
                                  "filings_are_the_whole_set": False},
                        index=index, closure=arguments.closure)
                    if refusal is not None:
                        raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":" + refusal)
                    identity["established_by"] = "RECORDED_AT_READING_TIME"
                    row["checked_identity"] = identity
                entry["metrics"][metric] = row
            body["per_position"][label] = entry
            print(label, " ".join(metric + ":" + entry["metrics"][metric]["verdict"] for metric in METRICS),
                  flush=True)
    (REPO / arguments.output).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                                         + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
