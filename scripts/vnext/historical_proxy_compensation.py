"""C03 from the Summary Compensation Table of a proxy without inline XBRL.

Purpose:
    The approved C03 source is the DEF 14A, ECD facts preferred. Proxies
    carried ECD facts only once pay-versus-performance required tagging, so the
    proxies filed in 2022 - the ones that first report fiscal 2021, and fiscal
    2022 for a January year-end - have none, and their Summary Compensation
    Table is the approved source left. The frozen table reader
    (``governance_compensation_table.resolve_compensation_table``) was written
    for an annual report's Part III: it binds the period through the report's
    DEI facts and reads the Total through header cells aligned with row cells.
    A proxy has no DEI facts, and on the eight saved 2022 proxies the header
    cells do not align with the rows in five: Enphase puts "$" in cells of its
    own, Ford pads with zero-width cells, Macy's splits its header over three
    rows and prints the chief executive's title on the row below his name,
    Lumen's header says only "Total", and Paramount's and Macy's titles carry
    the year.

    What this reader relies on instead is the table's own arithmetic. Item
    402(c) defines the Total as the sum of the other amounts in the row, so the
    fiscal-year row of each executive is read as its amounts in order, and the
    last is taken as the Total only when it equals the sum of the others. A
    column that slipped, a "$" cell or a zero-width cell cannot pass that; a
    reading that does pass it has found the Total the filer reported. Measured
    on the eight proxies: every chief executive's row passes it.

    The rest is the definition's: one chief executive (a year with two - a
    successor and a predecessor, or co-chief executives - is withheld with every
    candidate kept), the row whose year is the pinned annual report's fiscal
    year, the proxy's identity from its cover (``historical_proxy_identity``),
    a dollar sign in the table, and the frozen reader's refusal of foreign or
    scaled currency in the context.

How an executive is read:
    Each executive's rows start at a row whose year cell is the fiscal year -
    a proxy lists each named executive's years newest first, and every named
    executive has the newest - and run to the next such row. The text before
    the year in those rows, and the rows holding only text, are the name and
    title. It names the registrant's chief executive when it has "Chief
    Executive Officer", "CEO" or "PEO", not directly after "Deputy",
    "Assistant to", "Vice", "Office of" or "Staff to", and not followed by a
    comma, "of" or a dash naming another body: Macy's lists "Chairman & CEO,
    Bloomingdale's", a subsidiary's chief executive.

Call relationships:
    ``historical_governance_results._compensation_resolution`` calls
    ``resolve_proxy_compensation_table`` when the pinned proxy has no inline
    XBRL, before the annual report's table stage.
"""
from __future__ import annotations

import re

from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash
from .deterministic_router import _numeric_xbrl_value
from .governance_compensation_table import (_CEO, _TableRanges, _cell_evidence,
                                            _origin_cells)
from .historical_proxy_identity import (carries_inline_xbrl, cover_name_in_effect,
                                        governance_source_document, proxy_cover)
from .observations import scope_key, structured_observation
from .table_grid import build_table_grid
from .text_coverage import _byte_offsets

RESOLVER = "proxy_compensation_table_v1"
SPEC_PATH = "catalog/r6/C03_proxy_compensation_table_v1.md"
RECORD_TYPE = "C03_PROXY_TABLE_RESOLUTION"
_TITLE = re.compile(r"^(?:(?P<before>\d{4})\s+)?summary compensation table"
                    r"(?:\s+for(?:\s+fiscal)?(?:\s+year)?\s+(?P<after>\d{4}))?$", re.I)
