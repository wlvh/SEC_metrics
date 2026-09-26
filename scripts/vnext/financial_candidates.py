"""Discover financial candidates in ordinary source tables, without answers.

The catalog's metric name, role words/acronym, and required-scope vocabulary
are search leads. They are never sufficient to accept a financial result.
Every matching numeric origin remains visible, including prior periods, wrong
units, incomplete scope, duplicates, and disclosed-period contradictions.
Structured-first metrics retain their required upstream route.

This is additive offline discovery, not a Reader replacement, a qualification
certificate, or an automatic table-window completeness claim. It reads no
source-specific audit recipe, expected value, or supplied target table number.
"""

from datetime import date
from pathlib import Path
import re

from .canonical import content_hash, decimal_text, sha256_bytes
from .constraints import ConstraintError, parse_numeric_claim
from .financial_duration import (
    _cell_proof, _column_period, _contains, inspect_financial_duration,
)
from .r4_task_contracts import inspect_r4_task_catalog
from .resource_limits import RESOURCE_LIMITS
from .specs import compile_spec_file
from .table_grid import _AllTablesParser, _expanded_table, _semantic_text


class FinancialCandidateError(ValueError):
    """Reject invalid discovery inputs without creating a financial verdict."""


def _terms(*, task, spec):
    terms = [spec["name"]]
    for role in task["required_roles"]:
        words = role.split("_")
        terms.append(" ".join(words))
        if len(words) >= 3:
            terms.append("".join(word[0] for word in words))
    return list({term.casefold(): term for term in terms}.values())


def _scope_matches(*, text, task):
    result = {}
    aliases = task["scope_contract"]["exact_enum_aliases"]
    for dimension, required in task["required_claims"].items():
        result[dimension] = [term for term in aliases[dimension][required]
                             if _contains(text=text, term=term)]
    return result


def _row_match(*, text, task, terms):
    name_terms = [term for term in terms if _contains(text=text, term=term)]
    scopes = _scope_matches(text=text, task=task)
    scope_lead = bool(scopes) and all(scopes.values())
    return name_terms, scopes, bool(name_terms or scope_lead)


def _unit_lead(*, row, selected):
    prior = [cell for cell in row["cells"] if cell["is_origin"] and cell["text"]
             and cell["column_index"] < selected["column_index"]]
    later = [cell for cell in row["cells"] if cell["is_origin"] and cell["text"]
             and cell["column_index"] >= selected["column_index"] + selected["colspan"]]
    if selected["text"].endswith("%") or (later and later[0]["text"] == "%"):
        return "percent", [] if selected["text"].endswith("%") else [later[0]]
    if selected["text"].startswith("$") or (prior and prior[-1]["text"] == "$"):
        return "USD", [] if selected["text"].startswith("$") else [prior[-1]]
    return None, []


