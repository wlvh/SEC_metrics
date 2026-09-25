"""Prepare an annual input for an explicitly selected historical period.

Why this is a successor file rather than a parameter on the frozen entries:
``scripts/vnext/normal_annual_input_v2.py`` is bound byte-for-byte by the
``issue_28_v13`` rule set and ``scripts/vnext/normal_annual_input.py`` by
``issue_28_v11``. Changing either one stops every existing ordinary Run from
loading its own Requirement, which would break the current route instead of
extending it. So the period-dependent step is re-expressed here and everything
else — the saved-source reader, the DEI annual reader, the source admission
check, the fiscal-label inspector and its frozen policy — is the same code.

This module selects nothing by itself. It consumes a verified
``period_selection`` and re-derives it from source through
``normal_period_selection`` before reading a single document.
"""
from pathlib import Path

from sec_urls import (accession_document_url, companyfacts_url, submissions_file_url,
                      submissions_url)

from . import fiscal_year_labels
from .annual_update import saved_source
from .canonical import content_hash, sha256_file, strict_json_file, strict_json_loads
from .normal_annual_input import (NormalAnnualInputError, _cik, _registry_rows,
                                  _subject_policy, annual_period)
from .normal_annual_input_v2 import (POLICY_PATH as FISCAL_LABEL_POLICY_PATH,
                                     _choose_fiscal_year, exact_json_value)
from .normal_period_selection import (check_selected_label, check_selected_period,
                                      selected_historical_filing)
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import resolve_repository_file


SELECTION_RULE = "PINNED_ORDINARY_PERIOD_IN_COMPLETE_SAVED_SUBMISSIONS"
LABEL_POLICY = "SOURCE_ISSUER_YEAR_WITH_RAW_METADATA_RETAINED"


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalAnnualInputError(reason, category)


def prepare_original_historical_input(*, repo_root: Path, company_id: str, period_selection):
    """Return the original-input body for the pinned period.

    The body keeps the frozen current-route shape so every downstream consumer
    reads the same fields, and adds the verified selection so a historical input
    can never be mistaken for a current one.
    """
    companies = [c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id]
    _need(len(companies) == 1, "COMPANY_NOT_UNIQUE", "IMPLEMENTATION_GAP")
    company = companies[0]
    _subject_policy(company)
    # The registrant that filed this period: the primary, or a registered
    # predecessor for a year it filed (Issue #47 section 7.3). Read from the
    # record here only to know whose submissions to open; which one it is gets
    # proven by selected_historical_filing, which re-derives the whole record
    # from those saved submissions and refuses any difference.
    _need(type(period_selection) is dict and period_selection.get("reporting_cik") is not None,
          "ORDINARY_PERIOD_SELECTION_RECORD_REQUIRED", "IMPLEMENTATION_GAP")
    cik = _cik(period_selection["reporting_cik"])

    def read(url, accession=""):
        item = saved_source(repo_root=repo_root, url=url, accession=accession)
        _need(item is not None, "SAVED_SOURCE_MISSING:" + url, "SOURCE_UNAVAILABLE")
        return item

    inventory = read(submissions_url(cik=cik))
    payload = strict_json_loads(text=inventory["raw"].decode("utf-8"))
    selection = selected_historical_filing(repo_root=repo_root, company=company,
                                           submissions=payload,
                                           period_selection=period_selection)
    # Re-derived and equal, so the record's subject policy is the period's own:
    # the registry's for the primary's periods, the filing registrant's own for
    # a predecessor's.
    subject_policy = period_selection["subject_policy"]
    # A predecessor's period is selected only after the primary's own catalog is
    # read and found to hold nothing there; re-deriving the record reads those
    # blocks again. They are admitted inputs of this preparation, so they travel
    # with it - without them an installed data root cannot replay the selection,
    # which the first batch over these years found as "Request-ledger locator
    # evidence is invalid" on every metric.
    registrant = period_selection.get("period_registrant")
    primary_catalog = []
    if registrant is not None:
        names = registrant["primary_catalog"]["loaded_inventories"]
        primary_catalog = [read(submissions_url(cik=_cik(company["primary_cik"])))] + [
            read(submissions_file_url(file_name=name)) for name in names[1:]]
    filing = selection["filing"]
    accession = filing["accessionNumber"]
    primary = read(accession_document_url(cik=cik, accession=accession,
                                          document_name=filing["primaryDocument"]), accession)
    target = annual_period(raw=primary["raw"], cik=cik, filing=filing)
    check_selected_period(period_selection=period_selection, target_period=target)
    facts = read(companyfacts_url(cik=cik), accession)
    _need(_cik(strict_json_loads(text=facts["raw"].decode("utf-8"))["cik"]) == cik,
          "COMPANYFACTS_ENTITY_CONFLICT")
    # An amendment on this period is read - by historical_amendment_admission -
    # to decide whether the original's inputs still stand, so it is an admitted
    # input of this preparation and its proof has to travel with the others.
    # Leaving it out installed a data root the admission could not read, which
    # the batch found as "Request-ledger locator evidence is invalid": the
    # ledger named the amendment's bytes and the installed root did not carry
    # them.
    amendment_sources = [read(accession_document_url(cik=cik,
                                                     accession=item["accessionNumber"],
                                                     document_name=item["primaryDocument"]),
                              item["accessionNumber"])
                         for item in selection["amendments"]]

    def arguments(item):
        proof = item["proof"]
        return {"company_id": company_id, "target_period": target,
                "source_repo_relative_path": proof["request_repo_relative_path"],
                "source_url": proof["source_url"], "accession": accession,
                "document_name": proof["document_name"],
                "request_attempt_id": proof["request_attempt_id"]}

    body = {"company_id": company_id, "entity": str(cik), **selection,
            "subject_policy": subject_policy,
            "companyfacts_input": arguments(facts),
            "table_input": {**arguments(primary), "source_media_type": "text/html",
                            "source_role": "target_primary"},
            "source_proofs": [s["proof"] for s in (inventory, primary, facts,
                                                   *amendment_sources, *primary_catalog)],
            "selection_rule": SELECTION_RULE,
            "period_selection": period_selection,
            "source_evidence": "LEDGER_BOUND_SAVED_BYTES",
            "update_status": ("AMENDMENT_PROCESSING_REQUIRED" if selection["amendments"] else
                              "SUBJECT_TRANSITION_INPUT_READY"
                              if subject_policy["mode"] == "SUCCESSOR_REGISTRANT_ONLY"
                              else "ORIGINAL_INPUT_READY"),
            "current_latest_verified": False,
            "execution": "NOT_EXECUTED", "production_authorized": False}
    return {**body, "input_id": content_hash(value=body)}


