"""Rebuild catalog metrics for an explicitly selected historical period.

This is a source adapter, not a second calculator. The metric catalog, the
compiled Specs, the deterministic metric graph, the applicability rules and the
withheld-result constructor are the installed current ones, imported unchanged
from ``normal_companyfacts_results`` and ``zero_ai_r2``. What this module owns
is which filing each accession role means when the period is pinned.

It exists as a successor file because ``scripts/vnext/normal_companyfacts_results.py``
and ``scripts/vnext/normal_run_inputs.py`` are byte-bound by the ``issue_28_v13``
rule set: changing them would stop every existing ordinary Run from loading its
own Requirement.

Routes whose source scope is defined relative to the current period — amendment
scope, successor-registrant income statements, event windows — are refused here
as implementation gaps. Resolving them against today's latest filing under a
historical request would be a wrong answer, not a missing feature.
"""
from datetime import date, timedelta
from decimal import DecimalException
from pathlib import Path

from sec_urls import submissions_url

from .calculator import metric_is_applicable, withheld_metric_result
from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .historical_filing_inventory import filing_inventory
from .normal_annual_input import annual_period, _registry_rows
from .normal_companyfacts_results import (CATALOG_PATH, NormalCompanyfactsError,
                                          _SOURCE_ERRORS, _authority, _filing_source,
                                          _prior_filing)
from .normal_annual_input_v2 import exact_json_value
from .historical_spec_revision import compile_historical_spec_file
from .normal_governance_input import _Sources
from .normal_run_specs import validate_ordinary_spec_files
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
                         _deterministic_metric_graph, _manual_result_trace)


RESULT_RECORD_TYPE = "HISTORICAL_COMPANYFACTS_NATIVE_RESULTS"
RUN_INPUT_RECORD_TYPE = "HISTORICAL_ZERO_AI_RUN_INPUT"


def _need(condition, reason):
    if not condition:
        raise NormalCompanyfactsError(reason)


