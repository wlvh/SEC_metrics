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
    _MONTH, _date, _cell_proof, _column_period, _linked_notes, inspect_financial_duration,
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


def _entity_tokens(text):
    """Punctuation/case normalization only; no substring or fuzzy issuer match."""
    return re.findall(r"\w+", text.casefold().replace("&", " and "))


def _issuer_identity(*, source_bytes, expected_cik, target_period, structure):
    from .deterministic_router import parse_accession_xbrl_source
    from .governance_signals import _FactAttributes
    parsed = parse_accession_xbrl_source(raw_bytes=source_bytes)
    metadata = _FactAttributes()
    metadata.feed(source_bytes.decode("utf-8"))
    metadata.close()
    if metadata.ordinal != len(parsed.facts):
        raise FinancialRelationshipError("ENTITY_FACT_STREAM_DIFFERS")
    names = []
    for fact in parsed.facts:
        namespace, concept = metadata.facts[fact["ordinal"]]["concept"]
        if (concept.casefold() != "entityregistrantname" or not re.fullmatch(
                r"https?://xbrl\.sec\.gov/dei/[0-9]{4}", namespace)):
            continue
        context = parsed.contexts[fact["context_ref"]]
        if (not str(context["entity_identifier"]).isdigit()
                or int(context["entity_identifier"]) != int(expected_cik)
                or context["dimensions"] or context["typed_dimension_count"]
                or any(context[key] != target_period[key] for key in ("period_start", "period_end"))):
            raise FinancialRelationshipError("ENTITY_NAME_CONTEXT_CONFLICT")
        names.append({"name": fact["text"], "ordinal": fact["ordinal"],
                      "qualified_name": fact["qualified_name"], "context_ref": fact["context_ref"],
                      "entity_cik": str(int(context["entity_identifier"])), "namespace": namespace})
    identities = {tuple(_entity_tokens(item["name"])) for item in names}
    if len(identities) != 1 or not next(iter(identities)):
        raise FinancialRelationshipError("ENTITY_REGISTRANT_NAME_NOT_UNIQUE")
    tokens = next(iter(identities))
    aliases, consolidated, legal_aliases = [], [], []
    # A quoted alias immediately after the exact legal name is a definition.
    # A random occurrence of Firm elsewhere is only a search lead.
    for block in structure["blocks"]:
        if block["inside_table"]:
            continue
        for match in re.finditer(r"\(([^()]{1,200})\)", block["visible_text"]):
            quoted_aliases = re.findall(r'[“"]([^”"]+)[”"]', match[1])
            if not quoted_aliases:
                continue
            prefix = block["visible_text"][:match.start()]
            if tuple(_entity_tokens(prefix)[-len(tokens):]) == tokens:
                legal_aliases.extend({"name": alias, "definition": block}
                                     for alias in quoted_aliases)
            if re.search(r'[“"]Firm[”"]', match[1]) is None:
                continue
            if (tuple(_entity_tokens(prefix)[-len(tokens):]) == tokens
                    and not re.search(r"\bnot\b|\bexcluding\b", prefix[-100:], re.I)):
                aliases.append({"alias": "Firm", "definition": block})
            suffix = _entity_tokens(prefix)
            if (suffix[-3:] == ["and", "its", "subsidiaries"]
                    and tuple(suffix[-len(tokens) - 3:-3]) == tokens):
                proof = {"alias": "Firm", "definition": block, "entity_scope": "REGISTRANT_AND_SUBSIDIARIES"}
                aliases.append(proof)
                consolidated.append(proof)
        definition = re.search(r"^Throughout this report, (.+?) refer to (.+?) and its consolidated subsidiaries\.",
                               " ".join(block["visible_text"].split()), re.I)
        if definition and tuple(_entity_tokens(definition[2])) == tokens:
            consolidated.extend({"alias": alias.strip(","), "definition": block,
                                 "entity_scope": "REGISTRANT_AND_CONSOLIDATED_SUBSIDIARIES"}
                                for alias in re.findall(r'[“"]([^”"]+)[”"]', definition[1]))
    other_entities = []
    for owner in sorted({names[0]["name"], *(alias["name"] for alias in legal_aliases)}):
        pattern = re.compile(re.escape(owner) + r"[’']s (?:principal )?(?:bank |non-bank )?subsidiary is "
                             r"([^()]{1,200}?)\s*\((?:the )?[“\"]([^”\"]+)[”\"]\)", re.I)
        for block in structure["blocks"]:
            if block["inside_table"]:
                continue
            for match in pattern.finditer(" ".join(block["visible_text"].split())):
                other_entities.append({"owner": owner, "legal_name": match[1].strip(), "alias": match[2],
                                       "relationship": "EXPLICIT_SUBSIDIARY_OF_REGISTRANT", "definition": block})
    return {"registrant_name": names[0]["name"], "native_name_facts": names,
            "normalization": "EXACT_TOKENS_CASE_PUNCTUATION_AND_AMPERSAND_ONLY",
            "source_defined_aliases": aliases, "source_consolidated_aliases": consolidated,
            "source_legal_name_aliases": legal_aliases, "source_defined_other_entities": other_entities}