def prepare_historical_annual_input(*, repo_root: Path, company_id: str, period_selection):
    """Resolve the pinned period's issuer fiscal-year label from its own source.

    The label policy, its installed policy file and the inspector module are the
    frozen current ones; only the period they are pointed at is explicit here.
    """
    policy = strict_json_file(path=resolve_repository_file(
        repo_root=repo_root, repo_relative_path=FISCAL_LABEL_POLICY_PATH))
    if (policy != strict_json_file(path=ROOT / FISCAL_LABEL_POLICY_PATH)
            or policy["policy_id"] != "ordinary_fiscal_year_labels_v1"):
        raise NormalAnnualInputError("ORDINARY_FISCAL_LABEL_INSTALLED_POLICY_CHANGED",
                                     "AUTHORITY_CONFLICT")
    original = prepare_original_historical_input(repo_root=repo_root, company_id=company_id,
                                                 period_selection=period_selection)
    verify_ordinary_source_proofs(data_root=repo_root, proofs=original["source_proofs"])
    report = fiscal_year_labels._inspect_prepared_input(repo_root=repo_root, prepared=original)
    inspected = report["inspection"]
    year, basis = _choose_fiscal_year(inspected)
    period = {**original["table_input"]["target_period"], "fiscal_year": year}
    check_selected_label(period_selection=period_selection, target_period=period)
    resolution = {"record_type": "ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION",
                  "policy_id": policy["policy_id"],
                  "policy_sha256": sha256_file(path=ROOT / FISCAL_LABEL_POLICY_PATH),
                  "selected_fiscal_year": year, "basis": basis,
                  "source_inspection_status": inspected["status"],
                  "original_dei_fiscal_year": inspected["dei_fiscal_year"],
                  "original_companyfacts_fiscal_year_values": inspected["companyfacts_fiscal_year_values"],
                  "metadata_conflict_retained": inspected["status"] == "SOURCE_LABEL_CONFLICT",
                  "source_inspection": inspected, "actual_dates_changed": False,
                  "historical_input_or_run_changed": False}
    body = {key: value for key, value in original.items() if key != "input_id"}
    body.update(table_input={**original["table_input"], "target_period": period},
                companyfacts_input={**original["companyfacts_input"], "target_period": period},
                original_input=original, fiscal_year_label_resolution=resolution,
                fiscal_label_policy=LABEL_POLICY)
    body = exact_json_value(body)
    return {**body, "input_id": content_hash(value=body)}