_YEAR = re.compile(r"(?:19|20)\d{2}")
_FOOTNOTES = r"(?:\(\d{1,2}\))*"
_AMOUNT = re.compile(r"\$?\s*(?P<number>\d{1,3}(?:,\d{3})+|\d+)" + _FOOTNOTES)
_NIL = re.compile(r"\$?\s*[—–−-]" + _FOOTNOTES)
_FOOTNOTE_ONLY = re.compile(r"(?:\(\d{1,2}\))+")
# The frozen table reader's two context refusals, verbatim.
_FOREIGN_CURRENCY = (r"Canadian dollars|Australian dollars|Hong Kong dollars|euros|British pounds|yen|yuan"
                     r"|\b(?:CAD|AUD|HKD|EUR|GBP|JPY|CNY|CHF)\b|[€£¥]")
_SCALED = r"in (?:thousands|millions|billions)"
_NOT_THE_CHIEF = re.compile(r"(?:assistant to(?: the)?|deputy|vice|office of(?: the)?|staff to(?: the)?)\s*$",
                            re.I)
_ANOTHER_BODY = re.compile(r"\s*(?:,|\bof\b|—|–|-)\s*\S", re.I)
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
_CONTEXT_BLOCKS, _CONTEXT_CHARS = 12, 6000


class HistoricalProxyCompensationError(ValueError):
    """The proxy's table cannot be read as this route reads it."""


def _need(condition, reason):
    if not condition:
        raise HistoricalProxyCompensationError(reason)


def _clean(text):
    return " ".join(text.translate(_ZERO_WIDTH).split())


def names_the_chief_executive(text):
    """Whether an executive's name-and-title text names the registrant's chief executive."""
    for match in _CEO.finditer(text):
        if _NOT_THE_CHIEF.search(text[:match.start()]):
            continue
        if _ANOTHER_BODY.match(text[match.end():]):
            continue
        return True
    return False


def row_amounts(tokens):
    """The row's amounts after its year, as integers, or None if a token is not an amount."""
    amounts = []
    for token in tokens:
        if _FOOTNOTE_ONLY.fullmatch(token):
            continue
        amount = _AMOUNT.fullmatch(token)
        if amount:
            amounts.append((int(amount.group("number").replace(",", "")), amount.group("number")))
        elif _NIL.fullmatch(token):
            amounts.append((0, "0"))
        else:
            return None
    return amounts


def _cells(row):
    """A row's non-empty origin cells with their cleaned text; a lone "$" is not a cell."""
    return [(cell, _clean(cell["text"])) for cell in _origin_cells(row)
            if _clean(cell["text"]) not in ("", "$")]


def _title_year(text):
    match = _TITLE.fullmatch(_clean(text))
    if match is None:
        return None
    return match.group("before") or match.group("after") or ""


def _executives(table, fiscal_year):
    """Each named executive's rows, from a fiscal-year row to the next."""
    rows = [_cells(row) for row in table["rows"]]
    year_rows = [index for index, cells in enumerate(rows)
                 if any(_YEAR.fullmatch(text) for _, text in cells)]
    if not year_rows:
        return None, []
    header = " ".join(text for cells in rows[:year_rows[0]] for _, text in cells)
    starts = [index for index in year_rows
              if any(text == str(fiscal_year) for _, text in rows[index])]
    people = []
    for position, start in enumerate(starts):
        stop = starts[position + 1] if position + 1 < len(starts) else len(rows)
        name_cells, fiscal = [], None
        for index in range(start, stop):
            cells = rows[index]
            year_at = next((at for at, (_, text) in enumerate(cells) if _YEAR.fullmatch(text)), None)
            name_cells.extend(cells if year_at is None else cells[:year_at])
            if index == start:
                fiscal = (cells[year_at], cells[year_at + 1:])
        people.append({"name_cells": name_cells, "year_cell": fiscal[0], "amount_cells": fiscal[1],
                       "text": " ".join(text for _, text in name_cells)})
    return header, people


