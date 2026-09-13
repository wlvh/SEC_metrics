"""Source-bound AUM balances and annual-average total VaR components.

These inspections do not produce native Results or grant execution. AUM is
an end-date stock, while VaR has both a statistical measurement window and a
separate loss holding period. Equal values alone never close scope or time.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from .canonical import arithmetic_context, content_hash, decimal_text, sha256_bytes
from .composite_scope import index_source_structure
from .constraints import ConstraintError, parse_numeric_claim
from .financial_duration import _MONTH, _date, _cell_proof, _column_period, _linked_notes
from .financial_relationships import (
    _clean, _scale, _covering_headers, _proof, _issuer_identity, _entity_tokens,
    _reported_segment_sections, _segment_at,
    _table_reporting_declarations,
)
from .normal_annual_input import annual_period
from .r4_task_contracts import inspect_r4_task_catalog
from .resource_limits import RESOURCE_LIMITS
from .specs import compile_spec_file
from .table_grid import _AllTablesParser, _expanded_table, _semantic_text


class FinancialBalanceScopeError(ValueError):
    """Reject source or unsupported scope instead of inventing a total."""


def _prepare(*, repo_root, source_bytes, expected_source_sha256, expected_cik, target_period, metric_id):
    if (type(source_bytes) is not bytes or not source_bytes or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or sha256_bytes(content=source_bytes) != expected_source_sha256):
        raise FinancialBalanceScopeError("SOURCE_BYTES_DIFFER")
    period = annual_period(raw=source_bytes, cik=expected_cik,
                           filing={"form": "10-K", "reportDate": target_period["period_end"]})
    if period != target_period:
        raise FinancialBalanceScopeError("SOURCE_PERIOD_DIFFERS")
    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"] if task["metric_ids"] == [metric_id]]
    if len(tasks) != 1:
        raise FinancialBalanceScopeError("TASK_NOT_UNIQUE")
    spec = compile_spec_file(path=repo_root / tasks[0]["metric_spec_paths"][0], dependency_specs={})["compiled"]
    if spec["kind"] != "direct_numeric" or spec["reported_unit"] != "USD" or spec["canonical_unit"] != "USD":
        raise FinancialBalanceScopeError("BALANCE_METRIC_UNIT_OR_KIND_UNSUPPORTED")
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    return tasks[0], parser.tables, index_source_structure(source_bytes=source_bytes)


def _grid(builder):
    return _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                            remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)[0]


def _numeric(table, row_index, year, *, average=False):
    entries = []
    for cell in table["rows"][row_index]["cells"]:
        if not cell["is_origin"] or not cell["text"]:
            continue
        try:
            value = parse_numeric_claim(raw_value=cell["text"], reported_unit="ratio")
        except ConstraintError:
            continue
        column, headers, reason = _column_period(table=table, selected=cell)
        if reason or column["year"] != year:
            continue
        if average and not (_covering_headers(table, cell, "avg.") or _covering_headers(table, cell, "average")):
            continue
        entries.append({"cell": cell, "value": value, "column": column,
                        "header_evidence": [_cell_proof(table=table, cell=h) for h, _, _ in headers]})
    return entries


def _numeric_period_census(table, row_index):
    result = []
    for cell in table["rows"][row_index]["cells"]:
        if not cell["is_origin"] or not cell["text"]:
            continue
        try:
            parse_numeric_claim(raw_value=cell["text"], reported_unit="ratio")
        except ConstraintError:
            continue
        column, headers, reason = _column_period(table=table, selected=cell)
        result.append({"locator": _cell_proof(table=table, cell=cell), "column_year": column["year"] if column else None,
                       "column_reason": reason, "column_headers": [_cell_proof(table=table, cell=h) for h, _, _ in headers]})
    return result


def _balance_time(table, entry, label, target_period, structure):
    if re.search(r"\baverage\b|\bavg\b|\bbeginning\b", label["text"], re.I):
        return None
    markers = set(re.findall(r"\((?:[a-z]|[0-9]{1,2})\)", label["text"], re.I))
    notes, missing = _linked_notes(structure=structure, table_order=table["order"], markers={m[1:-1].casefold() for m in markers})
    if missing or any(re.search(r"\baverage\b|\bmonths?\b|\bquarter\b", note["visible_text"], re.I) for note in notes):
        return None
    header_cells = [c for row in table["rows"][:entry["column"]["row_index"] + 1] for c in row["cells"] if c["is_origin"]]
    if any(re.search(r"\baverage\b|\bavg\b|\bbeginning\b", c["text"], re.I) for c in header_cells):
        return None
    dates = []
    for cell in header_cells:
        match = re.match(r"^(?:Year ended |As of )?(" + _MONTH + r")\s+([0-9]{1,2}),?(?:\s+\(.*\))?$", " ".join(cell["text"].split()), re.I)
        if match:
            try:
                end = _date(year=entry["column"]["year"], month=match[1], day=int(match[2]))
            except ValueError:
                continue
            dates.append((end, cell))
    if len({end for end, _ in dates}) != 1:
        return None
    return {"kind": "INSTANT_BALANCE", "as_of_date": dates[0][0].isoformat(),
            "period_start": dates[0][0].isoformat(), "period_end": dates[0][0].isoformat(),
            "metric_basis": "TOTAL_ASSETS_UNDER_MANAGEMENT_BALANCE_NOT_AN_AVERAGE",
            "source_headers": [_cell_proof(table=table, cell=c) for _, c in dates], "row_notes": notes}


def _aum_definitions(structure):
    definitions = []
    for block in structure["blocks"]:
        if block["inside_table"]:
            continue
        match = re.fullmatch(r'AUM [“"]Assets under management[”"]: Represent assets managed by ([A-Za-z]+) '
                             r'on behalf of its (.+?) clients\. Includes [“"]Committed capital not Called\.[”"]',
                             " ".join(block["visible_text"].split()))
        if match:
            definitions.append((match[1], match[2], block))
    return definitions


def _client_population(expression):
    """Separate enumerated clients from exclusions and subset qualifiers."""
    boundary = re.search(r"\b(?:excluding|except(?: for)?|other than|but not|not including|without)\b", expression, re.I)
    included = expression[:boundary.start()] if boundary else expression
    excluded = expression[boundary.end():] if boundary else ""
    qualifiers = re.findall(r"\b(?:only|selected|certain|some|subset|limited to|solely|exclusively)\b", included, re.I)

    def members(text):
        text = re.sub(r"\bclients?\b", "", text, flags=re.I).strip(" ,")
        return [_clean(part.strip(" ,")) for part in re.split(r",\s*(?:and\s+)?|\s+and\s+", text) if part.strip(" ,")]

    positive, negative = members(included), members(excluded)
    plain = bool(positive) and all(re.fullmatch(r"[a-z][a-z &-]*", item) for item in positive)
    return {"source_expression": expression, "included_client_classes": positive,
            "excluded_client_classes": negative, "subset_qualifiers": qualifiers,
            "complete_unqualified_enumeration": plain and boundary is None and not qualifiers}


def _aum_reported_scope(*, builders, structure, disclosures, target_period, issuer):
    """Bind full AUM to its actual glossary, manager segment and table totals."""
    definitions = _aum_definitions(structure)
    if len({(manager, clients) for manager, clients, _ in definitions}) != 1:
        return None
    manager, clients, _ = definitions[0]
    population = _client_population(clients)
    if not population["complete_unqualified_enumeration"]:
        return None
    maps = []
    for block in structure["blocks"]:
        if not block["inside_table"]:
            match = re.fullmatch(re.escape(manager) + r": (.+)", " ".join(block["visible_text"].split()))
            if match:
                maps.append((match[1], block))
    if len({tuple(_entity_tokens(name)) for name, _ in maps}) != 1 or not issuer["source_consolidated_aliases"]:
        return None
    # The manager's own description independently names the investor classes
    # served by its investment-management business. This prevents a shortened
    # glossary list from granting full scope merely by omitting exclusion words.
    cohort_evidence, required_clients = [], set()
    for builder in builders:
        for raw_row in builder.rows:
            for raw_cell in raw_row:
                text = _semantic_text(raw_text="".join(raw_cell.raw_parts))
                if not re.match(re.escape(maps[0][0]) + r"\b", text, re.I):
                    continue
                for match in re.finditer(r"\bto ([a-z ,&-]{1,100}?) (?:investors|clients)\b", text, re.I):
                    clients_named = _client_population(match[1])
                    if clients_named["complete_unqualified_enumeration"] and len(clients_named["included_client_classes"]) > 1:
                        grid = _grid(builder)
                        witnesses = [c for row in grid["rows"] for c in row["cells"] if c["is_origin"] and c["text"] == text]
                        if len(witnesses) != 1:
                            return None
                        required_clients.update(clients_named["included_client_classes"])
                        cohort_evidence.append({"manager_description": _cell_proof(table=grid, cell=witnesses[0]),
                                                "named_investor_classes": clients_named["included_client_classes"]})
    if not required_clients or not required_clients <= set(population["included_client_classes"]):
        return None
    headings = _reported_segment_sections(builders, structure)
    bindings, reconciliations = [], []
    for disclosure in disclosures:
        locator = disclosure["value"]["locator"]
        table = _grid(builders[int(locator["table_id"].split("_")[1]) - 1])
        section = _segment_at(headings, table)
        if section is None or _entity_tokens(section["heading"]["text"]) != _entity_tokens(maps[0][0]):
            return None
        bindings.append({"locator": locator, "manager_section": section})
        group_headers = [c for row in table["rows"][:locator["row_index"]] for c in row["cells"]
                         if c["is_origin"] and c["column_index"] == 0 and _clean(c["text"]).startswith("assets by ")]
        if not group_headers:
            continue
        header = max(group_headers, key=lambda h: h["row_index"])
        if _clean(header["text"]) not in {"assets by asset class", "assets by client segment"}:
            return None
        components = []
        for row in table["rows"][header["row_index"] + 1:locator["row_index"]]:
            labels = [c for c in row["cells"] if c["is_origin"] and c["column_index"] == 0 and c["text"]]
            if not labels:
                continue
            entries = _numeric(table, row["row_index"], target_period["fiscal_year"])
            if len(labels) != 1 or len(entries) != 1 or _clean(labels[0]["text"]).startswith("total"):
                return None
            components.append({"label": _cell_proof(table=table, cell=labels[0]),
                               "value": _proof(table, entries[0], _scale(table))})
            if (_clean(header["text"]) == "assets by client segment"
                    and not _clean(labels[0]["text"]).startswith("global ")
                    and _clean(labels[0]["text"]) not in population["included_client_classes"]):
                return None
        with arithmetic_context():
            total = sum((Decimal(c["value"]["canonical_value"]) for c in components), Decimal(0))
        if not components or total != Decimal(disclosure["value"]["canonical_value"]):
            return None
        reconciliations.append({"group_header": _cell_proof(table=table, cell=header),
                                "components": components, "total_locator": locator})
    if not reconciliations:
        return None
    return {"basis": "ISSUER_DEFINED_AUM_ALL_CLIENTS_INCLUDES_COMMITTED_CAPITAL_NOT_CALLED",
            "aum_definitions": [block for _, _, block in definitions], "manager_definitions": [b for _, b in maps],
            "source_client_scope_text": clients, "manager_section_bindings": bindings,
            "client_population": population,
            "independently_named_manager_clients": sorted(required_clients), "manager_client_evidence": cohort_evidence,
            "complete_table_group_reconciliations": reconciliations,
            "equal_repeated_numbers_alone_are_not_scope_proof": True}


def inspect_aum_balance(*, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
                        expected_cik: str, target_period: dict) -> dict:
    """Inspect complete named AUM balances and consistent repeated disclosures."""
    task, builders, structure = _prepare(repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256, expected_cik=expected_cik, target_period=target_period, metric_id="A11")
    if task["required_claims"] != {"asset_scope": "total_assets_under_management"}:
        raise FinancialBalanceScopeError("AUM_SCOPE_CONTRACT_UNSUPPORTED")
    aliases = task["scope_contract"]["exact_enum_aliases"]["asset_scope"]["total_assets_under_management"]
    accepted, unresolved, excluded = [], [], []
    for builder in builders:
        if not any("assets under management" in _semantic_text(raw_text="".join(c.raw_parts)).casefold()
                   for row in builder.rows for c in row):
            continue
        table = _grid(builder)
        scale = _scale(table)
        for row in table["rows"]:
            labels = [c for c in row["cells"] if c["is_origin"] and "assets under management" in c["text"].casefold()]
            for label in labels:
                entries = _numeric(table, row["row_index"], target_period["fiscal_year"])
                if _clean(label["text"]) not in {_clean(alias) for alias in aliases}:
                    if entries:
                        excluded.append({"label": _cell_proof(table=table, cell=label), "reason": "NOT_COMPLETE_TOTAL_AUM_SCOPE"})
                    continue
                if not entries:
                    periods = _numeric_period_census(table, row["row_index"])
                    known_other = bool(periods) and all(p["column_year"] is not None and p["column_year"] != target_period["fiscal_year"] for p in periods)
                    (excluded if known_other else unresolved).append({"label": _cell_proof(table=table, cell=label),
                        "reason": "NO_REQUESTED_YEAR_BALANCE_IN_TABLE" if known_other else "SAME_NAMED_AUM_PERIOD_UNPROVEN",
                        "numeric_period_census": periods})
                    continue
                if len(entries) != 1 or scale is None:
                    unresolved.append({"label": _cell_proof(table=table, cell=label), "reason": "AUM_PERIOD_OR_SCALE_UNPROVEN"})
                    continue
                entry = entries[0]
                time = _balance_time(table, entry, label, target_period, structure)
                if time is None:
                    unresolved.append({"label": _cell_proof(table=table, cell=label), "reason": "AUM_INSTANT_NOT_PROVEN"})
                    continue
                if time["as_of_date"] != target_period["period_end"]:
                    excluded.append({"label": _cell_proof(table=table, cell=label),
                                     "measurement_time": time, "reason": "DIFFERENT_SOURCE_INSTANT"})
                    continue
                reporting = _table_reporting_declarations(structure=structure, table=table, label=label)
                if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
                    unresolved.append({"reason": "SOURCE_REPORTING_DECLARATION_CONFLICT", "reporting_declarations": reporting})
                    continue
                accepted.append({"value": _proof(table, entry, scale), "label": _cell_proof(table=table, cell=label),
                    "reporting_declarations": reporting,
                    "measurement_time": time, "scope": {"asset_scope": "total_assets_under_management"},
                    "currency_basis": "APPROVED_USD_REPORTING_UNIT_WITH_ORIGINAL_TABLE_SCALE"})
    values = {item["value"]["canonical_value"] for item in accepted}
    if len(values) > 1:
        unresolved.append({"reason": "CONFLICTING_SAME_SCOPE_AUM_BALANCES"})
    issuer = _issuer_identity(source_bytes=source_bytes, expected_cik=expected_cik,
                              target_period=target_period, structure=structure)
    whole = _aum_reported_scope(builders=builders, structure=structure, disclosures=accepted,
                               target_period=target_period, issuer=issuer) if accepted and not unresolved else None
    body = {"record_type": "AUM_BALANCE_SCOPE_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_entity_cik": str(int(expected_cik)),
        "target_filing_period": target_period, "task_contract_hash": content_hash(value=task),
        "status": "BALANCE_SCOPE_PROVEN" if accepted and not unresolved else "UNRESOLVED",
        "disclosures": accepted, "unresolved": unresolved, "excluded": excluded,
        "duplicate_rule": "SAME_SOURCE_ENTITY_EXACT_TOTAL_AUM_SCOPE_INSTANT_USD_SCALE_AND_VALUE",
        "value": next(iter(values)) if len(values) == 1 and not unresolved else None,
        "unit": "USD", "whole_issuer_scope_status": "SOURCE_WITNESSED_REPORTED_COMPLETE_AUM" if whole else "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
        "whole_issuer_scope_evidence": whole, "issuer_identity": issuer,
        "client_definition_analysis": [{"definition": b, **_client_population(clients)} for _, clients, b in _aum_definitions(structure)],
        "semantic_status": "SINGLE_SOURCE_SEMANTIC_FACT" if whole else "UNRESOLVED",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}


def _var_scope(structure, table):
    start = structure["tables"][table["order"]]["start_byte"]
    headings = [b for b in structure["blocks"] if not b["inside_table"] and b["end_byte"] < start
                and _clean(b["visible_text"]) in {"value-at-risk", "value at risk"}]
    if not headings:
        return None
    heading = headings[-1]
    blocks = [b for b in structure["blocks"] if not b["inside_table"] and heading["end_byte"] <= b["start_byte"] < start]
    introductions = [b for b in blocks if re.search(r"\btable below\b", b["visible_text"], re.I)
                     and "Risk Management VaR measure using a 95% confidence level" in b["visible_text"]]
    if len(introductions) != 1:
        return None
    pattern = re.compile(r"(?<![’'\w])((?:[A-Za-z]+\s+){1,4}VaR)(?: is calculated assuming a| model framework currently assumes a) "
                         r"(.+?) holding period[^.]*?(95|99)% confidence level", re.I)
    claims = []
    for block in blocks:
        for match in pattern.finditer(block["visible_text"]):
            measure = re.sub(r"^(?:This|The)\s+", "", match[1], flags=re.I)
            claims.append({"measure": measure, "holding_period_text": match[2], "confidence_percent": match[3], "source_block": block})
    census = []
    for block in blocks:
        if re.search(r"\bholding period\b|\bconfidence\b", block["visible_text"], re.I) is None:
            continue
        bound = [claim for claim in claims if claim["source_block"] == block]
        if (block == introductions[0]
                and len(re.findall(r"\bconfidence\b", block["visible_text"], re.I)) == 1
                and re.search(r"\bholding period\b", block["visible_text"], re.I) is None):
            disposition = "TARGET_TABLE_CONFIDENCE_ASSOCIATION"
        elif (len(bound) == 1 and bound[0]["measure"] in {"Risk Management VaR", "Regulatory VaR"}
              and len(re.findall(r"\bconfidence\b", block["visible_text"], re.I)) == 1
              and len(re.findall(r"[0-9]+(?:\.[0-9]+)?\s*(?:%|percent)\s+confidence level", block["visible_text"], re.I)) == 1
              and len(re.findall(r"\bholding period\b", block["visible_text"], re.I)) == 1):
            disposition = "TARGET_NAMED_DEFINITION" if bound[0]["measure"] == "Risk Management VaR" else "DIFFERENT_NAMED_REGULATORY_VAR"
        else:
            return None
        census.append({"source_block": block, "disposition": disposition})
    target = [c for c in claims if c["measure"] == "Risk Management VaR"]
    if len(target) != 1 or target[0]["holding_period_text"] not in {"one-day", "one day"} or target[0]["confidence_percent"] != "95":
        return None
    aggregation = [b for b in blocks if re.search(
        r"The VaR model results across all portfolios are aggregated at the Firm level\.", b["visible_text"])]
    complete = (len(aggregation) == 1 and "Firm’s Risk Management VaR" in introductions[0]["visible_text"]
                and "Firm’s Risk Management VaR" in target[0]["source_block"]["visible_text"])
    return {"named_measure": "Risk Management VaR", "holding_period_days": 1, "confidence_percent": "95",
            "section_heading": heading, "table_association": introductions[0], "selected_definition": target[0],
            "scope_span_census": census,
            "firmwide_aggregation_evidence": aggregation[0] if complete else None,
            "other_named_measure_definitions": [c for c in claims if c not in target],
            "holding_period_is_not_statistical_window": True}


def inspect_total_var(*, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
                      expected_cik: str, target_period: dict) -> dict:
    """Inspect an annual-average total VaR with explicit component/offset proof."""
    task, builders, structure = _prepare(repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256, expected_cik=expected_cik, target_period=target_period, metric_id="A12")
    if task["required_claims"] != {"confidence_level": "ninety_five_percent", "holding_period": "one_day"}:
        raise FinancialBalanceScopeError("VAR_SCOPE_CONTRACT_UNSUPPORTED")
    proven, unresolved, target_census = [], [], []
    for builder in builders:
        if not any(_clean(_semantic_text(raw_text="".join(c.raw_parts))) == "total var" for row in builder.rows for c in row):
            continue
        table = _grid(builder)
        labels = [(row["row_index"], c) for row in table["rows"] for c in row["cells"] if c["is_origin"] and c["column_index"] == 0 and c["text"]]
        targets = []
        for row, label in labels:
            if _clean(label["text"]) != "total var":
                continue
            entries = _numeric(table, row, target_period["fiscal_year"], average=True)
            periods = _numeric_period_census(table, row)
            item = {"label": _cell_proof(table=table, cell=label), "numeric_period_census": periods}
            title = (not periods and any(r > row and _clean(c["text"]) == "total var"
                                         and _numeric_period_census(table, r) for r, c in labels))
            counterfactual = [c for prior in table["rows"][:row] for c in prior["cells"] if c["is_origin"]
                and _clean(c["text"]) == "amounts by which reported average var would have been lower for the years ended:"
                and periods and all(c["column_index"] <= p["locator"]["column_index"] < c["column_index"] + c["colspan"] for p in periods)]
            if title:
                item["disposition"] = "TABLE_TITLE_WITH_LATER_NAMED_NUMERIC_TOTAL"
            elif counterfactual:
                item.update(disposition="COUNTERFACTUAL_REDUCTION_AMOUNT_NOT_REPORTED_TOTAL",
                            scope_headers=[_cell_proof(table=table, cell=c) for c in counterfactual])
            elif len(entries) == 1:
                item["disposition"] = "CURRENT_AVERAGE_REQUIRES_TOTAL_SCOPE_PROOF"
                targets.append((row, label, entries[0]))
            elif periods and all(p["column_year"] is not None and p["column_year"] != target_period["fiscal_year"] for p in periods):
                item["disposition"] = "DIFFERENT_SOURCE_YEAR"
            else:
                item["disposition"] = "SAME_NAMED_VAR_PERIOD_OR_AVERAGE_AMBIGUOUS"
                unresolved.append({"reason": item["disposition"], "candidate": item})
            target_census.append(item)
        if not targets:
            continue
        scope = _var_scope(structure, table)
        annual = [c for row in table["rows"][:4] for c in row["cells"] if c["is_origin"] and re.search(r"\bfor the year ended\b", c["text"], re.I)]
        for row_index, label, entry in targets:
            reporting = _table_reporting_declarations(structure=structure, table=table, label=label)
            if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
                unresolved.append({"reason": "SOURCE_REPORTING_DECLARATION_CONFLICT", "reporting_declarations": reporting})
                continue
            scale = _scale(table, header_rows=row_index)
            if scale is None or scope is None or len(annual) != 1:
                unresolved.append({"label": _cell_proof(table=table, cell=label), "reason": "TOTAL_VAR_SCOPE_SCALE_OR_STATISTICAL_WINDOW_UNPROVEN"})
                continue
            if any(re.search(r"\bquarter\b|\b(?:three|six|nine|3|6|9) months? ended\b", c["text"], re.I)
                   for header_row in table["rows"][:entry["column"]["row_index"] + 2]
                   for c in header_row["cells"] if c["is_origin"]):
                unresolved.append({"reason": "CONFLICTING_VAR_STATISTICAL_WINDOW"})
                continue
            end_match = re.search(r"year ended (" + _MONTH + r")\s+([0-9]{1,2})", annual[0]["text"], re.I)
            if end_match is None or _date(year=target_period["fiscal_year"], month=end_match[1], day=int(end_match[2])).isoformat() != target_period["period_end"]:
                unresolved.append({"reason": "VAR_STATISTICAL_WINDOW_DIFFERS"})
                continue
            offsets = [(r, c, re.fullmatch(r"diversification benefit to (.+) and (.+) var", _clean(c["text"]))) for r, c in labels if r < row_index]
            offsets = [(r, c, m) for r, c, m in offsets if m]
            if len(offsets) != 1:
                unresolved.append({"reason": "TOTAL_VAR_COMPOSITION_NOT_UNIQUE"})
                continue
            offset_row, offset_label, match = offsets[0]
            components = []
            for name in (match[1] + " var", match[2] + " var"):
                rows = [(r, c) for r, c in labels if r < offset_row and _clean(c["text"]) == name]
                if len(rows) == 1:
                    cells = _numeric(table, rows[0][0], target_period["fiscal_year"], average=True)
                    if len(cells) == 1:
                        components.append({"label": _cell_proof(table=table, cell=rows[0][1]), "value": _proof(table, cells[0], scale)})
            offsets_numeric = _numeric(table, offset_row, target_period["fiscal_year"], average=True)
            if len(components) != 2 or len(offsets_numeric) != 1:
                unresolved.append({"reason": "TOTAL_VAR_COMPONENT_PERIOD_OR_STATISTIC_UNPROVEN"})
                continue
            offset = _proof(table, offsets_numeric[0], scale)
            value = _proof(table, entry, scale)
            with arithmetic_context():
                computed = sum((Decimal(c["value"]["canonical_value"]) for c in components), Decimal(offset["canonical_value"]))
            if computed != Decimal(value["canonical_value"]):
                unresolved.append({"reason": "TOTAL_VAR_COMPONENT_RECONCILIATION_CONFLICT"})
                continue
            trading = [{"label": _cell_proof(table=table, cell=c), "reason": "NAMED_TRADING_COMPONENT_NOT_TOTAL_VAR"}
                       for r, c in labels if r < row_index and _clean(c["text"]).endswith("trading var")]
            proven.append({"value": value, "total_label": _cell_proof(table=table, cell=label),
                "statistical_window": {"period_start": target_period["period_start"], "period_end": target_period["period_end"],
                    "statistic": "AVERAGE", "source_header": _cell_proof(table=table, cell=annual[0])},
                "risk_horizon": scope, "components": components, "offset": offset,
                "reporting_declarations": reporting,
                "offset_label": _cell_proof(table=table, cell=offset_label), "trading_components_excluded": trading,
                "reconciliation": "REPORTED_COMPONENTS_PLUS_REPORTED_DIVERSIFICATION_OFFSET"})
    issuer = _issuer_identity(source_bytes=source_bytes, expected_cik=expected_cik,
                              target_period=target_period, structure=structure)
    definitions = [a for a in issuer["source_consolidated_aliases"] if a["alias"] == "Firm"]
    whole = (len(proven) == 1 and not unresolved and bool(definitions)
             and proven[0]["risk_horizon"]["firmwide_aggregation_evidence"] is not None)
    body = {"record_type": "TOTAL_VAR_SCOPE_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_entity_cik": str(int(expected_cik)),
        "task_contract_hash": content_hash(value=task), "target_filing_period": target_period,
        "status": "TOTAL_VAR_SCOPE_PROVEN" if len(proven) == 1 and not unresolved else "UNRESOLVED",
        "totals": proven, "unresolved": unresolved, "same_named_total_census": target_census,
        "whole_issuer_scope_status": "SOURCE_WITNESSED_FIRMWIDE_VAR" if whole else "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
        "issuer_identity": issuer, "consolidated_issuer_definitions": definitions,
        "semantic_status": "SINGLE_SOURCE_SEMANTIC_FACT" if whole else "UNRESOLVED",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}
