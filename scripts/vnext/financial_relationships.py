"""Reconstruct the named economic relationship behind a disclosed NIM.

Two source structures are supported: a single table with managed net interest
income, its reported/FTE bridge, average earning assets and net yield; and an
explicit NIM definition corroborated by an average-balance/interest/rate total.
The values are always read from the source. Equal arithmetic alone does not
establish a metric name, tax basis, period, unit, or business scope.

This produces offline relationship evidence, not a replacement calculated NIM
or a native Evidence/Run/publication acceptance. Existing snapshots are not read
as answer files and are not rewritten.
"""

from decimal import Decimal
from pathlib import Path
import re

from .canonical import arithmetic_context, content_hash, decimal_text, sha256_bytes
from .composite_scope import index_source_structure
from .constraints import ConstraintError, parse_numeric_claim
from .financial_duration import (
    _cell_proof, _column_period, _linked_notes, inspect_financial_duration,
)
from .normal_annual_input import annual_period
from .r4_task_contracts import inspect_r4_task_catalog
from .resource_limits import RESOURCE_LIMITS
from .specs import compile_spec_file
from .table_grid import _AllTablesParser, _expanded_table, _semantic_text


class FinancialRelationshipError(ValueError):
    """Reject source/identity drift without manufacturing a financial result."""


def _clean(text):
    text = " ".join(text.split()).replace("–", "-").replace("—", "-")
    return re.sub(r"(?:\((?:[a-z]|[0-9]{1,2})\))+$", "", text, flags=re.I).strip().casefold()


_ROLES = {
    "managed_numerator": re.compile(r"net interest income(?:\s*-\s*|,\s*)(?:managed basis|taxable equivalent basis)$"),
    "reported_numerator": re.compile(r"net interest income\s*-\s*reported$"),
    "fte_adjustment": re.compile(r"fully taxable-equivalent adjustments$"),
    "denominator": re.compile(r"average interest-earning assets$"),
    "total_earning_assets": re.compile(r"total interest-earning assets$"),
    "net_yield": re.compile(r"net yield on average interest-earning assets\s*-\s*managed basis$"),
    "nim": re.compile(r"net interest margin$"),
    "ratio_group": re.compile(r"net interest income as a percentage of average interest-earning assets$"),
}


def _role(text):
    clean = _clean(text)
    return next((name for name, pattern in _ROLES.items() if pattern.fullmatch(clean)), None)


def _scale(table, header_rows=3):
    evidence = []
    for row in table["rows"][:header_rows]:
        for cell in row["cells"]:
            if not cell["is_origin"]:
                continue
            match = re.search(
                r"\bin (thousands|millions|billions)(?: of dollars)?(?=\s*(?:,|\)|$))",
                cell["text"], re.I)
            if re.search(r"\bin (?:thousands|millions|billions)\b", cell["text"], re.I) and match is None:
                return None
            if match:
                evidence.append(({"thousands": 1000, "millions": 1000000,
                                  "billions": 1000000000}[match[1].casefold()], cell))
    if len({value for value, _ in evidence}) != 1:
        return None
    return {"unit": "USD", "factor": str(evidence[0][0]),
            "source_cells": [_cell_proof(table=table, cell=cell) for _, cell in evidence]}


def _cells(table, row_index, period):
    selected = []
    for cell in table["rows"][row_index]["cells"]:
        if not cell["is_origin"] or not cell["text"]:
            continue
        try:
            value = parse_numeric_claim(raw_value=cell["text"], reported_unit="ratio")
        except ConstraintError:
            continue
        column, headers, reason = _column_period(table=table, selected=cell)
        if reason or column["year"] != period["fiscal_year"]:
            continue
        if column["date"] is not None and column["date"].isoformat() != period["period_end"]:
            continue
        selected.append({"cell": cell, "value": value,
                         "header_evidence": [_cell_proof(table=table, cell=header) for header, _, _ in headers]})
    return selected


def _covering_headers(table, selected, text):
    return [cell for row in table["rows"][:selected["row_index"]]
            for cell in row["cells"] if cell["is_origin"] and _clean(cell["text"]) == text
            and cell["column_index"] <= selected["column_index"] < cell["column_index"] + cell["colspan"]]


