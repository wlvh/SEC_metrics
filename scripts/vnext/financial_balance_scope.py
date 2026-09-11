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
from .financial_relationships import _clean, _scale, _covering_headers, _proof
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
                    excluded.append({"label": _cell_proof(table=table, cell=label), "reason": "NO_REQUESTED_YEAR_BALANCE_IN_TABLE"})
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
                accepted.append({"value": _proof(table, entry, scale), "label": _cell_proof(table=table, cell=label),
                    "measurement_time": time, "scope": {"asset_scope": "total_assets_under_management"},
                    "currency_basis": "APPROVED_USD_REPORTING_UNIT_WITH_ORIGINAL_TABLE_SCALE"})
    values = {item["value"]["canonical_value"] for item in accepted}
    if len(values) > 1:
        unresolved.append({"reason": "CONFLICTING_SAME_SCOPE_AUM_BALANCES"})
    body = {"record_type": "AUM_BALANCE_SCOPE_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_entity_cik": str(int(expected_cik)),
        "target_filing_period": target_period, "task_contract_hash": content_hash(value=task),
        "status": "BALANCE_SCOPE_PROVEN" if accepted and not unresolved else "UNRESOLVED",
        "disclosures": accepted, "unresolved": unresolved, "excluded": excluded,
        "duplicate_rule": "SAME_SOURCE_ENTITY_EXACT_TOTAL_AUM_SCOPE_INSTANT_USD_SCALE_AND_VALUE",
        "value": next(iter(values)) if len(values) == 1 and not unresolved else None,
        "unit": "USD", "whole_issuer_scope_status": "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
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
    return {"named_measure": "Risk Management VaR", "holding_period_days": 1, "confidence_percent": "95",
            "section_heading": heading, "table_association": introductions[0], "selected_definition": target[0],
            "scope_span_census": census,
            "other_named_measure_definitions": [c for c in claims if c not in target],
            "holding_period_is_not_statistical_window": True}


def inspect_total_var(*, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
                      expected_cik: str, target_period: dict) -> dict:
    """Inspect an annual-average total VaR with explicit component/offset proof."""
    task, builders, structure = _prepare(repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256, expected_cik=expected_cik, target_period=target_period, metric_id="A12")
    if task["required_claims"] != {"confidence_level": "ninety_five_percent", "holding_period": "one_day"}:
        raise FinancialBalanceScopeError("VAR_SCOPE_CONTRACT_UNSUPPORTED")
    proven, unresolved = [], []
    for builder in builders:
        if not any(_clean(_semantic_text(raw_text="".join(c.raw_parts))) == "total var" for row in builder.rows for c in row):
            continue
        table = _grid(builder)
        labels = [(row["row_index"], c) for row in table["rows"] for c in row["cells"] if c["is_origin"] and c["column_index"] == 0 and c["text"]]
        targets = [(row, label, _numeric(table, row, target_period["fiscal_year"], average=True)) for row, label in labels if _clean(label["text"]) == "total var"]
        targets = [(row, label, entries[0]) for row, label, entries in targets if len(entries) == 1]
        if not targets:
            continue
        scope = _var_scope(structure, table)
        annual = [c for row in table["rows"][:4] for c in row["cells"] if c["is_origin"] and re.search(r"\bfor the year ended\b", c["text"], re.I)]
        for row_index, label, entry in targets:
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
                "offset_label": _cell_proof(table=table, cell=offset_label), "trading_components_excluded": trading,
                "reconciliation": "REPORTED_COMPONENTS_PLUS_REPORTED_DIVERSIFICATION_OFFSET"})
    body = {"record_type": "TOTAL_VAR_SCOPE_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_entity_cik": str(int(expected_cik)),
        "task_contract_hash": content_hash(value=task), "target_filing_period": target_period,
        "status": "TOTAL_VAR_SCOPE_PROVEN" if len(proven) == 1 and not unresolved else "UNRESOLVED",
        "totals": proven, "unresolved": unresolved, "whole_issuer_scope_status": "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}
