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

E01's 8.01 items are confirmed from their own text, read from the primary
document by ``historical_event_items``, not from the frozen brief, which for an
hdr-coded filing is a sentence the program wrote and which no 8.01 in this
repository ever matched. What an alias found there means is undecided, so a
window where one occurs is withheld by name rather than answered either way.
The other five event routes have no keyword items and are untouched.
"""
from decimal import Decimal
from pathlib import Path

from sec_urls import companyfacts_url, submissions_url

from .annual_update import AnnualUpdateError
from . import b03_contract_amortization_scope as _contract_scope
from .batch_workflow import BatchWorkflowError, _structured_concepts
from .calculator import (calculate_metric, calculate_observation_metric,
                         withheld_metric_result)
from .canonical import content_hash, sha256_file, strict_json_loads
from .historical_annual_input import prepare_historical_annual_input
from .historical_dei import release_aware
from .historical_da_scope_candidate import (COMPOSITION, DIRECT, WITHHELD_REASON as DA_SCOPE_REASON,
                                            agree, annual_facts, da_scope_answer)
from .historical_ma_confirmation import (ConfirmationNotRegistered, confirmation_request,
                                         item_id, load_registered_confirmation)
from .historical_event_items import (CONFIRMATION_REASON, NOT_LOCATED_REASON, SUCCESSOR_EVENT_ROUTES,
                                     EventItemTextError, compact_confirmation,
                                     content_confirmation_candidates, successor_event_route)
from .historical_event_walk import event_sources, registered_event_sources
from .historical_filing_inventory import filing_inventory
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources, NormalGovernanceInputError
from .normal_zero_ai_results import (B01_SPEC_PATH, B03_SPEC_PATH, EVENT_METRICS,
                                     NormalZeroAiError, _authority, _compiled_event_spec,
                                     _exact_set)
from .observations import structured_observation
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .normal_source_authority import ROOT
from .sources import companyfacts_structured_facts, resolve_repository_file, SourceError
from .specs import compile_spec_file
from .traits import repository_company_traits
from .deterministic_router import (adapt_companyfacts, load_event_route_catalog,
                                   project_event_result)


RECORD_TYPE = "HISTORICAL_ZERO_AI_SOURCE_RESULT"
SUPPORTED_METRICS = ("B01", "B03", *EVENT_METRICS)
_SOURCE_ERRORS = (NormalZeroAiError, NormalGovernanceInputError, AnnualUpdateError,
                  BatchWorkflowError, SourceError)


class _AmendmentRefused(Exception):
    """Control flow only: the approved amendment policy refused this input class."""


class _ConfirmationUnsettled(Exception):
    """A registered confirmation names an item its own text does not settle."""

    def __init__(self, registered):
        super().__init__(registered["counted"]["withheld_reason"])
        self.registered = registered


class _ConfirmationRequestBuilt(Exception):
    """The call path asked for the request, not the result; it carries the request."""

    def __init__(self, request, proofs):
        super().__init__("E01_CONFIRMATION_REQUEST_BUILT")
        self.request, self.proofs = request, proofs


class _ConfirmationNotRegistered(Exception):
    """Control flow only: a content-confirmed route's window holds a candidate nobody has confirmed."""


class _DepreciationScopeUnproven(Exception):
    """Control flow only: B03's D&A cannot be shown to be the whole of it; the answer rides along."""

    def __init__(self, answer):
        super().__init__(answer["why"])
        self.answer = answer


class _EventRouteResolved(Exception):
    """Control flow only: the event branch finished and skips the facts branch.

    Raised and caught inside one function so the two routes keep the same
    ``except`` clause for real source failures rather than duplicating it.
    """


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalZeroAiError(reason, category)


