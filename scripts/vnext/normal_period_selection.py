"""Prove which annual filing a requested historical period means.

A caller asks for a company and a period: either an SEC annual report end date
or an issuer fiscal year. The program proves the filing. A caller-supplied
accession, period start/end pair or answer is never accepted, and a selection
that a caller hands back is re-derived from saved source before it is used, so
re-signed JSON cannot introduce a different filing.

The selection is metadata only. The issuer fiscal-year label and the real
annual interval still come from that filing's own DEI contexts, through the
unchanged ``annual_period`` reader; this module only checks that what the
document says matches what the caller asked for.
"""
from datetime import date
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import (NormalAnnualInputError, _cik, _registry_rows,
                                  _subject_policy)
from .normal_history_catalog import (HistoryCatalogError, annual_periods,
                                     catalog_identity, load_history_for_period)
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


POLICY_PATH = "config/normal_period_selection_v1.json"
RECORD_TYPE = "ORDINARY_HISTORICAL_PERIOD_SELECTION"
_FIELDS = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")


class PeriodSelectionError(NormalAnnualInputError):
    """A selection limitation; never a financial or disclosure conclusion."""


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise PeriodSelectionError(reason, category)


def _policy(repo_root):
    installed = strict_json_file(path=resolve_repository_file(
        repo_root=repo_root, repo_relative_path=POLICY_PATH))
    _need(installed == strict_json_file(path=ROOT / POLICY_PATH)
          and installed["policy_id"] == "ordinary_period_selection_v1"
          and installed["caller_supplied_accession_authorized"] is False
          and installed["latest_restated_view_authorized"] is False
          and installed["point_in_time_view_authorized"] is False,
          "ORDINARY_PERIOD_SELECTION_INSTALLED_POLICY_CHANGED", "AUTHORITY_CONFLICT")
    return installed


def _report_end(value):
    try:
        _need(type(value) is str and date.fromisoformat(value).isoformat() == value,
              "ORDINARY_PERIOD_SELECTION_REPORT_END_INVALID", "IMPLEMENTATION_GAP")
    except ValueError as error:
        raise PeriodSelectionError("ORDINARY_PERIOD_SELECTION_REPORT_END_INVALID",
                                   "IMPLEMENTATION_GAP") from error
    return value


def _derive(*, repo_root, company_id, report_end, requested_fiscal_year):
    """Build the selection body from the complete saved annual catalog."""
    policy = _policy(repo_root)
    companies = [c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id]
    _need(len(companies) == 1, "ORDINARY_PERIOD_SELECTION_COMPANY_NOT_UNIQUE", "IMPLEMENTATION_GAP")
    company = companies[0]
    subject_policy = _subject_policy(company)
    cik = company["primary_cik"]
    try:
        history = load_history_for_period(repo_root=repo_root, company_id=company_id,
                                          report_end=report_end)
        periods = annual_periods(history=history)
    except HistoryCatalogError as error:
        raise PeriodSelectionError(str(error), error.category) from error
    _need(not history["limitations"], "ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT",
          "SOURCE_UNAVAILABLE")
    _need(not history["unloaded_history_reaching_period"],
          "ORDINARY_PERIOD_SELECTION_RELEVANT_HISTORY_NOT_LOADED", "SOURCE_UNAVAILABLE")
    index = next((i for i, item in enumerate(periods) if item["report_date"] == report_end), None)
    registrant = None
    if index is None:
        found = _predecessor_period(repo_root=repo_root, company=company,
                                    report_end=report_end, primary_periods=periods,
                                    primary_history=history)
        if found is not None:
            history, periods, index, registrant = found
            cik = registrant["reporting_cik"]
            subject_policy = registrant.pop("period_subject_policy")
            _need(not history["limitations"],
                  "ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT", "SOURCE_UNAVAILABLE")
            _need(not history["unloaded_history_reaching_period"],
                  "ORDINARY_PERIOD_SELECTION_RELEVANT_HISTORY_NOT_LOADED", "SOURCE_UNAVAILABLE")
    _need(index is not None, "ORDINARY_PERIOD_SELECTION_REPORT_END_NOT_IN_SAVED_SUBMISSIONS",
          "SOURCE_UNAVAILABLE")
    target = periods[index]
    _need(target["original_status"] == "SINGLE_ORIGINAL_ANNUAL",
          "ORDINARY_PERIOD_SELECTION_ANNUAL_MISSING_OR_AMBIGUOUS",
          "SOURCE_UNAVAILABLE" if target["original_status"] == "NO_ORIGINAL_ANNUAL"
          else "SOURCE_INTEGRITY_ERROR")
    filing = target["original"]
    _need(filing["filingDate"] >= filing["reportDate"] == report_end,
          "ORDINARY_PERIOD_SELECTION_FILING_DATE_CONFLICT")
    following = periods[index + 1] if index + 1 < len(periods) else None
    prior = following["original"] if following else None
    body = {"record_type": RECORD_TYPE, "schema_version": 1,
            "policy_id": policy["policy_id"], "policy_sha256": sha256_file(path=ROOT / POLICY_PATH),
            "company_id": company_id, "reporting_cik": str(_cik(cik)),
            "subject_policy": subject_policy,
            "target_report_end": report_end,
            "requested_fiscal_year": requested_fiscal_year,
            "current_filing": filing, "current_amendments": target["amendments"],
            "prior_report_end": following["report_date"] if following else None,
            "prior_filing": prior, "prior_amendments": following["amendments"] if following else [],
            "prior_status": ("SAME_CIK_PRIOR_DISCOVERED" if prior
                             else "NO_SAME_CIK_PRIOR_IN_COMPLETE_SAVED_SUBMISSIONS"),
            "dependency_filing_roles": {
                "target_primary": filing["accessionNumber"],
                "target_amendment_primary": [a["accessionNumber"] for a in target["amendments"]],
                "prior_annual_primary": prior["accessionNumber"] if prior else None,
                "prior_amendment_primary": [a["accessionNumber"] for a in
                                            (following["amendments"] if following else [])]},
            "filing_selection_policy_id": policy["filing_selection_policy_id"],
            "value_selection_policy_id": policy["value_selection_policy_id"],
            "amendment_policy_id": policy["amendment_policy_id"],
            "source_set_identity": catalog_identity(history=history)["catalog_id"],
            "loaded_inventories": history["loaded_inventories"],
            "latest_restated_values_used": False,
            "caller_supplied_selection_trusted": False,
            "production_authorized": False}
    # Present only when the period was filed by a registered predecessor, so a
    # selection of the primary's own period is exactly what it was before.
    if registrant is not None:
        body["period_registrant"] = registrant
    return {**body, "selection_id": content_hash(value=body)}