def _row(table, row_index):
    return [cell for cell in table["rows"][row_index]["cells"] if cell["is_origin"] and cell["text"]]


def _currency(table, cell):
    prior = [item for item in _row(table, cell["row_index"]) if item["column_index"] < cell["column_index"]]
    return bool(prior and prior[-1]["text"] == "$")


def _percent(table, cell):
    after = [item for item in _row(table, cell["row_index"])
             if item["column_index"] >= cell["column_index"] + cell["colspan"]]
    return cell["text"].endswith("%") or bool(after and after[0]["text"] == "%")


def _proof(table, entry, scale=None):
    value = entry["value"] if scale is not None else parse_numeric_claim(
        raw_value=entry["cell"]["text"], reported_unit="percent")
    if scale is not None:
        with arithmetic_context():
            value *= Decimal(scale["factor"])
    return {"locator": _cell_proof(table=table, cell=entry["cell"]),
            "header_evidence": entry["header_evidence"],
            "canonical_value": decimal_text(value=value),
            "canonical_unit": "USD" if scale is not None else "ratio",
            "amount_scale": scale}


def _check_rate(numerator, denominator, rate_cell):
    denominator = Decimal(denominator["canonical_value"])
    if denominator <= 0:
        return None
    raw = rate_cell["text"].strip()
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]+))?(?:\s*%)?", raw)
    if match is None:
        return None
    digits = len(match[2] or "")
    disclosed = parse_numeric_claim(raw_value=raw, reported_unit="percent")
    with arithmetic_context():
        computed = Decimal(numerator["canonical_value"]) / denominator
        quantum = Decimal(10) ** (-digits - 2)
        rounded = computed.quantize(quantum)
    return {"disclosed_ratio": decimal_text(value=disclosed),
            "computed_ratio_for_validation_only": decimal_text(value=computed),
            "source_display_decimal_places": digits,
            "canonical_rounding_quantum": decimal_text(value=quantum),
            "rounding": "ROUND_HALF_EVEN", "consistent": rounded == disclosed,
            "result_value_remains_source_disclosed": True}


def _same_table(*, table, roles, period, source_bytes, source_sha256):
    required = {"managed_numerator", "reported_numerator", "fte_adjustment", "denominator", "net_yield"}
    if not required <= set(roles):
        return None, "NAMED_SAME_TABLE_ROLES_INCOMPLETE"
    selected = {role: [entry for row, _ in roles[role] for entry in _cells(table, row, period)]
                for role in required}
    if any(len(entries) != 1 for entries in selected.values()):
        return None, "NAMED_ROLE_PERIOD_MISSING_OR_AMBIGUOUS"
    selected = {role: entries[0] for role, entries in selected.items()}
    scale = _scale(table)
    if (scale is None or any(not _currency(table, selected[role]["cell"])
                             for role in ("managed_numerator", "reported_numerator", "denominator"))
            or not _percent(table, selected["net_yield"]["cell"])):
        return None, "NAMED_ROLE_UNIT_NOT_PROVEN"
    proofs = {role: _proof(table, entry, scale if role != "net_yield" else None)
              for role, entry in selected.items()}
    with arithmetic_context():
        expected = Decimal(proofs["reported_numerator"]["canonical_value"]) + Decimal(proofs["fte_adjustment"]["canonical_value"])
    if expected != Decimal(proofs["managed_numerator"]["canonical_value"]):
        return None, "REPORTED_TO_FTE_BRIDGE_CONFLICT"
    rate = selected["net_yield"]["cell"]
    label = roles["net_yield"][0][1]
    duration = inspect_financial_duration(
        source_bytes=source_bytes, expected_source_sha256=source_sha256,
        table_id=table["table_id"], row_index=rate["row_index"], column_index=rate["column_index"],
        measurement_aliases=[label["text"]], required_row_terms=["managed basis"],
        reported_unit="percent", claimed_period_start=period["period_start"], claimed_period_end=period["period_end"],
    )
    if duration["status"] != "PASSED":
        return None, "DISCLOSED_RATE_PERIOD_NOT_PROVEN"
    check = _check_rate(proofs["managed_numerator"], proofs["denominator"], rate)
    if check is None or not check["consistent"]:
        return None, "DISCLOSED_RATE_RELATIONSHIP_CONFLICT"
    return {"mechanism": "SAME_TABLE_NAMED_ROLES_WITH_REPORTED_FTE_BRIDGE",
            "rate_locator": _cell_proof(table=table, cell=rate),
            "role_labels": {role: _cell_proof(table=table, cell=roles[role][0][1]) for role in required},
            "source_roles": proofs, "rate_check": check,
            "duration_evidence": duration, "basis": "managed_basis",
            "subject_binding": {"kind": "SAME_UNQUALIFIED_ORIGINAL_TABLE_ROWS", "table_id": table["table_id"]}}, None


