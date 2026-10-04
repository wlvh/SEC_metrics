"""Ordinary inline-XBRL financial claims with source-derived label witnesses.

No fixture recipe, reference number, or injected geography-member list selects
a result. Native contexts and claims retain their SourceSet; exact original
table labels explain the member and measure. This remains component evidence,
not a grant of source admission, provider use, native Run acceptance or release.
"""

from pathlib import Path
import re

from sec_http import request_log_attempt_id
from sec_urls import accession_document_url
from .annual_update import _rows, saved_source
from .canonical import content_hash, sha256_bytes
from .composite_scope import index_source_structure
from .constraints import parse_numeric_claim
from .deterministic_router import (
    adapt_accession_xbrl_from_parsed, parse_accession_xbrl_source,
    source_set_manifest as build_source_set, verify_source_set_completeness,
)
from .financial_duration import _cell_proof, _linked_notes
from .financial_relationships import _clean, _scale, _table_reporting_declarations
from .normal_annual_input import annual_period, prepare_saved_annual_input
from .r4_structured_sources import FIXTURE_SET_TYPE, validate_fixture_source_set
from .r4_task_contracts import inspect_r4_task_catalog
from .resource_limits import RESOURCE_LIMITS
from .sources import raw_blob_record, source_reference_record
from .table_grid import _AllTablesParser, _expanded_table


class FinancialStructuredError(ValueError):
    """Reject incomplete native context or an unproved source interpretation."""


class _InlineTableIndex(_AllTablesParser):
    """Attach native fact ordinals to the unchanged native raw cell objects."""

    def __init__(self, source_bytes):
        super().__init__()
        self.fact_ordinal = 0
        self.cell_ordinals = {}
        self.units = {}
        self._unit = None
        self._in_measure = False
        self.namespaces = {}
        self.source = source_bytes.decode("utf-8")
        self.lines = [0] + [match.end() for match in re.finditer("\n", self.source)]
        self._char_cursor = 0
        self._byte_cursor = 0
        self.fact_positions = {}

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        attributes = {key.casefold(): value for key, value in attrs}
        for key, value in attributes.items():
            if key.startswith("xmlns:"):
                self.namespaces.setdefault(key.split(":", 1)[1], set()).add(value)
        local = tag.rsplit(":", 1)[-1]
        if local == "unit":
            self._unit = {"id": attributes.get("id"), "measures": [], "divide": False}
        elif self._unit is not None and local == "measure":
            self._in_measure = True
            self._unit["measures"].append("")
        elif self._unit is not None and local == "divide":
            self._unit["divide"] = True
        if "contextref" in attributes:
            self.fact_ordinal += 1
            line, column = self.getpos()
            position = self.lines[line - 1] + column
            self._byte_cursor += len(self.source[self._char_cursor:position].encode("utf-8"))
            self._char_cursor = position
            self.fact_positions[self.fact_ordinal] = self._byte_cursor
            if self._stack and self._stack[-1].current_cell is not None:
                self.cell_ordinals.setdefault(id(self._stack[-1].current_cell), []).append(self.fact_ordinal)

    def handle_data(self, data):
        super().handle_data(data)
        if self._unit is not None and self._in_measure:
            self._unit["measures"][-1] += data

    def handle_endtag(self, tag):
        local = tag.rsplit(":", 1)[-1]
        if local == "measure":
            self._in_measure = False
        elif local == "unit" and self._unit is not None:
            unit_id = self._unit["id"]
            if not unit_id or unit_id in self.units:
                raise FinancialStructuredError("SOURCE_UNIT_ID_MISSING_OR_DUPLICATED")
            self.units[unit_id] = self._unit
            self._unit = None
        super().handle_endtag(tag)

    def unit(self, unit_id):
        unit = self.units.get(unit_id)
        if not unit or unit["divide"] or len(unit["measures"]) != 1:
            return None
        measure = unit["measures"][0].strip()
        if ":" not in measure:
            return None
        prefix, local = measure.split(":", 1)
        namespace = self.namespaces.get(prefix.casefold(), set())
        if namespace == {"http://www.xbrl.org/2003/iso4217"} and local == "USD":
            canonical = "USD"
        elif namespace == {"http://www.xbrl.org/2003/instance"} and local == "pure":
            canonical = "ratio"
        else:
            return None
        return {"unit_id": unit_id, "measure": measure, "namespace": next(iter(namespace)),
                "canonical_unit": canonical}


