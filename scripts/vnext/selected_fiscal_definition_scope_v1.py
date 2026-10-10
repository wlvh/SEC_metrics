"""Fixed #47 assertion check consumed by the explicit revenue source reader.

Copied require_actual_definition_scope from9749a213, preserving its exact
function body. Existing helpers are unchanged from that fixed version. This
is no new fiscal classifier or widened history consumer.
"""
import re
from .canonical import canonical_json_bytes,content_hash
from .historical_fiscal_labels import _frozen_labels,_ordered_pattern,_status
ASSERTION_SCOPE_RULE = "HISTORICAL_FISCAL_DEFINITION_ASSERTION_SCOPE_V1"
_CONDITIONAL_DEFINITION = re.compile(r"\bif\b[^.!?]{0,240}\b(?:proposed\s+)?naming convention\b", re.I)
_HYPOTHETICAL_DEFINITION = re.compile(r"\b(?:hypothetical example|not our actual naming convention)\b", re.I)


def require_actual_definition_scope(inspected):
    """Keep identified conditional/hypothetical mappings unresolved.

    The retained inspector recognizes sentence forms, including forms inside
    ordinary quoted text. Recognizing a mapping does not establish that the
    issuer has adopted it. This bounded historical check preserves the source
    block and prevents the two reported non-actual contexts from overriding
    metadata. Quotation marks around a label alone are not a rejection reason.
    Unaffected inspections are returned unchanged, including their identity.
    """
    definitions, rejected = [], []
    for item in inspected["source_definitions"]:
        pattern = {"EXPLICIT_EXAMPLE":_frozen_labels._SINGLE,
                   "EXPLICIT_ORDERED_YEARS":_ordered_pattern(),
                   "EXPLICIT_REFERENCE_YEARS":_frozen_labels._REFERENCES}[item["kind"]]
        contexts = []
        for match in pattern.finditer(item["text"]):
            if item["kind"] == "EXPLICIT_EXAMPLE":
                mapping = [{"fiscal_year":int(match["label"]),"period_end":_frozen_labels._iso_end(match["end"])}]
            else:
                mapping = [{"fiscal_year":int(year),"period_end":_frozen_labels._iso_end(end)}
                           for year,end in zip(re.findall(r"[0-9]{4}",match["labels"]),
                                               re.findall(_frozen_labels._DATE,match["ends"],re.I))]
            if mapping == item["mapping"]:
                prefix = item["text"][:match.start()]
                # The immediately governing sentence, not another sentence in
                # the same HTML paragraph, supplies conditional/example scope.
                contexts.append(re.split(r"[.!?]",prefix)[-1])
        reason = ("DEFINITION_CONDITIONAL_NOT_ADOPTED" if any(_CONDITIONAL_DEFINITION.search(c) for c in contexts)
                  else "DEFINITION_HYPOTHETICAL_NOT_ACTUAL" if any(_HYPOTHETICAL_DEFINITION.search(c) for c in contexts)
                  else None)
        if reason:
            rejected.append({**item, "reason": reason})
        else:
            definitions.append(item)
    if not rejected:
        return inspected
    unparsed = [*inspected["unsupported_definition_leads"],
                *({"block_index":item["block_index"], "text":item["text"], "reason":item["reason"]}
                  for item in rejected)]
    labels, status, proposed = _status(inspected, definitions, unparsed)
    body = {key:value for key,value in inspected.items() if key != "inspection_id"}
    body.update(source_definitions=definitions, unsupported_definition_leads=unparsed,
                current_definition_labels=labels, status=status,
                source_defined_fiscal_year=proposed, new_rule_label_proposal=proposed,
                definition_assertion_scope_rule=ASSERTION_SCOPE_RULE,
                rejected_non_actual_definitions=rejected,
                recognized_mapping_inspection_id=inspected["inspection_id"])
    canonical_json_bytes(value=body)
    return {**body, "inspection_id":content_hash(value=body)}
