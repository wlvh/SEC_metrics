"""Whether a pinned period's amendments leave one metric's inputs unchanged.

Purpose:
    The historical route refused any target period carrying a 10-K/A, with an
    honest ``AMENDED_TARGET_NOT_IMPLEMENTED``. Measured on the six-company
    matrix that cost 38 of 138 positions - every Company Facts and zero-AI
    metric for Southwest and Paramount.

    It was recorded here as a business question needing a decision. It is not.
    ``config/annual_amendment_scope_v1.json`` is an approved policy that
    already classifies these exact two shapes, and ``annual_amendment_scope``
    already proves the classification from the filings' own bytes. What was
    missing is that the historical route never asked. This module asks.

What the policy decides, and what it refuses to decide:
    A limited exhibit-link correction whose Item 15 text is identical and whose
    cover differs only in the amendment banner leaves ``ORIGINAL_STATEMENT_VALUES``
    and ``FISCAL_EVENT_WINDOW`` unchanged. A Part III addition that declares no
    new financial statements leaves only ``FISCAL_EVENT_WINDOW`` unchanged and
    sets ``original_statement_admission_requires_further_review``. So a Part III
    amendment clears the six event metrics and does NOT clear the statement
    ones - which is the repository's standing rule that Part III does not
    automatically approve a financial or subject-consolidation scope.

    The nine metric IDs in the policy's ``not_covered_metric_ids`` are refused
    whatever the classification, because a Part III amendment can change
    governance, legal, related-party and debt interpretation.

    Nothing here admits a metric whose class the policy did not clear, and
    nothing here reads the amendment as a source of values: the target stays
    the original filing. The amendment is only ever evidence about whether the
    original's inputs still stand.

Call relationships:
    The Company Facts and zero-AI historical routes call this in place of their
    blanket refusal. It creates no Run, no Result and no acquisition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from .annual_amendment_scope import POLICY, AmendmentScopeError, inspect_annual_amendment_scope
from .canonical import content_hash

# Which input class each metric family needs left unchanged. Statement values
# are what a Company Facts or reported-figure metric reads; the event window is
# what the 8-K event metrics read.
STATEMENT_INPUT_CLASS = POLICY["original_statement_input_class"]
EVENT_INPUT_CLASS = POLICY["event_input_class"]
NOT_COVERED_METRIC_IDS = frozenset(POLICY["not_covered_metric_ids"])
# The classifier's refusals that say the amendment's declared scope could not be
# mapped to an approved class - as opposed to an identity, period, byte-stream
# or installed-policy conflict, which is an integrity failure and still raises.
UNCLASSIFIED_SCOPE_REASONS = frozenset({"AMENDMENT_EXPLANATORY_NOTE_NOT_UNIQUE",
                                        "AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED",
                                        "AMENDMENT_DECLARED_LIMITED_SCOPE_NOT_PROVEN"})


class AmendmentAdmissionError(ValueError):
    """A pinned period's amendments do not leave this metric's inputs unchanged."""


def required_input_class(*, metric_id: str, event_metric_ids: Sequence[str]) -> str:
    """The input class this metric needs an amendment to have left unchanged.

    Args:
        metric_id: The metric being resolved.
        event_metric_ids: The route's own event metric IDs.

    Returns:
        ``FISCAL_EVENT_WINDOW`` for an event metric, else
        ``ORIGINAL_STATEMENT_VALUES``.
    """
    return EVENT_INPUT_CLASS if metric_id in set(event_metric_ids) else STATEMENT_INPUT_CLASS


def amendment_admission(*, repo_root: Path, company_id: str, metric_ids: Sequence[str],
                        prepared: Mapping[str, object],
                        event_metric_ids: Sequence[str] = ()) -> dict:
    """Decide whether these metrics may resolve on a period carrying amendments.

    Args:
        repo_root: Data root holding the saved originals.
        company_id: Logical company.
        metric_ids: Every metric this call resolves. The Company Facts route
            resolves a whole family at once, so the decision is taken for the
            set rather than for one arbitrary member of it.
        prepared: The historical annual input, carrying ``entity``, ``filing``
            and ``amendments``.
        event_metric_ids: The calling route's event metric IDs.

    Returns:
        A record naming every amendment's classification and the decision.

    Raises:
        AmendmentAdmissionError: When a metric is outside the policy, when the
            set would need two different input classes answered at once, or
            when any amendment fails to leave the required class unchanged.
            The reason names the classification rather than calling it
            unimplemented: a refusal under an approved policy is a different
            thing from a gap, and reporting one as the other is how a decided
            question looks open.
    """
    metric_ids = sorted(set(metric_ids))
    if not metric_ids:
        raise AmendmentAdmissionError("HISTORICAL_AMENDMENT_METRIC_SET_EMPTY")
    outside = [metric for metric in metric_ids if metric in NOT_COVERED_METRIC_IDS]
    if outside:
        raise AmendmentAdmissionError(
            "HISTORICAL_AMENDMENT_METRIC_NOT_COVERED_BY_POLICY:" + ",".join(outside))
    required = {required_input_class(metric_id=metric, event_metric_ids=event_metric_ids)
                for metric in metric_ids}
    if len(required) != 1:
        # A statement metric and an event metric get different answers from the
        # same amendment, which is the whole point, so they cannot share one
        # decision.
        raise AmendmentAdmissionError(
            "HISTORICAL_AMENDMENT_MIXED_INPUT_CLASSES:" + ",".join(sorted(required)))
    required = required.pop()
    scopes = [_scope(repo_root=repo_root, company_id=company_id, prepared=prepared,
                     amendment=amendment) for amendment in prepared["amendments"]]
    blocked = [scope for scope in scopes if required not in scope["unchanged_input_classes"]]
    record = {"record_type": "HISTORICAL_AMENDMENT_ADMISSION", "schema_version": 1,
              "company_id": company_id, "metric_ids": metric_ids,
              "required_input_class": required,
              "target_accession": prepared["filing"]["accessionNumber"],
              "amendments": [{"accession": scope["amendment"]["filing"]["accessionNumber"],
                              "classification": scope["classification"],
                              "issues": scope["issues"],
                              "unchanged_input_classes": scope["unchanged_input_classes"],
                              "scope_id": scope["scope_id"]} for scope in scopes],
              "policy_hash": scopes[0]["policy_hash"] if scopes else None,
              "admitted": not blocked, "production_authorized": False}
    if blocked:
        raise AmendmentAdmissionError(
            "HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:" + required + ":"
            + ",".join(sorted({scope["classification"]
                               + ("(" + ";".join(scope["issues"]) + ")"
                                  if scope["classification"] == "UNCLASSIFIED" else "")
                               for scope in blocked})))
    return record


def _scope(*, repo_root: Path, company_id: str, prepared, amendment):
    """One amendment's classification, proved from the saved originals."""
    from .annual_update import saved_source
    from .sources import raw_blob_record, source_reference_record
    from sec_urls import accession_document_url

    def read(filing):
        url = accession_document_url(cik=int(prepared["entity"]),
                                     accession=filing["accessionNumber"],
                                     document_name=filing["primaryDocument"])
        saved = saved_source(repo_root=repo_root, url=url, accession=filing["accessionNumber"])
        if saved is None:
            raise AmendmentAdmissionError("HISTORICAL_AMENDMENT_SOURCE_NOT_SAVED:" + url)
        proof = saved["proof"]
        blob = raw_blob_record(repo_root=repo_root,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type="text/html")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=url,
            accession=filing["accessionNumber"], document_name=filing["primaryDocument"],
            source_role="annual_source_identity",
            request_attempt_id=proof["request_attempt_id"])
        return {"raw": saved["raw"], "blob": blob, "reference": reference, "filing": filing}

    original, source = read(prepared["filing"]), read(amendment)
    try:
        return inspect_annual_amendment_scope(original=original, amendment=source,
                                              company_id=company_id, cik=prepared["entity"])
    except AmendmentScopeError as error:
        if str(error) not in UNCLASSIFIED_SCOPE_REASONS:
            raise
        # The approved classifier could not classify this amendment at all -
        # measured on Paramount Global's FY2024 10-K/A, whose Part III sentence
        # continues past "such Items" where the approved pattern ends. The
        # policy clears only what it classifies, so an amendment it cannot
        # classify clears nothing. That is the policy's own fail-closed answer
        # and is reported under it, by name, rather than as an unhandled error:
        # extending the approved wording would be a revision of the policy,
        # not a repair of this route.
        return {"amendment": {"filing": amendment}, "classification": "UNCLASSIFIED",
                "issues": [str(error)], "unchanged_input_classes": [], "scope_id": None,
                "policy_hash": content_hash(value=POLICY)}