def _nearest_table_introduction(structure, table):
    span = structure["tables"][table["order"]]
    prior = [s["end_byte"] for s in structure["tables"] if s["end_byte"] <= span["start_byte"]]
    left = max(prior, default=0)
    blocks = [b for b in structure["blocks"] if not b["inside_table"]
              and left <= b["start_byte"] < b["end_byte"] <= span["start_byte"]]
    return blocks[-1] if blocks else None


def _table_reporting_declarations(*, structure, table, label=None):
    """Check assertions about this table's values, not words anywhere nearby.

    A model may use hypothetical shocks to calculate a genuinely reported VaR.
    The contradiction is a declaration that the selected table's own amounts
    are illustrative, forecast/pro-forma or explicitly not reported values.
    Only forward table references in the intervening introduction, this-table
    captions/headers, and notes linked by the selected row are considered.
    """
    span = structure["tables"][table["order"]]
    previous = max((s["end_byte"] for s in structure["tables"] if s["end_byte"] <= span["start_byte"]), default=0)
    sources = [("INTRODUCTION", b["visible_text"], b) for b in structure["blocks"]
               if not b["inside_table"] and previous <= b["start_byte"] < b["end_byte"] <= span["start_byte"]]
    for row in table["rows"][:min(4, label["row_index"] if label else 4)]:
        for cell in row["cells"]:
            if cell["is_origin"] and cell["text"]:
                sources.append(("TABLE_HEADER", cell["text"], _cell_proof(table=table, cell=cell)))
    if table.get("caption_raw_text"):
        sources.append(("TABLE_CAPTION", table["caption_raw_text"], {"table_id": table["table_id"],
                        "grid_sha256": table["grid_sha256"], "caption_raw_text": table["caption_raw_text"]}))
    if label:
        markers = set(re.findall(r"\(([a-z]|[0-9]{1,2})\)", label["text"], re.I))
        notes, _ = _linked_notes(structure=structure, table_order=table["order"], markers={m.casefold() for m in markers})
        sources.extend(("ROW_LINKED_NOTE", n["visible_text"], n) for n in notes)
    statements, conflicts = [], []
    for kind, text, proof in sources:
        associated = kind in {"TABLE_CAPTION", "ROW_LINKED_NOTE"}
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
            direct = re.search(r"\b(?:the following table|the table below|this table|amounts in (?:this|the following) table)\b", sentence, re.I)
            continued = associated and re.search(r"\b(?:these|the) (?:amounts|values|figures|results|estimates)(?: shown)?\b", sentence, re.I)
            named_row = label is not None and _clean(label["text"]) in _clean(sentence)
            if kind == "ROW_LINKED_NOTE" and not (direct or continued or named_row):
                continue
            if not direct and not continued and kind not in {"TABLE_CAPTION", "ROW_LINKED_NOTE", "TABLE_HEADER"}:
                continue
            if re.search(r"\b(?:preceding|previous|earlier|another|other) (?:table|example)\b", sentence, re.I) and not direct:
                continue
            associated = associated or bool(direct)
            explicit = re.search(r"\bnot (?:the )?(?:actual )?reported\b|\bnot (?:actual )?values reported\b", sentence, re.I)
            illustrative = re.search(
                r"\b(?:table|amounts|values|figures|results) (?:is|are) (?:solely |only )?(?:for illustration|illustrative|hypothetical)\b"
                r"|\b(?:shows?|presents?|contains?) (?:only )?(?:hypothetical|illustrative|pro[- ]forma|forecast) (?:amounts|values|figures|results|estimates)\b"
                r"|\bfor (?:illustration|illustrative purposes) only\b", sentence, re.I)
            # A negative statement about the method's assumptions is not an
            # admission that the displayed metric is unreported.
            if not explicit and not illustrative:
                continue
            if kind == "TABLE_HEADER" and not direct and not re.search(r"\b(?:values|amounts|figures|results|estimates)\b", sentence, re.I):
                continue
            item = {"kind": kind, "statement": sentence, "source": proof,
                    "reason": "EXPLICIT_NON_REPORTED_TABLE_VALUES" if explicit else "ILLUSTRATIVE_OR_HYPOTHETICAL_TABLE_VALUES"}
            statements.append(item)
            conflicts.append(item)
    return {"status": "SOURCE_REPORTING_DECLARATION_CONFLICT" if conflicts else "NO_ASSOCIATED_REPORTING_CONTRADICTION",
            "conflicts": conflicts, "associated_qualifying_statements": statements}