def _predecessor_period(*, repo_root, company, report_end, primary_periods,
                        primary_history=None):
    """A period a registered predecessor filed, where the successor filed none.

    Issue #47 section 7.3: a predecessor's years are read from that year's own
    filings, with the registrant that filed them; today's successor-only status
    is not applied backward. So a predecessor's period is looked up only when
    the primary's complete catalog has no annual report there and the report
    end falls before the primary's oldest annual report - the successor's own
    periods are never answered from the predecessor - and exactly one
    registered predecessor must have filed it.

    The period's subject policy is that registrant's own: one CIK, with its
    prior found in the same catalog. That is what every route reads as a
    continuous primary, and it is true of these years - the registrant was the
    filer then - while nothing here combines two registrants: the prior of a
    predecessor period is never the successor's, and the prior of the
    successor's first period is never the predecessor's.

    Returns ``(history, periods, index, registrant)`` or None.
    """
    subject = _subject_policy(company)
    predecessors = subject.get("related_predecessor_ciks", ())
    oldest = primary_periods[-1]["report_date"] if primary_periods else None
    if not predecessors or (oldest is not None and report_end >= oldest):
        return None
    matches = []
    for predecessor in predecessors:
        try:
            history = load_history_for_period(repo_root=repo_root,
                                              company_id=company["company_id"],
                                              report_end=report_end, cik=predecessor)
            periods = annual_periods(history=history)
        except HistoryCatalogError as error:
            raise PeriodSelectionError(str(error), error.category) from error
        index = next((i for i, item in enumerate(periods) if item["report_date"] == report_end),
                     None)
        if index is not None:
            matches.append((history, periods, index, predecessor))
    if not matches:
        return None
    _need(len(matches) == 1, "ORDINARY_PERIOD_SELECTION_PREDECESSOR_PERIOD_AMBIGUOUS")
    history, periods, index, predecessor = matches[0]
    reporting = str(_cik(predecessor))
    registrant = {"role": "PREDECESSOR", "reporting_cik": reporting,
                  "successor_cik": str(_cik(company["primary_cik"])),
                  "company_subject_policy": subject,
                  "successor_oldest_annual_report_end": oldest,
                  # What of the primary's own catalog was read to show it has
                  # nothing here. The prepared input admits these blocks too:
                  # re-deriving this record reads them, so an installed data
                  # root that lacked them could not replay it.
                  "primary_catalog": (None if primary_history is None else {
                      "catalog_id": catalog_identity(history=primary_history)["catalog_id"],
                      "loaded_inventories": primary_history["loaded_inventories"]}),
                  "basis": ("the registry names this CIK a predecessor of the company, the "
                            "primary's complete saved catalog has no annual report at this "
                            "report end and none older, and this registrant's own saved "
                            "catalog has the period"),
                  "cross_entity_combination_authorized": False,
                  "period_subject_policy": {"mode": "CONTINUOUS_PRIMARY", "selected_cik": reporting,
                                            "cross_entity_combination_authorized": False}}
    return history, periods, index, registrant


