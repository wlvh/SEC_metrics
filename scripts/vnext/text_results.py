"""Reviewed source excerpts on the existing Observation/Trace/Result chain.

TEXT_V1 is an explicitly selected, additive value encoding. These primitives
verify supplied original bytes and the effective review chain; they do not
create provider attempts, grant source admission or authorize publication.
Run replay must independently supply its trusted source set and all decisions.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Mapping, Sequence

from .canonical import content_hash, execution_semantics_hash, sha256_bytes

VALUE_KIND = "TEXT_V1"
TEXT_KIND = "direct_text"
DETERMINISTIC_CANDIDATE_TYPE = "DETERMINISTIC_TEXT_CANDIDATE"
DETERMINISTIC_METHOD = "RISK_FACTOR_HEADINGS_V1"
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_CLAIM_FIELDS = {"value_kind", "extent", "order", "text", "source_reference_id", "document_id",
                 "section_id", "block_index", "raw_start_byte", "raw_end_byte", "raw_span_sha256"}
_BINDING_FIELDS = {"protocol", "extent", "spec_closure_hash", "candidate_hash", "review_unit_hash",
                   "coverage_hash", "document_id", "section_id", "block_index",
                   "raw_start_byte", "raw_end_byte", "raw_span_sha256", "order"}
_PAYLOAD_FIELDS = {"version", "content_kind", "renderer", "items", "coverage_hashes",
                   "candidate_hash", "review_unit_hash", "approval_effect_hash"}


class TextResultError(ValueError):
    """A text value lacks the required source, scope, review or content binding."""


def _need(condition, reason):
    if not condition:
        raise TextResultError(reason)


def _record(value):
    from .records import validate_record
    return validate_record(record=value)


def text_policy(compiled_spec):
    from .specs import SEMANTIC_SET_PATHS
    semantic = compiled_spec["compiled"]
    _need(compiled_spec["spec_semantic_hash"] == content_hash(value=semantic, set_paths=SEMANTIC_SET_PATHS),
          "TEXT_SPEC_SEMANTIC_HASH_CHANGED")
    _need(not semantic.get("dependencies") and compiled_spec["spec_closure_hash"] == content_hash(value={
        "spec_semantic_hash": compiled_spec["spec_semantic_hash"], "dependency_closure_hashes": [],
        "execution_semantics_hash": execution_semantics_hash()}), "TEXT_SPEC_CLOSURE_CHANGED")
    _need(semantic.get("kind") == TEXT_KIND and semantic.get("canonical_unit") == "text"
          and semantic.get("source_mode") in {"ai_text", "structured_first_ai_fallback"}
          and semantic.get("text_policy", {}).get("version") == VALUE_KIND
          and semantic["text_policy"].get("review_required") is True,
          "TEXT_SPEC_REQUIRED")
    return semantic["text_policy"]


def _text(value):
    _need(type(value) is str and bool(value.strip()) and len(value) <= 64000,
          "TEXT_VALUE_EMPTY_OR_TOO_LARGE")
    _need("\x00" not in value and all(ord(char) >= 32 or char in "\t\r\n" for char in value),
          "TEXT_CONTROL_CHARACTER_FORBIDDEN")
    _need(unicodedata.normalize("NFC", value) == value, "TEXT_VALUE_NOT_CANONICAL_NFC")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise TextResultError("TEXT_VALUE_INVALID_UTF8") from error


def render_text_payload(*, payload):
    """Render a strict ordered excerpt list without converting text to a count."""
    _need(type(payload) is dict and set(payload) == _PAYLOAD_FIELDS,
          "TEXT_PAYLOAD_FIELDS_INVALID")
    _need(payload["version"] == VALUE_KIND and payload["content_kind"] == "SOURCE_EXCERPTS"
          and payload["renderer"] == "ORDERED_NEWLINE_V1", "TEXT_PAYLOAD_PROTOCOL_UNSUPPORTED")
    for key in ("candidate_hash", "review_unit_hash", "approval_effect_hash"):
        _need(type(payload[key]) is str and _HASH.fullmatch(payload[key]), "TEXT_PAYLOAD_REVIEW_BINDING_INVALID")
    coverage = payload["coverage_hashes"]
    _need(type(coverage) is list and coverage
          and all(type(value) is str and _HASH.fullmatch(value) for value in coverage)
          and coverage == sorted(set(coverage)),
          "TEXT_PAYLOAD_COVERAGE_INVALID")
    items = payload["items"]
    _need(type(items) is list and 1 <= len(items) <= 64, "TEXT_PAYLOAD_ITEMS_INVALID")
    roles, ids = [], []
    for ordinal, item in enumerate(items):
        _need(type(item) is dict and set(item) == {"order", "role", "text", "observation_id"}
              and type(item["order"]) is int and item["order"] == ordinal,
              "TEXT_PAYLOAD_ITEM_ORDER_INVALID")
        _text(item["text"])
        _need(type(item["role"]) is str and item["role"]
              and type(item["observation_id"]) is str and _HASH.fullmatch(item["observation_id"]),
              "TEXT_PAYLOAD_ITEM_BINDING_INVALID")
        roles.append(item["role"]); ids.append(item["observation_id"])
    _need(len(roles) == len(set(roles)) and len(ids) == len(set(ids)), "TEXT_PAYLOAD_DUPLICATE_ITEM")
    rendered = "\n".join(item["text"] for item in items)
    _text(rendered)
    return rendered


def validate_text_record(*, record):
    """Validate the typed shape only; source replay belongs to the Run graph."""
    kind = record["record_type"]
    _need(kind in {"VERIFIED_OBSERVATION", "EXECUTION_TRACE", "METRIC_RESULT"}
          and record.get("value_kind") == VALUE_KIND, "TEXT_RECORD_MARKER_INVALID")
    if kind == "VERIFIED_OBSERVATION":
        _text(record["value"])
        _need(record["unit"] == "text" and record["quality"] == "EXACT"
              and bool(_HASH.fullmatch(record["approval_effect_hash"])), "TEXT_OBSERVATION_NOT_REVIEWED")
        binding = record["source_binding"].get("text_binding")
        _need(type(binding) is dict and set(binding) == _BINDING_FIELDS
              and binding["protocol"] == VALUE_KIND
              and type(binding["extent"]) is str
              and binding["extent"] in {"FULL_BLOCK", "LEADING_EMPHASIS"}, "TEXT_OBSERVATION_BINDING_INVALID")
        for key in ("spec_closure_hash", "candidate_hash", "review_unit_hash", "coverage_hash", "document_id"):
            _need(type(binding[key]) is str and _HASH.fullmatch(binding[key]), "TEXT_OBSERVATION_HASH_INVALID")
        for key in ("order", "block_index", "raw_start_byte", "raw_end_byte"):
            _need(type(binding[key]) is int and binding[key] >= 0, "TEXT_OBSERVATION_OFFSET_INVALID")
        _need(binding["raw_start_byte"] < binding["raw_end_byte"]
              and type(binding["raw_span_sha256"]) is str
              and re.fullmatch(r"[0-9a-f]{64}", binding["raw_span_sha256"])
              and type(binding["section_id"]) is str and binding["section_id"],
              "TEXT_OBSERVATION_SPAN_INVALID")
    elif kind == "METRIC_RESULT":
        _need("text_payload" in record, "TEXT_RESULT_PAYLOAD_MISSING")
        if record["value"] is None:
            _need(record["text_payload"] is None, "TEXT_NULL_RESULT_HAS_PAYLOAD")
        else:
            _need(record["unit"] == "text" and record["quality"] == "EXACT",
                  "TEXT_RESULT_UNIT_OR_QUALITY_INVALID")
            _need(render_text_payload(payload=record["text_payload"]) == record["value"],
                  "TEXT_RESULT_RENDERING_CHANGED")
    elif record["result"] is not None:
        _text(record["result"])


def prepare_text_sources(*, compiled_spec, target, source_references, raw_blobs, raw_bytes_by_id):
    """Rebuild full required local sections from originals, never supplied scans."""
    from .text_coverage import build_text_document
    from .deterministic_router import parse_accession_xbrl_source
    policy = text_policy(compiled_spec)
    sources = [_record(source) for source in source_references]
    ids = [source["source_reference_id"] for source in sources]
    _need(sources and len(ids) == len(set(ids)), "TEXT_SOURCE_SET_EMPTY_OR_DUPLICATE")
    documents, coverages = {}, {}
    for source in sources:
        _need(source["source_role"] in policy["allowed_source_roles"], "TEXT_SOURCE_ROLE_UNSUPPORTED")
        _need(source["company_id"] == target["company_id"] and source["accession"] == target["accession"],
              "TEXT_SOURCE_TARGET_ACCESSION_CHANGED")
        raw_id = source["raw_asset_id"]
        _need(raw_id in raw_blobs and raw_id in raw_bytes_by_id, "TEXT_ORIGINAL_SOURCE_MISSING")
        document = build_text_document(raw_bytes=raw_bytes_by_id[raw_id], raw_blob=raw_blobs[raw_id],
            source_reference=source, expected_company_id=target["company_id"],
            expected_cik=target["entity"], expected_period_end=target["period_end"])
        parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes_by_id[raw_id])
        periods = {(parsed.contexts[fact["context_ref"]]["period_start"], parsed.contexts[fact["context_ref"]]["period_end"])
                   for fact in parsed.facts if fact["qualified_name"].split(":")[-1].casefold() == "documentperiodenddate"}
        _need(periods == {(target["period_start"], target["period_end"])}, "TEXT_DOCUMENT_ANNUAL_PERIOD_CHANGED")
        _need(document["source_state"] == "COMPLETE_LOCAL_DOCUMENT", "TEXT_ORIGINAL_DOCUMENT_INCOMPLETE")
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


def _extent_value(block, extent):
    _need(type(extent) is str and extent in {"FULL_BLOCK", "LEADING_EMPHASIS"}, "TEXT_CLAIM_EXTENT_UNSUPPORTED")
    selected = block if extent == "FULL_BLOCK" else block.get("leading_emphasis")
    _need(type(selected) is dict and bool(selected.get("text")), "TEXT_LEADING_EMPHASIS_UNAVAILABLE")
    return selected


def text_claim_from_block(*, document, section_id, block_index, order, extent="FULL_BLOCK"):
    """Prepare a claim from a selected source block; this is not acceptance."""
    block = _extent_value(document["blocks"][block_index], extent)
    return {"value_kind": VALUE_KIND, "extent": extent, "order": order, "text": unicodedata.normalize("NFC", block["text"]),
        "source_reference_id": document["source_reference_id"], "document_id": document["text_document_id"],
        "section_id": section_id, "block_index": block_index,
        **{key: block[key] for key in ("raw_start_byte", "raw_end_byte", "raw_span_sha256")}}


def validate_deterministic_candidate_shape(*, candidate):
    _need(candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE and candidate["method"] == DETERMINISTIC_METHOD
          and candidate["status"] == "CANDIDATE" and not candidate["derived_asset_ids"]
          and not candidate["competing_candidates"] and not candidate["unresolved_competing_claims"],
          "DETERMINISTIC_TEXT_CANDIDATE_PROTOCOL_INVALID")
    for field in ("spec_semantic_hash", "spec_closure_hash", "source_set_hash"):
        _need(type(candidate[field]) is str and _HASH.fullmatch(candidate[field]), "DETERMINISTIC_TEXT_CANDIDATE_HASH_INVALID")
    ids = candidate["source_reference_ids"]
    _need(ids and all(type(value) is str and _HASH.fullmatch(value) for value in ids)
          and len(ids) == len(set(ids)) and set(candidate["document_bindings"]) == set(ids),
          "DETERMINISTIC_TEXT_CANDIDATE_SOURCE_SET_INVALID")
    for item in candidate["document_bindings"].values():
        _need(type(item) is dict and set(item) == {"document_id", "coverage_hash", "proposal_id"}
              and all(type(value) is str and _HASH.fullmatch(value) for value in item.values()),
              "DETERMINISTIC_TEXT_DOCUMENT_BINDING_INVALID")
    target = candidate["calculation_target"]
    _need(set(target) == {"company_id", "entity", "accession", "period_start", "period_end", "scope", "scope_key"}
          and target["scope_key"] == content_hash(value=target["scope"]), "DETERMINISTIC_TEXT_TARGET_INVALID")


def _derive_deterministic_candidate(*, compiled_spec, target, source_references, documents, coverages):
    from .risk_signals import risk_factor_headings
    policy = text_policy(compiled_spec)
    _need(compiled_spec["compiled"]["quality_rule"].get("deterministic_text_method") == DETERMINISTIC_METHOD
          and policy["required_sections"] == ["ITEM_1A"], "DETERMINISTIC_TEXT_SPEC_METHOD_REQUIRED")
    selected, document_bindings = {}, {}
    for source in source_references:
        source_id = source["source_reference_id"]
        document = documents[source_id]
        proposal = risk_factor_headings(document=document)
        _need(proposal["status"] == "SOURCE_HEADINGS_READY", "DETERMINISTIC_TEXT_HEADINGS_UNSUPPORTED")
        document_bindings[source_id] = {"document_id": document["text_document_id"],
            "coverage_hash": coverages[source_id]["coverage_hash"], "proposal_id": proposal["proposal_id"]}
        for heading in proposal["headings"]:
            order = len(selected)
            selected["excerpt_" + str(order)] = text_claim_from_block(document=document, section_id="ITEM_1A",
                block_index=heading["locators"][0]["block_index"], order=order, extent="LEADING_EMPHASIS")
    _need(1 <= len(selected) <= policy["max_items"], "DETERMINISTIC_TEXT_HEADINGS_EXCEED_BOUND")
    _need(sum(len(claim["text"]) for claim in selected.values()) + len(selected) - 1 <= policy["max_text_chars"],
          "DETERMINISTIC_TEXT_CONTENT_EXCEEDS_BOUND")
    body = {"record_type": DETERMINISTIC_CANDIDATE_TYPE, "method": DETERMINISTIC_METHOD,
        "spec_semantic_hash": compiled_spec["spec_semantic_hash"], "spec_closure_hash": compiled_spec["spec_closure_hash"],
        "source_set_hash": content_hash(value=list(source_references)), "document_bindings": document_bindings,
        "calculation_target": dict(target), "disclosure_group": compiled_spec["compiled"]["disclosure_group"],
        "source_reference_ids": [source["source_reference_id"] for source in source_references],
        "derived_asset_ids": [], "selected": selected, "competing_candidates": [], "unresolved_competing_claims": []}
    return _record({**body, "candidate_hash": content_hash(value=body), "status": "CANDIDATE"})


def create_deterministic_text_candidate(*, compiled_spec, target, source_references, raw_blobs, raw_bytes_by_id):
    """Derive all source headings from the trusted input set; no AI fields exist."""
    documents, coverages = prepare_text_sources(compiled_spec=compiled_spec, target=target,
        source_references=source_references, raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    return _derive_deterministic_candidate(compiled_spec=compiled_spec, target=target,
        source_references=source_references, documents=documents, coverages=coverages)


def verify_deterministic_text_candidate(*, candidate, **source_arguments):
    expected = create_deterministic_text_candidate(**source_arguments)
    _need(_record(candidate) == expected, "DETERMINISTIC_TEXT_CANDIDATE_REPLAY_CHANGED")
    return expected


def build_text_evidence(*, compiled_spec, target, candidate, source_references, raw_blobs, raw_bytes_by_id):
    """Check every selected exact excerpt and required section using raw bytes."""
    policy = text_policy(compiled_spec)
    candidate = _record(candidate)
    if compiled_spec["compiled"]["quality_rule"].get("deterministic_text_method"):
        _need(candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE,
              "DETERMINISTIC_TEXT_CANDIDATE_TYPE_REQUIRED")
    _need(candidate["record_type"] in {"OBSERVATION_CANDIDATE", DETERMINISTIC_CANDIDATE_TYPE}
          and candidate["disclosure_group"] == compiled_spec["compiled"]["disclosure_group"]
          and candidate["source_reference_ids"] == [source["source_reference_id"] for source in source_references]
          and not candidate["derived_asset_ids"] and not candidate["unresolved_competing_claims"]
          and not candidate["competing_candidates"], "TEXT_CANDIDATE_SCOPE_OR_COMPETITION_UNSUPPORTED")
    documents, coverages = prepare_text_sources(compiled_spec=compiled_spec, target=target,
        source_references=source_references, raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    if candidate["record_type"] == DETERMINISTIC_CANDIDATE_TYPE:
        expected = _derive_deterministic_candidate(compiled_spec=compiled_spec, target=target,
            source_references=source_references, documents=documents, coverages=coverages)
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
              and claim["section_id"] in policy["required_sections"], "TEXT_CLAIM_DOCUMENT_OR_SECTION_CHANGED")
        index = claim["block_index"]
        _need(type(index) is int and 0 <= index < len(document["blocks"]), "TEXT_CLAIM_BLOCK_INVALID")
        block = _extent_value(document["blocks"][index], claim["extent"])
        ranges = [scope for scope in coverages[source_id]["ranges"] if scope["section_id"] == claim["section_id"]]
        _need(len(ranges) == 1 and ranges[0]["start_block"] <= index < ranges[0]["end_block_exclusive"],
              "TEXT_CLAIM_OUTSIDE_REQUIRED_SCOPE")
        _need(claim["text"] == unicodedata.normalize("NFC", block["text"])
              and all(claim[key] == block[key] for key in ("raw_start_byte", "raw_end_byte", "raw_span_sha256")),
              "TEXT_EXCERPT_OR_RAW_SPAN_CHANGED")
        raw = raw_bytes_by_id[document["raw_asset_id"]]
        _need(sha256_bytes(content=raw[claim["raw_start_byte"]:claim["raw_end_byte"]]) == claim["raw_span_sha256"],
              "TEXT_RAW_SPAN_REPLAY_CHANGED")
        normalized[role] = claim["text"]
        orders.append(claim["order"]); spans.append((source_id, index))
        checks.append({"check": "TEXT_EXACT_EXCERPT:" + role, "status": "PASS", "claim_hash": content_hash(value=claim)})
    _need(sorted(orders) == list(range(len(selected))) and len(spans) == len(set(spans)),
          "TEXT_CLAIM_ORDER_OR_SPAN_DUPLICATED")
    _need(sum(len(value) for value in normalized.values()) + len(normalized) - 1 <= policy["max_text_chars"],
          "TEXT_RESULT_SIZE_LIMIT")
    body = {"candidate_hash": candidate["candidate_hash"], "status": "PASS", "normalized_values": normalized,
            "checks": [{"check": "TEXT_REQUIRED_SECTIONS", "status": "PASS", "coverage": list(coverages.values())}] + checks,
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
    return _record({"record_type": "EVIDENCE_CHECK", "evidence_check_id": content_hash(value=body), **body})


def reviewed_text_observations(*, compiled_spec, target, candidate, evidence_check, review_unit,
                               review_decisions, source_references, raw_blobs, raw_bytes_by_id):
    """Create same-type observations only after raw replay and effective approval."""
    from .observations import _build_text_observation
    from .review import effective_review_decision
    expected = build_text_evidence(compiled_spec=compiled_spec, target=target, candidate=candidate,
        source_references=source_references, raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    _need(_record(evidence_check) == expected, "TEXT_EVIDENCE_REPLAY_CHANGED")
    unit = _record(review_unit)
    _need(unit["evidence_check_id"] == expected["evidence_check_id"]
          and unit["spec_semantic_hash"] == compiled_spec["spec_semantic_hash"]
          and unit["compiled_spec"] == compiled_spec["compiled"]
          and unit["source_bindings"] == list(source_references)
          and all(unit[field] == candidate[field] for field in ("selected", "competing_candidates", "unresolved_competing_claims")),
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
        binding = {field: source[field] for field in ("raw_asset_id", "source_reference_id", "accession", "document_name", "source_role")}
        binding["text_binding"] = {"protocol": VALUE_KIND, "spec_closure_hash": compiled_spec["spec_closure_hash"],
            "candidate_hash": candidate["candidate_hash"], "review_unit_hash": unit["review_unit_hash"],
            "coverage_hash": coverages[source["source_reference_id"]]["coverage_hash"],
            **{key: claim[key] for key in ("extent", "document_id", "section_id", "block_index", "raw_start_byte", "raw_end_byte", "raw_span_sha256", "order")}}
        observations.append(_build_text_observation(metric_id=compiled_spec["compiled"]["metric_id"], semantic_role=role,
            company_id=target["company_id"], period_start=target["period_start"], period_end=target["period_end"],
            scope=target["scope"], value=claim["text"], source_binding=binding,
            approval_effect_hash=decision["approval_effect_hash"]))
    return observations


def payload_from_observations(*, compiled_spec, target, observations):
    """Pure Calculator input check; the Run must also replay raw sources/reviews."""
    policy = text_policy(compiled_spec)
    observations = [_record(observation) for observation in observations]
    _need(1 <= len(observations) <= policy["max_items"], "TEXT_APPROVED_OBSERVATIONS_REQUIRED")
    observations.sort(key=lambda observation: observation["source_binding"].get("text_binding", {}).get("order", -1))
    identities = set(); coverages = set(); items = []
    for order, observation in enumerate(observations):
        _need(observation.get("value_kind") == VALUE_KIND and observation["metric_id"] == compiled_spec["compiled"]["metric_id"]
              and all(observation[key] == target[key] for key in ("company_id", "period_start", "period_end", "scope", "scope_key")),
              "TEXT_OBSERVATION_TARGET_OR_KIND_CHANGED")
        binding = observation["source_binding"]["text_binding"]
        _need(binding["spec_closure_hash"] == compiled_spec["spec_closure_hash"] and binding["order"] == order,
              "TEXT_OBSERVATION_SPEC_OR_ORDER_CHANGED")
        identities.add((binding["candidate_hash"], binding["review_unit_hash"], observation["approval_effect_hash"]))
        coverages.add(binding["coverage_hash"])
        items.append({"order": order, "role": observation["semantic_role"], "text": observation["value"],
                      "observation_id": observation["observation_id"]})
    _need(len(identities) == 1, "TEXT_OBSERVATION_REVIEW_SET_MIXED")
    candidate_hash, unit_hash, effect_hash = identities.pop()
    payload = {"version": VALUE_KIND, "content_kind": policy["content_kind"], "renderer": policy["renderer"],
        "items": items, "coverage_hashes": sorted(coverages), "candidate_hash": candidate_hash,
        "review_unit_hash": unit_hash, "approval_effect_hash": effect_hash}
    _need(len(render_text_payload(payload=payload)) <= policy["max_text_chars"], "TEXT_RESULT_SIZE_LIMIT")
    return payload


def build_text_result_and_trace(*, compiled_spec, target, payload=None, reason_code="PASS", structural=False):
    from .records import metric_result_contract_hash
    text_policy(compiled_spec)
    value = render_text_payload(payload=payload) if payload is not None else None
    _need((value is not None) == (reason_code == "PASS") and not (value is not None and structural), "TEXT_RESULT_STATE_INVALID")
    contract = {"company_id": target["company_id"], "metric_id": compiled_spec["compiled"]["metric_id"],
        "period_start": target["period_start"], "period_end": target["period_end"], "scope_key": target["scope_key"],
        "spec_closure_hash": compiled_spec["spec_closure_hash"], "applicability": "N_A_STRUCTURAL" if structural else "APPLICABLE",
        "quality": "EXACT" if value is not None else "NONE", "publication": "PUBLISHED" if value is not None or structural else "WITHHELD",
        "reason_code": reason_code, "value": value, "unit": "text" if value is not None else None,
        "value_kind": VALUE_KIND, "text_payload": payload}
    inputs = [item["observation_id"] for item in payload["items"]] if payload else []
    steps = ([{"event": "TEXT_RESULT_RENDER", "text_payload": payload, "payload_hash": content_hash(value=payload)}]
             if payload else [{"event": "N_A_STRUCTURAL"}] if structural else [{"event": "WITHHELD", "reason_code": reason_code}])
    trace_body = {"metric_id": contract["metric_id"], "calculation_target": dict(target), "input_observation_ids": inputs,
        "steps": steps, "quality": contract["quality"], "result": value, "spec_closure_hash": compiled_spec["spec_closure_hash"],
        "execution_semantics_hash": execution_semantics_hash(), "result_contract_hash": metric_result_contract_hash(result=contract),
        "value_kind": VALUE_KIND}
    trace = {"record_type": "EXECUTION_TRACE", "trace_id": content_hash(value=trace_body), **trace_body}
    result_body = {**contract, "trace_id": trace["trace_id"]}
    result = {"record_type": "METRIC_RESULT", "result_id": content_hash(value=result_body), **result_body}
    return _record(result), _record(trace)


def verify_text_trace(*, trace, observations):
    _need(trace.get("value_kind") == VALUE_KIND, "TEXT_TRACE_MARKER_REQUIRED")
    if trace["result"] is None:
        _need(not trace["input_observation_ids"] and len(trace["steps"]) == 1
              and trace["quality"] == "NONE"
              and trace["steps"][0]["event"] in {"WITHHELD", "N_A_STRUCTURAL"}, "TEXT_NULL_TRACE_STATE_INVALID")
        step = trace["steps"][0]
        _need((step == {"event": "N_A_STRUCTURAL"}) or (set(step) == {"event", "reason_code"}
              and type(step["reason_code"]) is str and step["reason_code"] and step["reason_code"] != "PASS"),
              "TEXT_NULL_TRACE_REASON_INVALID")
        return
    steps = trace["steps"]
    _need(len(steps) == 1 and set(steps[0]) == {"event", "text_payload", "payload_hash"}
          and steps[0]["event"] == "TEXT_RESULT_RENDER", "TEXT_TRACE_RENDER_STEP_INVALID")
    payload = steps[0]["text_payload"]
    _need(steps[0]["payload_hash"] == content_hash(value=payload)
          and render_text_payload(payload=payload) == trace["result"], "TEXT_TRACE_PAYLOAD_CHANGED")
    _need(trace["input_observation_ids"] == [item["observation_id"] for item in payload["items"]],
          "TEXT_TRACE_INPUT_EXACT_SET_CHANGED")
    coverages = set()
    for item in payload["items"]:
        _need(item["observation_id"] in observations, "TEXT_TRACE_OBSERVATION_MISSING")
        observation = _record(observations[item["observation_id"]])
        _need(observation.get("value_kind") == VALUE_KIND and observation["semantic_role"] == item["role"]
              and observation["value"] == item["text"] and observation["quality"] == trace["quality"] == "EXACT",
              "TEXT_TRACE_OBSERVATION_VALUE_CHANGED")
        binding = observation["source_binding"]["text_binding"]
        _need(binding["order"] == item["order"] and binding["spec_closure_hash"] == trace["spec_closure_hash"]
              and binding["candidate_hash"] == payload["candidate_hash"] and binding["review_unit_hash"] == payload["review_unit_hash"]
              and observation["approval_effect_hash"] == payload["approval_effect_hash"], "TEXT_TRACE_REVIEW_BINDING_CHANGED")
        coverages.add(binding["coverage_hash"])
    _need(sorted(coverages) == payload["coverage_hashes"], "TEXT_TRACE_COVERAGE_CHANGED")


def replay_text_result(*, compiled_spec, target, company_traits, candidate, evidence_check, review_unit,
                       review_decisions, source_references, raw_blobs, raw_bytes_by_id):
    """Single raw-source-to-result replay hook for OPEN and FROZEN Run graphs."""
    from .calculator import calculate_text_metric
    observations = reviewed_text_observations(compiled_spec=compiled_spec, target=target, candidate=candidate,
        evidence_check=evidence_check, review_unit=review_unit, review_decisions=review_decisions,
        source_references=source_references, raw_blobs=raw_blobs, raw_bytes_by_id=raw_bytes_by_id)
    result, trace = calculate_text_metric(compiled_spec=compiled_spec, target=target,
        company_traits=company_traits, observations=observations)
    return result, trace, observations


def verify_text_result(*, result, trace, observations, **replay_arguments):
    """Reject a rehashed stored graph unless original-byte replay reproduces it."""
    expected_result, expected_trace, expected_observations = replay_text_result(**replay_arguments)
    actual_by_id = {observation["observation_id"]: observation for observation in observations}
    expected_by_id = {observation["observation_id"]: observation for observation in expected_observations}
    _need(len(actual_by_id) == len(observations) and actual_by_id == expected_by_id
          and result == expected_result and trace == expected_trace, "TEXT_NATIVE_REPLAY_CHANGED")
    return expected_result, expected_trace, expected_observations
