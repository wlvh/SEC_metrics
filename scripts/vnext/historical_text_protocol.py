"""Carry one more bound than the frozen text-result protocol, and nothing else.

Purpose:
    ``max_items`` turned out to be two bounds wearing one number. The first is
    what a Spec may declare, and ``historical_spec_revision`` raises that for a
    revised Spec without touching the frozen compiler. The second is what
    ``ORDERED_NEWLINE_V1`` will render: a literal ``64`` in
    ``text_results.render_text_payload``, with no Spec in scope, which every
    result of this kind passes through on construction, on shape validation, on
    trace verification and on projection. A Spec may declare 192 and still be
    unable to produce a 65th excerpt.

    ``text_results.py`` is a ``new_rule_file`` of ``issue_28_v11``, checked on
    both the data root and the code root, so this generation carries the
    capacity instead - the same shape as ``text_coverage`` ->
    ``historical_text_results``.

What is inherited and what changed:
    Every check is the frozen one, character for character, with exactly one
    edit: the literal item bound is a parameter. Order within the payload,
    duplicate roles and observation ids, per-item shape, text validity and
    encoding, hash formats, coverage ordering, the review bindings, the
    character ceiling and the rendering itself are unchanged, and
    ``test_historical_text_protocol`` proves it by differential comparison -
    for any payload at or under the frozen bound the successor must return
    exactly what the frozen implementation returns and raise exactly the error
    it raises. Raising capacity adds validation work; it relaxes nothing.

Where the capacity comes from, and why a payload cannot choose it:
    Wherever the compiled Spec is in scope - construction and mechanical replay
    - it is ``policy["max_items"]``, and the Spec is the one the Run manifest
    binds by bytes. Where it is not in scope - shape validation, trace
    verification, projection - it is resolved from the ``spec_closure_hash``
    the record already declares, against Specs this repository compiles itself.
    A record naming an identity the repository cannot reproduce gets the frozen
    bound. So capacity follows a Spec identity the repository can rebuild,
    never a number the payload asserts about itself.

    That resolution is a ceiling on shape, not the metric's bound. The metric's
    bound is enforced where the Spec is, and an over-bound payload that somehow
    reached disk still fails the Run graph, because the graph's own replay runs
    ``payload_from_observations`` against the byte-verified compiled Spec.

Call relationships:
    The historical Run's calculator route, record validation, trace
    verification and projection reach this by Requirement. Nothing here opens a
    source, calls a provider, or grants execution.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, Mapping

from .canonical import content_hash, execution_semantics_hash, sha256_file
from .normal_source_authority import ROOT
from .text_results import (VALUE_KIND, TextResultError, _PAYLOAD_FIELDS, _record, _text,
                           text_policy)

# What the frozen renderer allows, and therefore what anything this generation
# does not positively recognise as revised still gets.
FROZEN_PROTOCOL_MAX_ITEMS = 64
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_REVISED_CEILINGS: Dict[str, Dict[str, object]] = {}


def _need(condition, reason):
    if not condition:
        raise TextResultError(reason)


def revised_spec_ceilings(*, repo_root: Path = ROOT) -> Dict[str, int]:
    """Item bound by Spec closure hash, for the Specs this repository revises.

    Args:
        repo_root: Repository holding the revised Specs and their predecessors.

    Returns:
        Mapping of ``spec_closure_hash`` to the bound that Spec declares.

    Why:
        The closure hash folds in ``execution_semantics_hash()``, so it moves
        when unrelated code moves and cannot be written down as a constant. It
        is recomputed from the Spec files instead, and the per-process reuse is
        keyed on those files' bytes - the same discipline the shared source
        scope uses. Reusing a result without re-reading the bytes would be
        caching an authority, which is a different and worse thing than caching
        a parse.
    """
    from .historical_spec_revision import REVISED_TEXT_SPECS, compile_historical_spec_file
    key = (str(repo_root), execution_semantics_hash(),
           tuple(sorted((path, sha256_file(path=repo_root / path))
                        for path in REVISED_TEXT_SPECS)))
    cached = _REVISED_CEILINGS.get("entry")
    if cached is not None and cached["key"] == key:
        return dict(cached["ceilings"])
    ceilings = {}
    for path in sorted(REVISED_TEXT_SPECS):
        wrapper = compile_historical_spec_file(repo_root=repo_root, repo_relative_path=path,
                                               dependency_specs={})
        ceilings[str(wrapper["spec_closure_hash"])] = int(
            wrapper["compiled"]["text_policy"]["max_items"])
    _REVISED_CEILINGS["entry"] = {"key": key, "ceilings": dict(ceilings)}
    return dict(ceilings)


def declared_spec_ceiling(*, spec_closure_hash, repo_root: Path = ROOT) -> int:
    """The item bound a record's declared Spec identity carries.

    Args:
        spec_closure_hash: The identity the record already declares.
        repo_root: Repository used to recompile the revised Specs.

    Returns:
        The revised Spec's bound when the repository can reproduce that exact
        identity, and the frozen protocol bound otherwise.
    """
    if type(spec_closure_hash) is not str:
        return FROZEN_PROTOCOL_MAX_ITEMS
    return revised_spec_ceilings(repo_root=repo_root).get(spec_closure_hash,
                                                          FROZEN_PROTOCOL_MAX_ITEMS)


def render_text_payload(*, payload, max_items: int = FROZEN_PROTOCOL_MAX_ITEMS):
    """Render a strict ordered excerpt list without converting text to a count.

    Args:
        payload: The excerpt payload to validate and render.
        max_items: How many excerpts this payload's Spec permits. Everything
            else in this function is the frozen implementation verbatim.

    Returns:
        The newline-joined excerpt text.

    Raises:
        TextResultError: On any shape, ordering, duplication, binding, text or
            capacity violation the frozen implementation refuses.
    """
    _need(type(max_items) is int and 1 <= max_items, "TEXT_PAYLOAD_BOUND_INVALID")
    _need(type(payload) is dict and set(payload) == _PAYLOAD_FIELDS,
          "TEXT_PAYLOAD_FIELDS_INVALID")
    _need(payload["version"] == VALUE_KIND and payload["content_kind"] == "SOURCE_EXCERPTS"
          and payload["renderer"] == "ORDERED_NEWLINE_V1", "TEXT_PAYLOAD_PROTOCOL_UNSUPPORTED")
    for key in ("candidate_hash", "review_unit_hash", "approval_effect_hash"):
        _need(type(payload[key]) is str and _HASH.fullmatch(payload[key]),
              "TEXT_PAYLOAD_REVIEW_BINDING_INVALID")
    coverage = payload["coverage_hashes"]
    _need(type(coverage) is list and coverage
          and all(type(value) is str and _HASH.fullmatch(value) for value in coverage)
          and coverage == sorted(set(coverage)),
          "TEXT_PAYLOAD_COVERAGE_INVALID")
    items = payload["items"]
    _need(type(items) is list and 1 <= len(items) <= max_items, "TEXT_PAYLOAD_ITEMS_INVALID")
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
    _need(len(render_text_payload(payload=payload, max_items=policy["max_items"]))
          <= policy["max_text_chars"], "TEXT_RESULT_SIZE_LIMIT")
    return payload


def build_text_result_and_trace(*, compiled_spec, target, payload=None, reason_code="PASS",
                                structural=False):
    """Build the Result and Trace pair for one text metric."""
    from .records import metric_result_contract_hash
    policy = text_policy(compiled_spec)
    value = (render_text_payload(payload=payload, max_items=policy["max_items"])
             if payload is not None else None)
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


def record_item_ceiling(*, record, repo_root: Path = ROOT) -> int:
    """The item bound one record's own declared Spec identity carries."""
    declared = record.get("spec_closure_hash")
    if declared is None:
        binding = (record.get("source_binding") or {}).get("text_binding") or {}
        declared = binding.get("spec_closure_hash")
    return declared_spec_ceiling(spec_closure_hash=declared, repo_root=repo_root)


