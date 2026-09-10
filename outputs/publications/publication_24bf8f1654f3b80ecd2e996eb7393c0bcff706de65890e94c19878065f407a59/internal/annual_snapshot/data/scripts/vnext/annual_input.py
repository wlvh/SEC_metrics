"""Prepare calendar-year candidate inputs from saved SEC material only.

This bounded entry supports continuous primary entities and unamended 10-Ks.
It returns arguments for existing structured/table Run entrypoints, not a
release plan or permission to execute a LIVE table task. No result is read.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sec_http import parse_request_log_rows, validate_request_log_manifest
from sec_pipeline import filing_rows_from_submission_payloads
from sec_urls import accession_document_url, companyfacts_url, submissions_url

from .batch_workflow import _registry_rows, request_attempt_binding
from .canonical import content_hash, sha256_bytes, strict_json_loads
from .deterministic_router import parse_accession_xbrl_source
from .sources import resolve_repository_file


class AnnualInputError(ValueError):
    """Reject absent, ambiguous, amended, or unsupported annual input."""


def _saved_source(*, repo_root: Path, rows: list, url: str,
                  accession: str = "") -> tuple:
    """Read the latest successful saved response through its ledger proof."""
    matches = [row for row in rows if row["source_url"] == url
               and row["method"] == "GET" and row["status_code"] == "200"
               and not row["error"]]
    if not matches:
        raise AnnualInputError("SAVED_SOURCE_MISSING: " + url)
    row = matches[-1]
    binding = request_attempt_binding(
        repo_root=repo_root, source_url=url,
        content_sha256=row["content_sha256"], accession=accession,
        document_name=row["document_name"],
    )
    path = resolve_repository_file(
        repo_root=repo_root,
        repo_relative_path=binding["request_repo_relative_path"],
    )
    raw = path.read_bytes()
    if sha256_bytes(content=raw) != row["content_sha256"]:
        raise AnnualInputError("SOURCE_CHANGED_DURING_PREPARATION")
    return ({"source_url": url, "accession": accession,
             "document_name": row["document_name"],
             "content_sha256": row["content_sha256"], **binding},
            raw)


def _json(*, raw: bytes) -> dict:
    value = strict_json_loads(text=raw.decode("utf-8"))
    if type(value) is not dict:
        raise AnnualInputError("SOURCE_ROOT_NOT_OBJECT")
    return value


def _annual_period(*, raw: bytes, cik: int, filing: dict) -> dict:
    """Cross-check submissions with native DEI facts and their XBRL context."""
    parsed = parse_accession_xbrl_source(raw_bytes=raw)

    contexts = []

    def dei(name: str) -> tuple:
        facts = [f for f in parsed.facts
                 if f["qualified_name"] == "dei:" + name]
        if not facts:
            raise AnnualInputError("DEI_FACT_MISSING: " + name)
        values = {(f["text"].strip(), f["context_ref"]) for f in facts}
        if len(values) != 1:
            raise AnnualInputError("DEI_FACT_AMBIGUOUS: " + name)
        value, context_id = next(iter(values))
        context = parsed.contexts.get(context_id)
        if (context is None or context["dimensions"]
                or context["typed_dimension_count"]
                or int(context["entity_identifier"]) != cik):
            raise AnnualInputError("DEI_CONTEXT_IDENTITY_MISMATCH: " + name)
        contexts.append(context)
        return value, context

    form, context = dei("DocumentType")
    end, _ = dei("DocumentPeriodEndDate")
    if end != filing["reportDate"]:
        # The existing native inline parser preserves visible DEI date text.
        # Resolve this input metadata only; table text/Reader stays untouched.
        end = datetime.strptime(end, "%B %d, %Y").date().isoformat()
    year, _ = dei("DocumentFiscalYearFocus")
    period, _ = dei("DocumentFiscalPeriodFocus")
    amendment, _ = dei("AmendmentFlag")
    entity, _ = dei("EntityCentralIndexKey")
    start = context.get("period_start", "")
    if (form != "10-K" or form != filing["form"] or period != "FY"
            or amendment != "false" or int(entity) != cik
            or end != filing["reportDate"] or context["period_end"] != end
            or start != year + "-01-01" or end != year + "-12-31"):
        raise AnnualInputError("ANNUAL_IDENTITY_OR_PERIOD_UNSUPPORTED")
    if any(c.get("period_start") != start or c["period_end"] != end for c in contexts):
        raise AnnualInputError("DEI_CONTEXT_PERIOD_MISMATCH")
    if not 365 <= (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 366:
        raise AnnualInputError("ANNUAL_DURATION_INVALID")
    return {"fiscal_year": int(year), "period_start": start, "period_end": end}


def prepare_annual_input(*, repo_root: Path, company_id: str,
                         fiscal_year: Optional[int] = None) -> dict:
    """Return source-backed kwargs for the existing candidate Run functions.

    Args:
        repo_root: Checkout containing registry and saved request evidence.
        company_id: Configured continuous primary entity with a calendar year.
        fiscal_year: Optional historical calendar year; omission selects the
            latest reported annual period in the saved submissions snapshot.

    The selection uses reportDate, then validates the actual fiscal year and
    duration against primary-document DEI facts. filingDate never substitutes
    for the fiscal year. Historical result tables and qualification fixtures
    do not choose the accession, period, source, or any table location.
    """
    if fiscal_year is not None and (type(fiscal_year) is not int
                                    or not 1900 <= fiscal_year <= 9998):
        raise AnnualInputError("FISCAL_YEAR_INVALID")
    companies = [r for r in _registry_rows(repo_root=repo_root)
                 if r["company_id"] == company_id]
    if len(companies) != 1:
        raise AnnualInputError("COMPANY_NOT_UNIQUE")
    company = companies[0]
    if (company["entity_continuity_status"] != "continuous"
            or company["related_ciks"] or company["fiscal_year_end"] != "1231"):
        raise AnnualInputError("ONLY_CONTINUOUS_CALENDAR_YEAR_SUPPORTED")
    cik = int(company["primary_cik"])
    ledger = repo_root / "evidence/requests_log.csv"
    validate_request_log_manifest(log_path=ledger)
    rows = parse_request_log_rows(text=ledger.read_text(encoding="utf-8"))
    inventory, raw = _saved_source(
        repo_root=repo_root, rows=rows, url=submissions_url(cik=cik),
    )
    submissions = _json(raw=raw)
    if int(submissions["cik"]) != cik:
        raise AnnualInputError("SUBMISSIONS_CIK_MISMATCH")
    # Deliberately bounded to the current submissions block. Do not silently
    # claim historical coverage when the requested year precedes that block.
    filings = filing_rows_from_submission_payloads(
        company=company["display_name"], cik=cik, entity_role="primary",
        payloads=[submissions],
    )
    annual = [f for f in filings if f["form"] in {"10-K", "10-K/A"}]
    # An unknown annual period cannot safely be excluded from selection,
    # including when the caller explicitly requests a historical year.
    for filing in annual:
        report_date = filing["reportDate"]
        try:
            if (not isinstance(report_date, str)
                    or date.fromisoformat(report_date).isoformat() != report_date):
                raise ValueError("Expected YYYY-MM-DD")
        except ValueError as error:
            raise AnnualInputError(
                "ANNUAL_REPORT_DATE_INVALID: " + filing["accessionNumber"]
            ) from error
    if fiscal_year is None:
        if not annual:
            raise AnnualInputError("ANNUAL_FILING_MISSING_IN_SAVED_BLOCK")
        fiscal_year = date.fromisoformat(max(f["reportDate"] for f in annual)).year
    # Old supplemental shards are only safely irrelevant when they predate
    # this calendar year. Otherwise stop instead of inventing discovery rules.
    boundary = "{}-01-01".format(fiscal_year)
    if any(f["filingTo"] >= boundary for f in submissions["filings"]["files"]):
        raise AnnualInputError("SUPPLEMENTAL_HISTORY_REQUIRED")
    selected = [f for f in annual
                if date.fromisoformat(f["reportDate"]).year == fiscal_year]
    if not selected:
        raise AnnualInputError("ANNUAL_FILING_MISSING_IN_SAVED_BLOCK")
    if any(f["form"] == "10-K/A" for f in selected):
        raise AnnualInputError("AMENDED_ANNUAL_UNSUPPORTED")
    if len(selected) != 1:
        raise AnnualInputError("ANNUAL_FILING_AMBIGUOUS")
    filing = selected[0]
    accession, document = filing["accessionNumber"], filing["primaryDocument"]
    if not document or "/" in document or "\\" in document:
        raise AnnualInputError("PRIMARY_DOCUMENT_INVALID")
    primary, raw = _saved_source(
        repo_root=repo_root, rows=rows,
        url=accession_document_url(cik=cik, accession=accession,
                                   document_name=document),
        accession=accession,
    )
    target = _annual_period(raw=raw, cik=cik, filing=filing)
    if target["fiscal_year"] != fiscal_year:
        raise AnnualInputError("FISCAL_YEAR_MISMATCH")
    facts, raw = _saved_source(
        repo_root=repo_root, rows=rows, url=companyfacts_url(cik=cik),
        accession=accession,
    )
    if int(_json(raw=raw)["cik"]) != cik:
        raise AnnualInputError("COMPANYFACTS_CIK_MISMATCH")

    def arguments(source: dict) -> dict:
        return {"company_id": company_id, "target_period": target,
                "source_repo_relative_path": source["request_repo_relative_path"],
                "source_url": source["source_url"], "accession": accession,
                "document_name": source["document_name"],
                "request_attempt_id": source["request_attempt_id"]}

    body = {"companyfacts_input": arguments(facts),
            "table_input": {**arguments(primary), "source_media_type": "text/html",
                            "source_role": "target_primary"},
            "source_proofs": [inventory, primary, facts]}
    return {**body, "input_id": content_hash(value=body)}
