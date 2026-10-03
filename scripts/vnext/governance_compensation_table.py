"""Read a bounded Summary Compensation Table through native table locators.

This additive source adapter never chooses a company, fixed table number or
expected amount. Source-derived header, person, year, Total and actual period
must agree. The earlier ECD route is not modified or silently reinterpreted.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Mapping

from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash
from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
from .governance_signals import _FactAttributes
from .observations import scope_key, structured_observation
from .table_grid import build_table_grid, resolve_cell
from .text_coverage import build_text_document, _byte_offsets, _period_text


RESOLVER = "reported_compensation_table_v2"
SPEC_PATH = "catalog/r5/C03_reported_compensation_v2.md"
_DATE = r"(?:[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})"
_TITLE = re.compile(r"^summary compensation table(?:\s+(?:for|for fiscal|fiscal year)\s+\d{4})?\s*$", re.I)
_CEO = re.compile(r"\b(?:chief executive officer|principal executive officer|CEO|PEO)\b", re.I)
_NUMBER = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"
_LOCATOR_FIELDS = ("row_index", "column_index", "origin_row_index", "origin_column_index", "rowspan", "colspan")


class CompensationTableError(ValueError):
    """Report absent, ambiguous or unsupported compensation evidence."""


def _need(condition, reason):
    if not condition:
        raise CompensationTableError(reason)


class _TableRanges(HTMLParser):
    """Bind native table order to the original HTML extent, not a new grid."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.tables, self.stack = [], []

    def _offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append(len(self.tables))
            self.tables.append({"start": self._offset(), "end": None})

    def handle_endtag(self, tag):
        if tag == "table":
            _need(bool(self.stack), "SCT_UNMATCHED_TABLE_END")
            self.tables[self.stack.pop()]["end"] = self._offset() + len("</table>")


def _locator(asset, table, cell):
    return {"derived_asset_id": asset["derived_asset_id"], "table_id": table["table_id"],
            **{k: cell[k] for k in _LOCATOR_FIELDS}}


def _cell_evidence(asset, table, cell):
    locator = _locator(asset, table, cell)
    recovered = resolve_cell(derived_asset=asset, locator=locator)
    _need(recovered == cell, "SCT_NATIVE_CELL_RECOVERY_MISMATCH")
    return {"locator": locator, "raw_text": cell["raw_text"], "text": cell["text"]}


def _origin_cells(row):
    return [c for c in row["cells"] if c["is_origin"] and c["text"].strip()]


def _registrant_ceo(text):
    match = _CEO.search(text)
    if match is None or re.search(r"assistant to|deputy|vice |office of|staff to", text[:match.start()], re.I):
        return False
    suffix = text[match.end():].strip(" ,;&")
    return bool(not suffix or re.fullmatch(r"(?:and\s+)?(?:President|Chairman)(?:\s+of\s+the\s+Board)?\s*(?:\(\d+\))?", suffix, re.I))


def _header_role(text):
    value = " ".join(text.split())
    value = re.sub(r"\s*\(\d+\)\s*$", "", value)
    if re.fullmatch(r"name(?: and)? (?:principal )?position", value, re.I): return "person"
    if re.fullmatch(r"(?:fiscal )?year", value, re.I): return "year"
    if re.fullmatch(r"total\s*(?:\(\s*(?:\$|USD|U\.S\. dollars)\s*\)|USD|\$)", value, re.I): return "total"
    return None


def _column_cell(row, header):
    start, end = header["column_index"], header["column_index"] + header["colspan"]
    cells = []
    seen = set()
    for cell in row["cells"][start:end]:
        identity = (cell["origin_row_index"], cell["origin_column_index"])
        if cell["text"].strip() and identity not in seen:
            cells.append(cell)
            seen.add(identity)
    _need(len(cells) == 1, "SCT_COLUMN_VALUE_AMBIGUOUS")
    return cells[0]


def _text_evidence(document, block):
    return {"source_reference_id": document["source_reference_id"], "raw_asset_id": document["raw_asset_id"],
            **{k: block[k] for k in ("block_index", "text", "raw_start_byte", "raw_end_byte", "raw_span_sha256")}}


