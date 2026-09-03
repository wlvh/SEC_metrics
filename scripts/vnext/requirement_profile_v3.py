"""Retained V3 engine for owner-approved, bounded offline policy revisions.

V1/V2 remain untouched. This engine composes their strict file, Decision-chain,
typed safety and fragment validators with exact multi-policy Issue comments.
Policy approval is not activation, live execution, or publication authority.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Mapping

from . import requirement_profile_v1 as v1
from .canonical import content_hash, sha256_file, strict_json_loads

PROFILE_REQUIREMENT_GENERATION = "PROFILE_DRIVEN_V3"
PROFILE_SEMANTIC_VERSION = "3"
OWNER_COMMENT_KIND = "OWNER_ISSUE_COMMENT_POLICY"
COMMENT_COMPONENT_KINDS = {
    "a12_scope_policy": "SOURCE_BOUND_COMPOSITE_SCOPE_POLICY",
    "a03_scope_policy": "SOURCE_BOUND_COMPOSITE_SCOPE_POLICY",
    "a03_alternate_period_policy": "SOURCE_BOUND_ALTERNATE_PERIOD_POLICY",
    "a13_product_semantics": "INTERNATIONAL_NET_REVENUE_POLICY",
    "parser_resource_policy": "BOUNDED_PARSER_RESOURCE_POLICY",
    "sec_acquisition": "OFFLINE_FIXTURE_ACQUISITION_POLICY",
}
SCOPE_DIMENSIONS = {
    "A03": {"entity_scope", "aggregation"},
    "A12": {"confidence_level", "holding_period"},
}


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise v1.RequirementProfileError(label)


def _booleans(choice: Mapping, *, true_fields=(), false_fields=()) -> None:
    for name in true_fields:
        _require(choice.get(name) is True, "Required safety bound differs: " + name)
    for name in false_fields:
        _require(choice.get(name) is False, "Forbidden safety relaxation: " + name)


def _composite_scope(*, choice: Mapping) -> dict:
    metric = choice.get("metric_id")
    fields = {
        "kind", "metric_id", "mechanism", "numeric_value_locator",
        "scope_dimensions_allowed_from_text_span", "required_scope",
        "text_span_requirements", "provider_payload_remains_table_window_only",
        "ai_or_fuzzy_span_selection_allowed", "cross_source_scope_evidence_allowed",
        "copying_text_into_table_or_caption_allowed",
    }
    if metric == "A12":
        fields.add("amount_scale_locator")
        _require(choice.get("amount_scale_locator") == "SAME_TARGET_TABLE_HEADER_REQUIRED",
                 "A12 amount scale must remain in target table")
    v1._exact_fields(value=choice, expected=fields, label="Composite scope policy")
    _require(metric in SCOPE_DIMENSIONS, "Composite scope metric is not approved")
    dimensions = choice["scope_dimensions_allowed_from_text_span"]
    _require(type(dimensions) is list and len(dimensions) == 2
             and set(dimensions) == SCOPE_DIMENSIONS[metric],
             "Composite scope dimensions differ")
    expected_scope = ({"entity_scope": "firm", "aggregation": "average"}
                      if metric == "A03" else
                      {"confidence_level": "ninety_five_percent", "holding_period": "one_day"})
    _require(choice["required_scope"] == expected_scope, "Composite required scope differs")
    _require(choice["mechanism"] == "SOURCE_BOUND_COMPOSITE_SCOPE_PROOF_V1"
             and choice["numeric_value_locator"] == "SAME_TARGET_TABLE_CELL_REQUIRED",
             "Composite numeric/source mechanism differs")
    span = v1._mapping(value=choice["text_span_requirements"], label="Span requirements")
    span_fields = {"same_source_sha_and_accession", "exact_byte_offsets_and_span_sha256",
                   "deterministic_target_table_association", "all_competing_scope_spans_dispositioned",
                   "conflicting_scope_blocks_auto_certification"}
    span_fields.add("same_named_liquidity_section" if metric == "A03" else "same_named_market_risk_section")
    v1._exact_fields(value=span, expected=span_fields, label="Span requirements")
    _booleans(span, true_fields=span_fields)
    _booleans(choice, true_fields=("provider_payload_remains_table_window_only",),
              false_fields=("ai_or_fuzzy_span_selection_allowed", "cross_source_scope_evidence_allowed",
                            "copying_text_into_table_or_caption_allowed"))
    return dict(choice)


def _alternate_period(*, choice: Mapping) -> dict:
    v1._exact_fields(value=choice, expected={
        "kind", "metric_id", "source_id", "fixture_class", "averaging_period",
        "exact_disclosed_period_must_be_bound", "must_not_claim_annual_average",
        "other_metric_period_semantics_unchanged",
    }, label="Alternate period policy")
    _require(choice["metric_id"] == "A03"
             and choice["fixture_class"] == "POSITIVE_ALTERNATE_LAYOUT"
             and choice["averaging_period"] == "AS_DISCLOSED_QUARTER_AVERAGE",
             "Alternate period authority differs")
    v1._text(value=choice["source_id"], label="Alternate source")
    _booleans(choice, true_fields=("exact_disclosed_period_must_be_bound",
                                  "must_not_claim_annual_average",
                                  "other_metric_period_semantics_unchanged"))
    return dict(choice)


def _international_revenue(*, choice: Mapping) -> dict:
    v1._exact_fields(value=choice, expected={
        "kind", "metric_id", "economic_measure", "explicitly_not_net_income",
        "geography_scope", "period", "canonical_unit", "preferred_selection",
        "regional_sum_allowed_only_when", "excluded_measure_families",
        "no_independent_legacy_anchor_controls_remain_required",
    }, label="International revenue policy")
    _require(choice["metric_id"] == "A13"
             and choice["economic_measure"] == "INTERNATIONAL_NET_REVENUE"
             and choice["geography_scope"] == "ISSUER_DISCLOSED_NON_US_OR_INTERNATIONAL"
             and choice["period"] == "FULL_FISCAL_YEAR_DURATION"
             and choice["canonical_unit"] == "USD"
             and choice["preferred_selection"] == "DIRECT_ISSUER_DISCLOSED_INTERNATIONAL_TOTAL",
             "International revenue semantics differ")
    _booleans(choice, true_fields=("explicitly_not_net_income",
                                  "no_independent_legacy_anchor_controls_remain_required"))
    rules = v1._mapping(value=choice["regional_sum_allowed_only_when"], label="Regional sum")
    rule_fields = {"leaf_regions_are_mutually_exclusive", "concept_unit_period_and_non_geography_context_match",
                   "no_parent_child_geography_overlap", "reconciles_to_global_total_minus_us_total"}
    v1._exact_fields(value=rules, expected=rule_fields, label="Regional sum")
    _booleans(rules, true_fields=rule_fields)
    excluded = choice["excluded_measure_families"]
    _require(type(excluded) is list and len(excluded) == 7 and set(excluded) == {
        "NET_INCOME", "ASSETS", "LOANS", "DEPOSITS", "MATURITY_SCHEDULES",
        "SEGMENT_ONLY_TOTALS", "GLOBAL_TOTAL",
    }, "Revenue exclusions differ")
    return dict(choice)


def _parser_resource(*, choice: Mapping) -> dict:
    required = {"production_max_total_cells_may_increase",
                "actual_limit_must_be_minimum_sufficient_after_jpm_bac_citi_measurement",
                "same_production_parser_must_parse_all_r4_sources",
                "guarded_worker_must_stop_overriding_production_resource_limits",
                "other_resource_limits_must_remain_unchanged",
                "all_sources_must_pass_512_mib_no_swap_measurement",
                "over_250000_or_unsafe_memory_requires_new_owner_escalation"}
    v1._exact_fields(value=choice, expected={"kind", "maximum_authorized_total_cells",
                                           "runtime_or_caller_limit_override_allowed"} | required,
                     label="Parser resource policy")
    cap = choice["maximum_authorized_total_cells"]
    _require(type(cap) is int and 100000 <= cap <= 250000, "Parser safety ceiling differs")
    _booleans(choice, true_fields=required, false_fields=("runtime_or_caller_limit_override_allowed",))
    return dict(choice)


def _acquisition(*, choice: Mapping) -> dict:
    v1._exact_fields(value=choice, expected={"kind", "existing_two_filing_quota_may_proceed",
        "sources", "automatic_retry_count", "contact_environment_prerequisite_is_now_available"},
        label="Offline acquisition policy")
    sources = v1._string_list(value=choice["sources"], label="Acquisition sources")
    _require(len(sources) == 2 and type(choice["automatic_retry_count"]) is int
             and choice["automatic_retry_count"] == 0, "Acquisition quota/retry differs")
    _booleans(choice, true_fields=("existing_two_filing_quota_may_proceed",
                                  "contact_environment_prerequisite_is_now_available"))
    return dict(choice)


def single_table_scope_rule() -> dict:
    """Keep the default rule, with only the two explicitly approved exceptions."""
    return {"default_same_target_table_required": True,
            "numeric_value_same_target_table_required": True,
            "amount_scale_same_target_table_required": True,
            "exceptions": [{"metric_id": metric, "dimensions": sorted(dimensions)}
                           for metric, dimensions in sorted(SCOPE_DIMENSIONS.items())]}


def _inherited_semantics(*, choice: Mapping) -> dict:
    v1._exact_fields(value=choice, expected={"kind", "obligations", "single_table_scope_rule"},
                     label="Bounded inherited semantics")
    v1._parent_policy_carry_forward(choice={k: choice[k] for k in ("kind", "obligations")})
    _require(choice["single_table_scope_rule"] == single_table_scope_rule(),
             "Single-table scope exception was widened")
    return dict(choice)


EVALUATORS = {**v1.INVARIANT_EVALUATORS,
    "SOURCE_BOUND_COMPOSITE_SCOPE_POLICY": _composite_scope,
    "SOURCE_BOUND_ALTERNATE_PERIOD_POLICY": _alternate_period,
    "INTERNATIONAL_NET_REVENUE_POLICY": _international_revenue,
    "BOUNDED_PARSER_RESOURCE_POLICY": _parser_resource,
    "OFFLINE_FIXTURE_ACQUISITION_POLICY": _acquisition,
    "PARENT_POLICY_CARRY_FORWARD": _inherited_semantics,
}


def _owner_documents(*, baseline: Mapping, parent: Mapping) -> dict:
    """Validate original comment text, metadata and absent execution grants."""
    inherited = {s["source_id"]: s for s in parent["baseline"]["policy_evidence"]}
    ancestors = {}
    cursor = parent
    while cursor:
        ancestors[cursor["requirement_id"]] = cursor["requirement_closure_hash"]
        cursor = cursor.get("parent_snapshot")
    documents = {}
    source_ids = []
    for source in baseline["policy_evidence"]:
        source_ids.append(source["source_id"])
        if source["source_id"] in inherited:
            _require(source == inherited[source["source_id"]], "Inherited comment bytes differ")
        if source["kind"] != OWNER_COMMENT_KIND:
            _require(inherited.get(source["source_id"]) == source, "Inherited policy evidence differs")
            continue
        v1._exact_fields(value=source, expected={"source_id", "kind", "source_url", "source_sha256",
                                               "author", "published_at_utc", "text", "evidence_path"}, label="Owner comment")
        _require(source["source_url"].startswith(baseline["issue"]["url"] + "#issuecomment-")
                 and source["source_url"] != baseline["issue"]["identifier_comment_url"]
                 and source["author"] == "github:" + baseline["repository"]["identity"].split("/")[0]
                 and source["source_sha256"] == v1.sha256_bytes(content=source["text"].encode()),
                 "Owner comment identity differs")
        v1.parse_utc_timestamp(value=source["published_at_utc"])
        document = strict_json_loads(text=source["text"])
        _require(isinstance(document, dict) and document.get("decision") in {
            "APPROVE_R4_PRB_POLICY_REVISION", "APPROVE_R4_A03_COMPOSITE_SCOPE_AND_ALTERNATE_PERIOD"},
            "Unknown owner policy approval")
        _require(document["scope"] == "PR_B_OFFLINE_IMPLEMENTATION_ONLY"
                 and ancestors.get(document["predecessor_requirement_id"])
                 == document["predecessor_requirement_closure_hash"]
                 and document["active_publication_must_remain"] == "R3", "Owner policy predecessor/scope differs")
        _booleans(document, false_fields=("provider_calls_authorized", "paid_model_calls_authorized",
                                          "live_qualification_authorized", "publication_authorized"))
        if document["decision"].startswith("APPROVE_R4_A03_"):
            _booleans(document, false_fields=("additional_sec_acquisitions_authorized",
                                              "transition_activation_authorized", "merge_authorized"))
        documents[source["source_id"]] = (source, document)
    _require(source_ids == sorted(set(source_ids)), "Policy source IDs are not exact/unique")
    _require(len(documents) == 2 and set(inherited).issubset(source_ids), "Owner policy evidence is incomplete")
    approvals = list(documents.values())
    _require(len({source["source_url"] for source, _ in approvals}) == len(approvals),
             "Different policy captures cannot claim the same immutable comment")
    first = next((source for source, doc in approvals
                  if doc["decision"] == "APPROVE_R4_PRB_POLICY_REVISION"), None)
    second = next(((source, doc) for source, doc in approvals
                   if doc["decision"] == "APPROVE_R4_A03_COMPOSITE_SCOPE_AND_ALTERNATE_PERIOD"), None)
    _require(first is not None and second is not None
             and second[1]["predecessor_policy_comment_url"] == first["source_url"],
             "Supplemental policy comment predecessor differs")
    return documents


def _validate_comment_capture(*, baseline: Mapping, repo_root: Path) -> None:
    """Bind embedded approval content to the independently captured comment."""
    for source in baseline["policy_evidence"]:
        if source["kind"] != OWNER_COMMENT_KIND:
            continue
        relative = source["evidence_path"]
        _require(type(relative) is str and relative.startswith("docs/evidence/")
                 and Path(relative).as_posix() == relative and ".." not in Path(relative).parts,
                 "Owner capture path is unsafe")
        path = repo_root
        for part in Path(relative).parts:
            path = path / part
            _require(not path.is_symlink(), "Owner capture path contains an alias")
        capture = v1.read_requirement_object(path=path)
        binding = baseline["execution_authority"]["files"].get(relative)
        _require(binding == {"sha256": sha256_file(path=path), "size": path.stat().st_size},
                 "Owner capture is not bound by the execution closure")
        _require(capture["record_type"] == "OWNER_POLICY_COMMENT_EVIDENCE"
                 and capture["evidence_scope"] == "POLICY_CONTENT_ONLY"
                 and capture["owner_comment_url"] == source["source_url"]
                 and capture["author"] == source["author"]
                 and capture["published_at_utc"] == source["published_at_utc"]
                 and capture["raw_body"] == source["text"]
                 and capture["body_sha256"] == source["source_sha256"]
                 and capture["transition_activation"] == "NOT_ISSUED"
                 and capture["provider_paid_live_publication_authorization"] is False,
                 "Owner capture and policy provenance differ")


def _validate_decisions(*, decisions: Mapping, chains: Mapping, parent: Mapping,
                        owner_documents: Mapping) -> None:
    originals = {v1.decision_record_hash(decision=d) for values in parent["decision_chains"].values()
                 for d in values}
    required_obligations = [r for r in parent["effective_decisions"]["S-INHERITED-SEMANTICS"]["choice"]["obligations"]
                            if not (r["decision_id"] == "D-32" and r["source_path"] == "/single_table_locator_invariant")]
    introduced = [(decision_id, record) for decision_id, records in chains.items() for record in records]
    for decision_id, decision in introduced:
        if v1.decision_record_hash(decision=decision) in originals:
            continue
        _require(decision["status"] == "APPROVED", "New Decision is not approved")
        provenance = decision.get("policy_provenance", {})
        v1._exact_fields(value=provenance, expected={"source_id", "section", "scope"}, label="Policy provenance")
        _require(provenance.get("source_id") in owner_documents and provenance["scope"] == "POLICY_CONTENT_ONLY",
                 "New Decision lacks owner policy-content evidence")
        source, document = owner_documents[provenance["source_id"]]
        _require(decision["approved_by"] == source["author"]
                 and decision["approved_at_utc"] == source["published_at_utc"]
                 and decision["evidence"] == source["source_url"], "Decision approval metadata differs")
        choice = decision["choice"]
        if choice["kind"] == "PARENT_POLICY_CARRY_FORWARD":
            original = parent["effective_decisions"][decision_id]
            _require(decision["supersedes_decision_id"] == v1.decision_record_hash(decision=original)
                     and len(chains[decision_id]) == 2 and choice["obligations"] == required_obligations
                     and provenance["section"] == "a03_scope_policy", "Inherited scope revision differs")
            continue
        section = provenance["section"]
        _require(section in COMMENT_COMPONENT_KINDS and section in document
                 and choice["kind"] == COMMENT_COMPONENT_KINDS[section], "Policy component differs")
        _require(decision_id not in parent["effective_decisions"]
                 and decision["supersedes_decision_id"] is None and len(chains[decision_id]) == 1,
                 "New policy history is not approved by its comment")
        claimed = {k: v for k, v in choice.items() if k != "kind"}
        if section == "a03_alternate_period_policy":
            _require(claimed.pop("metric_id", None) == document["a03_scope_policy"]["metric_id"],
                     "Period approval was applied to another metric")
        _require(claimed == document[section], "Decision content is not approved by its evidence")


def _load_profile_requirement_snapshot(*, snapshot_dir: Path,
                                       parent_loader: Callable[..., Mapping]) -> dict:
    """Load the exact five-file revision without editing any retained engine."""
    _require(snapshot_dir.is_dir() and not snapshot_dir.is_symlink(), "Unsafe snapshot directory")
    _require(not snapshot_dir.parent.is_symlink() and not snapshot_dir.parent.parent.is_symlink(),
             "Requirement container/root cannot be a symlink")
    entries = list(snapshot_dir.iterdir())
    _require({p.name for p in entries} == v1.PROFILE_SNAPSHOT_FILES
             and all(p.is_file() and not p.is_symlink() for p in entries), "Snapshot file set differs")
    baseline = v1.read_requirement_object(path=snapshot_dir / "baseline_manifest.json")
    core_view = {**baseline, "policy_evidence": [s for s in baseline["policy_evidence"] if s["kind"] != OWNER_COMMENT_KIND]}
    v1._validate_baseline(baseline=core_view, snapshot_dir=snapshot_dir,
        generation=PROFILE_REQUIREMENT_GENERATION, semantic_version=PROFILE_SEMANTIC_VERSION,
        engine_file=Path(__file__), engine_dependencies=(Path(v1.__file__),))
    parent_binding = baseline["parent"]
    parent_id = parent_binding["requirement_id"]
    requirement_id = baseline["requirement_id"]
    current_match = re.fullmatch(r"issue_([0-9]+)_v([1-9][0-9]*)", requirement_id)
    previous_match = re.fullmatch(r"issue_([0-9]+)_v([1-9][0-9]*)", parent_id)
    _require(current_match is not None and previous_match is not None
             and current_match[1] == previous_match[1] and int(current_match[2]) > int(previous_match[2]),
             "Requirement revision identity differs")
    parent_dir = snapshot_dir.parent / parent_id
    parent = parent_loader(snapshot_dir=parent_dir)
    for field in ("active_publication", "historical_archive", "issue"):
        _require(baseline[field] == parent["baseline"][field],
                 "Historical baseline binding differs: " + field)
    _require(baseline["supersedes_requirement"] == {"requirement_id": parent_id,
             "requirement_closure_hash": parent["requirement_closure_hash"]}
             and parent_binding["requirement_closure_hash"] == parent["requirement_closure_hash"]
             and parent_binding["hashes"] == parent["hashes"]
             and parent_binding["snapshot_binding_hash"] == content_hash(value=parent_binding["snapshot_files"]),
             "Parent/revision closure differs")
    v1._verify_bound_files(root=parent_dir, bindings=parent_binding["snapshot_files"],
                          expected_files=v1.PROFILE_SNAPSHOT_FILES, label="Parent snapshot")
    documents = _owner_documents(baseline=baseline, parent=parent)
    _validate_comment_capture(baseline=baseline, repo_root=snapshot_dir.parent.parent)
    register = v1.read_requirement_object(path=snapshot_dir / "decision_register.json")
    v1._exact_fields(value=register, expected={"schema_version", "record_type", "requirement_id",
        "issue_contract_revision", "decisions", "pending_decisions"}, label="Decision Register")
    _require(register["schema_version"] == 2 and register["record_type"] == "REQUIREMENT_DECISION_REGISTER"
             and register["requirement_id"] == requirement_id
             and register["issue_contract_revision"] == baseline["contract_revision"], "Register identity differs")
    decisions, chains = v1.resolve_decision_chains(decisions=register["decisions"] + register["pending_decisions"])
    _validate_decisions(decisions=decisions, chains=chains, parent=parent, owner_documents=documents)
    profile = v1.read_requirement_object(path=snapshot_dir / "invariant_profile.json")
    evaluated = v1.evaluate_invariant_profile(profile=profile, requirement_id=requirement_id,
        effective_decisions=decisions, semantic_version=PROFILE_SEMANTIC_VERSION, evaluators=EVALUATORS)
    values = {}
    scopes = set()
    for row in evaluated["by_invariant_id"].values():
        kind, value = row["kind"], row["value"]
        scope = value.get("ratchet_id", value.get("metric_id", "GLOBAL"))
        _require((kind, scope) not in scopes, "Duplicate invariant scope")
        scopes.add((kind, scope)); values.setdefault(kind, []).append(value)
    _require(v1.SUPPORTED_INVARIANT_KINDS.issubset(values)
             and set(COMMENT_COMPONENT_KINDS.values()).issubset(values), "Required safety invariant is absent")
    _require({v["metric_id"] for v in values["SOURCE_BOUND_COMPOSITE_SCOPE_POLICY"]} == set(SCOPE_DIMENSIONS),
             "Composite approval set differs")
    for kind in ("PROVIDER_TRANSPORT_POLICY", "TEST_POLICY", "HISTORICAL_EVIDENCE_POLICY",
                 "ARTIFACT_REQUIREMENT_IDENTITY", "RATCHET_SCOPE", "LIVE_CALL_BOUND",
                 "PUBLICATION_PREDECESSOR", "SOURCE_SCOPE_POLICY", "SESSION_RESOURCE_POLICY",
                 "DELIVERY_SEPARATION_POLICY", "EVIDENCE_RESULT_POLICY", "SECURITY_BOUNDARY_POLICY",
                 "TRANSPORT_RETRY_POLICY"):
        prior = [d["choice"] for d in parent["effective_decisions"].values() if d.get("choice", {}).get("kind") == kind]
        _require(values[kind] == prior, "Revision changed an unapproved inherited policy: " + kind)
    transfer = v1.read_requirement_object(path=snapshot_dir / "transfer_manifest.json")
    pending_rows = transfer.get("pending_decision_transfers")
    approved_parent = {**parent, "effective_decisions": {k: d for k, d in parent["effective_decisions"].items() if d["status"] == "APPROVED"}}
    transfer_view = {k: v for k, v in transfer.items() if k != "pending_decision_transfers"}
    _require(transfer_view["schema_version"] == 3, "Revision transfer generation differs")
    transfer_view["schema_version"] = 2
    transfer_result = v1._validate_transfer(transfer=transfer_view, requirement_id=requirement_id,
        parent=approved_parent, current_decisions=decisions, parent_snapshot_dir=parent_dir,
        parent_snapshot_files=parent_binding["snapshot_files"])
    expected_replaced = set()
    prior_obligations = parent["effective_decisions"]["S-INHERITED-SEMANTICS"]["choice"]["obligations"]
    for index, obligation in enumerate(prior_obligations):
        if obligation["decision_id"] == "D-32" and obligation["source_path"] == "/single_table_locator_invariant":
            expected_replaced.update(("S-INHERITED-SEMANTICS", "/obligations/{}/{}".format(index, field))
                                     for field in ("decision_id", "source_path", "source_value_hash"))
    for row in transfer_result["fragments"]:
        replaced = (row["decision_id"], row["source_path"]) in expected_replaced
        _require(row["disposition"] == ("SUPERSEDED" if replaced else "CARRY_FORWARD"),
                 "Revision disposition changes an unapproved semantic obligation")
        if replaced:
            _require(row["successor_decision_id"] == "S-INHERITED-SEMANTICS"
                     and row["successor_path"] == "/single_table_scope_rule",
                     "D-32 exception transfer target differs")
    expected_pending = []
    for decision_id, prior in parent["effective_decisions"].items():
        if prior["status"] != "PENDING_EXTERNAL_APPROVAL":
            continue
        _require(decisions.get(decision_id) == prior, "Pending policy was activated without approval")
        expected_pending.append({"decision_id": decision_id, "disposition": "CARRY_FORWARD",
            "parent_record_hash": v1.decision_record_hash(decision=prior), "qualification_credit": "NONE"})
    _require(pending_rows == expected_pending, "Pending policy transfer differs")
    hashes = {"baseline_sha256": sha256_file(path=snapshot_dir / "baseline_manifest.json"),
        "contract_sha256": sha256_file(path=snapshot_dir / "CONTRACT.md"),
        "decision_register_sha256": sha256_file(path=snapshot_dir / "decision_register.json"),
        "invariant_profile_sha256": sha256_file(path=snapshot_dir / "invariant_profile.json"),
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "transfer_manifest_sha256": sha256_file(path=snapshot_dir / "transfer_manifest.json"),
        "validator_sha256": baseline["validator"]["sha256"]}
    return {"artifact_requirement_generation": baseline["artifact_requirement_generation"],
        "baseline": baseline, "decision_chains": chains, "effective_decisions": decisions,
        "evaluated_invariants": evaluated, "hashes": hashes,
        "issue_contract_revision": register["issue_contract_revision"],
        "parent_requirement_closure_hash": parent["requirement_closure_hash"],
        "parent_requirement_id": parent_id, "pending_decision_ids": [r["decision_id"] for r in expected_pending],
        "requirement_closure_hash": content_hash(value=hashes),
        "requirement_generation": PROFILE_REQUIREMENT_GENERATION, "requirement_id": requirement_id,
        "transfer": {**transfer_result, "pending_decision_transfers": pending_rows},
        "parent_snapshot": parent, "execution_authority": baseline["execution_authority"],
        "activation_state": baseline["activation_state"]}


def load_profile_requirement_snapshot(*, snapshot_dir: Path,
                                      parent_loader: Callable[..., Mapping]) -> dict:
    """Turn malformed untrusted JSON shapes into stable Requirement failures."""
    try:
        return _load_profile_requirement_snapshot(snapshot_dir=snapshot_dir,
                                                  parent_loader=parent_loader)
    except (KeyError, TypeError, IndexError, v1.CanonicalError) as error:
        raise v1.RequirementProfileError("Malformed V3 Requirement: " + str(error)) from error