def resolve_period_selection(*, repo_root: Path, company_id: str, report_end=None,
                             fiscal_year=None):
    """Return the verified selection for one requested historical period.

    Exactly one of ``report_end`` (an SEC annual report end date) and
    ``fiscal_year`` (an issuer fiscal-year label) must be given. A fiscal-year
    request is resolved by reading the DEI contexts of the candidate filings
    themselves, never by assuming a calendar relationship between a report end
    and an issuer label.
    """
    _need((report_end is None) != (fiscal_year is None),
          "ORDINARY_PERIOD_SELECTION_EXACTLY_ONE_REQUEST_REQUIRED", "IMPLEMENTATION_GAP")
    if report_end is not None:
        return _derive(repo_root=repo_root, company_id=company_id,
                       report_end=_report_end(report_end), requested_fiscal_year=None)
    _need(type(fiscal_year) is int and 1900 <= fiscal_year <= 9998,
          "ORDINARY_PERIOD_SELECTION_FISCAL_YEAR_INVALID", "IMPLEMENTATION_GAP")
    try:
        # A report end can only carry this label if it falls in the label's own
        # year or the next one, so the catalog is loaded down to that boundary.
        history = load_history_for_period(repo_root=repo_root, company_id=company_id,
                                          report_end=str(fiscal_year) + "-01-01")
    except HistoryCatalogError as error:
        raise PeriodSelectionError(str(error), error.category) from error
    _need(not history["limitations"], "ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT",
          "SOURCE_UNAVAILABLE")
    # An issuer label never precedes its own period start year and never follows
    # its period end year, so only these report ends can carry it. Each one is
    # then read; none is chosen by arithmetic on the date.
    primary_periods = annual_periods(history=history)
    candidates = [period for period in primary_periods
                  if period["original"] is not None
                  and int(period["report_date"][:4]) in {fiscal_year, fiscal_year + 1}]
    # A registered predecessor's periods are candidates on the same terms as in
    # _derive: only older than the primary's oldest annual report, and read
    # from that registrant's own catalog. _derive then re-proves the choice.
    companies = [c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id]
    _need(len(companies) == 1, "ORDINARY_PERIOD_SELECTION_COMPANY_NOT_UNIQUE", "IMPLEMENTATION_GAP")
    oldest = primary_periods[-1]["report_date"] if primary_periods else None
    for predecessor in _subject_policy(companies[0]).get("related_predecessor_ciks", ()):
        try:
            earlier = load_history_for_period(repo_root=repo_root, company_id=company_id,
                                              report_end=str(fiscal_year) + "-01-01",
                                              cik=predecessor)
        except HistoryCatalogError as error:
            raise PeriodSelectionError(str(error), error.category) from error
        _need(not earlier["limitations"], "ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT",
              "SOURCE_UNAVAILABLE")
        candidates.extend(period for period in annual_periods(history=earlier)
                          if period["original"] is not None
                          and (oldest is None or period["report_date"] < oldest)
                          and int(period["report_date"][:4]) in {fiscal_year, fiscal_year + 1})
    _need(bool(candidates), "ORDINARY_PERIOD_SELECTION_FISCAL_YEAR_NOT_IN_SAVED_SUBMISSIONS",
          "SOURCE_UNAVAILABLE")
    matched, unreadable = [], []
    for period in candidates:
        try:
            observed = issuer_fiscal_year(repo_root=repo_root, company_id=company_id,
                                          report_end=period["report_date"])
        except (NormalAnnualInputError, ValueError):
            unreadable.append(period["report_date"])
            continue
        if observed == fiscal_year:
            matched.append(period["report_date"])
    # Uniqueness is only proven when every candidate was actually read. An
    # unread neighbour is a source gap, not a reason to assume it is a
    # different year; the objective report-end request stays available.
    _need(not unreadable, "ORDINARY_PERIOD_SELECTION_CANDIDATE_SOURCE_UNAVAILABLE:"
          + ",".join(unreadable), "SOURCE_UNAVAILABLE")
    _need(len(matched) == 1, "ORDINARY_PERIOD_SELECTION_FISCAL_YEAR_MISSING_OR_AMBIGUOUS",
          "SOURCE_UNAVAILABLE" if not matched else "SOURCE_INTEGRITY_ERROR")
    return _derive(repo_root=repo_root, company_id=company_id, report_end=matched[0],
                   requested_fiscal_year=fiscal_year)