def inspect_financial_candidates(
    *, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
    task_contract_id: str, target_period: dict,
) -> dict:
    """Return source-derived candidates and unresolved obligations, with no AI.

    ``target_period`` is the ordinary input's native DEI filing interval. A
    source's shorter disclosed measurement is reported as a conflict with
    that request, not silently promoted to an annual value or authorized by
    another source's historical period exception.
    """
    if (type(source_bytes) is not bytes or not source_bytes
            or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or sha256_bytes(content=source_bytes) != expected_source_sha256):
        raise FinancialCandidateError("SOURCE_BYTES_DIFFER")
    if (type(target_period) is not dict or set(target_period) != {
            "fiscal_year", "period_start", "period_end"}
            or type(target_period["fiscal_year"]) is not int):
        raise FinancialCandidateError("TARGET_PERIOD_INVALID")
    try:
        start = date.fromisoformat(target_period["period_start"])
        end = date.fromisoformat(target_period["period_end"])
        if (start > end or start.isoformat() != target_period["period_start"]
                or end.isoformat() != target_period["period_end"]
                or not start.year <= target_period["fiscal_year"] <= end.year):
            raise ValueError("target period differs")
    except (ValueError, TypeError) as error:
        raise FinancialCandidateError("TARGET_PERIOD_INVALID") from error
    catalog = inspect_r4_task_catalog(repo_root=repo_root)
    tasks = [task for task in catalog["contracts"]
             if task["task_contract_id"] == task_contract_id]
    if len(tasks) != 1:
        raise FinancialCandidateError("TASK_NOT_IN_CATALOG")
    task = tasks[0]
    compiled = compile_spec_file(
        path=repo_root / task["metric_spec_paths"][0], dependency_specs={},
    )
    if (compiled["spec_semantic_hash"] != task["metric_spec_semantic_hashes"][0]
            or compiled["spec_closure_hash"] != task["metric_spec_closure_hashes"][0]):
        raise FinancialCandidateError("TASK_SPEC_BINDING_DIFFERS")
    spec = compiled["compiled"]
    terms = _terms(task=task, spec=spec)
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    candidates, row_census = [], []
    materialized = 0
    for builder in parser.tables:
        raw_matches = []
        for row_index, row in enumerate(builder.rows):
            if any(_row_match(text=_semantic_text(raw_text="".join(cell.raw_parts)),
                              task=task, terms=terms)[2] for cell in row):
                raw_matches.append(row_index)
        if not raw_matches:
            continue
        table, _ = _expanded_table(
            builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
            remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars,
        )
        materialized += 1
        for row_index in raw_matches:
            row = table["rows"][row_index]
            for label in row["cells"]:
                if not label["is_origin"] or not label["text"]:
                    continue
                names, scopes, matched = _row_match(text=label["text"], task=task, terms=terms)
                if not matched:
                    continue
                row_census.append({"label": _cell_proof(table=table, cell=label),
                                   "name_terms": names, "scope_terms": scopes})
                for selected in row["cells"]:
                    if (not selected["is_origin"] or not selected["text"]
                            or selected["column_index"] <= label["column_index"]):
                        continue
                    try:
                        parse_numeric_claim(raw_value=selected["text"], reported_unit="ratio")
                    except ConstraintError:
                        continue
                    reasons = []
                    if not names:
                        reasons.append("MEASUREMENT_SEMANTICS_UNPROVEN")
                    if not all(scopes.values()):
                        reasons.append("REQUIRED_SCOPE_NOT_PROVEN_IN_ROW")
                    if any(_contains(text=label["text"], term=term)
                           for term in task["forbidden_confusions"]):
                        reasons.append("FORBIDDEN_ROW_SCOPE")
                    column, headers, column_reason = _column_period(table=table, selected=selected)
                    if column_reason:
                        reasons.append(column_reason)
                    elif column["year"] not in {target_period["fiscal_year"], end.year}:
                        reasons.append("DIFFERENT_COLUMN_PERIOD")
                    actual_unit, unit_cells = _unit_lead(row=row, selected=selected)
                    if (actual_unit is not None and actual_unit != spec["reported_unit"]
                            and not (actual_unit == "percent" and spec["canonical_unit"] == "ratio")):
                        reasons.append("SOURCE_UNIT_CONFLICT")
                    if spec["source_mode"] == "structured_first_ai_fallback":
                        reasons.append("STRUCTURED_PRIMARY_NOT_EVALUATED")
                    duration = None
                    # Inspect one current, non-currency percent lead at a time;
                    # do not spend repeated source parsing on rejected periods
                    # or dollar amounts which only matched a broad scope word.
                    if (spec["reported_unit"] == "percent" and column is not None
                            and "DIFFERENT_COLUMN_PERIOD" not in reasons
                            and actual_unit != "USD"):
                        duration = inspect_financial_duration(
                            source_bytes=source_bytes,
                            expected_source_sha256=expected_source_sha256,
                            table_id=table["table_id"], row_index=row_index,
                            column_index=selected["column_index"],
                            measurement_aliases=[label["text"]],
                            required_row_terms=[matches[0] for matches in scopes.values() if matches],
                            reported_unit="percent",
                            claimed_period_start=target_period["period_start"],
                            claimed_period_end=target_period["period_end"],
                        )
                        if "CLAIMED_MEASUREMENT_PERIOD_DIFFERS" in duration["reasons"]:
                            reasons.append("DISCLOSED_PERIOD_DIFFERS_FROM_REQUEST")
                        elif duration["status"] != "PASSED":
                            reasons.append("MEASUREMENT_DURATION_UNPROVEN")
                        if duration["unit_evidence_cells"] or duration["unit_evidence_footnote_spans"]:
                            actual_unit = "percent"
                    if actual_unit is None:
                        reasons.append("SOURCE_UNIT_NOT_PROVEN")
                    if spec["reported_unit"] != "percent":
                        reasons.append("DURATION_COMPONENT_NOT_APPLIED")
                    body = {
                        "source_sha256": expected_source_sha256,
                        "metric_id": spec["metric_id"],
                        "spec_semantic_hash": compiled["spec_semantic_hash"],
                        "locator": _cell_proof(table=table, cell=selected),
                        "measurement_row": _cell_proof(table=table, cell=label),
                        "match_kind": "METRIC_NAME_OR_ROLE" if names else "SCOPE_VOCABULARY_ONLY",
                        "matched_name_terms": names, "matched_scope_terms": scopes,
                        "column_evidence": [_cell_proof(table=table, cell=cell) for cell, _, _ in headers],
                        "source_unit": actual_unit,
                        "unit_evidence": [_cell_proof(table=table, cell=cell) for cell in unit_cells],
                        "duration_component": duration,
                        "unresolved_obligations": reasons,
                        "native_evidence_status": "NOT_EVALUATED",
                        "auto_execution_eligible": False,
                    }
                    candidates.append({**body, "candidate_id": content_hash(value=body)})
    body = {
        "record_type": "FINANCIAL_SOURCE_CANDIDATE_DISCOVERY", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_size": len(source_bytes),
        "task_contract_id": task_contract_id, "task_catalog_id": catalog["catalog_id"],
        "task_contract_hash": content_hash(value=task),
        "spec_semantic_hash": compiled["spec_semantic_hash"],
        "spec_closure_hash": compiled["spec_closure_hash"],
        "target_period": dict(target_period), "search_terms": terms,
        "search_scope": "ALL_SOURCE_TABLE_ROWS_LITERAL_LEADS_ONLY",
        "source_table_count": len(parser.tables), "materialized_matching_tables": materialized,
        "matched_row_census": row_census, "candidates": candidates,
        "unresolved_candidate_set": [c["candidate_id"] for c in candidates
                                     if "DIFFERENT_COLUMN_PERIOD" not in c["unresolved_obligations"]],
        "semantic_completeness": "NOT_PROVEN_BY_LITERAL_SEARCH",
        "status": "CANDIDATES_DISCOVERED" if candidates else "NO_LITERAL_CANDIDATE_IMPLEMENTATION_LIMIT",
        "execution": "NOT_EXECUTED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0},
    }
    return {**body, "discovery_id": content_hash(value=body)}


