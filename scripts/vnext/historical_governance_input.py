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
        The same keys the frozen selector returns for the roles C04 reads, with
        ``selected_by`` naming how each was chosen. The proxy roles are absent
        rather than empty: C03 reads the annual meeting DEF 14A and this does
        not resolve it, so returning an empty proxy set would read as "there is
        no proxy" instead of "this does not answer that".

    Raises:
        HistoricalGovernanceError: When the pinned annual report is not in the
            loaded rows, when the rows disagree with the prepared input, or
            when the prior period is absent - each named separately, because a
            missing prior year and a missing target are different facts.
    """
    period = prepared["table_input"]["target_period"]
    rows = history["all_rows"]
    annual = [row for row in rows if row["form"] == "10-K"]
    current = [row for row in annual if row["reportDate"] == period["period_end"]]
    _need(len(current) == 1,
          "HISTORICAL_GOVERNANCE_PINNED_ANNUAL_NOT_UNIQUE:" + str(len(current)))
    _need(all(current[0][key] == prepared["filing"][key] for key in identity_fields),
          "HISTORICAL_GOVERNANCE_PINNED_ANNUAL_DIVERGED")
    amendments = _order([row for row in rows if row["form"] == "10-K/A"
                         and row["reportDate"] == period["period_end"]])
    prior_end = max((row["reportDate"] for row in annual
                     if row["reportDate"] < period["period_end"]), default="")
    priors = [row for row in annual if prior_end and row["reportDate"] == prior_end]
    _need(len(priors) <= 1, "HISTORICAL_GOVERNANCE_PRIOR_ANNUAL_AMBIGUOUS")
    prior_amendments = _order([row for row in rows if row["form"] == "10-K/A"
                               and prior_end and row["reportDate"] == prior_end])
    events = [row for row in rows if row["form"] in _EVENT_FORMS
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
                             else "NO_SAME_CIK_PRIOR_IN_LOADED_BLOCKS"),
            "events": sorted(events, key=lambda row: (row["filingDate"],
                                                      row["accessionNumber"])),
            "selected_by": {"annual": "PINNED_PERIOD_END_EQUALITY",
                            "prior": "GREATEST_ANNUAL_REPORT_END_BEFORE_THE_PINNED_ONE",
                            "events": "FILING_DATE_INSIDE_THE_PINNED_PERIOD"},
            "loaded_blocks": sorted(history["loaded_inventories"]),
            "value_taken_from_any_filing": False}