def validate_text_record(*, record, repo_root: Path = ROOT):
    """Validate the typed shape only; source replay belongs to the Run graph.

    Args:
        record: The text record to check.
        repo_root: Repository used to resolve the declared Spec's item bound.

    Raises:
        TextResultError: On any shape violation the frozen validator refuses.

    Why the ceiling is resolved rather than passed:
        This is reached from record loading, which has no Run and no compiled
        Spec in scope. The record does carry the Spec identity it was built
        under, and that identity is checked against Specs this repository
        compiles for itself, so a record cannot widen its own bound by saying
        so. The metric's real bound is enforced where the Spec is.
    """
    from .text_results import validate_text_record as frozen_validate_text_record
    kind = record["record_type"]
    if kind != "METRIC_RESULT" or record.get("value") is None:
        # Only the METRIC_RESULT branch renders a payload, so every other
        # branch is the frozen validator with nothing removed.
        frozen_validate_text_record(record=record)
        return
    _need(record.get("value_kind") == VALUE_KIND, "TEXT_RECORD_MARKER_INVALID")
    _need("text_payload" in record, "TEXT_RESULT_PAYLOAD_MISSING")
    _need(record["unit"] == "text" and record["quality"] == "EXACT",
          "TEXT_RESULT_UNIT_OR_QUALITY_INVALID")
    _need(render_text_payload(payload=record["text_payload"],
                              max_items=record_item_ceiling(record=record,
                                                            repo_root=repo_root))
          == record["value"], "TEXT_RESULT_RENDERING_CHANGED")


def verify_text_trace(*, trace, observations, repo_root: Path = ROOT):
    """Check one text trace against the observations it names."""
    from .text_results import verify_text_trace as frozen_verify_text_trace
    if trace.get("value_kind") != VALUE_KIND or trace.get("result") is None:
        frozen_verify_text_trace(trace=trace, observations=observations)
        return
    steps = trace["steps"]
    _need(len(steps) == 1 and set(steps[0]) == {"event", "text_payload", "payload_hash"}
          and steps[0]["event"] == "TEXT_RESULT_RENDER", "TEXT_TRACE_RENDER_STEP_INVALID")
    payload = steps[0]["text_payload"]
    _need(steps[0]["payload_hash"] == content_hash(value=payload)
          and render_text_payload(payload=payload,
                                  max_items=record_item_ceiling(record=trace,
                                                                repo_root=repo_root))
          == trace["result"], "TEXT_TRACE_PAYLOAD_CHANGED")
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


def projection_value(*, result, repo_root: Path = ROOT):
    """The legacy public value one text Result projects to."""
    return render_text_payload(payload=result["text_payload"],
                               max_items=record_item_ceiling(record=result,
                                                             repo_root=repo_root))