def resolve_historical_companyfacts_metrics(*, repo_root: Path, company_id: str, period_selection):
    """Resolve the Company Facts catalog metrics for one pinned period.

    Current values come from the selected filing's own accession; prior values
    come from the filing immediately preceding it, each from its own selected
    report. That is the frozen first-report semantics, applied to a past target
    rather than to the latest one, and it is not a restated view.
    """
    authority = _authority(repo_root)
    catalog = _load_deterministic_catalog(repo_root=repo_root)
    routes = {key: value for key, value in catalog["metrics"].items()
              if value["adapter_id"] == "companyfacts"}
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    verify_ordinary_source_proofs(data_root=repo_root, proofs=prepared["source_proofs"])
    # A period carrying a 10-K/A used to refuse outright. The approved policy in
    # config/annual_amendment_scope_v1.json already decides these shapes, and
    # annual_amendment_scope proves the classification from the filings' own
    # bytes, so this asks rather than refusing. The target stays the original
    # filing either way: the amendment is evidence about whether the original's
    # inputs still stand, never a source of values.
    traits = repository_company_traits(repo_root=repo_root, company_id=company_id)
    # Structural applicability is prior to the amendment question and is asked
    # first. A metric this company's traits exclude reads no input at all, so
    # no input class can be in doubt for it; refusing it because an amendment
    # left the original's statement values unproven says the values could not
    # be read when there were none to read. Measured on Paramount: five of the
    # eleven are N_A_STRUCTURAL and were being refused on an amendment
    # classification that cannot reach them.
    applicable = sorted(metric_id for metric_id, route in routes.items()
                        if metric_is_applicable(applicability=route["applicability"],
                                                traits=traits))
    amendment_error = None
    if prepared["amendments"] and applicable:
        from .historical_amendment_admission import (AmendmentAdmissionError,
                                                     amendment_admission)
        try:
            amendment_admission(repo_root=repo_root, company_id=company_id,
                                metric_ids=applicable, prepared=prepared)
        except AmendmentAdmissionError as error:
            # Carried per metric rather than raised for the family: the
            # metrics it does reach still report it, and it is the same
            # message as before, so an approved policy refusal never reads as
            # an implementation gap.
            amendment_error = str(error)
    # A successor registrant used to refuse all eleven metrics outright. The
    # ordinary route has had an answer for each of them for some time, and it
    # is an approved one: the catalog's REQUIRE_CONTINUOUS routes report
    # ENTITY_CONTINUITY_NOT_COMPARABLE, the current-instant ALLOW routes read
    # this registrant's own facts, and anything else still refuses. Refusing
    # where an approved answer exists reports an implementation gap that is
    # not there, so this asks the same question the ordinary chain asks and
    # gets the same three answers - measured against it, not assumed.
    subject_error = ("HISTORICAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED"
                     if prepared["subject_policy"]["mode"] != "CONTINUOUS_PRIMARY" else None)
    period = prepared["table_input"]["target_period"]
    registry = next(r for r in _registry_rows(repo_root=repo_root) if r["company_id"] == company_id)
    reader = _Sources(repo_root, company_id, prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),
                            role="sec_submissions_inventory", media_type="application/json")
    reader.primary(prepared["filing"])
    concepts = sorted({concept for route in routes.values() for branch in route["branches"]
                       for component in branch["components"] for concept in component["approved_concepts"]})
    sources, claims_by_role = [], {}
    # The target filing is proved against the document that lists it: the
    # main index when its recent block does, else the loaded history block
    # that does. The prior walk below already works this way, and keeps the
    # main index because the history index it walks is in that document.
    listed_in = filing_inventory(reader=reader, inventory=inventory,
                                 period_selection=period_selection, cik=prepared["entity"],
                                 accession=prepared["filing"]["accessionNumber"])
    source, claims_by_role["current"] = _filing_source(reader, prepared, prepared["filing"],
                                                       listed_in, concepts)
    sources.append({**source, "accession_role": "current"})
    periods = {"current": period, "prior": None}
    filings = {"current": prepared["filing"], "prior": None}
    prior_error = None
    needs_prior = any(metric_is_applicable(applicability=route["applicability"], traits=traits)
                      and any(c["accession_role"] == "prior" for b in route["branches"]
                              for c in b["components"]) for route in routes.values())
    if needs_prior:
        try:
            filing, prior_inventory = _prior_filing(reader, inventory, prepared)
            # The selected period already proved which filing precedes it from
            # the complete saved catalog; the source walk must land on it.
            _need(period_selection["prior_filing"] is not None
                  and filing["accessionNumber"] == period_selection["prior_filing"]["accessionNumber"],
                  "HISTORICAL_COMPANYFACTS_PRIOR_DIFFERS_FROM_SELECTION")
            # The prior role needs that filing's own annual interval and its
            # adjacency to the target, not an issuer fiscal-year label, so the
            # accession's own authenticated instance is a valid substitute here
            # exactly as it is on the frozen current route. The target role is a
            # different question and still requires the full primary document.
            primary = reader.primary(filing, required=False)
            documents = [primary] if primary else reader.auditor_filing(filing)
            source_periods = [annual_period(raw=s["raw_bytes"], cik=prepared["entity"], filing=filing)
                              for s in documents]
            _need(bool(source_periods) and all(p == source_periods[0] for p in source_periods),
                  "HISTORICAL_COMPANYFACTS_PRIOR_NATIVE_PERIOD_CONFLICT")
            prior = source_periods[0]
            _need(date.fromisoformat(prior["period_end"]) + timedelta(days=1)
                  == date.fromisoformat(period["period_start"]),
                  "HISTORICAL_COMPANYFACTS_PRIOR_PERIOD_NOT_ADJACENT")
            source, claims_by_role["prior"] = _filing_source(reader, prepared, filing,
                                                             prior_inventory, concepts)
            sources.append({**source, "accession_role": "prior"})
            periods["prior"], filings["prior"] = prior, filing
        except (*_SOURCE_ERRORS, NormalCompanyfactsError) as error:
            prior_error = {"reason": str(error), "error_type": type(error).__name__}
    context = {"repo_root": repo_root, "deterministic_catalog": catalog,
               "role_context": {(company_id, "companyfacts"):
                                {"sources": sources, "claims_by_accession_role": claims_by_role}},
               "target_periods": {company_id: periods}, "targets": {company_id: period},
               "registry": {company_id: registry},
               "filings_by_company": {company_id: {role: ({"accession": filing["accessionNumber"]}
                                                          if filing else None)
                                                   for role, filing in filings.items()}}}
    results = {}
    for metric_id, route in routes.items():
        spec = _compiled_deterministic_spec(metric_id=metric_id, route=route)
        instant = route["result_period_role"] == "current_instant"
        scope = {"coverage": "deterministic_source_set", "fiscal_year": period["fiscal_year"]}
        target = {"company_id": company_id,
                  "period_start": period["period_end"] if instant else period["period_start"],
                  "period_end": period["period_end"], "scope": scope,
                  "scope_key": scope_key(scope=scope)}
        detail = None
        graph = {"claims": [], "projection_claims": [], "observation": None}
        if not metric_is_applicable(applicability=route["applicability"], traits=traits):
            result, trace = _manual_result_trace(
                metric_id=metric_id, company_id=company_id, period_start=target["period_start"],
                period_end=target["period_end"], scope=scope, spec_closure_hash=spec["spec_closure_hash"],
                applicability="N_A_STRUCTURAL", quality="NONE", reason_code="TRAIT_NOT_APPLICABLE",
                input_observation_ids=[], steps=[{"event": "N_A_STRUCTURAL"}], accession=None,
                entity=None, unit=None)
        else:
            try:
                # An approved amendment refusal reaches the metrics it is about
                # and no further. It is raised here, inside the per-metric
                # handler, so it lands as this metric's named reason instead of
                # ending the whole resolve.
                _need(amendment_error is None, amendment_error)
                # The same guard the ordinary route runs, on the same catalog
                # policy and the same registry row. It needs the authenticated
                # registrant and period, not statement values, so it is asked
                # before the prior-period walk is required of anything.
                continuity_guard = (bool(subject_error)
                                    and route["continuity_policy"] == "REQUIRE_CONTINUOUS"
                                    and registry["entity_continuity_status"] != "continuous")
                requires_prior = any(c["accession_role"] == "prior" for b in route["branches"]
                                     for c in b["components"])
                if continuity_guard:
                    graph = _deterministic_metric_graph(context=context, company_id=company_id,
                                                        metric_id=metric_id)
                    result, trace = graph["result"], graph["trace"]
                    _need(result["quality"] == "NOT_MEANINGFUL"
                          and result["reason_code"] == "ENTITY_CONTINUITY_NOT_COMPARABLE"
                          and result["value"] is None and not graph["claims"]
                          and graph["observation"] is None,
                          "HISTORICAL_COMPANYFACTS_CONTINUITY_GUARD_CHANGED")
                    detail = {"category": "APPROVED_COMPARABILITY_LIMIT",
                              "reason": "ENTITY_CONTINUITY_NOT_COMPARABLE",
                              "continuity_policy": route["continuity_policy"],
                              "entity_continuity_status": registry["entity_continuity_status"],
                              "subject_policy": prepared["subject_policy"],
                              "statement_values_used": False}
                else:
                    # The installed catalog already permits these current-instant
                    # metrics across a registrant transition. Their facts still
                    # come from this primary CIK and this accession only; that
                    # is not comparable annual performance and is not claimed as
                    # any. Every other successor case keeps the refusal.
                    instant_scope = (route["continuity_policy"] == "ALLOW" and instant
                                     and all(c["accession_role"] == "current"
                                             and c["period_role"] == "current_instant"
                                             for b in route["branches"] for c in b["components"]))
                    _need(not subject_error or instant_scope, subject_error)
                    _need(not requires_prior or prior_error is None,
                          (prior_error or {}).get("reason"))
                    graph = _deterministic_metric_graph(context=context, company_id=company_id,
                                                        metric_id=metric_id)
                    result, trace = graph["result"], graph["trace"]
            except (*_SOURCE_ERRORS, NormalCompanyfactsError, DecimalException) as error:
                graph = {"claims": [], "projection_claims": [], "observation": None}
                # An approved policy refusal and an unresolved route are two
                # different answers and must not share a reason code. Reporting
                # a decided question as SOURCE_OR_IMPLEMENTATION_UNRESOLVED is
                # what makes a settled question read as still open.
                decided = amendment_error is not None and str(error) == amendment_error
                detail = {"reason": str(error), "error_type": type(error).__name__,
                          "category": ("APPROVED_AMENDMENT_POLICY_REFUSAL" if decided
                                       else "SOURCE_OR_IMPLEMENTATION_UNRESOLVED"),
                          "amendment_policy_decision": amendment_error if decided else None}
                result, trace = withheld_metric_result(
                    compiled_spec=spec, target=target,
                    reason_code=("HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED" if decided
                                 else "HISTORICAL_COMPANYFACTS_ROUTE_UNRESOLVED"))
        observations = [graph["observation"]] if graph["observation"] else []
        results[metric_id] = {"metric_id": metric_id, "compiled_spec": spec, "target": target,
                              "selection": detail, "claims": graph["claims"],
                              "projection_claims": graph["projection_claims"],
                              "observations": observations, "result": result, "trace": trace,
                              "records": [*observations, trace, result]}
    proofs = list({content_hash(value=p): p for p in
                   [*prepared["source_proofs"], *[s["proof"] for s in reader.proofs.values()]]}.values())
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    body = {"record_type": RESULT_RECORD_TYPE, "company_id": company_id,
            "period_selection": period_selection,
            "prepared_input": prepared, "filings": filings, "periods": periods,
            "prior_error": prior_error, "authority_file_hashes": authority,
            "source_records": list(reader.records.values()), "amendment_input": None,
            "instant_amendment_input": None, "source_proofs": proofs,
            "source_admission": admission, "source_sets": [s["manifest"] for s in sources],
            "claims_by_accession_role": claims_by_role,
            "failed_source_attempts": list(reader.failed_attempts.values()), "metrics": results,
            "resolver_sha256": sha256_file(path=Path(__file__)),
            "catalog_path": CATALOG_PATH,
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False, "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "component_id": content_hash(value=body)}


def verify_historical_companyfacts_metrics(*, candidate, repo_root: Path, company_id: str,
                                           period_selection):
    rebuilt = resolve_historical_companyfacts_metrics(repo_root=repo_root, company_id=company_id,
                                                      period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_COMPANYFACTS_SOURCE_REPLAY_CHANGED")
    return rebuilt


# A text metric does not live in the 22 zero-AI Spec set, and its result is not
# computed here: the review decision binds the Requirement, which only the Run
# factory holds. So this assembles the identity and the sources, and
# create_historical_run computes the text result from them, exactly as the
# current route splits the same work between normal_run_v2 and normal_run_v3.
TEXT_METRICS = ("C02", "D01", "D02")
# v2 declares max_items 192 where v1 declares 64. 64 was two bounds wearing one
# number: what a Spec may declare, which historical_spec_revision raises without
# touching the frozen compiler, and what ORDERED_NEWLINE_V1 will render, which
# historical_text_protocol carries for this generation. Both are wired, so the
# route can declare the capacity the runtime actually honours. v1 keeps its
# bytes and its identity, because the Runs frozen under it declare it.
# D01 keeps v1's bound. Measured across the ten companies its Item 1A carries
# 28 to 60 headings against max_items 64, so nothing here is waiting on the
# capacity work D02 needed - though Enphase is four headings away from it.
TEXT_SPEC_PATHS = {"C02": "catalog/r6/C02_board_disclosures_v1.md",
                   "D01": "catalog/r6/D01_risk_factor_headings.md",
                   "D02": "catalog/r6/D02_legal_disclosures_v2.md"}


def _historical_text_run_input(*, repo_root, company_id, metric_id, period_selection):
    """Assemble the text case's identity without its raw bytes.

    ``text_arguments`` carries the filing's bytes, which cannot enter a binding
    that has to be JSON and content-addressed. The binding therefore records
    which sources were admitted, and the Run factory re-prepares the same input
    from the data root to obtain the bytes again.
    """
    from .historical_text_input import prepare_historical_business_text_input
    prepared = prepare_historical_business_text_input(
        repo_root=repo_root, company_id=company_id, metric_id=metric_id,
        period_selection=period_selection)
    _need(prepared["input_status"] != "BLOCKED",
          "HISTORICAL_TEXT_RUN_INPUT_BLOCKED:" + str(prepared["input_binding"]["limitations"]))
    spec_path = TEXT_SPEC_PATHS[metric_id]
    spec = compile_historical_spec_file(repo_root=repo_root, repo_relative_path=spec_path,
                                        dependency_specs={})
    period = prepared["target_period"]
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": [metric_id],
            "spec_paths": {metric_id: spec_path}, "compiled_specs": {metric_id: spec},
            "records": prepared["records"], "source_records": prepared["records"],
            "source_references": prepared["source_references"],
            "source_proofs": prepared["source_proofs"],
            "source_admission": prepared["admission"],
            "primary_result": None, "results": {}, "traces": {},
            "target_period": {"fiscal_year": period["fiscal_year"],
                              "period_start": period["period_start"],
                              "period_end": period["period_end"]},
            "component": prepared["input_binding"], "kind": "TEXT",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}


def _historical_semantic_run_input(*, repo_root, company_id, metric_id, period_selection,
                                   assessment_mode):
    """Assemble D04's text case from its registered assessment, without raw bytes.

    The same shape as the text route's, and for the same reason: the text
    arguments hold the filing's bytes, so the binding records the admitted
    sources and the registered assessment's identity, and the Run factory
    re-prepares the case from the data root. The registered record itself is
    carried whole, because the installer has to place it in the data root and
    the binding has to cover it.
    """
    from .historical_semantic_results import prepare_historical_semantic_case
    case = prepare_historical_semantic_case(repo_root=repo_root, company_id=company_id,
                                            metric_id=metric_id, period_selection=period_selection,
                                            assessment_mode=assessment_mode)
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": [metric_id],
            "spec_paths": {metric_id: case["spec_path"]},
            "compiled_specs": {metric_id: case["compiled_spec"]},
            "records": case["records"], "source_records": case["records"],
            "source_references": case["source_references"],
            "source_proofs": case["source_proofs"], "source_admission": case["admission"],
            "primary_result": None, "results": {}, "traces": {},
            "target_period": case["target_period"], "component": case["component"],
            "registered_assessment": case["registered"], "kind": "TEXT",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}