def prepare_saved_inline_source_set(*, repo_root: Path, company_id: str) -> dict:
    """Build a real normal SourceSet from the ordinary saved-input selection."""
    prepared = prepare_saved_annual_input(repo_root=repo_root, company_id=company_id)
    if prepared["update_status"] != "ORIGINAL_INPUT_READY":
        raise FinancialStructuredError("CURRENT_ORIGINAL_INPUT_NOT_READY")
    rows = _rows(repo_root)
    source_items = []
    for proof in prepared["source_proofs"][:2]:
        item = saved_source(repo_root=repo_root, url=proof["source_url"], accession=proof["accession"])
        if item is None or item["proof"] != proof:
            raise FinancialStructuredError("SOURCE_CHANGED_AFTER_ORDINARY_SELECTION")
        matches = [row for index, row in enumerate(rows)
                   if request_log_attempt_id(row_index=index, row=row) == proof["request_attempt_id"]]
        if len(matches) != 1:
            raise FinancialStructuredError("SAVED_ATTEMPT_NOT_UNIQUE")
        row = matches[0]
        inventory = not source_items
        raw = raw_blob_record(repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"],
                              media_type="application/json" if inventory else "text/html")
        # Submissions is a dataset, not a filing; its saved ledger accession
        # can be empty. This explicit dataset identity is not a filing claim.
        accession = row["accession"] or ("SEC_SUBMISSIONS_INVENTORY" if inventory else "")
        reference = source_reference_record(raw_blob=raw, company_id=company_id,
            source_url=proof["source_url"], accession=accession, document_name=proof["document_name"],
            source_role="sec_submissions_inventory" if inventory else "target_primary",
            request_attempt_id=proof["request_attempt_id"])
        source_items.append({"reference": reference, "raw": item["raw"]})
    inventory, primary = source_items
    day = prepared["filing"]["filingDate"]
    manifest = build_source_set(company_id=company_id, source_role="target_primary", form_types=["10-K"],
        fiscal_or_date_window={"period_start": day, "period_end": day},
        discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
        inventory_source_reference=inventory["reference"], inventory_bytes=inventory["raw"],
        ordered_source_references=[primary["reference"]],
        cutoff_timestamp_or_pinned_submissions_attempt=inventory["reference"]["request_attempt_id"])
    return {"prepared_input_id": prepared["input_id"], "source_bytes": primary["raw"],
            "source_reference": primary["reference"], "source_set_manifest": manifest,
            "inventory_source_reference": inventory["reference"], "inventory_bytes": inventory["raw"],
            "expected_cik": prepared["entity"], "target_period": prepared["table_input"]["target_period"]}


def _source_set(*, source_reference, source_set_manifest, inventory_source_reference, inventory_bytes):
    if source_set_manifest.get("record_type") == FIXTURE_SET_TYPE:
        value = validate_fixture_source_set(manifest=source_set_manifest)
        if value["source_reference"] != source_reference:
            raise FinancialStructuredError("FIXTURE_SOURCE_REFERENCE_DIFFERS")
        return "PINNED_EXISTING_FIXTURE_ONLY_NO_PRODUCTION_CREDIT"
    if inventory_source_reference is None or inventory_bytes is None:
        raise FinancialStructuredError("NORMAL_SOURCE_SET_INVENTORY_REQUIRED")
    verify_source_set_completeness(manifest=source_set_manifest,
        inventory_source_reference=inventory_source_reference, inventory_bytes=inventory_bytes,
        ordered_source_references=[source_reference])
    return "NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET"


