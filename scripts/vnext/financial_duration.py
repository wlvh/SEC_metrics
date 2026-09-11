"""Inspect a financial table's actual measurement interval from source bytes.

This additive, offline component accepts a proposed origin cell and task terms,
not an audited fixture recipe or a reference answer. It supports an explicit
annual table header and a duration in a footnote linked by the measurement row.
It never turns a filing year, a point date, or the word ``average`` into a
duration. Unsupported associations remain unresolved.

The result is component evidence only. A caller must still bind the source,
task/Spec, entity, value, scale, and interpretation through the native Evidence
and Run path. This module does not select tables, authorize execution, establish
overall semantic correctness, or reinterpret existing Runs and publications.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Mapping, Sequence

from .canonical import content_hash, sha256_bytes
from .composite_scope import index_source_structure
from .constraints import ConstraintError, parse_numeric_claim
from .resource_limits import RESOURCE_LIMITS
from .table_grid import _AllTablesParser, _expanded_table


REVISION = "SOURCE_MEASUREMENT_DURATION_V1"
_ARGUMENT_FIELDS = frozenset({
    "expected_source_sha256", "table_id", "row_index", "column_index",
    "measurement_aliases", "required_row_terms", "reported_unit",
    "claimed_period_start", "claimed_period_end",
})
_YEAR = r"(?:19|20)[0-9]{2}"
_MONTHS = {name.casefold(): month for month in range(1, 13)
           for name in (calendar.month_name[month], calendar.month_abbr[month])}
_MONTH = "(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_DATE = re.compile(r"(" + _MONTH + r")\s+([0-9]{1,2}),?\s+(" + _YEAR + r")", re.I)
_FOOTNOTE = re.compile(r"^\s*\(([a-z]|[0-9]{1,2})\)", re.I)
_MARKER = re.compile(r"\(([a-z]|[0-9]{1,2})\)", re.I)
_MONTH_COUNTS = {"one": 1, "two": 2, "three": 3, "six": 6, "nine": 9, "twelve": 12}
_DURATION = re.compile(
    r"\b(" + "|".join(_MONTH_COUNTS) + r"|[0-9]{1,2})\s+months?\s+ended\s+"
    r"(" + _MONTH + r")\s+([0-9]{1,2}),?\s+(" + _YEAR + r")"
    r"((?:\s*(?:,\s*(?:and\s+)?|and\s+)" + _YEAR + r")*)", re.I,
)
_YEAR_END = re.compile(r"\byear\s+ended\s+(" + _MONTH + r")\s+([0-9]{1,2})", re.I)


class FinancialDurationError(ValueError):
    """Reject invalid inputs or an altered source-bound component receipt."""


def _text(value: str) -> str:
    return " ".join(value.split())


def _contains(*, text: str, term: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(_text(term)) + r"(?!\w)"
    return re.search(pattern, _text(text), flags=re.I) is not None


def _terms(*, values: Sequence[str], allow_empty: bool, field: str) -> list:
    if (type(values) not in (list, tuple) or (not values and not allow_empty)
            or any(type(value) is not str or not value.strip() for value in values)
            or len({_text(value).casefold() for value in values}) != len(values)):
        raise FinancialDurationError("INVALID_TASK_TERMS:" + field)
    return list(values)


def _date(*, year: int, month: str, day: int) -> date:
    return date(year, _MONTHS[month.casefold().rstrip(".")], day)


def _interval(*, end: date, months: int) -> dict:
    if not 1 <= months <= 12:
        raise FinancialDurationError("SOURCE_DURATION_OUT_OF_BOUNDS")
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise FinancialDurationError("SOURCE_DURATION_NON_MONTH_END_UNSUPPORTED")
    # A source's full N-month period ending at month end starts on day one
    # of its first included month, independent of the ending month's length.
    ordinal = end.year * 12 + end.month - months
    year, month = divmod(ordinal, 12)
    return {"period_start": date(year, month + 1, 1).isoformat(),
            "period_end": end.isoformat(), "duration_months": months}


def _cell_proof(*, table: Mapping, cell: Mapping) -> dict:
    return {"table_id": table["table_id"], "grid_sha256": table["grid_sha256"],
            **{key: cell[key] for key in (
                "row_index", "column_index", "origin_row_index", "origin_column_index",
                "rowspan", "colspan", "raw_text", "text")}}


def _column_period(*, table: Mapping, selected: Mapping) -> tuple:
    hits = []
    for row in table["rows"][:selected["row_index"]]:
        cells = [cell for cell in row["cells"] if cell["is_origin"] and cell["text"]]
        atoms = []
        for cell in cells:
            text = _text(cell["text"])
            full_date = _DATE.fullmatch(text)
            if re.fullmatch(_YEAR, text):
                atoms.append((cell, int(text), None))
            elif full_date:
                try:
                    value = _date(year=int(full_date[3]), month=full_date[1], day=int(full_date[2]))
                except ValueError:
                    return None, [], "SOURCE_COLUMN_DATE_INVALID"
                atoms.append((cell, value.year, value))
        if not atoms:
            continue
        # A body value of 2025 is not a year header. All other nonempty cells
        # in that row must be date/header/unit descriptors, never metric rows.
        atom_ids = {id(cell) for cell, _, _ in atoms}
        if any(id(cell) not in atom_ids and not (re.match(
                r"^(?:as of\b|(?:for the )?years? ended\b|in\b|\(in\b|\(dollars\b|change\b)",
                _text(cell["text"]), re.I) or re.fullmatch(
                    _MONTH + r"\s+[0-9]{1,2},?(?:\s+\(.*\))?",
                    _text(cell["text"]), re.I)) for cell in cells):
            continue
        hits.extend((cell, year, end) for cell, year, end in atoms
                    if cell["column_index"] <= selected["column_index"]
                    < cell["column_index"] + cell["colspan"])
    if not hits:
        return None, [], "COLUMN_PERIOD_NOT_PROVEN"
    last = max(cell["row_index"] for cell, _, _ in hits)
    hits = [hit for hit in hits if hit[0]["row_index"] == last]
    if len({(year, end) for _, year, end in hits}) != 1:
        return None, [], "COLUMN_PERIOD_AMBIGUOUS"
    _, year, end = hits[0]
    return {"year": year, "date": end, "row_index": last}, hits, None


def _linked_notes(*, structure: Mapping, table_order: int, markers: set) -> tuple:
    table = structure["tables"][table_order]
    later_tables = [item["start_byte"] for item in structure["tables"]
                    if item["start_byte"] >= table["end_byte"]]
    limit = min(later_tables, default=structure["source_size"])
    notes = {}
    # Only the contiguous numbered/lettered footnote block immediately after
    # this table can resolve a row marker. A heading or next table ends it.
    for block in structure["blocks"]:
        if block["inside_table"] or block["start_byte"] < table["end_byte"]:
            continue
        if block["start_byte"] >= limit:
            break
        match = _FOOTNOTE.match(_text(block["visible_text"]))
        if match is None:
            break
        notes.setdefault(match[1].casefold(), []).append(block)
    selected = [notes[marker][0] for marker in sorted(markers)
                if len(notes.get(marker, [])) == 1]
    missing = any(len(notes.get(marker, [])) != 1 for marker in markers)
    return selected, missing


def _footnote_intervals(*, notes: Sequence[Mapping], column: Mapping) -> tuple:
    intervals, unsupported = [], False
    for note in notes:
        text = _text(note["visible_text"])
        matches = list(_DURATION.finditer(text))
        if matches and re.search(r"\b(?:not|excluding)\b|\brather than\b|\binstead of\b", text, re.I):
            # This grammar does not interpret qualifications or negated
            # durations. Preserve the statement for the full semantic path.
            unsupported = True
        if not matches and (re.search(
                r"\b(?:quarter|months?|weeks?|days?|years?)\b|\bas of\b", text, re.I)
                or _DATE.search(text)):
            unsupported = True
        for match in matches:
            years = {int(match[4]), *map(int, re.findall(_YEAR, match[5]))}
            if column["year"] not in years:
                unsupported = True
                continue
            count_text = match[1].casefold()
            count = _MONTH_COUNTS.get(count_text, int(count_text) if count_text.isdecimal() else 0)
            try:
                end = _date(year=column["year"], month=match[2], day=int(match[3]))
                period = _interval(end=end, months=count)
            except ValueError:
                unsupported = True
                continue
            if column["date"] is not None and end != column["date"]:
                unsupported = True
                continue
            intervals.append(period)
    return intervals, unsupported


def _annual_interval(*, table: Mapping, column: Mapping) -> tuple:
    periods, evidence = [], []
    header_texts = [cell["text"] for row in table["rows"][:column["row_index"] + 1]
                    for cell in row["cells"] if cell["is_origin"]]
    if any(re.search(
            r"\bquarter\b|\b(?:one|two|three|six|nine|[1-9])\s+months?\s+ended\b|\bweeks?\s+ended\b",
            text, re.I) for text in header_texts):
        return [], []
    for row in table["rows"][:column["row_index"] + 1]:
        for cell in row["cells"]:
            if not cell["is_origin"]:
                continue
            text = _text(cell["text"])
            match = _YEAR_END.search(text)
            # Mixed stock/flow headers cannot establish which duration applies
            # to a particular measure. A row-linked footnote must resolve it.
            if not match or re.search(r"\bas of\b", text, re.I):
                continue
            try:
                end = _date(year=column["year"], month=match[1], day=int(match[2]))
                period = _interval(end=end, months=12)
            except ValueError:
                continue
            if column["date"] is not None and end != column["date"]:
                continue
            periods.append(period)
            evidence.append(_cell_proof(table=table, cell=cell))
    return periods, evidence


def inspect_financial_duration(
    *, source_bytes: bytes, expected_source_sha256: str, table_id: str,
    row_index: int, column_index: int, measurement_aliases: Sequence[str],
    required_row_terms: Sequence[str], reported_unit: str,
    claimed_period_start: str, claimed_period_end: str,
) -> dict:
    """Reconstruct and compare one proposed measurement interval, fully offline.

    Task terms must come from the caller's bound semantic contract. Their
    presence binds the period proof to the selected row; it is not a replacement
    for the native entity/scope checker. Only percent unit binding is supported
    here initially; other units remain unresolved without being reinterpreted.
    Inferred month intervals must end at a calendar month end. Non-month-end
    and week-based fiscal intervals require explicit source dates elsewhere.
    """
    if (type(source_bytes) is not bytes or not source_bytes
            or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes):
        raise FinancialDurationError("SOURCE_BYTES_INVALID")
    if sha256_bytes(content=source_bytes) != expected_source_sha256:
        raise FinancialDurationError("SOURCE_BYTES_DIFFER")
    aliases = _terms(values=measurement_aliases, allow_empty=False, field="measurement_aliases")
    terms = _terms(values=required_row_terms, allow_empty=True, field="required_row_terms")
    if (type(table_id) is not str or re.fullmatch(r"table_[0-9]{6}", table_id) is None
            or type(row_index) is not int or row_index < 0
            or type(column_index) is not int or column_index < 0
            or type(reported_unit) is not str or not reported_unit):
        raise FinancialDurationError("SELECTION_ARGUMENTS_INVALID")
    try:
        start, end = date.fromisoformat(claimed_period_start), date.fromisoformat(claimed_period_end)
        if start > end or start.isoformat() != claimed_period_start or end.isoformat() != claimed_period_end:
            raise ValueError("invalid interval")
    except (TypeError, ValueError) as error:
        raise FinancialDurationError("CLAIMED_PERIOD_INVALID") from error
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    order = int(table_id.split("_")[1]) - 1
    if not 0 <= order < len(parser.tables):
        raise FinancialDurationError("TABLE_NOT_FOUND")
    table, _ = _expanded_table(
        builder=parser.tables[order], remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
        remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars,
    )
    if row_index >= table["row_count"] or column_index >= table["column_count"]:
        raise FinancialDurationError("SELECTED_CELL_OUT_OF_RANGE")
    selected = table["rows"][row_index]["cells"][column_index]
    if not selected["is_origin"]:
        raise FinancialDurationError("SELECTED_CELL_NOT_ORIGIN")
    try:
        parse_numeric_claim(raw_value=selected["text"], reported_unit="ratio")
    except ConstraintError as error:
        raise FinancialDurationError("SELECTED_CELL_NOT_NUMERIC") from error
    labels = [cell for cell in table["rows"][row_index]["cells"]
              if cell["is_origin"] and cell["text"] and cell["column_index"] < column_index]
    matching = [cell for cell in labels if any(_contains(text=cell["text"], term=term) for term in aliases)]
    reasons = []
    if len(matching) != 1:
        reasons.append("MEASUREMENT_ROW_NOT_PROVEN")
    label = matching[0] if len(matching) == 1 else None
    if label is None or not all(_contains(text=label["text"], term=term) for term in terms):
        reasons.append("REQUIRED_ROW_TERM_NOT_PROVEN")
    if label is not None and re.search(
            r"\bas of\b|\b(?:period|year)[- ]end\b|\bend of (?:the )?year\b|\bpoint[- ]in[- ]time\b",
            label["text"], re.I):
        reasons.append("MEASUREMENT_ROW_IS_POINT_IN_TIME")
    structure = index_source_structure(source_bytes=source_bytes)
    markers = set(_MARKER.findall(label["text"].casefold())) if label else set()
    notes, missing = _linked_notes(structure=structure, table_order=order, markers=markers)
    if missing:
        reasons.append("ROW_FOOTNOTE_NOT_PROVEN")
    next_cells = [cell for cell in table["rows"][row_index]["cells"]
                  if cell["is_origin"] and cell["text"]
                  and cell["column_index"] >= column_index + selected["colspan"]]
    unit_cells = next_cells[:1] if next_cells and next_cells[0]["text"] == "%" else []
    unit_notes = [note for note in notes if re.search(
        r"\bpercentage\s+represents\s+(?:average\s+)?ratios?\s+for\b",
        _text(note["visible_text"]), re.I)]
    if reported_unit != "percent" or not (unit_cells or unit_notes or selected["text"].endswith("%")):
        reasons.append("REPORTED_UNIT_NOT_PROVEN")
    column, header_hits, column_reason = _column_period(table=table, selected=selected)
    if column_reason:
        reasons.append(column_reason)
    intervals, annual_cells, basis = [], [], None
    if (column is not None and not missing
            and "MEASUREMENT_ROW_IS_POINT_IN_TIME" not in reasons):
        intervals, unsupported = _footnote_intervals(notes=notes, column=column)
        if unsupported:
            reasons.append("FOOTNOTE_DURATION_UNSUPPORTED")
        if intervals:
            basis = "ROW_LINKED_FOOTNOTE"
        elif not unsupported:
            intervals, annual_cells = _annual_interval(table=table, column=column)
            basis = "EXPLICIT_ANNUAL_TABLE_HEADER" if intervals else None
    unique = {(p["period_start"], p["period_end"], p["duration_months"]) for p in intervals}
    if len(unique) > 1:
        reasons.append("CONFLICTING_MEASUREMENT_PERIODS")
    measurement_period = intervals[0] if len(unique) == 1 else None
    if measurement_period is None:
        reasons.append("MEASUREMENT_DURATION_NOT_PROVEN")
    status = "UNRESOLVED" if reasons else "PASSED"
    if measurement_period is not None and (
            measurement_period["period_start"] != claimed_period_start
            or measurement_period["period_end"] != claimed_period_end):
        reasons.append("CLAIMED_MEASUREMENT_PERIOD_DIFFERS")
        status = "REJECTED"
    arguments = {"expected_source_sha256": expected_source_sha256,
                 "table_id": table_id, "row_index": row_index, "column_index": column_index,
                 "measurement_aliases": aliases, "required_row_terms": terms,
                 "reported_unit": reported_unit, "claimed_period_start": claimed_period_start,
                 "claimed_period_end": claimed_period_end}
    body = {
        "record_type": "FINANCIAL_MEASUREMENT_DURATION_COMPONENT", "schema_version": 1,
        "revision": REVISION, "status": status, "reasons": reasons,
        "source_sha256": expected_source_sha256, "source_size": len(source_bytes),
        "arguments": arguments, "selected_cell": _cell_proof(table=table, cell=selected),
        "measurement_row": None if label is None else _cell_proof(table=table, cell=label),
        "table_source_span": structure["tables"][order],
        "column_period_evidence": [_cell_proof(table=table, cell=cell) for cell, _, _ in header_hits],
        "linked_footnotes": notes, "annual_header_evidence": annual_cells,
        "unit_evidence_cells": [_cell_proof(table=table, cell=cell) for cell in unit_cells],
        "unit_evidence_footnote_spans": [{key: note[key] for key in ("start_byte", "end_byte", "span_sha256")}
                                         for note in unit_notes],
        "measurement_period": measurement_period, "duration_basis": basis,
        "qualification_credit": "NONE_COMPONENT_ONLY", "publication_credit": "NONE",
    }
    return {**body, "duration_receipt_id": content_hash(value=body)}


def validate_financial_duration_receipt(*, receipt: Mapping, source_bytes: bytes) -> dict:
    """Independently reconstruct the component result from its original bytes."""
    if (type(receipt) is not dict or type(receipt.get("arguments")) is not dict
            or set(receipt["arguments"]) != _ARGUMENT_FIELDS):
        raise FinancialDurationError("RECEIPT_SHAPE_INVALID")
    rebuilt = inspect_financial_duration(source_bytes=source_bytes, **receipt["arguments"])
    if rebuilt != receipt:
        raise FinancialDurationError("RECEIPT_REPLAY_DIFFERS")
    return rebuilt
