"""Prepare ordinary annual inputs without sample, calendar-year or answer files.

This adapter reads the existing saved-request boundary and native XBRL parser.
It does not fetch sources, execute metrics, grant source admission or publish.
The older calendar-only and two-sample entries retain their frozen semantics.
"""

from datetime import date, datetime
from pathlib import Path
import re

from sec_urls import accession_document_url, companyfacts_url, submissions_url

from .annual_input import AnnualInputError, _registry_rows
from .annual_update import AnnualUpdateError, saved_source
from .canonical import content_hash, strict_json_loads
from .deterministic_router import parse_accession_xbrl_source


class NormalAnnualInputError(ValueError):
    """A source or implementation limitation, never a financial conclusion."""

    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise NormalAnnualInputError(reason, category)


def _date(value):
    try:
        _need(type(value) is str, "FILING_DATE_INVALID")
        result = date.fromisoformat(value)
        _need(result.isoformat() == value, "FILING_DATE_INVALID")
        return result
    except ValueError as error:
        raise NormalAnnualInputError(
            "FILING_DATE_INVALID", "SOURCE_INTEGRITY_ERROR"
        ) from error


def _cik(value):
    _need(type(value) in (str, int) and re.fullmatch(r"[0-9]{1,10}", str(value))
          and 0 < int(value) <= 9999999999, "SOURCE_ENTITY_INVALID")
    return int(value)


def select_filing(*, company, submissions):
    """Select the latest ordinary period; amendments remain separate inputs.

    Selection never uses a fiscal-year label inferred from the calendar date,
    a saved Result, a requested accession, or a per-company sample whitelist.
    Relevant missing history is a source-availability failure, not no change.
    """
    _need(company["entity_continuity_status"] == "continuous"
          and not company["related_ciks"], "ENTITY_CONTINUITY_NOT_IMPLEMENTED",
          "IMPLEMENTATION_GAP")
    _need(_cik(submissions["cik"]) == _cik(company["primary_cik"]),
          "SUBMISSIONS_ENTITY_CONFLICT")
    recent = submissions["filings"]["recent"]
    required = {"form", "reportDate", "filingDate", "accessionNumber",
                "primaryDocument"}
    _need(type(recent) is dict and required <= set(recent),
          "SUBMISSIONS_COLUMNS_MISSING")
    _need(all(type(v) is list for v in recent.values())
          and len({len(v) for v in recent.values()}) == 1,
          "SUBMISSIONS_COLUMNS_CONFLICT")
    annual = []
    for index, form in enumerate(recent["form"]):
        _need(type(form) is str and form and form == form.strip(),
              "FILING_FORM_INVALID")
        if form not in {"10-K", "10-K/A"}:
            continue
        filing = {key: values[index] for key, values in recent.items()}
        _need(_date(filing["filingDate"]) >= _date(filing["reportDate"]),
              "FILING_DATE_CONFLICT")
        _need(type(filing["accessionNumber"]) is str
              and re.fullmatch(r"\d{10}-\d{2}-\d{6}", filing["accessionNumber"]),
              "ACCESSION_INVALID")
        document = filing["primaryDocument"]
        _need(type(document) is str
              and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:htm|html)",
                               document, re.I), "PRIMARY_DOCUMENT_INVALID")
        annual.append(filing)
    _need(bool(annual), "ANNUAL_FILING_NOT_IN_SAVED_BLOCK",
          "SOURCE_UNAVAILABLE")
    latest_end = max(f["reportDate"] for f in annual)
    selected = [f for f in annual
                if f["form"] == "10-K" and f["reportDate"] == latest_end]
    _need(len(selected) == 1, "ORDINARY_ANNUAL_MISSING_OR_AMBIGUOUS",
          "SOURCE_UNAVAILABLE" if not selected else "SOURCE_INTEGRITY_ERROR")
    # A shard's dates are filing dates, not measurement dates. Any shard whose
    # last filing is on/after the period end may contain a relevant amendment.
    shards = submissions["filings"]["files"]
    _need(type(shards) is list, "SUBMISSIONS_HISTORY_INVALID")
    for shard in shards:
        _need(_date(shard["filingFrom"]) <= _date(shard["filingTo"]),
              "SUBMISSIONS_HISTORY_DATE_CONFLICT")
        _need(shard["filingTo"] < latest_end, "RELEVANT_HISTORY_NOT_LOADED",
              "SOURCE_UNAVAILABLE")
    amendments = [f for f in annual if f["form"] == "10-K/A"
                  and f["reportDate"] == latest_end]
    return {"filing": selected[0], "amendments": amendments,
            "prior_period_amendments": [f for f in annual
                                        if f["form"] == "10-K/A"
                                        and f["reportDate"] != latest_end]}