def _instant_column(table, cell):
    column, headers, reason = _column_period(table=table, selected=cell)
    if reason:
        return None
    dates = []
    for row in table["rows"][:column["row_index"] + 1]:
        for header in row["cells"]:
            if not header["is_origin"]:
                continue
            match = re.fullmatch(r"(?:As of )?(" + _MONTH + r")\s+([0-9]{1,2}),?(?:\s+\(.*\))?",
                                 " ".join(header["text"].split()), re.I)
            if match:
                try:
                    dates.append((_date(year=column["year"], month=match[1], day=int(match[2])), header))
                except ValueError:
                    return None
    if column["date"] is not None:
        dates.extend((column["date"], header) for header, _, _ in headers)
    if len({day for day, _ in dates}) != 1:
        return None
    return {"kind": "INSTANT", "as_of_date": dates[0][0].isoformat(),
            "source_headers": [_cell_proof(table=table, cell=h) for _, h in dates],
            "column_headers": [_cell_proof(table=table, cell=h) for h, _, _ in headers]}


def _reported_segment_sections(builders, structure):
    """Read the issuer's explicit segment list and its separate section titles."""
    definitions = []
    for block in structure["blocks"]:
        if block["inside_table"]:
            continue
        match = re.search(r"has (?:[0-9]+|two|three|four|five|six) reportable business segments\s*[–—-]\s*"
                          r"(.+?)\s*[–—-]\s*with the remaining activities in", block["visible_text"], re.I)
        if match:
            named = re.sub(r"\s*\([“\"][A-Za-z]+[”\"]\)", "", match[1])
            names = re.split(r",\s*(?:and\s+)?|\s+and\s+", named)
            definitions.append(({tuple(_entity_tokens(name)) for name in names}, block))
    consistent = len({frozenset(names) for names, _ in definitions}) == 1
    headings = []
    for builder in builders:
        nonempty = [_semantic_text(raw_text="".join(c.raw_parts)) for row in builder.rows for c in row]
        nonempty = [text for text in nonempty if text]
        if len(nonempty) != 1 or not nonempty[0].isupper() or len(nonempty[0]) < 5:
            continue
        table, _ = _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                                  remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
        cell = next(c for row in table["rows"] for c in row["cells"] if c["is_origin"] and c["text"])
        matches = [block for names, block in definitions if consistent and tuple(_entity_tokens(cell["text"])) in names]
        headings.append({"table_order": table["order"], "heading": _cell_proof(table=table, cell=cell),
                         "segment_definition": {"consistent_source_definitions": matches} if matches else None})
    return headings