def _period(*, document, context_blocks, report_period_start, report_period_end, fiscal_year):
    text = " ".join(b["text"] for b in context_blocks)
    statements = list(re.finditer(r"for the period (?:commencing|beginning|starting)\s+(?:on\s+)?(?:the\s+)?(?P<start>Closing Date|" + _DATE + r")\s+and ending\s+(?:on\s+)?(?P<end>" + _DATE + r")", text, re.I))
    _need(len({(m.group("start").casefold(), m.group("end").casefold()) for m in statements}) <= 1,
          "SCT_CONFLICTING_PERIOD_STATEMENTS")
    covered = statements[0] if statements else None
    evidence = [_text_evidence(document, b) for b in context_blocks]
    if covered:
        end = _period_text(covered.group("end"))
        if covered.group("start").casefold() == "closing date":
            definitions = []
            pattern = re.compile(r"(?P<date>" + _DATE + r")\s*\(\s*(?:the\s+)?[“\"']Closing Date[”\"']\s*\)", re.I)
            for block in document["blocks"]:
                for match in pattern.finditer(block["text"]):
                    definitions.append((_period_text(match.group("date")), block))
            dates = {d for d, _ in definitions}
            _need(len(dates) == 1, "SCT_CLOSING_DATE_MISSING_OR_CONFLICTING")
            start = next(iter(dates))
            evidence.extend(_text_evidence(document, b) for _, b in definitions)
        else:
            start = _period_text(covered.group("start"))
        _need(start <= end == report_period_end, "SCT_COVERED_PERIOD_CONFLICT")
        return {"period_start": start, "period_end": end, "basis": "EXPLICIT_COVERED_PERIOD", "evidence": evidence}
    annual = re.search(r"for (?:the )?(?:fiscal )?year(?:s)? ended\s+(?P<end>" + _DATE + r")", text, re.I)
    _need(annual is not None and _period_text(annual.group("end")) == report_period_end,
          "SCT_ACTUAL_PERIOD_NOT_ESTABLISHED")
    _need(report_period_start < report_period_end, "SCT_FISCAL_PERIOD_CONFLICT")
    return {"period_start": report_period_start, "period_end": report_period_end,
            "basis": "EXPLICIT_FISCAL_YEAR_AND_BOUND_REPORT_DURATION", "evidence": evidence}