def annual_period(*, raw, cik, filing):
    """Read the actual annual interval and fiscal label from DEI contexts."""
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    contexts = []

    def dei(name):
        facts = [f for f in parsed.facts if f["qualified_name"].casefold()
                 == ("dei:" + name).casefold()]
        pairs = {(f["text"].strip(), f["context_ref"]) for f in facts}
        _need(len(pairs) == 1, "DEI_MISSING_OR_AMBIGUOUS:" + name)
        value, ref = next(iter(pairs))
        context = parsed.contexts[ref]
        _need(not context["dimensions"] and not context["typed_dimension_count"]
              and _cik(context["entity_identifier"]) == _cik(cik),
              "DEI_SUBJECT_CONFLICT")
        contexts.append(context)
        return value

    form = dei("DocumentType")
    end = dei("DocumentPeriodEndDate")
    year = dei("DocumentFiscalYearFocus")
    focus = dei("DocumentFiscalPeriodFocus")
    amended = dei("AmendmentFlag")
    entity = dei("EntityCentralIndexKey")
    if end != filing["reportDate"]:
        try:
            end = datetime.strptime(end, "%B %d, %Y").date().isoformat()
        except ValueError as error:
            raise NormalAnnualInputError(
                "DEI_REPORT_DATE_CONFLICT", "SOURCE_INTEGRITY_ERROR"
            ) from error
    _need(form == filing["form"] == "10-K" and focus == "FY"
          and amended.casefold() == "false" and _cik(entity) == _cik(cik)
          and end == filing["reportDate"] and re.fullmatch(r"\d{4}", year),
          "ANNUAL_IDENTITY_CONFLICT")
    start = contexts[0]["period_start"]
    _need(all(c["period_start"] == start and c["period_end"] == end
              for c in contexts), "DEI_PERIOD_CONFLICT")
    _need(1900 <= int(year) <= 9998
          and _date(start).year <= int(year) <= _date(end).year,
          "DEI_FISCAL_YEAR_CONFLICT")
    duration = (_date(end) - _date(start)).days + 1
    _need(duration in {364, 365, 366, 371}, "ANNUAL_DURATION_NOT_IMPLEMENTED",
          "IMPLEMENTATION_GAP")
    return {"fiscal_year": int(year), "period_start": start,
            "period_end": end}


def prepare_saved_annual_input(*, repo_root: Path, company_id: str):
    """Return ordinary original inputs and explicit current-update limitations.

    A prepared original with amendments is not a successful current update.
    The caller must evaluate those amendments before making a current claim.
    """
    companies = [c for c in _registry_rows(repo_root=repo_root)
                 if c["company_id"] == company_id]
    _need(len(companies) == 1, "COMPANY_NOT_UNIQUE", "IMPLEMENTATION_GAP")
    company = companies[0]
    _need(company["entity_continuity_status"] == "continuous"
          and not company["related_ciks"], "ENTITY_CONTINUITY_NOT_IMPLEMENTED",
          "IMPLEMENTATION_GAP")
    cik = int(company["primary_cik"])

    def read(url, accession=""):
        item = saved_source(repo_root=repo_root, url=url, accession=accession)
        _need(item is not None, "SAVED_SOURCE_MISSING:" + url,
              "SOURCE_UNAVAILABLE")
        return item

    inventory = read(submissions_url(cik=cik))
    payload = strict_json_loads(text=inventory["raw"].decode("utf-8"))
    selection = select_filing(company=company, submissions=payload)
    filing = selection["filing"]
    accession = filing["accessionNumber"]
    primary = read(accession_document_url(
        cik=cik, accession=accession, document_name=filing["primaryDocument"]),
        accession)
    target = annual_period(raw=primary["raw"], cik=cik, filing=filing)
    facts = read(companyfacts_url(cik=cik), accession)
    _need(_cik(strict_json_loads(text=facts["raw"].decode("utf-8"))["cik"]) == cik,
          "COMPANYFACTS_ENTITY_CONFLICT")

    def arguments(item):
        proof = item["proof"]
        return {"company_id": company_id, "target_period": target,
                "source_repo_relative_path": proof["request_repo_relative_path"],
                "source_url": proof["source_url"], "accession": accession,
                "document_name": proof["document_name"],
                "request_attempt_id": proof["request_attempt_id"]}

    body = {"company_id": company_id, "entity": str(cik), **selection,
            "companyfacts_input": arguments(facts),
            "table_input": {**arguments(primary), "source_media_type": "text/html",
                            "source_role": "target_primary"},
            "source_proofs": [s["proof"] for s in (inventory, primary, facts)],
            "selection_rule": "LATEST_ORDINARY_PERIOD_IN_SAVED_SUBMISSIONS",
            "source_evidence": "LEDGER_BOUND_SAVED_BYTES",
            "update_status": ("AMENDMENT_PROCESSING_REQUIRED"
                              if selection["amendments"] else "ORIGINAL_INPUT_READY"),
            "current_latest_verified": False,
            "execution": "NOT_EXECUTED", "production_authorized": False}
    return {**body, "input_id": content_hash(value=body)}


def inspect_saved_annual_inputs(*, repo_root: Path):
    """Keep every configured company and isolate input-local failures."""
    reports = []
    for company in _registry_rows(repo_root=repo_root):
        try:
            prepared = prepare_saved_annual_input(
                repo_root=repo_root, company_id=company["company_id"])
            reports.append({"company_id": company["company_id"],
                            "status": prepared["update_status"],
                            "prepared_input": prepared})
        except NormalAnnualInputError as error:
            reports.append({"company_id": company["company_id"],
                            "status": "INPUT_BLOCKED", "category": error.category,
                            "reason": str(error)})
        except (AnnualInputError, AnnualUpdateError) as error:
            reason = str(error)
            category = ("SOURCE_ACCESS_FAILED" if reason.startswith(
                "LATEST_SOURCE_REQUEST_FAILED") else "SOURCE_UNAVAILABLE"
                if reason.startswith("SAVED_SOURCE_MISSING")
                else "SOURCE_INTEGRITY_ERROR")
            reports.append({"company_id": company["company_id"],
                            "status": "INPUT_BLOCKED",
                            "category": category, "reason": reason})
        except (ValueError, KeyError, TypeError, OSError) as error:
            # The orchestration boundary records an actual parser/schema/I/O
            # fault without pretending the issuer omitted a financial fact.
            reports.append({"company_id": company["company_id"],
                            "status": "INPUT_BLOCKED",
                            "category": "IMPLEMENTATION_ERROR",
                            "error_type": type(error).__name__,
                            "reason": str(error)})
    return {"companies": reports, "execution": "NOT_EXECUTED",
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