def inspect_nim_candidate_evidence(
    *, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
    expected_cik: str, target_period: dict,
) -> dict:
    """Bind automatic discovery to a freshly reconstructed NIM relationship.

    Both components reread the same exact source bytes. The source-discovery
    record retains its original unresolved row-local checks; this additional
    evidence explains which candidate the named relationship supports without
    pretending that native Evidence/Run acceptance has already occurred.
    """
    from .financial_relationships import inspect_nim_relationships

    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"]
             if task["metric_ids"] == ["A04"]]
    if len(tasks) != 1:
        raise FinancialCandidateError("NIM_TASK_NOT_UNIQUE")
    task = tasks[0]
    discovery = inspect_financial_candidates(
        repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256,
        task_contract_id=task["task_contract_id"], target_period=target_period,
    )
    relationship = inspect_nim_relationships(
        repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256,
        expected_cik=expected_cik, target_period=target_period,
    )
    if discovery["task_contract_hash"] != relationship["task_contract_hash"]:
        raise FinancialCandidateError("DISCOVERY_RELATIONSHIP_TASK_DIFFERS")
    matched = []
    if relationship["status"] == "RELATIONSHIP_PROVEN":
        locator = relationship["relations"][0]["rate_locator"]
        matched = [candidate["candidate_id"] for candidate in discovery["candidates"]
                   if candidate["locator"] == locator]
    body = {
        "record_type": "NIM_DISCOVERY_RELATIONSHIP_COMPONENT_BINDING", "schema_version": 1,
        "source_sha256": expected_source_sha256, "target_period": dict(target_period),
        "discovery": discovery, "relationship": relationship,
        "matched_candidate_ids": matched,
        "status": "RELATIONSHIP_BOUND_TO_DISCOVERED_CANDIDATE" if len(matched) == 1 else "UNRESOLVED",
        "native_evidence_status": "NOT_EVALUATED", "auto_execution_eligible": False,
        "qualification_credit": "NONE_COMPONENT_ONLY", "publication_credit": "NONE",
        "calls": {"provider": 0, "paid": 0, "sec": 0},
    }
    return {**body, "binding_id": content_hash(value=body)}


