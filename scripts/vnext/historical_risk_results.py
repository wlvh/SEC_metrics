"""D01 on documents whose emphasis includes underline.

``historical_text_emphasis`` builds the document; this is the chain that has to
carry it. Four of the five functions below exist only because the frozen ones
call ``prepare_text_sources`` and each other as module globals, so a successor
cannot reach them without rebinding names inside a frozen module - the same
reason ``historical_text_results`` duplicates its three.

What is NOT duplicated is the part that decides anything about a heading:
``_derive_deterministic_candidate`` takes ``documents`` and ``coverages`` as
arguments, so the frozen one is called unchanged, and with it the frozen
``risk_factor_headings``, ``text_claim_from_block``, both bound checks and the
whole record shape. The selection rule is the frozen route's; only the bytes it
is handed differ.

The duplication is held to the original by
``tests/vnext/test_historical_risk_headings.py``, differentially against the
frozen chain on every readable filing. What it can require is narrower than
"identical", and the narrowing is measured rather than assumed: the document
hash covers every block's emphasis fields, including blocks no heading
selects, so admitting underline moves the document identity in all nine - 3 to
416 additional leading emphases per filing, and none lost anywhere. Everything
derived from that identity moves with it (``document_id``, ``proposal_id``,
``coverage_hash``, ``candidate_hash``). So the requirement is that nothing
else moves: with those four scrubbed, the candidate is equal on the eight
filings where no heading changes, and on Marriott differs in ``selected``
alone, by exactly the four headings it marks with underline.
"""
from __future__ import annotations

import unicodedata

from .canonical import content_hash, sha256_bytes
from .historical_text_emphasis import build_text_document_admitting_underline
from . import text_results as frozen
from .text_results import (DETERMINISTIC_CANDIDATE_TYPE, DETERMINISTIC_METHOD,
                           VALUE_KIND, _CLAIM_FIELDS, _extent_value, _need, _record,
                           _text, text_policy)

SUPPORTED_METRICS = ("D01",)


def prepare_text_sources(*, compiled_spec, target, source_references, raw_blobs, raw_bytes_by_id):
    """The frozen preparation, on documents that admit underline as emphasis."""
    from .deterministic_router import parse_accession_xbrl_source
    policy = text_policy(compiled_spec)
    sources = [_record(source) for source in source_references]
    ids = [source["source_reference_id"] for source in sources]
    _need(sources and len(ids) == len(set(ids)), "TEXT_SOURCE_SET_EMPTY_OR_DUPLICATE")
    documents, coverages = {}, {}
    for source in sources:
        _need(source["source_role"] in policy["allowed_source_roles"], "TEXT_SOURCE_ROLE_UNSUPPORTED")
        _need(source["company_id"] == target["company_id"]
              and source["accession"] == target["accession"],
              "TEXT_SOURCE_TARGET_ACCESSION_CHANGED")
        raw_id = source["raw_asset_id"]
        _need(raw_id in raw_blobs and raw_id in raw_bytes_by_id, "TEXT_ORIGINAL_SOURCE_MISSING")
        document = build_text_document_admitting_underline(
            raw_bytes=raw_bytes_by_id[raw_id], raw_blob=raw_blobs[raw_id],
            source_reference=source, expected_company_id=target["company_id"],
            expected_cik=target["entity"], expected_period_end=target["period_end"])
        parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes_by_id[raw_id])
        periods = {(parsed.contexts[fact["context_ref"]]["period_start"],
                    parsed.contexts[fact["context_ref"]]["period_end"])
                   for fact in parsed.facts
                   if fact["qualified_name"].split(":")[-1].casefold() == "documentperiodenddate"}
        _need(periods == {(target["period_start"], target["period_end"])},
              "TEXT_DOCUMENT_ANNUAL_PERIOD_CHANGED")
        _need(document["source_state"] == "COMPLETE_LOCAL_DOCUMENT",
              "TEXT_ORIGINAL_DOCUMENT_INCOMPLETE")
        ranges = []
        for section in policy["required_sections"]:
            entry = document["sections"].get(section)
            _need(entry and entry["status"] == "LOCATED" and len(entry["candidates"]) == 1,
                  "TEXT_REQUIRED_COVERAGE_MISSING:" + section)
            ranges.append(entry["candidates"][0])
        coverage = {"source_reference_id": source["source_reference_id"],
                    "document_id": document["text_document_id"], "ranges": ranges,
                    "required_sections": policy["required_sections"],
                    "scope": "COMPLETE_LOCAL_SECTIONS_NOT_SEMANTIC_ABSENCE"}
        coverage["coverage_hash"] = content_hash(value=coverage)
        documents[source["source_reference_id"]] = document
        coverages[source["source_reference_id"]] = coverage
    return documents, coverages