def _fact_cells(index, parsed, ordinals):
    if index.fact_ordinal != max((fact["ordinal"] for fact in parsed.facts), default=0):
        raise FinancialStructuredError("NATIVE_FACT_ORDINAL_INDEX_DIFFERS")
    bound = {}
    for builder in index.tables:
        if not any(set(index.cell_ordinals.get(id(cell), [])) & ordinals for row in builder.rows for cell in row):
            continue
        table, _ = _expanded_table(builder=builder, remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                                   remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
        for row_index, raw_row in enumerate(builder.rows):
            origins = [cell for cell in table["rows"][row_index]["cells"] if cell["is_origin"]]
            if len(origins) < len(raw_row):
                raise FinancialStructuredError("RAW_CELL_ORIGIN_MAPPING_DIFFERS")
            for raw, cell in zip(raw_row, origins):
                if (cell["raw_text"] != "".join(raw.raw_parts) or cell["rowspan"] != raw.rowspan
                        or cell["colspan"] != raw.colspan):
                    raise FinancialStructuredError("RAW_CELL_ORIGIN_MAPPING_DIFFERS")
                for ordinal in set(index.cell_ordinals.get(id(raw), [])) & ordinals:
                    if ordinal in bound:
                        raise FinancialStructuredError("NATIVE_FACT_CELL_NOT_UNIQUE")
                    bound[ordinal] = (table, cell)
    return bound


def _revenue_column(table, cell, structure):
    headers = []
    for row in table["rows"][:cell["row_index"]]:
        for header in row["cells"]:
            if (header["is_origin"] and header["column_index"] <= cell["column_index"] < header["column_index"] + header["colspan"]
                    and re.search(r"\brevenue|\bincome\b|\bexpense\b|\bassets\b", header["text"], re.I)):
                headers.append(header)
    if not headers:
        return None
    nearest = max(header["row_index"] for header in headers)
    selected = [header for header in headers if header["row_index"] == nearest]
    if len(selected) != 1:
        return None
    header = selected[0]
    clean = _clean(header["text"])
    if clean in {"revenues, net of interest expense", "total net revenue", "net revenue"}:
        return {"header": _cell_proof(table=table, cell=header), "interpretation": "SOURCE_EXPLICIT_NET_REVENUE"}
    if clean not in {"revenue", "revenues"}:
        return None
    markers = set(re.findall(r"\(([a-z]|[0-9]{1,2})\)", header["text"], re.I))
    notes, missing = _linked_notes(structure=structure, table_order=table["order"], markers={x.casefold() for x in markers})
    definitions = [note for note in notes if re.fullmatch(
        r"\([a-z0-9]+\)\s*Revenue is composed of net interest income and noninterest revenue\.",
        " ".join(note["visible_text"].split()), re.I)]
    if missing or len(definitions) != 1:
        return None
    return {"header": _cell_proof(table=table, cell=header), "definition": definitions[0],
            "interpretation": "SOURCE_DEFINED_NET_INTEREST_PLUS_NONINTEREST_REVENUE"}


def _a13_witness(*, claim, fact, table, cell, task, structure):
    aliases = task["scope_contract"]["exact_enum_aliases"]["geography_scope"]["international"]
    labels = [item for item in table["rows"][cell["row_index"]]["cells"] if item["is_origin"]
              and item["column_index"] < cell["column_index"] and _clean(item["text"]) in {_clean(a) for a in aliases}]
    if len(labels) != 1:
        return None, "NOT_DIRECT_DISCLOSED_INTERNATIONAL_TOTAL_LABEL"
    reporting = _table_reporting_declarations(structure=structure, table=table, label=labels[0])
    if reporting["status"] != "NO_ASSOCIATED_REPORTING_CONTRADICTION":
        return {"reporting_declarations": reporting}, "SOURCE_REPORTING_DECLARATION_CONFLICT"
    measure = _revenue_column(table, cell, structure)
    scale = _scale(table)
    if measure is None:
        return None, "NET_REVENUE_COLUMN_NOT_PROVEN"
    if scale is None:
        return None, "VISIBLE_AMOUNT_SCALE_NOT_PROVEN"
    if fact["text"] != cell["text"]:
        return None, "INLINE_FACT_VISIBLE_CELL_DIFFERS"
    from decimal import Decimal
    from .canonical import arithmetic_context
    with arithmetic_context():
        visible_value = parse_numeric_claim(raw_value=cell["text"], reported_unit="USD") * Decimal(scale["factor"])
    if visible_value != Decimal(claim["value"]):
        return None, "NATIVE_FACT_VISIBLE_SCALE_CONFLICT"
    return {"native_fact_ordinal": fact["ordinal"], "native_context": claim["attributes"]["context"],
            "table_cell": _cell_proof(table=table, cell=cell), "geography_label": _cell_proof(table=table, cell=labels[0]),
            "reporting_declarations": reporting,
            "revenue_measure": measure, "source_amount_scale": scale,
            "member_classification": "FROM_SAME_FACT_ORIGINAL_ROW_LABEL_NOT_MEMBER_SPELLING"}, None


def _a09_witness(*, claim, fact, table, cell):
    if claim["attributes"]["canonical_name"] != "us-gaap:FinancingReceivableExcludingAccruedInterestNonaccrualPercentPastDue":
        return None, "FIRMWIDE_NPL_NATIVE_CONCEPT_RULE_UNIMPLEMENTED"
    labels = [label for label in table["rows"][cell["row_index"]]["cells"] if label["is_origin"]
              and label["column_index"] < cell["column_index"]
              and _clean(label["text"]) == "percentage of outstanding loans and leases"]
    headers = [header for row in table["rows"][:cell["row_index"]] for header in row["cells"]
               if header["is_origin"] and header["column_index"] <= cell["column_index"] < header["column_index"] + header["colspan"]
               and re.search(r"\bnonperforming\b|\baccruing past due\b", header["text"], re.I)]
    if len(labels) != 1 or not headers:
        return None, "FIRMWIDE_NPL_SOURCE_LABELS_UNPROVEN"
    nearest = max(header["row_index"] for header in headers)
    current = [header for header in headers if header["row_index"] == nearest]
    if len(current) != 1 or _clean(current[0]["text"]) != "nonperforming loans and leases":
        return None, "SOURCE_LOAN_STATUS_COLUMN_IS_NOT_NONPERFORMING"
    following = [item for item in table["rows"][cell["row_index"]]["cells"] if item["is_origin"] and item["text"]
                 and item["column_index"] >= cell["column_index"] + cell["colspan"]]
    if not following or following[0]["text"] != "%" or fact["text"] != cell["text"]:
        return None, "SOURCE_NPL_PERCENT_MARKER_UNPROVEN"
    from decimal import Decimal
    if parse_numeric_claim(raw_value=cell["text"], reported_unit="percent") != Decimal(claim["value"]):
        return None, "NATIVE_NPL_PERCENT_SCALE_CONFLICT"
    return {"native_fact_ordinal": fact["ordinal"], "native_context": claim["attributes"]["context"],
            "table_cell": _cell_proof(table=table, cell=cell), "denominator_label": _cell_proof(table=table, cell=labels[0]),
            "loan_status_header": _cell_proof(table=table, cell=current[0]),
            "percent_marker": _cell_proof(table=table, cell=following[0]),
            "scope_interpretation": "NO_DIMENSION_END_DATE_CONTEXT_AND_EXPLICIT_NONPERFORMING_LOAN_RATIO_LABELS"}, None


def _country_detail_witness(*, disposition, index, structure, selected):
    dimensions = disposition["context"]["dimensions"]
    if len(dimensions) != 1:
        return None
    member = next(iter(dimensions.values()))
    if ":" not in member:
        return None
    prefix, code = member.split(":", 1)
    namespaces = index.namespaces.get(prefix.casefold(), set())
    if (re.fullmatch(r"[A-Z]{2}", code) is None or len(namespaces) != 1
            or re.fullmatch(r"http://xbrl\.sec\.gov/country/[0-9]{4}", next(iter(namespaces))) is None):
        return None
    position = index.fact_positions[disposition["native_locator"]["ordinal"]]
    blocks = [block for block in structure["blocks"] if not block["inside_table"]
              and block["start_byte"] <= position < block["end_byte"]]
    if len(blocks) != 1 or re.match(r"^\([0-9]+\)\s*Total revenues for the .+? were approximately",
                                   " ".join(blocks[0]["visible_text"].split()), re.I) is None:
        return None
    links = []
    for item in selected:
        label = item["source_witness"]["geography_label"]
        markers = set(re.findall(r"\(([a-z]|[0-9]{1,2})\)", label["text"], re.I))
        notes, missing = _linked_notes(structure=structure,
            table_order=int(label["table_id"].split("_")[1]) - 1, markers={m.casefold() for m in markers})
        if not missing and blocks[0] in notes:
            links.append(label)
    if not links:
        return None
    return {"country_taxonomy_namespace": next(iter(namespaces)), "country_member": member,
            "native_fact_start_byte": position, "original_country_detail_footnote": blocks[0],
            "referencing_international_total_labels": links,
            "interpretation": "EXPLICIT_SINGLE_COUNTRY_DETAIL_OF_DISCLOSED_INTERNATIONAL_TOTAL"}


def inspect_inline_financial_claims(
    *, repo_root: Path, source_bytes: bytes, source_reference: dict, source_set_manifest: dict,
    expected_cik: str, target_period: dict, metric_id: str,
    inventory_source_reference=None, inventory_bytes=None,
) -> dict:
    """Use native XBRL with physical source witnesses for A13 and A09 routing."""
    if metric_id not in {"A09", "A13"}:
        raise FinancialStructuredError("STRUCTURED_FINANCIAL_METRIC_UNSUPPORTED")
    if (type(source_bytes) is not bytes or not source_bytes
            or len(source_bytes) > RESOURCE_LIMITS.max_html_bytes
            or type(source_reference) is not dict
            or source_reference.get("raw_asset_id") != "sha256:" + sha256_bytes(content=source_bytes)):
        raise FinancialStructuredError("SOURCE_BYTES_DIFFER")
    if source_reference["source_url"] != accession_document_url(cik=int(expected_cik),
            accession=source_reference["accession"], document_name=source_reference["document_name"]):
        raise FinancialStructuredError("SOURCE_ENTITY_ACCESSION_URL_DIFFERS")
    source_scope = _source_set(source_reference=source_reference, source_set_manifest=source_set_manifest,
        inventory_source_reference=inventory_source_reference, inventory_bytes=inventory_bytes)
    period = annual_period(raw=source_bytes, cik=expected_cik,
                           filing={"form": "10-K", "reportDate": target_period["period_end"]})
    if period != target_period:
        raise FinancialStructuredError("SOURCE_FISCAL_PERIOD_DIFFERS")
    parsed = parse_accession_xbrl_source(raw_bytes=source_bytes)
    tasks = [task for task in inspect_r4_task_catalog(repo_root=repo_root)["contracts"] if task["metric_ids"] == [metric_id]]
    if len(tasks) != 1:
        raise FinancialStructuredError("TASK_NOT_UNIQUE")
    task = tasks[0]
    expected_scope = {"geography_scope": "international"} if metric_id == "A13" else {"loan_population": "firmwide"}
    if task["required_claims"] != expected_scope:
        raise FinancialStructuredError("STRUCTURED_FINANCIAL_SCOPE_UNSUPPORTED")
    index = _InlineTableIndex(source_bytes)
    index.feed(source_bytes.decode("utf-8"))
    index.close()
    raw_dispositions = []
    if metric_id == "A13":
        names = ["us-gaap:Revenues", "us-gaap:RevenuesNetOfInterestExpense"]
    else:
        # This inventory is a discovery lead. No custom fact name alone is
        # granted firmwide NPL semantics or forced into the fallback route.
        names = set()
        for fact in parsed.facts:
            if re.search(r"nonaccrual|nonperform", fact["qualified_name"], re.I) is None:
                continue
            context = parsed.contexts[fact["context_ref"]]
            reason = "ELIGIBLE_NATIVE_RATIO_CONTEXT"
            if str(int(context["entity_identifier"])) != str(int(expected_cik)):
                reason = "DIFFERENT_SOURCE_ENTITY"
            elif context["period_start"] != period["period_end"] or context["period_end"] != period["period_end"]:
                reason = "NOT_TARGET_END_DATE_INSTANT"
            elif context["dimensions"] or context["typed_dimension_count"]:
                reason = "NOT_FIRMWIDE_CONTEXT"
            elif (index.unit(fact["unit_ref"]) or {}).get("canonical_unit") != "ratio":
                reason = "NOT_A_RATIO_UNIT"
            else:
                names.add(fact["qualified_name"])
            raw_dispositions.append({"native_fact_ordinal": fact["ordinal"], "qualified_name": fact["qualified_name"],
                "context": {**context, "dimensions": dict(context["dimensions"])},
                "raw_value": fact["text"], "unit_ref": fact["unit_ref"], "disposition": reason})
        names = sorted(names)
    claims = adapt_accession_xbrl_from_parsed(parsed_source=parsed, raw_bytes=source_bytes,
        source_reference=source_reference, source_set_manifest=source_set_manifest, fact_names=names) if names else []
    facts = {fact["ordinal"]: fact for fact in parsed.facts}
    locators = _fact_cells(index, parsed, {claim["locator"]["ordinal"] for claim in claims})
    structure = index_source_structure(source_bytes=source_bytes)
    selected, dispositions, implementation_gaps, source_conflicts = [], [], [], []
    for claim in claims:
        context = claim["attributes"]["context"]
        reason = None
        if str(int(context["entity_identifier"])) != str(int(expected_cik)):
            reason = "DIFFERENT_SOURCE_ENTITY"
        elif context["period_end"] != period["period_end"]:
            reason = "DIFFERENT_PERIOD_END"
        elif context["typed_dimension_count"]:
            reason = "TYPED_DIMENSION_NOT_APPROVED"
        elif metric_id == "A13" and context["period_start"] != period["period_start"]:
            reason = "DIFFERENT_FULL_FISCAL_DURATION"
        elif metric_id == "A13" and (len(context["dimensions"]) != 1 or next(iter(context["dimensions"])) not in {"srt:StatementGeographicalAxis", "us-gaap:GeographicDistributionAxis"}):
            reason = "NOT_SOLE_GEOGRAPHY_CONTEXT"
        elif metric_id == "A09" and context["period_start"] != period["period_end"]:
            reason = "NOT_TARGET_END_DATE_INSTANT"
        elif metric_id == "A09" and context["dimensions"]:
            reason = "NOT_FIRMWIDE_CONTEXT"
        elif (index.unit(claim["unit"]) or {}).get("canonical_unit") != ("USD" if metric_id == "A13" else "ratio"):
            reason = "DIFFERENT_UNIT"
        witness = None
        ordinal = claim["locator"]["ordinal"]
        if reason is None and ordinal not in locators:
            reason = "NATIVE_FACT_NOT_BOUND_TO_ORIGINAL_TABLE_CELL"
            implementation_gaps.append(reason)
        if reason is None and metric_id == "A13":
            table, cell = locators[ordinal]
            witness, reason = _a13_witness(claim=claim, fact=facts[ordinal], table=table, cell=cell, task=task, structure=structure)
            if reason == "SOURCE_REPORTING_DECLARATION_CONFLICT":
                source_conflicts.append(witness)
            elif reason and reason != "NOT_DIRECT_DISCLOSED_INTERNATIONAL_TOTAL_LABEL":
                implementation_gaps.append(reason)
        elif reason is None:
            table, cell = locators[ordinal]
            witness, reason = _a09_witness(claim=claim, fact=facts[ordinal], table=table, cell=cell)
            if reason:
                implementation_gaps.append(reason)
        if reason is None:
            witness["native_unit_definition"] = index.unit(claim["unit"])
            selected.append({"claim": claim, "source_witness": witness})
            reason = "SELECTED_NATIVE_SOURCE_WITNESSED_DIRECT_TOTAL"
        dispositions.append({"verified_claim_id": claim["verified_claim_id"], "native_locator": claim["locator"],
                             "context": context, "value": claim["value"], "unit": claim["unit"], "disposition": reason})
    if metric_id == "A13":
        for disposition in dispositions:
            if disposition["disposition"] == "NATIVE_FACT_NOT_BOUND_TO_ORIGINAL_TABLE_CELL":
                witness = _country_detail_witness(disposition=disposition, index=index, structure=structure, selected=selected)
                if witness is not None:
                    disposition["disposition"] = "COUNTRY_DETAIL_NOT_DIRECT_INTERNATIONAL_TOTAL"
                    disposition["source_witness"] = witness
        gap_codes = set(implementation_gaps)
        implementation_gaps = [d["disposition"] for d in dispositions if d["disposition"] in gap_codes]
    values = {(item["claim"]["value"], item["source_witness"]["native_unit_definition"]["canonical_unit"]) for item in selected}
    if source_conflicts:
        outcome = "STRUCTURED_SOURCE_CONFLICT"
    elif implementation_gaps:
        outcome = "STRUCTURED_IMPLEMENTATION_GAP"
    elif len(values) == 1:
        outcome = "STRUCTURED_PRIMARY_RESOLVED"
    elif claims or raw_dispositions:
        outcome = "STRUCTURED_SOURCE_AMBIGUOUS"
    else:
        outcome = "STRUCTURED_SOURCE_UNAVAILABLE"
    body = {"record_type": "FINANCIAL_NATIVE_STRUCTURED_COMPONENT", "schema_version": 1,
        "metric_id": metric_id, "task_contract_hash": content_hash(value=task),
        "source_reference": source_reference, "source_set_manifest": source_set_manifest,
        "source_set_scope": source_scope, "target_period": target_period,
        "parsed_source_id": parsed.parsed_source_id, "source_sha256": parsed.source_sha256,
        "native_claims_count": len(claims), "native_claims_hash": content_hash(value=claims),
        "native_raw_fact_dispositions": raw_dispositions,
        "selected": selected, "claim_dispositions": dispositions,
        "outcome": outcome, "value": next(iter(values))[0] if outcome == "STRUCTURED_PRIMARY_RESOLVED" else None,
        "implementation_gaps": sorted(set(implementation_gaps)), "regional_sum_used": False,
        "source_conflicts": source_conflicts,
        "fallback_plan_allowed_by_route": outcome == "STRUCTURED_SOURCE_AMBIGUOUS",
        "fallback_provider_authorized": False, "native_run_status": "NOT_CREATED",
        "qualification_credit": "NONE_COMPONENT_ONLY", "publication_credit": "NONE",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}


def inspect_ordinary_a09_source_fact(
    *, repo_root: Path, source_bytes: bytes, source_reference: dict,
    source_set_manifest: dict, expected_cik: str, target_period: dict,
    inventory_source_reference: dict = None, inventory_bytes: bytes = None,
) -> dict:
    """Recompute the complete native route before any HTML interpretation.

    The caller cannot supply an ambiguity flag or cached structured receipt.
    A resolved native primary remains primary; implementation gaps and missing
    source sets cannot be relabelled as the approved ambiguity fallback.
    """
    from .financial_relationships import inspect_nonaccrual_loan_ratio
    primary = inspect_inline_financial_claims(repo_root=repo_root, metric_id="A09",
        source_bytes=source_bytes, source_reference=source_reference,
        source_set_manifest=source_set_manifest, expected_cik=expected_cik, target_period=target_period,
        inventory_source_reference=inventory_source_reference, inventory_bytes=inventory_bytes)
    fallback = None
    if (primary["outcome"] == "STRUCTURED_SOURCE_AMBIGUOUS"
            and primary["source_set_scope"] == "NATIVE_SAVED_SUBMISSIONS_COMPLETE_SOURCE_SET"):
        fallback = inspect_nonaccrual_loan_ratio(repo_root=repo_root, source_bytes=source_bytes,
            expected_source_sha256=sha256_bytes(content=source_bytes), expected_cik=expected_cik,
            target_period=target_period)
    if primary["outcome"] == "STRUCTURED_PRIMARY_RESOLVED":
        outcome, value = "STRUCTURED_PRIMARY_RESOLVED", primary["value"]
    elif fallback and fallback["status"] == "SINGLE_SOURCE_SEMANTIC_FACT":
        outcome, value = "HTML_FALLBACK_SOURCE_SEMANTIC_FACT", fallback["value"]
    else:
        outcome, value = "UNRESOLVED", None
    body = {"record_type": "ORDINARY_A09_SOURCE_FACT_COMPONENT", "schema_version": 1,
        "source_sha256": sha256_bytes(content=source_bytes), "target_filing_period": target_period,
        "structured_primary": primary, "html_fallback": fallback,
        "outcome": outcome, "value": value, "unit": "ratio",
        "measurement_time": {"kind": "INSTANT", "as_of_date": target_period["period_end"]},
        "ordinary_result_rule_status": "EXPLICIT_DETERMINISTIC_FALLBACK_RULE_REQUIRED" if fallback else "NATIVE_PRIMARY_RULE",
        "native_run_status": "NOT_CREATED", "qualification_credit": "NONE_COMPONENT_ONLY",
        "publication_credit": "NONE", "calls": {"provider": 0, "paid": 0, "sec": 0}}
    return {**body, "component_id": content_hash(value=body)}
