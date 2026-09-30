"""The XBRL instance documents C04 and B06 read for an annual accession, declared beside the plan.

Purpose: ``plan_historical_sources`` declares two documents per annual
accession - the primary HTML and the accession's ``index.json`` - and nothing
the index lists. The frozen governance reader's ``auditor_filing`` reads the
index and then every XBRL instance it names (``*_htm.xml`` for an inline
filing), whether or not the primary is saved; C04 reads it for the target and
the prior year's accession, and B06's cascade reads the same reader for the
target. In the first acquisition every older year's primary and index were
fetched and none of their instances, so the full-frame batch withheld 32 C04
and 23 B06 positions with ``SAVED_SOURCE_MISSING`` naming an instance - and the
acquisition gate would refuse each of those files as undeclared.

Why this is not an edit to the planner: ``normal_history_plan.py`` is a
``NEW_RULE_FILE`` of ``issue_47_v1``; the same reasoning produced
``historical_event_sources`` and ``historical_governance_sources``.

What it does not restate: which XML documents an accession has. The frozen
``auditor_filing`` is run with a reader that records every document it asks for
in the ``auditor_facts`` role instead of reading it, so the list is the frozen
reader's own filter over the saved index, not a copy of it. An accession whose
index is not saved names nothing yet; that is recorded as a limitation, not as
an empty set.

Call relationships: ``historical_source_acquisition`` calls this. It reads
saved material only; it fetches nothing and executes no metric.
"""
from pathlib import Path

from .historical_source_acquisition import HistoricalAcquisitionError
from .normal_governance_input import _Sources
from .normal_history_plan import _saved_state

DEPENDENCY_CLASS = "ACCESSION_XBRL_INSTANCE"
# The role the frozen reader gives the documents; kept so a declared row names
# the same role the reader will ask for.
ROLE = "auditor_facts"
INDEX_CLASS = "ACCESSION_INSTANCE_DISCOVERY"
PRIMARY_CLASS = "ANNUAL_PERIOD_IDENTITY"


class HistoricalInstanceSourceError(HistoricalAcquisitionError):
    """The instance declaration could not be built for this company."""


class _Recording(_Sources):
    """The frozen reader, recording the instance documents instead of reading them."""

    def __init__(self, *arguments, **keywords):
        super().__init__(*arguments, **keywords)
        self.named = []

    def read(self, url, *, accession="", role, media_type, required=True):
        if role == ROLE:
            self.named.append({"source_url": url, "accession": accession,
                               "media_type": media_type})
            return {"raw_bytes": b"", "source_reference": {"source_reference_id": url}}
        return super().read(url, accession=accession, role=role, media_type=media_type,
                            required=required)


def _row(*, reader, repo_root, cik, named, consumers):
    row = {"source_url": named["source_url"], "media_type": named["media_type"],
           "accession": named["accession"],
           "document_name": named["source_url"].rsplit("/", 1)[1],
           "dependency_class": DEPENDENCY_CLASS, "source_roles": [ROLE],
           "consumers": list(consumers), "declared_by": "historical_instance_sources",
           "registrant_cik": str(cik)}
    row = {**row, **_saved_state(reader, repo_root, row),
           "new_acquisition_required": False, "acquisition_kind": None,
           "source_acquisition_credit": False}
    row["new_acquisition_required"] = row["saved_status"] != "VERIFIED_SAVED_SOURCE"
    if row["saved_status"] == "MISSING_SAVED_SOURCE":
        row["acquisition_kind"] = "FIRST_ACQUISITION"
    elif row["saved_status"] == "SAVED_SOURCE_BLOCKED":
        row["acquisition_kind"] = "REPLACEMENT_ACQUISITION"
    return row


def instance_dependencies(*, repo_root: Path, company_id: str, planned):
    """Declare the instance documents every planned annual accession's index names.

    Args:
        repo_root: Repository or installed data root holding saved material.
        company_id: Configured company identity.
        planned: The planner's requirement rows for this company.

    Returns:
        ``{"company_id", "requirements", "limitations"}``. A limitation names
        the accession and why its instances cannot be named yet.
    """
    root = Path(repo_root)
    primaries = {row["accession"]: row for row in planned
                 if row["dependency_class"] == PRIMARY_CLASS}
    requirements, limitations = {}, []
    for index in planned:
        if index["dependency_class"] != INDEX_CLASS:
            continue
        accession = index["accession"]
        if index.get("saved_status") != "VERIFIED_SAVED_SOURCE":
            limitations.append({"accession": accession, "reason": "ACCESSION_INDEX_NOT_SAVED",
                                "what_it_means": "the instances are named by the index, "
                                                 "so they are declared once it is saved"})
            continue
        primary = primaries.get(accession)
        if primary is None:
            limitations.append({"accession": accession, "reason": "NO_PLANNED_PRIMARY_FOR_INDEX",
                                "what_it_means": "the frozen reader needs the filing's "
                                                 "primary document name"})
            continue
        cik = str(int(index["source_url"].split("/Archives/edgar/data/")[1].split("/")[0]))
        recording = _Recording(root, company_id, cik)
        filing = {"accessionNumber": accession, "primaryDocument": primary["document_name"],
                  "form": "10-K"}
        try:
            recording.auditor_filing(filing)
        except Exception as error:                      # noqa: BLE001 - per accession
            limitations.append({"accession": accession,
                                "reason": type(error).__name__ + ":" + str(error)[:200],
                                "what_it_means": "the frozen reader refused the saved index"})
            continue
        for named in recording.named:
            held = requirements.get(named["source_url"])
            if held is not None:
                held["consumers"] = sorted(set(held["consumers"]) | set(index["consumers"]))
                continue
            requirements[named["source_url"]] = _row(
                reader=_Sources(root, company_id, cik), repo_root=root, cik=cik,
                named=named, consumers=index["consumers"])
    return {"company_id": company_id,
            "requirements": [requirements[url] for url in sorted(requirements)],
            "limitations": limitations}