def depreciation_scope(*, raw_bytes, period, observations):
    """Whether B03's D&A input is provably the whole of the definition's D&A, from the filing itself.

    The approved chain takes the first of three direct concepts Company Facts
    carries for the target and never compares it with the others; Salesforce's
    FY2026 filing tags the first one on a fixed-asset note sentence and the
    statement total on another, and the chain took the note. Standing rules
    forbid taking a subtotal as the total and require limiting the metric
    precisely when the total cannot be proven, so the rule below
    (``historical_da_scope_candidate``) asks the target filing's own inline
    facts: agreeing direct candidates keep the chain's choice; a conflict the
    filing's own Depreciation + AmortizationOfIntangibleAssets resolves takes
    the candidate they prove; anything else withholds by name.

    What the chain used must also be what the filing carries: a direct concept
    the filing does not tag for this period, or a composition taken while the
    filing tags a direct total, is a disagreement between the two sources the
    route cannot settle, and it withholds as well.

    A kept direct total is also asked whether the filing itself says it
    includes impairment-related depreciation, which the definition does not add
    back (``impairment_included``; the finding and the saved filing where it
    applies are in docs/evidence/issue47_history/b03-impairment-inclusion/).
    A total the filing says includes it is withheld by name; the exact
    exclusion #28 computes with its own successor Spec is not ported here.

    Returns:
        ``{"status": "KEEP" | "RETAKE" | "WITHHOLD", ...}`` with the filing's
        answer and the chain's input beside it; ``RETAKE`` names the concept
        the filing proves.
    """
    facts = annual_facts(raw_bytes=raw_bytes, period_start=period["period_start"],
                         period_end=period["period_end"], concepts=DIRECT + COMPOSITION)
    answer = da_scope_answer(facts=facts)
    direct = [o for o in observations if o["semantic_role"] == "depreciation_and_amortization"]
    composed = [o for o in observations if o["semantic_role"] in ("depreciation", "amortization")]
    chain = ({"concept": direct[0]["source_binding"]["concept"].split(":")[-1],
              "value": str(direct[0]["value"])} if direct
             else {"concept": "+".join(COMPOSITION),
                   "value": str(sum(Decimal(str(o["value"])) for o in composed))} if composed
             else None)
    body = {"filing_answer": answer, "chain_input": chain}
    if answer["status"] == "WITHHOLD":
        return {**body, "status": "WITHHOLD", "why": answer["why"]}
    if answer["status"] == "NO_DIRECT_CANDIDATE":
        if direct:
            return {**body, "status": "WITHHOLD",
                    "why": "THE_CHAIN_TOOK_A_DIRECT_TOTAL_THE_FILING_DOES_NOT_TAG_FOR_THIS_PERIOD"}
        return {**body, "status": "KEEP", "why": answer["why"]}
    selected = answer["selected"]
    if not direct:
        return {**body, "status": "WITHHOLD",
                "why": "THE_CHAIN_COMPOSED_WHILE_THE_FILING_TAGS_A_DIRECT_TOTAL"}
    if chain["concept"] != selected["concept"]:
        return {**body, "status": "RETAKE", "concept": selected["concept"], "why": answer["why"]}
    if not agree({"value": chain["value"], "decimals": "INF"}, selected):
        return {**body, "status": "WITHHOLD",
                "why": "THE_CHAIN_S_VALUE_IS_NOT_THE_FILING_S_AT_ITS_PRECISION"}
    included = impairment_included(raw_bytes=raw_bytes, period=period, observation=direct[0])
    if included is not None:
        return {**body, "status": "WITHHOLD", "impairment_inclusion": included,
                "why": "THE_SELECTED_TOTAL_INCLUDES_IMPAIRMENT_RELATED_DEPRECIATION"}
    return {**body, "status": "KEEP", "why": answer["why"]}