def _formula_notes(*, structure, table, rate_label):
    markers = set(re.findall(r"\(([a-z0-9]+)\)", rate_label["text"], re.I))
    notes, missing = _linked_notes(structure=structure, table_order=table["order"], markers=markers)
    if missing:
        return None
    if any(re.search(r"\b(?:quarter|months?|weeks?)\b", note["visible_text"], re.I)
           for note in notes):
        # A coincidentally equal annual narrative cannot erase a quarterly
        # qualifier attached to this particular reported-rate row.
        return None
    pattern = re.compile(
        r"^\([0-9]+\)\s*(.+?)\s+NIM is calculated by dividing net interest income "
        r"\(including TEGU\) by average interest-earning assets\.$", re.I,
    )
    formulas = [(note, pattern.fullmatch(" ".join(note["visible_text"].split()))) for note in notes]
    formulas = [(note, match) for note, match in formulas if match]
    tegu = [note for note in notes if re.search(r"\bNIM reflects TEGU\b", note["visible_text"], re.I)]
    if len(formulas) != 1 or not tegu:
        return None
    return {"subject": formulas[0][1][1], "definition": formulas[0][0], "tax_basis_notes": tegu}


def _annual_narrative(*, structure, formula, period, rate):
    year = period["fiscal_year"]
    # This form says 'In YYYY'; do not synthesize noncalendar fiscal dates.
    if period["period_start"] != f"{year}-01-01" or period["period_end"] != f"{year}-12-31":
        return None
    pattern = re.compile(r"^In " + str(year) + r", " + re.escape(formula["subject"])
                         + r" net interest margin\b[^.]*?\bto ([0-9]+\.[0-9]+)% on a taxable equivalent basis\b", re.I)
    found = []
    for block in structure["blocks"]:
        if block["inside_table"]:
            continue
        text = " ".join(block["visible_text"].split())
        match = pattern.search(text)
        if match and not re.search(r"\bquarter\b|\bmonth\b", text[:match.end()], re.I):
            if parse_numeric_claim(raw_value=match[1], reported_unit="percent") == parse_numeric_claim(raw_value=rate["text"], reported_unit="percent"):
                found.append(block)
    return found[0] if len(found) == 1 else None


def _ratio_totals(*, table, roles, period, structure):
    if "ratio_group" not in roles:
        return []
    table_span = structure["tables"][table["order"]]
    prior_tables = [span["end_byte"] for span in structure["tables"] if span["end_byte"] <= table_span["start_byte"]]
    left = max(prior_tables, default=0)
    basis = [block for block in structure["blocks"] if not block["inside_table"]
             and left <= block["start_byte"] < block["end_byte"] <= table_span["start_byte"]
             and _clean(block["visible_text"]) == "taxable equivalent basis"]
    if len(basis) != 1 or _scale(table) is None:
        return []
    result = []
    for row_index, group_label in roles["ratio_group"]:
        for row in table["rows"][row_index + 1:]:
            nonempty = _row(table, row["row_index"])
            if not nonempty:
                continue
            label = nonempty[0]
            entries = _cells(table, row["row_index"], period)
            if not entries:
                break
            if _clean(label["text"]) != "total":
                continue
            selected = {}
            for role, header in ("denominator", "average balance"), ("numerator", "interest expense"), ("rate", "% average rate"):
                hits = [entry for entry in entries if _covering_headers(table, entry["cell"], header)]
                if len(hits) == 1:
                    selected[role] = hits[0]
            if len(selected) != 3 or not _percent(table, selected["rate"]["cell"]):
                continue
            result.append({"table": table, "selected": selected, "basis_evidence": basis[0],
                           "group_label": _cell_proof(table=table, cell=group_label),
                           "total_label": _cell_proof(table=table, cell=label)})
    return result


