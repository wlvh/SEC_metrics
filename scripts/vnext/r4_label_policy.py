"""The single approved R4 label change, selected from a bound Requirement."""

CURRENT_R4_REQUIREMENT = "issue_28_v3"
RAW_LABEL_POLICY = "EXACT_RAW_TEXT_V1"
SOURCE_LABEL_POLICY = "EXACT_SOURCE_RAW_OR_TEXT_V2"
SOURCE_LABEL_POLICY_CANDIDATE = "EXACT_SOURCE_RAW_OR_TEXT_V2_OFFLINE_CANDIDATE"
DECISION_ID = "S-R4-LABEL-REPRESENTATION"


def approved_label_choice():
    return {"kind": "R4_SOURCE_LABEL_REPRESENTATION", "ratchet_id": "R4",
        "policy": SOURCE_LABEL_POLICY, "accepted_cell_fields": ["raw_text", "text"],
        "authoritative_cell_field": "raw_text", "caption_policy": RAW_LABEL_POLICY,
        "source_and_geometry_verification_required": True,
        "value_unit_period_scope_cross_table_ambiguity_rules": "UNCHANGED",
        "response_rewrite_allowed": False, "historical_reinterpretation_allowed": False,
        "fuzzy_matching_or_locator_search_allowed": False,
        "old_call_authorization_reuse_allowed": False}


def label_policy(requirement):
    """Only loaded, exact version policy is used by normal acceptance/replay."""
    decision = requirement.get("effective_decisions", {}).get(DECISION_ID)
    if decision is None:
        if requirement.get("requirement_id") == CURRENT_R4_REQUIREMENT:
            raise ValueError("Current R4 Requirement lacks its label policy")
        return RAW_LABEL_POLICY
    if (requirement.get("requirement_id") != CURRENT_R4_REQUIREMENT
            or requirement.get("requirement_generation") != "PROFILE_DRIVEN_V4"
            or decision.get("status") != "APPROVED"
            or decision.get("choice") != approved_label_choice()):
        raise ValueError("R4 bound label policy differs")
    return SOURCE_LABEL_POLICY


def corpus_root(requirement_id):
    if requirement_id == "issue_28_v2":
        return "docs/r4_offline/qualified_cases"
    if requirement_id == CURRENT_R4_REQUIREMENT:
        return "docs/r4_v3/qualified_cases"
    raise ValueError("Unknown R4 execution version")


def corpus_index(requirement_id):
    return corpus_root(requirement_id) + "/index.json"


def release_plan_id(requirement_id):
    corpus_root(requirement_id)
    return "issue_28_r4_scoped_engine_" + requirement_id.rsplit("_", 1)[1]
