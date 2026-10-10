"""Select the governance filing identities a pinned annual period means.

The frozen ``select_governance_metadata`` decides which annual report is the
current one by taking the maximum report date across every loaded row and
requiring it to equal the period it was given::

    current_end = max(r["reportDate"] for r in rows if r["form"] in {"10-K", "10-K/A"})
    _need(len(current) == 1 and current_end == period["period_end"], ...)

That is right while "current" means "the latest one filed", and it is exactly
wrong for a pinned earlier period: the maximum is the newest annual report in
the index, so asking for any year but the newest refuses. It is the same
conflation ``historical_metadata_context`` already had to undo for the text
roles, restated over the governance roles.

What this owns is the selection. The blocks come from
``load_history_for_period``, which loads exactly the blocks one target period
and its prior year can need and proves that no unread block could hold a filing
reaching either - so the rows here are complete for the question being asked,
and the prior year is part of that question rather than a sixth output year.

C04 is why this exists: ``resolve_c04`` compares the auditor named in the
pinned period's annual report with the one named in the prior period's, and
reads the fiscal window's 8-K item index independently so that equal names are
not turned into a confirmed no-change flag without it.
"""
from typing import Mapping, Sequence
from datetime import date, timedelta

RECORD_TYPE = "HISTORICAL_GOVERNANCE_SELECTION"
# The frozen module's own event forms, imported rather than restated so the two
# cannot drift apart.
from .normal_governance_input import _EVENT_FORMS, _order  # noqa: E402


class HistoricalGovernanceError(ValueError):
    """A pinned period's governance filings are not in the loaded blocks."""


def _need(condition, reason, category=None):
    if not condition:
        error = HistoricalGovernanceError(reason)
        if category is not None:
            error.category = category
        raise error


def select_historical_governance_metadata(*, prepared: Mapping, history: Mapping,
                                          event_forms=None,
                                          identity_fields: Sequence[str] = (
                                              "accessionNumber", "primaryDocument",
                                              "reportDate", "form")):
    """The pinned period's annual chain, its prior chain and its event window.

    Args:
        prepared: The historical annual input, which owns the selected filing.
        history: ``load_history_for_period`` output for that same period.
        identity_fields: The fields the selection must agree with the prepared
            input on, so a row that merely shares a report date cannot stand in
            for the filing the period selection pinned.

    Returns:
        Selected C04 annual/prior chains and event metadata only. This does
        not select compensation/governance proxy inputs or infer their period.

    Raises:
        HistoricalGovernanceError: Incomplete metadata, a changed selected CIK,
            an absent/ambiguous target, or identity divergence. Missing same-CIK
            prior is returned explicitly; no successor is borrowed as prior.
    """
    period = prepared["table_input"]["target_period"]
    _need(not history.get("limitations")
          and not history.get("unloaded_history_reaching_period"),
          "HISTORICAL_GOVERNANCE_METADATA_WINDOW_INCOMPLETE", "SOURCE_UNAVAILABLE")
    if "reporting_cik" in history:
        _need(str(int(history["reporting_cik"])) == str(int(prepared["entity"])),
              "HISTORICAL_GOVERNANCE_SELECTED_CIK_CHANGED", "SOURCE_INTEGRITY_ERROR")
    forms = _EVENT_FORMS if event_forms is None else event_forms
    _need(type(forms) in (list, tuple, set, frozenset)
          and set(forms) in (set(_EVENT_FORMS), {'8-K', '8-K/A', '8-K12B', '8-K12B/A'})
          and len(forms) == len(set(forms)), 'HISTORICAL_GOVERNANCE_EVENT_FORMS_UNSUPPORTED')
    rows = history["all_rows"]
    annual = [row for row in rows if row["form"] == "10-K"]
    current = [row for row in annual if row["reportDate"] == period["period_end"]]
    _need(len(current) == 1,
          "HISTORICAL_GOVERNANCE_PINNED_ANNUAL_NOT_UNIQUE:" + str(len(current)))
    _need(all(current[0][key] == prepared["filing"][key] for key in identity_fields),
          "HISTORICAL_GOVERNANCE_PINNED_ANNUAL_DIVERGED")
    amendments = _order([row for row in rows if row["form"] == "10-K/A"
                         and row["reportDate"] == period["period_end"]])
    prior_end = (date.fromisoformat(period["period_start"]) - timedelta(days=1)).isoformat()
    priors = [row for row in annual if row["reportDate"] == prior_end]
    _need(len(priors) <= 1, "HISTORICAL_GOVERNANCE_PRIOR_ANNUAL_AMBIGUOUS")
    prior_amendments = _order([row for row in rows if row["form"] == "10-K/A"
                               and row["reportDate"] == prior_end])
    if not priors:
        _need(not prior_amendments, "HISTORICAL_GOVERNANCE_PRIOR_ORIGINAL_MISSING",
              "SOURCE_UNAVAILABLE")
    events = [row for row in rows if row["form"] in forms
              and period["period_start"] <= row["filingDate"] <= period["period_end"]]
    return {"record_type": RECORD_TYPE, "schema_version": 1,
            "pinned_period": {"period_start": period["period_start"],
                              "period_end": period["period_end"],
                              "fiscal_year": period["fiscal_year"]},
            "ordinary": current[0], "amendments": amendments,
            "current_filing_chain": amendments + current,
            "prior_ordinary": priors[0] if priors else None,
            "prior_amendments": prior_amendments,
            "prior_filing_chain": prior_amendments + priors,
            "prior_status": ("SAME_CIK_PRIOR_DISCOVERED" if priors
                             else "NO_ADJACENT_SAME_CIK_PRIOR_IN_LOADED_BLOCKS"),
            "expected_prior_period_end": prior_end,
            "events": sorted(events, key=lambda row: (row["filingDate"],
                                                      row["accessionNumber"])),
            "selected_by": {"annual": "PINNED_PERIOD_END_EQUALITY",
                            "prior": "SAME_CIK_ANNUAL_END_ADJACENT_TO_ACTUAL_PERIOD_START",
                            "events": "FILING_DATE_INSIDE_THE_PINNED_PERIOD"},
            "loaded_blocks": sorted(history["loaded_inventories"]),
            "value_taken_from_any_filing": False}


