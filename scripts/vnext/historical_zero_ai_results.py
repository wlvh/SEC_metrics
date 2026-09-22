"""Rebuild the revenue route for an explicitly selected historical period.

Like ``historical_results``, this is a source adapter rather than a second
calculator: the installed B01/B03 Spec documents, ``_structured_concepts``,
``companyfacts_structured_facts``, ``adapt_companyfacts`` and ``calculate_metric``
are imported unchanged from the frozen modules. What this module owns is which
filing the Company Facts accession role means when the period is pinned.

It exists as a successor file because ``scripts/vnext/normal_zero_ai_results.py``
is byte-bound by the ``issue_28_v13`` rule set; changing it would stop every
existing ordinary Run from loading its own Requirement.

Only the revenue routes are wired for a successor registrant's own statement
values; that one stays an explicit implementation gap. The event routes are
wired for both continuity modes, because an event window is not a statement
period: the approved policy widens it to the prior calendar year's start for a
successor registrant, and the filings it then names belong to the registered
predecessor as well as to the successor. That widening is the event
measurement, not the Run's coordinate, and the two are kept apart - see
``event_measurement_window`` below and ``historical_results._run_coordinate``.
No cross-entity financial combination is authorised by any of this.
"""
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .annual_update import AnnualUpdateError
from .batch_workflow import BatchWorkflowError, _structured_concepts
from .calculator import (calculate_metric, calculate_observation_metric,
                         withheld_metric_result)
from .canonical import content_hash, sha256_file, strict_json_loads
from .historical_annual_input import prepare_historical_annual_input
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources, NormalGovernanceInputError
from .normal_zero_ai_results import (B01_SPEC_PATH, B03_SPEC_PATH, EVENT_METRICS,
                                     NormalZeroAiError, _authority, _compiled_event_spec,
                                     _event_sources, _exact_set, _registered_event_sources)
from .observations import structured_observation
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import companyfacts_structured_facts, SourceError
from .specs import compile_spec_file
from .traits import repository_company_traits
from .deterministic_router import (adapt_companyfacts, load_event_route_catalog,
                                   project_event_result)


RECORD_TYPE = "HISTORICAL_ZERO_AI_SOURCE_RESULT"
SUPPORTED_METRICS = ("B01", "B03", *EVENT_METRICS)
_SOURCE_ERRORS = (NormalZeroAiError, NormalGovernanceInputError, AnnualUpdateError,
                  BatchWorkflowError, SourceError)


class _EventRouteResolved(Exception):
    """Control flow only: the event branch finished and skips the facts branch.

    Raised and caught inside one function so the two routes keep the same
    ``except`` clause for real source failures rather than duplicating it.
    """


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalZeroAiError(reason, category)


def event_measurement_window(*, repo_root: Path, company_id: str, pinned, registered_event):
    """The window an event metric measures, which is not the Run's coordinate.

    For a continuous primary registrant the two are the same period and this
    returns the pinned one unchanged. For a successor registrant the approved
    policy widens the event window to the prior calendar year's start, because
    the events of the pinned year were filed partly by the predecessor - and
    the widened window is a measurement, not a fiscal coordinate. Truncating
    the sources to fit the coordinate would drop real filings; widening the
    coordinate to fit the sources would claim a fiscal year longer than 53
    weeks. So they stay separate and the Run records both.

    ``registered_event_scope`` is the evidence for that: the registered CIKs,
    the window, and the explicit statement that no cross-entity financial
    combination is authorised by widening an event window.
    """
    if not registered_event:
        return pinned, None
    from .public_projection import event_target_period
    from .traits import repository_company_ciks
    catalog = strict_json_loads(
        text=(Path(repo_root) / "catalog/zero_ai_public_projection.json").read_text(
            encoding="utf-8"))
    window = event_target_period(target_period=pinned,
                                 continuity_status="successor_predecessor",
                                 catalog=catalog)
    scope = {"registered_ciks": repository_company_ciks(repo_root=repo_root,
                                                        company_id=company_id),
             "window": window, "pinned_period": dict(pinned),
             "status": "SOURCE_RECONSTRUCTION_PENDING",
             "financial_cross_entity_combination_authorized": False}
    return window, scope


INCOME_STATEMENT_METRICS = frozenset({"B01", "B03"})