def resolve_compensation_table(*, raw_bytes: bytes, raw_blob: Mapping, source_reference: Mapping,
                               expected_company_id: str, expected_cik: str,
                               report_period_start: str, report_period_end: str,
                               fiscal_year: int, compiled_spec: Mapping) -> dict:
    """Produce one native C03 amount with its actual disclosed measurement period.

    The first supported fallback is an annual report/Part III amendment with
    explicit source identity and a local SCT heading/period paragraph. Ordinary
    ECD selection stays with resolve_c03. This function never marks a source
    lacking a supported table grammar as publicly undisclosed.
    """
    semantic = compiled_spec["compiled"]
    _need(semantic["metric_id"] == "C03" and semantic["kind"] == "direct_numeric"
          and semantic["canonical_unit"] == "USD" and semantic["quality_rule"].get("resolver") == RESOLVER,
          "SCT_SUCCESSOR_SPEC_REQUIRED")
    document = build_text_document(raw_bytes=raw_bytes, raw_blob=raw_blob, source_reference=source_reference,
        expected_company_id=expected_company_id, expected_cik=expected_cik, expected_period_end=report_period_end)
    _need(not (set(document["source_reasons"]) - {"TEXT_AMENDMENT_SOURCE_SET_REQUIRED"}), "SCT_INCOMPLETE_SOURCE_DOCUMENT")
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    attrs = _FactAttributes()
    attrs.feed(raw_bytes.decode("utf-8"))
    attrs.close()
    _need(attrs.unit is None and attrs.measure is None and attrs.ordinal == len(parsed.facts), "SCT_UNIT_OR_FACT_STREAM_INCOMPLETE")
    dei = [f for f in parsed.facts if re.fullmatch(r"https?://xbrl\.sec\.gov/dei/\d{4}", attrs.facts[f["ordinal"]]["concept"][0])]
    periods = {tuple(parsed.contexts[f["context_ref"]][k] for k in ("period_start", "period_end"))
               for f in dei if attrs.facts[f["ordinal"]]["concept"][1].casefold() == "documentperiodenddate"}
    _need(periods == {(report_period_start, report_period_end)}, "SCT_REPORT_DURATION_MISMATCH")
    year_facts = [f for f in dei if attrs.facts[f["ordinal"]]["concept"][1].casefold() == "documentfiscalyearfocus"]
    years = {str(f["text"]) for f in year_facts}
    _need(years == {str(fiscal_year)}, "SCT_REPORT_FISCAL_YEAR_MISMATCH")
    _need(all(tuple(parsed.contexts[f["context_ref"]][k] for k in ("period_start", "period_end")) == (report_period_start, report_period_end) for f in year_facts),
          "SCT_FISCAL_YEAR_CONTEXT_CONFLICT")
    currencies = {measure[1] for unit in attrs.units.values() for measure in unit["measures"]
                  if not unit["divided"] and len(unit["measures"]) == 1 and measure[0] == "http://www.xbrl.org/2003/iso4217"}
    text = raw_bytes.decode("utf-8")
    ranges = _TableRanges(text)
    ranges.feed(text)
    ranges.close()
    _need(not ranges.stack, "SCT_UNCLOSED_TABLE")
    offsets = _byte_offsets(text, [p for r in ranges.tables for p in (r["start"], r["end"])])
    asset = build_table_grid(html_bytes=raw_bytes, parent_raw_asset_ids=[raw_blob["raw_asset_id"]], storage_uri="derived/governance-compensation-table.json")
    _need(len(asset["tables"]) == len(ranges.tables), "SCT_NATIVE_TABLE_SET_MISMATCH")
    candidates, diagnostics = [], []
    for table, extent in zip(asset["tables"], ranges.tables):
        header_candidates = []
        for row in table["rows"][:8]:
            roles = {}
            for cell in _origin_cells(row):
                role = _header_role(cell["text"])
                if role: roles.setdefault(role, []).append(cell)
            if set(roles) == {"person", "year", "total"}:
                header_candidates.append((row["row_index"], roles))
        if not header_candidates:
            continue
        table_start = offsets[extent["start"]]
        preceding = [b for b in document["blocks"] if b["raw_end_byte"] <= table_start]
        titles = [i for i, b in enumerate(preceding) if _TITLE.fullmatch(b["text"]) and not b["linked"]]
        if not titles:
            diagnostics.append({"table_id": table["table_id"], "reason": "SCT_TITLE_NOT_ESTABLISHED"})
            continue
        context_blocks = preceding[titles[-1]:]
        if len(context_blocks) > 12 or sum(len(b["text"]) for b in context_blocks) > 6000:
            diagnostics.append({"table_id": table["table_id"], "reason": "SCT_LOCAL_CONTEXT_TOO_DISTANT"})
            continue
        try:
            title_year = re.search(r"\b(\d{4})\b", context_blocks[0]["text"])
            _need(title_year is None or int(title_year.group(1)) == fiscal_year, "SCT_TITLE_YEAR_CONFLICT")
            _need(len(header_candidates) == 1, "SCT_MULTIPLE_HEADER_ROWS")
            header_index, roles = header_candidates[0]
            _need(all(len(v) == 1 for v in roles.values()), "SCT_MULTIPLE_TOTAL_OR_IDENTITY_COLUMNS")
            header = {k: v[0] for k, v in roles.items()}
            context_text = " ".join(b["text"] for b in context_blocks)
            _need(not re.search(r"Canadian dollars|Australian dollars|Hong Kong dollars|euros|British pounds|yen|yuan|\b(?:CAD|AUD|HKD|EUR|GBP|JPY|CNY|CHF)\b|[€£¥]", context_text, re.I), "SCT_CONFLICTING_CURRENCY_CONTEXT")
            _need(not re.search(r"in (?:thousands|millions|billions)", context_text, re.I), "SCT_SCALED_CURRENCY_UNSUPPORTED")
            explicit_usd = bool(re.search(r"\bUSD\b|U\.S\. dollars", header["total"]["text"] + " " + context_text, re.I))
            _need(explicit_usd or currencies == {"USD"}, "SCT_USD_CURRENCY_NOT_ESTABLISHED")
            period = _period(document=document, context_blocks=context_blocks,
                report_period_start=report_period_start, report_period_end=report_period_end, fiscal_year=fiscal_year)
            table_candidates = []
            for row in table["rows"][header_index + 1:]:
                try:
                    person = _column_cell(row, header["person"])
                except CompensationTableError:
                    continue
                if not _registrant_ceo(person["text"]):
                    continue
                year = _column_cell(row, header["year"])
                _need(re.fullmatch(r"\d{4}", year["text"].strip()) is not None, "SCT_CEO_YEAR_NOT_EXPLICIT")
                if int(year["text"].strip()) != fiscal_year:
                    continue
                amount = _column_cell(row, header["total"])
                lexical = amount["text"].strip()
                _need(re.fullmatch(r"(?:-?" + _NUMBER + r"|\(" + _NUMBER + r"\))", lexical) is not None, "SCT_REPORTED_TOTAL_NOT_NUMERIC")
                value = _numeric_xbrl_value(text=lexical, scale="0", sign="")
                table_candidates.append({"table_id": table["table_id"], "table_grid_sha256": table["grid_sha256"],
                    "person_and_position": person["text"], "fiscal_year": fiscal_year, "value": value, "unit": "USD",
                    "currency_basis": "EXPLICIT_USD_SCOPE" if explicit_usd else "DOLLAR_HEADER_AND_UNIQUE_DOCUMENT_USD_UNIT",
                    "period": period, "person": _cell_evidence(asset, table, person),
                    "year": _cell_evidence(asset, table, year), "amount": _cell_evidence(asset, table, amount),
                    "headers": {k: _cell_evidence(asset, table, v) for k, v in header.items()}})
            _need(bool(table_candidates), "SCT_CEO_ROW_NOT_FOUND")
            unique = {}
            for candidate in table_candidates:
                key = tuple(candidate[role]["locator"][field] for role in ("person", "year", "amount") for field in ("origin_row_index", "origin_column_index"))
                if key not in unique:
                    unique[key] = candidate
            candidates.extend(unique.values())
        except ValueError as error:
            diagnostics.append({"table_id": table["table_id"], "reason": str(error)})
    reason = "PASS" if len(candidates) == 1 and not diagnostics else "SCT_AMBIGUOUS_OR_UNSUPPORTED_EVIDENCE" if candidates or diagnostics else "SCT_SUPPORTED_TABLE_NOT_FOUND"
    scope = {"entity_scope": "registrant"}
    target = {"company_id": expected_company_id, "period_start": report_period_start, "period_end": report_period_end,
              "scope": scope, "scope_key": scope_key(scope=scope)}
    if reason == "PASS":
        target.update(period_start=candidates[0]["period"]["period_start"], period_end=candidates[0]["period"]["period_end"])
    selection = {"resolver": RESOLVER, "source_reference_id": source_reference["source_reference_id"],
                 "raw_asset_id": raw_blob["raw_asset_id"], "derived_asset_id": asset["derived_asset_id"],
                 "text_document_id": document["text_document_id"], "report_period_start": report_period_start,
                 "report_period_end": report_period_end, "fiscal_year": fiscal_year, "actual_result_target": target,
                 "candidates": candidates, "diagnostics": diagnostics, "reason_code": reason}
    selection["selection_id"] = content_hash(value=selection)
    observation = None
    if reason == "PASS":
        observation = structured_observation(metric_id="C03", semantic_role="reported_total_compensation",
            company_id=expected_company_id, period_start=target["period_start"], period_end=target["period_end"], scope=scope,
            value=candidates[0]["value"], unit="USD", quality="EXACT",
            source_binding={"raw_asset_id": raw_blob["raw_asset_id"], "source_reference_id": source_reference["source_reference_id"],
                            "accession": source_reference["accession"], "document_name": source_reference["document_name"],
                            "source_role": source_reference["source_role"], "selection_id": selection["selection_id"],
                            "derived_asset_id": asset["derived_asset_id"], "amount_locator": candidates[0]["amount"]["locator"]})
        result, trace = calculate_observation_metric(compiled_spec=compiled_spec, target=target, company_traits=[], observation=observation)
    else:
        result, trace = withheld_metric_result(compiled_spec=compiled_spec, target=target, reason_code=reason)
    return {"record_type": "C03_REPORTED_TABLE_RESOLUTION", "selection": selection, "observation": observation,
            "derived_assets": [asset], "result": result, "trace": trace,
            "business_calls": [0, 0, 0], "formal_publication_authorized": False}


def replay_compensation_table(*, resolution: Mapping, **source_args) -> dict:
    """Rebuild all source/cell/period relationships before comparing a result."""
    rebuilt = resolve_compensation_table(**source_args)
    _need(rebuilt == resolution, "SCT_NATIVE_REPLAY_MISMATCH")
    return rebuilt
