"""A D04 answer the frozen checker accepts, for recorded tests of the historical semantic route.

Kept apart from the tests that use it so that importing it loads only what the
answer is built from: the model-egress suite imports it, and a process that
reaches the call path may load no checkout code the call is not bound to
(``historical_model_calls.loaded_code_holds``).
"""
import json

from vnext.capacity_semantic_review import _restore_units
from vnext.d04_native_assessment import source_statement_relations
from vnext.r6_semantic_review import _source_items
from vnext.regulatory_investigation_candidates import _self_aliases


def synthetic_output(request):
    """A response the frozen checker accepts: its own relations, nothing else.

    Every relation the checker proves is reported as that relation; every
    required candidate it cannot relate is reported as another meaning. This is
    the checker's expected answer, which is exactly what a plumbing fixture
    should be and exactly why it proves nothing about a filing.
    """
    units = _restore_units(request["units"], request["shared_source_dictionaries"])
    blocks = [b for u in units if u["kind"] == "VISIBLE_TEXT" for b in u["payload"]["blocks"]]
    binding = request["document_context"]["registrant_name_binding"]
    aliases = _self_aliases({"registrant_names": binding.get("accepted_source_names", []),
                             "blocks": blocks,
                             "text_document_id": request["document_context"]["document_id"],
                             "raw_asset_id": None, "source_reference_id": None})
    names = [a["text"] for a in aliases if a["text"].casefold() != "we"]
    required = {(r["unit_id"], r["kind"], r["source_index"])
                for r in request["required_candidate_assessments"]}
    rows = []
    for unit in units:
        kind, items = _source_items(unit)
        findings = []
        for index, item in items.items():
            text = item["raw_xml"] if kind == "NATIVE_SUPPLEMENT" else item["text"]
            proven = [r for r in source_statement_relations(
                text=text, names=names, period=request["target_period"],
                quoted=item.get("html_quotation_context", False)) if r["reason"] is None]
            for relation in proven:
                findings.append({"kind": relation["kind"],
                                 "subject": relation["subject"] or "TARGET_REGISTRANT",
                                 "timing": relation["timing"] or "CURRENT_REPORT",
                                 "evidence": [{"kind": kind, "source_index": index}],
                                 "reason": "synthetic fixture: the checker's own relation"})
            if not proven and (unit["unit_id"], kind, index) in required:
                findings.append({"kind": "VALUATION_OR_OTHER_MEANING",
                                 "subject": "TARGET_REGISTRANT", "timing": "CURRENT_REPORT",
                                 "evidence": [{"kind": kind, "source_index": index}],
                                 "reason": "synthetic fixture: an unrelated required candidate"})
        rows.append({"unit_id": unit["unit_id"], "reviewed": True, "findings": findings,
                     "unresolved": []})
    return json.dumps({"request_id": request["request_id"], "units": rows}).encode("utf-8")