def resolve_proxy_compensation_table(*, raw_bytes, raw_blob, source_reference, filing, inventory,
                                     company_id, cik, target, fiscal_year, compiled_spec):
    """C03 from a proxy's Summary Compensation Table; see the module docstring.

    Args:
        raw_bytes, raw_blob, source_reference: The pinned proxy as the reader
            admitted it.
        filing: The proxy's submissions row.
        inventory: The registrant's submissions record, for the cover's name.
        target: The pinned period's C03 target (company, period, scope).
        fiscal_year: The pinned annual report's fiscal-year label.
        compiled_spec: The compiled ``SPEC_PATH`` Spec.

    Returns:
        The resolution the historical component consumes: the selection with
        every chief-executive candidate, the observation when exactly one
        passes, the table grid, and the Result with its trace.
    """
    semantic = compiled_spec["compiled"]
    _need(semantic["metric_id"] == "C03" and semantic["quality_rule"].get("resolver") == RESOLVER,
          "C03_PROXY_SCT_SPEC_REQUIRED")
    _need(not carries_inline_xbrl(raw_bytes), "C03_PROXY_SCT_ONLY_FOR_A_PROXY_WITHOUT_INLINE_XBRL")
    document = governance_source_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
                                          source_reference=source_reference, company_id=company_id,
                                          cik=cik, filing=filing)
    identity = cover_name_in_effect(cover=proxy_cover(raw_bytes=raw_bytes, filing=filing),
                                    inventory=inventory, filing=filing)
    text = raw_bytes.decode("utf-8")
    ranges = _TableRanges(text)
    ranges.feed(text)
    ranges.close()
    _need(not ranges.stack, "C03_PROXY_SCT_UNCLOSED_TABLE")
    offsets = _byte_offsets(text, [p for extent in ranges.tables for p in (extent["start"], extent["end"])])
    asset = build_table_grid(html_bytes=raw_bytes, parent_raw_asset_ids=[raw_blob["raw_asset_id"]],
                             storage_uri="derived/governance-proxy-compensation-table.json")
    _need(len(asset["tables"]) == len(ranges.tables), "C03_PROXY_SCT_NATIVE_TABLE_SET_MISMATCH")
    candidates, diagnostics = [], []
    for table, extent in zip(asset["tables"], ranges.tables):
        header, people = _executives(table, fiscal_year)
        if header is None or not all(re.search(r"\b" + word + r"\b", header, re.I)
                                     for word in ("total", "year", "salary")):
            continue
        start = offsets[extent["start"]]
        preceding = [block for block in document["blocks"]
                     if block["raw_end_byte"] <= start and not block["linked"]][-_CONTEXT_BLOCKS:]
        titled = [index for index, block in enumerate(preceding) if _title_year(block["text"]) is not None]
        header_titles = [text for cells in table["rows"][:3] for text in
                         (_clean(cell["text"]) for cell in _origin_cells(cells))
                         if _title_year(text) is not None]
        if not titled and not header_titles:
            diagnostics.append({"table_id": table["table_id"], "reason": "C03_PROXY_SCT_TITLE_NOT_ESTABLISHED"})
            continue
        context = preceding[titled[-1]:] if titled else []
        title_texts = [block["text"] for block in context[:1]] + header_titles
        years = {_title_year(title) for title in title_texts} - {""}
        context_text = " ".join(block["text"] for block in context) + " " + header
        reason = None
        if years and years != {str(fiscal_year)}:
            reason = "C03_PROXY_SCT_TITLE_YEAR_CONFLICT"
        elif sum(len(block["text"]) for block in context) > _CONTEXT_CHARS:
            reason = "C03_PROXY_SCT_TITLE_TOO_DISTANT"
        elif re.search(_FOREIGN_CURRENCY, context_text, re.I):
            reason = "C03_PROXY_SCT_CONFLICTING_CURRENCY_CONTEXT"
        elif re.search(_SCALED, context_text, re.I):
            reason = "C03_PROXY_SCT_SCALED_CURRENCY_UNSUPPORTED"
        if reason:
            diagnostics.append({"table_id": table["table_id"], "reason": reason})
            continue
        for person in people:
            if not names_the_chief_executive(person["text"]):
                continue
            amounts = row_amounts([text for _, text in person["amount_cells"]])
            candidate = {"table_id": table["table_id"], "table_grid_sha256": table["grid_sha256"],
                         "person_and_position": person["text"], "fiscal_year": fiscal_year,
                         "person": [_cell_evidence(asset, table, cell) for cell, _ in person["name_cells"]],
                         "year": _cell_evidence(asset, table, person["year_cell"][0])}
            if amounts is None or len(amounts) < 3:
                candidate["reason"] = "C03_PROXY_SCT_ROW_UNREADABLE"
            elif sum(value for value, _ in amounts[:-1]) != amounts[-1][0]:
                candidate["reason"] = "C03_PROXY_SCT_TOTAL_IS_NOT_THE_SUM_OF_ITS_COMPONENTS"
            elif "$" not in header + " ".join(text for _, text in person["amount_cells"]):
                candidate["reason"] = "C03_PROXY_SCT_DOLLAR_NOT_ESTABLISHED"
            else:
                total_cell = person["amount_cells"][-1][0]
                candidate.update(reason="PASS", unit="USD",
                                 value=_numeric_xbrl_value(text=amounts[-1][1], scale="0", sign=""),
                                 components=[value for value, _ in amounts[:-1]],
                                 amount=_cell_evidence(asset, table, total_cell))
            candidates.append(candidate)
    passing = [candidate for candidate in candidates if candidate["reason"] == "PASS"]
    if len(candidates) == 1 and passing:
        reason = "PASS"
    elif len(candidates) > 1:
        reason = "C03_PROXY_SCT_MORE_THAN_ONE_CHIEF_EXECUTIVE"
    elif candidates:
        reason = candidates[0]["reason"]
    elif diagnostics:
        reason = "C03_PROXY_SCT_NOT_ESTABLISHED"
    else:
        reason = "C03_PROXY_SCT_NOT_FOUND"
    selection = {"resolver": RESOLVER, "source_reference_id": source_reference["source_reference_id"],
                 "raw_asset_id": raw_blob["raw_asset_id"], "derived_asset_id": asset["derived_asset_id"],
                 "text_document_id": document["text_document_id"], "proxy_cover_identity": identity,
                 "report_period_start": target["period_start"], "report_period_end": target["period_end"],
                 "fiscal_year": fiscal_year, "period_basis": "TABLE_YEAR_EQUALS_PINNED_FISCAL_YEAR",
                 "candidates": candidates, "diagnostics": diagnostics, "reason_code": reason}
    selection["selection_id"] = content_hash(value=selection)
    scope = {"entity_scope": "registrant"}
    _need(target["scope"] == scope and target["scope_key"] == scope_key(scope=scope),
          "C03_PROXY_SCT_TARGET_SCOPE_INVALID")
    observation = None
    if reason == "PASS":
        chosen = passing[0]
        observation = structured_observation(
            metric_id="C03", semantic_role="reported_total_compensation", company_id=company_id,
            period_start=target["period_start"], period_end=target["period_end"], scope=scope,
            value=chosen["value"], unit="USD", quality="EXACT",
            source_binding={"raw_asset_id": raw_blob["raw_asset_id"],
                            "source_reference_id": source_reference["source_reference_id"],
                            "accession": source_reference["accession"],
                            "document_name": source_reference["document_name"],
                            "source_role": source_reference["source_role"],
                            "selection_id": selection["selection_id"],
                            "derived_asset_id": asset["derived_asset_id"],
                            "amount_locator": chosen["amount"]["locator"]})
        result, trace = calculate_observation_metric(compiled_spec=compiled_spec, target=target,
                                                     company_traits=[], observation=observation)
    else:
        result, trace = withheld_metric_result(compiled_spec=compiled_spec, target=target, reason_code=reason)
    return {"record_type": RECORD_TYPE, "selection": selection, "observation": observation,
            "derived_assets": [asset], "result": result, "trace": trace,
            "business_calls": [0, 0, 0], "formal_publication_authorized": False}