def inspect_lcr_disclosed_fact(
    *, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
    expected_cik: str, target_period: dict,
) -> dict:
    """Resolve the issuer's actual disclosed average interval, without annualizing.

    This does not extend the historical Citi fixture exception. A new ordinary
    Result rule must explicitly preserve the returned measurement period and
    filing interval. Same-name candidates remain visible and unknowns block a
    single fact; repeated equal values only corroborate already-proven scope.
    """
    from .composite_scope import index_source_structure
    from .financial_relationships import _clean, _entity_tokens, _issuer_identity, _nearest_table_introduction, _table_reporting_declarations
    from .normal_annual_input import annual_period
    if (type(source_bytes) is not bytes or not source_bytes or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or sha256_bytes(content=source_bytes) != expected_source_sha256):
        raise FinancialCandidateError("SOURCE_BYTES_DIFFER")
    if annual_period(raw=source_bytes, cik=expected_cik,
                     filing={"form": "10-K", "reportDate": target_period["period_end"]}) != target_period:
        raise FinancialCandidateError("SOURCE_FILING_PERIOD_DIFFERS")
    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"] if task["metric_ids"] == ["A03"]]
    if len(tasks) != 1 or tasks[0]["required_claims"] != {"entity_scope": "firm", "aggregation": "average"}:
        raise FinancialCandidateError("LCR_SCOPE_CONTRACT_UNSUPPORTED")
    discovery = inspect_financial_candidates(repo_root=repo_root, source_bytes=source_bytes,
        expected_source_sha256=expected_source_sha256, task_contract_id=tasks[0]["task_contract_id"], target_period=target_period)
    structure = index_source_structure(source_bytes=source_bytes)
    issuer = _issuer_identity(source_bytes=source_bytes, expected_cik=expected_cik,
                              target_period=target_period, structure=structure)
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    tables, group_names = {}, []
    for table_id in sorted({c["locator"]["table_id"] for c in discovery["candidates"]}):
        builder = parser.tables[int(table_id.split("_")[1]) - 1]
        table, _ = _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                                  remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
        tables[table_id] = table
        for row in table["rows"]:
            nonempty = [c for c in row["cells"] if c["is_origin"] and c["text"]]
            if (len(nonempty) == 1 and nonempty[0]["text"].endswith(":")
                    and len(_entity_tokens(nonempty[0]["text"])) >= 2):
                group_names.append(_cell_proof(table=table, cell=nonempty[0]))
    census, selected, unresolved = [], [], []
    issuer_tokens = _entity_tokens(issuer["registrant_name"])
    for candidate in discovery["candidates"]:
        table = tables[candidate["locator"]["table_id"]]
        label = candidate["measurement_row"]
        cell = table["rows"][candidate["locator"]["row_index"]]["cells"][candidate["locator"]["column_index"]]
        item = {"candidate_id": candidate["candidate_id"], "locator": candidate["locator"], "label": label}
        column, _, column_reason = _column_period(table=table, selected=cell)
        if (column and (column["year"] != target_period["fiscal_year"]
                       or column["date"] and column["date"].isoformat() != target_period["period_end"])):
            item["disposition"] = "DIFFERENT_SOURCE_MEASUREMENT_END"
            census.append(item)
            continue
        match = re.fullmatch(r"(.*?)\s*(?:liquidity coverage ratio|lcr)(?:\s*\([“\"]?lcr[”\"]?\))?(?:\s*\(average\))?",
                             _clean(label["text"]), re.I)
        prefix = match[1].strip() if match else None
        group = None
        if prefix == "":
            groups = [g for g in group_names if g["table_id"] == table["table_id"] and g["row_index"] < label["row_index"]]
            group = max(groups, key=lambda g: g["row_index"]) if groups else None
            prefix = group["text"].rstrip(":") if group else None
        tokens = _entity_tokens(prefix or "")
        scope = None
        if tokens == issuer_tokens:
            scope = {"basis": "EXACT_NATIVE_REGISTRANT_NAME", "group_heading": group}
        elif tokens == ["firm"] and issuer["source_defined_aliases"]:
            scope = {"basis": "SOURCE_DEFINED_REGISTRANT_ALIAS", "alias_definitions": issuer["source_defined_aliases"]}
        elif tokens and any(tokens in (_entity_tokens(entity["legal_name"]), _entity_tokens(entity["alias"]))
                            for entity in issuer["source_defined_other_entities"]):
            entity = next(entity for entity in issuer["source_defined_other_entities"]
                          if tokens in (_entity_tokens(entity["legal_name"]), _entity_tokens(entity["alias"])))
            item.update(disposition="OTHER_EXPLICIT_NAMED_ENTITY", entity_heading=group,
                        distinct_entity_definition=entity)
            census.append(item)
            continue
        duration = candidate["duration_component"]
        introduction = _nearest_table_introduction(structure, table)
        average = (re.search(r"\(average\)", label["text"], re.I) is not None)
        average_intro = (introduction if introduction and re.search(r"^The following table\b.*\baverage LCR\b",
                            " ".join(introduction["visible_text"].split()), re.I) else None)
        reporting = _table_reporting_declarations(structure=structure, table=table, label=label)
        if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
            item.update(disposition="SOURCE_REPORTING_DECLARATION_CONFLICT", reporting_declarations=reporting)
        elif scope is None or match is None:
            item["disposition"] = "LCR_NAMED_ISSUER_OR_MEASURE_UNPROVEN"
        elif not average and not average_intro:
            item["disposition"] = "LCR_AVERAGE_AGGREGATION_UNPROVEN"
        elif (column_reason or duration is None or duration["measurement_period"] is None
              or set(duration["reasons"]) - {"CLAIMED_MEASUREMENT_PERIOD_DIFFERS"}):
            item["disposition"] = "LCR_ACTUAL_DURATION_OR_PERCENT_UNPROVEN"
        elif (duration["measurement_period"]["period_end"] != target_period["period_end"]
              or duration["measurement_period"]["period_start"] < target_period["period_start"]):
            item["disposition"] = "LCR_DISCLOSED_INTERVAL_OUTSIDE_REQUESTED_FILING"
        else:
            item["disposition"] = "SOURCE_WITNESSED_FIRM_AVERAGE_LCR"
            selected.append({**item, "value": decimal_text(value=parse_numeric_claim(raw_value=cell["text"], reported_unit="percent")),
                "scope": {"entity_scope": "firm", "aggregation": "average"}, "entity_evidence": scope,
                "reporting_declarations": reporting,
                "aggregation_evidence": {"row_label": label if average else None, "table_introduction": average_intro},
                "duration_evidence": duration, "measurement_period": duration["measurement_period"]})
        if item["disposition"] != "SOURCE_WITNESSED_FIRM_AVERAGE_LCR":
            unresolved.append(item)
        census.append(item)
    facts = {(c["value"], c["measurement_period"]["period_start"], c["measurement_period"]["period_end"]) for c in selected}
    if len(facts) > 1:
        unresolved.append({"disposition": "CONFLICTING_SAME_SCOPE_LCR_FACTS"})
    single = len(facts) == 1 and not unresolved
    body = {"record_type": "LCR_SOURCE_DISCLOSED_PERIOD_FACT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "task_contract_hash": discovery["task_contract_hash"],
        "discovery": discovery, "issuer_identity": issuer, "target_filing_period": target_period,
        "status": "SINGLE_SOURCE_SEMANTIC_FACT" if single else "UNRESOLVED",
        "value": selected[0]["value"] if single else None, "unit": "ratio",
        "measurement_period": selected[0]["measurement_period"] if single else None,
        "selected": selected, "candidate_census": census, "unresolved": unresolved,
        "ordinary_result_rule_status": "EXPLICIT_DISCLOSED_PERIOD_RULE_REQUIRED",
        "annual_average_claimed": bool(single and selected[0]["measurement_period"]["period_start"] == target_period["period_start"]),
        "historical_citi_exception_reused": False, "native_evidence_status": "NOT_EVALUATED",
        "qualification_credit": "NONE_COMPONENT_ONLY", "publication_credit": "NONE",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}


