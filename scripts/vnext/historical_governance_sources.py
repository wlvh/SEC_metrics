"""The governance document C02 reads for a pinned period, declared beside the plan.

Purpose: ``plan_historical_sources`` declares five dependency classes - the
submissions index, its history shards, Company Facts and the two per-accession
annual documents - and no governance class. C02's second source is either the
annual meeting's DEF 14A or, where a company puts its governance information
in the amendment that adds Part III, that 10-K/A. Ten of the 82 proxies the
saved submissions indexes list have their accession material saved and all ten
were filed in 2026, so every earlier period names a document the acquisition
gate would refuse by name, because nothing declares it.

Why this is not an edit to the planner: ``normal_history_plan.py`` is a
``NEW_RULE_FILE`` of ``issue_47_v1``, and changing its bytes moves the
Requirement closure that the frozen Runs of each batch are evidence about. The
same reasoning produced ``historical_event_sources``; this is its second
instance rather than a new pattern.

What it does not restate: which filing a period means. The row comes from the
route's own source plan - the second entry of ``plan["text_filings"]``, which
is what ``prepare_historical_business_text_input`` reads - so a declaration
cannot drift from what is consumed by describing the selection a second time.
The cost is that a period whose annual primary is not saved has no derivable
declaration at all, because the plan needs that document to exist before it
can name anything; that ordering is recorded as a limitation rather than as an
empty set.

Call relationships: ``historical_source_acquisition`` calls this. It reads
saved material only; it fetches nothing and executes no metric.
"""
from pathlib import Path

from .historical_source_acquisition import HistoricalAcquisitionError
from .normal_governance_input import _Sources
from .normal_history_plan import _saved_state

METRIC_ID = "C02"
DEPENDENCY_CLASS = "GOVERNANCE_DISCLOSURE_FILING"
# The two roles the frozen reader assigns, kept apart because they are not the
# same kind of document: one is the annual meeting's proxy and one is an
# amendment to the annual report itself.
PROXY_ROLE = "governance_proxy"
AMENDMENT_ROLE = "part_iii_annual_amendment"
# One document per filing, measured rather than assumed: `_Sources.primary`
# issues exactly one request for the filing's primary document, and C02 reads
# nothing else from that accession.
REQUESTS_PER_FILING = 1


class HistoricalGovernanceSourceError(HistoricalAcquisitionError):
    """The governance declaration could not be built for this company."""


def _need(condition, reason):
    if not condition:
        raise HistoricalGovernanceSourceError(reason)


def _row(*, reader, repo_root, cik, filing, consumers):
    """One declared dependency, classified by the planner's own saved state."""
    from sec_urls import accession_document_url
    accession = filing["accessionNumber"]
    url = accession_document_url(cik=int(cik), accession=accession,
                                 document_name=filing["primaryDocument"])
    role = PROXY_ROLE if filing["form"].startswith("DEF 14A") else AMENDMENT_ROLE
    row = {"source_url": url, "media_type": "text/html", "accession": accession,
           "document_name": filing["primaryDocument"],
           "dependency_class": DEPENDENCY_CLASS, "source_roles": [role],
           "form": filing["form"], "filing_date": filing["filingDate"],
           "consumers": list(consumers), "declared_by": "historical_governance_sources",
           "registrant_cik": str(cik), "primary_cik": str(cik)}
    # The same three fields the planner and the event declaration carry, set
    # the same way from the same saved state. A row missing them reaches the
    # listing view and raises there, which is how the first version of this
    # module was caught.
    row = {**row, **_saved_state(reader, repo_root, row),
           "new_acquisition_required": False, "acquisition_kind": None,
           "source_acquisition_credit": False}
    row["new_acquisition_required"] = row["saved_status"] != "VERIFIED_SAVED_SOURCE"
    if row["saved_status"] == "MISSING_SAVED_SOURCE":
        row["acquisition_kind"] = "FIRST_ACQUISITION"
    elif row["saved_status"] == "SAVED_SOURCE_BLOCKED":
        row["acquisition_kind"] = "REPLACEMENT_ACQUISITION"
    return row


def governance_dependencies(*, repo_root: Path, company_id: str, report_ends=None):
    """Declare the governance document each pinned period's C02 would read.

    Args:
        repo_root: Repository or installed data root holding saved material.
        company_id: Configured company identity.
        report_ends: Period ends to declare for. Defaults to every target
            period the saved catalog offers for this company.

    Returns:
        ``{"company_id", "requirements", "limitations"}``. A limitation names
        the period and why no document could be named for it, which is not the
        same as a period that needs nothing.

    Raises:
        HistoricalGovernanceSourceError: When the company is not configured.
    """
    from .historical_text_input import prepare_historical_business_text_input
    from .normal_history_catalog import target_period_candidates
    from .normal_period_selection import resolve_period_selection
    root = Path(repo_root)
    if report_ends is None:
        candidates = target_period_candidates(repo_root=root, company_id=company_id)
        report_ends = [str(candidate["report_date"]) for candidate in candidates
                       if candidate.get("report_date")]
    requirements, limitations, readers = [], [], {}
    for report_end in sorted(set(report_ends)):
        # The planner's own consumer form, "period:<label>:<metric>", because
        # the scope gate reads that prefix to decide which window a dependency
        # is checked against. A row with a consumer of another shape is checked
        # against the frame's window instead of its period's, which is a
        # different question and happens to be a wider one.
        consumers = ["period:" + report_end + ":" + METRIC_ID]
        try:
            selection = resolve_period_selection(repo_root=root, company_id=company_id,
                                                 report_end=report_end)
            prepared = prepare_historical_business_text_input(
                repo_root=root, company_id=company_id, metric_id=METRIC_ID,
                period_selection=selection)
        except Exception as error:                      # noqa: BLE001 - per period
            limitations.append({"report_end": report_end, "metric_id": METRIC_ID,
                                "reason": type(error).__name__ + ":" + str(error)[:200],
                                "what_it_means": "no plan exists for this period, so no "
                                                 "governance document can be named for it"})
            continue
        plan = prepared["input_binding"]["source_plan"]
        if plan is None or len(plan.get("text_filings", [])) < 2:
            limitations.append({"report_end": report_end, "metric_id": METRIC_ID,
                                "reason": "NO_GOVERNANCE_FILING_IN_PLAN",
                                "what_it_means": "the plan resolved without a second "
                                                 "source, so this period declares none"})
            continue
        cik = prepared["prepared_input"]["entity"]
        if cik not in readers:
            readers[cik] = _Sources(root, company_id, cik)
        requirements.append(_row(reader=readers[cik], repo_root=root, cik=cik,
                                 filing=plan["text_filings"][1], consumers=consumers))
    merged = {}
    for item in requirements:
        held = merged.get(item["source_url"])
        if held is None:
            merged[item["source_url"]] = item
            continue
        held["consumers"] = sorted(set(held["consumers"]) | set(item["consumers"]))
    return {"company_id": company_id,
            "requirements": [merged[url] for url in sorted(merged)],
            "limitations": limitations}
