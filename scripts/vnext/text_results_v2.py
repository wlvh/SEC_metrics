"""Explicit C02/D02 source excerpts on the existing reviewed TEXT_V1 records.

Annual coordinates group disclosures. Governance source filing dates remain
separate from the unknown board measurement date. These methods do not create
provider attempts, review decisions, source acquisition credit or publications.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from .records import validate_record
from .text_business_candidates import (
    governance_source_document, board_composition_candidates, legal_risk_candidates,
    reported_legal_fact_candidates,
)
from .text_coverage import build_text_document
from .text_results import text_policy as _text_policy
from .text_results import text_claim_from_block, build_text_result_and_trace
from .governance_signals import _FactAttributes, _qname, _source_value


METHODS = {"C02": "BOARD_DISCLOSURE_EXCERPTS_V1", "D02": "LEGAL_DISCLOSURE_EXCERPTS_V1"}
SCOPES = {
    "C02": {"entity_scope": "registrant", "disclosure_basis": "source_filing_text",
            "period_basis": "annual_grouping_only", "board_as_of": "not_inferred"},
    "D02": {"entity_scope": "registrant", "disclosure_basis": "source_filing_text",
            "period_basis": "annual_filing_disclosures", "liability_measurement": "not_inferred"},
}
REQUIRED_SECTIONS = {"C02": ["GOVERNANCE_DISCLOSURES"], "D02": ["ITEM_3", "ITEM_8", "REFERENCED_NOTES"]}
SOURCE_ROLES = {"C02": ["target_primary", "governance_proxy"], "D02": ["target_primary"]}
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_CANDIDATE_TYPE = "DETERMINISTIC_TEXT_CANDIDATE"
_CAPABILITY_POLICY = strict_json_file(path=Path(__file__).resolve().parents[2] / "catalog/r6/text_results_v2_policy.json")
_CAPABILITY_POLICY_HASH = content_hash(value=_CAPABILITY_POLICY)
_ACCRUAL_CANDIDATE = re.compile(_CAPABILITY_POLICY["current_accrual_candidate_concept_pattern"], re.I)
_UNACCRUED = re.compile(_CAPABILITY_POLICY["excluded_unaccrued_concept_pattern"], re.I)
_XBRLI = "http://www.xbrl.org/2003/instance"
_XBRLDI = "http://xbrl.org/2006/xbrldi"


class TextResultV2Error(ValueError):
    """A source, period, excerpt set or effective review is not proven."""


def _need(condition, reason):
    if not condition:
        raise TextResultV2Error(reason)


def _iso(value):
    _need(type(value) is str, "TEXT_V2_DATE_REQUIRED")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise TextResultV2Error("TEXT_V2_DATE_INVALID") from error
    _need(parsed.isoformat() == value, "TEXT_V2_DATE_INVALID")
    return parsed


class _ReportedFactMetadata(_FactAttributes):
    """Supplement the native fact stream with namespace-proven context fields."""

    def __init__(self):
        super().__init__()
        self.context_proofs = {}
        self.context_active = None
        self.context_field = None

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        namespaces = self.stack[-1][1] if self.stack else {}
        uri, local = _qname(tag, namespaces)
        attrs = dict(attrs)
        if uri == _XBRLI and local == "context":
            key = attrs.get("id")
            _need(key and key not in self.context_proofs and self.context_active is None,
                  "D02_FACT_CONTEXT_DUPLICATE_OR_NESTED")
            self.context_active = {"context_ref":key,"identifiers":[],"period_fields":[],"dimensions":[],"typed_dimension_count":0}
        elif self.context_active is not None:
            if uri == _XBRLI and local in {"identifier","instant","startdate","enddate"}:
                _need(self.context_field is None,"D02_FACT_CONTEXT_FIELDS_NESTED")
                self.context_field = {"tag":tag,"kind":local,"parts":[],"scheme":attrs.get("scheme","")}
            elif uri == _XBRLDI and local == "explicitmember":
                _need(self.context_field is None,"D02_FACT_CONTEXT_FIELDS_NESTED")
                self.context_field = {"tag":tag,"kind":local,"parts":[],"dimension_raw":attrs.get("dimension",""),
                                      "namespaces":dict(namespaces)}
            elif uri == _XBRLDI and local == "typedmember":
                self.context_active["typed_dimension_count"] += 1

    def handle_data(self, data):
        super().handle_data(data)
        if self.context_field is not None:
            _need(sum(len(x) for x in self.context_field["parts"]) + len(data) <= 8192,
                  "D02_FACT_CONTEXT_FIELD_LIMIT")
            self.context_field["parts"].append(data)

    def handle_endtag(self, tag):
        namespaces = self.stack[-1][1] if self.stack else {}
        uri, local = _qname(tag, namespaces)
        field = self.context_field
        if field is not None and field["tag"] == tag:
            value = "".join(field["parts"]).strip()
            if field["kind"] == "identifier":
                self.context_active["identifiers"].append({"value":value,"scheme":field["scheme"]})
            elif field["kind"] == "explicitmember":
                self.context_active["dimensions"].append({"dimension_raw":field["dimension_raw"],"member_raw":value,
                    "dimension_qname":list(_qname(field["dimension_raw"],field["namespaces"])),
                    "member_qname":list(_qname(value,field["namespaces"]))})
            else:
                self.context_active["period_fields"].append({"kind":field["kind"],"value":value})
            self.context_field = None
        if uri == _XBRLI and local == "context" and self.context_active is not None:
            self.context_proofs[self.context_active["context_ref"]] = self.context_active
            self.context_active = None
        super().handle_endtag(tag)


def _verified_context(*, native, metadata):
    key = native["context_ref"]
    _need(key in metadata.context_proofs,"D02_FACT_CONTEXT_NAMESPACE_NOT_PROVEN")
    context = metadata.context_proofs[key]
    _need(len(context["identifiers"]) == 1,"D02_FACT_ENTITY_NOT_UNIQUE")
    entity = context["identifiers"][0]
    _need(entity["scheme"] in _CAPABILITY_POLICY["cik_identifier_schemes"]
          and entity["value"].isdigit() and entity["value"] == native["entity_identifier"],
          "D02_FACT_ENTITY_SCHEME_NOT_PROVEN")
    fields = context["period_fields"]
    if len(fields) == 1 and fields[0]["kind"] == "instant":
        start = end = fields[0]["value"]
    else:
        _need(len(fields) == 2 and {f["kind"] for f in fields} == {"startdate","enddate"},
              "D02_FACT_PERIOD_NOT_PROVEN")
        start = next(f["value"] for f in fields if f["kind"] == "startdate")
        end = next(f["value"] for f in fields if f["kind"] == "enddate")
    _need(_iso(start) <= _iso(end) and (start,end) == (native["period_start"],native["period_end"]),
          "D02_FACT_PERIOD_CONFLICT")
    dims = context["dimensions"]
    _need(not context["typed_dimension_count"] and not native["typed_dimension_count"],
          "D02_FACT_TYPED_CONTEXT_NOT_IMPLEMENTED")
    _need(all(all(q) for d in dims for q in (d["dimension_qname"],d["member_qname"]))
          and len({tuple(d["dimension_qname"]) for d in dims}) == len(dims)
          and {d["dimension_raw"]:d["member_raw"] for d in dims} == native["dimensions"],
          "D02_FACT_DIMENSION_NAMESPACE_OR_IDENTITY_NOT_PROVEN")
    return context


def _verified_reported_facts(*, raw, candidates, cik):
    """Record each source fact independently, without creating an aggregate."""
    from .deterministic_router import parse_accession_xbrl_source
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata(); metadata.feed(raw.decode("utf-8-sig")); metadata.close()
    _need(metadata.ordinal == len(parsed.facts),"D02_FACT_ATTRIBUTE_STREAM_CONFLICT")
    by_ordinal = {f["ordinal"]:f for f in parsed.facts}
    rows = []
    for candidate in candidates["candidates"]:
        row = {k:v for k,v in candidate.items() if k not in {"source_numeric_value","numeric_parse_issue","metric_role_interpretation_required"}}
        fact = by_ordinal[row["locator"]["ordinal"]]
        meta = metadata.facts[fact["ordinal"]]
        row.update(value_normalized=None,verified_monetary_value=False,verification_status="SOURCE_LITERAL_ONLY",
                   verification_reason_codes=[],aggregate_or_target_period_value_asserted=False,
                   original_numeric_attributes={k:v for k,v in meta["attrs"].items()
                       if k in {"unitref","scale","sign","format"} or k.endswith(":nil")})
        try:
            _need(meta["concept"] == (row["concept_namespace"],row["concept_local_name"]),"D02_FACT_CONCEPT_NAMESPACE_CHANGED")
            tag_uri, tag_local = _qname(meta["tag"],meta["namespaces"])
            _need(tag_uri in _CAPABILITY_POLICY["numeric_inline_namespaces"] and tag_local == "nonfraction",
                  "D02_FACT_NUMERIC_TAG_NOT_PROVEN")
            unit = row["declared_unit"]
            _need(unit is not None and not unit["divided"] and len(unit["measures"]) == 1
                  and unit["measures"][0][0] == _CAPABILITY_POLICY["monetary_unit_namespace"]
                  and re.fullmatch(r"[A-Z]{3}",unit["measures"][0][1]),"D02_FACT_MONETARY_UNIT_NOT_PROVEN")
            _need(unit["measures"][0][1] in _CAPABILITY_POLICY["supported_currency_codes"],
                  "D02_FACT_CURRENCY_NOT_SUPPORTED")
            row["verified_context"] = _verified_context(native=row["context"],metadata=metadata)
            normalized = _source_value(fact,meta)
            # The inherited normalizer removes grouping characters. Admit only
            # a declared, bounded lexical subset before publishing its amount.
            transform = meta["attrs"].get("format", "")
            local = _qname(transform,meta["namespaces"])[1] if transform else ""
            if local not in {"fixed-zero", "numdash"}:
                pattern = (_CAPABILITY_POLICY["dot_decimal_supported_lexical_pattern"] if transform
                           else _CAPABILITY_POLICY["unformatted_decimal_lexical_pattern"])
                _need(re.fullmatch(pattern,str(fact["text"]).strip()) is not None,
                      "D02_FACT_NUMERIC_LEXICAL_FORM_NOT_SUPPORTED")
            row.update(value_normalized=normalized,verified_monetary_value=True,
                       verification_status="VERIFIED_AS_REPORTED_MONETARY_FACT",
                       context_entity_relation="SAME_REGISTRANT" if int(row["context"]["entity_identifier"]) == int(cik) else "OTHER_ENTITY_AS_REPORTED",
                       reported_currency=unit["measures"][0][1])
        except ValueError as error:
            reason = str(error).replace("C03_", "D02_FACT_")
            if reason == "D02_FACT_NIL_TARGET_COMPENSATION":
                reason = "D02_FACT_NIL_SOURCE_VALUE"
            row["verification_reason_codes"] = [reason]
        row["fact_evidence_id"] = content_hash(value=row)
        rows.append(row)
    body = {"record_type":"REPORTED_LEGAL_FACT_EVIDENCE","source_reference_id":candidates["source_reference_id"],
            "candidate_inventory_id":candidates["proposal_id"],"facts":rows,"policy_hash":_CAPABILITY_POLICY_HASH,
            "complete_legal_liability_asserted":False,"source_reported_periods_preserved":True}
    return {**body,"fact_inventory_id":content_hash(value=body)}


def _target(metric_id, target):
    _need(metric_id in METHODS and type(target) is dict
          and set(target) == {"company_id", "entity", "accession", "period_start", "period_end", "scope", "scope_key"},
          "TEXT_V2_TARGET_FIELDS_INVALID")
    _need(target["scope"] == SCOPES[metric_id] and target["scope_key"] == content_hash(value=target["scope"]),
          "TEXT_V2_DISCLOSURE_SCOPE_CHANGED")
    _need(_iso(target["period_start"]) <= _iso(target["period_end"]), "TEXT_V2_TARGET_PERIOD_REVERSED")
    _need(type(target["company_id"]) is str and target["company_id"]
          and type(target["entity"]) is str and target["entity"].isdigit()
          and re.fullmatch(r"\d{10}-\d{2}-\d{6}", target["accession"]), "TEXT_V2_TARGET_IDENTITY_INVALID")


def text_policy(compiled_spec):
    policy = _text_policy(compiled_spec)
    semantic = compiled_spec["compiled"]
    metric_id = semantic["metric_id"]
    _need(metric_id in METHODS and semantic["quality_rule"].get("deterministic_text_method") == METHODS[metric_id],
          "TEXT_V2_SPEC_METHOD_REQUIRED")
    _need(semantic["required_claims"] == SCOPES[metric_id]
          and policy["required_sections"] == REQUIRED_SECTIONS[metric_id]
          and policy["allowed_source_roles"] == SOURCE_ROLES[metric_id], "TEXT_V2_SPEC_SCOPE_CHANGED")
    return policy


def _annual_document(*, source, blob, raw, target, filing):
    from .deterministic_router import parse_accession_xbrl_source
    _need(filing["form"] == "10-K" and filing["accessionNumber"] == target["accession"]
          and filing["reportDate"] == target["period_end"], "TEXT_V2_ORDINARY_ANNUAL_ANCHOR_REQUIRED")
    document = build_text_document(raw_bytes=raw, raw_blob=blob, source_reference=source,
        expected_company_id=target["company_id"], expected_cik=target["entity"], expected_period_end=target["period_end"])
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    periods = {(parsed.contexts[f["context_ref"]]["period_start"], parsed.contexts[f["context_ref"]]["period_end"])
               for f in parsed.facts if f["qualified_name"].split(":")[-1].casefold() == "documentperiodenddate"}
    _need(periods == {(target["period_start"], target["period_end"])}, "TEXT_V2_ANNUAL_PERIOD_CHANGED")
    _need(document["source_state"] == "COMPLETE_LOCAL_DOCUMENT", "TEXT_V2_ANNUAL_DOCUMENT_INCOMPLETE")
    return document


def prepare_business_text_sources(*, metric_id, target, source_references, raw_blobs, raw_bytes_by_id, source_filings):
    """Rebuild an ordinary annual anchor and all supported disclosure excerpts.

    Input discovery and request-proof admission belong to the existing normal
    input boundary. This function verifies that the supplied original set has
    the exact identity and period expected by that trusted boundary.
    """
    _target(metric_id, target)
    sources = [validate_record(record=s) for s in source_references]
    ids = [s["source_reference_id"] for s in sources]
    _need(len(ids) == len(set(ids)) and set(source_filings) == set(ids)
          and len(sources) == (2 if metric_id == "C02" else 1), "TEXT_V2_SOURCE_SET_INVALID")
    documents, coverages, proposals, source_data = {}, {}, {}, {}
    for source in sources:
        sid = source["source_reference_id"]; filing = source_filings[sid]
        _need(source["record_type"] == "SOURCE_REFERENCE" and source["source_role"] in SOURCE_ROLES[metric_id]
              and source["company_id"] == target["company_id"], "TEXT_V2_SOURCE_COMPANY_OR_ROLE_CHANGED")
        _need(type(filing) is dict and {"form", "accessionNumber", "primaryDocument", "filingDate", "reportDate"} <= set(filing)
              and source["accession"] == filing["accessionNumber"]
              and source["document_name"] == filing["primaryDocument"], "TEXT_V2_SOURCE_FILING_CHANGED")
        expected_role = "governance_proxy" if filing["form"] == "DEF 14A" else "target_primary"
        _need(source["source_role"] == expected_role, "TEXT_V2_SOURCE_FORM_ROLE_CHANGED")
        _iso(filing["filingDate"])
        raw_id = source["raw_asset_id"]
        _need(raw_id in raw_blobs and raw_id in raw_bytes_by_id, "TEXT_V2_ORIGINAL_SOURCE_MISSING")
        blob, raw = raw_blobs[raw_id], raw_bytes_by_id[raw_id]
        source_data[sid] = (source, filing, blob, raw)
    annual_ids = [sid for sid in ids if source_filings[sid]["form"] == "10-K"]
    _need(len(annual_ids) == 1, "TEXT_V2_UNIQUE_ANNUAL_ANCHOR_REQUIRED")
    annual_id = annual_ids[0]
    source, filing, blob, raw = source_data[annual_id]
    annual = _annual_document(source=source, blob=blob, raw=raw, target=target, filing=filing)
    documents[annual_id] = annual
    anchor = {"source_reference_id": annual_id, "document_id": annual["text_document_id"],
              "source_filing": dict(filing), "coordinate_period_start": target["period_start"],
              "coordinate_period_end": target["period_end"], "ranges": [],
              "scope": "ORDINARY_ANNUAL_IDENTITY_ANCHOR_ONLY"}
    anchor["coverage_hash"] = content_hash(value=anchor)
    coverages[annual_id] = anchor
    if metric_id == "C02":
        governance_id = next(sid for sid in ids if sid != annual_id)
        source, filing, blob, raw = source_data[governance_id]
        _need(filing["form"] in {"DEF 14A", "10-K/A"}, "TEXT_V2_GOVERNANCE_SOURCE_FORM_REQUIRED")
        _need(_iso(filing["filingDate"]) >= _iso(target["period_end"]), "TEXT_V2_GOVERNANCE_SOURCE_PRECEDES_ANNUAL_END")
        if filing["form"] == "10-K/A":
            _need(filing["reportDate"] == target["period_end"], "TEXT_V2_GOVERNANCE_AMENDMENT_PERIOD_CHANGED")
            # The source metadata alone cannot retarget a different year.
            # This reader checks the real DEI period; amendment completeness
            # is separately assessed by the full governance document parser.
            build_text_document(raw_bytes=raw, raw_blob=blob, source_reference=source,
                expected_company_id=target["company_id"], expected_cik=target["entity"],
                expected_period_end=target["period_end"])
        doc = governance_source_document(raw_bytes=raw, raw_blob=blob, source_reference=source,
            company_id=target["company_id"], cik=target["entity"], filing=filing)
        _need(doc["source_state"] == "COMPLETE_LOCAL_DOCUMENT", "TEXT_V2_GOVERNANCE_DOCUMENT_INCOMPLETE")
        proposal = board_composition_candidates(document=doc)
        _need(proposal["candidates"], "TEXT_V2_GOVERNANCE_STATEMENT_STRUCTURE_UNSUPPORTED")
        documents[governance_id] = doc; proposals[governance_id] = proposal
        coverage = {"source_reference_id": governance_id, "document_id": doc["text_document_id"],
                    "source_filing": dict(filing), "source_disclosure_date": filing["filingDate"],
                    "board_measurement_as_of": None, "board_count_asserted": False,
                    "coordinate_use": "ANNUAL_GROUPING_ONLY_NOT_BOARD_OR_COMPENSATION_MEASUREMENT",
                    "annual_anchor_coverage_hash": anchor["coverage_hash"],
                    "ranges": [{"section_id": "GOVERNANCE_DISCLOSURES", "start_block": 0,
                                "end_block_exclusive": len(doc["blocks"])}],
                    "scope": "COMPLETE_LOCAL_GOVERNANCE_DOCUMENT_SUPPORTED_STATEMENTS"}
        coverage["coverage_hash"] = content_hash(value=coverage); coverages[governance_id] = coverage
    else:
        proposal = legal_risk_candidates(document=annual)
        _need(proposal["coverage_status"] == "LOCAL_REQUESTED_RANGES_SCANNED",
              "TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE")
        _need(proposal["D02"]["candidates"], "TEXT_V2_LEGAL_DISCLOSURE_TEXT_UNSUPPORTED")
        fact_candidates = reported_legal_fact_candidates(raw_bytes=raw, raw_blob=blob, source_reference=source,
            company_id=target["company_id"], cik=target["entity"], filing=filing)
        facts = _verified_reported_facts(raw=raw,candidates=fact_candidates,cik=target["entity"])
        current_candidates = []
        for fact in facts["facts"]:
            context = fact["context"]
            entity = context["entity_identifier"]
            if ("verified_context" in fact and type(entity) is str and entity.isdigit() and int(entity) == int(target["entity"])
                    and _ACCRUAL_CANDIDATE.search(fact["concept_local_name"])
                    and not _UNACCRUED.search(fact["concept_local_name"])
                    and _iso(target["period_start"]) <= _iso(context["period_end"]) <= _iso(target["period_end"])):
                current_candidates.append(fact)
        proposals[annual_id] = proposal
        coverage = {"source_reference_id": annual_id, "document_id": annual["text_document_id"],
                    "source_filing": dict(filing), "source_disclosure_date": filing["filingDate"],
                    "ranges": proposal["checked_ranges"], "note_references": proposal["note_references"],
                    "source_fact_inventory": facts,
                    "current_accrual_source_fact_ids": [f["fact_evidence_id"] for f in current_candidates],
                    "capability_policy_hash": _CAPABILITY_POLICY_HASH,
                    "fact_periods_and_dimensions_preserved": True, "current_liability_or_accrual_asserted": False,
                    "scope": "LEGAL_DISCLOSURE_SOURCE_TEXT_NOT_TOTAL_CASE_OR_LIABILITY_MEASUREMENT"}
        coverage["coverage_hash"] = content_hash(value=coverage); coverages[annual_id] = coverage
    return {"metric_id": metric_id, "documents": documents, "coverages": coverages,
            "proposals": proposals, "source_references": sources,
            "capability_status": "SOURCE_TEXT_READY", "capability_gaps": []}


def validate_deterministic_candidate_shape(*, candidate):
    """Additional method validation called by the shared native record router."""
    _need(candidate["record_type"] == _CANDIDATE_TYPE and candidate["method"] in METHODS.values()
          and candidate["status"] == "CANDIDATE" and not candidate["derived_asset_ids"]
          and not candidate["competing_candidates"] and not candidate["unresolved_competing_claims"],
          "TEXT_V2_CANDIDATE_PROTOCOL_INVALID")
    for field in ("spec_semantic_hash", "spec_closure_hash", "source_set_hash"):
        _need(type(candidate[field]) is str and _HASH.fullmatch(candidate[field]), "TEXT_V2_CANDIDATE_HASH_INVALID")
    ids = candidate["source_reference_ids"]
    _need(ids and all(type(s) is str and _HASH.fullmatch(s) for s in ids)
          and len(ids) == len(set(ids)) and set(candidate["document_bindings"]) == set(ids),
          "TEXT_V2_CANDIDATE_SOURCE_BINDING_INVALID")
    for binding in candidate["document_bindings"].values():
        _need(type(binding) is dict and set(binding) == {"document_id", "coverage_hash", "proposal_id"}
              and all(type(v) is str and _HASH.fullmatch(v) for v in binding.values()), "TEXT_V2_DOCUMENT_BINDING_INVALID")
    metric_id = next(k for k, v in METHODS.items() if v == candidate["method"])
    _target(metric_id, candidate["calculation_target"])


def _derive_candidate(*, compiled_spec, target, prepared):
    policy = text_policy(compiled_spec); metric_id = compiled_spec["compiled"]["metric_id"]
    _need(prepared["capability_status"] == "SOURCE_TEXT_READY", "TEXT_V2_SOURCE_TEXT_NOT_READY")
    selected, bindings = {}, {}
    for source in prepared["source_references"]:
        sid = source["source_reference_id"]; document = prepared["documents"][sid]
        proposal = prepared["proposals"].get(sid)
        coverage = prepared["coverages"][sid]
        bindings[sid] = {"document_id": document["text_document_id"], "coverage_hash": coverage["coverage_hash"],
                         "proposal_id": proposal["proposal_id"] if proposal else coverage["coverage_hash"]}
        excerpts = [] if proposal is None else proposal["candidates"] if metric_id == "C02" else proposal["D02"]["candidates"]
        for excerpt in excerpts:
            order = len(selected)
            selected["excerpt_" + str(order)] = text_claim_from_block(document=document,
                section_id=excerpt["section_id"], block_index=excerpt["block_index"], order=order, extent="FULL_BLOCK")
    _need(1 <= len(selected) <= policy["max_items"], "TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND")
    _need(sum(len(v["text"]) for v in selected.values()) + len(selected) - 1 <= policy["max_text_chars"],
          "TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_TEXT_BOUND")
    body = {"record_type": _CANDIDATE_TYPE, "method": METHODS[metric_id],
            "spec_semantic_hash": compiled_spec["spec_semantic_hash"], "spec_closure_hash": compiled_spec["spec_closure_hash"],
            "source_set_hash": content_hash(value=prepared["source_references"]), "document_bindings": bindings,
            "calculation_target": dict(target), "disclosure_group": compiled_spec["compiled"]["disclosure_group"],
            "source_reference_ids": [s["source_reference_id"] for s in prepared["source_references"]],
            "derived_asset_ids": [], "selected": selected, "competing_candidates": [], "unresolved_competing_claims": []}
    return validate_record(record={**body, "candidate_hash": content_hash(value=body), "status": "CANDIDATE"})


def create_deterministic_text_candidate(*, compiled_spec, **source_arguments):
    prepared = prepare_business_text_sources(metric_id=compiled_spec["compiled"]["metric_id"], **source_arguments)
    return _derive_candidate(compiled_spec=compiled_spec, target=source_arguments["target"], prepared=prepared)


def build_text_evidence(*, compiled_spec, candidate, **source_arguments):
    """Independently reconstruct the exact complete supported excerpt set."""
    prepared = prepare_business_text_sources(metric_id=compiled_spec["compiled"]["metric_id"], **source_arguments)
    expected = _derive_candidate(compiled_spec=compiled_spec, target=source_arguments["target"], prepared=prepared)
    _need(validate_record(record=candidate) == expected, "TEXT_V2_CANDIDATE_REPLAY_CHANGED")
    checks, normalized, seen = [], {}, set()
    for role, claim in sorted(candidate["selected"].items(), key=lambda pair: pair[1]["order"]):
        sid = claim["source_reference_id"]; doc = prepared["documents"][sid]; index = claim["block_index"]
        _need((sid, index) not in seen, "TEXT_V2_DUPLICATE_EXCERPT"); seen.add((sid, index))
        _need(any(r["section_id"] == claim["section_id"] and r["start_block"] <= index < r["end_block_exclusive"]
                  for r in prepared["coverages"][sid]["ranges"]), "TEXT_V2_EXCERPT_OUTSIDE_SOURCE_RANGE")
        raw = source_arguments["raw_bytes_by_id"][doc["raw_asset_id"]]
        _need(sha256_bytes(content=raw[claim["raw_start_byte"]:claim["raw_end_byte"]]) == claim["raw_span_sha256"],
              "TEXT_V2_RAW_SPAN_REPLAY_CHANGED")
        normalized[role] = claim["text"]
        checks.append({"check": "TEXT_EXACT_EXCERPT:" + role, "status": "PASS", "claim_hash": content_hash(value=claim)})
    target = source_arguments["target"]
    body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS", "normalized_values": normalized,
            "checks": [{"check": "TEXT_V2_SOURCE_COVERAGE_AND_TIME", "status": "PASS",
                        "coverage": list(prepared["coverages"].values())}] + checks,
            "reason_codes": [], "identity_constraints": [], "normalized_scope": dict(target["scope"]),
            "system_approval_eligible": True, "unresolved_scope_dimensions": []}
    return validate_record(record={"record_type": "EVIDENCE_CHECK", "evidence_check_id": content_hash(value=body), **body})


def build_text_review_unit(*, compiled_spec, candidate, evidence_check, source_bindings):
    """Reuse the native review, displaying the source date and measure boundary."""
    from .text_review import render_text_review
    from .review import build_review_unit
    from .render import visible_untrusted_text
    base = render_text_review(compiled_spec=compiled_spec, candidate=candidate,
        evidence_check=evidence_check, source_bindings=source_bindings)
    disclosure_context = {"calculation_target": candidate["calculation_target"],
                          "source_coverages": evidence_check["checks"][0]["coverage"]}
    version = "TEXT_SOURCE_DISCLOSURE_REVIEW_V2"
    context = {"protocol": version, "compiled_spec": compiled_spec, "candidate": candidate,
               "evidence_check": evidence_check, "source_bindings": list(source_bindings),
               "disclosure_context": disclosure_context}
    context_bytes = canonical_json_bytes(value=context)
    lines = [base["rendered_review_bytes"].decode("utf-8"), "", "## Source dates and measurement basis", "",
             "The annual coordinate groups filing disclosures. It does not assign a board measurement date or a current aggregate liability.", ""]
    for coverage in disclosure_context["source_coverages"]:
        filing = coverage["source_filing"]
        summary = {"source_reference_id": coverage["source_reference_id"], "source_form": filing["form"],
                   "filing_date": filing["filingDate"], "filing_report_date_metadata": filing["reportDate"],
                   "scope": coverage["scope"], "board_measurement_as_of": coverage.get("board_measurement_as_of"),
                   "current_liability_or_accrual_asserted": coverage.get("current_liability_or_accrual_asserted", False)}
        lines.append("<pre>" + visible_untrusted_text(value=canonical_json_bytes(value=summary).decode("utf-8")) + "</pre>")
        inventory = coverage.get("source_fact_inventory")
        if inventory is not None:
            lines.extend(["", "### Reported source facts", "",
                "Each fact retains its own source entity, period and dimensions. The values are not added together.", ""])
            for fact in inventory["facts"]:
                shown = {"concept_namespace":fact["concept_namespace"],"concept":fact["concept_local_name"],
                         "value_raw":fact["source_text"],"value_normalized":fact["value_normalized"],
                         "unit":fact["declared_unit"],"context":fact["context"],
                         "verified_context":fact.get("verified_context"),"locator":fact["locator"],
                         "numeric_attributes":fact["original_numeric_attributes"],
                         "verification_status":fact["verification_status"],"reasons":fact["verification_reason_codes"],
                         "context_entity_relation":fact.get("context_entity_relation"),"fact_evidence_id":fact["fact_evidence_id"]}
                lines.append("<pre>" + visible_untrusted_text(value=canonical_json_bytes(value=shown).decode("utf-8")) + "</pre>")
    rendered_bytes = "\n".join(lines).encode("utf-8")
    assets = {"review_context_bytes": context_bytes, "rendered_review_bytes": rendered_bytes,
              "review_context_hash": sha256_bytes(content=context_bytes),
              "rendered_review_hash": sha256_bytes(content=rendered_bytes),
              "review_renderer_semantic_version": version}
    unit = build_review_unit(candidate=candidate, evidence_check=evidence_check,
        source_bindings=source_bindings, compiled_spec=compiled_spec,
        review_context_hash=assets["review_context_hash"], rendered_review_hash=assets["rendered_review_hash"],
        renderer_semantic_version=version)
    return unit, assets


def reviewed_text_observations(*, compiled_spec, target, candidate, evidence_check, review_unit,
                               review_decisions, **source_arguments):
    from .observations import _build_text_observation
    from .review import effective_review_decision
    expected = build_text_evidence(compiled_spec=compiled_spec, target=target, candidate=candidate, **source_arguments)
    _need(validate_record(record=evidence_check) == expected, "TEXT_V2_EVIDENCE_REPLAY_CHANGED")
    unit = validate_record(record=review_unit)
    expected_unit, _ = build_text_review_unit(compiled_spec=compiled_spec, candidate=candidate,
        evidence_check=expected, source_bindings=source_arguments["source_references"])
    _need(unit == expected_unit, "TEXT_V2_REVIEW_BINDING_CHANGED")
    decision = effective_review_decision(review_unit=unit, decisions=review_decisions)
    _need(decision["decision"] == "APPROVE" and decision["reviewer_type"] in {"HUMAN", "SYSTEM"}
          and decision["approved_claims"] == target["scope"], "TEXT_V2_EFFECTIVE_APPROVAL_REQUIRED")
    sources = {s["source_reference_id"]: s for s in source_arguments["source_references"]}
    coverages = {r["source_reference_id"]: r for r in expected["checks"][0]["coverage"]}
    observations = []
    for role, claim in sorted(candidate["selected"].items(), key=lambda pair: pair[1]["order"]):
        source = sources[claim["source_reference_id"]]
        binding = {k: source[k] for k in ("raw_asset_id", "source_reference_id", "accession", "document_name", "source_role")}
        binding["text_binding"] = {"protocol": "TEXT_V1", "spec_closure_hash": compiled_spec["spec_closure_hash"],
            "candidate_hash": candidate["candidate_hash"], "review_unit_hash": unit["review_unit_hash"],
            "coverage_hash": coverages[source["source_reference_id"]]["coverage_hash"],
            **{key: claim[key] for key in ("extent", "document_id", "section_id", "block_index", "raw_start_byte", "raw_end_byte", "raw_span_sha256", "order")}}
        observations.append(_build_text_observation(metric_id=compiled_spec["compiled"]["metric_id"], semantic_role=role,
            company_id=target["company_id"], period_start=target["period_start"], period_end=target["period_end"],
            scope=target["scope"], value=claim["text"], source_binding=binding,
            approval_effect_hash=decision["approval_effect_hash"]))
    return observations


def replay_text_result(*, compiled_spec, target, company_traits, candidate, evidence_check, review_unit,
                       review_decisions, **source_arguments):
    from .calculator import calculate_text_metric
    observations = reviewed_text_observations(compiled_spec=compiled_spec, target=target, candidate=candidate,
        evidence_check=evidence_check, review_unit=review_unit, review_decisions=review_decisions, **source_arguments)
    result, trace = calculate_text_metric(compiled_spec=compiled_spec, target=target,
        company_traits=company_traits, observations=observations)
    return result, trace, observations


def verify_text_result(*, result, trace, observations, **replay_arguments):
    expected_result, expected_trace, expected_observations = replay_text_result(**replay_arguments)
    actual = {o["observation_id"]: o for o in observations}
    expected = {o["observation_id"]: o for o in expected_observations}
    _need(len(actual) == len(observations) and actual == expected and result == expected_result and trace == expected_trace,
          "TEXT_V2_NATIVE_REPLAY_CHANGED")
    return expected_result, expected_trace, expected_observations