def inspect_balance_candidate_evidence(
    *, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
    expected_cik: str, target_period: dict, metric_id: str,
) -> dict:
    """Combine ordinary candidate discovery with AUM or total-VaR source scope."""
    from .financial_balance_scope import inspect_aum_balance, inspect_total_var

    if metric_id not in {"A11", "A12"}:
        raise FinancialCandidateError("BALANCE_METRIC_UNSUPPORTED")
    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"]
             if task["metric_ids"] == [metric_id]]
    if len(tasks) != 1:
        raise FinancialCandidateError("BALANCE_TASK_NOT_UNIQUE")
    discovery = inspect_financial_candidates(
        repo_root=repo_root, source_bytes=source_bytes, expected_source_sha256=expected_source_sha256,
        task_contract_id=tasks[0]["task_contract_id"], target_period=target_period,
    )
    scope = (inspect_aum_balance if metric_id == "A11" else inspect_total_var)(
        repo_root=repo_root, source_bytes=source_bytes, expected_source_sha256=expected_source_sha256,
        expected_cik=expected_cik, target_period=target_period,
    )
    if scope["task_contract_hash"] != discovery["task_contract_hash"]:
        raise FinancialCandidateError("DISCOVERY_SCOPE_TASK_DIFFERS")
    supported = scope["status"] in {"BALANCE_SCOPE_PROVEN", "TOTAL_VAR_SCOPE_PROVEN"}
    entries = scope.get("disclosures", scope.get("totals", [])) if supported else []
    bindings = []
    for entry in entries:
        matches = [candidate["candidate_id"] for candidate in discovery["candidates"]
                   if candidate["locator"] == entry["value"]["locator"]]
        bindings.append({"locator": entry["value"]["locator"], "candidate_ids": matches})
    body = {"record_type": "FINANCIAL_BALANCE_DISCOVERY_COMPONENT_BINDING", "schema_version": 1,
        "metric_id": metric_id, "source_sha256": expected_source_sha256, "target_period": dict(target_period),
        "discovery": discovery, "scope_component": scope, "bindings": bindings,
        "status": "SCOPE_BOUND_TO_DISCOVERED_CANDIDATES" if bindings and all(len(b["candidate_ids"]) == 1 for b in bindings) else "UNRESOLVED",
        "native_evidence_status": "NOT_EVALUATED", "auto_execution_eligible": False,
        "qualification_credit": "NONE_COMPONENT_ONLY", "publication_credit": "NONE",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "binding_id": content_hash(value=body)}