def create_deterministic_text_candidate(*, compiled_spec, target, source_references,
                                        raw_blobs, raw_bytes_by_id):
    """Derive all source headings from the trusted input set; no AI fields exist."""
    documents, coverages = prepare_text_sources(
        compiled_spec=compiled_spec, target=target, source_references=source_references,
        raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    return frozen._derive_deterministic_candidate(
        compiled_spec=compiled_spec, target=target, source_references=source_references,
        documents=documents, coverages=coverages)


def verify_deterministic_text_candidate(*, candidate, **source_arguments):
    expected = create_deterministic_text_candidate(**source_arguments)
    _need(_record(candidate) == expected, "DETERMINISTIC_TEXT_CANDIDATE_REPLAY_CHANGED")
    return expected


def build_text_evidence(*, compiled_spec, target, candidate, source_references,
                        raw_blobs, raw_bytes_by_id):
    """Check every selected exact excerpt and required section using raw bytes."""
    policy = text_policy(compiled_spec)
    candidate = _record(candidate)
    if compiled_spec["compiled"]["quality_rule"].get("deterministic_text_method"):
        _need(candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE,
              "DETERMINISTIC_TEXT_CANDIDATE_TYPE_REQUIRED")
    _need(candidate["record_type"] in {"OBSERVATION_CANDIDATE", DETERMINISTIC_CANDIDATE_TYPE}
          and candidate["disclosure_group"] == compiled_spec["compiled"]["disclosure_group"]
          and candidate["source_reference_ids"] == [source["source_reference_id"]
                                                    for source in source_references]
          and not candidate["derived_asset_ids"] and not candidate["unresolved_competing_claims"]
          and not candidate["competing_candidates"],
          "TEXT_CANDIDATE_SCOPE_OR_COMPETITION_UNSUPPORTED")
    documents, coverages = prepare_text_sources(
        compiled_spec=compiled_spec, target=target, source_references=source_references,
        raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    if candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE:
        expected = frozen._derive_deterministic_candidate(
            compiled_spec=compiled_spec, target=target, source_references=source_references,
            documents=documents, coverages=coverages)
        _need(candidate == expected, "DETERMINISTIC_TEXT_CANDIDATE_REPLAY_CHANGED")
    selected = candidate["selected"]
    _need(1 <= len(selected) <= policy["max_items"], "TEXT_CANDIDATE_ITEM_COUNT_INVALID")
    normalized, checks, orders, spans = {}, [], [], []
    # JSON object-key order is not semantic. Persisted canonical JSON sorts
    # excerpt_10 before excerpt_2; source order must come from the claim.
    for role, claim in sorted(selected.items(), key=lambda pair: pair[1].get("order", -1)):
        _need(type(role) is str and role and type(claim) is dict and set(claim) == _CLAIM_FIELDS
              and claim["value_kind"] == VALUE_KIND, "TEXT_CLAIM_FIELDS_INVALID")
        _text(claim["text"])
        _need(type(claim["order"]) is int, "TEXT_CLAIM_ORDER_INVALID")
        source_id = claim["source_reference_id"]
        _need(source_id in documents, "TEXT_CLAIM_CROSS_SOURCE")
        document = documents[source_id]
        _need(claim["document_id"] == document["text_document_id"]
              and claim["section_id"] in policy["required_sections"],
              "TEXT_CLAIM_DOCUMENT_OR_SECTION_CHANGED")
        index = claim["block_index"]
        _need(type(index) is int and 0 <= index < len(document["blocks"]),
              "TEXT_CLAIM_BLOCK_INVALID")
        block = _extent_value(document["blocks"][index], claim["extent"])
        ranges = [scope for scope in coverages[source_id]["ranges"]
                  if scope["section_id"] == claim["section_id"]]
        _need(len(ranges) == 1
              and ranges[0]["start_block"] <= index < ranges[0]["end_block_exclusive"],
              "TEXT_CLAIM_OUTSIDE_REQUIRED_SCOPE")
        _need(claim["text"] == unicodedata.normalize("NFC", block["text"])
              and all(claim[key] == block[key]
                      for key in ("raw_start_byte", "raw_end_byte", "raw_span_sha256")),
              "TEXT_EXCERPT_OR_RAW_SPAN_CHANGED")
        raw = raw_bytes_by_id[document["raw_asset_id"]]
        _need(sha256_bytes(content=raw[claim["raw_start_byte"]:claim["raw_end_byte"]])
              == claim["raw_span_sha256"], "TEXT_RAW_SPAN_REPLAY_CHANGED")
        normalized[role] = claim["text"]
        orders.append(claim["order"])
        spans.append((source_id, index))
        checks.append({"check": "TEXT_EXACT_EXCERPT:" + role, "status": "PASS",
                       "claim_hash": content_hash(value=claim)})
    _need(sorted(orders) == list(range(len(selected))) and len(spans) == len(set(spans)),
          "TEXT_CLAIM_ORDER_OR_SPAN_DUPLICATED")
    _need(sum(len(value) for value in normalized.values()) + len(normalized) - 1
          <= policy["max_text_chars"], "TEXT_RESULT_SIZE_LIMIT")
    body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS",
            "normalized_values": normalized,
            "checks": [{"check": "TEXT_REQUIRED_SECTIONS", "status": "PASS",
                        "coverage": list(coverages.values())}] + checks,
            "reason_codes": [], "identity_constraints": []}
    if compiled_spec["compiled"].get("scope_contract") is not None:
        # Only the source-derived, complete heading collection can obtain this
        # narrow mechanical eligibility. It certifies whose disclosures are
        # quoted, not the truth/occurrence of a risk or a synthesized summary.
        eligible = (candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE
                    and candidate["method"] == DETERMINISTIC_METHOD
                    and target["scope"] == {"entity_scope": "registrant"}
                    and compiled_spec["compiled"]["required_claims"] == target["scope"])
        body.update(normalized_scope=dict(target["scope"]),
                    system_approval_eligible=eligible,
                    unresolved_scope_dimensions=[] if eligible else list(target["scope"]))
    return _record({"record_type": "EVIDENCE_CHECK",
                    "evidence_check_id": content_hash(value=body), **body})


def reviewed_text_observations(*, compiled_spec, target, candidate, evidence_check, review_unit,
                               review_decisions, source_references, raw_blobs, raw_bytes_by_id):
    """Create same-type observations only after raw replay and effective approval."""
    from .observations import _build_text_observation
    from .review import effective_review_decision
    expected = build_text_evidence(compiled_spec=compiled_spec, target=target, candidate=candidate,
                                   source_references=source_references, raw_blobs=raw_blobs,
                                   raw_bytes_by_id=raw_bytes_by_id)
    _need(_record(evidence_check) == expected, "TEXT_EVIDENCE_REPLAY_CHANGED")
    unit = _record(review_unit)
    _need(unit["evidence_check_id"] == expected["evidence_check_id"]
          and unit["spec_semantic_hash"] == compiled_spec["spec_semantic_hash"]
          and unit["compiled_spec"] == compiled_spec["compiled"]
          and unit["source_bindings"] == list(source_references)
          and all(unit[field] == candidate[field]
                  for field in ("selected", "competing_candidates",
                                "unresolved_competing_claims")),
          "TEXT_REVIEW_UNIT_BINDING_CHANGED")
    decision = effective_review_decision(review_unit=unit, decisions=review_decisions)
    _need(decision["decision"] == "APPROVE" and decision["reviewer_type"] in {"HUMAN", "SYSTEM"},
          "TEXT_EFFECTIVE_APPROVAL_REQUIRED")
    _need(decision["approved_claims"] == target["scope"], "TEXT_REVIEW_TARGET_SCOPE_CHANGED")
    sources = {source["source_reference_id"]: source for source in source_references}
    coverages = {row["source_reference_id"]: row for row in expected["checks"][0]["coverage"]}
    observations = []
    for role, claim in sorted(candidate["selected"].items(), key=lambda pair: pair[1]["order"]):
        source = sources[claim["source_reference_id"]]
        binding = {field: source[field] for field in ("raw_asset_id", "source_reference_id",
                                                      "accession", "document_name", "source_role")}
        binding["text_binding"] = {
            "protocol": VALUE_KIND, "spec_closure_hash": compiled_spec["spec_closure_hash"],
            "candidate_hash": candidate["candidate_hash"], "review_unit_hash": unit["review_unit_hash"],
            "coverage_hash": coverages[source["source_reference_id"]]["coverage_hash"],
            **{key: claim[key] for key in ("extent", "document_id", "section_id", "block_index",
                                           "raw_start_byte", "raw_end_byte", "raw_span_sha256",
                                           "order")}}
        observations.append(_build_text_observation(
            metric_id=compiled_spec["compiled"]["metric_id"], semantic_role=role,
            company_id=target["company_id"], period_start=target["period_start"],
            period_end=target["period_end"], scope=target["scope"], value=claim["text"],
            source_binding=binding, approval_effect_hash=decision["approval_effect_hash"]))
    return observations


def replay_text_result(*, compiled_spec, target, company_traits, candidate, evidence_check,
                       review_unit, review_decisions, source_references, raw_blobs,
                       raw_bytes_by_id):
    """Single raw-source-to-result replay hook for OPEN and FROZEN Run graphs."""
    from .calculator import calculate_text_metric
    observations = reviewed_text_observations(
        compiled_spec=compiled_spec, target=target, candidate=candidate,
        evidence_check=evidence_check, review_unit=review_unit,
        review_decisions=review_decisions, source_references=source_references,
        raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    result, trace = calculate_text_metric(compiled_spec=compiled_spec, target=target,
                                          company_traits=company_traits,
                                          observations=observations)
    return result, trace, observations