def _run_coordinate(*, pinned, primary):
    """The Run's fiscal coordinate, which is not always the result's window.

    The primary result's own window is used when it lies inside the pinned
    period, and that covers every case this repository has run: an instant
    metric measures a point in the year, and a duration metric measures the
    year itself. Measured over 117 primary results from the batch, all 117 are
    contained, so this rule changes none of them.

    It is not the same rule as "take the result's window", and the difference
    is a real case rather than a hypothetical one. A registered event metric on
    a successor registrant measures a window the approved policy widens to the
    prior calendar year's start - two years of filing dates. Taking that as the
    coordinate makes the Run claim a fiscal year longer than 53 weeks and it is
    refused, correctly: a fiscal coordinate is not a lookback window. Narrowing
    the event sources to fit the coordinate would be the other wrong answer,
    because it would drop filings the policy says belong to the measurement.

    So when the result's window leaves the pinned period, the coordinate stays
    pinned and the widened window stays on the result, where the record that
    carries it also carries the scope evidence for why it is wider.
    """
    inside = (str(primary["period_start"]) >= str(pinned["period_start"])
              and str(primary["period_end"]) <= str(pinned["period_end"]))
    window = primary if inside else pinned
    return {"fiscal_year": pinned["fiscal_year"],
            "period_start": window["period_start"],
            "period_end": window["period_end"]}