def prepare_selected_auditor_base(*, repo_root, company_id, fiscal_year):
    """Prepare selected annual roles for the one public C04 successor.

    No event census or auditor-change decision is made here. Public code
    receives these source roles and must still prove its complete four-form
    event window before concluding zero.
    """
    from pathlib import Path
    from .canonical import content_hash
    from .normal_source_authority import ROOT
    from .normal_period_selection import resolve_period_selection
    from .historical_annual_input import prepare_historical_annual_input
    from .normal_history_catalog import load_history_for_period
    from .normal_governance_input import _Sources
    from .observations import scope_key
    from .governance_signals import C04_V2_SPEC_PATH
    source = Path(repo_root)
    selected = resolve_period_selection(repo_root=source, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    labelled = prepare_historical_annual_input(repo_root=source, company_id=company_id,
        period_selection=selected, rules_root=ROOT)
    _need(labelled['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
          'HISTORICAL_C04_SELECTED_SUBJECT_NOT_COMPARABLE', 'IMPLEMENTATION_GAP')
    annual = labelled.get('original_input', labelled)
    period = annual['table_input']['target_period']
    reader = _Sources(source, company_id, annual['entity'])
    history = load_history_for_period(repo_root=source, company_id=company_id,
        report_end=period['period_end'], cik=annual['entity'], reader=reader)
    choice = select_historical_governance_metadata(prepared=annual, history=history)
    choice['history_loaded'] = [name for name in history['loaded_inventories']
                               if name != history['inventory']['source_reference']['document_name']]
    from sec_urls import companyfacts_url
    # Carry the annual preparer's already consumed proof as ordinary records;
    # CompanyFacts is never used to infer an auditor or a change signal.
    reader.read(companyfacts_url(cik=int(annual['entity'])),
                accession=annual['filing']['accessionNumber'], role='companyfacts',
                media_type='application/json')
    current = [reader.auditor_filing(f) for f in choice['current_filing_chain']]
    prior = [reader.auditor_filing(f) for f in choice['prior_filing_chain']]
    scope = {'entity_scope': 'registrant'}
    target = {'company_id': company_id, 'period_start': period['period_start'],
              'period_end': period['period_end'], 'scope': scope, 'scope_key': scope_key(scope=scope)}
    proof_map = {content_hash(value=p): p for p in
        [*annual['source_proofs'], *[entry['proof'] for entry in reader.proofs.values()]]}
    proofs = list(proof_map.values())
    body = {'record_type': 'HISTORICAL_SELECTED_GOVERNANCE_INPUT',
        'company_id': company_id, 'prepared_annual_input': annual,
        'selection': choice, 'period_selection': selected, 'source_proofs': proofs,
        'history_alignment_conflicts': history['limitations'],
        'metric_input_status': {'C04': 'PREPARED'}, 'new_calls': [0, 0, 0]}
    binding = {**body, 'input_binding_id': content_hash(value=body)}
    arguments = {'current_filings': current, 'prior_filings': prior or None, 'prior_sources': [],
        'target_accession': choice['current_filing_chain'][0]['accessionNumber'],
        'prior_period_end': choice['prior_ordinary']['reportDate'] if choice['prior_ordinary'] else '',
        'target': target, 'expected_cik': annual['entity'], 'event_input': None}
    return {'base': {'input_binding': binding, 'records': list(reader.records.values()),
        'resolver_inputs': {'c04': {'spec_path': C04_V2_SPEC_PATH, 'arguments': arguments}}},
        'labelled_annual': labelled, 'metadata_only_event_selection': True,
        'value_created': False, 'new_calls': [0, 0, 0]}