def _explicit_formula(*, tables, structure, period):
    totals = [total for table, roles in tables for total in _ratio_totals(
        table=table, roles=roles, period=period, structure=structure)]
    denominators = []
    for table, roles in tables:
        scale = _scale(table)
        for row, label in roles.get("total_earning_assets", []):
            for entry in _cells(table, row, period):
                headers = _covering_headers(table, entry["cell"], "average balance")
                if scale and headers and _currency(table, entry["cell"]):
                    denominators.append((table, label, entry, scale, headers))
    results, failures = [], []
    for table, roles in tables:
        if "nim" not in roles:
            continue
        scale = _scale(table)
        for row, label in roles["nim"]:
            rates = _cells(table, row, period)
            numerators = [entry for num_row, _ in roles.get("managed_numerator", []) for entry in _cells(table, num_row, period)]
            formula = _formula_notes(structure=structure, table=table, rate_label=label)
            if len(rates) != 1 or len(numerators) != 1 or formula is None or scale is None:
                failures.append("EXPLICIT_NIM_DEFINITION_OR_NAMED_NUMERATOR_UNPROVEN")
                continue
            rate, numerator = rates[0], numerators[0]
            narrative = _annual_narrative(structure=structure, formula=formula, period=period, rate=rate["cell"])
            if narrative is None or not _currency(table, numerator["cell"]):
                failures.append("NIM_SOURCE_ANNUAL_PERIOD_OR_UNIT_UNPROVEN")
                continue
            np = _proof(table, numerator, scale)
            compatible = []
            for total in totals:
                peer_scale = _scale(total["table"])
                peer_num = _proof(total["table"], total["selected"]["numerator"], peer_scale)
                peer_den = _proof(total["table"], total["selected"]["denominator"], peer_scale)
                peer_rate = total["selected"]["rate"]["cell"]
                if (peer_num["canonical_value"] != np["canonical_value"]
                        or parse_numeric_claim(raw_value=peer_rate["text"], reported_unit="percent")
                        != parse_numeric_claim(raw_value=rate["cell"]["text"], reported_unit="percent")):
                    continue
                for dt, dl, de, ds, dh in denominators:
                    dp = _proof(dt, de, ds)
                    if dp["canonical_value"] == peer_den["canonical_value"] and ds["factor"] == scale["factor"] == peer_scale["factor"]:
                        compatible.append((total, dt, dl, dp, dh))
            if len(compatible) != 1:
                failures.append("NAMED_AVERAGE_BALANCE_RELATION_MISSING_OR_AMBIGUOUS")
                continue
            total, dt, dl, dp, dh = compatible[0]
            check = _check_rate(np, dp, rate["cell"])
            if check is None or not check["consistent"]:
                failures.append("DISCLOSED_RATE_RELATIONSHIP_CONFLICT")
                continue
            results.append({"mechanism": "SOURCE_EXPLICIT_NIM_FORMULA_WITH_NAMED_TOTAL_CORROBORATION",
                "rate_locator": _cell_proof(table=table, cell=rate["cell"]),
                "rate_label": _cell_proof(table=table, cell=label),
                "source_roles": {"managed_numerator": np, "denominator": dp},
                "denominator_label": _cell_proof(table=dt, cell=dl),
                "denominator_average_headers": [_cell_proof(table=dt, cell=header) for header in dh],
                "formula_evidence": formula, "source_annual_narrative": narrative,
                "corroborating_total": {"group_label": total["group_label"], "total_label": total["total_label"],
                    "basis_evidence": total["basis_evidence"],
                    "cells": {role: _proof(total["table"], entry, _scale(total["table"]) if role != "rate" else None)
                              for role, entry in total["selected"].items()}},
                "rate_check": check, "measurement_period": dict(period), "basis": "managed_basis",
                "subject_binding": {"kind": "SAME_SOURCE_NAMED_NIM_SUBJECT_AND_TOTAL", "source_subject_text": formula["subject"]}})
    return results, failures