def _segment_at(headings, table):
    prior = [h for h in headings if h["table_order"] < table["order"]]
    nearest = prior[-1] if prior else None
    return nearest if nearest and nearest["segment_definition"] else None


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
_NIM_RATE_LEAD = re.compile(r"net interest margin|net yield on average interest[- ]earning assets", re.I)


def _role(text):
    clean = _clean(text)
    return next((name for name, pattern in _ROLES.items() if pattern.fullmatch(clean)), None)


def _scale(table, header_rows=3):
    evidence = []
    for row in table["rows"][:header_rows]:
        for cell in row["cells"]:
            if not cell["is_origin"]:
                continue
            if re.search(r"\b(?:EUR|euros?|GBP|pounds?|JPY|yen)\b|[€£¥]", cell["text"], re.I):
                return None
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


def inspect_nonaccrual_loan_ratio(*, repo_root: Path, source_bytes: bytes, expected_source_sha256: str,
                                 expected_cik: str, target_period: dict) -> dict:
    """Prove the source's firmwide nonaccrual/total-loan disclosed ratio.

    This is HTML economic evidence, not authority to bypass A09's structured
    route. The SourceSet composition in financial_structured owns that gate.
    All loan-ratio leads remain in the census, including segment and retained
    loan subpopulations; only explicit source scope can exclude them.
    """
    if (type(source_bytes) is not bytes or not source_bytes
            or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or sha256_bytes(content=source_bytes) != expected_source_sha256):
        raise FinancialRelationshipError("SOURCE_BYTES_DIFFER")
    if annual_period(raw=source_bytes, cik=expected_cik,
                     filing={"form": "10-K", "reportDate": target_period["period_end"]}) != target_period:
        raise FinancialRelationshipError("SOURCE_PERIOD_DIFFERS")
    tasks = [t for t in inspect_r4_task_catalog(repo_root=repo_root)["contracts"] if t["metric_ids"] == ["A09"]]
    if len(tasks) != 1 or tasks[0]["required_claims"] != {"loan_population": "firmwide"}:
        raise FinancialRelationshipError("LOAN_RATIO_SCOPE_UNSUPPORTED")
    task = tasks[0]
    spec = compile_spec_file(path=repo_root / task["metric_spec_paths"][0], dependency_specs={})["compiled"]
    if spec["source_mode"] != "structured_first_ai_fallback" or spec["canonical_unit"] != "ratio":
        raise FinancialRelationshipError("LOAN_RATIO_ROUTE_UNSUPPORTED")
    parser = _AllTablesParser()
    parser.feed(source_bytes.decode("utf-8"))
    parser.close()
    structure = index_source_structure(source_bytes=source_bytes)
    issuer = _issuer_identity(source_bytes=source_bytes, expected_cik=expected_cik,
                              target_period=target_period, structure=structure)
    sections = _reported_segment_sections(parser.tables, structure)
    census, selected, unresolved = [], [], []
    lead = re.compile(r"nonaccrual.+\bto\b|non[- ]?perform.*(?:ratio|percent)|loan ratio|\bfirmwide\b", re.I)
    exact = re.compile(r"firmwide nonaccrual loans to total loans outstanding", re.I)
    for builder in parser.tables:
        if not any(lead.search(_semantic_text(raw_text="".join(c.raw_parts))) for r in builder.rows for c in r):
            continue
        table, _ = _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                                  remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
        segment = _segment_at(sections, table)
        for row in table["rows"]:
            labels = [c for c in row["cells"] if c["is_origin"] and lead.search(c["text"])]
            for label in labels:
                for cell in row["cells"]:
                    if not cell["is_origin"] or cell["column_index"] <= label["column_index"]:
                        continue
                    try:
                        value = parse_numeric_claim(raw_value=cell["text"], reported_unit="ratio")
                    except ConstraintError:
                        continue
                    item = {"label": _cell_proof(table=table, cell=label),
                            "locator": _cell_proof(table=table, cell=cell)}
                    page = _covering_headers(table, cell, "page")
                    column, _, _ = _column_period(table=table, selected=cell)
                    if page and column is None:
                        item.update(disposition="NONFINANCIAL_PAGE_COLUMN", source_scope_evidence=[_cell_proof(table=table, cell=h) for h in page])
                    elif re.search(r"\bcriticized\b.*\bretained\b|\bsecured by real estate\b", label["text"], re.I):
                        item.update(disposition="EXPLICIT_DIFFERENT_LOAN_POPULATION")
                    elif segment:
                        item.update(disposition="OTHER_REPORTED_BUSINESS_SEGMENT", source_scope_evidence=segment)
                    else:
                        instant = _instant_column(table, cell)
                        item["measurement_time"] = instant
                        if instant and instant["as_of_date"] != target_period["period_end"]:
                            item["disposition"] = "DIFFERENT_SOURCE_INSTANT"
                        elif not exact.fullmatch(_clean(label["text"])):
                            item["disposition"] = "LOAN_RATIO_NAME_OR_SCOPE_UNPROVEN"
                            unresolved.append(item)
                        elif instant is None or not _percent(table, cell):
                            item["disposition"] = "LOAN_RATIO_INSTANT_OR_PERCENT_UNPROVEN"
                            unresolved.append(item)
                        else:
                            introduction = _nearest_table_introduction(structure, table)
                            named = bool(introduction and re.fullmatch(
                                r"The following table provides information on Firmwide nonaccrual loans to total loans\.",
                                " ".join(introduction["visible_text"].split()), re.I))
                            roles = {}
                            for role_row in table["rows"]:
                                for role_label in role_row["cells"]:
                                    if not role_label["is_origin"]:
                                        continue
                                    role = {"total nonaccrual loans": "numerator", "total loans": "denominator"}.get(_clean(role_label["text"]))
                                    if role:
                                        roles.setdefault(role, []).extend((entry, role_label) for entry in _cells(table, role_row["row_index"], target_period))
                            scale = _scale(table)
                            reporting = _table_reporting_declarations(structure=structure, table=table, label=label)
                            if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
                                item.update(disposition="SOURCE_REPORTING_DECLARATION_CONFLICT", reporting_declarations=reporting)
                                unresolved.append(item)
                            elif (not named or not any(a["alias"] == "Firm" for a in issuer["source_consolidated_aliases"]) or scale is None
                                    or any(len(roles.get(role, [])) != 1 for role in ("numerator", "denominator"))):
                                item["disposition"] = "LOAN_RATIO_NAMED_ROLES_OR_ISSUER_UNPROVEN"
                                unresolved.append(item)
                            else:
                                proofs = {role: _proof(table, entries[0][0], scale) for role, entries in roles.items()}
                                role_times = [_instant_column(table, roles[role][0][0]["cell"]) for role in roles]
                                check = _check_rate(proofs["numerator"], proofs["denominator"], cell)
                                if (any(t is None or t["as_of_date"] != instant["as_of_date"] for t in role_times)
                                        or check is None or not check["consistent"]):
                                    item["disposition"] = "LOAN_RATIO_PERIOD_OR_RELATIONSHIP_CONFLICT"
                                    unresolved.append(item)
                                else:
                                    item["disposition"] = "SOURCE_WITNESSED_FIRMWIDE_NONACCRUAL_RATIO"
                                    selected.append({**item, "source_roles": proofs,
                                        "reporting_declarations": reporting,
                                        "role_labels": {role: _cell_proof(table=table, cell=entries[0][1]) for role, entries in roles.items()},
                                        "rate_check": check, "table_association": introduction,
                                        "scope": {"loan_population": "firmwide"}})
                    census.append(item)
    values = {entry["rate_check"]["disclosed_ratio"] for entry in selected}
    if len(values) > 1:
        unresolved.append({"disposition": "CONFLICTING_FIRMWIDE_DISCLOSED_RATIOS"})
    body = {"record_type": "FIRMWIDE_NONACCRUAL_RATIO_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "task_contract_hash": content_hash(value=task),
        "target_filing_period": target_period, "issuer_identity": issuer,
        "status": "SINGLE_SOURCE_SEMANTIC_FACT" if len(values) == 1 and not unresolved else "UNRESOLVED",
        "value": next(iter(values)) if len(values) == 1 and not unresolved else None,
        "unit": "ratio", "selected": selected, "candidate_census": census, "unresolved": unresolved,
        "measurement_time": {"kind": "INSTANT", "as_of_date": target_period["period_end"]},
        "structured_route_status": "REQUIRES_RECOMPUTED_SOURCE_SET_ROUTE",
        "interpretation": "SOURCE_DISCLOSED_NONACCRUAL_LOANS_DIVIDED_BY_TOTAL_LOANS_NOT_NONPERFORMING_ASSETS",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}


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
        if not any(_role(_semantic_text(raw_text="".join(cell.raw_parts))) or _NIM_RATE_LEAD.search(
                _semantic_text(raw_text="".join(cell.raw_parts))) for row in builder.rows for cell in row):
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
    rate_census = []
    selected_locators = [relation["rate_locator"] for relation in relations]
    for table, _ in tables:
        for row in table["rows"]:
            labels = [c for c in row["cells"] if c["is_origin"] and _NIM_RATE_LEAD.search(c["text"])]
            for label in labels:
                for cell in row["cells"]:
                    if not cell["is_origin"] or cell["column_index"] <= label["column_index"]:
                        continue
                    try:
                        parse_numeric_claim(raw_value=cell["text"], reported_unit="ratio")
                    except ConstraintError:
                        continue
                    locator = _cell_proof(table=table, cell=cell)
                    column, headers, _ = _column_period(table=table, selected=cell)
                    item = {"label": _cell_proof(table=table, cell=label), "locator": locator,
                            "column_headers": [_cell_proof(table=table, cell=h) for h, _, _ in headers]}
                    introduction = _nearest_table_introduction(structure, table)
                    changes = [h for prior in table["rows"][:cell["row_index"]] for h in prior["cells"] if h["is_origin"]
                               and h["column_index"] <= cell["column_index"] < h["column_index"] + h["colspan"]
                               and re.fullmatch(r"change (?:19|20)[0-9]{2} vs\. (?:19|20)[0-9]{2}", _clean(h["text"]))]
                    if column is None and _covering_headers(table, cell, "page"):
                        disposition = "NONFINANCIAL_PAGE_COLUMN"
                    elif column is None and introduction and re.search(r"\bTable of Contents$", introduction["visible_text"], re.I):
                        disposition = "SOURCE_NAMED_TABLE_OF_CONTENTS"
                        item["navigation_heading"] = introduction
                    elif column is None and changes:
                        disposition = "EXPLICIT_BETWEEN_YEAR_CHANGE_COLUMN"
                        item["change_headers"] = [_cell_proof(table=table, cell=h) for h in changes]
                    elif column and column["year"] != target_period["fiscal_year"]:
                        disposition = "DIFFERENT_SOURCE_YEAR"
                    elif _clean(label["text"]) == "net yield on average interest-earning assets excluding markets":
                        disposition = "EXPLICIT_MARKETS_EXCLUDED_MEASURE"
                    elif locator in selected_locators:
                        disposition = "SOURCE_NAMED_NIM_RELATIONSHIP"
                    else:
                        disposition = "SAME_NAMED_NIM_CANDIDATE_UNRESOLVED"
                        rejected.append({"reason": disposition, "candidate": item})
                    item["disposition"] = disposition
                    rate_census.append(item)
    issuer = _issuer_identity(source_bytes=source_bytes, expected_cik=expected_cik,
                              target_period=target_period, structure=structure)
    whole_scope = []
    for relation in relations:
        table = next(t for t, _ in tables if t["table_id"] == relation["rate_locator"]["table_id"])
        label = relation.get("rate_label") or relation["role_labels"]["net_yield"]
        reporting = _table_reporting_declarations(structure=structure, table=table, label=label)
        relation["reporting_declarations"] = reporting
        if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
            rejected.append({"reason": "SOURCE_REPORTING_DECLARATION_CONFLICT", "reporting_declarations": reporting})
            continue
        if relation["mechanism"] == "SOURCE_EXPLICIT_NIM_FORMULA_WITH_NAMED_TOTAL_CORROBORATION":
            subject = relation["formula_evidence"]["subject"]
            # The formula grammar allows a possessive subject ("Issuer's NIM").
            # Remove only that grammatical suffix, never tokens from a legal name.
            named_subject = re.sub(r"[’']s$", "", subject)
            definitions = [a for a in issuer["source_consolidated_aliases"]
                           if _entity_tokens(a["alias"]) == _entity_tokens(named_subject)]
            if definitions:
                whole_scope.append({"basis": "EXPLICIT_FORMULA_NAMES_SOURCE_DEFINED_CONSOLIDATED_ISSUER",
                                    "issuer_definitions": definitions, "formula": relation["formula_evidence"]["definition"],
                                    "source_subject_text": subject, "grammatical_subject": named_subject})
        else:
            table = next(t for t, _ in tables if t["table_id"] == relation["rate_locator"]["table_id"])
            introduction = _nearest_table_introduction(structure, table)
            definitions = [a for a in issuer["source_consolidated_aliases"] if a["alias"] == "Firm"]
            text = " ".join(introduction["visible_text"].split()) if introduction else ""
            if (definitions and text.startswith("In addition to reviewing net interest income, net yield,")
                    and "on a managed basis" in text and "excluding Markets, as shown below" in text
                    and re.search(r"\bFirm[’']s lending, investing\b", text)):
                whole_scope.append({"basis": "SOURCE_FIRM_MANAGED_BASELINE_WITH_EXPLICIT_MARKETS_EXCLUSION_BRIDGE",
                    "issuer_definitions": definitions, "table_introduction": introduction,
                    "included_baseline_labels": relation["role_labels"],
                    "selected_measure_excludes_markets": False})
    whole = len(relations) == len(whole_scope) == 1 and not rejected
    body = {"record_type": "NIM_SOURCE_RELATIONSHIP_COMPONENT", "schema_version": 1,
        "source_sha256": expected_source_sha256, "source_size": len(source_bytes),
        "source_entity_cik": str(int(expected_cik)), "source_fiscal_period": source_period,
        "task_contract_hash": content_hash(value=task), "metric_id": "A04",
        "status": "RELATIONSHIP_PROVEN" if len(relations) == 1 and not rejected else "UNRESOLVED",
        "relations": relations, "rejected_candidates": rejected, "named_role_census": census,
        "same_named_rate_census": rate_census,
        "whole_issuer_scope_status": "SOURCE_WITNESSED_WHOLE_ISSUER" if whole else "REQUIRES_NATIVE_SCOPE_ACCEPTANCE",
        "issuer_identity": issuer, "whole_issuer_scope_evidence": whole_scope,
        "semantic_status": "SINGLE_SOURCE_SEMANTIC_FACT" if whole else "UNRESOLVED",
        "native_evidence_status": "NOT_EVALUATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "result_value_policy": "RETAIN_DISCLOSED_RATE_NOT_COMPUTED_PROXY",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "relationship_id": content_hash(value=body)}
