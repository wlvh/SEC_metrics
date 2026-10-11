"""C03 from an original no-inline proxy: existing table arithmetic and references.

Adapted from retained bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786 historical_proxy_compensation.
The measure, parser and named refusals are retained; company selection and
ordinary storage are owned by the existing consumers. No ledger or call path.
"""
from __future__ import annotations

import re
from datetime import date

from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash
from .deterministic_router import _numeric_xbrl_value
from .governance_compensation_table import (_CEO, _TableRanges, _cell_evidence,
                                            _origin_cells)
from .proxy_source_identity import (carries_inline_xbrl, cover_name_in_effect,
                                        governance_source_document, proxy_cover)
from .observations import scope_key, structured_observation
from .table_grid import build_table_grid
from .text_coverage import _byte_offsets

RESOLVER = "proxy_compensation_table_v1"
SPEC_PATH = "catalog/r6/C03_proxy_compensation_table_v1.md"
RECORD_TYPE = "C03_PROXY_TABLE_RESOLUTION"
PROCESSING_FILES=tuple('scripts/vnext/'+name+'.py' for name in (
    'proxy_compensation_source','proxy_source_identity','organization_name_core',
    'governance_compensation_table','table_grid','text_coverage','sources','records',
    'canonical','calculator','observations','resource_limits',
))+(SPEC_PATH,)
_TITLE = re.compile(r"^(?:(?:[IVX]+|\d+)\.\s*)?(?:(?P<before>\d{4})\s+)?summary compensation table"
                    r"(?:\s+for(?:\s+fiscal)?(?:\s+year)?\s+(?P<after>\d{4}))?(?:\s*\(SCT\))?$", re.I)
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
# A business unit's initials right after the title: "CEO CIB", "CEO AWM".
_UNIT_INITIALS = re.compile(r"\s+(?!(?:AND|OR)\b)[A-Z]{2,5}\b")
_MARK_CELL = re.compile(r"\d{1,2}")
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
_CONTEXT_BLOCKS, _CONTEXT_CHARS = 12, 6000


class ProxyCompensationError(ValueError):
    """The proxy's table cannot be read as this route reads it."""


def _need(condition, reason):
    if not condition:
        raise ProxyCompensationError(reason)


def _clean(text):
    return " ".join(text.translate(_ZERO_WIDTH).split())


def names_the_chief_executive(text):
    """Whether an executive's name-and-title text names the registrant's chief executive."""
    for match in _CEO.finditer(text):
        if _NOT_THE_CHIEF.search(text[:match.start()]):
            continue
        if _ANOTHER_BODY.match(text[match.end():]) or _UNIT_INITIALS.match(text[match.end():]):
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


def _sums(amounts):
    return amounts is not None and len(amounts) >= 3 and sum(value for value, _ in amounts[:-1]) == amounts[-1][0]


def row_amounts_by_arithmetic(tokens):
    """The row's amounts, and the one- or two-digit cells read as footnote marks.

    A filer may print a footnote mark in a cell of its own, where it reads as
    an amount of a few dollars. The row is first read as printed; only when
    that reading fails Item 402(c)'s sum are those cells read as marks, and
    the reading is kept only if the sum then holds. A row that sums as
    printed keeps every amount it prints.
    """
    amounts = row_amounts(tokens)
    if amounts is None or len(amounts) < 3 or _sums(amounts):
        return amounts, []
    marks = [token for token in tokens if _MARK_CELL.fullmatch(token)]
    alternative = row_amounts([token for token in tokens if not _MARK_CELL.fullmatch(token)])
    if marks and _sums(alternative):
        return alternative, marks
    return amounts, []


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
    _need(target['company_id']==company_id and type(fiscal_year) is int
          and 1900<=fiscal_year<=9998 and date.fromisoformat(target['period_start'])
          <date.fromisoformat(target['period_end']), 'C03_PROXY_SCT_TARGET_IDENTITY_INVALID')
    _need(str(int(inventory['cik']))==str(int(cik)), 'C03_PROXY_SCT_INVENTORY_CIK_CHANGED')
    _need(not carries_inline_xbrl(raw_bytes), "C03_PROXY_SCT_ONLY_FOR_A_PROXY_WITHOUT_INLINE_XBRL")
    document = governance_source_document(raw_bytes=raw_bytes, raw_blob=raw_blob,
                                          source_reference=source_reference, company_id=company_id,
                                          cik=cik, filing=filing)
    _need(document['source_state']=='COMPLETE_LOCAL_DOCUMENT',
          'C03_PROXY_SCT_SOURCE_DOCUMENT_INCOMPLETE')
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
            amounts, marks = row_amounts_by_arithmetic([text for _, text in person["amount_cells"]])
            candidate = {"table_id": table["table_id"], "table_grid_sha256": table["grid_sha256"],
                         "person_and_position": person["text"], "fiscal_year": fiscal_year,
                         "person": [_cell_evidence(asset, table, cell) for cell, _ in person["name_cells"]],
                         "year": _cell_evidence(asset, table, person["year_cell"][0])}
            if marks:
                candidate["cells_read_as_footnote_marks"] = marks
            if amounts is None or len(amounts) < 3:
                candidate["reason"] = "C03_PROXY_SCT_ROW_UNREADABLE"
            elif sum(value for value, _ in amounts[:-1]) != amounts[-1][0]:
                candidate["reason"] = "C03_PROXY_SCT_TOTAL_IS_NOT_THE_SUM_OF_ITS_COMPONENTS"
            elif "$" not in header + " ".join(text for _, text in person["amount_cells"]):
                candidate["reason"] = "C03_PROXY_SCT_DOLLAR_NOT_ESTABLISHED"
            else:
                # Arithmetic may exclude a separate footnote cell, including
                # one after Total. The quoted cell must be the last retained
                # amount, not the final physical cell in that row.
                amount_cells=[cell for cell,text in person['amount_cells']
                              if not _FOOTNOTE_ONLY.fullmatch(text)
                              and (not marks or not _MARK_CELL.fullmatch(text))]
                _need(len(amount_cells)==len(amounts), 'C03_PROXY_SCT_AMOUNT_LOCATORS_CONFLICT')
                total_cell = amount_cells[-1]
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
                            "amount_locator": chosen["amount"]["locator"],
                            "table_locator":chosen['amount']['locator'],
                            "reported_raw_text":chosen['amount']['raw_text'],
                            "source_witnesses":[*chosen['person'],chosen['year'],chosen['amount']]})
        result, trace = calculate_observation_metric(compiled_spec=compiled_spec, target=target,
                                                     company_traits=[], observation=observation)
    else:
        result, trace = withheld_metric_result(compiled_spec=compiled_spec, target=target, reason_code=reason)
    return {"record_type": RECORD_TYPE, "selection": selection, "observation": observation,
            "derived_assets": [asset], "result": result, "trace": trace,
            "business_calls": [0, 0, 0], "formal_publication_authorized": False}