def impairment_included(*, raw_bytes, period, observation):
    """The filing's own proof that the kept D&A total includes impairment-related depreciation, or None.

    The same question #28's ordinary route asks after a Run
    (``b03_depreciation_scope.assess_direct_depreciation_scope``), asked here
    of the pinned filing's bytes before the result is published: the inline
    facts that carry the selected concept and value for the target annual
    period, undimensioned and for the observation's own entity, and then the
    visible table row and footnote around them. The row test is #28's
    (``_selected_impairment_inclusion``, bound here through the parent
    generation's authority): the footnote marker must follow a numeric
    component of the selected row, the visible components must sum to the
    selected total, and the adjacent footnote must say the component includes
    depreciation related to an impairment. A nearby mention of impairment is
    not enough, and a prior year's column in the same table is its own fact.
    """
    from .b03_depreciation_scope import _DA_CONCEPTS, _selected_impairment_inclusion
    from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
    binding = observation["source_binding"]
    if binding["concept"] not in _DA_CONCEPTS:
        return None
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    rows = []
    for fact in parsed.facts:
        if fact["qualified_name"] != binding["concept"]:
            continue
        context = parsed.contexts[fact["context_ref"]]
        if (context["period_start"] != period["period_start"]
                or context["period_end"] != period["period_end"]
                or context["typed_dimension_count"] or context["dimensions"]
                or str(int(context["entity_identifier"])) != str(int(binding["entity"]))):
            continue
        try:
            value = str(_numeric_xbrl_value(text=fact["text"], scale=fact["scale"],
                                            sign=fact["sign"]))
        except (ValueError, TypeError):
            continue
        if value == str(observation["value"]):
            rows.append({"ordinal": fact["ordinal"], "concept": fact["qualified_name"],
                         "value": value, "context_ref": fact["context_ref"]})
    proof = _selected_impairment_inclusion(raw_bytes, parsed, rows) if rows else None
    if proof is None:
        return None
    return {"selected_fact": proof["selected_fact"], "table_id": proof["table_id"],
            "table_grid_sha256": proof["table_grid_sha256"],
            "selected_visible_total": proof["selected_visible_total"],
            "included_component": proof["included_component"],
            "footnote_text": " ".join(proof["footnote"]["text"].split()),
            "footnote_span_sha256": proof["footnote"]["span_sha256"]}


# #28's check, seen through the release-aware view (historical_dei): it asks
# whether a fact's concept is US GAAP in the year-only namespace form.
_UNRECONCILED_CONTRACT_AMORTIZATION = release_aware(
    _contract_scope._unreconciled_contract_amortization)


def contract_amortization_unreconciled(*, repo_root, prepared, period, observations):
    """#28's answer on whether the filing reports an amortization a composed D&A does not take.

    #28 found that an annual report can state, apart from the depreciation and
    intangible-asset amortization the approved composition takes, a positive
    amortization of capitalized contract costs on its own line, which the
    composition neither adds nor is shown to include
    (``b03_contract_amortization_scope``, ``[shared-with-#47]`` commit
    ``45bcce3d``; docs/evidence/issue28_continuous/
    b03-marriott-contract-amortization-20260929/). #28 later proved, from the
    filing's own income-statement rows, that such a line can be a gross-to-net
    revenue deduction (``7bb17621``): gross revenues, contract amortization
    and net revenues in consecutive rows whose displayed amounts reconcile to
    the tagged fact. Then the answer is ``blocked: False`` and the composition
    stands - the amortization is not D&A, so nothing is added. Otherwise the
    relation is unproved, a composed total is not provably the whole D&A, and
    it is withheld by name - never added to and never recomputed.

    Asked with #28's own check, not a copy of it: the case it reads is the
    pinned input's source proofs, the target period and the route's B03
    observations, and it reads the same primary document the pinned input
    admitted. A direct D&A total is not its question and gets None, as there.
    The caller acts on ``blocked``, as #28's own consumers do. Through the
    release-aware view: #28's check asks whether a fact's concept is US GAAP
    with the frozen year-only namespace, which a FY2021 report's dated release
    fails.
    """
    return _UNRECONCILED_CONTRACT_AMORTIZATION(
        case={"observations": observations, "target_period": period,
              "source_proofs": prepared["source_proofs"]},
        data_root=Path(repo_root))


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
    from . import ordinary_income_input
    income_input = release_aware(ordinary_income_input).prepare_current_income_input(
        repo_root=repo_root, company_id=company_id)
    proved = income_input["annual_input"]["filing"]["accessionNumber"]
    if proved != prepared["filing"]["accessionNumber"]:
        return None
    return income_input