def _check_bound_assets(*, records):
    """Every asset an observation names has to be a record of the same Run.

    Asked here because this is the one place all four component routes pass
    through, and because the Run factory asks it too - only later, in a tree
    this one cannot create a Run in. Two routes have now shipped without it and
    were found by a batch: the compensation-table stage of C03 rebuilds the
    annual report's grid and did not carry it, and the lodging route needed its
    grid recognised before a Run could be frozen at all. The cost of finding
    that at freeze time rather than here is a whole batch.

    Args:
        records: The component's records, observations and assets together.

    Raises:
        HistoricalResultsError: Naming the asset that is missing, so the report
            says which record the route did not carry rather than that the Run
            would not freeze.
    """
    present = {str(record.get("derived_asset_id")) for record in records
               if record.get("record_type") == "DERIVED_ASSET"}
    for record in records:
        if record.get("record_type") != "VERIFIED_OBSERVATION":
            continue
        named = record.get("source_binding", {}).get("derived_asset_id")
        _need(named is None or str(named) in present,
              "HISTORICAL_COMPONENT_DERIVED_ASSET_NOT_CARRIED:" + str(named))


def _historical_component_run_input(*, repo_root, company_id, metric_id, period_selection,
                                     resolve):
    """The Run shape around a component that has already produced its Result.

    Two routes hand over a finished Result rather than a graph to evaluate,
    and they differ in what is behind it. The structural one read no filing at
    all, so it carries no claims and no observations - its Result is that the
    metric does not apply to this company. C04 read several and carries an
    observation, or a withheld Result naming the material it could not read.

    What they share, and what this owns, is the Run's shape: the same pinned
    coordinate, the same admitted source set, and the component's own records.
    It was named for the first of the two before there was a second; the name
    now says what it does rather than who first used it.
    """
    component = resolve(repo_root=repo_root, company_id=company_id, metric_id=metric_id,
                        period_selection=period_selection)
    _check_bound_assets(records=component["records"])
    specs = {metric_id: component["compiled_spec"]}
    primary = component["result"]
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": [metric_id],
            "spec_paths": {metric_id: component["spec_path"]},
            "compiled_specs": specs, "records": component["records"],
            "source_records": component["source_records"],
            "source_references": component["source_references"],
            "source_proofs": component["source_proofs"],
            "source_admission": component["source_admission"],
            "primary_result": primary, "results": {metric_id: primary},
            "traces": {metric_id: component["trace"]},
            "target_period": _run_coordinate(pinned=component["target_period"],
                                             primary=primary),
            "component": component, "kind": "STRUCTURED",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}