def inspect_nim_relationships(
    *, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
    expected_cik: str, target_period: dict,
) -> dict:
    """Discover and verify source-named NIM relations for one ordinary filing."""
    if (type(source_bytes) is not bytes or not source_bytes
            or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or sha256_bytes(content=source_bytes) != expected_source_sha256):
        raise FinancialRelationshipError("SOURCE_BYTES_DIFFER")
    if type(target_period) is not dict or set(target_period) != {"fiscal_year", "period_start", "period_end"}:
        raise FinancialRelationshipError("TARGET_PERIOD_INVALID")
    source_period = annual_period(raw=source_bytes, cik=expected_cik,
                                  filing={"form": "10-K", "reportDate": target_period["period_end"]})
    if source_period != target_period:
        raise FinancialRelationshipError("SOURCE_FISCAL_PERIOD_DIFFERS")
    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"] if task["metric_ids"] == ["A04"]]
    if len(tasks) != 1:
        raise FinancialRelationshipError("NIM_TASK_NOT_UNIQUE")
    task = tasks[0]
    spec = compile_spec_file(path=repo_root / task["metric_spec_paths"][0], dependency_specs={})["compiled"]
    if (spec["name"] != "Net interest margin" or spec["kind"] != "direct_numeric"
            or spec["canonical_unit"] != "ratio" or spec["reported_unit"] != "percent"
            or task["required_claims"] != {"basis": "managed_basis"}
            or set(task["scope_contract"]["exact_enum_aliases"]["basis"]["managed_basis"])
            != {"managed basis", "taxable equivalent basis"}):
        raise FinancialRelationshipError("APPROVED_NIM_BASIS_CONTRACT_DIFFERS")
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    structure = index_source_structure(source_bytes=source_bytes)
    tables, census = [], []
    for builder in parser.tables:
        if not any(_role(_semantic_text(raw_text="".join(cell.raw_parts))) for row in builder.rows for cell in row):
            continue
        table, _ = _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                                   remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
        roles = {}
        for row in table["rows"]:
            for cell in row["cells"]:
                if not cell["is_origin"]:
                    continue
                role = _role(cell["text"])
                if role:
                    roles.setdefault(role, []).append((row["row_index"], cell))
                    census.append({"role": role, "label": _cell_proof(table=table, cell=cell)})
        tables.append((table, roles))
    relations, rejected = [], []
    for table, roles in tables:
        if "net_yield" not in roles:
            continue
        relation, reason = _same_table(table=table, roles=roles, period=source_period,
                                      source_bytes=source_bytes, source_sha256=expected_source_sha256)
        if relation:
            relations.append(relation)
        else:
            rejected.append({"table_id": table["table_id"], "reason": reason})
    explicit, failures = _explicit_formula(tables=tables, structure=structure, period=source_period)
    relations.extend(explicit)
    rejected.extend({"reason": reason} for reason in failures)
    body = {"record_type": "NIM_SOURCE_RELATIONSHIP_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_size": len(source_bytes),
        "source_entity_cik": str(int(expected_cik)), "source_fiscal_period": source_period,
        "task_contract_hash": content_hash(value=task), "metric_id": "A04",
        "status": "RELATIONSHIP_PROVEN" if len(relations) == 1 and not rejected else "UNRESOLVED",
        "relations": relations, "rejected_candidates": rejected, "named_role_census": census,
        "whole_issuer_scope_status": "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "result_value_policy": "RETAIN_DISCLOSED_RATE_NOT_COMPUTED_PROXY",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "relationship_id": content_hash(value=body)}