def restore_period_selection(*, repo_root: Path, company_id: str, target_report_end: str,
                             requested_fiscal_year=None):
    """Rebuild a selection that was already resolved, from its own recorded request.

    A replay restores the request that was installed, not a fresh one. A period
    installed as an issuer fiscal year keeps that label inside its identity, so
    re-deriving it from the report end alone produces a different selection and
    would reject a valid package for a difference that is not a change in the
    sources.

    The body is rebuilt from saved source, so a recorded request cannot
    introduce a different filing, and the label claim is re-proven downstream
    against the target filing's own DEI contexts by ``check_selected_label``.
    What this deliberately does not re-prove is that no neighbouring report end
    now carries the same label: that neighbour is an input of no period here and
    is absent from an installed data root by design. Label uniqueness is proven
    once, when the fiscal year is first resolved against the complete saved
    submissions history.
    """
    _need(requested_fiscal_year is None
          or (type(requested_fiscal_year) is int and 1900 <= requested_fiscal_year <= 9998),
          "ORDINARY_PERIOD_SELECTION_FISCAL_YEAR_INVALID", "IMPLEMENTATION_GAP")
    return _derive(repo_root=repo_root, company_id=company_id,
                   report_end=_report_end(target_report_end),
                   requested_fiscal_year=requested_fiscal_year)


def issuer_fiscal_year(*, repo_root: Path, company_id: str, report_end: str):
    """Resolve one selected period's issuer fiscal-year label from its own source.

    The label comes from the unchanged fiscal-label policy reading that filing's
    own DEI contexts and Company Facts metadata, not from arithmetic on the
    report end date. The probe pins the period by report end only, so it places
    no fiscal-year expectation on the source it is about to read.
    """
    # Imported here because the historical input layer consumes this module.
    from .historical_annual_input import prepare_historical_annual_input
    selection = _derive(repo_root=repo_root, company_id=company_id,
                        report_end=_report_end(report_end), requested_fiscal_year=None)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=selection)
    return prepared["table_input"]["target_period"]["fiscal_year"]


def selected_historical_filing(*, repo_root: Path, company, submissions, period_selection):
    """Re-derive a pinned selection from source and return the filing set.

    The returned shape is exactly what the unchanged latest-period selector
    returns, so downstream preparation does not branch on how the period was
    chosen.
    """
    _need(type(period_selection) is dict and period_selection.get("record_type") == RECORD_TYPE,
          "ORDINARY_PERIOD_SELECTION_RECORD_REQUIRED", "IMPLEMENTATION_GAP")
    _need(period_selection.get("company_id") == company["company_id"],
          "ORDINARY_PERIOD_SELECTION_COMPANY_CONFLICT")
    # The submissions read are the reporting registrant's: the primary's, or a
    # registered predecessor's for a period that registrant filed. Which one it
    # is is proven by the re-derivation below, not taken from the record.
    reporting = period_selection.get("reporting_cik")
    _need(reporting is not None and _cik(submissions["cik"]) == _cik(reporting)
          and (_cik(reporting) == _cik(company["primary_cik"])
               or str(_cik(reporting)) in _subject_policy(company).get(
                   "related_predecessor_ciks", ())),
          "SUBMISSIONS_ENTITY_CONFLICT")
    rebuilt = _derive(repo_root=repo_root, company_id=company["company_id"],
                      report_end=_report_end(period_selection.get("target_report_end")),
                      requested_fiscal_year=period_selection.get("requested_fiscal_year"))
    _need(rebuilt == period_selection
          and content_hash(value={k: v for k, v in rebuilt.items() if k != "selection_id"})
          == rebuilt["selection_id"],
          "ORDINARY_PERIOD_SELECTION_CHANGED")
    return {"filing": {key: rebuilt["current_filing"][key] for key in _FIELDS},
            "amendments": [{key: item[key] for key in _FIELDS}
                           for item in rebuilt["current_amendments"]],
            "prior_period_amendments": [{key: item[key] for key in _FIELDS}
                                        for item in rebuilt["prior_amendments"]]}


def check_selected_period(*, period_selection, target_period):
    """The selected filing's own annual interval must end where it was pinned."""
    if period_selection is None:
        return
    _need(target_period["period_end"] == period_selection["target_report_end"],
          "ORDINARY_PERIOD_SELECTION_PERIOD_END_CONFLICT")


def check_selected_label(*, period_selection, target_period):
    """A requested issuer fiscal year must be what the source actually resolves.

    The label is owned by the frozen fiscal-label policy, so this check runs
    after that policy has read the source, never before it.
    """
    if period_selection is None:
        return
    check_selected_period(period_selection=period_selection, target_period=target_period)
    requested = period_selection.get("requested_fiscal_year")
    _need(requested is None or target_period["fiscal_year"] == requested,
          "ORDINARY_PERIOD_SELECTION_FISCAL_LABEL_CONFLICT")