def _successor_income_input(*, repo_root: Path, company_id: str, metric_id: str, prepared):
    """The ordinary current-income proof, when it is about this exact target.

    The ordinary route builds this for a successor registrant's B01 and B03
    because the successor's own statement values need a proof of which period
    the income statement actually covers. It is built against the current
    period and names the filing it proved, so it transfers to a historical
    target only when that filing is this target - otherwise it would be a
    proof about one report being used to admit another, which is the failure
    this whole route exists to avoid. Anything else returns None and the
    caller keeps the named gap.
    """
    if (metric_id not in INCOME_STATEMENT_METRICS
            or prepared["subject_policy"]["mode"] != "SUCCESSOR_REGISTRANT_ONLY"):
        return None
    from .ordinary_income_input import prepare_current_income_input
    income_input = prepare_current_income_input(repo_root=repo_root, company_id=company_id)
    proved = income_input["annual_input"]["filing"]["accessionNumber"]
    if proved != prepared["filing"]["accessionNumber"]:
        return None
    return income_input


def resolve_historical_zero_ai_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                      period_selection):
    """Resolve revenue, or EBITDA margin with its rebuilt revenue dependency.

    Values come from the selected filing's own accession, which is the same
    first-report semantics the current route uses, applied to a past target.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_ZERO_AI_METRIC_NOT_WIRED:" + metric_id, "IMPLEMENTATION_GAP")
    authority = _authority(repo_root)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    # See historical_amendment_admission: the approved policy decides these
    # shapes per input class, so an event metric and a statement metric can get
    # different answers on the same amendment - which is the point, because a
    # Part III addition leaves the event window alone and does not clear the
    # statement values.
    pinned = prepared["table_input"]["target_period"]
    registered_event = (metric_id in EVENT_METRICS
                        and prepared["subject_policy"]["mode"] == "SUCCESSOR_REGISTRANT_ONLY")
    # A successor registrant's own statement values need the current income
    # input the ordinary route builds. That input is defined against the
    # current period and carries its own approved amendment proof - the
    # registrant's original HTML, XML and Company Facts, the period it
    # actually reports, and a Part III revenue-correction check - so where it
    # describes this target it applies verbatim, and where it does not the gap
    # stands and says so. An event window needs none of it.
    income_input = _successor_income_input(repo_root=repo_root, company_id=company_id,
                                           metric_id=metric_id, prepared=prepared)
    _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY" or registered_event
          or income_input is not None,
          "HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED", "IMPLEMENTATION_GAP")
    # Asked after the income input, because that input is the narrower proof
    # for exactly this case and the ordinary route uses it in place of the
    # family question. Every other shape still asks the family question first.
    if prepared["amendments"] and income_input is None:
        from .historical_amendment_admission import (AmendmentAdmissionError,
                                                     amendment_admission)
        try:
            amendment_admission(repo_root=repo_root, company_id=company_id,
                                metric_ids=[metric_id], prepared=prepared,
                                event_metric_ids=EVENT_METRICS)
        except AmendmentAdmissionError as error:
            _need(False, str(error), "SOURCE_SCOPE_NOT_CLEARED")
    period, registered_scope = event_measurement_window(
        repo_root=repo_root, company_id=company_id, pinned=pinned,
        registered_event=registered_event)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),
                            role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    facts_source = reader.read(companyfacts_url(cik=int(prepared["entity"])),
                               accession=prepared["filing"]["accessionNumber"],
                               role="companyfacts", media_type="application/json")
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    dependency_specs = {}
    catalog = None
    if metric_id in EVENT_METRICS:
        # The event window is the measurement window, which for a continuous
        # primary registrant is the pinned period's own start and end. Nothing
        # here reads "today": both come from
        # prepared["table_input"]["target_period"], which historical_annual_input
        # sets to the selected period rather than the latest one.
        catalog = load_event_route_catalog(repo_root=repo_root)
        spec_path = None
        spec_origin = {"catalog_path": "catalog/event_routes.json", "metric_id": metric_id}
        spec = _compiled_event_spec(metric_id=metric_id, route=catalog["routes"][metric_id])
        scope = {"coverage": "fiscal_year_source_set", "fiscal_year": period["fiscal_year"],
                 "shared_claim_group_id": catalog["routes"][metric_id]["shared_claim_group_id"]}
    else:
        spec_path = B01_SPEC_PATH if metric_id == "B01" else B03_SPEC_PATH
        spec_origin = {"spec_path": spec_path}
        if metric_id == "B03":
            dependency_specs["B01"] = compile_spec_file(path=repo_root / B01_SPEC_PATH,
                                                        dependency_specs={})
        spec = compile_spec_file(path=repo_root / spec_path, dependency_specs=dependency_specs)
        scope = {"entity_scope": "registrant", "period_basis": "source_annual_duration"}
    if income_input is not None:
        # The successor reports its own statement period, not the pinned
        # fiscal year, and the proof above is what establishes which one that
        # is. Leaving the pinned period here asked Company Facts for a year
        # this registrant never reported and got MISSING_CANDIDATE - an answer
        # about a period nobody filed, which is worse than the named gap it
        # replaced. The Run keeps the pinned coordinate; the result keeps the
        # measured window, the same separation the event window already uses.
        period = {**period, **income_input["statement_period"]}
    target = {"company_id": company_id, "period_start": period["period_start"],
              "period_end": period["period_end"], "scope": scope,
              "scope_key": scope_key(scope=scope)}
    claims, source_sets, observations, dependency_records = [], [], [], []
    filings = [prepared["filing"]]
    selection = {}
    try:
        if metric_id in EVENT_METRICS:
            if registered_event:
                # The predecessor's filings are read through the same reader,
                # from each registered CIK's own submissions, and their
                # accessions may not overlap. This is source discovery across
                # registered identities; it authorises no financial
                # combination, which the scope record states explicitly.
                claims, source_sets, events, evidence = _registered_event_sources(
                    repo_root=repo_root, reader=reader, prepared=prepared,
                    inventory=inventory, period=period)
                registered_scope = {**registered_scope, **evidence,
                                    "pinned_period": dict(pinned),
                                    "status": "SOURCE_RECONSTRUCTED_FROM_REGISTERED_CIKS"}
            else:
                claims, source_sets, events = _event_sources(
                    repo_root=repo_root, reader=reader, prepared=prepared, inventory=inventory)
            filings.extend(events)
            graph = project_event_result(
                metric_id=metric_id, claims=claims, source_set_manifest=source_sets[-1],
                inventory_source_reference=inventory["source_reference"],
                target_period=period, catalog=catalog)
            original = graph["observation"]
            # The inventory reference and the event collection are distinct
            # roles, exactly as the current route keeps them.
            binding = {**original["source_binding"],
                       "source_role": inventory["source_reference"]["source_role"],
                       "source_set_role": source_sets[-1]["source_role"]}
            observation = structured_observation(
                metric_id=metric_id, semantic_role=original["semantic_role"],
                company_id=company_id, period_start=period["period_start"],
                period_end=period["period_end"], scope=original["scope"],
                value=original["value"], unit=original["unit"],
                quality=original["quality"], source_binding=binding)
            result, trace = calculate_observation_metric(
                compiled_spec=spec, target=target, company_traits=traits,
                observation=observation)
            observations = [observation]
            selection = {"reason_code": result["reason_code"],
                         "matched_verified_claim_ids": graph["matched_verified_claim_ids"],
                         "source_event_accessions": sorted({f["accessionNumber"]
                                                            for f in events})}
            raise _EventRouteResolved
        manifest = _exact_set(prepared, inventory, facts_source, "companyfacts")
        source_sets = [manifest]
        approved = sorted(set(_structured_concepts(compiled_spec=spec)) | {
            concept for dependency in dependency_specs.values()
            for concept in _structured_concepts(compiled_spec=dependency)})
        facts = companyfacts_structured_facts(
            raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
            approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
        claims = adapt_companyfacts(
            raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
            source_set_manifest=manifest, approved_concepts=approved,
            allowed_ciks=[prepared["entity"]], include_instant=False)
        execution_target = {**target, "entity": prepared["entity"],
                            "accession": prepared["filing"]["accessionNumber"]}
        reusable = []
        for dependency in dependency_specs.values():
            dep_result, dep_trace, dep_observations = calculate_metric(
                compiled_spec=dependency, target=execution_target, company_traits=traits,
                structured_facts=facts, verified_observations=[])
            dependency_records.extend([*dep_observations, dep_trace, dep_result])
            reusable.extend(dep_observations)
        result, trace, observations = calculate_metric(
            compiled_spec=spec, target=execution_target, company_traits=traits,
            structured_facts=facts, verified_observations=reusable)
        selection = {"source_candidate_count": len(facts),
                     "selected_fact_ids": [o["source_binding"]["fact_id"] for o in observations],
                     "source_reported_periods": sorted({(f["period_start"], f["period_end"])
                                                        for f in facts}),
                     "reason_code": result["reason_code"]}
    except _EventRouteResolved:
        pass
    except _SOURCE_ERRORS as error:
        reason = str(error)
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code="HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED")
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": reason,
                     "category": getattr(error, "category", "SOURCE_INTEGRITY_ERROR")}
    if income_input is not None and observations:
        # The same check the ordinary route runs: the observations must be the
        # ones the income proof is about, so an admitted proof cannot stand
        # behind a value it never described.
        from .ordinary_income_input import verify_income_observations
        selection = {**selection,
                     "income_observation_checks": verify_income_observations(income_input,
                                                                             observations)}
    proofs = list({content_hash(value=p): p for p in
                   [*prepared["source_proofs"],
                    *([] if income_input is None else income_input["source_proofs"]),
                    *[entry["proof"] for entry in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    source_records = list({content_hash(value=r): r for r in
                           [*reader.records.values(),
                            *([] if income_input is None
                              else income_input["source_records"])]}.values())
    input_binding = {"prepared_input": prepared, "target": target, "target_period": period,
                     "period_selection": period_selection,
                     "amendment_input": (None if income_input is None else {
                         **income_input["amendment_input"],
                         "decision": "INPUT_PROPERTY_PROVEN",
                         "input_class": "CURRENT_ORIGINAL_INCOME_STATEMENT_VALUES",
                         "current_income_checks": income_input["amendment_checks"]}),
                     "current_income_input": (None if income_input is None
                                              else income_input["income_input_id"]),
                     "spec_origin": spec_origin,
                     "spec_closure_hash": spec["spec_closure_hash"],
                     "authority_file_hashes": authority,
                     "dependency_spec_closure_hashes": {key: value["spec_closure_hash"]
                                                        for key, value in dependency_specs.items()},
                     "source_proofs": proofs, "source_admission": admission,
                     "source_set_manifests": source_sets,
                     "failed_source_attempts": list(reader.failed_attempts.values()),
                     "selection": selection,
                     "resolver_sha256": sha256_file(path=Path(__file__))}
    if registered_scope is not None:
        input_binding["registered_event_scope"] = registered_scope
    body = {"record_type": RECORD_TYPE, "company_id": company_id, "metric_id": metric_id,
            "period_selection": period_selection, "spec_path": spec_path,
            "spec_origin": spec_origin, "compiled_spec": spec,
            "authority_file_hashes": authority, "dependency_specs": dependency_specs,
            "dependency_records": dependency_records, "input_binding": input_binding,
            "prepared_input": prepared, "target_period": period, "target": target,
            # The Run's coordinate is the pinned period, never the widened
            # event window. A reader of this component should not have to
            # infer which of the two a period field means.
            "pinned_target_period": dict(pinned),
            "registered_event_scope": registered_scope,
            "source_records": source_records,
            "source_references": [r for r in source_records
                                  if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": proofs, "source_admission": admission,
            "source_set_manifests": source_sets, "filings": filings,
            "claims": claims, "selection": selection, "observations": observations,
            "result": result, "trace": trace,
            "records": list({content_hash(value=r): r for r in
                             [*source_records, *dependency_records, *observations,
                              trace, result]}.values()),
            "failed_source_attempts": list(reader.failed_attempts.values()),
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_binding_id": content_hash(value=body["input_binding"]),
            "component_id": content_hash(value=body)}


def verify_historical_zero_ai_metric(*, candidate, repo_root: Path, company_id: str,
                                     metric_id: str, period_selection):
    rebuilt = resolve_historical_zero_ai_metric(repo_root=repo_root, company_id=company_id,
                                                metric_id=metric_id,
                                                period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_ZERO_AI_SOURCE_REPLAY_CHANGED",
          "SOURCE_REPLAY_CONFLICT")
    return rebuilt