def e01_confirmation_request(*, repo_root: Path, company_id: str, period_selection):
    """The content-confirmation request of E01's window at a pinned period, and its source proofs.

    Built by the route itself, up to the point where it would ask for a
    registered confirmation - the same prepared input, amendment answer, window,
    event discovery and candidate reading - so the question a model is asked is
    the one the route will check the answer against. A window with no candidate
    item has no request; the route answers it zero.
    """
    try:
        component = resolve_historical_zero_ai_metric(
            repo_root=repo_root, company_id=company_id, metric_id="E01",
            period_selection=period_selection, _build_request_only=True)
    except _ConfirmationRequestBuilt as built:
        return built.request, built.proofs
    # No request: either the window has no candidate item and is answered, or
    # the route stopped before reading one - and then the reason is the
    # route's, not "no candidate".
    result = component["result"]
    if result["publication"] == "PUBLISHED":
        raise NormalZeroAiError("HISTORICAL_E01_WINDOW_HAS_NO_CANDIDATE_TO_CONFIRM")
    raise NormalZeroAiError("HISTORICAL_E01_WINDOW_HAS_NO_REQUEST:" + str(result["reason_code"]),
                            component["selection"].get("category", "IMPLEMENTATION_GAP"))


def resolve_historical_zero_ai_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                      period_selection, confirmation_mode=None,
                                      _build_request_only=False):
    """Resolve revenue, or EBITDA margin with its rebuilt revenue dependency.

    Values come from the selected filing's own accession, which is the same
    first-report semantics the current route uses, applied to a past target.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_ZERO_AI_METRIC_NOT_WIRED:" + metric_id, "IMPLEMENTATION_GAP")
    _need(confirmation_mode is None or metric_id in SUCCESSOR_EVENT_ROUTES,
          "HISTORICAL_CONFIRMATION_MODE_WITHOUT_CONFIRMATION", "IMPLEMENTATION_GAP")
    authority = _authority(repo_root)
    if metric_id in SUCCESSOR_EVENT_ROUTES:
        # The successor route is read from the data root the Run is built in;
        # it must be the code tree's own, as every frozen authority file is.
        relative = SUCCESSOR_EVENT_ROUTES[metric_id]
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root, repo_relative_path=relative))
              == expected, "HISTORICAL_EVENT_SUCCESSOR_ROUTE_NOT_INSTALLED:" + relative, "AUTHORITY_CONFLICT")
        authority = {**authority, relative: expected}
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
    amendment_refusal, per_filing = None, []
    if prepared["amendments"] and income_input is None:
        from .historical_amendment_admission import (AmendmentAdmissionError,
                                                     amendment_admission,
                                                     per_filing_admissions)
        try:
            per_filing = per_filing_admissions(amendment_admission(
                repo_root=repo_root, company_id=company_id, metric_ids=[metric_id],
                prepared=prepared, event_metric_ids=EVENT_METRICS))
        except AmendmentAdmissionError as error:
            # A decided answer, carried as this metric's withheld result with
            # its own reason code and category - the way the Company Facts
            # route carries the same refusal. Failing the attempt instead left
            # no public row for a question the policy had already answered,
            # beside withheld rows for the same refusal in the same year.
            amendment_refusal = str(error)
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
        if metric_id in SUCCESSOR_EVENT_ROUTES:
            # The owner's content-confirmed meaning is a new route with its own
            # hash, so its Spec - and every acceptance bound to a Spec - is not
            # the approved item-rule route's. The frozen catalog is left as it
            # is; only this metric's route is substituted.
            route = successor_event_route(repo_root=repo_root, metric_id=metric_id,
                                          frozen_route=catalog["routes"][metric_id])
            catalog = {**catalog, "routes": {**catalog["routes"], metric_id: route}}
            spec_origin = {"catalog_path": SUCCESSOR_EVENT_ROUTES[metric_id], "metric_id": metric_id}
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
    confirmation = None
    try:
        if amendment_refusal is not None:
            raise _AmendmentRefused
        if metric_id in EVENT_METRICS:
            if registered_event:
                # The predecessor's filings are read through the same reader,
                # from each registered CIK's own submissions, and their
                # accessions may not overlap. This is source discovery across
                # registered identities; it authorises no financial
                # combination, which the scope record states explicitly.
                claims, source_sets, events, evidence = registered_event_sources(
                    repo_root=repo_root, reader=reader, prepared=prepared,
                    inventory=inventory, period=period)
                registered_scope = {**registered_scope, **evidence,
                                    "pinned_period": dict(pinned),
                                    "status": "SOURCE_RECONSTRUCTED_FROM_REGISTERED_CIKS"}
            else:
                claims, source_sets, events = event_sources(
                    repo_root=repo_root, reader=reader, prepared=prepared, inventory=inventory)
            filings.extend(events)
            route = catalog["routes"][metric_id]
            # The frozen matcher reads a keyword item's alias off the claim's
            # brief, which for an hdr-coded filing is a sentence the program
            # wrote; the one route that had keyword items now reads its
            # candidates' own text instead. A route with keyword items reaching
            # here would be answered by that brief, so it stops by name.
            _need(not route["keyword_item_rules"], "HISTORICAL_EVENT_KEYWORD_ROUTE_NOT_READ:" + metric_id,
                  "IMPLEMENTATION_GAP")
            if "confirmation" in route:
                # Every candidate is read from its own text; none is confirmed
                # here. A window with a candidate is withheld by name until its
                # confirmations are registered; a window with none is answered
                # through the route's own matcher, which then finds no
                # candidate code among the claims.
                confirmation = content_confirmation_candidates(
                    repo_root=repo_root, route=route, claims=claims, records=reader.records,
                    keep_text=True)
                if confirmation["candidates"]:
                    request = confirmation_request(
                        route=route, company_id=company_id, target_cik=prepared["entity"],
                        window=period, candidates=confirmation["candidates"])
                    if _build_request_only:
                        raise _ConfirmationRequestBuilt(request, list(
                            {content_hash(value=p): p for p in [
                                *prepared["source_proofs"],
                                *[entry["proof"] for entry in reader.proofs.values()]]}.values()))
                    try:
                        registered = load_registered_confirmation(
                            data_root=repo_root, request=request,
                            period_selection_id=period_selection["selection_id"],
                            mode=confirmation_mode)
                    except ConfirmationNotRegistered:
                        raise _ConfirmationNotRegistered
                    confirmation = {**confirmation, "registered": {
                        "input_record_id": registered["input_record_id"],
                        "request_id": registered["request_id"], "mode": registered["mode"]}}
                    for candidate in confirmation["candidates"]:
                        candidate["confirmation"] = registered["decisions"][
                            item_id(candidate)]["decision"]
                    # Carried for installation whichever way it answers: a
                    # window withheld because an item's text does not settle
                    # it is rebuilt from the data root by the same record, and
                    # without the installed copy that rebuild would read "not
                    # registered" instead.
                    confirmation["registered_record"] = registered
                    if registered["counted"]["value"] is None:
                        raise _ConfirmationUnsettled(registered)
                    # The route's own matcher, over the confirmed candidates
                    # and every claim that is not a candidate: a candidate the
                    # confirmation says does not report a transaction is not
                    # an announcement, and the matcher then never sees it.
                    confirmed = {candidate["verified_claim_id"]
                                 for candidate in confirmation["candidates"]
                                 if candidate["confirmation"] == "REPORTS_A_TRANSACTION"}
                    candidate_ids = {candidate["verified_claim_id"]
                                     for candidate in confirmation["candidates"]}
                    claims = [claim for claim in claims
                              if claim["verified_claim_id"] not in candidate_ids
                              or claim["verified_claim_id"] in confirmed]
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
            if confirmation is not None:
                binding["content_confirmation"] = compact_confirmation(confirmation)
                if "registered" in confirmation:
                    binding["content_confirmation"]["registered"] = confirmation["registered"]
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
            if confirmation is not None:
                selection["content_confirmation"] = _without_text(confirmation)
            raise _EventRouteResolved
        # The statement source set is proved against the document that lists
        # the filing; the event branch above keeps the main index, because its
        # own walk reads the history blocks from it.
        listed_in = filing_inventory(reader=reader, inventory=inventory,
                                     period_selection=period_selection,
                                     cik=prepared["entity"],
                                     accession=prepared["filing"]["accessionNumber"])
        manifest = _exact_set(prepared, listed_in, facts_source, "companyfacts")
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
        da_scope = None
        if metric_id == "B03" and result["publication"] == "PUBLISHED":
            da_scope = depreciation_scope(raw_bytes=reader.primary(prepared["filing"])["raw_bytes"],
                                       period=period, observations=observations)
            if da_scope["status"] == "WITHHOLD":
                raise _DepreciationScopeUnproven(da_scope)
            if da_scope["status"] == "KEEP":
                unreconciled = contract_amortization_unreconciled(
                    repo_root=repo_root, prepared=prepared, period=period,
                    observations=observations)
                # #28's answer blocks only when the separate amortization is
                # not proved to be a gross-to-net revenue deduction; a proved
                # one is excluded from D&A there and here, and kept on record.
                if unreconciled is not None and unreconciled["blocked"]:
                    raise _DepreciationScopeUnproven({
                        **da_scope, "status": "WITHHOLD", "contract_amortization": unreconciled,
                        "why": "THE_FILING_REPORTS_AN_AMORTIZATION_THE_COMPOSITION_DOES_NOT_TAKE"})
                if unreconciled is not None:
                    da_scope = {**da_scope, "contract_amortization": unreconciled}
            if da_scope["status"] == "RETAKE":
                # The filing's own composition proves a later direct candidate;
                # the frozen selector is asked again over a pool without the
                # direct candidates it disproves, so it still does the choosing.
                disproved = set(DIRECT) - {da_scope["concept"]}
                facts = [fact for fact in facts
                         if str(fact["concept"]).split(":")[-1] not in disproved]
                result, trace, observations = calculate_metric(
                    compiled_spec=spec, target=execution_target, company_traits=traits,
                    structured_facts=facts, verified_observations=reusable)
                # The retaken total is asked the question a kept one is.
                retaken = [o for o in observations
                           if o["semantic_role"] == "depreciation_and_amortization"]
                included = (impairment_included(
                    raw_bytes=reader.primary(prepared["filing"])["raw_bytes"], period=period,
                    observation=retaken[0]) if result["publication"] == "PUBLISHED" and retaken
                    else None)
                if included is not None:
                    raise _DepreciationScopeUnproven({
                        **da_scope, "status": "WITHHOLD", "impairment_inclusion": included,
                        "why": "THE_SELECTED_TOTAL_INCLUDES_IMPAIRMENT_RELATED_DEPRECIATION"})
        selection = {"source_candidate_count": len(facts),
                     "selected_fact_ids": [o["source_binding"]["fact_id"] for o in observations],
                     "source_reported_periods": sorted({(f["period_start"], f["period_end"])
                                                        for f in facts}),
                     "reason_code": result["reason_code"]}
        if da_scope is not None:
            selection["depreciation_scope"] = da_scope
    except _EventRouteResolved:
        pass
    except _DepreciationScopeUnproven as withheld:
        # B03 still carries B01: the dependency was computed above and its
        # records are already in dependency_records, so only B03 is withheld.
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code=DA_SCOPE_REASON)
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": withheld.answer["why"],
                     "category": "DISCLOSURE_SCOPE_UNPROVEN",
                     "depreciation_scope": withheld.answer}
    except _ConfirmationUnsettled as unsettled:
        # The registered answer says an item's own text does not settle it:
        # most candidate items incorporate an exhibit, and none is saved.
        # Counting the settled ones would report a lower bound as the count.
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code=unsettled.registered["counted"]["withheld_reason"])
        observations = []
        selection = {"reason_code": result["reason_code"],
                     "category": "CONTENT_CONFIRMATION_DOES_NOT_SETTLE_IT",
                     "unsettled_items": unsettled.registered["counted"]["items"],
                     "content_confirmation": _without_text(confirmation)}
    except _ConfirmationNotRegistered:
        # A candidate may or may not report an M&A transaction; until its
        # content confirmation is registered the window is not counted, and the
        # withheld result lists exactly which item spans are waiting.
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code=CONFIRMATION_REASON)
        observations = []
        selection = {"reason_code": result["reason_code"],
                     "category": "CONTENT_CONFIRMATION_NOT_EXECUTED",
                     "source_event_accessions": sorted({f["accessionNumber"]
                                                        for f in filings[1:]}),
                     "content_confirmation": _without_text(confirmation)}
    except EventItemTextError as error:
        # An item whose own text could not be read never counts and never
        # silently fails to count; the reason names it.
        result, trace = withheld_metric_result(
            compiled_spec=spec, target=target,
            reason_code=(NOT_LOCATED_REASON if error.category == "IMPLEMENTATION_GAP"
                         else "HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED"))
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": str(error),
                     "category": error.category}
    except _AmendmentRefused:
        result, trace = withheld_metric_result(
            compiled_spec=spec, target=target,
            reason_code="HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED")
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": amendment_refusal,
                     "category": "APPROVED_AMENDMENT_POLICY_REFUSAL",
                     "amendment_policy_decision": amendment_refusal}
    except _SOURCE_ERRORS as error:
        reason = str(error)
        result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                               reason_code="HISTORICAL_ZERO_AI_SOURCE_ROUTE_UNRESOLVED")
        observations = []
        selection = {"reason_code": result["reason_code"], "reason": reason,
                     "category": getattr(error, "category", "SOURCE_INTEGRITY_ERROR")}
    # A withheld result still arrives with its dependencies' results: the Run
    # requires B03 to carry B01's result and trace, and a B03 withheld before
    # B01 was computed left the Run's dependency set incomplete - the attempt
    # failed instead of withholding. The dependency was not computed for the
    # same reason, so it is withheld with the same reason code.
    if (result["publication"] == "WITHHELD" and dependency_specs
            and not any(record["record_type"] == "METRIC_RESULT"
                        for record in dependency_records)):
        for dependency in dependency_specs.values():
            dependency_result, dependency_trace = withheld_metric_result(
                compiled_spec=dependency, target=target, reason_code=result["reason_code"])
            dependency_records.extend([dependency_trace, dependency_result])
    if per_filing:
        # A result that relied on the owner's per-filing admission says so,
        # with the conditions that held; one the policy alone decided is
        # unchanged.
        selection = {**selection, "amendment_per_filing_admission": per_filing}
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
    if confirmation is not None and confirmation.get("registered_record") is not None:
        body["registered_confirmation"] = confirmation["registered_record"]
    body = exact_json_value(body)
    return {**body, "input_binding_id": content_hash(value=body["input_binding"]),
            "component_id": content_hash(value=body)}


def _without_text(confirmation):
    """A confirmation as a record carries it: every candidate's hash, not its text."""
    if confirmation is None:
        return None
    kept = {key: value for key, value in confirmation.items() if key != "registered_record"}
    kept["candidates"] = [{key: value for key, value in candidate.items() if key != "text"}
                          for candidate in confirmation["candidates"]]
    return kept


def verify_historical_zero_ai_metric(*, candidate, repo_root: Path, company_id: str,
                                     metric_id: str, period_selection):
    rebuilt = resolve_historical_zero_ai_metric(repo_root=repo_root, company_id=company_id,
                                                metric_id=metric_id,
                                                period_selection=period_selection)
    _need(candidate == rebuilt, "HISTORICAL_ZERO_AI_SOURCE_REPLAY_CHANGED",
          "SOURCE_REPLAY_CONFLICT")
    return rebuilt