def prepare_historical_run_input(*, repo_root: Path, company_id: str, metric_id: str,
                                 period_selection, assessment_mode=None):
    """Assemble one metric's complete historical graph for a Run factory.

    The installed Spec set, dependency closure and record-collision rules are
    the frozen current ones. Only the period is explicit.

    ``assessment_mode`` concerns D04 alone, whose input includes a registered
    model assessment: None means the installed copy's mode in a data root and
    LIVE otherwise, so a batch never consumes a recorded test registration. It
    is refused for every other metric, which has nothing it could select.
    """
    from .historical_semantic_results import SUPPORTED_METRICS as SEMANTIC_METRICS
    _need(assessment_mode is None or metric_id in SEMANTIC_METRICS,
          "HISTORICAL_RUN_ASSESSMENT_MODE_WITHOUT_ASSESSMENT")
    from .historical_accession_results import resolve_historical_accession_metrics
    # Revenue and the 8-K event windows share one adapter, as they do in the
    # current route, so this follows that module's own supported set.
    from .historical_zero_ai_results import (SUPPORTED_METRICS as ZERO_AI_METRICS,
                                             resolve_historical_zero_ai_metric)
    from .historical_structural_results import (SUPPORTED_METRICS as STRUCTURAL_METRICS,
                                                 resolve_historical_structural_metric,
                                                 structurally_not_applicable)
    ACCESSION_METRICS = ("A01", "A02", "B12")
    from .historical_governance_results import (
        SUPPORTED_METRICS as GOVERNANCE_METRICS,
        resolve_historical_governance_metric)
    from .historical_debt_results import (SUPPORTED_METRICS as DEBT_METRICS,
                                          resolve_historical_debt_metric)
    from .historical_lodging_results import (SUPPORTED_METRICS as LODGING_METRICS,
                                             resolve_historical_lodging_metric)
    from .historical_capacity_results import (SUPPORTED_METRICS as CAPACITY_METRICS,
                                              resolve_historical_capacity_metric)
    from .historical_financial_results import (SUPPORTED_METRICS as FINANCIAL_METRICS,
                                               resolve_historical_financial_metric)
    if metric_id in TEXT_METRICS:
        return _historical_text_run_input(repo_root=repo_root, company_id=company_id,
                                          metric_id=metric_id,
                                          period_selection=period_selection)
    # D04 is read by a model, and its Run consumes the registered review of
    # every unit of the pinned source. Its Spec is not in the ordinary set, so
    # this answers before that set is consulted.
    if metric_id in SEMANTIC_METRICS:
        return _historical_semantic_run_input(repo_root=repo_root, company_id=company_id,
                                              metric_id=metric_id,
                                              period_selection=period_selection,
                                              assessment_mode=assessment_mode)
    # C04's Spec is not in the ordinary twenty-two, so like the text and
    # structural routes this answers before that set is consulted. The
    # component owns the comparison; this owns only the Run's shape.
    if metric_id in GOVERNANCE_METRICS:
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_governance_metric)
    # B06 answers the same way and for the same reason: its Spec is not in the
    # ordinary twenty-two either, because the cascade chooses among several and
    # the stage that answers decides which one this period's Result is under.
    if metric_id in DEBT_METRICS:
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_debt_metric)
    # B10 and B11 are trait-gated too, so this sits above the structural check
    # and answers only where the gate is open. The structural route keeps the
    # other side: for a company that is not a lodging operator the answer is
    # that the metric does not apply, and it is that route's to give.
    if metric_id in LODGING_METRICS and not structurally_not_applicable(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id):
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_lodging_metric)
    # The six financial metrics, where the gate is open. Same placement and the
    # same reason as the lodging pair: the structural route keeps the closed
    # side, and a bank's liquidity coverage ratio is not that route's to answer.
    if metric_id in FINANCIAL_METRICS and not structurally_not_applicable(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id):
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_financial_metric)
    # B13 answers where the approved definition leaves the company out; for
    # Ford and Enphase the component refuses by name, because what is missing
    # there is the semantic review, not an answer. Its Spec is not in the
    # ordinary set either, so this also sits above it.
    if metric_id in CAPACITY_METRICS:
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_capacity_metric)
    # A metric the company's traits put outside its own gate. Checked before
    # the Spec set below, because these Specs are not in it: a liquidity
    # coverage ratio has no ordinary route to be in.
    if metric_id in STRUCTURAL_METRICS and structurally_not_applicable(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id):
        return _historical_component_run_input(
            repo_root=repo_root, company_id=company_id, metric_id=metric_id,
            period_selection=period_selection,
            resolve=resolve_historical_structural_metric)
    specifications = validate_ordinary_spec_files(repo_root=repo_root)
    _need(metric_id in specifications, "HISTORICAL_RUN_METRIC_NOT_IN_ZERO_AI_SET")
    expected_ids = {metric_id, *specifications[metric_id]["compiled_spec"]["compiled"]["dependencies"]}
    if metric_id in ZERO_AI_METRICS:
        component = resolve_historical_zero_ai_metric(repo_root=repo_root, company_id=company_id,
                                                      metric_id=metric_id,
                                                      period_selection=period_selection)
        specs = {metric_id: component["compiled_spec"], **component["dependency_specs"]}
        source_records = component["source_records"]
        records = [*component["records"], *component["claims"]]
    elif metric_id in ACCESSION_METRICS:
        _need(expected_ids == {metric_id}, "HISTORICAL_RUN_DEPENDENT_METRIC_NOT_IMPLEMENTED")
        component = resolve_historical_accession_metrics(repo_root=repo_root,
                                                         company_id=company_id,
                                                         period_selection=period_selection)
        metric = component["metrics"][metric_id]
        specs = {metric_id: metric["compiled_spec"]}
        source_records = component["source_records"]
        records = [*source_records, *metric["claims"], *metric["records"]]
    else:
        _need(expected_ids == {metric_id}, "HISTORICAL_RUN_DEPENDENT_METRIC_NOT_IMPLEMENTED")
        component = resolve_historical_companyfacts_metrics(repo_root=repo_root,
                                                            company_id=company_id,
                                                            period_selection=period_selection)
        _need(metric_id in component["metrics"], "HISTORICAL_RUN_METRIC_NOT_IN_COMPANYFACTS_ROUTE")
        metric = component["metrics"][metric_id]
        specs = {metric_id: metric["compiled_spec"]}
        source_records = component["source_records"]
        records = [*source_records, *metric["claims"], *metric["records"]]
    unique = {}
    for record in records:
        key = content_hash(value=record)
        _need(key not in unique or unique[key] == record,
              "HISTORICAL_RUN_RECORD_HASH_COLLISION_WITH_DIFFERENT_BYTES")
        unique.setdefault(key, record)
    records = list(unique.values())
    results = {r["metric_id"]: r for r in records if r["record_type"] == "METRIC_RESULT"}
    traces = {r["metric_id"]: r for r in records if r["record_type"] == "EXECUTION_TRACE"}
    _need(sum(r["record_type"] == "METRIC_RESULT" for r in records) == len(results)
          and sum(r["record_type"] == "EXECUTION_TRACE" for r in records) == len(traces),
          "HISTORICAL_RUN_DUPLICATE_RESULT_OR_TRACE")
    _need(set(results) == set(traces) == expected_ids,
          "HISTORICAL_RUN_RESULT_DEPENDENCY_SET_INCOMPLETE")
    for metric_key, result in results.items():
        _need(result["trace_id"] == traces[metric_key]["trace_id"]
              and result["spec_closure_hash"] == specs[metric_key]["spec_closure_hash"],
              "HISTORICAL_RUN_RESULT_TRACE_OR_SPEC_CHANGED")
    for metric_key, spec in specs.items():
        _need(spec == specifications[metric_key]["compiled_spec"],
              "HISTORICAL_RUN_INSTALLED_SPEC_DIFFERS_FROM_SOURCE_ROUTE:" + metric_key)
    _need(set(specs) == expected_ids, "HISTORICAL_RUN_DEPENDENCY_SPEC_SET_CHANGED")
    primary = results[metric_id]
    period = component["prepared_input"]["table_input"]["target_period"]
    body = {"record_type": RUN_INPUT_RECORD_TYPE, "company_id": company_id,
            "primary_metric_id": metric_id, "period_selection": period_selection,
            "requested_metric_ids": [metric_id], "required_metric_ids": sorted(expected_ids),
            "spec_paths": {m: specifications[m]["path"] for m in sorted(expected_ids)},
            "compiled_specs": specs, "records": records, "source_records": source_records,
            "source_references": [r for r in source_records if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": component["source_proofs"],
            "source_admission": component["source_admission"],
            "primary_result": primary, "results": results, "traces": traces,
            "target_period": _run_coordinate(pinned=period, primary=primary),
            "component": component, "kind": "STRUCTURED",
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_status": "NOT_CREATED", "production_authorized": False}
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}
