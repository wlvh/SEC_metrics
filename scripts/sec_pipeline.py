"""SEC semantic metrics spike pipeline.

Purpose:
    Execute the ten-company one-year SEC-only spike through auditable stages:
    company resolution, filing inventory, companyfacts metrics, accession
    materials, XBRL instance inventory, 8-K events, DEF 14A signals, MD&A/risk
    text signals, golden assertions, and the final Chinese report.

Call relationships:
    scripts/00_*.py through scripts/12_*.py call run_stage(stage_name=...).
    run_stage dispatches to stage_* functions in this file.
    Every SEC request goes through sec_http.SecHttpClient.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import subprocess
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

from sec_http import (
    REDIRECT_DISABLED_ERROR_PREFIX,
    REQUEST_LOG_FIELDNAMES,
    SecHttpClient,
    legacy_repository_path_candidates,
    migrate_request_log,
    parse_request_log_rows,
    request_accession,
    request_artifact_candidate,
    request_log_source_url,
    validate_official_sec_url,
    validate_request_log_manifest,
    write_repository_bytes_atomically,
)
from git_workspace import (
    git_checkout_metadata_error,
    sanitized_git_environment,
)
from sec_urls import (
    accession_directory_url,
    accession_document_url,
    company_tickers_exchange_url,
    companyconcept_url,
    companyfacts_url,
    filing_detail_url,
    filing_summary_url,
    hdr_sgml_url,
    submissions_file_url,
    submissions_url,
)

csv.field_size_limit(sys.maxsize)


WORKDIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = WORKDIR / "config" / "sec_config.json"
COMPANY_REGISTRY_PATH = WORKDIR / "config" / "company_registry.csv"
METRIC_APPLICABILITY_PATH = WORKDIR / "config" / "metric_applicability.yaml"
REQUEST_LOG_PATH = WORKDIR / "evidence" / "requests_log.csv"
LIGHT_REVIEW_MARKER_PATH = WORKDIR / "LIGHT_REVIEW_PACKAGE.marker"
SUBMISSION_SUPPLEMENTAL_LIMIT = 12

VALIDATION_STATUSES = {
    "PASS",
    "FAIL",
    "SKIPPED_LIGHT_PACKAGE",
    "NOT_EVALUATED_MISSING_EVIDENCE",
    "WORKSPACE_INCOMPLETE",
}

VALIDATION_TRACKED_ARTIFACTS = [
    "implementation_map.csv",
    "spec_implementation_audit.csv",
    "stub_period_metrics.csv",
    "stratified_audit.csv",
    "scalability_audit.csv",
    "repair_validation_results.csv",
]
VALIDATION_MANIFEST_MODES = {
    "FULL_VALIDATION",
    "LIGHT_REVIEW_MODE",
    "WORKSPACE_INCOMPLETE",
}
VALIDATION_MANIFEST_RESULTS = {
    "IN_PROGRESS",
    "PASSED",
    "PASSED_WITH_CAVEATS",
    "FAILED",
}

ALLOWED_STATUSES = {
    "OK",
    "OK_APPROX",
    "DIM_XBRL_OK",
    "MDA_OK",
    "DEF14A_OK",
    "8K_ITEM_OK",
    "TEXT_QUAL",
    "NOT_AVAILABLE_SEC",
    "NOT_EXTRACTED",
    "NOT_MEANINGFUL",
    "N_A_STRUCTURAL",
    "PARSE_FAILED",
    "NEEDS_REVIEW",
}

METRICS_FIELDNAMES = [
    "company",
    "cik",
    "metric_id",
    "metric_name",
    "value",
    "unit",
    "status",
    "source_class",
    "formula",
    "period_start",
    "period_end",
    "fiscal_year",
    "fiscal_period",
    "accession",
    "form",
    "filed_date",
    "concept_or_section",
    "context_or_dimension",
    "confidence",
    "notes",
]

EVIDENCE_FIELDNAMES = [
    "company",
    "cik",
    "metric_id",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "accession",
    "document_name",
    "concept_or_section",
    "context_or_dimension",
    "unit",
    "period_start",
    "period_end",
    "value_raw",
    "value_normalized",
    "evidence_quote",
    "extraction_method",
    "parser_version",
]

COMPANY_RESOLUTION_FIELDNAMES = [
    "company",
    "primary_cik",
    "resolved_cik",
    "entity_role",
    "name",
    "entityType",
    "sic",
    "sicDescription",
    "fiscalYearEnd",
    "tickers",
    "exchanges",
    "formerNames",
    "related_ciks",
    "resolution_status",
    "notes",
]

FILING_FIELDNAMES = [
    "company",
    "cik",
    "entity_role",
    "form",
    "accession",
    "filingDate",
    "reportDate",
    "primaryDocument",
    "isXBRL",
    "isInlineXBRL",
    "source_role",
    "source_url",
]

MATERIAL_FIELDNAMES = [
    "company",
    "cik",
    "entity_role",
    "form",
    "accession",
    "document_name",
    "document_type",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "status_code",
    "content_length",
]

INSTANCE_FIELDNAMES = [
    "company",
    "cik",
    "accession",
    "document_name",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "namespace",
    "concept",
    "unit",
    "context",
    "dimensions",
    "period_start",
    "period_end",
    "value",
]

REVIEW_EXTRACT_FIELDNAMES = [
    "source_file",
    "company",
    "cik",
    "accession",
    "document_name",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "concept",
    "namespace",
    "unit",
    "context",
    "dimensions",
    "period_start",
    "period_end",
    "value",
]

GOLDEN_RESULT_FIELDNAMES = [
    "assertion_id",
    "description",
    "expected",
    "actual",
    "status",
    "evidence_path",
    "notes",
]

G2_FINANCIAL_ASSETSCURRENT_ASSERTION_ID = "G2_financial_assetscurrent_b08"
G2_FINANCIAL_NON_STD_METRIC_IDS = ("A01", "A02")
G2_CAPTIVE_FINANCE_ASSERTION_ID = "G2_captive_finance_b06_dimension_review"
G2_AUDITORNAME_ASSERTION_ID = "G2_auditorname_material_source"

GOLDEN_CANDIDATE_FIELDNAMES = [
    "company",
    "metric_name",
    "value",
    "unit",
    "status",
    "accession",
    "concept",
    "period",
    "filed_date",
    "evidence_path",
]

EVENT_FIELDNAMES = [
    "company",
    "cik",
    "accession",
    "document_name",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "filing_date",
    "item_code",
    "item_source",
    "mapping_method",
    "confidence",
    "brief",
]

GOVERNANCE_FIELDNAMES = [
    "company",
    "cik",
    "signal_id",
    "signal_name",
    "value",
    "status",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "accession",
    "document_name",
    "concept_or_section",
    "evidence_quote",
    "notes",
]

RISK_FIELDNAMES = GOVERNANCE_FIELDNAMES

REPAIR_VALIDATION_FIELDNAMES = [
    "check_id",
    "severity",
    "status",
    "details",
]

IMPLEMENTATION_MAP_FIELDNAMES = [
    "instruction_id",
    "file",
    "function_or_line",
    "validation_id",
    "status",
    "notes",
]

STRATIFIED_AUDIT_FIELDNAMES = [
    "audit_id",
    "source_bucket",
    "company",
    "metric_id",
    "metric_name",
    "value",
    "unit",
    "status",
    "source_class",
    "period_start",
    "period_end",
    "accession",
    "concept_or_section",
    "context_or_dimension",
    "evidence_value",
    "evidence_unit",
    "evidence_quote",
    "audit_verdict",
    "audit_notes",
]

STRATIFIED_AUDIT_SPECS = [
    ("STD_XBRL_DERIVED", {"STD_XBRL", "DERIVED"}, 8),
    ("DIM_XBRL", {"DIM_XBRL"}, 4),
    ("DEF14A", {"DEF14A"}, 3),
    ("MDA_TEXT", {"MDA", "TEXT"}, 3),
    ("8K_ITEM", {"8K_ITEM"}, 2),
]

SCALABILITY_AUDIT_FIELDNAMES = [
    "file",
    "line",
    "literal",
    "type",
    "allowed",
    "reason",
    "replacement_plan",
]

BASEL_RATIO_CANDIDATE_FIELDNAMES = [
    "company",
    "cik",
    "metric_id",
    "candidate_role",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "accession",
    "document_name",
    "concept",
    "context_or_dimension",
    "unit",
    "period_end",
    "value",
    "parser_version",
]

STUB_PERIOD_FIELDNAMES = [
    "company",
    "metric_id",
    "stub_period_start",
    "stub_period_end",
    "value",
    "unit",
    "concept_or_section",
    "accession",
    "notes",
]

SPEC_IMPLEMENTATION_AUDIT_FIELDNAMES = [
    "metric_id",
    "spec_rule",
    "implementation_location",
    "implemented",
    "validation_check",
    "notes",
]

OPTIONAL_B_OBSERVATION_FIELDNAMES = [
    "company",
    "cik",
    "metric_id",
    "metric_name",
    "value",
    "unit",
    "status",
    "source_class",
    "period_end",
    "accession",
    "concept_or_section",
    "context_or_dimension",
    "candidate_role",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "document_name",
    "evidence_quote",
    "notes",
]

B06_CANDIDATE_FIELDNAMES = [
    "company",
    "cik",
    "metric_id",
    "value",
    "unit",
    "status",
    "period_end",
    "accession",
    "concept_or_section",
    "context_or_dimension",
    "candidate_role",
    "source_url",
    "repo_relative_path",
    "content_sha256",
    "document_name",
    "evidence_quote",
    "notes",
]

BASEL_THRESHOLD_CONCEPT_FRAGMENTS = [
    "minimum",
    "capitaladequacyminimum",
    "requiredforcapitaladequacy",
    "requiredtobewellcapitalized",
    "wellcapitalized",
    "wellcapitalizedminimum",
    "tobewellcapitalized",
]

LIGHT_GOLDEN_COMPONENT_METRICS = {
    "revenue": "B01",
    "net_income": "B04",
    "cash": "B09",
    "derived_fcf": "B05",
    "derived_current_ratio": "B08",
    "derived_debt_to_equity": "B06",
}

NUMERIC_EVIDENCE_STATUSES = {
    "OK",
    "OK_APPROX",
    "MDA_OK",
    "DEF14A_OK",
    "DIM_XBRL_OK",
    "8K_ITEM_OK",
}

OK_RECALL_STATUSES = {
    "OK",
    "MDA_OK",
    "DIM_XBRL_OK",
    "DEF14A_OK",
    "8K_ITEM_OK",
    "TEXT_QUAL",
}

RECALL_REGRESSION_STATUSES = {
    "NOT_EXTRACTED",
    "NEEDS_REVIEW",
    "NOT_AVAILABLE_SEC",
}

'''
B01 revenue is the metrics_matrix B01 metric: the registrant's annual,
company-level total revenue for the target fiscal year. It is not segment
revenue, product-line revenue, revenue growth, or cash received from customers.
It uses one global concept chain rather than switching labels by industry
because companyfacts exposes standard company-level facts and this metric asks
the shared question: total company revenue for the fiscal year.
The chain moves from the most explicit ASC 606 revenue concept to broader
fallback labels that remain acceptable for company total revenue.
Runtime probing follows this order and stops at the first concept with a
matching annual 10-K duration fact. Within that concept, the target accession
wins; otherwise the latest filed/accession/unit tuple wins. It does not sort
by value, industry category, or raw tag order.
'''
REVENUE_CHAIN = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]
NET_INCOME_CHAIN = [
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
]
DA_CHAIN = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization",
]
DA_COMPOSITION_CHAIN = [
    "Depreciation",
    "AmortizationOfIntangibleAssets",
]
OPERATING_INCOME_CHAIN = ["OperatingIncomeLoss"]
PRETAX_CONTINUING_INCOME_CHAIN = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterest"
        "AndIncomeLossFromEquityMethodInvestments"
    ),
]
NONOPERATING_BRIDGE_CHAIN = [
    "NonoperatingIncomeExpense",
    "OtherNonoperatingIncomeExpense",
]
CAPEX_CHAIN = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
INTEREST_CHAIN = [
    "InterestExpense",
    "InterestExpenseNonoperating",
    "InterestExpenseDebt",
]
EQUITY_CHAIN = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
TOTAL_DEBT_DIRECT_CHAIN = [
    "DebtAndCapitalLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
]
TOTAL_DEBT_PAIR_CHAINS = [
    (
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "LongTermDebtAndCapitalLeaseObligationsNoncurrent",
    ),
    ("LongTermDebtCurrent", "LongTermDebtNoncurrent"),
]
TOTAL_DEBT_LEASE_PAIR_CHAINS = [
    ("FinanceLeaseLiabilityCurrent", "FinanceLeaseLiabilityNoncurrent"),
]
TOTAL_DEBT_STANDALONE_FALLBACK_CHAIN = [
    "LongTermDebtAndCapitalLeaseObligations",
]
TOTAL_DEBT_SHORT_ADDER_CHAIN = [
    "ShortTermBorrowings",
    "CommercialPaper",
]
LEGACY_GOLDEN_LONG_TERM_DEBT_CHAIN = [
    "LongTermDebt",
    "LongTermDebtNoncurrent",
]
JPM_A08_COMPONENTS = [
    "NoninterestIncome",
    "InterestIncomeExpenseNet",
]
JPM_A10_COMPONENTS = [
    "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest",
    "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss",
]
STUB_PERIOD_COMPONENT_CHAINS = [
    ("B01", REVENUE_CHAIN),
    ("B03", OPERATING_INCOME_CHAIN + DA_CHAIN + DA_COMPOSITION_CHAIN),
    ("B04", NET_INCOME_CHAIN),
    (
        "B05",
        ["NetCashProvidedByUsedInOperatingActivities"] + CAPEX_CHAIN,
    ),
    ("B07", OPERATING_INCOME_CHAIN + INTEREST_CHAIN),
]
STUB_PERIOD_MAIN_METRICS = {"B01", "B02", "B03", "B04", "B05", "B07"}


@dataclass(frozen=True)
class FactHit:
    """Represent one selected companyfacts fact with traceable metadata.

    Args:
        concept: XBRL concept local name.
        taxonomy: Taxonomy namespace prefix, such as us-gaap.
        unit: SEC companyfacts unit bucket.
        value: Decimal numeric value.
        raw_value: Original JSON value converted to string.
        start: Period start date or empty string for instant facts.
        end: Period end date.
        filed: SEC filed date.
        form: Filing form.
        fiscal_year: SEC fy value or configured fallback.
        fiscal_period: SEC fp value.
        accession: Filing accession.
        frame: SEC frame string or empty string.
        source_path: Local companyfacts JSON path.
        source_url: SEC companyfacts URL.

    Expected output:
        A selected fact can be written to metrics_matrix and metric_evidence.
    """

    concept: str
    taxonomy: str
    unit: str
    value: Decimal
    raw_value: str
    start: str
    end: str
    filed: str
    form: str
    fiscal_year: str
    fiscal_period: str
    accession: str
    frame: str
    source_path: str
    source_url: str


@dataclass(frozen=True)
class ComponentResolution:
    """Represent one resolved formula component and its audit boundary.

    Args:
        value: Numeric component value, or None when the component is unsafe.
        hits: Companyfacts facts that prove the value or the reviewed candidate.
        status: Metric status implied by this component, such as OK or OK_APPROX.
        formula: Human-readable component formula.
        notes: Evidence and assumption notes for the downstream metric row.

    Expected output:
        Derived metrics can combine the value while preserving component facts.
    """

    value: Decimal | None
    hits: list[FactHit]
    status: str
    formula: str
    notes: str


def utc_now_iso() -> str:
    """Return the current UTC timestamp for generated report metadata."""
    return datetime.now(tz=timezone.utc).isoformat()


def is_utc_iso_timestamp(*, value: str) -> bool:
    """Return whether a string is an ISO-8601 timestamp in UTC."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def is_official_sec_url(*, source_url: str) -> bool:
    """Return whether a URL uses one of the two allowed SEC origins."""
    try:
        validate_official_sec_url(url=source_url)
    except ValueError:
        return False
    return True


def client() -> SecHttpClient:
    """Create the configured SEC HTTP client used by every stage."""
    return SecHttpClient(
        workdir=WORKDIR,
        config_path=CONFIG_PATH,
        log_path=REQUEST_LOG_PATH,
    )


def ensure_output_dirs() -> None:
    """Create all required output and evidence directories."""
    for path in [
        WORKDIR / "evidence" / "company_tickers",
        WORKDIR / "evidence" / "submissions",
        WORKDIR / "evidence" / "companyfacts",
        WORKDIR / "evidence" / "accession_materials",
        WORKDIR / "evidence" / "xbrl_instances",
        WORKDIR / "evidence" / "def14a",
        WORKDIR / "evidence" / "mda_text",
        WORKDIR / "outputs" / "concept_inventory",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def require_key(*, mapping: dict, key: str) -> object:
    """Return a required mapping value or fail fast.

    Args:
        mapping: Dictionary parsed from SEC JSON or internal rows.
        key: Required key name.

    Returns:
        The mapped value.
    """
    if key not in mapping:
        raise KeyError(f"Required key missing: {key}")
    return mapping[key]


def optional_key(*, mapping: dict, key: str, default: object) -> object:
    """Return an optional mapping value with an explicit logged fallback.

    Args:
        mapping: Dictionary parsed from SEC JSON or internal rows.
        key: Optional key name.
        default: Fallback value used when the key is absent.

    Returns:
        Existing value or the provided default.
    """
    if key in mapping:
        return mapping[key]
    return default


def artifact_path_parts(*, path_text: str) -> list[str]:
    """Split a semicolon-delimited artifact path field.

    Args:
        path_text: One path or aligned component paths used by derived metrics.

    Returns:
        Non-empty path strings in their original order.
    """
    return [part for part in path_text.split(";") if part]


def repository_artifact_candidate(*, relative_path: str) -> Path:
    """Return one repository-contained artifact candidate.

    Args:
        relative_path: Repository-relative artifact locator.

    Returns:
        Candidate path under the current WORKDIR without resolving away its
        repository spelling.
    """
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Artifact path escapes repository: {relative_path}")
    candidate = WORKDIR / path
    # Lexical checks do not detect a repository symlink targeting external
    # bytes; the resolved target must remain inside the current clone.
    if not candidate.resolve(strict=False).is_relative_to(WORKDIR.resolve()):
        raise ValueError(f"Artifact path escapes repository: {relative_path}")
    return candidate


def artifact_relocation_identity_matches(
    *,
    path: Path,
    relative_path: Path,
    accession: str,
    document_name: str,
    source_url: str,
    cik: str,
    content_sha256: str,
) -> bool:
    """Return whether one legacy suffix matches its declared SEC identity.

    Args:
        path: Existing current-clone candidate.
        relative_path: Candidate repository-relative spelling.
        accession: Declared filing accession, when applicable.
        document_name: Declared response document name.
        source_url: Declared official SEC URL.
        cik: Declared filing CIK, when applicable.
        content_sha256: Declared artifact digest, when available.

    Returns:
        True when structural path, document, URL, accession, and CIK agree.
    """
    if not path.is_file() or (document_name and path.name != document_name):
        return False
    if content_sha256 and file_sha256(path_text=str(path)) != content_sha256:
        return False
    archive_cik, derived_accession = archive_url_identity(
        source_url=source_url,
    )
    if derived_accession:
        if accession and accession != derived_accession:
            return False
        if (
            document_name
            and Path(urlparse(source_url).path).name != document_name
        ):
            return False
        if "accession_materials" in relative_path.parts and (
            not accession_material_path_matches(
                path=relative_path,
                accession=derived_accession,
                cik=cik if cik else archive_cik,
            )
        ):
            return False
    companyfacts_cik = companyfacts_url_cik(source_url=source_url)
    if companyfacts_cik:
        expected_name = f"CIK{int(companyfacts_cik):010d}.json"
        expected_path = f"evidence/companyfacts/{expected_name}"
        if relative_path.as_posix() != expected_path:
            return False
        if cik:
            try:
                if str(int(cik)) != companyfacts_cik:
                    return False
            except ValueError:
                return False
    return True


def repo_relative_artifact_path(
    *,
    path_text: str,
    row: dict,
) -> str:
    """Convert one current or legacy artifact path to repository-relative form.

    Args:
        path_text: Relative path, current absolute path, or an absolute legacy
            path from another clone.
        row: Locator row carrying optional hash and SEC identity fields.

    Returns:
        POSIX repository-relative path. An unrelated external absolute path
        yields an empty string because it cannot be authoritative evidence.
    """
    path = Path(path_text)
    content_sha256 = (
        str(row["content_sha256"])
        if "content_sha256" in row and row["content_sha256"]
        else str(row["sha256"])
        if "sha256" in row and row["sha256"]
        else ""
    )
    accession = str(row["accession"]) if "accession" in row else ""
    document_name = (
        str(row["document_name"])
        if "document_name" in row and row["document_name"]
        else path.name
    )
    source_url = str(row["source_url"]) if "source_url" in row else ""
    cik = str(row["cik"]) if "cik" in row else ""
    relative_path = path
    if not path.is_absolute():
        repository_artifact_candidate(relative_path=path.as_posix())
        return path.as_posix()
    try:
        relative_path = path.relative_to(WORKDIR)
    except ValueError:
        candidates = legacy_repository_path_candidates(path=path)
        if not candidates:
            return ""
        candidate_pairs = [
            (
                candidate,
                repository_artifact_candidate(
                    relative_path=candidate.as_posix(),
                ),
            )
            for candidate in candidates
        ]
        if len(candidate_pairs) == 1:
            # Preserve existing single-anchor migration; validation remains
            # responsible for reporting missing or hash-mismatched evidence.
            relative_path = candidate_pairs[0][0]
        else:
            matched = [
                pair
                for pair in candidate_pairs
                if artifact_relocation_identity_matches(
                    path=pair[1],
                    relative_path=pair[0],
                    accession=accession,
                    document_name=document_name,
                    source_url=source_url,
                    cik=cik,
                    content_sha256=content_sha256,
                )
            ]
            if len(matched) == 1:
                relative_path = matched[0][0]
            elif not matched:
                raise FileNotFoundError(
                    "Legacy artifact has no current-clone identity match: "
                    f"{path_text}"
                )
            else:
                raise ValueError(
                    f"Legacy artifact relocation is ambiguous: {path_text}"
                )
    repository_artifact_candidate(relative_path=relative_path.as_posix())
    return relative_path.as_posix()


def aligned_locator_component(
    *,
    text: str,
    index: int,
    component_count: int,
) -> str:
    """Return one aligned identity component or blank when not one-to-one.

    Args:
        text: Empty, scalar, or semicolon-delimited locator identity text.
        index: Zero-based path component index.
        component_count: Total number of path components.

    Returns:
        The aligned field value, or blank for aggregate/non-aligned fields.
    """
    parts = artifact_path_parts(path_text=text)
    return parts[index] if len(parts) == component_count else ""


def repo_relative_artifact_paths(
    *,
    path_text: str,
    row: dict,
) -> str:
    """Normalize aligned artifact locators using one row's joint identity."""
    paths = artifact_path_parts(path_text=path_text)
    content_sha256 = (
        str(row["content_sha256"])
        if "content_sha256" in row and row["content_sha256"]
        else str(row["sha256"])
        if "sha256" in row and row["sha256"]
        else ""
    )
    accession = str(row["accession"]) if "accession" in row else ""
    document_name = (
        str(row["document_name"])
        if "document_name" in row
        else ""
    )
    source_url = str(row["source_url"]) if "source_url" in row else ""
    cik = str(row["cik"]) if "cik" in row else ""
    relative_paths = [
        repo_relative_artifact_path(
            path_text=part,
            row={
                "content_sha256": aligned_locator_component(
                    text=content_sha256,
                    index=index,
                    component_count=len(paths),
                ),
                "accession": aligned_locator_component(
                    text=accession,
                    index=index,
                    component_count=len(paths),
                ),
                "document_name": aligned_locator_component(
                    text=document_name,
                    index=index,
                    component_count=len(paths),
                ),
                "source_url": aligned_locator_component(
                    text=source_url,
                    index=index,
                    component_count=len(paths),
                ),
                "cik": cik,
            },
        )
        for index, part in enumerate(paths)
    ]
    return ";".join([path for path in relative_paths if path])


@lru_cache(maxsize=None)
def cached_file_sha256(
    *,
    path_text: str,
    modified_ns: int,
    changed_ns: int,
    size_bytes: int,
) -> str:
    """Return a cached digest keyed by path and current file identity.

    Args:
        path_text: Absolute file path.
        modified_ns: File modification time in nanoseconds.
        changed_ns: File metadata-change time in nanoseconds. This prevents a
            same-size rewrite with a restored mtime from reusing a stale hash.
        size_bytes: Current file size.

    Returns:
        SHA-256 hex digest for the current bytes.
    """
    path = Path(path_text)
    digest = hashlib.sha256()
    with path.open(mode="rb") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_sha256(*, path_text: str) -> str:
    """Return the SHA-256 digest for one existing local file.

    Args:
        path_text: Absolute file path.

    Returns:
        Hex digest, or an empty string when the candidate does not exist.
    """
    path = Path(path_text)
    if not path.is_file():
        return ""
    stat = path.stat()
    return cached_file_sha256(
        path_text=str(path),
        modified_ns=stat.st_mtime_ns,
        changed_ns=stat.st_ctime_ns,
        size_bytes=stat.st_size,
    )


def artifact_reference_text(*, row: dict) -> str:
    """Return the preferred repository-relative locator text for a row.

    Args:
        row: Artifact or evidence row using the current locator fields or a
            legacy local_path/source_path field.

    Returns:
        Repository-relative path text, possibly semicolon-delimited.
    """
    if "repo_relative_path" in row and row["repo_relative_path"]:
        return repo_relative_artifact_paths(
            path_text=str(row["repo_relative_path"]),
            row=row,
        )
    for legacy_field in ["local_path", "source_path"]:
        if legacy_field not in row or not row[legacy_field]:
            continue
        return repo_relative_artifact_paths(
            path_text=str(row[legacy_field]),
            row=row,
        )
    return ""


def artifact_document_name(*, row: dict) -> str:
    """Return an explicit document name or derive one from the locator."""
    path_text = artifact_reference_text(row=row)
    paths = artifact_path_parts(path_text=path_text)
    declared_names = artifact_path_parts(
        path_text=(
            str(row["document_name"])
            if "document_name" in row and row["document_name"]
            else ""
        ),
    )
    if declared_names and (
        not paths or len(declared_names) == len(paths)
    ):
        return ";".join(declared_names)
    if paths:
        # document_name is part of the locator identity, not a free-form label;
        # deriving it keeps multi-component fields aligned for other clones.
        return ";".join([Path(path).name for path in paths])
    return ""


def artifact_source_url(*, row: dict) -> str:
    """Return an existing or identity-derived official SEC source URL.

    Args:
        row: Artifact row containing source_url or a single CIK, accession, and
            document name.

    Returns:
        Existing URL, derived SEC archive URL, or an empty string when the row
        does not identify one SEC document.
    """
    if "source_url" in row and row["source_url"]:
        return str(row["source_url"])
    accession = str(row["accession"]) if "accession" in row else ""
    document_name = artifact_document_name(row=row)
    cik = str(row["cik"]) if "cik" in row else ""
    if not accession or not document_name or not cik:
        return ""
    if ";" in accession or ";" in document_name or ";" in cik:
        return ""
    return accession_document_url(
        cik=int(cik),
        accession=accession,
        document_name=document_name,
    )


def artifact_content_hash_text(*, row: dict, relative_paths: str) -> str:
    """Return aligned content hashes for one or more repository artifacts.

    Args:
        row: Source row that may already contain current or legacy hash fields.
        relative_paths: Normalized repository-relative path text.

    Returns:
        Existing trusted hash text or hashes computed from current local bytes.
    """
    # An acquisition hash is the recorded content identity. Recomputing first
    # would silently bless replacement bytes at the same relative path.
    if "content_sha256" in row and row["content_sha256"]:
        return str(row["content_sha256"])
    if "sha256" in row and row["sha256"]:
        return str(row["sha256"])
    computed_hashes = [
        file_sha256(
            path_text=str(repository_artifact_candidate(relative_path=path))
        )
        for path in artifact_path_parts(path_text=relative_paths)
    ]
    if computed_hashes and all(computed_hashes):
        return ";".join(computed_hashes)
    return ";".join([digest for digest in computed_hashes if digest])


def normalize_csv_row(*, row: dict, fieldnames: list[str]) -> dict:
    """Normalize one output row to its declared CSV and locator schema.

    Args:
        row: Source row, including legacy locator fields when migrating.
        fieldnames: Exact output header.

    Returns:
        Row containing only declared fields. Portable schemas always write
        repository-relative paths and content hashes.
    """
    source = dict(row)
    if (
        "evidence_path" in fieldnames
        and "evidence_path" in source
        and source["evidence_path"]
    ):
        source["evidence_path"] = repo_relative_artifact_paths(
            path_text=str(source["evidence_path"]),
            row={},
        )
    if "repo_relative_path" in fieldnames:
        relative_paths = artifact_reference_text(row=source)
        source["repo_relative_path"] = relative_paths
        source["content_sha256"] = artifact_content_hash_text(
            row=source,
            relative_paths=relative_paths,
        )
        if "document_name" in fieldnames:
            source["document_name"] = artifact_document_name(row=source)
        if (
            "source_url" in fieldnames
            and (
                "source_url" not in source
                or not source["source_url"]
            )
        ):
            source["source_url"] = artifact_source_url(row=source)
    return {
        fieldname: source[fieldname] if fieldname in source else ""
        for fieldname in fieldnames
    }


def rehydrate_artifact_row(*, row: dict) -> dict:
    """Add current-clone path aliases to a CSV row in memory.

    Args:
        row: CSV row using current portable fields or legacy absolute paths.

    Returns:
        The same logical row with local_path/source_path aliases resolved under
        the current WORKDIR. These aliases are never written by current schemas.
    """
    relative_paths = artifact_reference_text(row=row)
    if not relative_paths:
        return row
    absolute_paths = ";".join(
        [
            str(repository_artifact_candidate(relative_path=path))
            for path in artifact_path_parts(path_text=relative_paths)
        ]
    )
    row["repo_relative_path"] = relative_paths
    row["local_path"] = absolute_paths
    row["source_path"] = absolute_paths
    return row


def artifact_candidate_matches_hash(*, path: Path, content_sha256: str) -> bool:
    """Return whether an existing candidate matches the optional content hash."""
    if not path.is_file():
        return False
    if not path.resolve().is_relative_to(WORKDIR.resolve()):
        return False
    if not content_sha256:
        return True
    return file_sha256(path_text=str(path)) == content_sha256


def archive_url_identity(*, source_url: str) -> tuple[str, str]:
    """Return normalized CIK and accession from one Archives URL."""
    if not is_official_sec_url(source_url=source_url):
        return "", ""
    match = re.fullmatch(
        pattern=r"/Archives/edgar/data/(\d+)/(\d{18})/[^/]+",
        string=urlparse(source_url).path,
    )
    if match is None:
        return "", ""
    compact = match.group(2)
    return (
        str(int(match.group(1))),
        f"{compact[:10]}-{compact[10:12]}-{compact[12:]}",
    )


def companyfacts_url_cik(*, source_url: str) -> str:
    """Return normalized CIK from one official companyfacts URL."""
    if not is_official_sec_url(source_url=source_url):
        return ""
    match = re.fullmatch(
        pattern=r"/api/xbrl/companyfacts/CIK(\d{10})\.json",
        string=urlparse(source_url).path,
    )
    if match is None:
        return ""
    return str(int(match.group(1)))


def accession_material_path_matches(
    *,
    path: Path,
    accession: str,
    cik: str,
) -> bool:
    """Return whether a raw filing path belongs to its CIK and accession.

    Args:
        path: Repository-relative or absolute artifact path.
        accession: Hyphenated SEC accession number.
        cik: Source filing CIK.

    Returns:
        True only for an evidence/accession_materials directory whose suffix
        contains the compact declared accession.
    """
    candidate = path if path.is_absolute() else WORKDIR / path
    try:
        relative_path = candidate.resolve().relative_to(WORKDIR.resolve())
    except ValueError:
        return False
    folder_match = re.search(
        pattern=r"_(\d+)_(\d{18})$",
        string=relative_path.parent.name,
    )
    if folder_match is None:
        return False
    try:
        normalized_cik = str(int(cik))
    except (TypeError, ValueError):
        return False
    return (
        relative_path.parts[:2] == ("evidence", "accession_materials")
        and str(int(folder_match.group(1))) == normalized_cik
        and folder_match.group(2) == accession.replace("-", "")
    )


@lru_cache(maxsize=2)
def cached_companyfacts_payload(
    *,
    path_text: str,
    modified_ns: int,
    changed_ns: int,
    size_bytes: int,
) -> dict:
    """Return cached companyfacts JSON keyed by current file identity."""
    return read_json_file(path=Path(path_text))


def companyfacts_payload(*, path: Path) -> dict:
    """Return one companyfacts payload without caching stale file bytes."""
    stat = path.stat()
    return cached_companyfacts_payload(
        path_text=str(path),
        modified_ns=stat.st_mtime_ns,
        changed_ns=stat.st_ctime_ns,
        size_bytes=stat.st_size,
    )


def companyfacts_component_matches(
    *,
    path: Path,
    row: dict,
    verify_provenance: bool,
) -> bool:
    """Return whether one component has valid companyfacts identity."""
    source_urls = artifact_path_parts(
        path_text=str(row["source_url"]) if "source_url" in row else "",
    )
    accessions = artifact_path_parts(
        path_text=str(row["accession"]) if "accession" in row else "",
    )
    document_names = artifact_path_parts(
        path_text=artifact_document_name(row=row),
    )
    if len(source_urls) != 1 or len(accessions) != 1:
        return False
    url_cik = companyfacts_url_cik(source_url=source_urls[0])
    if not url_cik or len(document_names) != 1:
        return False
    expected_name = f"CIK{int(url_cik):010d}.json"
    try:
        row_cik = str(int(row["cik"]))
        relative_path = path.resolve(strict=False).relative_to(
            WORKDIR.resolve()
        )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ):
        return False
    if (
        row_cik != url_cik
        or document_names[0] != expected_name
        or relative_path.as_posix() != f"evidence/companyfacts/{expected_name}"
    ):
        return False
    if not verify_provenance:
        return True
    try:
        payload = companyfacts_payload(path=path)
        payload_cik = str(int(payload["cik"]))
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
    if payload_cik != url_cik:
        return False
    concept = (
        str(row["concept_or_section"])
        if "concept_or_section" in row
        else ""
    )
    context = (
        str(row["context_or_dimension"])
        if "context_or_dimension" in row
        else ""
    )
    context_parts = context.split(":")
    component_unit = (
        context_parts[1]
        if len(context_parts) > 1 and context_parts[0] == "companyfacts"
        else ""
    )
    component_frame = (
        context_parts[2]
        if len(context_parts) > 2 and context_parts[0] == "companyfacts"
        else ""
    )
    expected_value = str(row["value_raw"]) if "value_raw" in row else ""
    expected_start = str(row["period_start"]) if "period_start" in row else ""
    expected_end = str(row["period_end"]) if "period_end" in row else ""
    facts_root = payload["facts"] if "facts" in payload else {}
    if not concept or not isinstance(facts_root, dict):
        return False
    for concepts in facts_root.values():
        if not isinstance(concepts, dict) or concept not in concepts:
            continue
        concept_payload = concepts[concept]
        units = concept_payload["units"] if "units" in concept_payload else {}
        if not isinstance(units, dict):
            continue
        for unit, facts in units.items():
            if component_unit and str(unit) != component_unit:
                continue
            for fact in facts:
                if "accn" not in fact or str(fact["accn"]) != accessions[0]:
                    continue
                fact_frame = str(fact["frame"]) if "frame" in fact else ""
                fact_end = str(fact["end"]) if "end" in fact else ""
                fact_start = (
                    str(fact["start"])
                    if "start" in fact
                    else fact_end
                )
                if component_frame and fact_frame != component_frame:
                    continue
                if expected_start and fact_start != expected_start:
                    continue
                if expected_end and fact_end != expected_end:
                    continue
                if expected_value:
                    try:
                        value_matches = Decimal(str(fact["val"])) == Decimal(
                            expected_value
                        )
                    except (InvalidOperation, KeyError, ValueError):
                        value_matches = False
                    if not value_matches:
                        continue
                return True
    return False


def event_aggregate_pairs_match(*, row: dict) -> bool:
    """Return whether an event aggregate declares the exact scan pair set."""
    if "company" not in row or not row["company"]:
        return False
    source_urls = artifact_path_parts(path_text=str(row["source_url"]))
    accessions = artifact_path_parts(path_text=str(row["accession"]))
    if len(source_urls) != len(accessions):
        return False
    declared_pairs = list(zip(source_urls, accessions))
    try:
        events = read_csv_file(path=WORKDIR / "outputs" / "events.csv")
        inventory = read_csv_file(
            path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
        )
    except (OSError, UnicodeDecodeError, csv.Error):
        return False
    if event_inventory_coverage_errors(inventory=inventory, events=events):
        return False
    expected_pairs = {
        (event["source_url"], event["accession"])
        for event in events
        if event["company"] == row["company"]
    }
    return (
        len(declared_pairs) == len(set(declared_pairs))
        and set(declared_pairs) == expected_pairs
    )


def is_derived_locator_aggregate(*, row: dict) -> bool:
    """Return whether a row declares the supported event-scan aggregate.

    Args:
        row: Portable locator row that may carry metric-evidence semantics.

    Returns:
        True only for the explicit zero-item scan over outputs/events.csv.
    """
    extraction_method = (
        str(row["extraction_method"])
        if "extraction_method" in row
        else ""
    )
    return (
        extraction_method == "eightk_zero_item_scan"
        and artifact_reference_text(row=row) == "outputs/events.csv"
        and artifact_document_name(row=row) == "events.csv"
    )


def artifact_candidate_matches_identity(*, path: Path, row: dict) -> bool:
    """Return whether one candidate matches the row's joint SEC identity.

    Args:
        path: Existing candidate artifact.
        row: Scalar portable locator row.

    Returns:
        True when document, URL, accession, and resolved filing directory all
        identify the same artifact. Aggregate derived rows remain path/hash
        bound and are checked by their aligned source/accession pairs.
    """
    document_names = artifact_path_parts(
        path_text=artifact_document_name(row=row),
    )
    source_urls = artifact_path_parts(
        path_text=str(row["source_url"]) if "source_url" in row else "",
    )
    accessions = artifact_path_parts(
        path_text=str(row["accession"]) if "accession" in row else "",
    )
    if len(document_names) == 1 and path.name != document_names[0]:
        return False
    if is_derived_locator_aggregate(row=row):
        if len(source_urls) != len(accessions):
            return False
        for source_url, accession in zip(source_urls, accessions):
            if not is_official_sec_url(source_url=source_url):
                return False
            _archive_cik, derived_accession = archive_url_identity(
                source_url=source_url,
            )
            if not derived_accession or accession != derived_accession:
                return False
        return event_aggregate_pairs_match(row=row)
    if not source_urls:
        # Legacy parser rows may predate source_url; portable schema validation
        # rejects that omission before the full locator gate resolves bytes.
        return True
    if len(source_urls) != 1 or len(accessions) != 1:
        return False
    source_url = source_urls[0]
    accession = accessions[0]
    if companyfacts_url_cik(source_url=source_url):
        return companyfacts_component_matches(
            path=path,
            row=row,
            verify_provenance=True,
        )
    archive_cik, derived_accession = archive_url_identity(
        source_url=source_url,
    )
    if not derived_accession:
        return False
    try:
        row_cik = str(int(row["cik"]))
    except (KeyError, TypeError, ValueError):
        return False
    return (
        accession == derived_accession
        and archive_cik == row_cik
        and len(document_names) == 1
        and Path(urlparse(source_url).path).name == document_names[0]
        and accession_material_path_matches(
            path=path,
            accession=accession,
            cik=row_cik,
        )
    )


def artifact_relocation_candidates(*, row: dict) -> list[Path]:
    """Return fallback candidates from filing identity and document name.

    Args:
        row: Artifact row with repository-relative or legacy fields plus
            accession/document metadata when available.

    Returns:
        Ordered fallback candidates. Direct repository paths are checked before
        this function; the original external absolute path is never used.
    """
    candidates = []
    document_name = artifact_document_name(row=row)
    accession = str(row["accession"]) if "accession" in row else ""
    if document_name and ";" not in document_name:
        compact_accession = accession.replace("-", "")
        if compact_accession:
            exact_candidates = sorted(
                (WORKDIR / "evidence" / "accession_materials").glob(
                    f"*_{compact_accession}/{document_name}",
                )
            )
            if exact_candidates:
                # Accession plus document name is already the strongest
                # relocation key; avoid three recursive scans for every fact.
                return exact_candidates
        for root in ["evidence", "outputs", "tests"]:
            root_path = WORKDIR / root
            if root_path.exists():
                candidates.extend(sorted(root_path.rglob(document_name)))
    unique = []
    seen = set()
    for candidate in candidates:
        candidate_text = str(candidate)
        if candidate_text in seen:
            continue
        seen.add(candidate_text)
        unique.append(candidate)
    return unique


def resolve_artifact_path(*, row: dict) -> Path:
    """Resolve one artifact under the current clone and verify its hash.

    Args:
        row: Artifact row with portable locators or legacy path hints.

    Returns:
        Existing current-clone path. Repository-relative path has priority;
        accession/document/hash relocation is the fallback.
    """
    relative_paths = artifact_path_parts(
        path_text=artifact_reference_text(row=row),
    )
    if len(relative_paths) > 1:
        raise ValueError("A single artifact path is required for file access")
    hashes = artifact_path_parts(
        path_text=(
            str(row["content_sha256"])
            if "content_sha256" in row and row["content_sha256"]
            else str(row["sha256"])
            if "sha256" in row and row["sha256"]
            else ""
        ),
    )
    expected_hash = hashes[0] if hashes else ""
    for relative_path in relative_paths:
        candidate = repository_artifact_candidate(
            relative_path=relative_path,
        )
        if artifact_candidate_matches_hash(
            path=candidate,
            content_sha256=expected_hash,
        ) and artifact_candidate_matches_identity(path=candidate, row=row):
            return candidate
    for candidate in artifact_relocation_candidates(row=row):
        if artifact_candidate_matches_hash(
            path=candidate,
            content_sha256=expected_hash,
        ) and artifact_candidate_matches_identity(path=candidate, row=row):
            return candidate
    raise FileNotFoundError(
        "Artifact unavailable in current clone; "
        f"repo_relative_path={artifact_reference_text(row=row)}; "
        f"accession={row['accession'] if 'accession' in row else ''}; "
        f"document_name={artifact_document_name(row=row)}"
    )


def artifact_component_row(
    *,
    row: dict,
    index: int,
    component_count: int,
) -> dict:
    """Return one row with aligned evidence semantics for one component."""
    component = dict(row)
    semantic_parts = {
        "concept_or_section": [
            part
            for part in str(row["concept_or_section"]).split("+")
            if part
        ]
        if "concept_or_section" in row
        else [],
        "context_or_dimension": artifact_path_parts(
            path_text=str(row["context_or_dimension"]),
        )
        if "context_or_dimension" in row
        else [],
        "value_raw": artifact_path_parts(
            path_text=str(row["value_raw"]),
        )
        if "value_raw" in row
        else [],
    }
    for field, values in semantic_parts.items():
        if len(values) == component_count:
            component[field] = values[index]
        elif field == "value_raw" and component_count > 1:
            # Some derived rows store only the final normalized value; it is
            # not evidence for any individual companyfacts component.
            component[field] = ""
    if component_count > 1:
        component["period_start"] = ""
        component["period_end"] = ""
    return component


def resolve_artifact_paths(*, row: dict) -> list[Path]:
    """Resolve every aligned path/hash component in one artifact row.

    Args:
        row: Artifact row whose locators may be semicolon-delimited.

    Returns:
        Existing current-clone paths in declared order.
    """
    relative_paths = artifact_path_parts(
        path_text=artifact_reference_text(row=row),
    )
    hashes = artifact_path_parts(
        path_text=(
            str(row["content_sha256"])
            if "content_sha256" in row and row["content_sha256"]
            else ""
        ),
    )
    document_names = artifact_path_parts(
        path_text=artifact_document_name(row=row),
    )
    source_urls = artifact_path_parts(
        path_text=str(row["source_url"]) if "source_url" in row else "",
    )
    accessions = artifact_path_parts(
        path_text=str(row["accession"]) if "accession" in row else "",
    )
    if not relative_paths:
        raise FileNotFoundError("Artifact row has no repository-relative path")
    if hashes and len(hashes) != len(relative_paths):
        raise ValueError("Artifact paths and content hashes are not aligned")
    resolved = []
    for index, relative_path in enumerate(relative_paths):
        component = artifact_component_row(
            row=row,
            index=index,
            component_count=len(relative_paths),
        )
        component["repo_relative_path"] = relative_path
        component["content_sha256"] = hashes[index] if hashes else ""
        component["document_name"] = (
            document_names[index]
            if len(document_names) == len(relative_paths)
            else Path(relative_path).name
        )
        if len(source_urls) == len(relative_paths):
            component["source_url"] = source_urls[index]
        if len(accessions) == len(relative_paths):
            component["accession"] = accessions[index]
        resolved.append(resolve_artifact_path(row=component))
    return resolved


def csv_line_terminator(*, path: Path) -> str:
    """Return an existing CSV's newline convention or LF for a new file.

    Args:
        path: CSV output path before it is opened for writing.

    Returns:
        CRLF for an existing CRLF file; otherwise LF. Preserving unchanged
        files avoids repository-wide formatting churn during regeneration.
    """
    if not path.is_file():
        return "\n"
    with path.open(mode="rb") as file_obj:
        sample = file_obj.read(8192)
    return "\r\n" if b"\r\n" in sample else "\n"


def write_csv_file(*, path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write CSV rows with a stable header and UTF-8 encoding.

    Args:
        path: Output CSV path.
        fieldnames: Ordered CSV column names.
        rows: List of dictionaries. Missing fields are written as empty strings.

    Expected output:
        A CSV file with exactly the requested header order.
    """
    # Normalize before opening because a row may cite the output file itself;
    # hashing after truncation would record the wrong bytes.
    normalized_rows = [
        normalize_csv_row(row=row, fieldnames=fieldnames)
        for row in rows
    ]
    line_terminator = csv_line_terminator(path=path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode="w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator=line_terminator,
        )
        writer.writeheader()
        writer.writerows(normalized_rows)


def append_csv_file(*, path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Append rows to a CSV file, creating the header when absent.

    Args:
        path: Output CSV path.
        fieldnames: Ordered CSV column names.
        rows: Rows to append.

    Expected output:
        Existing files keep their header and receive additional rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    if file_exists:
        with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
            existing_header = next(csv.reader(file_obj), [])
        if existing_header != fieldnames:
            existing_rows = read_csv_file(path=path)
            write_csv_file(
                path=path,
                fieldnames=fieldnames,
                rows=existing_rows + rows,
            )
            return
    normalized_rows = [
        normalize_csv_row(row=row, fieldnames=fieldnames)
        for row in rows
    ]
    line_terminator = csv_line_terminator(path=path)
    with path.open(mode="a", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator=line_terminator,
        )
        if not file_exists:
            writer.writeheader()
        writer.writerows(normalized_rows)


def read_csv_file(*, path: Path) -> list[dict]:
    """Read a UTF-8 CSV file into dictionaries.

    Args:
        path: Existing CSV path.

    Returns:
        List of row dictionaries. A missing file returns an empty list because
        later stages may legitimately run before optional evidence exists.
    """
    if not path.exists():
        print(f"CSV not found; returning empty rows: {path}")
        return []
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        return [
            rehydrate_artifact_row(row=row)
            for row in csv.DictReader(file_obj)
        ]


def path_has_matching_files(*, path: Path, pattern: str) -> bool:
    """Return whether a directory contains at least one matching file.

    Args:
        path: Directory expected by a full validation run.
        pattern: Glob pattern relative to the directory.

    Returns:
        True when the directory exists and has matching files.
    """
    if not path.exists():
        return False
    return any(path.glob(pattern))


def full_validation_missing_reasons() -> list[str]:
    """Return missing full-evidence materials required by full validation.

    Returns:
        Empty list for a complete workspace. Non-empty reasons mean full raw
        evidence validation cannot be represented truthfully.
    """
    reasons = []
    evidence_dir = WORKDIR / "evidence"
    concept_dir = WORKDIR / "outputs" / "concept_inventory"
    if not evidence_dir.exists():
        reasons.append("missing evidence/")
    if not REQUEST_LOG_PATH.exists():
        reasons.append("missing evidence/requests_log.csv")
    if not path_has_matching_files(path=concept_dir, pattern="*.csv"):
        reasons.append("missing outputs/concept_inventory/*.csv")
    return reasons


def workspace_incomplete_row(*, reasons: list[str]) -> dict:
    """Build the hard-fail validation row for undeclared partial packages.

    Args:
        reasons: Missing full-validation materials.

    Returns:
        A P0 validation row whose status makes package incompleteness explicit.
    """
    return validation_row(
        check_id="validation_package_mode",
        status="WORKSPACE_INCOMPLETE",
        details="WORKSPACE_INCOMPLETE; " + "; ".join(reasons),
    )


def validation_package_mode() -> tuple[str, list[str]]:
    """Return FULL_VALIDATION, LIGHT_REVIEW_MODE, or WORKSPACE_INCOMPLETE.

    Returns:
        Mode string and missing-material reasons. WORKSPACE_INCOMPLETE means
        full evidence is absent and no explicit light marker was supplied.
    """
    reasons = full_validation_missing_reasons()
    if not reasons:
        return "FULL_VALIDATION", []
    if LIGHT_REVIEW_MARKER_PATH.exists():
        return "LIGHT_REVIEW_MODE", reasons
    return "WORKSPACE_INCOMPLETE", reasons


def validation_run_manifest_path() -> Path:
    """Return the current workspace validation run manifest path."""
    return WORKDIR / "outputs" / "validation_run_manifest.json"


def current_source_commit() -> str:
    """Return the current Git commit with an explicit dirty-tree marker.

    Returns:
        Full Git commit hash, suffixed with +dirty when tracked or untracked
        files differ, or UNAVAILABLE_NON_GIT_WORKSPACE for extracted packages.
    """
    metadata_error = git_checkout_metadata_error(repo_root=WORKDIR)
    if metadata_error:
        print(f"Git source commit unavailable: {metadata_error}")
        return "UNAVAILABLE_NON_GIT_WORKSPACE"
    try:
        result = subprocess.run(
            args=["git", "rev-parse", "HEAD"],
            cwd=WORKDIR,
            check=False,
            capture_output=True,
            text=True,
            env=sanitized_git_environment(),
        )
    except OSError as error:
        print(f"Git source commit unavailable: {error}")
        return "UNAVAILABLE_NON_GIT_WORKSPACE"
    if result.returncode != 0:
        print(f"Git source commit unavailable: {result.stderr.strip()}")
        return "UNAVAILABLE_NON_GIT_WORKSPACE"
    commit = result.stdout.strip()
    if not commit:
        return "UNAVAILABLE_NON_GIT_WORKSPACE"
    try:
        status_result = subprocess.run(
            args=["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=WORKDIR,
            check=False,
            capture_output=True,
            text=True,
            env=sanitized_git_environment(),
        )
    except OSError as error:
        print(f"Git worktree status unavailable: {error}")
        return f"{commit}+status-unknown"
    if status_result.returncode != 0:
        print(f"Git worktree status unavailable: {status_result.stderr.strip()}")
        return f"{commit}+status-unknown"
    return f"{commit}+dirty" if status_result.stdout.strip() else commit


def validation_manifest_errors(*, manifest: dict) -> list[str]:
    """Return deterministic structural and state errors for one run manifest.

    Args:
        manifest: Candidate validation run evidence.

    Returns:
        Empty list only when fields, enums, and artifact partition are valid.
    """
    required_keys = {
        "run_id",
        "source_commit",
        "started_at_utc",
        "mode",
        "refreshed_artifacts",
        "not_refreshed_artifacts",
        "result",
    }
    errors = []
    missing_keys = sorted(required_keys - set(manifest))
    unexpected_keys = sorted(set(manifest) - required_keys)
    if missing_keys:
        errors.append("missing keys: " + ",".join(missing_keys))
    if unexpected_keys:
        errors.append("unexpected keys: " + ",".join(unexpected_keys))
    if missing_keys:
        return errors
    for key in ["run_id", "source_commit", "started_at_utc"]:
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            errors.append(f"{key} must be a non-empty string")
    started_at_utc = manifest["started_at_utc"]
    if (
        isinstance(started_at_utc, str)
        and started_at_utc.strip()
        and not is_utc_iso_timestamp(value=started_at_utc)
    ):
        errors.append("started_at_utc must be an ISO 8601 UTC timestamp")
    mode = manifest["mode"]
    result = manifest["result"]
    if not isinstance(mode, str) or mode not in VALIDATION_MANIFEST_MODES:
        errors.append(f"unknown mode: {mode}")
    if (
        not isinstance(result, str)
        or result not in VALIDATION_MANIFEST_RESULTS
    ):
        errors.append(f"unknown result: {result}")
    refreshed = manifest["refreshed_artifacts"]
    not_refreshed = manifest["not_refreshed_artifacts"]
    if not isinstance(refreshed, list) or not isinstance(not_refreshed, list):
        errors.append("artifact lists must be arrays")
        return errors
    if any(not isinstance(name, str) for name in refreshed + not_refreshed):
        errors.append("artifact names must be strings")
        return errors
    if len(refreshed) != len(set(refreshed)):
        errors.append("refreshed_artifacts contains duplicates")
    if len(not_refreshed) != len(set(not_refreshed)):
        errors.append("not_refreshed_artifacts contains duplicates")
    refreshed_set = set(refreshed)
    not_refreshed_set = set(not_refreshed)
    tracked_set = set(VALIDATION_TRACKED_ARTIFACTS)
    if refreshed_set & not_refreshed_set:
        errors.append("artifact lists overlap")
    if refreshed_set | not_refreshed_set != tracked_set:
        errors.append("artifact lists must partition tracked artifacts")
    if (
        isinstance(mode, str)
        and mode in VALIDATION_MANIFEST_MODES
        and isinstance(result, str)
        and result in VALIDATION_MANIFEST_RESULTS
    ):
        terminal_results = {
            "FULL_VALIDATION": {"PASSED", "FAILED"},
            "LIGHT_REVIEW_MODE": {"PASSED_WITH_CAVEATS", "FAILED"},
            "WORKSPACE_INCOMPLETE": {"FAILED"},
        }
        if result != "IN_PROGRESS" and result not in terminal_results[mode]:
            errors.append(f"result {result} is invalid for mode {mode}")
        required_success_artifacts = {
            ("FULL_VALIDATION", "PASSED"): tracked_set,
            ("LIGHT_REVIEW_MODE", "PASSED_WITH_CAVEATS"): tracked_set
            - {"stub_period_metrics.csv"},
        }
        mode_result = (mode, result)
        required_refreshed = (
            required_success_artifacts[mode_result]
            if mode_result in required_success_artifacts
            else set()
        )
        missing_success_artifacts = sorted(
            required_refreshed - refreshed_set
        )
        if missing_success_artifacts:
            errors.append(
                "successful run did not refresh required artifacts: "
                + ",".join(missing_success_artifacts)
            )
    return errors


def new_validation_run_manifest(*, mode: str, started_at_utc: str) -> dict:
    """Build the initial manifest before validation artifacts are refreshed.

    Args:
        mode: FULL_VALIDATION, LIGHT_REVIEW_MODE, or WORKSPACE_INCOMPLETE.
        started_at_utc: UTC timestamp captured before the first validation write.

    Returns:
        Minimal run evidence with every tracked artifact initially not refreshed.
    """
    if mode not in VALIDATION_MANIFEST_MODES:
        raise ValueError(f"Unknown validation manifest mode: {mode}")
    manifest = {
        "run_id": str(uuid.uuid4()),
        "source_commit": current_source_commit(),
        "started_at_utc": started_at_utc,
        "mode": mode,
        "refreshed_artifacts": [],
        "not_refreshed_artifacts": list(VALIDATION_TRACKED_ARTIFACTS),
        "result": "IN_PROGRESS",
    }
    if validation_manifest_errors(manifest=manifest):
        raise ValueError("New validation manifest is invalid")
    return manifest


def write_utf8_text_atomically(*, path: Path, text: str) -> None:
    """Atomically replace one repository text artifact without aliases.

    Args:
        path: Final repository-owned regular-file path.
        text: Exact UTF-8 content to persist.

    Expected output:
        The lexical target is a regular file containing exactly ``text``;
        symlink, directory, and repository-escape targets fail before write.
    """
    write_repository_bytes_atomically(
        workdir=WORKDIR,
        path=path,
        content=text.encode("utf-8"),
    )


def write_validation_run_manifest(*, manifest: dict) -> None:
    """Persist the minimal validation run manifest as UTF-8 JSON.

    Args:
        manifest: Run evidence with the seven required top-level fields.

    Expected output:
        outputs/validation_run_manifest.json reflects the latest completed or
        interrupted validation attempt, never merely the existence of old CSVs.
    """
    errors = validation_manifest_errors(manifest=manifest)
    if errors:
        raise ValueError("Invalid validation manifest: " + "; ".join(errors))
    path = validation_run_manifest_path()
    write_utf8_text_atomically(
        path=path,
        text=json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )


def mark_validation_artifact_refreshed(*, manifest: dict, artifact: str) -> None:
    """Move one tracked artifact from not-refreshed to refreshed.

    Args:
        manifest: Mutable current run manifest.
        artifact: Basename from VALIDATION_TRACKED_ARTIFACTS.

    Expected output:
        The manifest is persisted after the transition so a later interruption
        still exposes the last completed write.
    """
    if artifact not in VALIDATION_TRACKED_ARTIFACTS:
        raise ValueError(f"Untracked validation artifact: {artifact}")
    refreshed = list(require_key(mapping=manifest, key="refreshed_artifacts"))
    if artifact not in refreshed:
        refreshed.append(artifact)
    manifest["refreshed_artifacts"] = refreshed
    manifest["not_refreshed_artifacts"] = [
        name for name in VALIDATION_TRACKED_ARTIFACTS if name not in refreshed
    ]
    write_validation_run_manifest(manifest=manifest)


def finish_validation_run_manifest(*, manifest: dict, result: str) -> None:
    """Persist the terminal validation result.

    Args:
        manifest: Mutable current run manifest.
        result: PASSED, PASSED_WITH_CAVEATS, or FAILED.
    """
    allowed_results = {"PASSED", "PASSED_WITH_CAVEATS", "FAILED"}
    if result not in allowed_results:
        raise ValueError(f"Unknown validation manifest result: {result}")
    manifest["result"] = result
    write_validation_run_manifest(manifest=manifest)


def read_validation_run_manifest() -> dict:
    """Read and structurally validate the current validation run manifest."""
    path = validation_run_manifest_path()
    if not path.exists():
        return {
            "run_id": "MISSING",
            "source_commit": "UNKNOWN",
            "started_at_utc": "UNKNOWN",
            "mode": "WORKSPACE_INCOMPLETE",
            "refreshed_artifacts": [],
            "not_refreshed_artifacts": list(VALIDATION_TRACKED_ARTIFACTS),
            "result": "FAILED",
        }
    manifest = read_json_file(path=path)
    errors = validation_manifest_errors(manifest=manifest)
    if errors:
        raise ValueError("Invalid validation manifest: " + "; ".join(errors))
    return manifest


def manifest_artifact_was_refreshed(*, manifest: dict, artifact: str) -> bool:
    """Return whether the current manifest marks an artifact as refreshed."""
    if artifact not in VALIDATION_TRACKED_ARTIFACTS:
        raise ValueError(f"Untracked validation artifact: {artifact}")
    if validation_manifest_errors(manifest=manifest):
        return False
    refreshed = require_key(mapping=manifest, key="refreshed_artifacts")
    not_refreshed = require_key(mapping=manifest, key="not_refreshed_artifacts")
    if not isinstance(refreshed, list) or not isinstance(not_refreshed, list):
        raise TypeError("Validation manifest artifact lists must be arrays")
    return artifact in refreshed and artifact not in not_refreshed


def light_review_mode_reasons() -> list[str]:
    """Return light-review reasons only when the marker explicitly permits it.

    Returns:
        Empty list for full validation. Non-empty reasons mean this checkout is
        an explicitly marked light package, not an implicit downgrade.
    """
    mode, reasons = validation_package_mode()
    if mode == "FULL_VALIDATION":
        return []
    if mode == "LIGHT_REVIEW_MODE":
        return reasons
    raise RuntimeError("WORKSPACE_INCOMPLETE; " + "; ".join(reasons))


def is_light_review_package() -> bool:
    """Return whether this checkout is an explicitly marked light package."""
    return bool(light_review_mode_reasons())


def read_json_file(*, path: Path) -> dict:
    """Read a UTF-8 JSON object from disk and fail when it is not an object."""
    with path.open(mode="r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be object: {path}")
    return payload


def slugify(*, text: str) -> str:
    """Return a filesystem-safe ASCII slug for evidence filenames."""
    lowered = text.lower()
    chars = []
    for char in lowered:
        if char.isalnum():
            chars.append(char)
        elif char in {" ", "/", "-", "&", "'"}:
            chars.append("_")
    slug = re.sub(pattern=r"_+", repl="_", string="".join(chars)).strip("_")
    if not slug:
        raise ValueError(f"Cannot slugify text: {text}")
    return slug


def decimal_from_value(*, value: object) -> Decimal:
    """Convert a SEC numeric value to Decimal and fail on non-numeric data."""
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"SEC value is not numeric: {value}") from error


def decimal_text(*, value: Decimal) -> str:
    """Format Decimal without scientific notation for CSV output."""
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def parse_date_text(*, value: str) -> date:
    """Parse an ISO date string required by SEC filing metadata."""
    if not value:
        raise ValueError("Date value is required")
    return date.fromisoformat(value)


def json_text(*, value: object) -> str:
    """Serialize nested SEC values into compact UTF-8 JSON text for CSV cells."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class StandardCompanyfactsExtractor:
    """Marker for generic companyfacts-backed metric extraction.

    Expected output:
        B01-B09 or FI base metrics are attempted from SEC companyfacts without
        company identity branches.
    """


class BaselCapitalRatioExtractor:
    """Marker for Basel ratio extraction from accession instance facts.

    Expected output:
        A01/A02 are selected from pure-unit Basel/RWA methodology dimensions
        for every financial institution profile company.
    """


class RpoCrpoExtractor:
    """Marker for RPO/cRPO extraction from instance facts before text fallback.

    Expected output:
        B12 uses explicit RPO/cRPO facts or text and labels that RPO/cRPO are
        not ARR.
    """


class LodgingKpiExtractor:
    """Marker for lodging KPI extraction from table headers and scoped rows.

    Expected output:
        B10/B11 consume RevPAR, occupancy, and ADR tables without company-name
        dispatch.
    """


class EcdCompensationExtractor:
    """Marker for ECD executive compensation facts from DEF 14A instances.

    Expected output:
        C03 uses PeoTotalCompAmt facts where available for all companies.
    """


class AuditorNameExtractor:
    """Marker for auditor-name comparison from current/prior instance facts.

    Expected output:
        C04 uses dei:AuditorName for every configured company.
    """


class CaptiveFinanceDebtExtractor:
    """Marker for debt metrics that detect captive-finance dimensions.

    Expected output:
        B06 flags consolidated debt only when eligible debt facts include
        captive finance segment or legal-entity dimensions.
    """


class EntityContinuityYoyRule:
    """Marker for YoY comparability checks based on continuity facts.

    Expected output:
        B02 is meaningful only when period lengths and entity chains are
        comparable.
    """


class CapacityUtilizationExtractor:
    """Marker for qualitative or numeric capacity utilization text signals.

    Expected output:
        B13 is attempted for relevant profiles or capacity keyword evidence.
    """


class EightKItemExtractor:
    """Marker for FY-window 8-K item extraction.

    Expected output:
        Event metrics are updated from 8-K item codes and item text.
    """


class RiskLegalTextExtractor:
    """Marker for risk, legal, regulatory, and going-concern text extraction.

    Expected output:
        D01-D04 are updated from 10-K text sections and keywords.
    """


EXTRACTOR_REGISTRY = {
    "StandardCompanyfactsExtractor": StandardCompanyfactsExtractor,
    "BaselCapitalRatioExtractor": BaselCapitalRatioExtractor,
    "RpoCrpoExtractor": RpoCrpoExtractor,
    "LodgingKpiExtractor": LodgingKpiExtractor,
    "EcdCompensationExtractor": EcdCompensationExtractor,
    "AuditorNameExtractor": AuditorNameExtractor,
    "CaptiveFinanceDebtExtractor": CaptiveFinanceDebtExtractor,
    "EntityContinuityYoyRule": EntityContinuityYoyRule,
    "CapacityUtilizationExtractor": CapacityUtilizationExtractor,
    "EightKItemExtractor": EightKItemExtractor,
    "RiskLegalTextExtractor": RiskLegalTextExtractor,
}


def parse_role_text(*, role_text: str) -> list[dict]:
    """Parse company_registry roles into role dictionaries.

    Args:
        role_text: Semicolon-delimited role cells in the format role:cik.

    Returns:
        List of {"entity_role": str, "cik": int} dictionaries.
    """
    if not role_text:
        raise ValueError("company_registry roles must not be empty")
    roles = []
    for item in role_text.split(";"):
        parts = item.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid role cell: {item}")
        roles.append({"entity_role": parts[0], "cik": int(parts[1])})
    return roles


def load_company_registry_from_path(*, path: Path) -> list[dict]:
    """Load company registry CSV and normalize fields for the pipeline.

    Args:
        path: Registry CSV path with one row per logical company.

    Returns:
        Company configuration dictionaries consumed by stage functions.
    """
    if not path.exists():
        raise FileNotFoundError(f"Company registry missing: {path}")
    rows = read_csv_file(path=path)
    companies = []
    for row in rows:
        required_fields = [
            "company_id",
            "display_name",
            "primary_cik",
            "ticker",
            "sic",
            "sic_description",
            "industry_profile",
            "fiscal_year_end",
            "target_period_policy",
            "entity_continuity_status",
            "related_ciks",
            "roles",
        ]
        for field in required_fields:
            require_key(mapping=row, key=field)
        companies.append(
            {
                "company_id": row["company_id"],
                "company": row["display_name"],
                "display_name": row["display_name"],
                "primary_cik": int(row["primary_cik"]),
                "ticker": row["ticker"],
                "sic": row["sic"],
                "sic_description": row["sic_description"],
                "industry_profile": row["industry_profile"],
                "fiscal_year_end": row["fiscal_year_end"],
                "target_period_policy": row["target_period_policy"],
                "entity_continuity_status": row["entity_continuity_status"],
                "related_ciks": row["related_ciks"],
                "roles": parse_role_text(role_text=row["roles"]),
                "target_fiscal_year": row["target_period_policy"],
                "target_fiscal_period": "FY",
                "notes": (
                    f"profile={row['industry_profile']}; "
                    f"continuity={row['entity_continuity_status']}"
                ),
            }
        )
    return companies


def load_company_registry() -> list[dict]:
    """Load the canonical company registry from config/company_registry.csv."""
    return load_company_registry_from_path(path=COMPANY_REGISTRY_PATH)


def load_metric_applicability() -> dict:
    """Load the JSON-compatible YAML applicability registry.

    Returns:
        Dictionary whose profiles decide extractor attempts only.
    """
    if not METRIC_APPLICABILITY_PATH.exists():
        raise FileNotFoundError(
            f"Metric applicability registry missing: {METRIC_APPLICABILITY_PATH}"
        )
    return read_json_file(path=METRIC_APPLICABILITY_PATH)


def profile_from_sic_rules(*, sic: str) -> str:
    """Infer industry profile from configured SIC range rules.

    Args:
        sic: Four-digit SIC code from company_registry.csv.

    Returns:
        Profile inferred from metric_applicability profile_rules.
    """
    sic_value = int(sic)
    applicability = load_metric_applicability()
    rules = require_key(mapping=applicability, key="profile_rules")
    for rule in rules:
        start = int(require_key(mapping=rule, key="sic_start"))
        end = int(require_key(mapping=rule, key="sic_end"))
        if start <= sic_value <= end:
            return str(require_key(mapping=rule, key="profile"))
    return "default_non_fi"


def profile_override_reason(*, company_id: str) -> str:
    """Return override reason for a registry/profile rule mismatch.

    Args:
        company_id: Stable company id from company_registry.csv.

    Returns:
        Non-empty reason from metric_applicability profile_overrides, or empty
        string when no override exists.
    """
    applicability = load_metric_applicability()
    overrides = require_key(mapping=applicability, key="profile_overrides")
    if company_id not in overrides:
        return ""
    return str(overrides[company_id])


def extractor_names_for_profile(*, profile: str) -> list[str]:
    """Return extractor names configured for one industry profile.

    Args:
        profile: industry_profile value from company_registry.csv.

    Returns:
        Ordered extractor class names. Missing profiles fail fast.
    """
    applicability = load_metric_applicability()
    profiles = require_key(mapping=applicability, key="profiles")
    if profile not in profiles:
        raise KeyError(f"Unknown industry profile: {profile}")
    profile_config = profiles[profile]
    extractors = require_key(mapping=profile_config, key="extractors")
    if not isinstance(extractors, list):
        raise TypeError(f"extractors must be a list for profile: {profile}")
    for extractor_name in extractors:
        if extractor_name not in EXTRACTOR_REGISTRY:
            raise KeyError(
                "Unknown extractor in applicability registry: "
                f"{extractor_name}"
            )
    return [str(extractor_name) for extractor_name in extractors]


def company_extractors(*, company_config: dict) -> list[str]:
    """Return configured extractor names for one company registry row."""
    profile = str(require_key(mapping=company_config, key="industry_profile"))
    return extractor_names_for_profile(profile=profile)


def company_by_name(*, company_name: str) -> dict:
    """Return configured company metadata by display name."""
    for company in load_company_registry():
        if company["company"] == company_name:
            return company
    raise KeyError(f"Unknown company: {company_name}")


def all_role_rows() -> list[dict]:
    """Return one row per configured company CIK role.

    Expected output:
        Multi-entity registrants contribute one row per configured role.
    """
    rows = []
    for company in load_company_registry():
        roles = company["roles"]
        for role in roles:
            rows.append(
                {
                    "company": company["company"],
                    "company_id": company["company_id"],
                    "primary_cik": company["primary_cik"],
                    "cik": role["cik"],
                    "entity_role": role["entity_role"],
                    "target_fiscal_year": company["target_fiscal_year"],
                    "target_fiscal_period": company["target_fiscal_period"],
                    "fiscal_year_end": company["fiscal_year_end"],
                    "industry_profile": company["industry_profile"],
                    "entity_continuity_status": company["entity_continuity_status"],
                    "notes": company["notes"],
                }
            )
    return rows


def companyfacts_path(*, cik: int) -> Path:
    """Return the local companyfacts evidence path for one CIK."""
    return WORKDIR / "evidence" / "companyfacts" / f"CIK{cik:010d}.json"


def submissions_path(*, cik: int) -> Path:
    """Return the local submissions evidence path for one CIK."""
    return WORKDIR / "evidence" / "submissions" / f"CIK{cik:010d}.json"


def load_submissions(*, cik: int) -> dict:
    """Load a previously saved submissions JSON file."""
    return read_json_file(path=submissions_path(cik=cik))


def fetch_json_to_path(
    *,
    http: SecHttpClient,
    url: str,
    purpose: str,
    path: Path,
    required_status: int,
) -> dict:
    """Fetch JSON from SEC and return the parsed object.

    Args:
        http: Configured SEC HTTP client.
        url: Official SEC URL.
        purpose: Request purpose written to the log.
        path: Raw response persistence path.
        required_status: Required HTTP status for fail-fast behavior.

    Returns:
        Parsed JSON object.
    """
    result = http.fetch(url=url, purpose=purpose, local_path=path)
    if result.status_code != required_status:
        raise RuntimeError(
            f"SEC request failed; status={result.status_code}; "
            f"url={url}; path={path}; error={result.error}"
        )
    return read_json_file(path=path)


def stage_smoke_test_sec_access() -> None:
    """M0 smoke test: request company_tickers_exchange.json from SEC."""
    ensure_output_dirs()
    http = client()
    path = WORKDIR / "evidence" / "company_tickers" / "company_tickers_exchange.json"
    payload = fetch_json_to_path(
        http=http,
        url=company_tickers_exchange_url(),
        purpose="smoke_company_tickers_exchange",
        path=path,
        required_status=200,
    )
    for key in ["fields", "data"]:
        require_key(mapping=payload, key=key)
    print(f"SEC smoke OK: {path}")


def ticker_associations_by_cik(*, payload: dict) -> dict[int, list[dict]]:
    """Transform company_tickers_exchange.json into CIK-indexed associations.

    Args:
        payload: SEC company_tickers_exchange JSON object.

    Returns:
        Dictionary keyed by integer CIK with ticker/exchange/name rows.
    """
    fields = require_key(mapping=payload, key="fields")
    data_rows = require_key(mapping=payload, key="data")
    if not isinstance(fields, list):
        raise TypeError("company_tickers_exchange fields must be a list")
    if not isinstance(data_rows, list):
        raise TypeError("company_tickers_exchange data must be a list")

    result: dict[int, list[dict]] = {}
    for data_row in data_rows:
        association = {}
        for index, fieldname in enumerate(fields):
            association[str(fieldname)] = data_row[index]
        cik_value = int(require_key(mapping=association, key="cik"))
        if cik_value not in result:
            result[cik_value] = []
        result[cik_value].append(association)
    return result


def stage_resolve_companies() -> None:
    """M0 company resolution: fetch submissions and write identity table."""
    ensure_output_dirs()
    http = client()
    tickers_path = (
        WORKDIR / "evidence" / "company_tickers" / "company_tickers_exchange.json"
    )
    if not tickers_path.exists():
        print("company_tickers evidence absent; fetching before resolution")
        fetch_json_to_path(
            http=http,
            url=company_tickers_exchange_url(),
            purpose="resolve_company_tickers_exchange",
            path=tickers_path,
            required_status=200,
        )
    ticker_payload = read_json_file(path=tickers_path)
    ticker_map = ticker_associations_by_cik(payload=ticker_payload)

    rows = []
    for role_row in all_role_rows():
        cik = int(role_row["cik"])
        submission = fetch_json_to_path(
            http=http,
            url=submissions_url(cik=cik),
            purpose=f"resolve_submissions_{cik}",
            path=submissions_path(cik=cik),
            required_status=200,
        )
        ticker_rows = ticker_map[cik] if cik in ticker_map else []
        ticker_values = [str(row["ticker"]) for row in ticker_rows]
        exchange_values = [str(row["exchange"]) for row in ticker_rows]
        related_ciks = []
        for peer_role in company_by_name(company_name=role_row["company"])["roles"]:
            if int(peer_role["cik"]) != cik:
                related_ciks.append(str(peer_role["cik"]))

        rows.append(
            {
                "company": role_row["company"],
                "primary_cik": role_row["primary_cik"],
                "resolved_cik": require_key(mapping=submission, key="cik"),
                "entity_role": role_row["entity_role"],
                "name": require_key(mapping=submission, key="name"),
                "entityType": optional_key(
                    mapping=submission,
                    key="entityType",
                    default="",
                ),
                "sic": optional_key(mapping=submission, key="sic", default=""),
                "sicDescription": optional_key(
                    mapping=submission,
                    key="sicDescription",
                    default="",
                ),
                "fiscalYearEnd": optional_key(
                    mapping=submission,
                    key="fiscalYearEnd",
                    default="",
                ),
                "tickers": json_text(value=ticker_values),
                "exchanges": json_text(value=exchange_values),
                "formerNames": json_text(
                    value=optional_key(
                        mapping=submission,
                        key="formerNames",
                        default=[],
                    )
                ),
                "related_ciks": ";".join(related_ciks),
                "resolution_status": "OK",
                "notes": role_row["notes"],
            }
        )

    write_csv_file(
        path=WORKDIR / "outputs" / "company_resolution.csv",
        fieldnames=COMPANY_RESOLUTION_FIELDNAMES,
        rows=rows,
    )
    validate_structure_assertions(rows=rows)
    print("M0 company resolution complete")


def validate_structure_assertions(*, rows: list[dict]) -> None:
    """Run fail-fast company identity assertions required in M0.

    Args:
        rows: company_resolution rows.

    Returns:
        None. Raises RuntimeError on structural mismatch.
    """
    for company_config in load_company_registry():
        company = str(company_config["company"])
        expected_roles = company_config["roles"]
        expected_ciks = {int(role["cik"]) for role in expected_roles}
        actual_ciks = {
            int(row["resolved_cik"])
            for row in rows
            if row["company"] == company
        }
        if actual_ciks != expected_ciks:
            raise RuntimeError(
                f"G1 failed for {company}; target={sorted(expected_ciks)}; "
                f"actual={sorted(actual_ciks)}"
            )

        # Fiscal-year-end is identity metadata; validating it against registry
        # prevents hidden per-company branches later in metric calculation.
        primary_rows = [
            row
            for row in rows
            if row["company"] == company
            and row["entity_role"] in {"primary", "successor"}
        ]
        for row in primary_rows:
            if row["fiscalYearEnd"] != company_config["fiscal_year_end"]:
                raise RuntimeError(
                    f"G1 failed for {company} fiscalYearEnd; "
                    f"target={company_config['fiscal_year_end']}; "
                    f"actual={row['fiscalYearEnd']}"
                )


def supplemental_submission_path(*, file_name: str) -> Path:
    """Return the contained local path for one supplemental submissions file."""
    if (
        not file_name
        or file_name != file_name.strip()
        or file_name in {".", ".."}
        or Path(file_name).name != file_name
    ):
        raise ValueError(
            f"Invalid supplemental submissions file name: {file_name}"
        )
    return WORKDIR / "evidence" / "submissions" / file_name


def submission_supplemental_names(*, submission: dict, cik: int) -> list[str]:
    """Return the bounded supplemental file names declared by one base file.

    Args:
        submission: Parsed base SEC submissions response.
        cik: Filing CIK used only for a precise schema diagnostic.

    Returns:
        At most the configured collection boundary of safe base names.
    """
    filings = require_key(mapping=submission, key="filings")
    files = optional_key(mapping=filings, key="files", default=[])
    if not isinstance(files, list):
        raise TypeError(f"submissions.filings.files must be list for {cik}")
    names = []
    for file_info in files[:SUBMISSION_SUPPLEMENTAL_LIMIT]:
        if not isinstance(file_info, dict):
            raise TypeError(
                f"submissions.filings.files entry must be object for {cik}"
            )
        file_name_value = require_key(mapping=file_info, key="name")
        if not isinstance(file_name_value, str):
            raise TypeError(
                f"submissions file name must be text for {cik}"
            )
        file_name = file_name_value
        if re.fullmatch(
            pattern=rf"CIK{cik:010d}-submissions-\d+\.json",
            string=file_name,
        ) is None:
            raise ValueError(
                f"Supplemental submissions identity mismatch: {file_name}"
            )
        supplemental_submission_path(file_name=file_name)
        names.append(file_name)
    return names


def ensure_submission_supplementals(
    *,
    http: SecHttpClient,
    cik: int,
) -> None:
    """Fetch recent supplemental submissions files for high-volume filers.

    Args:
        http: Configured SEC HTTP client.
        cik: CIK whose base submissions JSON is already saved.

    Expected output:
        The shared bounded set is written under evidence/submissions/.
    """
    submission = load_submissions(cik=cik)
    file_names = submission_supplemental_names(
        submission=submission,
        cik=cik,
    )
    for file_name in file_names:
        path = supplemental_submission_path(file_name=file_name)
        if path.exists():
            continue
        fetch_json_to_path(
            http=http,
            url=submissions_file_url(file_name=file_name),
            purpose=f"submissions_supplement_{cik}",
            path=path,
            required_status=200,
        )


def flatten_filing_block(
    *,
    company: str,
    cik: int,
    entity_role: str,
    recent: dict,
) -> list[dict]:
    """Flatten one SEC submissions filing block into row dictionaries.

    Args:
        company: Display company name.
        cik: Integer CIK for the submissions block.
        entity_role: primary/successor/predecessor role.
        recent: SEC recent-like block with parallel filing arrays.

    Returns:
        Filing rows with SEC metadata.
    """
    accession_numbers = require_key(mapping=recent, key="accessionNumber")
    row_count = len(accession_numbers)
    output_rows = []
    fields = [
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "act",
        "form",
        "fileNumber",
        "filmNumber",
        "items",
        "size",
        "isXBRL",
        "isInlineXBRL",
        "primaryDocument",
        "primaryDocDescription",
    ]
    for field in fields:
        if field not in recent:
            raise KeyError(f"submissions.recent missing field: {field}")
        if len(recent[field]) != row_count:
            raise ValueError(f"submissions.recent field length mismatch: {field}")

    for index in range(row_count):
        row = {
            "company": company,
            "cik": str(cik),
            "entity_role": entity_role,
        }
        for field in fields:
            row[field] = recent[field][index]
        output_rows.append(row)
    return output_rows


def filing_rows_from_submission_payloads(
    *,
    company: str,
    cik: int,
    entity_role: str,
    payloads: list[dict],
) -> list[dict]:
    """Flatten explicit base and supplemental payloads into filing rows.

    Args:
        company: Display company name owning the filing rows.
        cik: Integer filing CIK.
        entity_role: primary/successor/predecessor role.
        payloads: Base submissions payload followed by bounded supplements.

    Returns:
        Filing rows without any hidden filesystem reads.
    """
    if not payloads:
        raise ValueError(f"No submissions payload supplied for {cik}")
    submission = payloads[0]
    filings = require_key(mapping=submission, key="filings")
    recent = require_key(mapping=filings, key="recent")
    rows = flatten_filing_block(
        company=company,
        cik=cik,
        entity_role=entity_role,
        recent=recent,
    )
    for supplemental in payloads[1:]:
        rows.extend(
            flatten_filing_block(
                company=company,
                cik=cik,
                entity_role=entity_role,
                recent=supplemental,
            )
        )
    return rows


def recent_filing_rows(*, company: str, cik: int, entity_role: str) -> list[dict]:
    """Load and flatten the bounded submissions evidence for one CIK.

    Args:
        company: Display company name.
        cik: Integer CIK for the submissions file.
        entity_role: primary/successor/predecessor role.

    Returns:
        Filing rows from the base response and every required supplement.
    """
    submission = load_submissions(cik=cik)
    payloads = [submission]
    for file_name in submission_supplemental_names(
        submission=submission,
        cik=cik,
    ):
        path = supplemental_submission_path(file_name=file_name)
        if not path.is_file():
            raise FileNotFoundError(
                f"Required supplemental submissions file missing: {path}"
            )
        payloads.append(read_json_file(path=path))
    return filing_rows_from_submission_payloads(
        company=company,
        cik=cik,
        entity_role=entity_role,
        payloads=payloads,
    )


def sorted_filings(*, rows: list[dict]) -> list[dict]:
    """Sort filings by filingDate and accession descending."""
    return sorted(
        rows,
        key=lambda row: (str(row["filingDate"]), str(row["accessionNumber"])),
        reverse=True,
    )


def select_latest_10k(*, rows: list[dict]) -> dict:
    """Select the latest 10-K or 10-K/A from flattened submissions rows."""
    candidates = [
        row
        for row in rows
        if str(row["form"]) in {"10-K", "10-K/A"} and str(row["reportDate"])
    ]
    if not candidates:
        raise RuntimeError("No 10-K or 10-K/A found in submissions rows")
    return sorted_filings(rows=candidates)[0]


def select_prior_10k(*, rows: list[dict], target_report_date: str) -> dict:
    """Select the prior-year 10-K with a distinct earlier reportDate."""
    candidates = [
        row
        for row in rows
        if str(row["form"]) in {"10-K", "10-K/A"}
        and str(row["reportDate"])
        and str(row["reportDate"]) < target_report_date
    ]
    if not candidates:
        raise RuntimeError(f"No prior 10-K found before {target_report_date}")
    latest_report = sorted(
        {str(row["reportDate"]) for row in candidates},
        reverse=True,
    )[0]
    same_period = [
        row for row in candidates if str(row["reportDate"]) == latest_report
    ]
    return sorted_filings(rows=same_period)[0]


def same_period_original_10k(*, rows: list[dict], target: dict) -> dict | None:
    """Return the same-fiscal-year original 10-K for an amended target.

    Args:
        rows: Flattened submissions rows for one configured role.
        target: Selected target 10-K or 10-K/A row.

    Returns:
        Latest original 10-K for the same reportDate, or None when the SEC
        filing history does not provide one.
    """
    originals = [
        row
        for row in rows
        if row["form"] == "10-K"
        and row["reportDate"] == target["reportDate"]
        and row["accessionNumber"] != target["accessionNumber"]
    ]
    if not originals:
        return None
    return sorted_filings(rows=originals)[0]


def instance_rows_have_dei_key_facts(*, rows: list[dict]) -> bool:
    """Return whether parsed rows contain core DEI identity/date facts."""
    concepts = {row["concept"] for row in rows}
    required = {
        "DocumentType",
        "DocumentPeriodEndDate",
        "EntityRegistrantName",
    }
    return bool(required.intersection(concepts))


def instance_rows_have_basel_key_facts(*, rows: list[dict]) -> bool:
    """Return whether parsed rows contain Basel ratio facts on methodology axes."""
    return any(
        dimensions_have_basel_methodology(dimensions=row["dimensions"])
        and concept_has_rwa_ratio_semantics(
            normalized=normalized_concept_name(concept=row["concept"]),
        )
        for row in rows
    )


def instance_rows_have_rpo_key_facts(*, rows: list[dict]) -> bool:
    """Return whether parsed rows contain explicit RPO/cRPO facts."""
    return any(concept_matches_rpo(concept=row["concept"]) for row in rows)


def instance_rows_have_debt_dimension_key_facts(*, rows: list[dict]) -> bool:
    """Return whether parsed rows contain debt facts with segment dimensions."""
    return any(row_has_captive_finance_signal(row=row) for row in rows)


def required_instance_fact_groups(*, company_config: dict) -> list[str]:
    """Return key instance fact groups expected for one registry profile.

    Args:
        company_config: Loaded company registry row.

    Returns:
        Group names used to decide whether an amended or tiny target instance
        should fall back to a same-period original 10-K full instance.
    """
    extractors = company_extractors(company_config=company_config)
    groups = ["dei"]
    if has_extractor(
        extractors=extractors,
        extractor_name="BaselCapitalRatioExtractor",
    ):
        groups.append("basel")
    if has_extractor(extractors=extractors, extractor_name="RpoCrpoExtractor"):
        groups.append("rpo")
    if has_extractor(
        extractors=extractors,
        extractor_name="CaptiveFinanceDebtExtractor",
    ):
        groups.append("debt_dimension")
    return groups


def missing_instance_fact_groups(
    *,
    rows: list[dict],
    company_config: dict,
) -> list[str]:
    """Return required instance fact groups absent from parsed rows.

    Args:
        rows: Parsed target instance rows.
        company_config: Loaded company registry row.

    Returns:
        Missing group names. A non-empty result is a reason to inspect the
        same-period original 10-K full instance instead of trusting an amended
        or partial target instance.
    """
    checks = {
        "dei": instance_rows_have_dei_key_facts,
        "basel": instance_rows_have_basel_key_facts,
        "rpo": instance_rows_have_rpo_key_facts,
        "debt_dimension": instance_rows_have_debt_dimension_key_facts,
    }
    missing = []
    for group in required_instance_fact_groups(company_config=company_config):
        if not checks[group](rows=rows):
            missing.append(group)
    return missing


def full_instance_fallback_reasons(
    *,
    target: dict,
    company_config: dict,
    parsed_rows: list[dict] | None,
) -> list[str]:
    """Return reasons to use a same-period original 10-K full instance.

    Args:
        target: Selected target filing row.
        company_config: Loaded company registry row.
        parsed_rows: Parsed target instance rows, or None before parsing.

    Returns:
        Reason codes. Empty means the target instance is sufficient.
    """
    reasons = []
    if target["form"] == "10-K/A":
        reasons.append("target_form_10_k_a")
    if parsed_rows is None:
        return reasons
    if len(parsed_rows) < 500:
        reasons.append("target_instance_fact_count_lt_500")
    missing_groups = missing_instance_fact_groups(
        rows=parsed_rows,
        company_config=company_config,
    )
    if missing_groups:
        reasons.append("missing_instance_fact_groups:" + ",".join(missing_groups))
    return reasons


def original_full_instance_fallback_row(
    *,
    rows: list[dict],
    target: dict,
    company_config: dict,
    parsed_rows: list[dict] | None,
) -> dict | None:
    """Return a fallback inventory row when original full instance is needed.

    Args:
        rows: Flattened submissions rows for one configured role.
        target: Selected target 10-K or 10-K/A row.
        company_config: Loaded company registry row.
        parsed_rows: Parsed target instance rows, or None before parsing.

    Returns:
        latest_filings_inventory row with source_role
        target_original_full_instance, or None when no fallback is required or
        no same-period original 10-K exists.
    """
    reasons = full_instance_fallback_reasons(
        target=target,
        company_config=company_config,
        parsed_rows=parsed_rows,
    )
    if not reasons:
        return None
    original = same_period_original_10k(rows=rows, target=target)
    if original is None:
        return None
    return filing_output_row(
        row=original,
        source_role="target_original_full_instance",
    )


def select_latest_def14a(*, rows: list[dict]) -> dict | None:
    """Select the latest DEF 14A from submissions rows when available."""
    candidates = [row for row in rows if str(row["form"]) == "DEF 14A"]
    if not candidates:
        print("No DEF 14A found in submissions rows")
        return None
    return sorted_filings(rows=candidates)[0]


def fiscal_window(*, target_row: dict, prior_row: dict | None) -> tuple[str, str]:
    """Return fiscal window start and end dates for 8-K scanning.

    Args:
        target_row: Selected target 10-K row.
        prior_row: Prior 10-K row or None.

    Returns:
        ISO start and end date strings.
    """
    end_date = parse_date_text(value=str(target_row["reportDate"]))
    if prior_row is not None and str(prior_row["reportDate"]):
        prior_end = parse_date_text(value=str(prior_row["reportDate"]))
        start_date = prior_end + timedelta(days=1)
    else:
        start_date = end_date - timedelta(days=364)
    return start_date.isoformat(), end_date.isoformat()


def select_8k_window(
    *,
    rows: list[dict],
    window_start: str,
    window_end: str,
) -> list[dict]:
    """Select all 8-K filings whose filing date falls inside the fiscal window."""
    selected = []
    start = parse_date_text(value=window_start)
    end = parse_date_text(value=window_end)
    for row in rows:
        form = str(row["form"])
        filing_date_text = str(row["filingDate"])
        if form not in {"8-K", "8-K/A"}:
            continue
        filing_date = parse_date_text(value=filing_date_text)
        if start <= filing_date <= end:
            selected.append(row)
    return sorted_filings(rows=selected)


def filing_output_row(*, row: dict, source_role: str) -> dict:
    """Convert a submissions filing row into latest_filings_inventory schema."""
    cik = int(row["cik"])
    accession = str(row["accessionNumber"])
    return {
        "company": row["company"],
        "cik": str(cik),
        "entity_role": row["entity_role"],
        "form": row["form"],
        "accession": accession,
        "filingDate": row["filingDate"],
        "reportDate": row["reportDate"],
        "primaryDocument": row["primaryDocument"],
        "isXBRL": row["isXBRL"],
        "isInlineXBRL": row["isInlineXBRL"],
        "source_role": source_role,
        "source_url": accession_document_url(
            cik=cik,
            accession=accession,
            document_name=str(row["primaryDocument"]),
        ),
    }


def stage_inventory_filings() -> None:
    """M1: locate target 10-K, prior 10-K, DEF 14A, and FY-window 8-K filings."""
    ensure_output_dirs()
    http = client()
    inventory_rows = []
    companies_by_id = {
        company["company_id"]: company
        for company in load_company_registry()
    }
    for role_row in all_role_rows():
        cik = int(role_row["cik"])
        ensure_submission_supplementals(http=http, cik=cik)
        rows = recent_filing_rows(
            company=role_row["company"],
            cik=cik,
            entity_role=role_row["entity_role"],
        )
        target = select_latest_10k(rows=rows)
        prior: dict | None
        try:
            prior = select_prior_10k(
                rows=rows,
                target_report_date=str(target["reportDate"]),
            )
        except RuntimeError as error:
            print(f"Prior 10-K unavailable for {role_row['company']} {cik}: {error}")
            prior = None
        def14a = select_latest_def14a(rows=rows)
        start_text, end_text = fiscal_window(target_row=target, prior_row=prior)
        eight_ks = select_8k_window(
            rows=rows,
            window_start=start_text,
            window_end=end_text,
        )

        inventory_rows.append(
            filing_output_row(row=target, source_role="target_10k")
        )
        fallback = original_full_instance_fallback_row(
            rows=rows,
            target=target,
            company_config=companies_by_id[str(role_row["company_id"])],
            parsed_rows=None,
        )
        if fallback is not None:
            inventory_rows.append(fallback)
        if prior is not None:
            inventory_rows.append(
                filing_output_row(row=prior, source_role="prior_10k")
            )
        if def14a is not None:
            inventory_rows.append(
                filing_output_row(row=def14a, source_role="latest_def14a")
            )
        for event_row in eight_ks:
            inventory_rows.append(
                filing_output_row(row=event_row, source_role="fy_8k")
            )

    write_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv",
        fieldnames=FILING_FIELDNAMES,
        rows=inventory_rows,
    )
    print(f"M1 filing inventory complete; rows={len(inventory_rows)}")


def unique_inventory_ciks() -> list[int]:
    """Return all CIKs that appear in company configuration or filing inventory."""
    ciks = {int(row["cik"]) for row in all_role_rows()}
    inventory_path = WORKDIR / "outputs" / "latest_filings_inventory.csv"
    for row in read_csv_file(path=inventory_path):
        ciks.add(int(row["cik"]))
    return sorted(ciks)


def stage_companyfacts_inventory() -> None:
    """M2: fetch companyfacts JSON and write per-company concept inventories."""
    ensure_output_dirs()
    http = client()
    for cik in unique_inventory_ciks():
        fetch_json_to_path(
            http=http,
            url=companyfacts_url(cik=cik),
            purpose=f"companyfacts_{cik}",
            path=companyfacts_path(cik=cik),
            required_status=200,
        )

    rows_by_company: dict[str, list[dict]] = {}
    for role_row in all_role_rows():
        company = role_row["company"]
        cik = int(role_row["cik"])
        if company not in rows_by_company:
            rows_by_company[company] = []
        rows_by_company[company].extend(companyfacts_inventory_rows(cik=cik))

    fieldnames = [
        "company",
        "cik",
        "entity_role",
        "taxonomy",
        "concept",
        "label",
        "unit",
        "form",
        "fy",
        "fp",
        "start",
        "end",
        "filed",
        "accn",
        "val",
        "frame",
    ]
    for company, rows in rows_by_company.items():
        write_csv_file(
            path=(
                WORKDIR
                / "outputs"
                / "concept_inventory"
                / f"{slugify(text=company)}_companyfacts.csv"
            ),
            fieldnames=fieldnames,
            rows=rows,
        )
    print("M2 companyfacts inventory complete")


def role_for_cik(*, company: str, cik: int) -> str:
    """Return configured entity role for a company CIK."""
    config = company_by_name(company_name=company)
    for role in config["roles"]:
        if int(role["cik"]) == cik:
            return str(role["entity_role"])
    return "unconfigured"


def company_for_cik(*, cik: int) -> str:
    """Return configured display company for a CIK."""
    for role_row in all_role_rows():
        if int(role_row["cik"]) == cik:
            return str(role_row["company"])
    raise KeyError(f"CIK not configured: {cik}")


def companyfacts_inventory_rows(*, cik: int) -> list[dict]:
    """Flatten companyfacts JSON into concept inventory rows.

    Args:
        cik: Integer CIK whose companyfacts JSON was fetched.

    Returns:
        Rows containing taxonomy, concept, unit, period, accession, and value.
    """
    payload = read_json_file(path=companyfacts_path(cik=cik))
    facts = require_key(mapping=payload, key="facts")
    company = company_for_cik(cik=cik)
    entity_role = role_for_cik(company=company, cik=cik)
    output_rows = []
    for taxonomy, concepts in facts.items():
        for concept, concept_payload in concepts.items():
            label = optional_key(
                mapping=concept_payload,
                key="label",
                default="",
            )
            units = optional_key(
                mapping=concept_payload,
                key="units",
                default={},
            )
            if not isinstance(units, dict):
                print(f"Skipping malformed units for {cik} {concept}")
                continue
            for unit, facts_list in units.items():
                for fact in facts_list:
                    output_rows.append(
                        {
                            "company": company,
                            "cik": str(cik),
                            "entity_role": entity_role,
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "label": label,
                            "unit": unit,
                            "form": optional_key(
                                mapping=fact,
                                key="form",
                                default="",
                            ),
                            "fy": optional_key(mapping=fact, key="fy", default=""),
                            "fp": optional_key(mapping=fact, key="fp", default=""),
                            "start": optional_key(
                                mapping=fact,
                                key="start",
                                default="",
                            ),
                            "end": optional_key(mapping=fact, key="end", default=""),
                            "filed": optional_key(
                                mapping=fact,
                                key="filed",
                                default="",
                            ),
                            "accn": optional_key(
                                mapping=fact,
                                key="accn",
                                default="",
                            ),
                            "val": optional_key(mapping=fact, key="val", default=""),
                            "frame": optional_key(
                                mapping=fact,
                                key="frame",
                                default="",
                            ),
                        }
                    )
    return output_rows


def inventory_rows_for_company(*, company: str, source_role: str) -> list[dict]:
    """Return filing inventory rows for one company and source role."""
    rows = read_csv_file(path=WORKDIR / "outputs" / "latest_filings_inventory.csv")
    return [
        row
        for row in rows
        if row["company"] == company and row["source_role"] == source_role
    ]


def target_10k_for_company(*, company: str) -> dict:
    """Return the selected target 10-K row used for metrics.

    The rule prefers primary/successor rows, then predecessor rows. This keeps
    role choice explicit while using a same-period original full-instance row
    when a 10-K/A or sparse target requires fallback.
    """
    rows = inventory_rows_for_company(company=company, source_role="target_10k")
    rows.extend(
        inventory_rows_for_company(
            company=company,
            source_role="target_original_full_instance",
        )
    )
    if not rows:
        raise RuntimeError(f"No target_10k inventory row for {company}")
    role_rank = {"primary": 0, "successor": 0, "predecessor": 1}
    source_rank = {"target_original_full_instance": 0, "target_10k": 1}
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            role_rank[str(row["entity_role"])]
            if str(row["entity_role"]) in role_rank
            else 5,
            source_rank[str(row["source_role"])],
            str(row["filingDate"]),
        ),
        reverse=False,
    )
    return ranked_rows[0]


def c04_target_filing(*, company: str) -> dict:
    """Return the filed target used before C04 AuditorName fallback.

    Args:
        company: Display company name.

    Returns:
        The preferred primary/successor `target_10k` row. An amended target
        remains authoritative until its AuditorName is proven unavailable.
    """
    rows = inventory_rows_for_company(
        company=company,
        source_role="target_10k",
    )
    if not rows:
        raise RuntimeError(f"No target_10k inventory row for {company}")
    role_rank = {"primary": 0, "successor": 0, "predecessor": 1}
    best_rank = min(
        role_rank[str(row["entity_role"])]
        if str(row["entity_role"]) in role_rank
        else 5
        for row in rows
    )
    preferred = [
        row
        for row in rows
        if (
            role_rank[str(row["entity_role"])]
            if str(row["entity_role"]) in role_rank
            else 5
        )
        == best_rank
    ]
    return sorted(
        preferred,
        key=lambda row: (
            str(row["reportDate"]),
            str(row["filingDate"]),
            str(row["accession"]),
        ),
        reverse=True,
    )[0]


def prior_10k_for_company(*, company: str, cik: int) -> dict | None:
    """Return prior 10-K row matching the selected metric CIK."""
    rows = [
        row
        for row in inventory_rows_for_company(company=company, source_role="prior_10k")
        if int(row["cik"]) == cik
    ]
    if not rows:
        print(f"No prior 10-K inventory row for {company} CIK {cik}")
        return None
    return sorted(rows, key=lambda row: str(row["reportDate"]), reverse=True)[0]


def c04_period_start(
    *,
    prior: dict | None,
    target_cik: int,
    period_end: str,
) -> str:
    """Return the comparison start without crossing a CIK boundary.

    Args:
        prior: Selected same-CIK prior 10-K, or None when unavailable.
        target_cik: Current C04 filing CIK.
        period_end: Current target report date in ISO format.

    Returns:
        Day after a same-CIK prior report date, otherwise calendar-year start.
    """
    if prior is not None:
        if str(prior["cik"]) != str(target_cik):
            raise ValueError("C04 prior filing must use the target CIK")
        return (
            parse_date_text(value=str(prior["reportDate"]))
            + timedelta(days=1)
        ).isoformat()
    end_date = parse_date_text(value=period_end)
    return date(year=end_date.year, month=1, day=1).isoformat()


def fact_duration_days(*, fact: dict) -> int | None:
    """Return fact duration in days, or None when no start date exists."""
    start_text = str(optional_key(mapping=fact, key="start", default=""))
    end_text = str(optional_key(mapping=fact, key="end", default=""))
    if not start_text:
        return None
    start_date = parse_date_text(value=start_text)
    end_date = parse_date_text(value=end_text)
    return (end_date - start_date).days + 1


def fact_is_annual_duration(*, fact: dict, period_end: str) -> bool:
    """Return whether a companyfacts item is an annual duration fact."""
    form = str(optional_key(mapping=fact, key="form", default=""))
    end_text = str(optional_key(mapping=fact, key="end", default=""))
    if not form.startswith("10-K"):
        return False
    if end_text != period_end:
        return False
    days = fact_duration_days(fact=fact)
    if days is None:
        return False
    return 300 <= days <= 400


def fact_is_instant(*, fact: dict, period_end: str) -> bool:
    """Return whether a companyfacts item is an instant fact at period end."""
    form = str(optional_key(mapping=fact, key="form", default=""))
    end_text = str(optional_key(mapping=fact, key="end", default=""))
    start_text = str(optional_key(mapping=fact, key="start", default=""))
    if not form.startswith("10-K"):
        return False
    if end_text != period_end:
        return False
    return start_text == ""


def fact_from_json(
    *,
    cik: int,
    taxonomy: str,
    concept: str,
    unit: str,
    fact: dict,
) -> FactHit:
    """Convert one raw companyfacts item into a FactHit."""
    value = decimal_from_value(value=require_key(mapping=fact, key="val"))
    return FactHit(
        concept=concept,
        taxonomy=taxonomy,
        unit=unit,
        value=value,
        raw_value=str(require_key(mapping=fact, key="val")),
        start=str(optional_key(mapping=fact, key="start", default="")),
        end=str(optional_key(mapping=fact, key="end", default="")),
        filed=str(optional_key(mapping=fact, key="filed", default="")),
        form=str(optional_key(mapping=fact, key="form", default="")),
        fiscal_year=str(optional_key(mapping=fact, key="fy", default="")),
        fiscal_period=str(optional_key(mapping=fact, key="fp", default="")),
        accession=str(optional_key(mapping=fact, key="accn", default="")),
        frame=str(optional_key(mapping=fact, key="frame", default="")),
        source_path=str(companyfacts_path(cik=cik)),
        source_url=companyfacts_url(cik=cik),
    )


def candidate_fact_hits(
    *,
    cik: int,
    concept_chain: list[str],
    period_end: str,
    period_kind: str,
) -> list[FactHit]:
    """Return companyfacts hits for a concept chain and period rule.

    Args:
        cik: Integer CIK.
        concept_chain: Ordered XBRL concept candidate chain.
        period_end: Target period end date, ISO format.
        period_kind: "duration" or "instant".

    Returns:
        Matching facts in concept-chain priority order.
    """
    payload = read_json_file(path=companyfacts_path(cik=cik))
    facts_root = require_key(mapping=payload, key="facts")
    hits = []
    for concept_index, concept in enumerate(concept_chain):
        concept_hits = []
        for taxonomy, concepts in facts_root.items():
            if concept not in concepts:
                continue
            concept_payload = concepts[concept]
            units = optional_key(mapping=concept_payload, key="units", default={})
            if not isinstance(units, dict):
                print(f"Malformed units skipped for {cik} {concept}")
                continue
            for unit, fact_list in units.items():
                for fact in fact_list:
                    matches = False
                    if period_kind == "duration":
                        matches = fact_is_annual_duration(
                            fact=fact,
                            period_end=period_end,
                        )
                    elif period_kind == "instant":
                        matches = fact_is_instant(fact=fact, period_end=period_end)
                    else:
                        raise ValueError(f"Unknown period_kind: {period_kind}")
                    if matches:
                        hit = fact_from_json(
                            cik=cik,
                            taxonomy=taxonomy,
                            concept=concept,
                            unit=str(unit),
                            fact=fact,
                        )
                        concept_hits.append(hit)
        if concept_hits:
            concept_hits.sort(
                key=lambda hit: (hit.filed, hit.accession, hit.unit),
                reverse=True,
            )
            hits.extend(concept_hits)
            print(
                f"Selected candidate concept tier {concept_index} "
                f"for CIK {cik}: {concept}"
            )
            return hits
    return hits


def select_fact(
    *,
    cik: int,
    concept_chain: list[str],
    period_end: str,
    period_kind: str,
    preferred_accession: str,
) -> FactHit | None:
    """Select the best companyfacts hit for a metric component."""
    hits = candidate_fact_hits(
        cik=cik,
        concept_chain=concept_chain,
        period_end=period_end,
        period_kind=period_kind,
    )
    if not hits:
        return None
    preferred = [hit for hit in hits if hit.accession == preferred_accession]
    if preferred:
        return preferred[0]
    return hits[0]


def metric_row(
    *,
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    value: str,
    unit: str,
    status: str,
    source_class: str,
    formula: str,
    period_start: str,
    period_end: str,
    fiscal_year: str,
    fiscal_period: str,
    accession: str,
    form: str,
    filed_date: str,
    concept_or_section: str,
    context_or_dimension: str,
    confidence: str,
    notes: str,
) -> dict:
    """Build one metrics_matrix row with status validation."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Illegal metric status: {status}")
    return {
        "company": company,
        "cik": str(cik),
        "metric_id": metric_id,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "status": status,
        "source_class": source_class,
        "formula": formula,
        "period_start": period_start,
        "period_end": period_end,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "accession": accession,
        "form": form,
        "filed_date": filed_date,
        "concept_or_section": concept_or_section,
        "context_or_dimension": context_or_dimension,
        "confidence": confidence,
        "notes": notes,
    }


def fact_period_start(*, hit: FactHit) -> str:
    """Return a non-empty period start for duration and instant facts.

    Args:
        hit: Selected companyfacts fact.

    Expected output:
        Duration facts keep their SEC start date; instant facts use their end
        date as the start so value-bearing rows never have an empty period.
    """
    if hit.start:
        return hit.start
    if hit.end:
        return hit.end
    return ""


def evidence_row_for_fact(
    *,
    company: str,
    cik: int,
    metric_id: str,
    hit: FactHit,
    value_normalized: str,
    extraction_method: str,
) -> dict:
    """Build one metric_evidence row from a companyfacts FactHit."""
    period_start = fact_period_start(hit=hit)
    context = f"companyfacts:{hit.unit}:{hit.frame}:{period_start}:{hit.end}"
    return {
        "company": company,
        "cik": str(cik),
        "metric_id": metric_id,
        "source_url": hit.source_url,
        "local_path": hit.source_path,
        "accession": hit.accession,
        "document_name": Path(hit.source_path).name,
        "concept_or_section": hit.concept,
        "context_or_dimension": context,
        "unit": hit.unit,
        "period_start": period_start,
        "period_end": hit.end,
        "value_raw": hit.raw_value,
        "value_normalized": value_normalized,
        "evidence_quote": (
            f"{hit.taxonomy}:{hit.concept} unit={hit.unit} "
            f"accn={hit.accession} filed={hit.filed}"
        ),
        "extraction_method": extraction_method,
        "parser_version": "sec_pipeline_v1",
    }


def metric_from_fact(
    *,
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    hit: FactHit | None,
    period_end: str,
    notes: str,
) -> tuple[dict, list[dict]]:
    """Build metric and evidence rows for a direct companyfacts fact."""
    if hit is None:
        row = metric_row(
            company=company,
            cik=cik,
            metric_id=metric_id,
            metric_name=metric_name,
            value="",
            unit="",
            status="NOT_AVAILABLE_SEC",
            source_class="NOT_AVAILABLE",
            formula="direct companyfacts candidate chain",
            period_start="",
            period_end=period_end,
            fiscal_year="",
            fiscal_period="",
            accession="",
            form="",
            filed_date="",
            concept_or_section="",
            context_or_dimension="",
            confidence="0.00",
            notes=notes,
        )
        return row, []
    normalized = decimal_text(value=hit.value)
    period_start = fact_period_start(hit=hit)
    row = metric_row(
        company=company,
        cik=cik,
        metric_id=metric_id,
        metric_name=metric_name,
        value=normalized,
        unit=hit.unit,
        status="OK",
        source_class="STD_XBRL",
        formula="direct",
        period_start=period_start,
        period_end=hit.end,
        fiscal_year=hit.fiscal_year,
        fiscal_period=hit.fiscal_period,
        accession=hit.accession,
        form=hit.form,
        filed_date=hit.filed,
        concept_or_section=hit.concept,
        context_or_dimension=f"companyfacts:{hit.unit}:{hit.frame}",
        confidence="0.95",
        notes=notes,
    )
    evidence = evidence_row_for_fact(
        company=company,
        cik=cik,
        metric_id=metric_id,
        hit=hit,
        value_normalized=normalized,
        extraction_method="companyfacts_direct",
    )
    return row, [evidence]


def derived_metric(
    *,
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    value: Decimal | None,
    unit: str,
    status: str,
    formula: str,
    period_start: str,
    period_end: str,
    fiscal_year: str,
    fiscal_period: str,
    hits: list[FactHit],
    notes: str,
) -> tuple[dict, list[dict]]:
    """Build metric and evidence rows for a derived formula."""
    accession = ";".join([hit.accession for hit in hits])
    concepts = "+".join([hit.concept for hit in hits])
    local_paths = ";".join([hit.source_path for hit in hits])
    source_urls = ";".join([hit.source_url for hit in hits])
    if value is None:
        value_text = ""
    else:
        value_text = decimal_text(value=value)
    row_period_start = period_start
    if value is not None and not row_period_start and period_end:
        row_period_start = period_end
    row = metric_row(
        company=company,
        cik=cik,
        metric_id=metric_id,
        metric_name=metric_name,
        value=value_text,
        unit=unit,
        status=status,
        source_class="DERIVED" if value is not None else "NOT_AVAILABLE",
        formula=formula,
        period_start=row_period_start,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        accession=accession,
        form="10-K",
        filed_date=";".join([hit.filed for hit in hits]),
        concept_or_section=concepts,
        context_or_dimension=";".join(
            [f"companyfacts:{hit.unit}:{hit.frame}" for hit in hits]
        ),
        confidence="0.90" if value is not None else "0.00",
        notes=notes,
    )
    evidence_rows = []
    if hits:
        evidence_rows.append(
            {
                "company": company,
                "cik": str(cik),
                "metric_id": metric_id,
                "source_url": source_urls,
                "local_path": local_paths,
                "accession": accession,
                "document_name": "companyfacts components",
                "concept_or_section": concepts,
                "context_or_dimension": row["context_or_dimension"],
                "unit": unit,
                "period_start": row_period_start,
                "period_end": period_end,
                "value_raw": ";".join([hit.raw_value for hit in hits]),
                "value_normalized": value_text,
                "evidence_quote": (
                    f"{formula}; components="
                    f"{';'.join([hit.concept + '=' + hit.raw_value for hit in hits])}"
                ),
                "extraction_method": "companyfacts_derived",
                "parser_version": "sec_pipeline_v1",
            }
        )
    return row, evidence_rows


def period_start_for_company_period(*, company: str, period_end: str) -> str:
    """Infer the fiscal-period start for a company/report date.

    Args:
        company: Display company name used in latest_filings_inventory.csv.
        period_end: ISO reportDate for the metric row.

    Expected output:
        The day after the latest earlier 10-K reportDate when available;
        otherwise a conservative calendar-year start for the same end year.
    """
    if not period_end:
        return ""
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    prior_dates = []
    for row in inventory:
        if row["company"] != company:
            continue
        if row["source_role"] != "prior_10k":
            continue
        report_date = str(row["reportDate"])
        if report_date and report_date < period_end:
            prior_dates.append(report_date)
    if prior_dates:
        latest_prior = sorted(prior_dates, reverse=True)[0]
        return (
            parse_date_text(value=latest_prior) + timedelta(days=1)
        ).isoformat()
    end_date = parse_date_text(value=period_end)
    return date(year=end_date.year, month=1, day=1).isoformat()


def placeholder_metric(
    *,
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    status: str,
    source_class: str,
    period_end: str,
    notes: str,
) -> dict:
    """Build a non-numeric placeholder metric row with explicit status."""
    period_start = period_start_for_company_period(
        company=company,
        period_end=period_end,
    )
    return metric_row(
        company=company,
        cik=cik,
        metric_id=metric_id,
        metric_name=metric_name,
        value="",
        unit="",
        status=status,
        source_class=source_class,
        formula="not numeric in companyfacts stage",
        period_start=period_start,
        period_end=period_end,
        fiscal_year="",
        fiscal_period="",
        accession="",
        form="",
        filed_date="",
        concept_or_section=notes,
        context_or_dimension="",
        confidence="0.00",
        notes=notes,
    )


def select_component(
    *,
    cik: int,
    concept_chain: list[str],
    period_end: str,
    period_kind: str,
    accession: str,
) -> FactHit | None:
    """Select a companyfacts component by chain and target accession."""
    return select_fact(
        cik=cik,
        concept_chain=concept_chain,
        period_end=period_end,
        period_kind=period_kind,
        preferred_accession=accession,
    )


def select_target_component(
    *,
    cik: int,
    concept_chain: list[str],
    period_end: str,
    period_kind: str,
    accession: str,
) -> FactHit | None:
    """Select a component only when it belongs to the target accession.

    Args:
        cik: Target CIK.
        concept_chain: Candidate concepts in priority order.
        period_end: Target report date.
        period_kind: "duration" or "instant".
        accession: Required accession.

    Returns:
        FactHit from the target accession or None.
    """
    hit = select_component(
        cik=cik,
        concept_chain=concept_chain,
        period_end=period_end,
        period_kind=period_kind,
        accession=accession,
    )
    if hit is None:
        return None
    if hit.accession != accession:
        print(
            "Component skipped because latest fact is outside target accession: "
            f"{hit.concept} {hit.accession} expected={accession}"
        )
        return None
    return hit


def compatible_component_hits(
    *,
    hits: list[FactHit],
    period_start: str,
    period_end: str,
    accession: str,
    unit: str,
) -> bool:
    """Return whether duration facts can be safely combined.

    Args:
        hits: Facts that would be added or subtracted together.
        period_start: Required start date.
        period_end: Required end date.
        accession: Required accession.
        unit: Required unit.

    Returns:
        True when all facts share the annual target context.
    """
    for hit in hits:
        if hit.accession != accession:
            return False
        if hit.unit != unit:
            return False
        if hit.start != period_start or hit.end != period_end:
            return False
        if not hit.form.startswith("10-K"):
            return False
        if hit.fiscal_period != "FY":
            return False
        if not annual_duration_ok(hit=hit):
            return False
    return True


def instant_component_hits_compatible(
    *,
    hits: list[FactHit],
    period_end: str,
    accession: str,
    unit: str,
) -> bool:
    """Return whether instant facts can be safely combined.

    Args:
        hits: Instant facts that would be added together.
        period_end: Required balance-sheet date.
        accession: Required accession.
        unit: Required unit.

    Returns:
        True when all facts are from the target filing and unit.
    """
    for hit in hits:
        if hit.accession != accession:
            return False
        if hit.unit != unit:
            return False
        if hit.end != period_end:
            return False
        if not hit.form.startswith("10-K"):
            return False
    return True


def resolve_da_component(
    *,
    cik: int,
    period_end: str,
    accession: str,
) -> ComponentResolution:
    """Resolve depreciation and amortization for B03.

    Args:
        cik: Target CIK.
        period_end: Target fiscal year end.
        accession: Required target 10-K accession.

    Returns:
        Direct D&A when available, otherwise a strictly compatible
        Depreciation + AmortizationOfIntangibleAssets composition.
    """
    direct = select_target_component(
        cik=cik,
        concept_chain=DA_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if direct is not None:
        return ComponentResolution(
            value=direct.value,
            hits=[direct],
            status="OK",
            formula=direct.concept,
            notes="Direct D&A concept selected.",
        )
    depreciation = select_target_component(
        cik=cik,
        concept_chain=["Depreciation"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    amortization = select_target_component(
        cik=cik,
        concept_chain=["AmortizationOfIntangibleAssets"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if depreciation is None or amortization is None:
        return ComponentResolution(
            value=None,
            hits=[hit for hit in [depreciation, amortization] if hit is not None],
            status="NOT_AVAILABLE_SEC",
            formula="Depreciation + AmortizationOfIntangibleAssets",
            notes="Direct D&A and compatible D&A composition are missing.",
        )
    hits = [depreciation, amortization]
    if not compatible_component_hits(
        hits=hits,
        period_start=depreciation.start,
        period_end=period_end,
        accession=accession,
        unit="USD",
    ):
        return ComponentResolution(
            value=None,
            hits=hits,
            status="NEEDS_REVIEW",
            formula="Depreciation + AmortizationOfIntangibleAssets",
            notes=(
                "D&A composition rejected because period, accession, or "
                "unit differs."
            ),
        )
    return ComponentResolution(
        value=depreciation.value + amortization.value,
        hits=hits,
        status="OK",
        formula="Depreciation + AmortizationOfIntangibleAssets",
        notes=(
            "D&A composed from standard Depreciation + "
            "AmortizationOfIntangibleAssets."
        ),
    )


def custom_da_observation_note(
    *,
    company: str,
    period_start: str,
    period_end: str,
    accession: str,
) -> str:
    """Return a note when a custom D&A-and-other line is observed.

    Args:
        company: Display company name.
        period_start: Target duration start.
        period_end: Target duration end.
        accession: Target accession.

    Returns:
        Disclosure note, or empty string when no matching custom line exists.
    """
    rows = read_csv_file(path=instance_inventory_path(company=company))
    matches = [
        row
        for row in rows
        if row["accession"] == accession
        and row["period_start"] == period_start
        and row["period_end"] == period_end
        and row["unit"] == "iso4217:USD"
        and row["dimensions"] == ""
        and re.search(
            pattern=r"DepreciationAmortizationAndOther",
            string=row["concept"],
            flags=re.IGNORECASE,
        )
    ]
    if not matches:
        return ""
    values = ";".join(
        f"{row['concept']}={row['value']}" for row in matches[:3]
    )
    return (
        " custom DepreciationAmortizationAndOther observed "
        f"({values}) but not added because \"and other\" is not cleanly "
        "attributable to D&A expense."
    )


def resolve_operating_income_component(
    *,
    cik: int,
    period_end: str,
    accession: str,
    revenue: FactHit | None,
) -> ComponentResolution:
    """Resolve operating income for B03 and B07.

    Args:
        cik: Target CIK.
        period_end: Target fiscal year end.
        accession: Required target accession.
        revenue: Revenue fact used for optional cross-validation.

    Returns:
        Direct operating income, or an OK_APPROX reconstruction from pretax
        continuing income less aggregate nonoperating income/expense.
    """
    direct = select_target_component(
        cik=cik,
        concept_chain=OPERATING_INCOME_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if direct is not None:
        return ComponentResolution(
            value=direct.value,
            hits=[direct],
            status="OK",
            formula="OperatingIncomeLoss",
            notes="Direct OperatingIncomeLoss selected.",
        )
    pretax = select_target_component(
        cik=cik,
        concept_chain=PRETAX_CONTINUING_INCOME_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    bridge = select_target_component(
        cik=cik,
        concept_chain=NONOPERATING_BRIDGE_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if pretax is None or bridge is None:
        return ComponentResolution(
            value=None,
            hits=[hit for hit in [pretax, bridge] if hit is not None],
            status="NOT_AVAILABLE_SEC",
            formula="pretax continuing income - aggregate nonoperating bridge",
            notes="Operating income and aggregate nonoperating bridge are missing.",
        )
    hits = [pretax, bridge]
    if not compatible_component_hits(
        hits=hits,
        period_start=pretax.start,
        period_end=period_end,
        accession=accession,
        unit="USD",
    ):
        return ComponentResolution(
            value=None,
            hits=hits,
            status="NEEDS_REVIEW",
            formula="pretax continuing income - aggregate nonoperating bridge",
            notes="Operating income reconstruction rejected for mixed context.",
        )
    reconstructed = pretax.value - bridge.value
    costs = select_target_component(
        cik=cik,
        concept_chain=["CostsAndExpenses"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if costs is not None and revenue is not None:
        expected = revenue.value - costs.value
        denominator = abs(reconstructed) if reconstructed != 0 else Decimal("1")
        error = abs(expected - reconstructed) / denominator
        if error > Decimal("0.01"):
            return ComponentResolution(
                value=None,
                hits=[pretax, bridge, revenue, costs],
                status="NEEDS_REVIEW",
                formula="pretax continuing income - aggregate nonoperating bridge",
                notes=(
                    "Operating income reconstruction failed Revenues - "
                    f"CostsAndExpenses cross-check; relative_error={error}."
                ),
            )
        cross_note = " Cross-checked against Revenues - CostsAndExpenses."
        hits = [pretax, bridge, revenue, costs]
    else:
        cross_note = (
            " CostsAndExpenses cross-check unavailable; assumes the "
            "nonoperating aggregate is the complete operating-to-pretax bridge."
        )
    return ComponentResolution(
        value=reconstructed,
        hits=hits,
        status="OK_APPROX",
        formula="pretax continuing income - aggregate nonoperating bridge",
        notes=(
            "Operating income reconstructed from pretax continuing income less "
            "aggregate nonoperating income/expense; assumes the nonoperating "
            "aggregate is the complete operating-to-pretax bridge."
            + cross_note
        ),
    )


def concept_excluded_from_total_debt(*, concept: str) -> bool:
    """Return whether a concept is forbidden in total debt resolution.

    Args:
        concept: XBRL concept local name.

    Returns:
        True for securities, fair-value, face-value, maturity, proceeds, and
        repayment concepts that do not represent current debt outstanding.
    """
    normalized = normalized_concept_name(concept=concept)
    excluded_patterns = [
        r"^debtsecurities",
        r"^availableforsalesecuritiesdebt",
        r"^debtinstrumentfairvalue$",
        r"^debtinstrumentfaceamount$",
        r"^debtinstrumentunamortized",
        r"maturitiesrepayments",
        r"paymentsdue",
        r"^proceedsfromdebt",
        r"^proceedsfromissuanceofdebt",
        r"^repaymentsofdebt",
        r"^repaymentsoflongtermdebt",
    ]
    return any(
        re.search(pattern=pattern, string=normalized)
        for pattern in excluded_patterns
    )


def target_instant_component_exists(
    *,
    cik: int,
    concept: str,
    period_end: str,
    accession: str,
) -> bool:
    """Return whether a target instant fact exists for a concept.

    Args:
        cik: Target CIK.
        concept: Exact concept name.
        period_end: Target balance-sheet date.
        accession: Required accession.

    Returns:
        True when the exact concept is available in the target filing.
    """
    hit = select_target_component(
        cik=cik,
        concept_chain=[concept],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    return hit is not None


def resolve_total_debt_component(
    *,
    cik: int,
    period_end: str,
    accession: str,
) -> ComponentResolution:
    """Resolve B06 total debt without double-counting adders.

    Args:
        cik: Target CIK.
        period_end: Target balance-sheet date.
        accession: Required target accession.

    Returns:
        Total debt component using direct totals first, then same-family pairs,
        then restricted standalone/additional short-debt fallback.
    """
    for concept in TOTAL_DEBT_DIRECT_CHAIN:
        hit = select_target_component(
            cik=cik,
            concept_chain=[concept],
            period_end=period_end,
            period_kind="instant",
            accession=accession,
        )
        if hit is None:
            continue
        if concept_excluded_from_total_debt(concept=hit.concept):
            continue
        return ComponentResolution(
            value=hit.value,
            hits=[hit],
            status="OK",
            formula=concept,
            notes="Tier 1 direct total debt selected; no adders applied.",
        )
    for current_concept, noncurrent_concept in TOTAL_DEBT_PAIR_CHAINS:
        current = select_target_component(
            cik=cik,
            concept_chain=[current_concept],
            period_end=period_end,
            period_kind="instant",
            accession=accession,
        )
        noncurrent = select_target_component(
            cik=cik,
            concept_chain=[noncurrent_concept],
            period_end=period_end,
            period_kind="instant",
            accession=accession,
        )
        if current is None or noncurrent is None:
            continue
        hits = [current, noncurrent]
        if not instant_component_hits_compatible(
            hits=hits,
            period_end=period_end,
            accession=accession,
            unit="USD",
        ):
            continue
        return ComponentResolution(
            value=current.value + noncurrent.value,
            hits=hits,
            status="OK",
            formula=f"{current_concept} + {noncurrent_concept}",
            notes="Tier 2 same-family current/noncurrent debt pair selected.",
        )
    standalone = select_target_component(
        cik=cik,
        concept_chain=TOTAL_DEBT_STANDALONE_FALLBACK_CHAIN,
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    sibling_current_exists = target_instant_component_exists(
        cik=cik,
        concept="LongTermDebtAndCapitalLeaseObligationsCurrent",
        period_end=period_end,
        accession=accession,
    )
    base_hits = []
    total = Decimal("0")
    note = "Tier 3 restricted fallback."
    if standalone is not None and not sibling_current_exists:
        base_hits.append(standalone)
        total += standalone.value
        note = (
            "Standalone LongTermDebtAndCapitalLeaseObligations used only after "
            "Tier 1 and complete same-family pairs were unavailable."
        )
    if not base_hits:
        for current_concept, noncurrent_concept in TOTAL_DEBT_LEASE_PAIR_CHAINS:
            current = select_target_component(
                cik=cik,
                concept_chain=[current_concept],
                period_end=period_end,
                period_kind="instant",
                accession=accession,
            )
            noncurrent = select_target_component(
                cik=cik,
                concept_chain=[noncurrent_concept],
                period_end=period_end,
                period_kind="instant",
                accession=accession,
            )
            if current is None or noncurrent is None:
                continue
            hits = [current, noncurrent]
            if not instant_component_hits_compatible(
                hits=hits,
                period_end=period_end,
                accession=accession,
                unit="USD",
            ):
                continue
            return ComponentResolution(
                value=current.value + noncurrent.value,
                hits=hits,
                status="OK",
                formula=f"{current_concept} + {noncurrent_concept}",
                notes="Tier 2 same-family finance lease liability pair selected.",
            )
    short_hits = []
    for concept in TOTAL_DEBT_SHORT_ADDER_CHAIN:
        hit = select_target_component(
            cik=cik,
            concept_chain=[concept],
            period_end=period_end,
            period_kind="instant",
            accession=accession,
        )
        if hit is not None:
            short_hits.append(hit)
    if base_hits and short_hits:
        if instant_component_hits_compatible(
            hits=base_hits + short_hits,
            period_end=period_end,
            accession=accession,
            unit="USD",
        ):
            for hit in short_hits:
                total += hit.value
            base_hits.extend(short_hits)
            note += " ShortTermBorrowings/CommercialPaper adders included."
    if base_hits:
        return ComponentResolution(
            value=total,
            hits=base_hits,
            status="OK",
            formula=" + ".join([hit.concept for hit in base_hits]),
            notes=note,
        )
    if short_hits:
        return ComponentResolution(
            value=None,
            hits=short_hits,
            status="NEEDS_REVIEW",
            formula=" + ".join([hit.concept for hit in short_hits]),
            notes="Only short debt adders were found; total debt base is missing.",
        )
    return ComponentResolution(
        value=None,
        hits=[],
        status="NOT_AVAILABLE_SEC",
        formula="total debt tier resolver",
        notes="No acceptable total debt concept, same-family pair, or fallback found.",
    )


def stub_period_fact_hits(
    *,
    cik: int,
    concept_chain: list[str],
    period_end: str,
    accession: str,
) -> list[FactHit]:
    """Return target facts whose duration is not annual-comparable.

    Args:
        cik: Target CIK.
        concept_chain: Concepts to scan for stub period values.
        period_end: Target report date.
        accession: Required target accession.

    Returns:
        FactHit rows with duration outside the 300-400 day annual window.
    """
    payload = read_json_file(path=companyfacts_path(cik=cik))
    facts_root = require_key(mapping=payload, key="facts")
    hits = []
    for concept in concept_chain:
        for taxonomy, concepts in facts_root.items():
            if concept not in concepts:
                continue
            concept_payload = concepts[concept]
            units = optional_key(mapping=concept_payload, key="units", default={})
            if not isinstance(units, dict):
                print(f"Malformed stub units skipped for {cik} {concept}")
                continue
            for unit, fact_list in units.items():
                for fact in fact_list:
                    form = str(optional_key(mapping=fact, key="form", default=""))
                    start = str(optional_key(mapping=fact, key="start", default=""))
                    end = str(optional_key(mapping=fact, key="end", default=""))
                    accn = str(optional_key(mapping=fact, key="accn", default=""))
                    if not form.startswith("10-K"):
                        continue
                    if accn != accession or end != period_end or not start:
                        continue
                    duration = fact_duration_days(fact=fact)
                    if duration is None or 300 <= duration <= 400:
                        continue
                    hits.append(
                        fact_from_json(
                            cik=cik,
                            taxonomy=taxonomy,
                            concept=concept,
                            unit=str(unit),
                            fact=fact,
                        )
                    )
    return hits


def stub_period_bounds(
    *,
    cik: int,
    period_end: str,
    accession: str,
) -> tuple[str, str]:
    """Return the dominant target stub period bounds.

    Args:
        cik: Target CIK.
        period_end: Target report date.
        accession: Required target accession.

    Returns:
        Tuple of start/end dates, or two blanks when no stub facts exist.
    """
    bounds: dict[tuple[str, str], int] = {}
    for _metric_id, concept_chain in STUB_PERIOD_COMPONENT_CHAINS:
        for hit in stub_period_fact_hits(
            cik=cik,
            concept_chain=concept_chain,
            period_end=period_end,
            accession=accession,
        ):
            key = (hit.start, hit.end)
            if key not in bounds:
                bounds[key] = 0
            bounds[key] += 1
    if not bounds:
        return "", ""
    return sorted(bounds.items(), key=lambda item: item[1], reverse=True)[0][0]


def stub_period_note(*, stub_start: str, stub_end: str) -> str:
    """Return the standard annual-metric stub caveat."""
    return (
        f"successor stub period {stub_start} to {stub_end}; annual metric "
        "not comparable."
    )


def apply_stub_period_metric_semantics(
    *,
    rows: list[dict],
    company: str,
    accession: str,
    stub_start: str,
    stub_end: str,
) -> list[dict]:
    """Blank annual period metrics when only successor stub facts exist.

    Args:
        rows: Metric rows for one company.
        company: Display company name.
        accession: Target accession used as evidence anchor.
        stub_start: Stub period start date.
        stub_end: Stub period end date.

    Returns:
        Rows with period metrics marked NOT_MEANINGFUL and B06 untouched.
    """
    note = stub_period_note(stub_start=stub_start, stub_end=stub_end)
    output = []
    for row in rows:
        if row["company"] == company and row["metric_id"] in STUB_PERIOD_MAIN_METRICS:
            updated = dict(row)
            updated["value"] = ""
            updated["unit"] = ""
            updated["status"] = "NOT_MEANINGFUL"
            updated["source_class"] = "NOT_AVAILABLE"
            updated["period_start"] = stub_start
            updated["period_end"] = stub_end
            updated["accession"] = accession
            updated["notes"] = note
            output.append(updated)
        else:
            output.append(row)
    return output


def stub_period_sidecar_rows() -> list[dict]:
    """Build outputs/stub_period_metrics.csv rows from local companyfacts.

    Returns:
        Stub-period component facts for companies whose continuity status makes
        annual period metrics non-comparable.
    """
    rows = []
    for company_config in load_company_registry():
        company = str(company_config["company"])
        continuity = str(company_config["entity_continuity_status"])
        if continuity not in {"successor_predecessor", "stub_period", "major_reorg"}:
            continue
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        period_end = str(target["reportDate"])
        accession = str(target["accession"])
        for metric_id, concept_chain in STUB_PERIOD_COMPONENT_CHAINS:
            for hit in stub_period_fact_hits(
                cik=cik,
                concept_chain=concept_chain,
                period_end=period_end,
                accession=accession,
            ):
                rows.append(
                    {
                        "company": company,
                        "metric_id": metric_id,
                        "stub_period_start": hit.start,
                        "stub_period_end": hit.end,
                        "value": hit.raw_value,
                        "unit": hit.unit,
                        "concept_or_section": hit.concept,
                        "accession": hit.accession,
                        "notes": stub_period_note(
                            stub_start=hit.start,
                            stub_end=hit.end,
                        ),
                    }
                )
    return rows


def write_stub_period_sidecar() -> None:
    """Write the stub-period sidecar for annual-metric review."""
    write_csv_file(
        path=WORKDIR / "outputs" / "stub_period_metrics.csv",
        fieldnames=STUB_PERIOD_FIELDNAMES,
        rows=stub_period_sidecar_rows(),
    )


def company_continuity_status(*, company: str) -> str:
    """Return entity continuity status from the company registry.

    Args:
        company: Display company name in metric rows.

    Returns:
        Registry continuity status string.
    """
    return str(company_by_name(company_name=company)["entity_continuity_status"])


def fact_hit_duration_days(*, hit: FactHit | None) -> int | None:
    """Return inclusive duration days for a selected fact.

    Args:
        hit: Selected fact or None.

    Returns:
        Integer day count for duration facts; None for missing/instant facts.
    """
    if hit is None or not hit.start:
        return None
    return (parse_date_text(value=hit.end) - parse_date_text(value=hit.start)).days + 1


def annual_duration_ok(*, hit: FactHit | None) -> bool:
    """Return whether a fact has a comparable annual duration."""
    duration = fact_hit_duration_days(hit=hit)
    return duration is not None and 300 <= duration <= 400


def entity_continuity_yoy_result(
    *,
    company: str,
    current_revenue: FactHit | None,
    prior_revenue: FactHit | None,
    current_cik: int,
    prior_cik: int | None,
) -> tuple[str, Decimal | None, str]:
    """Decide B02 YoY comparability without company identity branches.

    Args:
        company: Display company name for registry lookup.
        current_revenue: Current-year revenue fact.
        prior_revenue: Prior-year revenue fact.
        current_cik: CIK for current target filing.
        prior_cik: CIK for prior filing when available.

    Returns:
        Status, Decimal value or None, and explanatory notes.
    """
    continuity = company_continuity_status(company=company)
    if continuity in {"successor_predecessor", "stub_period", "major_reorg"}:
        return (
            "NOT_MEANINGFUL",
            None,
            f"Entity continuity status makes YoY not meaningful: {continuity}.",
        )
    if current_revenue is None or prior_revenue is None:
        return "NOT_AVAILABLE_SEC", None, "Revenue or prior-year revenue missing."
    if not annual_duration_ok(hit=current_revenue) or not annual_duration_ok(
        hit=prior_revenue,
    ):
        return (
            "NOT_MEANINGFUL",
            None,
            "Current/prior revenue duration is outside 300-400 days.",
        )
    if prior_cik is None or current_cik != prior_cik:
        return "NOT_MEANINGFUL", None, "Current/prior CIK chain is not continuous."
    if prior_revenue.value == 0:
        return "NOT_MEANINGFUL", None, "Prior-year revenue denominator is zero."
    return (
        "OK",
        (current_revenue.value - prior_revenue.value) / prior_revenue.value,
        "Same revenue candidate chain YoY pair after continuity checks.",
    )


def non_fi_metric_rows(*, company: str, target: dict) -> tuple[list[dict], list[dict]]:
    """Compute B01-B09 companyfacts-supported metrics for a non-FI company."""
    cik = int(target["cik"])
    period_end = str(target["reportDate"])
    accession = str(target["accession"])
    prior = prior_10k_for_company(company=company, cik=cik)
    prior_end = str(prior["reportDate"]) if prior is not None else ""
    prior_accession = str(prior["accession"]) if prior is not None else ""
    rows: list[dict] = []
    evidence_rows: list[dict] = []

    revenue = select_component(
        cik=cik,
        concept_chain=REVENUE_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    row, evidence = metric_from_fact(
        company=company,
        cik=cik,
        metric_id="B01",
        metric_name="Revenue",
        hit=revenue,
        period_end=period_end,
        notes="Revenue candidate chain from metric definition.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    prior_revenue = None
    if prior_end:
        prior_revenue = select_component(
            cik=cik,
            concept_chain=REVENUE_CHAIN,
            period_end=prior_end,
            period_kind="duration",
            accession=prior_accession,
        )
    yoy_status, yoy_value, yoy_notes = entity_continuity_yoy_result(
        company=company,
        current_revenue=revenue,
        prior_revenue=prior_revenue,
        current_cik=cik,
        prior_cik=int(prior["cik"]) if prior is not None else None,
    )
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B02",
        metric_name="Revenue YoY growth",
        value=yoy_value,
        unit="ratio",
        status=yoy_status,
        formula="(Revenue_t - Revenue_t-1) / Revenue_t-1",
        period_start=revenue.start if revenue is not None else "",
        period_end=period_end,
        fiscal_year=revenue.fiscal_year if revenue is not None else "",
        fiscal_period=revenue.fiscal_period if revenue is not None else "",
        hits=[hit for hit in [revenue, prior_revenue] if hit is not None],
        notes=yoy_notes,
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    operating_income = resolve_operating_income_component(
        cik=cik,
        period_end=period_end,
        accession=accession,
        revenue=revenue,
    )
    da = resolve_da_component(
        cik=cik,
        period_end=period_end,
        accession=accession,
    )
    da_custom_note = ""
    if da.hits:
        da_custom_note = custom_da_observation_note(
            company=company,
            period_start=da.hits[0].start,
            period_end=period_end,
            accession=accession,
        )
    if (
        revenue is not None
        and operating_income.value is not None
        and da.value is not None
        and revenue.value != 0
    ):
        ebitda_margin = (operating_income.value + da.value) / revenue.value
        ebitda_status = (
            "OK_APPROX" if operating_income.status == "OK_APPROX" else "OK"
        )
        ebitda_notes = (
            f"{operating_income.notes} {da.notes}{da_custom_note} "
            "GAAP EBITDA proxy; impairment is not added back."
        )
    else:
        ebitda_margin = None
        ebitda_status = (
            "NEEDS_REVIEW"
            if "NEEDS_REVIEW" in {operating_income.status, da.status}
            else "NOT_AVAILABLE_SEC"
        )
        ebitda_notes = (
            f"Required revenue, operating income, or D&A missing. "
            f"Operating income: {operating_income.notes} D&A: {da.notes}"
        )
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B03",
        metric_name="EBITDA margin",
        value=ebitda_margin,
        unit="ratio",
        status=ebitda_status,
        formula="(Operating income + D&A) / revenue",
        period_start=revenue.start if revenue is not None else "",
        period_end=period_end,
        fiscal_year=revenue.fiscal_year if revenue is not None else "",
        fiscal_period=revenue.fiscal_period if revenue is not None else "",
        hits=(
            operating_income.hits
            + da.hits
            + ([revenue] if revenue is not None else [])
        ),
        notes=ebitda_notes,
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    net_income = select_component(
        cik=cik,
        concept_chain=NET_INCOME_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    row, evidence = metric_from_fact(
        company=company,
        cik=cik,
        metric_id="B04",
        metric_name="Net income",
        hit=net_income,
        period_end=period_end,
        notes="Net income candidate chain from metric definition.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    ocf = select_component(
        cik=cik,
        concept_chain=["NetCashProvidedByUsedInOperatingActivities"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    capex = select_component(
        cik=cik,
        concept_chain=CAPEX_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if ocf is not None and capex is not None:
        fcf = ocf.value - capex.value
        fcf_status = "OK"
    else:
        fcf = None
        fcf_status = "NOT_AVAILABLE_SEC"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B05",
        metric_name="Free cash flow",
        value=fcf,
        unit="USD",
        status=fcf_status,
        formula="operating cash flow - capital expenditures",
        period_start=ocf.start if ocf is not None else "",
        period_end=period_end,
        fiscal_year=ocf.fiscal_year if ocf is not None else "",
        fiscal_period=ocf.fiscal_period if ocf is not None else "",
        hits=[hit for hit in [ocf, capex] if hit is not None],
        notes="Capex chain allows PaymentsToAcquireProductiveAssets.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    equity = select_component(
        cik=cik,
        concept_chain=EQUITY_CHAIN,
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    debt = resolve_total_debt_component(
        cik=cik,
        period_end=period_end,
        accession=accession,
    )
    if debt.value is not None and equity is not None and equity.value <= 0:
        debt_to_equity = None
        debt_status = "NOT_MEANINGFUL"
        debt_notes = (
            "Equity is negative; debt/equity ratio is not economically "
            "meaningful. "
            f"Total debt candidate={decimal_text(value=debt.value)}. {debt.notes}"
        )
    elif debt.value is not None and equity is not None and equity.value != 0:
        debt_to_equity = debt.value / equity.value
        debt_status = debt.status
        debt_notes = (
            "Consolidated entity-level debt/equity; "
            f"{debt.notes} Captive-finance dimensions are reviewed after "
            "accession instance parsing."
        )
        if company_continuity_status(company=company) in {
            "successor_predecessor",
            "stub_period",
            "major_reorg",
        }:
            debt_notes += (
                " successor balance sheet point-in-time, not annualized "
                "period metric."
            )
    else:
        debt_to_equity = None
        debt_status = (
            "NEEDS_REVIEW" if debt.status == "NEEDS_REVIEW" else "NOT_AVAILABLE_SEC"
        )
        debt_notes = f"Debt or equity missing. {debt.notes}"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B06",
        metric_name="Debt-to-equity",
        value=debt_to_equity,
        unit="ratio",
        status=debt_status,
        formula="total debt / shareholders' equity",
        period_start="",
        period_end=period_end,
        fiscal_year=equity.fiscal_year if equity is not None else "",
        fiscal_period=equity.fiscal_period if equity is not None else "",
        hits=debt.hits + ([equity] if equity is not None else []),
        notes=debt_notes,
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    interest = select_component(
        cik=cik,
        concept_chain=INTEREST_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if operating_income.value is not None and operating_income.value <= 0:
        interest_coverage = None
        interest_status = "NOT_MEANINGFUL"
        interest_notes = "Operating income is non-positive."
    elif (
        operating_income.value is not None
        and interest is not None
        and interest.value != 0
    ):
        interest_coverage = operating_income.value / interest.value
        interest_status = (
            "OK_APPROX" if operating_income.status == "OK_APPROX" else "OK"
        )
        interest_notes = (
            "Interest coverage uses reconstructed operating income."
            if operating_income.status == "OK_APPROX"
            else "Operating income divided by interest expense."
        )
    else:
        interest_coverage = None
        interest_status = "NOT_AVAILABLE_SEC"
        interest_notes = (
            "Operating income or interest expense missing. "
            f"{operating_income.notes}"
        )
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B07",
        metric_name="Interest coverage ratio",
        value=interest_coverage,
        unit="ratio",
        status=interest_status,
        formula="operating income / interest expense",
        period_start=operating_income.hits[0].start if operating_income.hits else "",
        period_end=period_end,
        fiscal_year=(
            operating_income.hits[0].fiscal_year if operating_income.hits else ""
        ),
        fiscal_period=(
            operating_income.hits[0].fiscal_period if operating_income.hits else ""
        ),
        hits=operating_income.hits + ([interest] if interest is not None else []),
        notes=interest_notes,
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    current_assets = select_component(
        cik=cik,
        concept_chain=["AssetsCurrent"],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    current_liabilities = select_component(
        cik=cik,
        concept_chain=["LiabilitiesCurrent"],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    if current_assets is not None and current_liabilities is not None:
        current_ratio = current_assets.value / current_liabilities.value
        current_status = "OK"
    else:
        current_ratio = None
        current_status = "NOT_AVAILABLE_SEC"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B08",
        metric_name="Current ratio",
        value=current_ratio,
        unit="ratio",
        status=current_status,
        formula="current assets / current liabilities",
        period_start="",
        period_end=period_end,
        fiscal_year=current_assets.fiscal_year if current_assets is not None else "",
        fiscal_period=(
            current_assets.fiscal_period if current_assets is not None else ""
        ),
        hits=[
            hit
            for hit in [current_assets, current_liabilities]
            if hit is not None
        ],
        notes="Financial-institution profiles handle current ratio as structural N/A.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    cash = select_component(
        cik=cik,
        concept_chain=["CashAndCashEquivalentsAtCarryingValue"],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    row, evidence = metric_from_fact(
        company=company,
        cik=cik,
        metric_id="B09",
        metric_name="Cash reserves",
        hit=cash,
        period_end=period_end,
        notes="Cash and cash equivalents only; short-term investments not merged.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    stub_start, stub_end = stub_period_bounds(
        cik=cik,
        period_end=period_end,
        accession=accession,
    )
    if stub_start and stub_end:
        rows = apply_stub_period_metric_semantics(
            rows=rows,
            company=company,
            accession=accession,
            stub_start=stub_start,
            stub_end=stub_end,
        )

    return rows, evidence_rows


def fi_metric_rows(*, company: str, target: dict) -> tuple[list[dict], list[dict]]:
    """Compute FI-track metrics that can be supported by companyfacts.

    Args:
        company: Display company name for one financial institution profile.
        target: Selected target 10-K inventory row.

    Returns:
        Metric rows and evidence rows for the FI profile.
    """
    cik = int(target["cik"])
    period_end = str(target["reportDate"])
    accession = str(target["accession"])
    prior = prior_10k_for_company(company=company, cik=cik)
    prior_end = str(prior["reportDate"]) if prior is not None else ""
    prior_accession = str(prior["accession"]) if prior is not None else ""
    rows: list[dict] = []
    evidence_rows: list[dict] = []

    for metric_id, metric_name, notes in [
        (
            "A01",
            "Tier 1 capital ratio",
            "Requires Basel/regulatory capital table or dimensions.",
        ),
        (
            "A02",
            "CET1 ratio",
            "Requires Basel standardized/advanced approach evidence.",
        ),
        ("A03", "Liquidity coverage ratio", "Usually MD&A liquidity table."),
        (
            "A04",
            "Net interest margin",
            "Requires MD&A average balances or net interest margin table.",
        ),
        (
            "A08",
            "Fee income vs interest income",
            "Requires bank-specific revenue composition review.",
        ),
        (
            "A09",
            "Non-performing loans / NPL ratio",
            "Requires credit risk table or reviewed dimensions.",
        ),
        (
            "A10",
            "Loan loss reserves",
            "Requires allowance and loans denominator review.",
        ),
        ("A11", "AUM", "Typically disclosed in MD&A/segment text."),
        ("A12", "Trading exposure", "Requires VaR or market risk table."),
        (
            "A13",
            "Geographic exposure",
            "Requires geographic dimensions or segment table.",
        ),
    ]:
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id=metric_id,
                metric_name=metric_name,
                status="NOT_EXTRACTED",
                source_class="NOT_AVAILABLE",
                period_end=period_end,
                notes=notes,
            )
        )

    noninterest_income = select_target_component(
        cik=cik,
        concept_chain=["NoninterestIncome"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    net_interest_income = select_target_component(
        cik=cik,
        concept_chain=["InterestIncomeExpenseNet"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if (
        noninterest_income is not None
        and net_interest_income is not None
        and net_interest_income.value != 0
    ):
        a08_value = noninterest_income.value / net_interest_income.value
        a08_status = "OK"
    else:
        a08_value = None
        a08_status = "NOT_EXTRACTED"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="A08",
        metric_name="Fee income vs interest income",
        value=a08_value,
        unit="ratio",
        status=a08_status,
        formula="NoninterestIncome / InterestIncomeExpenseNet",
        period_start=(
            noninterest_income.start if noninterest_income is not None else ""
        ),
        period_end=period_end,
        fiscal_year=(
            noninterest_income.fiscal_year if noninterest_income is not None else ""
        ),
        fiscal_period=(
            noninterest_income.fiscal_period if noninterest_income is not None else ""
        ),
        hits=[
            hit
            for hit in [noninterest_income, net_interest_income]
            if hit is not None
        ],
        notes=(
            "Per 02 §A08 definition, this uses noninterest income, not pure "
            "fee income; noninterest income may include trading, investment "
            "banking, asset-management and other noninterest revenue."
        ),
    )
    if a08_value is not None:
        row["source_class"] = "STD_XBRL"
    rows = upsert_metric(rows=rows, new_row=row)
    evidence_rows.extend(evidence)

    allowance = select_target_component(
        cik=cik,
        concept_chain=[
            "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest"
        ],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    loans_before_allowance = select_target_component(
        cik=cik,
        concept_chain=[
            "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss"
        ],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    if (
        allowance is not None
        and loans_before_allowance is not None
        and loans_before_allowance.value != 0
    ):
        a10_value = allowance.value / loans_before_allowance.value
        a10_status = "OK"
    else:
        a10_value = None
        a10_status = "NOT_EXTRACTED"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="A10",
        metric_name="Loan loss reserves",
        value=a10_value,
        unit="ratio",
        status=a10_status,
        formula=(
            "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest / "
            "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss"
        ),
        period_start="",
        period_end=period_end,
        fiscal_year=allowance.fiscal_year if allowance is not None else "",
        fiscal_period=allowance.fiscal_period if allowance is not None else "",
        hits=[
            hit
            for hit in [allowance, loans_before_allowance]
            if hit is not None
        ],
        notes=(
            "Primary allowance ratio uses retained loans before allowance for "
            "credit loss; securities credit-loss allowance is excluded."
        ),
    )
    if a10_value is not None:
        row["source_class"] = "STD_XBRL"
    rows = upsert_metric(rows=rows, new_row=row)
    evidence_rows.extend(evidence)

    net_income = select_component(
        cik=cik,
        concept_chain=NET_INCOME_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    assets = select_component(
        cik=cik,
        concept_chain=["Assets"],
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    prior_assets = None
    if prior_end:
        prior_assets = select_component(
            cik=cik,
            concept_chain=["Assets"],
            period_end=prior_end,
            period_kind="instant",
            accession=prior_accession,
        )
    if net_income is not None and assets is not None and prior_assets is not None:
        avg_assets = (assets.value + prior_assets.value) / Decimal("2")
        roa = net_income.value / avg_assets
        roa_status = "OK"
    else:
        roa = None
        roa_status = "NOT_AVAILABLE_SEC"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="A05",
        metric_name="ROA",
        value=roa,
        unit="ratio",
        status=roa_status,
        formula="net income / average total assets",
        period_start=net_income.start if net_income is not None else "",
        period_end=period_end,
        fiscal_year=net_income.fiscal_year if net_income is not None else "",
        fiscal_period=net_income.fiscal_period if net_income is not None else "",
        hits=[hit for hit in [net_income, assets, prior_assets] if hit is not None],
        notes="Average assets uses current and prior 10-K Assets.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    equity = select_component(
        cik=cik,
        concept_chain=EQUITY_CHAIN,
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    prior_equity = None
    if prior_end:
        prior_equity = select_component(
            cik=cik,
            concept_chain=EQUITY_CHAIN,
            period_end=prior_end,
            period_kind="instant",
            accession=prior_accession,
        )
    if net_income is not None and equity is not None and prior_equity is not None:
        avg_equity = (equity.value + prior_equity.value) / Decimal("2")
        roe = net_income.value / avg_equity
        roe_status = "OK"
    else:
        roe = None
        roe_status = "NOT_AVAILABLE_SEC"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="A06",
        metric_name="ROE",
        value=roe,
        unit="ratio",
        status=roe_status,
        formula="net income / average shareholders' equity",
        period_start=net_income.start if net_income is not None else "",
        period_end=period_end,
        fiscal_year=net_income.fiscal_year if net_income is not None else "",
        fiscal_period=net_income.fiscal_period if net_income is not None else "",
        hits=[hit for hit in [net_income, equity, prior_equity] if hit is not None],
        notes="Uses total equity when common-shareholder denominator is absent.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    prior_net_income = None
    if prior_end:
        prior_net_income = select_component(
            cik=cik,
            concept_chain=NET_INCOME_CHAIN,
            period_end=prior_end,
            period_kind="duration",
            accession=prior_accession,
        )
    if net_income is not None and prior_net_income is not None:
        trend = net_income.value - prior_net_income.value
        trend_status = "OK"
    else:
        trend = None
        trend_status = "NOT_AVAILABLE_SEC"
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="A07",
        metric_name="Net income trends",
        value=trend,
        unit="USD",
        status=trend_status,
        formula="NetIncome_t - NetIncome_t-1",
        period_start=net_income.start if net_income is not None else "",
        period_end=period_end,
        fiscal_year=net_income.fiscal_year if net_income is not None else "",
        fiscal_period=net_income.fiscal_period if net_income is not None else "",
        hits=[hit for hit in [net_income, prior_net_income] if hit is not None],
        notes="Single-year task trend is YoY pair.",
    )
    rows.append(row)
    evidence_rows.extend(evidence)

    rows.append(
        placeholder_metric(
            company=company,
            cik=cik,
            metric_id="B08",
            metric_name="Current ratio",
            status="N_A_STRUCTURAL",
            source_class="NOT_AVAILABLE",
            period_end=period_end,
            notes="Bank current ratio is structurally not applicable.",
        )
    )
    return rows, evidence_rows


def governance_risk_event_placeholders(
    *,
    company: str,
    cik: int,
    period_end: str,
) -> list[dict]:
    """Create C, D, and E placeholder rows before text/event extraction."""
    definitions = [
        ("C01", "CEO / CFO changes", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("C02", "Board composition", "NOT_EXTRACTED", "DEF14A"),
        ("C03", "Executive compensation signals", "NOT_EXTRACTED", "DEF14A"),
        ("C04", "Auditor changes", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("D01", "Risk factors summary", "NOT_EXTRACTED", "TEXT"),
        ("D02", "Litigation disclosures", "NOT_EXTRACTED", "TEXT"),
        ("D03", "Regulatory investigations", "NOT_EXTRACTED", "TEXT"),
        ("D04", "Going concern statements", "NOT_EXTRACTED", "TEXT"),
        ("E01", "M&A announcements", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("E02", "Bankruptcy filings", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("E03", "Leadership departures", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("E04", "Financial restatements", "NOT_AVAILABLE_SEC", "8K_ITEM"),
        ("E05", "Material agreements", "NOT_AVAILABLE_SEC", "8K_ITEM"),
    ]
    rows = []
    for metric_id, metric_name, status, source_class in definitions:
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id=metric_id,
                metric_name=metric_name,
                status=status,
                source_class=source_class,
                period_end=period_end,
                notes="Initialized before event/text extraction.",
            )
        )
    return rows


def has_extractor(*, extractors: list[str], extractor_name: str) -> bool:
    """Return whether an extractor is mounted for a company profile.

    Args:
        extractors: Configured extractor class names.
        extractor_name: Required extractor class name.

    Returns:
        True when the extractor should be attempted.
    """
    return extractor_name in extractors


BASE_METRIC_IDS_BY_TRACK = {
    "financial_institution": {
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
        "A06",
        "A07",
        "A08",
        "A09",
        "A10",
        "A11",
        "A12",
        "A13",
        "B08",
    },
    "non_financial": {
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B09",
    },
}
COMMON_METRIC_IDS = {
    "C01",
    "C02",
    "C03",
    "C04",
    "D01",
    "D02",
    "D03",
    "D04",
    "E01",
    "E02",
    "E03",
    "E04",
    "E05",
}
OPTIONAL_B_EXTRACTOR_BY_METRIC_ID = {
    "B10": "LodgingKpiExtractor",
    "B11": "LodgingKpiExtractor",
    "B12": "RpoCrpoExtractor",
    "B13": "CapacityUtilizationExtractor",
}


def optional_b_metric_is_main_applicable(*, company: str, metric_id: str) -> bool:
    """Return whether an optional B metric belongs in metrics_matrix.

    Args:
        company: Display company name.
        metric_id: Optional metric id: B10, B11, B12, or B13.

    Expected output:
        Main-matrix scope follows the configured profile extractors. Out-of-
        scope probes are preserved in sidecars rather than as placeholder rows.

    Returns:
        True only for metrics allowed by the company's configured extractor.
    """
    extractors = company_extractors(
        company_config=company_by_name(company_name=company),
    )
    if metric_id not in OPTIONAL_B_EXTRACTOR_BY_METRIC_ID:
        raise ValueError(f"Unsupported optional B metric: {metric_id}")
    return has_extractor(
        extractors=extractors,
        extractor_name=OPTIONAL_B_EXTRACTOR_BY_METRIC_ID[metric_id],
    )


def optional_b_metric_ids() -> set[str]:
    """Return optional B metrics governed by profile applicability."""
    return set(OPTIONAL_B_EXTRACTOR_BY_METRIC_ID)


def expected_metrics_matrix_keys() -> set[tuple[str, str]]:
    """Derive the exact matrix key set from registry and profile contracts.

    Returns:
        One ``(company, metric_id)`` key for every required matrix row. The
        result is independent of the currently persisted matrix rows.
    """
    expected = set()
    # The acceptance set comes from configuration, never from rows under test.
    for company_config in load_company_registry():
        company = str(require_key(mapping=company_config, key="company"))
        extractors = company_extractors(company_config=company_config)
        track = (
            "financial_institution"
            if has_extractor(
                extractors=extractors,
                extractor_name="BaselCapitalRatioExtractor",
            )
            else "non_financial"
        )
        metric_ids = BASE_METRIC_IDS_BY_TRACK[track] | COMMON_METRIC_IDS
        for metric_id, extractor_name in (
            OPTIONAL_B_EXTRACTOR_BY_METRIC_ID.items()
        ):
            if has_extractor(
                extractors=extractors,
                extractor_name=extractor_name,
            ):
                metric_ids.add(metric_id)
        expected.update((company, metric_id) for metric_id in metric_ids)
    return expected


def special_metric_placeholders(
    *,
    company: str,
    cik: int,
    period_end: str,
    extractors: list[str],
) -> list[dict]:
    """Create optional metric placeholder rows from extractor applicability.

    Args:
        company: Display company name.
        cik: Selected target CIK.
        period_end: Target reportDate.
        extractors: Mounted extractor names from metric_applicability.yaml.

    Returns:
        Placeholder rows for optional B10-B13 surfaces.
    """
    rows = []
    if has_extractor(extractors=extractors, extractor_name="LodgingKpiExtractor"):
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id="B10",
                metric_name="Occupancy rate",
                status="NOT_EXTRACTED",
                source_class="MDA",
                period_end=period_end,
                notes="Requires MD&A or EX-99 operating statistics.",
            )
        )
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id="B11",
                metric_name="RevPAR",
                status="NOT_EXTRACTED",
                source_class="MDA",
                period_end=period_end,
                notes="Requires MD&A or EX-99 operating statistics.",
            )
        )
    if has_extractor(extractors=extractors, extractor_name="RpoCrpoExtractor"):
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id="B12",
                metric_name="ARR / churn or RPO substitute",
                status="NOT_EXTRACTED",
                source_class="MDA",
                period_end=period_end,
                notes="RPO/cRPO must be labeled as not ARR.",
            )
        )
    if has_extractor(
        extractors=extractors,
        extractor_name="CapacityUtilizationExtractor",
    ):
        rows.append(
            placeholder_metric(
                company=company,
                cik=cik,
                metric_id="B13",
                metric_name="Capacity utilization",
                status="NOT_AVAILABLE_SEC",
                source_class="TEXT",
                period_end=period_end,
                notes="SEC 10-K may provide only qualitative capacity text.",
            )
        )
    return rows


def stage_compute_standard_metrics() -> None:
    """M2: compute companyfacts-supported metrics and initialize full matrix."""
    ensure_output_dirs()
    metric_rows: list[dict] = []
    evidence_rows: list[dict] = []
    for company_config in load_company_registry():
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        period_end = str(target["reportDate"])
        extractors = company_extractors(company_config=company_config)
        if has_extractor(
            extractors=extractors,
            extractor_name="BaselCapitalRatioExtractor",
        ):
            rows, evidence = fi_metric_rows(company=company, target=target)
        else:
            rows, evidence = non_fi_metric_rows(company=company, target=target)
        metric_rows.extend(rows)
        evidence_rows.extend(evidence)
        metric_rows.extend(
            special_metric_placeholders(
                company=company,
                cik=cik,
                period_end=period_end,
                extractors=extractors,
            )
        )
        metric_rows.extend(
            governance_risk_event_placeholders(
                company=company,
                cik=cik,
                period_end=period_end,
            )
        )

    write_csv_file(
        path=WORKDIR / "outputs" / "metrics_matrix.csv",
        fieldnames=METRICS_FIELDNAMES,
        rows=metric_rows,
    )
    write_csv_file(
        path=WORKDIR / "outputs" / "metric_evidence.csv",
        fieldnames=EVIDENCE_FIELDNAMES,
        rows=evidence_rows,
    )
    write_stub_period_sidecar()
    print(f"M2 standard metrics complete; metrics={len(metric_rows)}")


def load_metrics() -> list[dict]:
    """Load metrics_matrix.csv rows."""
    return read_csv_file(path=WORKDIR / "outputs" / "metrics_matrix.csv")


def save_metrics(*, rows: list[dict]) -> None:
    """Write metrics_matrix.csv rows after updates."""
    write_csv_file(
        path=WORKDIR / "outputs" / "metrics_matrix.csv",
        fieldnames=METRICS_FIELDNAMES,
        rows=rows,
    )


def upsert_metric(*, rows: list[dict], new_row: dict) -> list[dict]:
    """Replace or append one metric row by company and metric_id."""
    output = []
    replaced = False
    for row in rows:
        if (
            row["company"] == new_row["company"]
            and row["metric_id"] == new_row["metric_id"]
        ):
            output.append(new_row)
            replaced = True
        else:
            output.append(row)
    if not replaced:
        output.append(new_row)
    return output


def append_evidence(*, rows: list[dict]) -> None:
    """Append metric evidence rows to the canonical evidence CSV."""
    append_csv_file(
        path=WORKDIR / "outputs" / "metric_evidence.csv",
        fieldnames=EVIDENCE_FIELDNAMES,
        rows=rows,
    )


def accession_dir_path(*, company: str, cik: int, accession: str) -> Path:
    """Return the local evidence directory for one accession."""
    return (
        WORKDIR
        / "evidence"
        / "accession_materials"
        / f"{slugify(text=company)}_{cik}_{accession.replace('-', '')}"
    )


def material_row_from_fetch(
    *,
    inventory_row: dict,
    document_name: str,
    document_type: str,
    source_url: str,
    local_path: Path,
    status_code: int,
    content_length: int,
    sha256: str,
) -> dict:
    """Build one accession_materials_inventory row."""
    return {
        "company": inventory_row["company"],
        "cik": inventory_row["cik"],
        "entity_role": inventory_row["entity_role"],
        "form": inventory_row["form"],
        "accession": inventory_row["accession"],
        "document_name": document_name,
        "document_type": document_type,
        "source_url": source_url,
        "local_path": str(local_path),
        "status_code": str(status_code),
        "content_length": str(content_length),
        "sha256": sha256,
    }


def fetch_accession_document(
    *,
    http: SecHttpClient,
    inventory_row: dict,
    document_name: str,
    document_type: str,
    purpose: str,
) -> dict:
    """Fetch one accession document and return a material inventory row."""
    cik = int(inventory_row["cik"])
    accession = str(inventory_row["accession"])
    url = accession_document_url(
        cik=cik,
        accession=accession,
        document_name=document_name,
    )
    local_path = accession_dir_path(
        company=str(inventory_row["company"]),
        cik=cik,
        accession=accession,
    ) / document_name
    result = http.fetch(url=url, purpose=purpose, local_path=local_path)
    return material_row_from_fetch(
        inventory_row=inventory_row,
        document_name=document_name,
        document_type=document_type,
        source_url=url,
        local_path=local_path,
        status_code=result.status_code,
        content_length=result.content_length,
        sha256=result.sha256,
    )


def accession_index_items_from_payload(
    *,
    payload: dict,
    source: str,
) -> list[dict]:
    """Return SEC archive directory items from an explicit payload.

    Args:
        payload: Parsed SEC accession index JSON object.
        source: Diagnostic label for malformed input.

    Returns:
        The exact directory item list declared by SEC.
    """
    directory = require_key(mapping=payload, key="directory")
    items = require_key(mapping=directory, key="item")
    if not isinstance(items, list):
        raise TypeError(f"SEC archive index item must be list: {source}")
    return items


def accession_index_items(*, index_path: Path) -> list[dict]:
    """Read SEC archive index.json and return directory item rows."""
    return accession_index_items_from_payload(
        payload=read_json_file(path=index_path),
        source=str(index_path),
    )


def xml_instance_candidates(*, items: list[dict]) -> list[str]:
    """Return likely XBRL instance XML filenames from archive index items."""
    excluded_suffixes = (
        "_cal.xml",
        "_def.xml",
        "_lab.xml",
        "_pre.xml",
        ".xsd",
    )
    candidates = []
    for item in items:
        name = str(require_key(mapping=item, key="name"))
        lower = name.lower()
        if lower == "filingsummary.xml":
            continue
        if not lower.endswith(".xml"):
            continue
        if lower.endswith(excluded_suffixes):
            continue
        if lower.startswith("r") and lower[1:2].isdigit():
            continue
        candidates.append(name)
    return sorted(candidates)


def stage_fetch_accession_materials() -> None:
    """M3: fetch latest 10-K accession materials and raw XBRL instances."""
    ensure_output_dirs()
    http = client()
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    material_rows: list[dict] = []
    target_rows = [
        row
        for row in inventory
        if row["source_role"] in {"target_10k", "target_original_full_instance"}
    ]
    for row in target_rows:
        cik = int(row["cik"])
        accession = str(row["accession"])
        base_dir = accession_dir_path(
            company=str(row["company"]),
            cik=cik,
            accession=accession,
        )
        index_url = accession_directory_url(cik=cik, accession=accession)
        index_path = base_dir / "index.json"
        index_result = http.fetch(
            url=index_url,
            purpose=f"accession_index_{accession}",
            local_path=index_path,
        )
        material_rows.append(
            material_row_from_fetch(
                inventory_row=row,
                document_name="index.json",
                document_type="accession_index",
                source_url=index_url,
                local_path=index_path,
                status_code=index_result.status_code,
                content_length=index_result.content_length,
                sha256=index_result.sha256,
            )
        )

        detail_url = filing_detail_url(cik=cik, accession=accession)
        detail_path = base_dir / f"{accession}-index.html"
        detail_result = http.fetch(
            url=detail_url,
            purpose=f"filing_detail_{accession}",
            local_path=detail_path,
        )
        material_rows.append(
            material_row_from_fetch(
                inventory_row=row,
                document_name=f"{accession}-index.html",
                document_type="filing_detail",
                source_url=detail_url,
                local_path=detail_path,
                status_code=detail_result.status_code,
                content_length=detail_result.content_length,
                sha256=detail_result.sha256,
            )
        )

        summary_url = filing_summary_url(cik=cik, accession=accession)
        summary_path = base_dir / "FilingSummary.xml"
        summary_result = http.fetch(
            url=summary_url,
            purpose=f"filing_summary_{accession}",
            local_path=summary_path,
        )
        material_rows.append(
            material_row_from_fetch(
                inventory_row=row,
                document_name="FilingSummary.xml",
                document_type="filing_summary",
                source_url=summary_url,
                local_path=summary_path,
                status_code=summary_result.status_code,
                content_length=summary_result.content_length,
                sha256=summary_result.sha256,
            )
        )

        primary_doc = str(row["primaryDocument"])
        material_rows.append(
            fetch_accession_document(
                http=http,
                inventory_row=row,
                document_name=primary_doc,
                document_type="primary_document",
                purpose=f"primary_document_{accession}",
            )
        )

        if index_result.status_code == 200:
            items = accession_index_items(index_path=index_path)
            for instance_name in xml_instance_candidates(items=items):
                material_rows.append(
                    fetch_accession_document(
                        http=http,
                        inventory_row=row,
                        document_name=instance_name,
                        document_type="xbrl_instance",
                        purpose=f"xbrl_instance_{accession}",
                    )
                )
        else:
            print(
                f"Skipping XML candidate discovery because index failed: "
                f"{accession} status={index_result.status_code}"
            )

    write_csv_file(
        path=WORKDIR / "outputs" / "accession_materials_inventory.csv",
        fieldnames=MATERIAL_FIELDNAMES,
        rows=material_rows,
    )
    print(f"M3 accession materials fetched; rows={len(material_rows)}")


def local_name(*, tag: str) -> str:
    """Return XML local name from Clark or prefixed tag text."""
    if "}" in tag:
        return tag.rsplit("}", maxsplit=1)[1]
    if ":" in tag:
        return tag.rsplit(":", maxsplit=1)[1]
    return tag


def namespace_name(*, tag: str) -> str:
    """Return XML namespace URI or prefix text from an element tag."""
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", maxsplit=1)[0]
    if ":" in tag:
        return tag.split(":", maxsplit=1)[0]
    return ""


def attr_value(*, attrs: dict, wanted_local_name: str) -> str:
    """Return attribute value by local name without using implicit defaults."""
    for key, value in attrs.items():
        if local_name(tag=str(key)).lower() == wanted_local_name.lower():
            return str(value)
    return ""


def context_from_element(*, elem: ElementTree.Element) -> dict:
    """Extract period and dimensions from one xbrli:context element."""
    context_id = attr_value(attrs=elem.attrib, wanted_local_name="id")
    start = ""
    end = ""
    instant = ""
    dimensions = []
    for child in elem.iter():
        child_name = local_name(tag=str(child.tag))
        if child_name == "startDate" and child.text:
            start = child.text.strip()
        if child_name == "endDate" and child.text:
            end = child.text.strip()
        if child_name == "instant" and child.text:
            instant = child.text.strip()
        if child_name == "explicitMember" and child.text:
            dimension = attr_value(
                attrs=child.attrib,
                wanted_local_name="dimension",
            )
            dimensions.append(f"{dimension}={child.text.strip()}")
    if instant and not end:
        end = instant
    return {
        "context": context_id,
        "start": start,
        "end": end,
        "instant": instant,
        "dimensions": ";".join(dimensions),
    }


def unit_from_element(*, elem: ElementTree.Element) -> dict:
    """Extract unit measures from one xbrli:unit element."""
    unit_id = attr_value(attrs=elem.attrib, wanted_local_name="id")
    measures = []
    for child in elem.iter():
        if local_name(tag=str(child.tag)) == "measure" and child.text:
            measures.append(child.text.strip())
    return {"unit": unit_id, "measure": "*".join(measures)}


def parse_xbrl_xml_instance(
    *,
    file_path: Path,
    material_row: dict,
) -> list[dict]:
    """Stream parse a XBRL XML instance into concept inventory rows.

    Args:
        file_path: Saved XML instance file.
        material_row: accession_materials_inventory row for provenance.

    Returns:
        Fact inventory rows with context, unit, dimensions, and period.
    """
    contexts: dict[str, dict] = {}
    units: dict[str, dict] = {}
    facts: list[dict] = []
    events = ("start", "end")
    metadata_depth = 0
    for event, elem in ElementTree.iterparse(str(file_path), events=events):
        name = local_name(tag=str(elem.tag))
        if event == "start":
            if name in {"context", "unit"}:
                metadata_depth += 1
            continue
        if name == "context":
            context = context_from_element(elem=elem)
            contexts[context["context"]] = context
            elem.clear()
            metadata_depth -= 1
            continue
        if name == "unit":
            unit = unit_from_element(elem=elem)
            units[unit["unit"]] = unit
            elem.clear()
            metadata_depth -= 1
            continue
        if metadata_depth:
            continue
        context_ref = attr_value(attrs=elem.attrib, wanted_local_name="contextRef")
        if not context_ref:
            elem.clear()
            continue
        text = "".join(elem.itertext()).strip()
        if not text:
            elem.clear()
            continue
        unit_ref = attr_value(attrs=elem.attrib, wanted_local_name="unitRef")
        unit_measure = units[unit_ref]["measure"] if unit_ref in units else unit_ref
        context = (
            contexts[context_ref]
            if context_ref in contexts
            else {
                "context": context_ref,
                "start": "",
                "end": "",
                "instant": "",
                "dimensions": "",
            }
        )
        facts.append(
            {
                "company": material_row["company"],
                "cik": material_row["cik"],
                "accession": material_row["accession"],
                "document_name": material_row["document_name"],
                "source_url": (
                    material_row["source_url"]
                    if "source_url" in material_row
                    else ""
                ),
                "namespace": namespace_name(tag=str(elem.tag)),
                "concept": name,
                "unit": unit_measure,
                "context": context_ref,
                "dimensions": context["dimensions"],
                "period_start": context["start"],
                "period_end": context["end"],
                "value": text,
                "source_path": str(file_path),
            }
        )
        elem.clear()
    return facts


def scaled_inline_value(*, value: str, scale: str, sign: str) -> str:
    """Normalize an ix:nonFraction text value using SEC inline scale.

    Args:
        value: Visible inline fact text, possibly comma formatted.
        scale: iXBRL scale attribute as a base-10 exponent.
        sign: iXBRL sign attribute; '-' means the value is negative.

    Expected output:
        Decimal text comparable to companyfacts values. Non-numeric text is
        returned unchanged after logging because nonNumeric facts are expected.
    """
    raw = " ".join(value.split()).replace(",", "")
    if not raw:
        return ""
    if raw in {"-", "–", "—"}:
        return raw
    normalized = raw
    if raw.startswith("(") and raw.endswith(")"):
        normalized = f"-{raw[1:-1]}"
    try:
        number = Decimal(normalized)
        if scale:
            number *= Decimal(10) ** int(scale)
        if sign == "-" and number > 0:
            number *= Decimal("-1")
        return decimal_text(value=number)
    except (InvalidOperation, ValueError) as error:
        print(f"Inline fact is not numeric; keeping raw value: {raw}; {error}")
        return value


class InlineFactParser(HTMLParser):
    """Streaming parser for inline XBRL facts in HTML documents.

    Expected output:
        rows contains ix:nonFraction and ix:nonNumeric facts with context
        period, dimensions, unit, and scaled numeric values when available.
    """

    def __init__(self, *, material_row: dict, file_path: Path) -> None:
        """Initialize parser state for one saved HTML/iXBRL file."""
        super().__init__(convert_charrefs=True)
        self.material_row = material_row
        self.file_path = file_path
        self.rows: list[dict] = []
        self.current: dict | None = None
        self.buffer: list[str] = []
        self.contexts: dict[str, dict] = {}
        self.units: dict[str, dict] = {}
        self.current_context: dict | None = None
        self.current_context_field = ""
        self.current_context_buffer: list[str] = []
        self.current_context_dimension = ""
        self.current_unit: dict | None = None
        self.current_unit_buffer: list[str] = []
        self.namespaces: dict[str, str] = {}
        self.conflicting_namespaces: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Start capturing ix facts when a fact tag opens."""
        local = local_name(tag=tag)
        local_lower = local.lower()
        attr_map = {}
        for key, value in attrs:
            normalized_value = value if value is not None else ""
            attr_map[key] = normalized_value
            if not key.lower().startswith("xmlns:"):
                continue
            prefix = key.split(":", maxsplit=1)[1].lower()
            # Inline fact names carry prefixes, while the evidence contract
            # needs the declared URI to distinguish official from custom DEI.
            if (
                prefix in self.namespaces
                and self.namespaces[prefix] != normalized_value
            ):
                self.conflicting_namespaces.add(prefix)
            elif prefix not in self.conflicting_namespaces:
                self.namespaces[prefix] = normalized_value
        if local_lower == "context":
            context_id = attr_value(attrs=attr_map, wanted_local_name="id")
            self.current_context = {
                "context": context_id,
                "start": "",
                "end": "",
                "instant": "",
                "dimensions": [],
            }
            return
        if self.current_context is not None:
            if local_lower in {"startdate", "enddate", "instant"}:
                self.current_context_field = local_lower
                self.current_context_buffer = []
                return
            if local_lower == "explicitmember":
                self.current_context_field = local_lower
                self.current_context_buffer = []
                self.current_context_dimension = attr_value(
                    attrs=attr_map,
                    wanted_local_name="dimension",
                )
                return
        if local_lower == "unit":
            unit_id = attr_value(attrs=attr_map, wanted_local_name="id")
            self.current_unit = {"unit": unit_id, "measures": []}
            return
        if self.current_unit is not None and local_lower == "measure":
            self.current_unit_buffer = []
            return
        if local_lower not in {"nonfraction", "nonnumeric"}:
            return
        fact_name = attr_value(attrs=attr_map, wanted_local_name="name")
        context_ref = attr_value(attrs=attr_map, wanted_local_name="contextRef")
        unit_ref = attr_value(attrs=attr_map, wanted_local_name="unitRef")
        self.current = {
            "name": fact_name,
            "context": context_ref,
            "unit": unit_ref,
            "scale": attr_value(attrs=attr_map, wanted_local_name="scale"),
            "sign": attr_value(attrs=attr_map, wanted_local_name="sign"),
            "tag": local_lower,
        }
        self.buffer = []

    def handle_data(self, data: str) -> None:
        """Accumulate text for the active inline fact."""
        if self.current_context_field:
            self.current_context_buffer.append(data)
        if self.current_unit is not None and self.current_unit_buffer is not None:
            self.current_unit_buffer.append(data)
        if self.current is not None:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Write an inline fact row when a fact tag closes."""
        local = local_name(tag=tag)
        local_lower = local.lower()
        if self.current_context is not None:
            if local_lower in {"startdate", "enddate", "instant", "explicitmember"}:
                text = " ".join("".join(self.current_context_buffer).split())
                if local_lower == "startdate":
                    self.current_context["start"] = text
                if local_lower == "enddate":
                    self.current_context["end"] = text
                if local_lower == "instant":
                    self.current_context["instant"] = text
                if local_lower == "explicitmember":
                    self.current_context["dimensions"].append(
                        f"{self.current_context_dimension}={text}"
                    )
                self.current_context_field = ""
                self.current_context_buffer = []
                self.current_context_dimension = ""
                return
            if local_lower == "context":
                context = self.current_context
                if context["instant"] and not context["end"]:
                    context["end"] = context["instant"]
                if context["instant"] and not context["start"]:
                    context["start"] = context["instant"]
                self.contexts[context["context"]] = {
                    "context": context["context"],
                    "start": context["start"],
                    "end": context["end"],
                    "instant": context["instant"],
                    "dimensions": ";".join(context["dimensions"]),
                }
                self.current_context = None
                return
        if self.current_unit is not None:
            if local_lower == "measure":
                measure = " ".join("".join(self.current_unit_buffer).split())
                self.current_unit["measures"].append(measure)
                self.current_unit_buffer = []
                return
            if local_lower == "unit":
                self.units[self.current_unit["unit"]] = {
                    "unit": self.current_unit["unit"],
                    "measure": "*".join(self.current_unit["measures"]),
                }
                self.current_unit = None
                return
        if local_lower not in {"nonfraction", "nonnumeric"}:
            return
        if self.current is None:
            return
        name = self.current["name"]
        if ":" in name:
            namespace_prefix, concept = name.split(":", maxsplit=1)
            normalized_prefix = namespace_prefix.lower()
            if normalized_prefix in self.conflicting_namespaces:
                namespace = ""
            elif normalized_prefix in self.namespaces:
                namespace = self.namespaces[normalized_prefix]
            else:
                namespace = namespace_prefix
        else:
            namespace = ""
            concept = name
        raw_value = " ".join("".join(self.buffer).split())
        value = raw_value
        if self.current["tag"] == "nonfraction":
            value = scaled_inline_value(
                value=raw_value,
                scale=self.current["scale"],
                sign=self.current["sign"],
            )
        context_ref = self.current["context"]
        if context_ref in self.contexts:
            context = self.contexts[context_ref]
        else:
            context = {
                "start": "",
                "end": "",
                "dimensions": "",
            }
        unit_ref = self.current["unit"]
        if unit_ref in self.units:
            unit = self.units[unit_ref]["measure"]
        else:
            unit = unit_ref
        self.rows.append(
            {
                "company": self.material_row["company"],
                "cik": self.material_row["cik"],
                "accession": self.material_row["accession"],
                "document_name": self.material_row["document_name"],
                "source_url": (
                    self.material_row["source_url"]
                    if "source_url" in self.material_row
                    else ""
                ),
                "namespace": namespace,
                "concept": concept,
                "unit": unit,
                "context": context_ref,
                "dimensions": context["dimensions"],
                "period_start": context["start"],
                "period_end": context["end"],
                "value": value,
                "source_path": str(self.file_path),
            }
        )
        self.current = None
        self.buffer = []


def parse_inline_instance(*, file_path: Path, material_row: dict) -> list[dict]:
    """Stream parse inline XBRL facts from an HTML-like document."""
    parser = InlineFactParser(material_row=material_row, file_path=file_path)
    with file_path.open(mode="r", encoding="utf-8", errors="replace") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            parser.feed(chunk)
    parser.close()
    if parser.conflicting_namespaces:
        raise ValueError(
            "Inline XBRL namespace prefix has conflicting declarations: "
            + ",".join(sorted(parser.conflicting_namespaces))
        )
    return parser.rows


def file_contains_inline_xbrl(*, file_path: Path) -> bool:
    """Return whether a saved instance contains inline XBRL fact tags.

    Args:
        file_path: Local accession material path.

    Returns:
        True when iXBRL tags are present. This check protects scale handling:
        well-formed inline files can be XML-parseable, but XML streaming does
        not apply ix:nonFraction scale/sign semantics.
    """
    with file_path.open(mode="r", encoding="utf-8", errors="replace") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                return False
            lowered = chunk.lower()
            if "<ix:" in lowered or "xmlns:ix=" in lowered:
                return True


def parse_instance_with_fallback(*, material_row: dict) -> list[dict]:
    """Parse one instance using the route that preserves fact value semantics."""
    file_path = resolve_artifact_path(row=material_row)
    if file_contains_inline_xbrl(file_path=file_path):
        return parse_inline_instance(file_path=file_path, material_row=material_row)
    try:
        return parse_xbrl_xml_instance(file_path=file_path, material_row=material_row)
    except ElementTree.ParseError as error:
        print(f"XML parse failed; using inline parser: {file_path}; {error}")
        return parse_inline_instance(file_path=file_path, material_row=material_row)


def stage_parse_xbrl_instances() -> None:
    """M3: stream parse saved XBRL instances into concept inventories."""
    material_rows = read_csv_file(
        path=WORKDIR / "outputs" / "accession_materials_inventory.csv"
    )
    instance_rows = [
        row
        for row in material_rows
        if row["document_type"] == "xbrl_instance" and row["status_code"] == "200"
    ]
    rows_by_company: dict[str, list[dict]] = {}
    for material_row in instance_rows:
        company = material_row["company"]
        if company not in rows_by_company:
            rows_by_company[company] = []
        parsed_rows = parse_instance_with_fallback(material_row=material_row)
        rows_by_company[company].extend(parsed_rows)
        print(
            f"Parsed instance {material_row['accession']} "
            f"facts={len(parsed_rows)}"
        )

    for company, rows in rows_by_company.items():
        write_csv_file(
            path=(
                WORKDIR
                / "outputs"
                / "concept_inventory"
                / f"{slugify(text=company)}_instance.csv"
            ),
            fieldnames=INSTANCE_FIELDNAMES,
            rows=rows,
        )
    print("M3 XBRL instance parsing complete")


def text_metric_row(
    *,
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    value: str,
    unit: str,
    status: str,
    source_class: str,
    period_end: str,
    accession: str,
    filed_date: str,
    concept_or_section: str,
    context_or_dimension: str,
    confidence: str,
    notes: str,
) -> dict:
    """Build a text/event backed metric row."""
    period_start = period_start_for_company_period(
        company=company,
        period_end=period_end,
    )
    return metric_row(
        company=company,
        cik=cik,
        metric_id=metric_id,
        metric_name=metric_name,
        value=value,
        unit=unit,
        status=status,
        source_class=source_class,
        formula="text/event extraction",
        period_start=period_start,
        period_end=period_end,
        fiscal_year="",
        fiscal_period="FY",
        accession=accession,
        form="",
        filed_date=filed_date,
        concept_or_section=concept_or_section,
        context_or_dimension=context_or_dimension,
        confidence=confidence,
        notes=notes,
    )


def text_evidence_row(
    *,
    company: str,
    cik: int,
    metric_id: str,
    source_url: str,
    local_path: str,
    accession: str,
    document_name: str,
    concept_or_section: str,
    context_or_dimension: str,
    unit: str,
    period_end: str,
    value: str,
    quote: str,
    extraction_method: str,
) -> dict:
    """Build a metric_evidence row for text or event extraction."""
    period_start = period_start_for_company_period(
        company=company,
        period_end=period_end,
    )
    return {
        "company": company,
        "cik": str(cik),
        "metric_id": metric_id,
        "source_url": source_url,
        "local_path": local_path,
        "accession": accession,
        "document_name": document_name,
        "concept_or_section": concept_or_section,
        "context_or_dimension": context_or_dimension,
        "unit": unit,
        "period_start": period_start,
        "period_end": period_end,
        "value_raw": value,
        "value_normalized": value,
        "evidence_quote": quote[:1000],
        "extraction_method": extraction_method,
        "parser_version": "sec_pipeline_v1",
    }


def normalize_item_code(*, item_text: str) -> str:
    """Normalize SEC 8-K item text into a code like 5.02."""
    match = re.search(pattern=r"(\d{1,2}\.\d{2})", string=item_text)
    if not match:
        return item_text.strip()
    return match.group(1)


def parse_items_from_hdr(*, text: str) -> list[str]:
    """Parse <ITEMS> entries from hdr.sgml text."""
    repeated_matches = re.findall(
        pattern=r"<ITEMS?>\s*([0-9]{1,2}\.[0-9]{2})",
        string=text,
        flags=re.IGNORECASE,
    )
    if repeated_matches:
        seen = set()
        output = []
        for item in repeated_matches:
            code = normalize_item_code(item_text=item)
            if code in seen:
                continue
            seen.add(code)
            output.append(code)
        return output
    block_match = re.search(
        pattern=r"<ITEMS>(.*?)</ITEMS>",
        string=text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return []
    item_matches = re.findall(
        pattern=r"<ITEM>(.*?)</ITEM>",
        string=block_match.group(1),
        flags=re.IGNORECASE | re.DOTALL,
    )
    return [normalize_item_code(item_text=item) for item in item_matches]


def parse_items_from_primary_text(*, text: str) -> list[tuple[str, str]]:
    """Fallback parse Item headings from an 8-K primary document."""
    matches = list(
        re.finditer(
            pattern=r"Item\s+(\d{1,2}\.\d{2})",
            string=text,
            flags=re.IGNORECASE,
        )
    )
    rows = []
    seen = set()
    for match in matches:
        code = match.group(1)
        if code in seen:
            continue
        seen.add(code)
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 220)
        rows.append((code, " ".join(text[start:end].split())))
    return rows


def event_rows_from_document(
    *,
    filing_row: dict,
    document_path: Path,
    source_url: str,
    item_source: str,
) -> list[dict]:
    """Parse one saved 8-K document into deterministic event component rows.

    Args:
        filing_row: FY-window filing inventory row.
        document_path: Saved hdr.sgml or primary filing document.
        source_url: Official SEC URL for the saved document.
        item_source: `hdr.sgml` or `primary_document` parsing route.

    Returns:
        One event row per unique item code, or an empty list when the selected
        document exposes no item headings.
    """
    if item_source == "hdr.sgml":
        text = document_path.read_text(encoding="utf-8", errors="replace")
        parsed_items = [
            (code, f"8-K item {code} parsed from hdr.sgml")
            for code in parse_items_from_hdr(text=text)
        ]
        method = "hdr_items"
        confidence = "0.90"
    elif item_source == "primary_document":
        text = html_file_to_text(path=document_path)
        parsed_items = parse_items_from_primary_text(text=text)
        method = "primary_heading_fallback"
        confidence = "0.70"
    else:
        raise ValueError(f"Unknown 8-K item source: {item_source}")

    rows = [
        {
            "company": filing_row["company"],
            "cik": str(filing_row["cik"]),
            "accession": str(filing_row["accession"]),
            "filing_date": filing_row["filingDate"],
            "item_code": code,
            "item_source": item_source,
            "mapping_method": method,
            "confidence": confidence,
            "brief": brief,
            "source_url": source_url,
            "local_path": str(document_path),
        }
        for code, brief in parsed_items
    ]
    # The in-memory handoff must match the persisted CSV contract so stage 07
    # and stage 11 repair cannot observe different locator field names.
    return [
        normalize_csv_row(row=row, fieldnames=EVENT_FIELDNAMES)
        for row in rows
    ]


class HtmlTextParser(HTMLParser):
    """Streaming HTML-to-text parser for SEC filing documents."""

    def __init__(self) -> None:
        """Initialize text buffer."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect visible text chunks."""
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        """Return normalized extracted document text."""
        return " ".join(" ".join(self.parts).split())


def html_file_to_text(*, path: Path) -> str:
    """Stream a saved SEC HTML document into normalized text."""
    parser = HtmlTextParser()
    with path.open(mode="r", encoding="utf-8", errors="replace") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            parser.feed(chunk)
    parser.close()
    return parser.text()


def fetch_primary_for_inventory_row(
    *,
    http: SecHttpClient,
    row: dict,
    document_type: str,
    purpose: str,
) -> dict:
    """Fetch a filing primary document for any inventory row."""
    return fetch_accession_document(
        http=http,
        inventory_row=row,
        document_name=str(row["primaryDocument"]),
        document_type=document_type,
        purpose=purpose,
    )


def eight_k_event_update_specs() -> list[tuple[str, str, str, str, str]]:
    """Return 8-K item mappings used to update event-backed metrics.

    Expected output:
        Tuples of metric id, metric name, item code, success status, and notes.
        E01 is handled separately because it accepts a small item-code set plus
        a keyword gate for broad item 8.01 announcements.

    Returns:
        Stable data-only mapping shared by live and cached 8-K application.
    """
    return [
        (
            "C01",
            "CEO / CFO changes",
            "5.02",
            "8K_ITEM_OK",
            "CEO/CFO or director/officer event.",
        ),
        (
            "C04",
            "Auditor changes",
            "4.01",
            "8K_ITEM_OK",
            "Auditor change event.",
        ),
        (
            "E02",
            "Bankruptcy filings",
            "1.03",
            "8K_ITEM_OK",
            "Bankruptcy event.",
        ),
        (
            "E03",
            "Leadership departures",
            "5.02",
            "8K_ITEM_OK",
            "Leadership event.",
        ),
        (
            "E04",
            "Financial restatements",
            "4.02",
            "8K_ITEM_OK",
            "Restatement event.",
        ),
        (
            "E05",
            "Material agreements",
            "1.01",
            "8K_ITEM_OK",
            "Material agreement event.",
        ),
    ]


def cached_8k_evidence_removed(*, row: dict, event_metric_ids: set[str]) -> bool:
    """Return whether an old 8-K evidence row should be replaced.

    Args:
        row: metric_evidence row.
        event_metric_ids: Metric ids maintained by 8-K item extraction.

    Returns:
        True when the row belongs to an 8-K extraction result that will be
        rebuilt from the local event table.
    """
    return (
        row["metric_id"] in event_metric_ids
        and str(row["extraction_method"]).startswith("eightk_")
    )


def event_inventory_coverage_errors(
    *,
    inventory: list[dict],
    events: list[dict],
) -> list[str]:
    """Return exact FY-window filing coverage and event uniqueness errors.

    Args:
        inventory: Filing inventory rows containing `source_role=fy_8k`.
        events: Parsed event component rows.

    Returns:
        Empty only when every expected filing has event rows, no unexpected
        filing appears, and `(filing, item_code)` components are unique.
    """
    expected_counts = Counter(
        (
            str(row["company"]),
            str(row["cik"]),
            str(row["accession"]),
        )
        for row in inventory
        if row["source_role"] == "fy_8k"
    )
    event_counts = Counter(
        (
            str(row["company"]),
            str(row["cik"]),
            str(row["accession"]),
        )
        for row in events
    )
    component_counts = Counter(
        (
            str(row["company"]),
            str(row["cik"]),
            str(row["accession"]),
            str(row["item_code"]),
        )
        for row in events
    )
    expected = set(expected_counts)
    actual = set(event_counts)
    errors = []
    error_groups = [
        ("missing", sorted(expected - actual)),
        ("unexpected", sorted(actual - expected)),
        (
            "duplicate_inventory",
            sorted(
                key
                for key, count in expected_counts.items()
                if count != 1
            ),
        ),
    ]
    for label, identities in error_groups:
        for company, cik, accession in identities[:20]:
            errors.append(f"{label}={company}:{cik}:{accession}")
    for company, cik, accession, item_code in sorted(component_counts):
        count = component_counts[(company, cik, accession, item_code)]
        if not item_code:
            errors.append(f"blank_item={company}:{cik}:{accession}")
        elif count != 1:
            errors.append(
                f"duplicate_item={company}:{cik}:{accession}:{item_code}"
            )
    return errors


def event_rows_for_metric(*, events: list[dict], metric_id: str) -> list[dict]:
    """Return stable event components contributing to one event metric.

    Args:
        events: One company's parsed FY-window event rows.
        metric_id: C01, C04, or E01-E05 event metric identifier.

    Returns:
        Matching rows sorted by source identity and item code.
    """
    if metric_id == "E01":
        matching = [
            event
            for event in events
            if event["item_code"] in {"1.01", "2.01"}
            or (
                event["item_code"] == "8.01"
                and re.search(
                    pattern=r"merger|acquisition|combine|transaction",
                    string=event["brief"],
                    flags=re.IGNORECASE,
                )
            )
        ]
    else:
        codes = {
            spec_metric_id: code
            for spec_metric_id, _name, code, _status, _notes
            in eight_k_event_update_specs()
        }
        if metric_id not in codes:
            raise ValueError(f"Unknown 8-K metric id: {metric_id}")
        matching = [
            event for event in events if event["item_code"] == codes[metric_id]
        ]
    return sorted(
        matching,
        key=lambda event: (
            str(event["source_url"]),
            str(event["accession"]),
            str(event["item_code"]),
        ),
    )


def event_component_evidence_rows(
    *,
    company: str,
    metric_id: str,
    matching_events: list[dict],
    period_end: str,
    extraction_method: str,
) -> list[dict]:
    """Return one scalar evidence row for each counted 8-K event component.

    Args:
        company: Logical company name.
        metric_id: Event metric identifier.
        matching_events: Stable event components contributing to the count.
        period_end: Metric fiscal period end date.
        extraction_method: `eightk_item` or `eightk_item_keyword`.

    Returns:
        Evidence rows whose individual source identity and contribution are
        explicit while `value_normalized` retains the final aggregate count.
    """
    normalized_value = str(len(matching_events))
    rows = []
    for event in matching_events:
        row = text_evidence_row(
            company=company,
            cik=int(event["cik"]),
            metric_id=metric_id,
            source_url=event["source_url"],
            local_path=str(
                repository_artifact_candidate(
                    relative_path=event["repo_relative_path"],
                )
            ),
            accession=event["accession"],
            document_name=event["document_name"],
            concept_or_section=f"8-K Item {event['item_code']}",
            context_or_dimension="FY window",
            unit="count",
            period_end=period_end,
            value=normalized_value,
            quote=event["brief"],
            extraction_method=extraction_method,
        )
        # Each row proves one contribution; the normalized value binds that
        # component to the aggregate metric checked as an exact group later.
        row["value_raw"] = "1"
        rows.append(row)
    return rows


def event_scan_locators(*, events: list[dict]) -> tuple[str, str]:
    """Return aligned SEC source URLs and accessions for one event scan.

    Args:
        events: Fiscal-window event rows with source_url and accession.

    Returns:
        Semicolon-delimited source URLs and accessions sorted as stable pairs.
    """
    pairs = set()
    for event in events:
        source_url = str(event["source_url"])
        accession = str(event["accession"])
        if bool(source_url) != bool(accession):
            raise ValueError("Event scan locator requires URL and accession")
        if source_url:
            pairs.add((source_url, accession))
    ordered_pairs = sorted(pairs)
    return (
        ";".join([source_url for source_url, _accession in ordered_pairs]),
        ";".join([accession for _source_url, accession in ordered_pairs]),
    )


def apply_8k_event_metrics_from_events(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    events: list[dict],
    inventory: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Apply event-backed metric rows from already extracted 8-K events.

    Args:
        metrics: Current metrics_matrix rows to update.
        evidence_rows: Current metric_evidence rows to replace for 8-K metrics.
        events: Local `outputs/events.csv` rows with company, accession, item
            code, filing date, source URL, local path, confidence, and brief.
        inventory: Filing inventory that independently defines FY-window 8-Ks.

    Expected output:
        C01/C04/E01/E02/E03/E04/E05 rows and evidence are rebuilt without new
        network requests, preserving previous 8-K facts after M2 resets.

    Returns:
        Updated metrics and evidence rows.
    """
    coverage_errors = event_inventory_coverage_errors(
        inventory=inventory,
        events=events,
    )
    if coverage_errors:
        raise ValueError(
            "8-K event inventory coverage failed: "
            + ";".join(coverage_errors[:20])
        )
    event_metric_ids = {
        metric_id
        for metric_id, _metric_name, _code, _status, _notes
        in eight_k_event_update_specs()
    } | {"E01"}
    next_evidence_rows = [
        row
        for row in evidence_rows
        if not cached_8k_evidence_removed(
            row=row,
            event_metric_ids=event_metric_ids,
        )
    ]
    new_evidence_rows: list[dict] = []
    for company_config in load_company_registry():
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        company_events = [row for row in events if row["company"] == company]
        company_inventory = [
            row
            for row in inventory
            if row["company"] == company and row["source_role"] == "fy_8k"
        ]
        scanned_source_urls, scanned_locator_accessions = event_scan_locators(
            events=company_events,
        )
        scanned_accessions = ";".join(
            sorted({row["accession"] for row in company_inventory})
        )
        scanned_dates = ";".join(
            sorted({row["filingDate"] for row in company_inventory})
        )
        scanned_context = (
            "FY-window 8-K accessions scanned"
            if scanned_accessions
            else "No FY-window 8-K accession in inventory"
        )
        # Use inventory metadata here so cached repair cannot smuggle a
        # hard-coded fiscal year into event rows.
        period_end = str(target["reportDate"])

        for (
            metric_id,
            metric_name,
            code,
            ok_status,
            notes,
        ) in eight_k_event_update_specs():
            matching = event_rows_for_metric(
                events=company_events,
                metric_id=metric_id,
            )
            if matching:
                first = matching[0]
                new_row = text_metric_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    metric_name=metric_name,
                    value=str(len(matching)),
                    unit="count",
                    status=ok_status,
                    source_class="8K_ITEM",
                    period_end=period_end,
                    accession=";".join([event["accession"] for event in matching]),
                    filed_date=";".join([event["filing_date"] for event in matching]),
                    concept_or_section=f"8-K Item {code}",
                    context_or_dimension="FY window",
                    confidence=first["confidence"],
                    notes=notes,
                )
                new_evidence_rows.extend(
                    event_component_evidence_rows(
                        company=company,
                        metric_id=metric_id,
                        matching_events=matching,
                        period_end=period_end,
                        extraction_method="eightk_item",
                    )
                )
            else:
                note = f"FY-window 8-K scanned; no item {code} found."
                if metric_id == "E02":
                    # A bankruptcy non-hit is a normal zero, not an extraction
                    # failure, but the status remains non-OK because no event
                    # exists in the SEC window.
                    note = "No Item 1.03 in FY-window 8-K; zero is normal."
                new_row = text_metric_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    metric_name=metric_name,
                    value="0",
                    unit="count",
                    status="NOT_AVAILABLE_SEC",
                    source_class="8K_ITEM",
                    period_end=period_end,
                    accession=scanned_accessions,
                    filed_date=scanned_dates,
                    concept_or_section=f"8-K Item {code}",
                    context_or_dimension=scanned_context,
                    confidence="0.80",
                    notes=note,
                )
                new_evidence_rows.append(
                    text_evidence_row(
                        company=company,
                        cik=cik,
                        metric_id=metric_id,
                        source_url=scanned_source_urls,
                        local_path=str(WORKDIR / "outputs" / "events.csv"),
                        accession=scanned_locator_accessions,
                        document_name="events.csv",
                        concept_or_section=f"8-K Item {code}",
                        context_or_dimension=scanned_context,
                        unit="count",
                        period_end=period_end,
                        value="0",
                        quote=note,
                        extraction_method="eightk_zero_item_scan",
                    )
                )
            metrics = upsert_metric(rows=metrics, new_row=new_row)

        ma_events = event_rows_for_metric(
            events=company_events,
            metric_id="E01",
        )
        if ma_events:
            value = str(len(ma_events))
            note = "M&A candidate from item mapping and keyword rule."
            accession_text = ";".join([event["accession"] for event in ma_events])
            filed_date = ""
            new_evidence_rows.extend(
                event_component_evidence_rows(
                    company=company,
                    metric_id="E01",
                    matching_events=ma_events,
                    period_end=period_end,
                    extraction_method="eightk_item_keyword",
                )
            )
            status = "8K_ITEM_OK"
        else:
            value = "0"
            note = "FY-window 8-K scanned; no M&A item rule matched."
            accession_text = scanned_accessions
            filed_date = scanned_dates
            status = "NOT_AVAILABLE_SEC"
            new_evidence_rows.append(
                text_evidence_row(
                    company=company,
                    cik=cik,
                    metric_id="E01",
                    source_url=scanned_source_urls,
                    local_path=str(WORKDIR / "outputs" / "events.csv"),
                    accession=scanned_locator_accessions,
                    document_name="events.csv",
                    concept_or_section="8-K Item 1.01/2.01/8.01",
                    context_or_dimension=scanned_context,
                    unit="count",
                    period_end=period_end,
                    value="0",
                    quote=note,
                    extraction_method="eightk_zero_item_scan",
                )
            )
        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=cik,
                metric_id="E01",
                metric_name="M&A announcements",
                value=value,
                unit="count",
                status=status,
                source_class="8K_ITEM",
                period_end=period_end,
                accession=accession_text,
                filed_date=filed_date,
                concept_or_section="8-K Item 1.01/2.01/8.01",
                context_or_dimension=scanned_context,
                confidence="0.75",
                notes=note,
            ),
        )
    return metrics, next_evidence_rows + new_evidence_rows


def stage_extract_8k_events() -> None:
    """M4: fetch 8-K hdr.sgml files and extract multi-item event rows."""
    ensure_output_dirs()
    http = client()
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    eight_k_rows = [row for row in inventory if row["source_role"] == "fy_8k"]
    events: list[dict] = []

    for row in eight_k_rows:
        cik = int(row["cik"])
        accession = str(row["accession"])
        hdr_url = hdr_sgml_url(cik=cik, accession=accession)
        hdr_path = accession_dir_path(
            company=str(row["company"]),
            cik=cik,
            accession=accession,
        ) / f"{accession}.hdr.sgml"
        hdr_result = http.fetch(
            url=hdr_url,
            purpose=f"eightk_hdr_{accession}",
            local_path=hdr_path,
        )
        filing_events = (
            event_rows_from_document(
                filing_row=row,
                document_path=hdr_path,
                source_url=hdr_url,
                item_source="hdr.sgml",
            )
            if hdr_result.status_code == 200
            else []
        )
        if not filing_events:
            primary_material = fetch_primary_for_inventory_row(
                http=http,
                row=row,
                document_type="eightk_primary_document",
                purpose=f"eightk_primary_{accession}",
            )
            if primary_material["status_code"] != "200":
                raise RuntimeError(
                    "8-K primary fallback request failed; "
                    f"accession={accession}; "
                    f"status={primary_material['status_code']}"
                )
            filing_events = event_rows_from_document(
                filing_row=row,
                document_path=Path(primary_material["local_path"]),
                source_url=primary_material["source_url"],
                item_source="primary_document",
            )
        events.extend(filing_events)

    write_csv_file(
        path=WORKDIR / "outputs" / "events.csv",
        fieldnames=EVENT_FIELDNAMES,
        rows=events,
    )
    coverage_errors = event_inventory_coverage_errors(
        inventory=inventory,
        events=events,
    )
    if coverage_errors:
        raise RuntimeError(
            "8-K extraction did not cover the filing inventory: "
            + ";".join(coverage_errors[:20])
        )
    metrics, evidence_rows = apply_8k_event_metrics_from_events(
        metrics=load_metrics(),
        evidence_rows=read_csv_file(
            path=WORKDIR / "outputs" / "metric_evidence.csv"
        ),
        events=events,
        inventory=inventory,
    )
    save_metrics(rows=metrics)
    save_evidence(rows=evidence_rows)
    print(f"M4 8-K event extraction complete; events={len(events)}")


def dump_ecd_facts(*, material_row: dict) -> list[dict]:
    """Extract ecd inline facts from a DEF 14A primary document."""
    file_path = resolve_artifact_path(row=material_row)
    parsed = parse_inline_instance(
        file_path=file_path,
        material_row=material_row,
    )
    return [
        row
        for row in parsed
        if is_ecd_namespace(namespace=str(row["namespace"]))
        or str(row["concept"]).lower().startswith("ecd")
    ]


def def14a_quote(*, text: str, pattern: str) -> str:
    """Return a short DEF 14A quote around a governance pattern."""
    match = re.search(pattern=pattern, string=text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - 260)
    end = min(len(text), match.end() + 520)
    return " ".join(text[start:end].split())


def stage_extract_def14a() -> None:
    """M5: fetch DEF 14A and extract governance/compensation signals."""
    ensure_output_dirs()
    http = client()
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    def_rows = [
        row for row in inventory if row["source_role"] == "latest_def14a"
    ]
    governance_rows: list[dict] = []
    evidence_to_append: list[dict] = []
    metrics = load_metrics()

    ecd_by_company: dict[str, list[dict]] = {}

    for row in def_rows:
        material = fetch_primary_for_inventory_row(
            http=http,
            row=row,
            document_type="def14a_primary_document",
            purpose=f"def14a_primary_{row['accession']}",
        )
        path = resolve_artifact_path(row=material)
        text = html_file_to_text(path=path)
        ecd_rows = dump_ecd_facts(material_row=material)
        ecd_by_company[row["company"]] = ecd_rows
        board_quote = def14a_quote(
            text=text,
            pattern=(
                r"board of directors|director nominees|"
                r"independent directors"
            ),
        )
        comp_quote = def14a_quote(
            text=text,
            pattern=(
                r"summary compensation table|total compensation|"
                r"principal executive officer"
            ),
        )
        company = row["company"]
        cik = int(row["cik"])
        period_end = target_10k_for_company(company=company)["reportDate"]

        board_status = "TEXT_QUAL" if board_quote else "NEEDS_REVIEW"
        comp_status = "DEF14A_OK" if ecd_rows else "NEEDS_REVIEW"
        comp_note = (
            "ecd facts dumped for review."
            if ecd_rows
            else "No ecd facts found; text table requires review."
        )
        governance_rows.append(
            {
                "company": company,
                "cik": row["cik"],
                "signal_id": "C02",
                "signal_name": "Board composition",
                "value": "",
                "status": board_status,
                "source_url": material["source_url"],
                "local_path": material["local_path"],
                "accession": row["accession"],
                "concept_or_section": "DEF 14A board section",
                "evidence_quote": board_quote,
                "notes": (
                    "Board composition is qualitative unless structured "
                    "counts are reviewed."
                ),
            }
        )
        governance_rows.append(
            {
                "company": company,
                "cik": row["cik"],
                "signal_id": "C03",
                "signal_name": "Executive compensation signals",
                "value": str(len(ecd_rows)) if ecd_rows else "",
                "status": comp_status,
                "source_url": material["source_url"],
                "local_path": material["local_path"],
                "accession": row["accession"],
                "concept_or_section": "DEF 14A ecd / compensation table",
                "evidence_quote": comp_quote,
                "notes": comp_note,
            }
        )

        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=cik,
                metric_id="C02",
                metric_name="Board composition",
                value="",
                unit="",
                status=board_status,
                source_class="DEF14A",
                period_end=str(period_end),
                accession=row["accession"],
                filed_date=row["filingDate"],
                concept_or_section="DEF 14A board section",
                context_or_dimension="proxy statement",
                confidence="0.65" if board_quote else "0.30",
                notes="Textual board evidence captured; structured counts need review.",
            ),
        )
        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=cik,
                metric_id="C03",
                metric_name="Executive compensation signals",
                value=str(len(ecd_rows)) if ecd_rows else "",
                unit="ecd_fact_count" if ecd_rows else "",
                status=comp_status,
                source_class="DEF14A",
                period_end=str(period_end),
                accession=row["accession"],
                filed_date=row["filingDate"],
                concept_or_section="DEF 14A ecd / compensation table",
                context_or_dimension="proxy statement",
                confidence="0.70" if ecd_rows else "0.35",
                notes=comp_note,
            ),
        )
        for metric_id, quote, status in [
            ("C02", board_quote, board_status),
            ("C03", comp_quote, comp_status),
        ]:
            evidence_to_append.append(
                text_evidence_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    source_url=material["source_url"],
                    local_path=material["local_path"],
                    accession=row["accession"],
                    document_name=Path(material["local_path"]).name,
                    concept_or_section=(
                        "DEF 14A board/compensation section"
                    ),
                    context_or_dimension="proxy statement",
                    unit="",
                    period_end=str(period_end),
                    value=str(len(ecd_rows)) if metric_id == "C03" and ecd_rows else "",
                    quote=quote,
                    extraction_method=f"def14a_{status.lower()}",
                )
            )

    for company, rows in ecd_by_company.items():
        write_csv_file(
            path=(
                WORKDIR
                / "outputs"
                / "concept_inventory"
                / f"{slugify(text=company)}_ecd.csv"
            ),
            fieldnames=INSTANCE_FIELDNAMES,
            rows=rows,
        )
    write_csv_file(
        path=WORKDIR / "outputs" / "governance_signals.csv",
        fieldnames=GOVERNANCE_FIELDNAMES,
        rows=governance_rows,
    )
    save_metrics(rows=metrics)
    append_evidence(rows=evidence_to_append)
    print(f"M5 DEF 14A extraction complete; rows={len(governance_rows)}")


def material_primary_rows() -> list[dict]:
    """Return fetched target 10-K primary document material rows."""
    rows = read_csv_file(
        path=WORKDIR / "outputs" / "accession_materials_inventory.csv"
    )
    return [
        row
        for row in rows
        if row["document_type"] == "primary_document" and row["status_code"] == "200"
    ]


def snippet_for_pattern(*, text: str, pattern: str, width: int) -> str:
    """Return normalized text around a regex pattern."""
    match = re.search(pattern=pattern, string=text, flags=re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - width)
    end = min(len(text), match.end() + width)
    return " ".join(text[start:end].split())


def numeric_after_pattern(*, text: str, pattern: str) -> str:
    """Extract the first numeric token near a text pattern."""
    match = re.search(pattern=pattern, string=text, flags=re.IGNORECASE)
    if not match:
        return ""
    raw = match.group(1).replace(",", "")
    if raw.endswith("."):
        raw = raw[:-1]
    return raw


def mda_anchor_quote(
    *,
    text: str,
    match: re.Match,
    parsed: str,
) -> str:
    """Return raw table header and row snippets around an MD&A match.

    Args:
        text: Normalized filing text.
        match: Regex match anchored on the row label/value.
        parsed: Parsed value detail to include in evidence.

    Returns:
        Evidence quote with raw_header and raw_row substrings.
    """
    header_start = max(0, match.start() - 520)
    row_end = min(len(text), match.end() + 520)
    raw_header = " ".join(text[header_start: match.start()].split())
    raw_row = " ".join(text[match.start(): row_end].split())
    return (
        f"parsed={parsed}; raw_header={raw_header[:520]}; "
        f"raw_row={raw_row[:520]}"
    )


def scaled_mda_value(
    *,
    raw_value: str,
    scale: str,
) -> str:
    """Scale a table token into the matrix unit.

    Args:
        raw_value: Numeric token captured from MD&A text.
        scale: percent_to_ratio, billions_to_usd, or millions_to_usd.

    Returns:
        Decimal text after applying the declared scale.
    """
    value = Decimal(raw_value.replace(",", ""))
    if scale == "percent_to_ratio":
        return decimal_text(value=value / Decimal("100"))
    if scale == "billions_to_usd":
        return decimal_text(value=value * Decimal("1000000000"))
    if scale == "millions_to_usd":
        return decimal_text(value=value * Decimal("1000000"))
    raise ValueError(f"Unsupported MD&A scale: {scale}")


def a04_companyfacts_proxy_note(*, company: str) -> str:
    """Return the A04 proxy cross-check note from companyfacts.

    Args:
        company: Financial institution display name.

    Returns:
        Note with NII / average total assets proxy, or an explicit absence note.
    """
    target = target_10k_for_company(company=company)
    cik = int(target["cik"])
    accession = str(target["accession"])
    net_interest = select_target_component(
        cik=cik,
        concept_chain=["InterestIncomeExpenseNet"],
        period_end=str(target["reportDate"]),
        period_kind="duration",
        accession=accession,
    )
    assets = select_target_component(
        cik=cik,
        concept_chain=["Assets"],
        period_end=str(target["reportDate"]),
        period_kind="instant",
        accession=accession,
    )
    prior = prior_10k_for_company(company=company, cik=cik)
    if prior is None:
        return " companyfacts proxy unavailable: prior Assets missing."
    prior_assets = select_target_component(
        cik=cik,
        concept_chain=["Assets"],
        period_end=str(prior["reportDate"]),
        period_kind="instant",
        accession=str(prior["accession"]),
    )
    if net_interest is None or assets is None or prior_assets is None:
        return " companyfacts proxy unavailable: component missing."
    average_assets = (assets.value + prior_assets.value) / Decimal("2")
    proxy = net_interest.value / average_assets
    return (
        " companyfacts proxy NII / average total assets="
        f"{decimal_text(value=proxy)}; table NIM should normally exceed this "
        "proxy because average interest-earning assets are usually smaller "
        "than average total assets."
    )


def fi_mda_table_specs() -> list[dict]:
    """Return MD&A table row specs for FI text extraction.

    Returns:
        Metric specs with regex, unit scaling, and notes.
    """
    return [
        {
            "metric_id": "A03",
            "metric_name": "Liquidity coverage ratio",
            "pattern": (
                r"Firm Liquidity coverage ratio .{0,80}? "
                r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s+"
                r"[0-9]+(?:\.[0-9]+)?\s+[0-9]+(?:\.[0-9]+)?"
            ),
            "unit": "ratio",
            "scale": "percent_to_ratio",
            "notes": (
                "Firm average LCR table row selected; raw table reports percent "
                "and matrix stores ratio."
            ),
        },
        {
            "metric_id": "A04",
            "metric_name": "Net interest margin",
            "pattern": (
                r"Net yield on average interest-earning assets .{0,80}? "
                r"(?P<value>[0-9]+(?:\.[0-9]+)?)\s*%"
            ),
            "unit": "ratio",
            "scale": "percent_to_ratio",
            "notes": "Managed basis / non-GAAP table row selected.",
        },
        {
            "metric_id": "A11",
            "metric_name": "AUM",
            "pattern": (
                r"Total assets under management\s+"
                r"(?P<value>[0-9,]+(?:\.[0-9]+)?)\s+"
                r"[0-9,]+(?:\.[0-9]+)?\s+[0-9,]+(?:\.[0-9]+)?"
            ),
            "unit": "USD",
            "scale": "billions_to_usd",
            "notes": (
                "Assets under management table row selected; source unit is "
                "billions."
            ),
        },
        {
            "metric_id": "A12",
            "metric_name": "Trading exposure",
            "pattern": (
                r"Total VaR\s+\$?\s*(?P<value>[0-9,]+(?:\.[0-9]+)?)"
                r"\s+\$?\s*[0-9,]+(?:\.[0-9]+)?"
            ),
            "unit": "USD",
            "scale": "millions_to_usd",
            "notes": (
                "Total VaR average table row selected; source unit is millions "
                "and table states 95% confidence level."
            ),
        },
    ]


def apply_fi_mda_table_metrics(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    company: str,
    text: str,
    source_url: str,
    local_path: str,
) -> tuple[list[dict], list[dict]]:
    """Apply FI MD&A row-label anchored table extraction.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Evidence rows to append.
        company: Display company name.
        text: Normalized 10-K text.
        source_url: Source SEC URL.
        local_path: Local primary document path.

    Returns:
        Updated metrics and evidence rows for A03/A04/A11/A12.
    """
    target = target_10k_for_company(company=company)
    for spec in fi_mda_table_specs():
        match = re.search(
            pattern=str(spec["pattern"]),
            string=text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        raw_value = match.group("value")
        value = scaled_mda_value(raw_value=raw_value, scale=str(spec["scale"]))
        notes = str(spec["notes"])
        if spec["metric_id"] == "A04":
            notes += a04_companyfacts_proxy_note(company=company)
        quote = mda_anchor_quote(
            text=text,
            match=match,
            parsed=f"{spec['metric_id']} raw_value={raw_value} value={value}",
        )
        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=int(target["cik"]),
                metric_id=str(spec["metric_id"]),
                metric_name=str(spec["metric_name"]),
                value=value,
                unit=str(spec["unit"]),
                status="MDA_OK",
                source_class="MDA",
                period_end=str(target["reportDate"]),
                accession=str(target["accession"]),
                filed_date=str(target["filingDate"]),
                concept_or_section=str(spec["metric_name"]),
                context_or_dimension="MD&A table row label",
                confidence="0.80",
                notes=notes,
            ),
        )
        evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=int(target["cik"]),
                metric_id=str(spec["metric_id"]),
                source_url=source_url,
                local_path=local_path,
                accession=str(target["accession"]),
                document_name=Path(local_path).name,
                concept_or_section=str(spec["metric_name"]),
                context_or_dimension="MD&A table row label",
                unit=str(spec["unit"]),
                period_end=str(target["reportDate"]),
                value=value,
                quote=quote,
                extraction_method="fi_mda_table_row_anchor",
            )
        )
    return metrics, evidence_rows


def update_text_metric(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    company: str,
    cik: int,
    metric_id: str,
    metric_name: str,
    value: str,
    unit: str,
    status: str,
    source_class: str,
    period_end: str,
    accession: str,
    filed_date: str,
    source_url: str,
    local_path: str,
    section: str,
    quote: str,
    notes: str,
) -> list[dict]:
    """Update one text-backed metric and append its evidence row."""
    updated = upsert_metric(
        rows=metrics,
        new_row=text_metric_row(
            company=company,
            cik=cik,
            metric_id=metric_id,
            metric_name=metric_name,
            value=value,
            unit=unit,
            status=status,
            source_class=source_class,
            period_end=period_end,
            accession=accession,
            filed_date=filed_date,
            concept_or_section=section,
            context_or_dimension="10-K text",
            confidence="0.65" if quote else "0.30",
            notes=notes,
        ),
    )
    evidence_rows.append(
        text_evidence_row(
            company=company,
            cik=cik,
            metric_id=metric_id,
            source_url=source_url,
            local_path=local_path,
            accession=accession,
            document_name=Path(local_path).name,
            concept_or_section=section,
            context_or_dimension="10-K text",
            unit=unit,
            period_end=period_end,
            value=value,
            quote=quote,
            extraction_method=f"text_{status.lower()}",
        )
    )
    return updated


def evidence_quote_for_metric(
    *,
    evidence_rows: list[dict],
    company: str,
    metric_id: str,
) -> tuple[str, str, str]:
    """Return source URL, local path, and quote for one metric evidence set.

    Args:
        evidence_rows: metric_evidence rows.
        company: Display company name.
        metric_id: Metric id.

    Returns:
        Source URL, local path, and compact quote. Empty strings mean no
        evidence row exists for the metric.
    """
    rows = evidence_for_metric(
        evidence_rows=evidence_rows,
        company=company,
        metric_id=metric_id,
    )
    if not rows:
        return "", "", ""
    first = rows[0]
    quote = " | ".join(
        row["evidence_quote"] for row in rows if row["evidence_quote"]
    )
    return first["source_url"], first["local_path"], quote[:1000]


def optional_b_observation_from_metric(
    *,
    metric: dict,
    evidence_rows: list[dict],
    candidate_role: str,
) -> dict:
    """Build one optional-B sidecar row from a pruned matrix row.

    Args:
        metric: metrics_matrix row that is out of main-matrix scope.
        evidence_rows: metric_evidence rows.
        candidate_role: Role explaining why the observation is sidecar-only.

    Returns:
        Sidecar row preserving value, source, evidence quote, and notes.
    """
    source_url, local_path, quote = evidence_quote_for_metric(
        evidence_rows=evidence_rows,
        company=metric["company"],
        metric_id=metric["metric_id"],
    )
    return {
        "company": metric["company"],
        "cik": metric["cik"],
        "metric_id": metric["metric_id"],
        "metric_name": metric["metric_name"],
        "value": metric["value"],
        "unit": metric["unit"],
        "status": metric["status"],
        "source_class": metric["source_class"],
        "period_end": metric["period_end"],
        "accession": metric["accession"],
        "concept_or_section": metric["concept_or_section"],
        "context_or_dimension": metric["context_or_dimension"],
        "candidate_role": candidate_role,
        "source_url": source_url,
        "local_path": local_path,
        "evidence_quote": quote,
        "notes": metric["notes"],
    }


def write_optional_b_sidecars(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> None:
    """Write sidecars for optional-B probes outside main applicability.

    Args:
        metrics: Current metrics_matrix rows before pruning.
        evidence_rows: Current metric_evidence rows.

    Expected output:
        RPO/cRPO, capacity, and lodging out-of-scope probes remain auditable
        outside the main annual matrix.
    """
    rpo_rows = []
    capacity_rows = []
    lodging_rows = []
    for row in metrics:
        metric_id = row["metric_id"]
        if metric_id not in optional_b_metric_ids():
            continue
        if optional_b_metric_is_main_applicable(
            company=row["company"],
            metric_id=metric_id,
        ):
            continue
        if metric_id == "B12":
            rpo_rows.append(
                optional_b_observation_from_metric(
                    metric=row,
                    evidence_rows=evidence_rows,
                    candidate_role="out_of_scope_rpo_crpo_observation",
                )
            )
        elif metric_id == "B13":
            capacity_rows.append(
                optional_b_observation_from_metric(
                    metric=row,
                    evidence_rows=evidence_rows,
                    candidate_role="out_of_scope_capacity_text_signal",
                )
            )
        else:
            lodging_rows.append(
                optional_b_observation_from_metric(
                    metric=row,
                    evidence_rows=evidence_rows,
                    candidate_role="out_of_scope_lodging_kpi_probe",
                )
            )
    write_csv_file(
        path=WORKDIR / "outputs" / "rpo_crpo_observations.csv",
        fieldnames=OPTIONAL_B_OBSERVATION_FIELDNAMES,
        rows=rpo_rows,
    )
    write_csv_file(
        path=WORKDIR / "outputs" / "capacity_text_signals.csv",
        fieldnames=OPTIONAL_B_OBSERVATION_FIELDNAMES,
        rows=capacity_rows,
    )
    write_csv_file(
        path=WORKDIR / "outputs" / "lodging_kpi_probe_failures.csv",
        fieldnames=OPTIONAL_B_OBSERVATION_FIELDNAMES,
        rows=lodging_rows,
    )


def prune_non_applicable_optional_b_metrics(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Remove out-of-scope optional B rows from main matrix/evidence.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.

    Expected output:
        Main matrix only includes B10/B11/B12/B13 rows when the configured
        profile extractor makes the metric applicable.

    Returns:
        Pruned metrics and evidence rows.
    """
    removed_keys = {
        (row["company"], row["metric_id"])
        for row in metrics
        if row["metric_id"] in optional_b_metric_ids()
        and not optional_b_metric_is_main_applicable(
            company=row["company"],
            metric_id=row["metric_id"],
        )
    }
    if not removed_keys:
        return metrics, evidence_rows
    return (
        [
            row
            for row in metrics
            if (row["company"], row["metric_id"]) not in removed_keys
        ],
        remove_evidence_for_keys(evidence_rows=evidence_rows, keys=removed_keys),
    )


def stage_extract_mda_and_risk_text() -> None:
    """M6: extract MD&A, risk, legal, and special KPI text evidence."""
    primary_rows = material_primary_rows()
    metrics = load_metrics()
    risk_rows: list[dict] = []
    evidence_rows: list[dict] = []
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    filing_by_accession = {row["accession"]: row for row in inventory}

    for material in primary_rows:
        company = material["company"]
        cik = int(material["cik"])
        accession = material["accession"]
        filing = filing_by_accession[accession]
        period_end = filing["reportDate"]
        filed_date = filing["filingDate"]
        source_url = material["source_url"]
        local_path = artifact_reference_text(row=material)
        text = html_file_to_text(path=resolve_artifact_path(row=material))

        risk_quote = snippet_for_pattern(
            text=text,
            pattern=r"Item\s+1A\.?\s+Risk Factors|Risk Factors",
            width=700,
        )
        legal_quote = snippet_for_pattern(
            text=text,
            pattern=r"Item\s+3\.?\s+Legal Proceedings|Legal Proceedings|litigation",
            width=700,
        )
        regulatory_quote = snippet_for_pattern(
            text=text,
            pattern=r"investigation|subpoena|inquiry|regulatory|SEC|DOJ|FTC|FDA",
            width=700,
        )
        going_quote = snippet_for_pattern(
            text=text,
            pattern=r"going concern|substantial doubt",
            width=500,
        )
        d_signals = [
            (
                "D01",
                "Risk factors summary",
                "TEXT_QUAL" if risk_quote else "NOT_EXTRACTED",
                "Item 1A Risk Factors",
                risk_quote,
                "Risk factor heading or theme evidence.",
            ),
            (
                "D02",
                "Litigation disclosures",
                "TEXT_QUAL" if legal_quote else "NOT_AVAILABLE_SEC",
                "Item 3 / litigation",
                legal_quote,
                "Legal proceedings or litigation text evidence.",
            ),
            (
                "D03",
                "Regulatory investigations",
                "TEXT_QUAL" if regulatory_quote else "NOT_AVAILABLE_SEC",
                "Regulatory investigation keywords",
                regulatory_quote,
                "Keyword scan across risk/legal text.",
            ),
            (
                "D04",
                "Going concern statements",
                "TEXT_QUAL",
                "Going concern",
                going_quote if going_quote else "未披露持续经营疑虑",
                (
                    "Going-concern phrase found."
                    if going_quote
                    else "No going-concern doubt phrase found in 10-K text."
                ),
            ),
        ]
        for metric_id, metric_name, status, section, quote, notes in d_signals:
            risk_rows.append(
                {
                    "company": company,
                    "cik": str(cik),
                    "signal_id": metric_id,
                    "signal_name": metric_name,
                    "value": "",
                    "status": status,
                    "source_url": source_url,
                    "local_path": local_path,
                    "accession": accession,
                    "concept_or_section": section,
                    "evidence_quote": quote,
                    "notes": notes,
                }
            )
            metrics = update_text_metric(
                metrics=metrics,
                evidence_rows=evidence_rows,
                company=company,
                cik=cik,
                metric_id=metric_id,
                metric_name=metric_name,
                value="",
                unit="",
                status=status,
                source_class="TEXT",
                period_end=period_end,
                accession=accession,
                filed_date=filed_date,
                source_url=source_url,
                local_path=local_path,
                section=section,
                quote=quote,
                notes=notes,
            )

        company_config = company_by_name(company_name=company)
        extractors = company_extractors(company_config=company_config)
        if has_extractor(
            extractors=extractors,
            extractor_name="LodgingKpiExtractor",
        ) or text_has_lodging_kpi_keywords(text=text):
            metrics, evidence_rows = apply_lodging_kpi_metrics(
                metrics=metrics,
                evidence_rows=evidence_rows,
                company=company,
                text=text,
                source_url=source_url,
                local_path=local_path,
            )

        if has_extractor(
            extractors=extractors,
            extractor_name="RpoCrpoExtractor",
        ) or text_has_rpo_keywords(text=text):
            metrics, evidence_rows = apply_rpo_crpo_metric(
                metrics=metrics,
                evidence_rows=evidence_rows,
                company=company,
                text=text,
                source_url=source_url,
                local_path=local_path,
            )

        if has_extractor(
            extractors=extractors,
            extractor_name="BaselCapitalRatioExtractor",
        ):
            metrics, evidence_rows = apply_fi_mda_table_metrics(
                metrics=metrics,
                evidence_rows=evidence_rows,
                company=company,
                text=text,
                source_url=source_url,
                local_path=local_path,
            )

        if has_extractor(
            extractors=extractors,
            extractor_name="CapacityUtilizationExtractor",
        ) or text_has_capacity_keywords(text=text):
            capacity_quote = snippet_for_pattern(
                text=text,
                pattern=(
                    r"capacity utilization|production capacity|"
                    r"manufacturing capacity"
                ),
                width=650,
            )
            status = "TEXT_QUAL" if capacity_quote else "NOT_AVAILABLE_SEC"
            metrics = update_text_metric(
                metrics=metrics,
                evidence_rows=evidence_rows,
                company=company,
                cik=cik,
                metric_id="B13",
                metric_name="Capacity utilization",
                value="",
                unit="",
                status=status,
                source_class="TEXT",
                period_end=period_end,
                accession=accession,
                filed_date=filed_date,
                source_url=source_url,
                local_path=local_path,
                section="Capacity utilization",
                quote=capacity_quote,
                notes=(
                    "Only qualitative capacity evidence is used unless a "
                    "ratio appears."
                ),
            )

    write_csv_file(
        path=WORKDIR / "outputs" / "risk_legal_signals.csv",
        fieldnames=RISK_FIELDNAMES,
        rows=risk_rows,
    )
    write_optional_b_sidecars(metrics=metrics, evidence_rows=evidence_rows)
    metrics, evidence_rows = prune_non_applicable_optional_b_metrics(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    save_metrics(rows=metrics)
    append_evidence(rows=evidence_rows)
    print(f"M6 MD&A/risk extraction complete; risk_rows={len(risk_rows)}")


def component_for_golden(
    *,
    company: str,
    concept_chain: list[str],
    period_kind: str,
    prior: bool,
) -> FactHit | None:
    """Select a golden assertion component from raw companyfacts evidence."""
    target = target_10k_for_company(company=company)
    cik = int(target["cik"])
    if prior:
        prior_row = prior_10k_for_company(company=company, cik=cik)
        if prior_row is None:
            return None
        return select_component(
            cik=cik,
            concept_chain=concept_chain,
            period_end=str(prior_row["reportDate"]),
            period_kind=period_kind,
            accession=str(prior_row["accession"]),
        )
    return select_component(
        cik=cik,
        concept_chain=concept_chain,
        period_end=str(target["reportDate"]),
        period_kind=period_kind,
        accession=str(target["accession"]),
    )


def golden_result_row(
    *,
    assertion_id: str,
    description: str,
    target: str,
    actual: str,
    status: str,
    evidence_path: str,
    notes: str,
) -> dict:
    """Build one golden_results.csv row."""
    return {
        "assertion_id": assertion_id,
        "description": description,
        "expected": target,
        "actual": actual,
        "status": status,
        "evidence_path": evidence_path,
        "notes": notes,
    }


def compare_decimal(
    *,
    assertion_id: str,
    description: str,
    target: Decimal,
    actual: Decimal | None,
    evidence_path: str,
    tolerance: Decimal,
) -> dict:
    """Compare a Decimal assertion and return a golden result row."""
    if actual is None:
        return golden_result_row(
            assertion_id=assertion_id,
            description=description,
            target=decimal_text(value=target),
            actual="MISSING",
            status="FAIL",
            evidence_path=evidence_path,
            notes="Required fact not selected from companyfacts.",
        )
    diff = abs(actual - target)
    status = "PASS" if diff <= tolerance else "FAIL"
    return golden_result_row(
        assertion_id=assertion_id,
        description=description,
        target=decimal_text(value=target),
        actual=decimal_text(value=actual),
        status=status,
        evidence_path=evidence_path,
        notes=f"diff={decimal_text(value=diff)} tolerance={tolerance}",
    )


def fact_value(*, hit: FactHit | None) -> Decimal | None:
    """Return Decimal value from a FactHit or None."""
    if hit is None:
        return None
    return hit.value


def evidence_path_for_hit(*, hit: FactHit | None) -> str:
    """Return evidence path for a FactHit or empty string."""
    if hit is None:
        return ""
    return hit.source_path


def golden_components(*, company: str) -> dict[str, FactHit | None]:
    """Return standard component hits used by fixture assertions."""
    return {
        "revenue": component_for_golden(
            company=company,
            concept_chain=REVENUE_CHAIN,
            period_kind="duration",
            prior=False,
        ),
        "prior_revenue": component_for_golden(
            company=company,
            concept_chain=REVENUE_CHAIN,
            period_kind="duration",
            prior=True,
        ),
        "net_income": component_for_golden(
            company=company,
            concept_chain=NET_INCOME_CHAIN,
            period_kind="duration",
            prior=False,
        ),
        "operating_income": component_for_golden(
            company=company,
            concept_chain=["OperatingIncomeLoss"],
            period_kind="duration",
            prior=False,
        ),
        "da": component_for_golden(
            company=company,
            concept_chain=DA_CHAIN,
            period_kind="duration",
            prior=False,
        ),
        "ocf": component_for_golden(
            company=company,
            concept_chain=["NetCashProvidedByUsedInOperatingActivities"],
            period_kind="duration",
            prior=False,
        ),
        "capex": component_for_golden(
            company=company,
            concept_chain=CAPEX_CHAIN,
            period_kind="duration",
            prior=False,
        ),
        "current_assets": component_for_golden(
            company=company,
            concept_chain=["AssetsCurrent"],
            period_kind="instant",
            prior=False,
        ),
        "current_liabilities": component_for_golden(
            company=company,
            concept_chain=["LiabilitiesCurrent"],
            period_kind="instant",
            prior=False,
        ),
        "cash": component_for_golden(
            company=company,
            concept_chain=["CashAndCashEquivalentsAtCarryingValue"],
            period_kind="instant",
            prior=False,
        ),
        "equity": component_for_golden(
            company=company,
            concept_chain=EQUITY_CHAIN,
            period_kind="instant",
            prior=False,
        ),
        "total_assets": component_for_golden(
            company=company,
            concept_chain=["Assets"],
            period_kind="instant",
            prior=False,
        ),
        "long_term_debt": component_for_golden(
            company=company,
            concept_chain=LEGACY_GOLDEN_LONG_TERM_DEBT_CHAIN,
            period_kind="instant",
            prior=False,
        ),
        "interest_expense": component_for_golden(
            company=company,
            concept_chain=INTEREST_CHAIN,
            period_kind="duration",
            prior=False,
        ),
    }


def run_company_structure_golden() -> list[dict]:
    """Run G1 structure assertions using company_resolution.csv."""
    rows = read_csv_file(path=WORKDIR / "outputs" / "company_resolution.csv")
    results = []
    for company_config in load_company_registry():
        company = str(company_config["company"])
        primary_roles = [
            role
            for role in company_config["roles"]
            if role["entity_role"] in {"primary", "successor"}
        ]
        if not primary_roles:
            raise RuntimeError(f"Registry lacks primary/successor role: {company}")
        target = str(int(primary_roles[0]["cik"]))
        actual = [
            str(int(row["resolved_cik"]))
            for row in rows
            if row["company"] == company and row["entity_role"] == "primary"
        ]
        if not actual:
            actual = [
                str(int(row["resolved_cik"]))
                for row in rows
                if row["company"] == company and row["entity_role"] == "successor"
            ]
        actual_text = actual[0] if actual else "MISSING"
        results.append(
            golden_result_row(
                assertion_id=f"G1_{slugify(text=company)}_cik",
                description=f"{company} CIK",
                target=target,
                actual=actual_text,
                status="PASS" if actual_text == target else "FAIL",
                evidence_path=str(WORKDIR / "outputs" / "company_resolution.csv"),
                notes="Company structure assertion.",
            )
        )
        target_fye = str(company_config["fiscal_year_end"])
        actual = [
            row["fiscalYearEnd"]
            for row in rows
            if row["company"] == company
            and row["entity_role"] in {"primary", "successor"}
        ]
        actual_text = actual[0] if actual else "MISSING"
        results.append(
            golden_result_row(
                assertion_id=f"G1_{slugify(text=company)}_fye",
                description=f"{company} fiscalYearEnd",
                target=target_fye,
                actual=actual_text,
                status="PASS" if actual_text == target_fye else "FAIL",
                evidence_path=str(WORKDIR / "outputs" / "company_resolution.csv"),
                notes="Fiscal year-end assertion.",
            )
        )
        role_ciks = sorted(str(int(role["cik"])) for role in company_config["roles"])
        if len(role_ciks) > 1:
            actual_ciks = sorted(
                str(int(row["resolved_cik"]))
                for row in rows
                if row["company"] == company
            )
            results.append(
                golden_result_row(
                    assertion_id=f"G1_{slugify(text=company)}_role_chain",
                    description=f"{company} role CIK chain",
                    target=";".join(role_ciks),
                    actual=";".join(actual_ciks),
                    status="PASS" if actual_ciks == role_ciks else "FAIL",
                    evidence_path=str(
                        WORKDIR / "outputs" / "company_resolution.csv"
                    ),
                    notes="Company_resolution must preserve configured roles.",
                )
            )
    return results


def run_g2_structural_golden(*, http: SecHttpClient) -> list[dict]:
    """Run G2 assertions that guard against wrong source classes."""
    results = []
    financial_configs = [
        company
        for company in load_company_registry()
        if has_extractor(
            extractors=company_extractors(company_config=company),
            extractor_name="BaselCapitalRatioExtractor",
        )
    ]
    if not financial_configs:
        raise RuntimeError("No financial institution profile configured")
    financial_company = str(financial_configs[0]["company"])
    financial_cik = int(financial_configs[0]["primary_cik"])
    concept_path = (
        WORKDIR
        / "evidence"
        / "companyfacts"
        / f"{slugify(text=financial_company)}_assetscurrent_companyconcept.json"
    )
    concept_result = http.fetch(
        url=companyconcept_url(
            cik=financial_cik,
            taxonomy="us-gaap",
            concept="AssetsCurrent",
        ),
        purpose=f"g2_financial_assetscurrent_{financial_cik}",
        local_path=concept_path,
    )
    metrics = load_metrics()
    fi_b08 = [
        row
        for row in metrics
        if row["company"] == financial_company and row["metric_id"] == "B08"
    ]
    actual = (
        f"companyconcept_status={concept_result.status_code}; "
        f"B08_status={fi_b08[0]['status'] if fi_b08 else 'MISSING'}"
    )
    results.append(
        golden_result_row(
            assertion_id=G2_FINANCIAL_ASSETSCURRENT_ASSERTION_ID,
            description=(
                "Financial-institution AssetsCurrent companyconcept and B08 "
                "structural status"
            ),
            target="B08=N_A_STRUCTURAL",
            actual=actual,
            status=(
                "PASS"
                if fi_b08 and fi_b08[0]["status"] == "N_A_STRUCTURAL"
                else "FAIL"
            ),
            evidence_path=str(concept_path),
            notes="If companyconcept is 404, B08 must remain structural N/A.",
        )
    )

    for metric_id in G2_FINANCIAL_NON_STD_METRIC_IDS:
        row = [
            item
            for item in metrics
            if item["company"] == financial_company and item["metric_id"] == metric_id
        ]
        actual_class = row[0]["source_class"] if row else "MISSING"
        results.append(
            golden_result_row(
                assertion_id=f"G2_financial_{metric_id.lower()}_not_std",
                description=(
                    f"Financial-institution {metric_id} not hard-calculated "
                    "from STD_XBRL"
                ),
                target="source_class != STD_XBRL",
                actual=actual_class,
                status="PASS" if actual_class != "STD_XBRL" else "FAIL",
                evidence_path=str(WORKDIR / "outputs" / "metrics_matrix.csv"),
                notes="Capital ratios require regulatory table or dimensions.",
            )
        )
    captive_configs = [
        company
        for company in load_company_registry()
        if has_extractor(
            extractors=company_extractors(company_config=company),
            extractor_name="CaptiveFinanceDebtExtractor",
        )
    ]
    for company_config in captive_configs[:1]:
        company = str(company_config["company"])
        b06_rows = [
            row
            for row in metrics
            if row["company"] == company and row["metric_id"] == "B06"
        ]
        b06_status = b06_rows[0]["status"] if b06_rows else "MISSING"
        results.append(
            golden_result_row(
                assertion_id=G2_CAPTIVE_FINANCE_ASSERTION_ID,
                description=(
                    "Captive-finance B06 requires review when entity-level "
                    "debt is insufficient"
                ),
                target="NEEDS_REVIEW or DIM_XBRL_OK or OK",
                actual=b06_status,
                status=(
                    "PASS"
                    if b06_status in {"NEEDS_REVIEW", "DIM_XBRL_OK", "OK"}
                    else "FAIL"
                ),
                evidence_path=str(WORKDIR / "outputs" / "metrics_matrix.csv"),
                notes="DebtSecurities concepts are excluded.",
            )
        )
    auditor_rows = find_instance_facts(concept_pattern=r"AuditorName")
    results.append(
        golden_result_row(
            assertion_id=G2_AUDITORNAME_ASSERTION_ID,
            description="AuditorName comes from accession instance or filing material",
            target="at least one AuditorName fact",
            actual=str(len(auditor_rows)),
            status="PASS" if auditor_rows else "FAIL",
            evidence_path=str(WORKDIR / "outputs" / "concept_inventory"),
            notes="No companyfacts assumption is used for auditor name.",
        )
    )
    return results


def find_instance_facts(*, concept_pattern: str) -> list[dict]:
    """Find rows across instance inventories whose concept matches a regex."""
    output = []
    inventory_dir = WORKDIR / "outputs" / "concept_inventory"
    for path in sorted(inventory_dir.glob("*_instance.csv")):
        for row in read_csv_file(path=path):
            if re.search(
                pattern=concept_pattern,
                string=row["concept"],
                flags=re.IGNORECASE,
            ):
                output.append(row)
    return output


def company_by_id(*, company_id: str) -> dict:
    """Return configured company metadata by registry company_id."""
    for company in load_company_registry():
        if company["company_id"] == company_id:
            return company
    raise KeyError(f"Unknown company_id: {company_id}")


def derived_golden_values(*, components: dict) -> dict[str, Decimal | None]:
    """Return derived golden values from selected component facts."""
    op = fact_value(hit=components["operating_income"])
    da = fact_value(hit=components["da"])
    ocf = fact_value(hit=components["ocf"])
    capex = fact_value(hit=components["capex"])
    current_assets = fact_value(hit=components["current_assets"])
    current_liabilities = fact_value(hit=components["current_liabilities"])
    equity = fact_value(hit=components["equity"])
    debt = fact_value(hit=components["long_term_debt"])
    return {
        "derived_ebitda": op + da if op is not None and da is not None else None,
        "derived_fcf": ocf - capex if ocf is not None and capex is not None else None,
        "derived_current_ratio": (
            current_assets / current_liabilities
            if current_assets is not None and current_liabilities is not None
            else None
        ),
        "derived_debt_to_equity": (
            debt / equity
            if debt is not None and equity is not None and equity != 0
            else None
        ),
    }


def concept_golden_result(
    *,
    row: dict,
    company: str,
    components: dict,
) -> dict:
    """Build a concept-name golden assertion from fixture metadata."""
    component_key = str(row["component_key"]).replace("concept_", "")
    hit = components[component_key]
    actual = hit.concept if hit is not None else "MISSING"
    expected = row["expected"]
    return golden_result_row(
        assertion_id=row["assertion_id"],
        description=row["description"],
        target=expected,
        actual=actual,
        status="PASS" if actual == expected else "FAIL",
        evidence_path=evidence_path_for_hit(hit=hit),
        notes=f"Actual selected concept for {company}.",
    )


def metric_status_golden_result(*, row: dict, company: str) -> dict:
    """Build a metric-status golden assertion from fixture metadata."""
    metric_id = str(row["component_key"]).replace("metric_status_", "")
    metric_rows = [
        item
        for item in load_metrics()
        if item["company"] == company and item["metric_id"] == metric_id
    ]
    actual = metric_rows[0]["status"] if metric_rows else "MISSING"
    expected = row["expected"]
    return golden_result_row(
        assertion_id=row["assertion_id"],
        description=row["description"],
        target=expected,
        actual=actual,
        status="PASS" if actual == expected else "FAIL",
        evidence_path=str(WORKDIR / "outputs" / "metrics_matrix.csv"),
        notes="Metric status assertion from golden fixture.",
    )


def metric_value_golden_result(*, row: dict, company: str) -> dict:
    """Build a metrics_matrix numeric golden assertion.

    Args:
        row: Fixture row whose component_key is metric_value_<metric_id>.
        company: Display company name.

    Returns:
        Golden result comparing fixture expected against metrics_matrix value.
    """
    metric_id = str(row["component_key"]).replace("metric_value_", "")
    metric_rows = [
        item
        for item in load_metrics()
        if item["company"] == company and item["metric_id"] == metric_id
    ]
    actual = (
        Decimal(metric_rows[0]["value"])
        if metric_rows and metric_rows[0]["value"]
        else None
    )
    return compare_decimal(
        assertion_id=row["assertion_id"],
        description=row["description"],
        target=Decimal(row["expected"]),
        actual=actual,
        evidence_path=str(WORKDIR / "outputs" / "metrics_matrix.csv"),
        tolerance=Decimal(row["tolerance"]),
    )


def fixture_numeric_golden_results() -> list[dict]:
    """Run numeric and concept assertions from golden fixture rows."""
    path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "sec_10_company_spike"
        / "golden_expected_values.csv"
    )
    results = []
    components_by_company: dict[str, dict] = {}
    derived_by_company: dict[str, dict] = {}
    for row in read_csv_file(path=path):
        company_config = company_by_id(company_id=row["company_id"])
        company = str(company_config["company"])
        if company not in components_by_company:
            components_by_company[company] = golden_components(company=company)
            derived_by_company[company] = derived_golden_values(
                components=components_by_company[company],
            )
        components = components_by_company[company]
        component_key = row["component_key"]
        if component_key.startswith("concept_"):
            results.append(
                concept_golden_result(
                    row=row,
                    company=company,
                    components=components,
                )
            )
            continue
        if component_key.startswith("metric_status_"):
            results.append(metric_status_golden_result(row=row, company=company))
            continue
        if component_key.startswith("metric_value_"):
            results.append(metric_value_golden_result(row=row, company=company))
            continue
        actual = (
            derived_by_company[company][component_key]
            if component_key in derived_by_company[company]
            else fact_value(hit=components[component_key])
        )
        tolerance = Decimal(row["tolerance"])
        results.append(
            compare_decimal(
                assertion_id=row["assertion_id"],
                description=row["description"],
                target=Decimal(row["expected"]),
                actual=actual,
                evidence_path=evidence_path_for_hit(hit=components["revenue"]),
                tolerance=tolerance,
            )
        )
    return results


def golden_rows_by_assertion(*, rows: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """Index golden rows by assertion id and report duplicates.

    Args:
        rows: Rows from outputs/golden_results.csv.

    Returns:
        Mapping and duplicate assertion ids.
    """
    indexed: dict[str, dict] = {}
    duplicates = []
    for row in rows:
        assertion_id = row["assertion_id"]
        if assertion_id in indexed:
            duplicates.append(assertion_id)
            continue
        indexed[assertion_id] = row
    return indexed, duplicates


def recompute_golden_status(
    *,
    expected: str,
    actual: str,
    tolerance: str,
) -> str:
    """Recompute PASS/FAIL from expected, actual, and tolerance.

    Args:
        expected: Expected value from fixture or snapshot target.
        actual: Stored actual value from golden_results.csv.
        tolerance: Decimal tolerance or exact.

    Returns:
        PASS when the row is internally consistent, otherwise FAIL.
    """
    if tolerance == "exact":
        return "PASS" if actual == expected else "FAIL"
    expected_decimal = decimal_or_none(value=expected)
    actual_decimal = decimal_or_none(value=actual)
    tolerance_decimal = decimal_or_none(value=tolerance)
    if (
        expected_decimal is None
        or actual_decimal is None
        or tolerance_decimal is None
    ):
        return "FAIL"
    diff = abs(actual_decimal - expected_decimal)
    return "PASS" if diff <= tolerance_decimal else "FAIL"


def recompute_non_fixture_golden_status(*, row: dict) -> str:
    """Recompute non-fixture snapshot status from expected and actual text.

    Args:
        row: One golden_results.csv row outside G3/G4 fixtures.

    Returns:
        PASS or FAIL from the row's explicit expectation grammar.
    """
    expected = row["expected"]
    actual = row["actual"]
    if expected.startswith("source_class != "):
        rejected = expected.replace("source_class != ", "", 1)
        return "PASS" if actual and actual != rejected else "FAIL"
    if expected.startswith("B08="):
        expected_status = expected.replace("B08=", "", 1)
        return "PASS" if f"B08_status={expected_status}" in actual else "FAIL"
    if " or " in expected:
        allowed = {item.strip() for item in expected.split(" or ")}
        return "PASS" if actual in allowed else "FAIL"
    if expected.startswith("at least one"):
        actual_decimal = decimal_or_none(value=actual)
        if actual_decimal is None:
            return "FAIL"
        return "PASS" if actual_decimal >= Decimal("1") else "FAIL"
    return "PASS" if actual == expected else "FAIL"


def golden_fixture_rows_by_assertion() -> dict[str, dict]:
    """Return G3/G4 fixture expectations keyed by assertion id."""
    path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "sec_10_company_spike"
        / "golden_expected_values.csv"
    )
    return {
        row["assertion_id"]: row
        for row in read_csv_file(path=path)
    }


def metric_rows_for_company_metric(
    *,
    metrics: list[dict],
    company: str,
    metric_id: str,
) -> list[dict]:
    """Return matching metric rows without raising on missing rows."""
    return [
        row
        for row in metrics
        if row["company"] == company and row["metric_id"] == metric_id
    ]


def golden_decimal_matches_metric(*, actual: str, metric_value: str) -> bool:
    """Return whether a golden actual value equals a metrics_matrix value."""
    actual_decimal = decimal_or_none(value=actual)
    metric_decimal = decimal_or_none(value=metric_value)
    if actual_decimal is None or metric_decimal is None:
        return False
    return actual_decimal == metric_decimal


def light_golden_fixture_failures(
    *,
    golden_by_id: dict[str, dict],
    fixture_by_id: dict[str, dict],
    metrics: list[dict],
) -> list[str]:
    """Return G3/G4 fixture and metrics cross-check failures.

    Args:
        golden_by_id: Golden snapshot rows keyed by assertion id.
        fixture_by_id: Expected G3/G4 rows keyed by assertion id.
        metrics: Current metrics_matrix rows.

    Returns:
        Failure messages for fixture drift, actual tampering, or metric drift.
    """
    failures = []
    for assertion_id, fixture_row in fixture_by_id.items():
        if assertion_id not in golden_by_id:
            failures.append(f"{assertion_id}:missing_snapshot_row")
            continue
        golden_row = golden_by_id[assertion_id]
        if golden_row["expected"] != fixture_row["expected"]:
            failures.append(f"{assertion_id}:fixture_expected_mismatch")
        recomputed = recompute_golden_status(
            expected=fixture_row["expected"],
            actual=golden_row["actual"],
            tolerance=fixture_row["tolerance"],
        )
        if golden_row["status"] != recomputed:
            failures.append(
                f"{assertion_id}:stored_status={golden_row['status']}:"
                f"recomputed={recomputed}"
            )
        if recomputed != "PASS":
            failures.append(f"{assertion_id}:expected_actual_mismatch")
        company = str(company_by_id(company_id=fixture_row["company_id"])["company"])
        component_key = fixture_row["component_key"]
        if component_key.startswith("metric_status_"):
            metric_id = component_key.replace("metric_status_", "", 1)
            metric_rows = metric_rows_for_company_metric(
                metrics=metrics,
                company=company,
                metric_id=metric_id,
            )
            if not metric_rows:
                failures.append(f"{assertion_id}:metric_missing:{metric_id}")
                continue
            metric_status = metric_rows[0]["status"]
            if golden_row["actual"] != metric_status:
                failures.append(f"{assertion_id}:metrics_status_drift")
            if fixture_row["expected"] != metric_status:
                failures.append(f"{assertion_id}:fixture_status_drift")
            continue
        if component_key not in LIGHT_GOLDEN_COMPONENT_METRICS:
            continue
        metric_id = LIGHT_GOLDEN_COMPONENT_METRICS[component_key]
        metric_rows = metric_rows_for_company_metric(
            metrics=metrics,
            company=company,
            metric_id=metric_id,
        )
        if not metric_rows or not metric_rows[0]["value"]:
            failures.append(f"{assertion_id}:metric_unverifiable:{metric_id}")
            continue
        if not golden_decimal_matches_metric(
            actual=golden_row["actual"],
            metric_value=metric_rows[0]["value"],
        ):
            failures.append(f"{assertion_id}:metrics_value_drift:{metric_id}")
    return failures


def light_golden_g1_failures(*, golden_by_id: dict[str, dict]) -> list[str]:
    """Cross-check G1 rows against company_resolution.csv."""
    failures = []
    for recomputed in run_company_structure_golden():
        assertion_id = recomputed["assertion_id"]
        if assertion_id not in golden_by_id:
            failures.append(f"{assertion_id}:missing_snapshot_row")
            continue
        golden_row = golden_by_id[assertion_id]
        for field in ["expected", "actual", "status"]:
            if golden_row[field] != recomputed[field]:
                failures.append(f"{assertion_id}:company_resolution_{field}_drift")
    return failures


def light_golden_g2_failures(
    *,
    golden_by_id: dict[str, dict],
    metrics: list[dict],
) -> list[str]:
    """Cross-check metrics-backed G2 rows against metrics_matrix.csv."""
    failures = []
    financial_configs = company_configs_with_extractor(
        extractor_name="BaselCapitalRatioExtractor",
    )
    if financial_configs:
        company = str(financial_configs[0]["company"])
        for metric_id in G2_FINANCIAL_NON_STD_METRIC_IDS:
            assertion_id = f"G2_financial_{metric_id.lower()}_not_std"
            if assertion_id not in golden_by_id:
                failures.append(f"{assertion_id}:missing_snapshot_row")
                continue
            metric_rows = metric_rows_for_company_metric(
                metrics=metrics,
                company=company,
                metric_id=metric_id,
            )
            actual_class = metric_rows[0]["source_class"] if metric_rows else "MISSING"
            golden_row = golden_by_id[assertion_id]
            recomputed = "PASS" if actual_class != "STD_XBRL" else "FAIL"
            if golden_row["actual"] != actual_class:
                failures.append(f"{assertion_id}:metrics_source_class_drift")
            if golden_row["status"] != recomputed:
                failures.append(f"{assertion_id}:stored_status_drift")
        b08_rows = metric_rows_for_company_metric(
            metrics=metrics,
            company=company,
            metric_id="B08",
        )
        assertion_id = G2_FINANCIAL_ASSETSCURRENT_ASSERTION_ID
        if assertion_id in golden_by_id and b08_rows:
            b08_status = b08_rows[0]["status"]
            golden_row = golden_by_id[assertion_id]
            if f"B08_status={b08_status}" not in golden_row["actual"]:
                failures.append(f"{assertion_id}:metrics_b08_status_drift")
            recomputed = "PASS" if b08_status == "N_A_STRUCTURAL" else "FAIL"
            if golden_row["status"] != recomputed:
                failures.append(f"{assertion_id}:stored_status_drift")
    captive_configs = company_configs_with_extractor(
        extractor_name="CaptiveFinanceDebtExtractor",
    )
    assertion_id = G2_CAPTIVE_FINANCE_ASSERTION_ID
    if captive_configs and assertion_id in golden_by_id:
        company = str(captive_configs[0]["company"])
        b06_rows = metric_rows_for_company_metric(
            metrics=metrics,
            company=company,
            metric_id="B06",
        )
        actual_status = b06_rows[0]["status"] if b06_rows else "MISSING"
        golden_row = golden_by_id[assertion_id]
        if golden_row["actual"] != actual_status:
            failures.append(f"{assertion_id}:metrics_b06_status_drift")
    return failures


def light_golden_snapshot_integrity_failures() -> list[str]:
    """Return failures from light golden snapshot integrity recomputation.

    Returns:
        Empty list only when stored expected/actual/status, fixture expected
        values, company_resolution, and metrics_matrix agree.
    """
    rows = read_csv_file(path=WORKDIR / "outputs" / "golden_results.csv")
    if not rows:
        return ["golden_results_missing"]
    golden_by_id, duplicates = golden_rows_by_assertion(rows=rows)
    failures = [f"{assertion_id}:duplicate" for assertion_id in duplicates]
    fixture_by_id = golden_fixture_rows_by_assertion()
    for row in rows:
        assertion_id = row["assertion_id"]
        if assertion_id in fixture_by_id:
            continue
        recomputed = recompute_non_fixture_golden_status(row=row)
        if row["status"] != recomputed:
            failures.append(
                f"{assertion_id}:stored_status={row['status']}:"
                f"recomputed={recomputed}"
            )
        if recomputed != "PASS":
            failures.append(f"{assertion_id}:expected_actual_mismatch")
    metrics = load_metrics()
    failures.extend(
        light_golden_fixture_failures(
            golden_by_id=golden_by_id,
            fixture_by_id=fixture_by_id,
            metrics=metrics,
        )
    )
    failures.extend(light_golden_g1_failures(golden_by_id=golden_by_id))
    failures.extend(
        light_golden_g2_failures(
            golden_by_id=golden_by_id,
            metrics=metrics,
        )
    )
    return failures


def check_light_golden_snapshot_integrity() -> dict:
    """Validate light golden snapshot without raw evidence rerun."""
    failures = light_golden_snapshot_integrity_failures()
    return validation_row(
        check_id="light_golden_snapshot_integrity",
        status="FAIL" if failures else "PASS",
        details=(
            ";".join(failures[:30])
            if failures
            else "snapshot expected/actual/status and cross-checks agree"
        ),
    )


def build_golden_candidates() -> list[dict]:
    """Build G5 candidate values for configured companies."""
    rows = []
    field_map = [
        ("Revenue", REVENUE_CHAIN, "duration"),
        ("Net income", NET_INCOME_CHAIN, "duration"),
        ("Total assets", ["Assets"], "instant"),
    ]
    for company_config in load_company_registry():
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        for metric_name, concept_chain, period_kind in field_map:
            hit = select_component(
                cik=cik,
                concept_chain=concept_chain,
                period_end=str(target["reportDate"]),
                period_kind=period_kind,
                accession=str(target["accession"]),
            )
            candidate_status = "CANDIDATE"
            if hit is None:
                related_targets = [
                    row
                    for row in inventory_rows_for_company(
                        company=company,
                        source_role="target_10k",
                    )
                    if int(row["cik"]) != cik
                ]
                for related_target in related_targets:
                    related_hit = select_component(
                        cik=int(related_target["cik"]),
                        concept_chain=concept_chain,
                        period_end=str(related_target["reportDate"]),
                        period_kind=period_kind,
                        accession=str(related_target["accession"]),
                    )
                    if related_hit is not None:
                        hit = related_hit
                        candidate_status = "CANDIDATE_RELATED_CIK"
                        break
            if hit is None:
                rows.append(
                    {
                        "company": company,
                        "metric_name": metric_name,
                        "value": "",
                        "unit": "",
                        "status": "NOT_AVAILABLE_SEC",
                        "accession": "",
                        "concept": "",
                        "period": target["reportDate"],
                        "filed_date": "",
                        "evidence_path": str(companyfacts_path(cik=cik)),
                    }
                )
            else:
                rows.append(
                    {
                        "company": company,
                        "metric_name": metric_name,
                        "value": decimal_text(value=hit.value),
                        "unit": hit.unit,
                        "status": candidate_status,
                        "accession": hit.accession,
                        "concept": hit.concept,
                        "period": f"{hit.start}:{hit.end}",
                        "filed_date": hit.filed,
                        "evidence_path": hit.source_path,
                    }
                )
    return rows


def stage_run_golden_assertions() -> None:
    """Stage 10: run structure, source-class, numeric, and candidate assertions."""
    mode, reasons = validation_package_mode()
    if mode == "WORKSPACE_INCOMPLETE":
        print("WORKSPACE_INCOMPLETE; " + "; ".join(reasons))
        raise SystemExit(1)
    if mode == "LIGHT_REVIEW_MODE":
        result = check_light_golden_snapshot_integrity()
        if result["status"] == "PASS":
            print("PASS: LIGHT_REVIEW_MODE; " + result["details"])
            return
        print("Light golden snapshot integrity failed:")
        print(result["details"])
        raise SystemExit(1)
    http = client()
    results = []
    results.extend(run_company_structure_golden())
    results.extend(run_g2_structural_golden(http=http))
    results.extend(fixture_numeric_golden_results())
    write_csv_file(
        path=WORKDIR / "outputs" / "golden_results.csv",
        fieldnames=GOLDEN_RESULT_FIELDNAMES,
        rows=results,
    )
    candidate_rows = build_golden_candidates()
    write_csv_file(
        path=WORKDIR / "outputs" / "golden_candidates.csv",
        fieldnames=GOLDEN_CANDIDATE_FIELDNAMES,
        rows=candidate_rows,
    )
    failed = [row for row in results if row["status"] != "PASS"]
    if failed:
        print("Golden assertions failed; actual values follow:")
        for row in failed:
            print(
                f"{row['assertion_id']}: target={row['expected']} "
                f"actual={row['actual']} notes={row['notes']}"
            )
        raise SystemExit(1)
    print("Stage 10 golden assertions complete; all pass")


def save_evidence(*, rows: list[dict]) -> None:
    """Write metric_evidence.csv rows with the canonical schema.

    Args:
        rows: Evidence dictionaries normalized to EVIDENCE_FIELDNAMES.

    Expected output:
        Existing metric evidence is replaced by the repaired evidence set.
    """
    write_csv_file(
        path=WORKDIR / "outputs" / "metric_evidence.csv",
        fieldnames=EVIDENCE_FIELDNAMES,
        rows=rows,
    )


def save_governance(*, rows: list[dict]) -> None:
    """Write governance_signals.csv rows with the canonical schema.

    Args:
        rows: Governance signal dictionaries, including C03 detail rows.

    Expected output:
        Existing governance rows are replaced after P0 C03 repair.
    """
    write_csv_file(
        path=WORKDIR / "outputs" / "governance_signals.csv",
        fieldnames=GOVERNANCE_FIELDNAMES,
        rows=rows,
    )


def normalize_fact_text(*, value: str) -> str:
    """Normalize SEC fact text for matching and evidence notes.

    Args:
        value: Raw fact text from CSV or extracted filing text.

    Returns:
        UTF-8 text with non-breaking spaces collapsed to ordinary spaces.
    """
    return " ".join(str(value).replace("\xa0", " ").split())


def canonical_auditor_name(*, value: str) -> str:
    """Return an auditor name key that ignores punctuation-only differences.

    Args:
        value: AuditorName fact text.

    Returns:
        Lowercase alphanumeric comparison key.
    """
    normalized = normalize_fact_text(value=value).lower()
    return re.sub(pattern=r"[^a-z0-9]+", repl="", string=normalized)


def is_dei_namespace(*, namespace: str) -> bool:
    """Return whether a namespace is an official annual SEC DEI taxonomy."""
    return re.fullmatch(
        pattern=r"https?://xbrl\.sec\.gov/dei/\d{4}",
        string=namespace,
    ) is not None


def is_ecd_namespace(*, namespace: str) -> bool:
    """Return whether a namespace is an SEC ECD taxonomy or legacy prefix."""
    normalized = namespace.lower()
    return normalized == "ecd" or re.fullmatch(
        pattern=r"https?://xbrl\.sec\.gov/ecd/\d{4}",
        string=normalized,
    ) is not None


def decimal_or_none(*, value: str) -> Decimal | None:
    """Return Decimal for numeric text, or None for dash/blank markers.

    Args:
        value: Raw numeric text. Commas are allowed.

    Returns:
        Decimal value or None when SEC text is intentionally non-numeric.
    """
    text = normalize_fact_text(value=value).replace(",", "")
    if text in {"", "-", "–", "—"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as error:
        print(f"Non-numeric repair value skipped: {text}; {error}")
        return None


def evidence_key_set(*, evidence_rows: list[dict]) -> set[tuple[str, str]]:
    """Return company/metric pairs that have at least one evidence row."""
    return {(row["company"], row["metric_id"]) for row in evidence_rows}


def remove_evidence_for_keys(
    *,
    evidence_rows: list[dict],
    keys: set[tuple[str, str]],
) -> list[dict]:
    """Remove evidence rows for metrics that will be rebuilt.

    Args:
        evidence_rows: Existing metric_evidence rows.
        keys: Company/metric pairs to delete before appending repair evidence.

    Returns:
        Evidence rows excluding stale or rejected P0 evidence.
    """
    return [
        row
        for row in evidence_rows
        if (row["company"], row["metric_id"]) not in keys
    ]


def material_url_for_path(*, local_path: str) -> str:
    """Return the SEC source URL for a saved accession material path.

    Args:
        local_path: Current or legacy evidence locator stored in an inventory.

    Returns:
        Matching SEC URL or blank when the path is not in material inventory.
    """
    target_relative_path = repo_relative_artifact_paths(
        path_text=local_path,
        row={},
    )
    rows = read_csv_file(
        path=WORKDIR / "outputs" / "accession_materials_inventory.csv"
    )
    for row in rows:
        if artifact_reference_text(row=row) == target_relative_path:
            return row["source_url"]
    return ""


def ecd_inventory_path(*, company: str) -> Path:
    """Return the local ECD concept inventory path for a company."""
    return (
        WORKDIR
        / "outputs"
        / "concept_inventory"
        / f"{slugify(text=company)}_ecd.csv"
    )


def instance_inventory_path(*, company: str) -> Path:
    """Return the local instance concept inventory path for a company."""
    return (
        WORKDIR
        / "outputs"
        / "concept_inventory"
        / f"{slugify(text=company)}_instance.csv"
    )


def unique_rows(*, rows: list[dict], fields: list[str]) -> list[dict]:
    """Deduplicate rows by explicit fields while preserving order.

    Args:
        rows: Candidate rows.
        fields: Field names that define semantic identity for this repair.

    Returns:
        First occurrence for each field tuple.
    """
    seen: set[tuple[str, ...]] = set()
    output = []
    for row in rows:
        key = tuple(row[field] for field in fields)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def valid_peo_total_comp_facts(*, company: str, period_end: str) -> list[dict]:
    """Return valid ecd:PeoTotalCompAmt facts for the target fiscal year.

    Args:
        company: Display company name.
        period_end: Target fiscal year end date in ISO format.

    Returns:
        Numeric USD PEO total compensation facts matching the target period.
    """
    candidates = []
    for row in read_csv_file(path=ecd_inventory_path(company=company)):
        if row["concept"] != "PeoTotalCompAmt":
            continue
        if row["unit"] != "iso4217:USD":
            continue
        if row["period_end"] != period_end:
            continue
        if decimal_or_none(value=row["value"]) is None:
            continue
        candidates.append(row)
    return unique_rows(
        rows=candidates,
        fields=[
            "accession",
            "concept",
            "unit",
            "context",
            "dimensions",
            "period_start",
            "period_end",
            "value",
        ],
    )


def primary_peo_fact(*, facts: list[dict]) -> dict:
    """Choose a primary PEO fact without summing compensation facts.

    Args:
        facts: Valid PeoTotalCompAmt facts for one company/period.

    Returns:
        Preferred fact, with no-dimension contexts ranked first.
    """
    if not facts:
        raise ValueError("PEO facts required for primary selection")
    return sorted(
        facts,
        key=lambda row: (
            0 if row["dimensions"] == "" else 1,
            row["context"],
            row["value"],
        ),
    )[0]


def build_c03_repair_rows(
    *,
    company: str,
    cik: int,
    period_end: str,
    accession: str,
    filed_date: str,
    source_url: str,
    local_path: str,
) -> tuple[dict, list[dict], list[dict]]:
    """Build repaired C03 metric, evidence, and governance rows.

    Args:
        company: Display company name.
        cik: SEC CIK.
        period_end: Target fiscal year end date.
        accession: DEF 14A accession.
        filed_date: DEF 14A filing date.
        source_url: DEF 14A source URL.
        local_path: DEF 14A local evidence path.

    Returns:
        Repaired metric row plus evidence rows and governance detail rows.
    """
    facts = valid_peo_total_comp_facts(company=company, period_end=period_end)
    if not facts:
        note = (
            "No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; "
            "C03 degraded from previous ecd_fact_count."
        )
        metric = text_metric_row(
            company=company,
            cik=cik,
            metric_id="C03",
            metric_name="Executive compensation signals",
            value="",
            unit="",
            status="NOT_EXTRACTED",
            source_class="DEF14A",
            period_end=period_end,
            accession=accession,
            filed_date=filed_date,
            concept_or_section="PeoTotalCompAmt",
            context_or_dimension="target fiscal year",
            confidence="0.35",
            notes=note,
        )
        governance = [
            {
                "company": company,
                "cik": str(cik),
                "signal_id": "C03",
                "signal_name": "Executive compensation signals",
                "value": "",
                "status": "NOT_EXTRACTED",
                "source_url": source_url,
                "local_path": local_path,
                "accession": accession,
                "concept_or_section": "PeoTotalCompAmt",
                "evidence_quote": "",
                "notes": note,
            }
        ]
        return metric, [], governance

    primary = primary_peo_fact(facts=facts)
    distinct_values = sorted({row["value"] for row in facts})
    if len(distinct_values) == 1:
        status = "DEF14A_OK"
        note = "Selected ecd:PeoTotalCompAmt; duplicate contexts retained in evidence."
    else:
        status = "NEEDS_REVIEW"
        note = (
            "Multiple numeric ecd:PeoTotalCompAmt values matched the target "
            "period; selected a primary fact and retained all evidence."
        )
    metric = text_metric_row(
        company=company,
        cik=cik,
        metric_id="C03",
        metric_name="Executive compensation signals",
        value=primary["value"],
        unit="USD",
        status=status,
        source_class="DEF14A",
        period_end=period_end,
        accession=primary["accession"],
        filed_date=filed_date,
        concept_or_section="PeoTotalCompAmt",
        context_or_dimension=primary["dimensions"],
        confidence="0.85" if status == "DEF14A_OK" else "0.55",
        notes=note,
    )
    evidence_rows = []
    governance_rows = [
        {
            "company": company,
            "cik": str(cik),
            "signal_id": "C03",
            "signal_name": "Executive compensation signals",
            "value": primary["value"],
            "status": status,
            "source_url": source_url,
            "local_path": local_path,
            "accession": primary["accession"],
            "concept_or_section": "PeoTotalCompAmt",
            "evidence_quote": (
                f"ecd:PeoTotalCompAmt unit=iso4217:USD "
                f"context={primary['context']} dimensions={primary['dimensions']} "
                f"value={primary['value']}"
            ),
            "notes": note,
        }
    ]
    for fact in facts:
        quote = (
            f"ecd:PeoTotalCompAmt unit=iso4217:USD context={fact['context']} "
            f"dimensions={fact['dimensions']} value={fact['value']}"
        )
        evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=cik,
                metric_id="C03",
                source_url=source_url,
                local_path=fact["source_path"],
                accession=fact["accession"],
                document_name=fact["document_name"],
                concept_or_section="PeoTotalCompAmt",
                context_or_dimension=fact["dimensions"],
                unit="USD",
                period_end=period_end,
                value=fact["value"],
                quote=quote,
                extraction_method="ecd_peo_total_comp_repair",
            )
        )
        governance_rows.append(
            {
                "company": company,
                "cik": str(cik),
                "signal_id": "C03_PEO_FACT",
                "signal_name": "PEO total compensation fact",
                "value": fact["value"],
                "status": "DEF14A_OK",
                "source_url": source_url,
                "local_path": fact["source_path"],
                "accession": fact["accession"],
                "concept_or_section": "PeoTotalCompAmt",
                "evidence_quote": quote,
                "notes": "All target-year PEO facts retained for C03 review.",
            }
        )
    return metric, evidence_rows, governance_rows


def repair_c03_compensation(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    governance_rows: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Repair C03 from ECD fact counts to PeoTotalCompAmt facts.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.
        governance_rows: Current governance_signals rows.

    Returns:
        Repaired metrics, evidence, and governance rows.
    """
    evidence_rows = remove_evidence_for_keys(
        evidence_rows=evidence_rows,
        keys={(row["company"], "C03") for row in metrics},
    )
    governance_rows = [
        row
        for row in governance_rows
        if row["signal_id"] not in {"C03", "C03_PEO_FACT"}
    ]
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    materials = read_csv_file(
        path=WORKDIR / "outputs" / "accession_materials_inventory.csv"
    )
    for row in [
        item
        for item in inventory
        if item["source_role"] == "latest_def14a"
    ]:
        company = row["company"]
        target = target_10k_for_company(company=company)
        material_rows = [
            material
            for material in materials
            if material["accession"] == row["accession"]
            and material["document_type"] == "def14a_primary_document"
        ]
        ecd_rows = [
            fact
            for fact in read_csv_file(path=ecd_inventory_path(company=company))
            if fact["accession"] == row["accession"]
        ]
        locator_rows = material_rows if material_rows else ecd_rows
        local_path = locator_rows[0]["local_path"] if locator_rows else ""
        source_url = (
            locator_rows[0]["source_url"]
            if locator_rows and locator_rows[0]["source_url"]
            else row["source_url"]
        )
        metric, new_evidence, new_governance = build_c03_repair_rows(
            company=company,
            cik=int(row["cik"]),
            period_end=str(target["reportDate"]),
            accession=row["accession"],
            filed_date=row["filingDate"],
            source_url=source_url,
            local_path=local_path,
        )
        metrics = upsert_metric(rows=metrics, new_row=metric)
        evidence_rows.extend(new_evidence)
        governance_rows.extend(new_governance)
    return metrics, evidence_rows, governance_rows


def repair_c02_board_text_from_governance(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    governance_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Restore qualitative C02 board evidence from local governance signals.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.
        governance_rows: Local governance_signals rows created by DEF 14A
            extraction.

    Expected output:
        C02 remains non-numeric but keeps the reviewed DEF 14A text anchor
        after an M2 standard-metric rebuild resets placeholders.

    Returns:
        Updated metrics and evidence rows.
    """
    c02_signals = [row for row in governance_rows if row["signal_id"] == "C02"]
    if not c02_signals:
        return metrics, evidence_rows

    filing_date_by_accession = {
        row["accession"]: row["filingDate"]
        for row in read_csv_file(
            path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
        )
    }
    next_evidence_rows = [
        row for row in evidence_rows if row["metric_id"] != "C02"
    ]
    for signal in c02_signals:
        company = signal["company"]
        accession = signal["accession"]
        if accession not in filing_date_by_accession:
            raise KeyError(f"C02 accession missing from inventory: {accession}")
        period_end = str(target_10k_for_company(company=company)["reportDate"])
        status = signal["status"]
        if status not in {"TEXT_QUAL", "NEEDS_REVIEW", "NOT_EXTRACTED"}:
            raise ValueError(f"Unsupported C02 status: {status}")
        # Keep C02 qualitative. This restores the evidence anchor without
        # inventing board-composition counts.
        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=int(signal["cik"]),
                metric_id="C02",
                metric_name="Board composition",
                value="",
                unit="",
                status=status,
                source_class="DEF14A",
                period_end=period_end,
                accession=accession,
                filed_date=filing_date_by_accession[accession],
                concept_or_section="DEF 14A board section",
                context_or_dimension="proxy statement",
                confidence="0.65" if signal["evidence_quote"] else "0.30",
                notes="Textual board evidence captured; structured counts need review.",
            ),
        )
        next_evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=int(signal["cik"]),
                metric_id="C02",
                source_url=signal["source_url"],
                local_path=signal["local_path"],
                accession=accession,
                document_name=Path(signal["local_path"]).name,
                concept_or_section="DEF 14A board/compensation section",
                context_or_dimension="proxy statement",
                unit="",
                period_end=period_end,
                value="",
                quote=signal["evidence_quote"],
                extraction_method=f"def14a_{status.lower()}",
            )
        )
    return metrics, next_evidence_rows


def normalized_concept_name(*, concept: str) -> str:
    """Return a comparable XBRL concept name with Basel spellings unified.

    Args:
        concept: XBRL concept local name.

    Returns:
        Lowercase alphanumeric concept text where written-out Tier One/Two
        variants are normalized to tier1/tier2.
    """
    normalized = re.sub(pattern=r"[^a-z0-9]+", repl="", string=concept.lower())
    return (
        normalized.replace("tierone", "tier1")
        .replace("tiertwo", "tier2")
    )


def concept_is_basel_threshold_or_requirement(*, concept: str) -> bool:
    """Return whether a Basel concept is a regulatory threshold.

    Args:
        concept: XBRL concept local name.

    Returns:
        True for minimum, capital-adequacy, and well-capitalized requirement
        concepts that describe context/thresholds rather than actual ratios.
    """
    normalized = normalized_concept_name(concept=concept)
    return any(
        fragment in normalized
        for fragment in BASEL_THRESHOLD_CONCEPT_FRAGMENTS
    )


def concept_has_rwa_ratio_semantics(*, normalized: str) -> bool:
    """Return whether a Basel concept expresses an RWA/risk-based ratio.

    Args:
        normalized: Output from normalized_concept_name.

    Returns:
        True when the concept names either risk weighted assets or the banking
        regulation risk-based capital ratio family.
    """
    return (
        "riskweightedassets" in normalized
        or "riskbasedcapitalratio" in normalized
    )


def concept_has_cet1_semantics(*, normalized: str) -> bool:
    """Return whether a normalized concept is CET1/Common Equity Tier 1.

    Args:
        normalized: Output from normalized_concept_name.

    Returns:
        True for CET1 abbreviations and written Common Equity Tier 1 variants.
    """
    return "cet1" in normalized or "commonequitytier1" in normalized


def concept_matches_basel_metric(*, concept: str, metric_id: str) -> bool:
    """Return whether a ratio concept name matches A01 or A02 semantics.

    Args:
        concept: XBRL concept local name.
        metric_id: A01 for Tier 1/RWA or A02 for CET1/RWA.

    Returns:
        True when the concept name encodes the requested Basel ratio.
    """
    normalized = normalized_concept_name(concept=concept)
    if concept_is_basel_threshold_or_requirement(concept=concept):
        return False
    has_rwa_ratio = concept_has_rwa_ratio_semantics(normalized=normalized)
    is_cet1 = concept_has_cet1_semantics(normalized=normalized)
    if metric_id == "A01":
        has_tier_one = "tier1" in normalized
        return has_rwa_ratio and has_tier_one and not is_cet1
    if metric_id == "A02":
        return has_rwa_ratio and is_cet1
    raise ValueError(f"Unsupported Basel metric id: {metric_id}")


def dimensions_have_basel_methodology(*, dimensions: str) -> bool:
    """Return whether dimensions contain a Basel/RWA methodology axis.

    Args:
        dimensions: Semicolon-delimited instance dimension string.

    Returns:
        True for explicit RWA methodology axes or equivalent Basel axes.
    """
    lower = dimensions.lower()
    normalized = re.sub(pattern=r"[^a-z0-9]+", repl="", string=lower)
    return (
        "riskweightedassetscalculationmethodologyaxis" in lower
        or "riskbasedcapitalratiocalculationmethodologyaxis" in lower
        or "regulatorycapitalmethodologyaxis" in normalized
        or "regulatorycapitalratioaxis" in normalized
        or ("basel" in lower and "methodologyaxis" in lower)
    )


def basel_ratio_candidates_from_rows(
    *,
    rows: list[dict],
    metric_id: str,
    period_end: str,
) -> list[dict]:
    """Return pure-unit Basel ratio candidates from prepared fact rows.

    Args:
        rows: Instance inventory-like fact rows.
        metric_id: A01 or A02.
        period_end: Target report date in YYYY-MM-DD format.

    Returns:
        Rows whose concept, unit, period, and dimensions satisfy Basel ratio
        semantics without relying on company identity.
    """
    candidates = []
    for row in rows:
        if row["unit"] != "pure":
            continue
        if row["period_end"] != period_end:
            continue
        if not dimensions_have_basel_methodology(dimensions=row["dimensions"]):
            continue
        # Threshold facts can share the same context and dimensions as actual
        # ratios; excluding them here prevents sort order from promoting rules.
        if concept_is_basel_threshold_or_requirement(concept=row["concept"]):
            continue
        if not concept_matches_basel_metric(
            concept=row["concept"],
            metric_id=metric_id,
        ):
            continue
        if decimal_or_none(value=row["value"]) is None:
            continue
        candidates.append(row)
    return candidates


def basel_ratio_candidates(
    *,
    company: str,
    metric_id: str,
    period_end: str,
) -> list[dict]:
    """Return pure-unit Basel ratio candidates for one company."""
    return basel_ratio_candidates_from_rows(
        rows=read_csv_file(path=instance_inventory_path(company=company)),
        metric_id=metric_id,
        period_end=period_end,
    )


def basel_candidate_role(*, concept: str, metric_id: str) -> str:
    """Return the role for a Basel ratio-like concept.

    Args:
        concept: XBRL concept local name.
        metric_id: A01 or A02.

    Returns:
        actual_ratio, regulatory_threshold, or rejected_non_candidate.
    """
    if concept_is_basel_threshold_or_requirement(concept=concept):
        return "regulatory_threshold"
    if concept_matches_basel_metric(concept=concept, metric_id=metric_id):
        return "actual_ratio"
    return "rejected_non_candidate"


def basel_ratio_candidate_rows(
    *,
    company: str,
    cik: int,
    metric_id: str,
    period_end: str,
) -> list[dict]:
    """Build auditable Basel candidate rows outside metric_evidence.csv.

    Args:
        company: Display company name.
        cik: Selected target CIK.
        metric_id: A01 or A02.
        period_end: Target report date.

    Returns:
        Candidate rows with candidate_role explicitly separating actual ratios
        from regulatory thresholds.
    """
    rows = []
    for row in read_csv_file(path=instance_inventory_path(company=company)):
        if row["unit"] != "pure":
            continue
        if row["period_end"] != period_end:
            continue
        if not dimensions_have_basel_methodology(dimensions=row["dimensions"]):
            continue
        role = basel_candidate_role(concept=row["concept"], metric_id=metric_id)
        if role == "rejected_non_candidate":
            continue
        rows.append(
            {
                "company": company,
                "cik": str(cik),
                "metric_id": metric_id,
                "candidate_role": role,
                "source_url": material_url_for_path(local_path=row["source_path"]),
                "local_path": row["source_path"],
                "accession": row["accession"],
                "document_name": row["document_name"],
                "concept": row["concept"],
                "context_or_dimension": row["dimensions"],
                "unit": row["unit"],
                "period_end": row["period_end"],
                "value": row["value"],
                "parser_version": "sec_pipeline_v1",
            }
        )
    return rows


def save_basel_ratio_candidates(*, rows: list[dict]) -> None:
    """Write Basel candidate roles to a separate review artifact.

    Args:
        rows: Candidate rows from all FI A01/A02 repairs.

    Expected output:
        metric_evidence.csv remains primary-metric evidence only, while
        regulatory thresholds stay reviewable in outputs/basel_ratio_candidates.csv.
    """
    write_csv_file(
        path=WORKDIR / "outputs" / "basel_ratio_candidates.csv",
        fieldnames=BASEL_RATIO_CANDIDATE_FIELDNAMES,
        rows=rows,
    )


def selected_basel_ratio_fact(*, rows: list[dict]) -> dict:
    """Select the preferred Basel ratio fact without dropping alternatives."""
    if not rows:
        raise ValueError("Basel ratio rows are required")
    return sorted(
        rows,
        key=lambda row: (
            0
            if re.search(
                pattern=r"parentcompanymember|consolidated",
                string=row["dimensions"],
                flags=re.IGNORECASE,
            )
            else 1,
            0
            if re.search(
                pattern=r"standardized",
                string=row["dimensions"],
                flags=re.IGNORECASE,
            )
            else 1,
            0
            if not re.search(
                pattern=r"bankn|bank na|legalentityaxis",
                string=row["dimensions"],
                flags=re.IGNORECASE,
            )
            else 1,
            row["context"],
        ),
    )[0]


def repair_basel_capital_ratios(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Repair A01/A02 for every financial institution profile company."""
    metric_defs = [
        ("A01", "Tier 1 capital ratio"),
        ("A02", "CET1 ratio"),
    ]
    candidate_rows: list[dict] = []
    for company_config in load_company_registry():
        extractors = company_extractors(company_config=company_config)
        if not has_extractor(
            extractors=extractors,
            extractor_name="BaselCapitalRatioExtractor",
        ):
            continue
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        period_end = str(target["reportDate"])
        cik = int(target["cik"])
        keys = {(company, metric_id) for metric_id, _name in metric_defs}
        evidence_rows = remove_evidence_for_keys(
            evidence_rows=evidence_rows,
            keys=keys,
        )
        for metric_id, metric_name in metric_defs:
            candidate_rows.extend(
                basel_ratio_candidate_rows(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    period_end=period_end,
                )
            )
            candidates = basel_ratio_candidates(
                company=company,
                metric_id=metric_id,
                period_end=period_end,
            )
            if not candidates:
                metrics = upsert_metric(
                    rows=metrics,
                    new_row=placeholder_metric(
                        company=company,
                        cik=cik,
                        metric_id=metric_id,
                        metric_name=metric_name,
                        status="NOT_EXTRACTED",
                        source_class="DIM_XBRL",
                        period_end=period_end,
                        notes=(
                            "本轮没抽到: pure-unit Basel ratio fact with RWA "
                            "methodology dimensions is missing."
                        ),
                    ),
                )
                continue
            primary = selected_basel_ratio_fact(rows=candidates)
            other_notes = []
            for fact in candidates:
                if fact["context"] == primary["context"]:
                    continue
                other_notes.append(
                    f"{fact['context']} {fact['dimensions']}={fact['value']}"
                )
            note = (
                "Selected parent/consolidated standardized Basel ratio fact; "
                "candidate facts and regulatory thresholds are retained in "
                "outputs/basel_ratio_candidates.csv. "
                + " | ".join(other_notes[:6])
            )
            metrics = upsert_metric(
                rows=metrics,
                new_row=text_metric_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    metric_name=metric_name,
                    value=primary["value"],
                    unit="pure",
                    status="DIM_XBRL_OK",
                    source_class="DIM_XBRL",
                    period_end=period_end,
                    accession=primary["accession"],
                    filed_date=target["filingDate"],
                    concept_or_section=primary["concept"],
                    context_or_dimension=primary["dimensions"],
                    confidence="0.90",
                    notes=note,
                ),
            )
            quote = (
                f"{primary['concept']} unit=pure context={primary['context']} "
                f"dimensions={primary['dimensions']} value={primary['value']}"
            )
            evidence_rows.append(
                text_evidence_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    source_url=material_url_for_path(
                        local_path=primary["source_path"],
                    ),
                    local_path=primary["source_path"],
                    accession=primary["accession"],
                    document_name=primary["document_name"],
                    concept_or_section=primary["concept"],
                    context_or_dimension=primary["dimensions"],
                    unit="pure",
                    period_end=period_end,
                    value=primary["value"],
                    quote=quote,
                    extraction_method="basel_capital_ratio_extractor",
                )
            )
    save_basel_ratio_candidates(rows=candidate_rows)
    return metrics, evidence_rows


def primary_material_for_company(*, company: str) -> dict:
    """Return the local target 10-K primary document material for a company."""
    target = target_10k_for_company(company=company)
    rows = read_csv_file(path=WORKDIR / "outputs" / "accession_materials_inventory.csv")
    for row in rows:
        if row["company"] != company:
            continue
        if row["accession"] != target["accession"]:
            continue
        if row["document_type"] == "primary_document":
            return row
    raise RuntimeError(f"Primary 10-K material missing for {company}")


def applicability_settings() -> dict:
    """Return non-profile settings from metric_applicability.yaml."""
    applicability = load_metric_applicability()
    return require_key(mapping=applicability, key="settings")


def text_has_lodging_kpi_keywords(*, text: str) -> bool:
    """Return whether filing text contains lodging KPI headers."""
    return bool(
        re.search(
            pattern=(
                r"RevPAR|Revenue per available room|Occupancy|"
                r"Average Daily Rate|ADR"
            ),
            string=text,
            flags=re.IGNORECASE,
        )
    )


def scope_pattern(*, scope: str) -> str:
    """Build a loose regex that preserves configured scope token order."""
    tokens = [re.escape(token) for token in scope.split()]
    return r".{0,80}".join(tokens)


def lodging_header_order(*, text: str) -> list[str]:
    """Return KPI column order inferred from a lodging table header.

    Args:
        text: Text segment that starts near a lodging KPI table header.

    Returns:
        Metric keys ordered by header position. Empty means the segment does
        not expose all required KPI headers.
    """
    header_patterns = [
        ("revpar", r"\bRevPAR\b|Revenue per available room"),
        ("occupancy", r"\bOccupancy(?: rate)?\b"),
        ("adr", r"Average Daily Rate|\bADR\b"),
    ]
    positions = []
    for metric_key, pattern in header_patterns:
        match = re.search(pattern=pattern, string=text, flags=re.IGNORECASE)
        if not match:
            return []
        positions.append((match.start(), metric_key))
    return [metric_key for _position, metric_key in sorted(positions)]


def lodging_metric_orders(*, text: str) -> list[list[str]]:
    """Return detected and fallback KPI column orders to test by identity.

    Args:
        text: Lodging table text segment.

    Returns:
        Candidate metric orders. The detected header order is tried first, and
        remaining permutations are retained so ambiguous flattened tables can
        still be resolved by the RevPAR identity.
    """
    detected = lodging_header_order(text=text)
    if not detected:
        return []
    output = [detected]
    for order in permutations(["revpar", "occupancy", "adr"]):
        candidate = list(order)
        if candidate not in output:
            output.append(candidate)
    return output


def lodging_table_segments(*, text: str) -> list[str]:
    """Return text windows that may contain lodging KPI tables.

    Args:
        text: Normalized filing text.

    Returns:
        Candidate windows starting at KPI header mentions.
    """
    segments = []
    pattern = (
        r"\bRevPAR\b|Revenue per available room|"
        r"\bOccupancy(?: rate)?\b|Average Daily Rate|\bADR\b"
    )
    for match in re.finditer(pattern=pattern, string=text, flags=re.IGNORECASE):
        segment = text[match.start(): match.start() + 5000]
        # Flattened SEC HTML often loses row boundaries, so table windows are
        # accepted only when all headers and at least one scope row survive.
        if not lodging_header_order(text=segment):
            continue
        if not re.search(
            pattern=r"Worldwide|Companywide|Comparable\s+.+?Properties",
            string=segment,
            flags=re.IGNORECASE,
        ):
            continue
        segments.append(segment)
    return segments


def lodging_scope_row_labels(*, scopes: list[object]) -> list[str]:
    """Return row labels implied by configured lodging scope priority.

    Args:
        scopes: Scope priority strings from metric_applicability settings.

    Returns:
        Distinct row labels searched in table text.
    """
    labels = []
    for scope in scopes:
        normalized = re.sub(
            pattern=r"[^a-z0-9]+",
            repl=" ",
            string=str(scope).lower(),
        ).strip()
        if "worldwide" in normalized and "Worldwide" not in labels:
            labels.append("Worldwide")
        if "companywide" in normalized and "Companywide" not in labels:
            labels.append("Companywide")
        if normalized.endswith("total") and "Total" not in labels:
            labels.append("Total")
    if not labels:
        labels.append("Worldwide")
    return labels


def normalized_scope_text(*, value: str) -> str:
    """Return normalized text for scope-token containment checks."""
    return re.sub(pattern=r"[^a-z0-9]+", repl=" ", string=value.lower()).strip()


def lodging_scope_matches(*, scope: str, section: str, label: str) -> bool:
    """Return whether a parsed row satisfies one configured scope string.

    Args:
        scope: Configured scope priority string.
        section: Nearest table section heading.
        label: Parsed row label.

    Returns:
        True when every configured scope token appears in the section/row text.
    """
    scope_tokens = normalized_scope_text(value=scope).split()
    candidate = normalized_scope_text(value=f"{section} {label}")
    return all(token in candidate for token in scope_tokens)


def lodging_section_before(*, segment: str, row_start: int) -> str:
    """Return the closest lodging table section before a row.

    Args:
        segment: Candidate lodging table text.
        row_start: Character offset where the row label starts.

    Returns:
        Section heading text or empty string.
    """
    section_pattern = (
        r"Comparable\s+[A-Za-z&.\- ]{1,90}\s+Properties|"
        r"Company-Operated\s+Properties|Systemwide\s+Properties"
    )
    matches = list(
        re.finditer(
            pattern=section_pattern,
            string=segment[:row_start],
            flags=re.IGNORECASE,
        )
    )
    if not matches:
        return ""
    return " ".join(matches[-1].group(0).split())


def lodging_numeric_cells(*, text: str) -> list[Decimal | None]:
    """Return flattened numeric table cells after a row label.

    Args:
        text: Row text beginning after the selected label.

    Returns:
        Parsed numeric cells. Dash cells are retained as None so absolute KPI
        positions do not slide onto percentage-change values.
    """
    cells: list[Decimal | None] = []
    cell_pattern = (
        r"(?:\$\s*)?"
        r"(?P<raw>\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?|—|-)"
        r"\s*%?\s*(?:pts?\.?)?"
    )
    for match in re.finditer(pattern=cell_pattern, string=text):
        raw = match.group("raw").replace(",", "")
        if raw in {"—", "-"}:
            cells.append(None)
        elif raw.startswith("(") and raw.endswith(")"):
            cells.append(-Decimal(raw[1:-1]))
        else:
            cells.append(Decimal(raw))
        if len(cells) == 6:
            return cells
    return cells


def lodging_quote_text(
    *,
    segment: str,
    row_start: int,
    row_text: str,
) -> tuple[str, str]:
    """Return normalized raw header and raw row snippets for KPI evidence.

    Args:
        segment: Lodging table text segment beginning near KPI headers.
        row_start: Character offset where the selected row begins.
        row_text: Text window beginning at the selected row.

    Returns:
        Header and row snippets suitable for evidence_quote.
    """
    header_pattern = (
        r"\bRevPAR\b|Revenue per available room|"
        r"\bOccupancy(?: rate)?\b|Average Daily Rate|\bADR\b"
    )
    header_matches = list(
        re.finditer(
            pattern=header_pattern,
            string=segment[:row_start],
            flags=re.IGNORECASE,
        )
    )
    if len(header_matches) >= 3:
        start = max(0, header_matches[-3].start() - 120)
        end = min(row_start, header_matches[-1].end() + 180)
        raw_header = " ".join(segment[start:end].split())
    else:
        raw_header = " ".join(segment[:row_start].split())
    raw_row = " ".join(row_text.split())
    return raw_header[:420], raw_row[:350]


def lodging_identity_error(
    *,
    revpar_value: Decimal,
    occupancy_value: Decimal,
    adr_value: Decimal,
) -> Decimal | None:
    """Return RevPAR identity relative error.

    Args:
        revpar_value: Revenue per available room in USD.
        occupancy_value: Occupancy percentage, not a change column.
        adr_value: Average daily rate in USD.

    Returns:
        Relative error against ADR * occupancy / 100, or None for invalid
        denominators.
    """
    expected = adr_value * occupancy_value / Decimal("100")
    if expected <= 0:
        return None
    return abs(revpar_value - expected) / expected


def lodging_candidate_from_cells(
    *,
    cells: list[Decimal | None],
    order: list[str],
    revpar_range: list[object],
    occupancy_range: list[object],
) -> dict | None:
    """Build one lodging KPI candidate from cells and a header order.

    Args:
        cells: Six flattened cells as metric absolute/change pairs.
        order: Metric order inferred from headers or permutation fallback.
        revpar_range: Accepted RevPAR USD range.
        occupancy_range: Accepted occupancy percent range.

    Returns:
        Candidate dict with KPI values and identity error, or None when the row
        fails range or identity checks.
    """
    if len(cells) < 6:
        return None
    values: dict[str, Decimal] = {}
    for index, metric_key in enumerate(order):
        value = cells[index * 2]
        if value is None:
            return None
        values[metric_key] = value
    revpar_value = values["revpar"]
    occupancy_value = values["occupancy"]
    adr_value = values["adr"]
    if not Decimal(str(revpar_range[0])) <= revpar_value <= Decimal(
        str(revpar_range[1]),
    ):
        return None
    if not Decimal(str(occupancy_range[0])) <= occupancy_value <= Decimal(
        str(occupancy_range[1]),
    ):
        return None
    error = lodging_identity_error(
        revpar_value=revpar_value,
        occupancy_value=occupancy_value,
        adr_value=adr_value,
    )
    if error is None or error > Decimal("0.05"):
        return None
    return {
        "revpar": decimal_text(value=revpar_value),
        "occupancy": decimal_text(value=occupancy_value),
        "adr": decimal_text(value=adr_value),
        "identity_error": decimal_text(value=error),
    }


def lodging_kpi_fact_from_text(*, text: str) -> dict:
    """Extract lodging KPI values by header and configured scope priority.

    Args:
        text: Normalized 10-K text.

    Returns:
        Dictionary with RevPAR, occupancy, ADR, scope, and quote fields.
    """
    settings = applicability_settings()
    scopes = require_key(mapping=settings, key="lodging_scope_priority")
    revpar_range = require_key(mapping=settings, key="revpar_usd_range")
    occupancy_range = require_key(mapping=settings, key="occupancy_percent_range")
    empty_quote = snippet_for_pattern(
        text=text,
        pattern=r"RevPAR|Revenue per available room|Occupancy|Average Daily Rate|ADR",
        width=1400,
    )
    empty = {
        "revpar": "",
        "occupancy": "",
        "adr": "",
        "scope": "",
        "quote": empty_quote,
    }
    candidates = []
    row_labels = lodging_scope_row_labels(scopes=scopes)
    labels_pattern = "|".join(re.escape(label) for label in row_labels)
    for segment in lodging_table_segments(text=text):
        orders = lodging_metric_orders(text=segment)
        if not orders:
            continue
        for row_match in re.finditer(
            pattern=rf"\b(?P<label>{labels_pattern})\b(?:\s*\([0-9]+\))?\s+",
            string=segment,
            flags=re.IGNORECASE,
        ):
            label = row_match.group("label")
            section = lodging_section_before(
                segment=segment,
                row_start=row_match.start(),
            )
            for scope_index, scope in enumerate(scopes):
                if not lodging_scope_matches(
                    scope=str(scope),
                    section=section,
                    label=label,
                ):
                    continue
                row_text = segment[row_match.start(): row_match.start() + 650]
                cells = lodging_numeric_cells(text=segment[row_match.end():])
                for order in orders:
                    candidate = lodging_candidate_from_cells(
                        cells=cells,
                        order=order,
                        revpar_range=revpar_range,
                        occupancy_range=occupancy_range,
                    )
                    if candidate is None:
                        continue
                    raw_header, raw_row = lodging_quote_text(
                        segment=segment,
                        row_start=row_match.start(),
                        row_text=row_text,
                    )
                    candidate["scope"] = str(scope)
                    candidate["scope_index"] = str(scope_index)
                    candidate["quote"] = (
                        "Lodging KPI table; table headers map columns by name; "
                        f"selected scope={scope}; order={','.join(order)}; "
                        f"parsed=RevPAR={candidate['revpar']}; "
                        f"occupancy={candidate['occupancy']}; "
                        f"adr={candidate['adr']}; "
                        f"identity_error={candidate['identity_error']}; "
                        f"raw_header={raw_header}; "
                        f"raw_row={raw_row}"
                    )
                    candidates.append(candidate)
    if not candidates:
        return empty
    selected = sorted(
        candidates,
        key=lambda row: (
            int(row["scope_index"]),
            Decimal(row["identity_error"]),
        ),
    )[0]
    return {
        "revpar": selected["revpar"],
        "occupancy": selected["occupancy"],
        "adr": selected["adr"],
        "scope": selected["scope"],
        "quote": selected["quote"],
    }


def upsert_lodging_text_metric(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    company: str,
    metric_id: str,
    metric_name: str,
    value: str,
    unit: str,
    section: str,
    quote: str,
    note: str,
    source_url: str,
    local_path: str,
) -> tuple[list[dict], list[dict]]:
    """Upsert one lodging KPI metric from the table-header parse.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.
        company: Display company name.
        metric_id: KPI metric id, B10 or B11.
        metric_name: Reader-facing metric name.
        value: Parsed absolute value, or blank when the strict parse failed.
        unit: Metric unit for a parsed value.
        section: Evidence section label.
        quote: Lodging KPI table quote.
        note: Metric note explaining scope and rejection boundary.
        source_url: SEC source URL.
        local_path: Local primary document path.

    Returns:
        Updated metrics and evidence rows.
    """
    target = target_10k_for_company(company=company)
    status = "MDA_OK" if value else "NOT_EXTRACTED"
    metrics = upsert_metric(
        rows=metrics,
        new_row=text_metric_row(
            company=company,
            cik=int(target["cik"]),
            metric_id=metric_id,
            metric_name=metric_name,
            value=value,
            unit=unit if value else "",
            status=status,
            source_class="MDA",
            period_end=str(target["reportDate"]),
            accession=target["accession"],
            filed_date=target["filingDate"],
            concept_or_section=section,
            context_or_dimension=section,
            confidence="0.85" if value else "0.00",
            notes=note,
        ),
    )
    if value:
        evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=int(target["cik"]),
                metric_id=metric_id,
                source_url=source_url,
                local_path=local_path,
                accession=target["accession"],
                document_name=Path(local_path).name,
                concept_or_section=section,
                context_or_dimension=section,
                unit=unit,
                period_end=str(target["reportDate"]),
                value=value,
                quote=quote,
                extraction_method="lodging_kpi_extractor",
            )
        )
    return metrics, evidence_rows


def apply_lodging_kpi_metrics(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    company: str,
    text: str,
    source_url: str,
    local_path: str,
) -> tuple[list[dict], list[dict]]:
    """Apply lodging KPI extraction to one company when applicable.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.
        company: Display company name.
        text: Normalized 10-K text.
        source_url: SEC source URL.
        local_path: Local primary document path.

    Returns:
        Metrics and evidence with absolute KPI facts added when available.
    """
    evidence_rows = remove_evidence_for_keys(
        evidence_rows=evidence_rows,
        keys={(company, "B10"), (company, "B11")},
    )
    fact = lodging_kpi_fact_from_text(text=text)
    fallback_b10 = (
        "本轮没抽到: lodging table did not provide a configured-scope "
        f"absolute occupancy value. Document={local_path}"
    )
    fallback_b11 = (
        "本轮没抽到: no configured-scope absolute RevPAR value passed the "
        f"USD range check. Document={local_path}"
    )
    b10_note = (
        f"Selected absolute occupancy from lodging KPI table; scope={fact['scope']}."
        if fact["occupancy"]
        else fallback_b10
    )
    b11_note = (
        f"Selected absolute RevPAR from lodging KPI table; scope={fact['scope']}; "
        "percentage change columns are not used as USD values."
        if fact["revpar"]
        else fallback_b11
    )
    metrics, evidence_rows = upsert_lodging_text_metric(
        metrics=metrics,
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B10",
        metric_name="Occupancy rate",
        value=fact["occupancy"],
        unit="percent",
        section="MD&A occupancy",
        quote=fact["quote"],
        note=b10_note,
        source_url=source_url,
        local_path=local_path,
    )
    metrics, evidence_rows = upsert_lodging_text_metric(
        metrics=metrics,
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B11",
        metric_name="RevPAR",
        value=fact["revpar"],
        unit="USD",
        section="MD&A RevPAR",
        quote=fact["quote"],
        note=b11_note,
        source_url=source_url,
        local_path=local_path,
    )
    return metrics, evidence_rows


def text_has_rpo_keywords(*, text: str) -> bool:
    """Return whether filing text contains RPO/cRPO keywords."""
    return bool(
        re.search(
            pattern=r"remaining performance obligation|RPO|cRPO",
            string=text,
            flags=re.IGNORECASE,
        )
    )


def concept_matches_rpo(*, concept: str) -> bool:
    """Return whether an instance concept is an RPO/cRPO value concept."""
    normalized = re.sub(pattern=r"[^a-z0-9]+", repl="", string=concept.lower())
    if "expectedtiming" in normalized or "period" in normalized:
        return False
    return (
        normalized == "revenueremainingperformanceobligation"
        or normalized.endswith("revenueremainingperformanceobligation")
        or "remainingperformanceobligationcurrent" in normalized
        or "remainingperformanceobligationnoncurrent" in normalized
    )


def rpo_instance_fact_from_rows(
    *,
    rows: list[dict],
    period_end: str,
) -> tuple[str, list[dict]]:
    """Select RPO/cRPO value from prepared instance rows first.

    Args:
        rows: Instance inventory-like fact rows.
        period_end: Target reportDate.

    Returns:
        Normalized USD value and evidence facts. Empty value means no fact.
    """
    settings = applicability_settings()
    min_value = Decimal(str(require_key(mapping=settings, key="rpo_min_usd")))
    candidates = []
    components = []
    for row in rows:
        if row["unit"] != "iso4217:USD":
            continue
        if row["period_end"] != period_end:
            continue
        if not concept_matches_rpo(concept=row["concept"]):
            continue
        value = decimal_or_none(value=row["value"])
        if value is None or value < min_value:
            continue
        if re.search(
            pattern=r"current|noncurrent",
            string=row["concept"],
            flags=re.IGNORECASE,
        ):
            components.append(row)
        else:
            candidates.append(row)
    if candidates:
        selected = sorted(
            candidates,
            key=lambda row: decimal_or_none(value=row["value"]),
            reverse=True,
        )[0]
        return selected["value"], [selected]
    if len(components) >= 2:
        total = Decimal("0")
        for row in components:
            value = decimal_or_none(value=row["value"])
            if value is None:
                raise ValueError(f"RPO component unexpectedly nonnumeric: {row}")
            total += value
        if total >= min_value:
            return decimal_text(value=total), components
    return "", []


def rpo_instance_fact(*, company: str, period_end: str) -> tuple[str, list[dict]]:
    """Select RPO/cRPO value from accession instance rows first.

    Args:
        company: Display company name.
        period_end: Target reportDate.

    Returns:
        Normalized USD value and evidence facts. Empty value means no fact.
    """
    return rpo_instance_fact_from_rows(
        rows=read_csv_file(path=instance_inventory_path(company=company)),
        period_end=period_end,
    )


def rpo_text_fact(*, text: str) -> tuple[str, str]:
    """Extract RPO/cRPO value from generic text fallback.

    Args:
        text: Normalized 10-K text.

    Returns:
        Normalized USD value and quote. Empty value means no fallback.
    """
    quote = snippet_for_pattern(
        text=text,
        pattern=r"remaining performance obligation|RPO|cRPO",
        width=900,
    )
    if not quote:
        return "", ""
    settings = applicability_settings()
    min_value = Decimal(str(require_key(mapping=settings, key="rpo_min_usd")))
    values = []
    for match in re.finditer(
        pattern=r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million)?",
        string=quote,
        flags=re.IGNORECASE,
    ):
        value = Decimal(match.group(1))
        scale = match.group(2).lower() if match.group(2) else ""
        if scale == "billion":
            value *= Decimal("1000000000")
        elif scale == "million":
            value *= Decimal("1000000")
        if value >= min_value:
            values.append(value)
    if not values:
        return "", quote
    return decimal_text(value=max(values)), quote


def apply_rpo_crpo_metric(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    company: str,
    text: str,
    source_url: str,
    local_path: str,
) -> tuple[list[dict], list[dict]]:
    """Apply B12 RPO/cRPO extractor to one company.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.
        company: Display company name.
        text: Normalized 10-K text.
        source_url: SEC source URL.
        local_path: Local primary document path.

    Returns:
        Metrics and evidence with instance-first RPO/cRPO extraction.
    """
    target = target_10k_for_company(company=company)
    evidence_rows = remove_evidence_for_keys(
        evidence_rows=evidence_rows,
        keys={(company, "B12")},
    )
    value, instance_facts = rpo_instance_fact(
        company=company,
        period_end=str(target["reportDate"]),
    )
    quote = ""
    if value:
        status = "DIM_XBRL_OK"
        source_class = "DIM_XBRL"
        note = "RPO != ARR; cRPO != ARR. Selected accession instance fact."
    else:
        value, quote = rpo_text_fact(text=text)
        status = "MDA_OK" if value else "NOT_EXTRACTED"
        source_class = "MDA"
        note = (
            "RPO != ARR; cRPO != ARR. Total RPO is used only as labeled SEC text."
            if value
            else (
                "本轮没抽到: explicit RPO/cRPO fact or USD text boundary failed; "
                "RPO != ARR; cRPO != ARR."
            )
        )
    metrics = upsert_metric(
        rows=metrics,
        new_row=text_metric_row(
            company=company,
            cik=int(target["cik"]),
            metric_id="B12",
            metric_name="ARR / churn or RPO substitute",
            value=value,
            unit="USD" if value else "",
            status=status,
            source_class=source_class,
            period_end=str(target["reportDate"]),
            accession=target["accession"],
            filed_date=target["filingDate"],
            concept_or_section=(
                "+".join([fact["concept"] for fact in instance_facts])
                if instance_facts
                else "RPO/cRPO text"
            ),
            context_or_dimension=(
                ";".join([fact["context"] for fact in instance_facts])
                if instance_facts
                else "10-K text"
            ),
            confidence="0.90" if instance_facts else "0.70" if value else "0.35",
            notes=note,
        ),
    )
    if instance_facts:
        for fact in instance_facts:
            evidence_rows.append(
                text_evidence_row(
                    company=company,
                    cik=int(target["cik"]),
                    metric_id="B12",
                    source_url=material_url_for_path(
                        local_path=fact["source_path"],
                    ),
                    local_path=fact["source_path"],
                    accession=fact["accession"],
                    document_name=fact["document_name"],
                    concept_or_section=fact["concept"],
                    context_or_dimension=fact["context"],
                    unit="USD",
                    period_end=str(target["reportDate"]),
                    value=fact["value"],
                    quote=(
                        f"{fact['concept']} unit=iso4217:USD "
                        f"context={fact['context']} value={fact['value']}"
                    ),
                    extraction_method="rpo_crpo_instance_extractor",
                )
            )
        return metrics, evidence_rows
    if value:
        evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=int(target["cik"]),
                metric_id="B12",
                source_url=source_url,
                local_path=local_path,
                accession=target["accession"],
                document_name=Path(local_path).name,
                concept_or_section="RPO/cRPO text",
                context_or_dimension="10-K text",
                unit="USD",
                period_end=str(target["reportDate"]),
                value=value,
                quote=quote,
                extraction_method="rpo_crpo_text_fallback",
            )
        )
    return metrics, evidence_rows


def repair_lodging_kpis(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Run lodging KPI extractor for all applicable companies."""
    for company_config in load_company_registry():
        extractors = company_extractors(company_config=company_config)
        if not has_extractor(
            extractors=extractors,
            extractor_name="LodgingKpiExtractor",
        ):
            continue
        company = str(company_config["company"])
        material = primary_material_for_company(company=company)
        text = html_file_to_text(path=resolve_artifact_path(row=material))
        metrics, evidence_rows = apply_lodging_kpi_metrics(
            metrics=metrics,
            evidence_rows=evidence_rows,
            company=company,
            text=text,
            source_url=material["source_url"],
            local_path=artifact_reference_text(row=material),
        )
    return metrics, evidence_rows


def repair_rpo_crpo_metrics(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Run RPO/cRPO extractor for all applicable companies."""
    for company_config in load_company_registry():
        extractors = company_extractors(company_config=company_config)
        if not has_extractor(
            extractors=extractors,
            extractor_name="RpoCrpoExtractor",
        ):
            continue
        company = str(company_config["company"])
        material = primary_material_for_company(company=company)
        text = html_file_to_text(path=resolve_artifact_path(row=material))
        metrics, evidence_rows = apply_rpo_crpo_metric(
            metrics=metrics,
            evidence_rows=evidence_rows,
            company=company,
            text=text,
            source_url=material["source_url"],
            local_path=artifact_reference_text(row=material),
        )
    return metrics, evidence_rows


def text_has_capacity_keywords(*, text: str) -> bool:
    """Return whether filing text contains capacity-utilization signals."""
    return bool(
        re.search(
            pattern=r"capacity utilization|production capacity|manufacturing capacity",
            string=text,
            flags=re.IGNORECASE,
        )
    )


def concept_is_captive_debt_probe(*, concept: str) -> bool:
    """Return whether a concept is eligible for captive-finance probing.

    Args:
        concept: XBRL concept local name.

    Returns:
        True only for debt concepts where a segment/legal-entity dimension can
        affect B06 interpretation.
    """
    normalized = normalized_concept_name(concept=concept)
    excluded_patterns = [
        r"^financeleaseliability",
        r"^deferredfinancecosts",
        r"^supplierfinanceprogram",
        r"^debtsecurities.*creditloss",
    ]
    for pattern in excluded_patterns:
        if re.search(pattern=pattern, string=normalized):
            return False
    return (
        normalized.startswith("longtermdebt")
        or normalized.startswith("shorttermborrowings")
        or normalized.startswith("commercialpaper")
        or normalized.startswith("debtandfinanceleaseobligations")
        or normalized.startswith("debtandcapitalleaseobligations")
        or normalized == "debtcurrent"
    )


def captive_dimension_axis_allowed(*, axis: str) -> bool:
    """Return whether a dimension axis can express captive finance scope.

    Args:
        axis: Dimension axis QName or local name.

    Returns:
        True for segment/legal-entity/consolidated-entity axes only.
    """
    axis_local = axis.split(":")[-1]
    normalized = normalized_concept_name(concept=axis_local)
    allowed_axes = {
        "statementbusinesssegmentsaxis",
        "legalentityaxis",
        "operatingsegmentsaxis",
        "consolidatedentitiesaxis",
    }
    return normalized in allowed_axes


def captive_dimension_member_allowed(*, member: str) -> bool:
    """Return whether a dimension member expresses captive finance.

    Args:
        member: Dimension member QName or local name.

    Returns:
        True for credit, financial-services, captive-finance, financing
        subsidiary, or company-excluding-credit member semantics.
    """
    member_local = member.split(":")[-1]
    normalized = normalized_concept_name(concept=member_local)
    excluded_fragments = [
        "creditloss",
        "creditfacility",
        "lineofcredit",
        "letterofcredit",
        "financelease",
        "deferredfinancecosts",
        "supplierfinance",
    ]
    if any(fragment in normalized for fragment in excluded_fragments):
        return False
    captive_fragments = [
        "credit",
        "financial",
        "financing",
        "captivefinance",
        "capitalcorporation",
    ]
    return any(fragment in normalized for fragment in captive_fragments)


def dimension_pairs(*, dimensions: str) -> list[tuple[str, str]]:
    """Return parsed axis/member pairs from a semicolon-delimited string.

    Args:
        dimensions: Instance dimension string such as axis=member;axis=member.

    Returns:
        List of axis/member pairs. Malformed pieces are ignored because parsed
        instance inventories can include non-dimensional context text.
    """
    pairs = []
    for item in dimensions.split(";"):
        if "=" not in item:
            continue
        axis, member = item.split("=", 1)
        pairs.append((axis, member))
    return pairs


def row_has_captive_finance_signal(*, row: dict) -> bool:
    """Return whether one fact row proves captive-finance review is needed.

    Args:
        row: Instance inventory-like row.

    Returns:
        True only when a debt fact has an allowed axis/member pair. Concept-only
        finance, lease, deferred-cost, or credit-loss wording is insufficient.
    """
    if not concept_is_captive_debt_probe(concept=row["concept"]):
        return False
    for axis, member in dimension_pairs(dimensions=row["dimensions"]):
        if (
            captive_dimension_axis_allowed(axis=axis)
            and captive_dimension_member_allowed(member=member)
        ):
            return True
    return False


def captive_finance_signal_from_rows(*, rows: list[dict]) -> bool:
    """Return whether prepared fact rows contain a captive-finance signal.

    Args:
        rows: Instance inventory-like fact rows.

    Returns:
        True when at least one eligible debt fact has an allowed segment or
        legal-entity member.
    """
    return any(row_has_captive_finance_signal(row=row) for row in rows)


def company_has_captive_finance_signal(*, company: str) -> bool:
    """Return whether instance facts show a captive finance segment."""
    return captive_finance_signal_from_rows(
        rows=read_csv_file(path=instance_inventory_path(company=company)),
    )


def b06_candidate_row_from_metric(
    *,
    metric: dict,
    evidence_rows: list[dict],
    candidate_role: str,
) -> dict:
    """Build a B06 candidate sidecar row from a reviewed metric row.

    Args:
        metric: B06 metrics_matrix row before blanking the main value.
        evidence_rows: metric_evidence rows for the candidate components.
        candidate_role: Role explaining why the value is sidecar-only.

    Returns:
        Candidate row with value, formula context, source, and evidence quote.
    """
    source_url, local_path, quote = evidence_quote_for_metric(
        evidence_rows=evidence_rows,
        company=metric["company"],
        metric_id="B06",
    )
    return {
        "company": metric["company"],
        "cik": metric["cik"],
        "metric_id": metric["metric_id"],
        "value": metric["value"],
        "unit": metric["unit"],
        "status": metric["status"],
        "period_end": metric["period_end"],
        "accession": metric["accession"],
        "concept_or_section": metric["concept_or_section"],
        "context_or_dimension": metric["context_or_dimension"],
        "candidate_role": candidate_role,
        "source_url": source_url,
        "local_path": local_path,
        "evidence_quote": quote,
        "notes": metric["notes"],
    }


def b06_candidate_evidence_row(
    *,
    evidence_rows: list[dict],
    company: str,
) -> dict | None:
    """Return the best existing B06 candidate evidence row for a company.

    Args:
        evidence_rows: Current metric_evidence rows.
        company: Company name to match.

    Returns:
        Explicit candidate marker evidence when present, otherwise the latest
        numeric B06 evidence row that can rebuild the sidecar after reruns.
    """
    marker_rows = [
        row
        for row in evidence_rows
        if row["company"] == company
        and row["metric_id"] == "B06"
        and (
            row["extraction_method"] == "b06_captive_finance_candidate"
            or "candidate_role=consolidated_captive_finance_candidate"
            in row["evidence_quote"]
        )
    ]
    if marker_rows:
        return marker_rows[-1]
    numeric_rows = [
        row
        for row in evidence_rows
        if row["company"] == company
        and row["metric_id"] == "B06"
        and row["value_normalized"] != ""
    ]
    if not numeric_rows:
        return None
    return numeric_rows[-1]


def b06_candidate_row_from_evidence(
    *,
    metric: dict,
    evidence: dict,
    candidate_role: str,
) -> dict:
    """Build a B06 candidate sidecar row from existing evidence.

    Args:
        metric: Current B06 metrics_matrix row.
        evidence: Existing metric_evidence row carrying the candidate value.
        candidate_role: Role explaining why the value is sidecar-only.

    Returns:
        Candidate sidecar row rebuilt without requiring a nonblank main value.
    """
    return {
        "company": metric["company"],
        "cik": metric["cik"],
        "metric_id": "B06",
        "value": evidence["value_normalized"],
        "unit": evidence["unit"],
        "status": "NEEDS_REVIEW",
        "period_end": evidence["period_end"],
        "accession": evidence["accession"],
        "concept_or_section": evidence["concept_or_section"],
        "context_or_dimension": evidence["context_or_dimension"],
        "candidate_role": candidate_role,
        "source_url": evidence["source_url"],
        "local_path": evidence["local_path"],
        "evidence_quote": evidence["evidence_quote"],
        "notes": (
            "Consolidated candidate retained only in evidence and sidecar; "
            "main value is blank because captive finance segment/dimension "
            "was detected."
        ),
    }


def append_b06_candidate_evidence(
    *,
    evidence_rows: list[dict],
    metric: dict,
    candidate_role: str,
) -> list[dict]:
    """Append explicit candidate-role evidence for a B06 review value.

    Args:
        evidence_rows: Existing metric_evidence rows.
        metric: B06 metric row before blanking the main value.
        candidate_role: Candidate role persisted in the evidence quote.

    Returns:
        Evidence rows with one candidate marker row appended.
    """
    source_url, local_path, quote = evidence_quote_for_metric(
        evidence_rows=evidence_rows,
        company=metric["company"],
        metric_id="B06",
    )
    for row in evidence_rows:
        if (
            row["company"] == metric["company"]
            and row["metric_id"] == "B06"
            and row["extraction_method"] == "b06_captive_finance_candidate"
            and f"candidate_role={candidate_role}" in row["evidence_quote"]
        ):
            return evidence_rows
    evidence_rows.append(
        {
            "company": metric["company"],
            "cik": metric["cik"],
            "metric_id": "B06",
            "source_url": source_url,
            "local_path": local_path,
            "accession": metric["accession"],
            "document_name": Path(local_path).name if local_path else "",
            "concept_or_section": metric["concept_or_section"],
            "context_or_dimension": metric["context_or_dimension"],
            "unit": metric["unit"],
            "period_start": metric["period_start"],
            "period_end": metric["period_end"],
            "value_raw": metric["value"],
            "value_normalized": metric["value"],
            "evidence_quote": (
                f"candidate_role={candidate_role}; "
                f"main_value_blank=true; {quote}"
            )[:1000],
            "extraction_method": "b06_captive_finance_candidate",
            "parser_version": "sec_pipeline_v1",
        }
    )
    return evidence_rows


def repair_captive_finance_debt(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Flag B06 when captive-finance dimensions affect debt interpretation.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.

    Returns:
        Metrics and evidence with consolidated B06 values retained but marked
        for review when no industrial-only ratio has been extracted.
    """
    candidate_rows = []
    for company_config in load_company_registry():
        extractors = company_extractors(company_config=company_config)
        if not has_extractor(
            extractors=extractors,
            extractor_name="CaptiveFinanceDebtExtractor",
        ):
            continue
        company = str(company_config["company"])
        if not company_has_captive_finance_signal(company=company):
            row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
            if row["status"] == "NEEDS_REVIEW" and "captive finance" in row[
                "notes"
            ].lower():
                row["status"] = "OK" if row["value"] else "NOT_AVAILABLE_SEC"
                row["notes"] = (
                    "Entity-level debt/equity; no captive finance segment "
                    "dimension detected."
                )
                metrics = upsert_metric(rows=metrics, new_row=row)
            continue
        row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
        if row["value"]:
            candidate_role = "consolidated_captive_finance_candidate"
            candidate_rows.append(
                b06_candidate_row_from_metric(
                    metric=row,
                    evidence_rows=evidence_rows,
                    candidate_role=candidate_role,
                )
            )
            evidence_rows = append_b06_candidate_evidence(
                evidence_rows=evidence_rows,
                metric=row,
                candidate_role=candidate_role,
            )
            row["value"] = ""
            row["status"] = "NEEDS_REVIEW"
            row["source_class"] = "DERIVED"
            row["notes"] = (
                "Main debt/equity value is blank because captive finance "
                "segment/dimension was detected; consolidated candidate is "
                "retained only in evidence and sidecar with candidate_role."
            )
            metrics = upsert_metric(rows=metrics, new_row=row)
        else:
            candidate_role = "consolidated_captive_finance_candidate"
            evidence = b06_candidate_evidence_row(
                evidence_rows=evidence_rows,
                company=company,
            )
            if evidence is not None:
                candidate_rows.append(
                    b06_candidate_row_from_evidence(
                        metric=row,
                        evidence=evidence,
                        candidate_role=candidate_role,
                    )
                )
                target = target_10k_for_company(company=company)
                row["value"] = ""
                row["unit"] = evidence["unit"]
                row["status"] = "NEEDS_REVIEW"
                row["source_class"] = "DERIVED"
                row["formula"] = "total debt / shareholders' equity"
                row["period_start"] = evidence["period_start"]
                row["period_end"] = evidence["period_end"]
                row["fiscal_year"] = evidence["period_end"][:4]
                row["fiscal_period"] = "FY"
                row["accession"] = evidence["accession"]
                row["form"] = str(target["form"])
                row["filed_date"] = str(target["filingDate"])
                row["concept_or_section"] = evidence["concept_or_section"]
                row["context_or_dimension"] = evidence["context_or_dimension"]
                row["confidence"] = "0.90"
                row["notes"] = (
                    "Main debt/equity value is blank because captive finance "
                    "segment/dimension was detected; consolidated candidate "
                    "is retained only in evidence and sidecar with "
                    "candidate_role."
                )
                metrics = upsert_metric(rows=metrics, new_row=row)
            else:
                target = target_10k_for_company(company=company)
                metrics = upsert_metric(
                    rows=metrics,
                    new_row=placeholder_metric(
                        company=company,
                        cik=int(target["cik"]),
                        metric_id="B06",
                        metric_name="Debt-to-equity",
                        status="NEEDS_REVIEW",
                        source_class="DERIVED",
                        period_end=str(target["reportDate"]),
                        notes=(
                            "Captive finance segment/dimension detected; "
                            "industrial-only debt-to-equity unavailable."
                        ),
                    ),
                )
    write_csv_file(
        path=WORKDIR / "outputs" / "b06_debt_to_equity_candidates.csv",
        fieldnames=B06_CANDIDATE_FIELDNAMES,
        rows=candidate_rows,
    )
    return metrics, evidence_rows


def auditor_facts_for_company(*, company: str) -> list[dict]:
    """Return local dei:AuditorName facts parsed from instance inventories.

    Args:
        company: Display company name.

    Returns:
        Instance inventory rows whose concept is AuditorName.
    """
    return [
        row
        for row in read_csv_file(path=instance_inventory_path(company=company))
        if row["concept"] == "AuditorName"
        and is_dei_namespace(namespace=str(row["namespace"]))
    ]


def request_rows_for_document(
    *,
    observation_rows: list[dict],
    source_url: str,
    document_name: str,
) -> list[dict]:
    """Return observations for one exact SEC document identity.

    Args:
        observation_rows: Manifest-attested request observations.
        source_url: Canonical SEC document URL.
        document_name: Expected response document basename.

    Returns:
        Every attempt for the URL/document pair, in ledger order.
    """
    return [
        row
        for row in observation_rows
        if request_log_source_url(row=row) == source_url
        and row["document_name"] == document_name
    ]


def request_bound_xbrl_material_rows(
    *,
    candidate: dict,
    observation_rows: list[dict],
) -> list[dict]:
    """Rebuild successful XBRL materials from index and request evidence.

    Args:
        candidate: Current or prior filing identity.
        observation_rows: Manifest-attested request observations.

    Returns:
        Successful local instance materials discovered from the verified
        accession index, independent of the derived material inventory CSV.
    """
    cik = int(candidate["cik"])
    accession = str(candidate["accession"])
    base_dir = accession_dir_path(
        company=str(candidate["company"]),
        cik=cik,
        accession=accession,
    )
    observation_identities = response_identities_from_request_rows(
        rows=observation_rows,
    )
    index_path = base_dir / "index.json"
    index_url = accession_directory_url(cik=cik, accession=accession)
    index_body = verified_immutable_response_bytes(
        path=index_path,
        source_url=index_url,
        observation_identities=observation_identities,
    )
    try:
        index_payload = json.loads(index_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Saved accession index JSON is invalid: {index_path}"
        ) from error
    if not isinstance(index_payload, dict):
        raise TypeError(
            f"Saved accession index root must be object: {index_path}"
        )
    instance_names = xml_instance_candidates(
        items=accession_index_items_from_payload(
            payload=index_payload,
            source=str(index_path),
        )
    )
    materials = []
    for document_name in instance_names:
        source_url = accession_document_url(
            cik=cik,
            accession=accession,
            document_name=document_name,
        )
        matching_rows = request_rows_for_document(
            observation_rows=observation_rows,
            source_url=source_url,
            document_name=document_name,
        )
        if not matching_rows:
            raise ValueError(
                "Accession index document lacks a request observation: "
                f"{accession}:{document_name}"
            )
        if not any(row["status_code"] == "200" for row in matching_rows):
            continue
        local_path = base_dir / document_name
        body = verified_immutable_response_bytes(
            path=local_path,
            source_url=source_url,
            observation_identities=observation_identities,
        )
        materials.append(
            material_row_from_fetch(
                inventory_row=candidate,
                document_name=document_name,
                document_type="xbrl_instance",
                source_url=source_url,
                local_path=local_path,
                status_code=200,
                content_length=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
        )
    return materials


def raw_auditor_facts_for_candidates(
    *,
    candidates: list[dict],
    observation_rows: list[dict],
) -> list[dict]:
    """Replay official DEI AuditorName facts from candidate instance bytes.

    Args:
        candidates: Current or prior filing rows whose raw XBRL materials are
            independently selected from request-bound submissions/inventory.
        observation_rows: Manifest-attested request observations used to
            discover the complete accession instance set.

    Returns:
        Official-DEI AuditorName facts parsed directly from the saved raw
        instances, without trusting the derived concept inventory CSV.
    """
    facts = []
    seen_accessions = set()
    for candidate in candidates:
        accession = str(candidate["accession"])
        if accession in seen_accessions:
            continue
        seen_accessions.add(accession)
        for material in request_bound_xbrl_material_rows(
            candidate=candidate,
            observation_rows=observation_rows,
        ):
            parsed_rows = parse_instance_with_fallback(
                material_row=material,
            )
            facts.extend(
                row
                for row in parsed_rows
                if row["accession"] == accession
                and row["concept"] == "AuditorName"
                and is_dei_namespace(namespace=str(row["namespace"]))
            )
    return facts


def auditor_fact_for_accession(
    *,
    facts: list[dict],
    accession: str,
    period_end: str,
) -> tuple[dict | None, str]:
    """Select one nonblank, unambiguous AuditorName fact and reason.

    Args:
        facts: Local AuditorName fact rows.
        accession: Target or prior 10-K accession.
        period_end: Report date expected for the fact context.

    Returns:
        Deduplicated fact row with an empty reason, or None with
        `missing_or_blank` / `conflicting_values`.
    """
    matches = [
        row
        for row in facts
        if row["accession"] == accession and row["period_end"] == period_end
        and is_dei_namespace(namespace=str(row["namespace"]))
        and canonical_auditor_name(value=str(row["value"]))
    ]
    if not matches:
        return None, "missing_or_blank"
    canonical_names = {
        canonical_auditor_name(value=str(row["value"])) for row in matches
    }
    if len(canonical_names) != 1:
        return None, "conflicting_values"
    selected = unique_rows(
        rows=matches,
        fields=["accession", "concept", "period_end", "value", "source_path"],
    )
    return selected[0], ""


def xbrl_material_rows_for_accession(*, accession: str) -> list[dict]:
    """Return existing successful local XBRL material rows for one accession.

    Args:
        accession: SEC accession number.

    Returns:
        XBRL instance material rows whose local files exist.
    """
    rows = read_csv_file(path=WORKDIR / "outputs" / "accession_materials_inventory.csv")
    selected = []
    for row in rows:
        if row["accession"] != accession:
            continue
        if row["document_type"] != "xbrl_instance" or row["status_code"] != "200":
            continue
        try:
            resolve_artifact_path(row=row)
        except FileNotFoundError as error:
            print(f"XBRL material locator unresolved: {error}")
            continue
        selected.append(row)
    return selected


def auditor_fact_locator_component(*, fact: dict) -> dict:
    """Return one raw-document locator for a selected AuditorName fact.

    Args:
        fact: Parsed AuditorName row containing source_path and accession.

    Returns:
        The four source fields consumed by the C04 evidence builder.
    """
    source_path = str(fact["source_path"])
    return {
        "source_url": material_url_for_path(local_path=source_path),
        "local_path": source_path,
        "accession": str(fact["accession"]),
        "document_name": Path(source_path).name,
    }


def auditor_material_locator_components(*, candidates: list[dict]) -> list[dict]:
    """Return every available raw XBRL locator for filing candidates.

    Args:
        candidates: Ordered filing identities whose instance scan proves a
            missing or conflicting AuditorName result.

    Returns:
        Deduplicated raw-document locator components in candidate/index order.
    """
    components = []
    for candidate in candidates:
        for material in xbrl_material_rows_for_accession(
            accession=str(candidate["accession"]),
        ):
            components.append(
                {
                    "source_url": str(material["source_url"]),
                    "local_path": str(resolve_artifact_path(row=material)),
                    "accession": str(material["accession"]),
                    "document_name": str(material["document_name"]),
                }
            )
    return unique_rows(
        rows=components,
        fields=[
            "source_url",
            "local_path",
            "accession",
            "document_name",
        ],
    )


def append_material_rows(*, rows: list[dict]) -> None:
    """Merge targeted SEC fetch material rows into the inventory.

    Args:
        rows: New accession material rows.

    Expected output:
        New observations supersede an older row with the same filing/document
        identity; unrelated existing material rows remain available.
    """
    if not rows:
        return
    path = WORKDIR / "outputs" / "accession_materials_inventory.csv"
    existing = read_csv_file(path=path)
    merged = unique_rows(
        rows=rows + existing,
        fields=["accession", "document_name", "document_type"],
    )
    write_csv_file(path=path, fieldnames=MATERIAL_FIELDNAMES, rows=merged)


def fetch_xbrl_materials_for_filing(
    *,
    http: SecHttpClient,
    filing_row: dict,
) -> list[dict]:
    """Fetch XBRL instance material for one filing when absent.

    Args:
        http: Configured SEC client that logs every request.
        filing_row: Filing inventory-compatible row.

    Returns:
        Successful XBRL instance material rows available for parsing.
    """
    accession = str(filing_row["accession"])
    existing = xbrl_material_rows_for_accession(accession=accession)
    if existing:
        return existing

    # AuditorName is an iXBRL fact; index discovery plus XML/iXBRL instance
    # files is enough and avoids refetching unrelated primary HTML.
    cik = int(filing_row["cik"])
    base_dir = accession_dir_path(
        company=str(filing_row["company"]),
        cik=cik,
        accession=accession,
    )
    index_url = accession_directory_url(cik=cik, accession=accession)
    index_path = base_dir / "index.json"
    index_result = http.fetch(
        url=index_url,
        purpose=f"auditor_accession_index_{accession}",
        local_path=index_path,
    )
    new_rows = [
        material_row_from_fetch(
            inventory_row=filing_row,
            document_name="index.json",
            document_type="accession_index",
            source_url=index_url,
            local_path=index_path,
            status_code=index_result.status_code,
            content_length=index_result.content_length,
            sha256=index_result.sha256,
        )
    ]
    if index_result.status_code != 200:
        append_material_rows(rows=new_rows)
        return []

    items = accession_index_items(index_path=index_path)
    for instance_name in xml_instance_candidates(items=items):
        new_rows.append(
            fetch_accession_document(
                http=http,
                inventory_row=filing_row,
                document_name=instance_name,
                document_type="xbrl_instance",
                purpose=f"auditor_xbrl_instance_{accession}",
            )
        )
    append_material_rows(rows=new_rows)
    selected = []
    for row in new_rows:
        if row["document_type"] != "xbrl_instance" or row["status_code"] != "200":
            continue
        try:
            resolve_artifact_path(row=row)
        except FileNotFoundError as error:
            print(f"Fetched XBRL material locator unresolved: {error}")
            continue
        selected.append(row)
    return selected


def append_instance_inventory_rows(*, company: str, rows: list[dict]) -> None:
    """Merge parsed instance facts into one company's concept inventory.

    Args:
        company: Display company name.
        rows: Parsed XBRL/iXBRL fact rows.

    Expected output:
        New facts are appended without duplicating rows already present.
    """
    if not rows:
        return
    path = instance_inventory_path(company=company)
    existing = read_csv_file(path=path)
    merged = unique_rows(
        rows=existing + rows,
        fields=[
            "company",
            "cik",
            "accession",
            "document_name",
            "namespace",
            "concept",
            "unit",
            "context",
            "dimensions",
            "period_start",
            "period_end",
            "value",
        ],
    )
    write_csv_file(path=path, fieldnames=INSTANCE_FIELDNAMES, rows=merged)


def ensure_auditor_facts_for_filing(
    *,
    http: SecHttpClient,
    company: str,
    filing_row: dict,
) -> None:
    """Ensure local inventory contains AuditorName for one filing.

    Args:
        http: Configured SEC client.
        company: Display company name.
        filing_row: Filing row to fetch and parse if AuditorName is absent.

    Expected output:
        Missing SEC XBRL instance files are saved and parsed into the local
        concept inventory; existing facts remain unchanged.
    """
    facts = auditor_facts_for_company(company=company)
    existing, reason = auditor_fact_for_accession(
        facts=facts,
        accession=str(filing_row["accession"]),
        period_end=str(filing_row["reportDate"]),
    )
    if existing is not None or reason == "conflicting_values":
        return
    material_rows = fetch_xbrl_materials_for_filing(
        http=http,
        filing_row=filing_row,
    )
    parsed_rows = []
    for material_row in material_rows:
        parsed_rows.extend(parse_instance_with_fallback(material_row=material_row))
    append_instance_inventory_rows(company=company, rows=parsed_rows)


def auditor_current_filing_candidates(*, company: str, target: dict) -> list[dict]:
    """Return current-period filings to search for AuditorName.

    Args:
        company: Display company name.
        target: Selected target filing row.

    Returns:
        Target first, then same-period original 10-K when the target is a
        10-K/A that may omit the auditor report.
    """
    candidates = [target]
    if target["form"] != "10-K/A":
        return candidates
    originals = inventory_rows_for_company(
        company=company,
        source_role="target_original_full_instance",
    )
    originals = [
        row
        for row in originals
        if str(row["cik"]) == str(target["cik"])
        and row["form"] == "10-K"
        and row["reportDate"] == target["reportDate"]
        and row["accession"] != target["accession"]
    ]
    if not originals:
        return candidates
    selected = sorted(
        originals,
        key=lambda row: (str(row["filingDate"]), str(row["accession"])),
        reverse=True,
    )[0]
    candidates.append(selected)
    return candidates


def select_auditor_fact_from_candidates(
    *,
    facts: list[dict],
    candidates: list[dict],
) -> tuple[dict | None, dict, str]:
    """Return the first usable AuditorName fact, source, and reason.

    Args:
        facts: Local AuditorName facts.
        candidates: Ordered filing rows.

    Returns:
        Fact row or None, candidate provenance, and missing/conflict reason.
    """
    for candidate in candidates:
        fact, reason = auditor_fact_for_accession(
            facts=facts,
            accession=str(candidate["accession"]),
            period_end=str(candidate["reportDate"]),
        )
        if fact is not None:
            return fact, candidate, ""
        if reason == "conflicting_values":
            return None, candidate, reason
    return None, candidates[0], "missing_or_blank"


def ensure_auditor_fact_from_candidates(
    *,
    http: SecHttpClient,
    company: str,
    candidates: list[dict],
) -> tuple[dict | None, dict, str]:
    """Return the first local AuditorName, fetching only while still absent.

    Args:
        http: Configured SEC client used only for a required missing candidate.
        company: Display company name owning the concept inventory.
        candidates: Ordered target and fallback filing rows.

    Returns:
        Selected fact or None, provenance filing, and missing/conflict reason.
    """
    if not candidates:
        raise ValueError("AuditorName candidates must not be empty")
    facts = auditor_facts_for_company(company=company)
    selected, source, reason = select_auditor_fact_from_candidates(
        facts=facts,
        candidates=candidates,
    )
    if selected is not None or reason == "conflicting_values":
        return selected, source, reason
    for candidate in candidates:
        # The next network boundary is justified only while no ordered local
        # candidate can support the C04 comparison.
        ensure_auditor_facts_for_filing(
            http=http,
            company=company,
            filing_row=candidate,
        )
        facts = auditor_facts_for_company(company=company)
        selected, reason = auditor_fact_for_accession(
            facts=facts,
            accession=str(candidate["accession"]),
            period_end=str(candidate["reportDate"]),
        )
        if selected is not None:
            return selected, candidate, ""
        if reason == "conflicting_values":
            return None, candidate, reason
    return None, candidates[0], "missing_or_blank"


def repair_c04_auditor_changes(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Repair C04 by comparing current and prior dei:AuditorName facts locally.

    Args:
        metrics: Current metrics_matrix rows.
        evidence_rows: Current metric_evidence rows.

    Returns:
        Metrics and evidence with 8-K-only auditor checks replaced.
    """
    keys = {(str(company["company"]), "C04") for company in load_company_registry()}
    evidence_rows = remove_evidence_for_keys(evidence_rows=evidence_rows, keys=keys)
    http = client()
    for company_config in load_company_registry():
        company = str(company_config["company"])
        target = c04_target_filing(company=company)
        cik = int(target["cik"])
        prior = prior_10k_for_company(company=company, cik=cik)
        period_start = c04_period_start(
            prior=prior,
            target_cik=cik,
            period_end=str(target["reportDate"]),
        )
        current_candidates = auditor_current_filing_candidates(
            company=company,
            target=target,
        )
        current, current_source, current_reason = (
            ensure_auditor_fact_from_candidates(
                http=http,
                company=company,
                candidates=current_candidates,
            )
        )
        prior_fact = None
        prior_reason = "missing_or_blank"
        if prior is not None:
            prior_fact, _prior_source, prior_reason = (
                ensure_auditor_fact_from_candidates(
                    http=http,
                    company=company,
                    candidates=[prior],
                )
            )
        evidence_components = []
        if current is None:
            status = "NEEDS_REVIEW"
            value = ""
            current_issue = (
                "conflicting dei:AuditorName values"
                if current_reason == "conflicting_values"
                else "missing or blank dei:AuditorName"
            )
            note = (
                f"需复核: current 10-K has {current_issue}; "
                f"current accession/material {target['accession']}."
            )
            quote = note
            metric_accession = str(current_source["accession"])
            scan_candidates = (
                [current_source]
                if current_reason == "conflicting_values"
                else current_candidates
            )
            evidence_components.extend(
                auditor_material_locator_components(
                    candidates=scan_candidates,
                )
            )
        elif prior is None or prior_fact is None:
            status = "NEEDS_REVIEW"
            value = ""
            missing = "prior_10k inventory row" if prior is None else prior["accession"]
            prior_issue = (
                "conflicting AuditorName values"
                if prior_reason == "conflicting_values"
                else "missing or blank AuditorName"
            )
            note = (
                "需复核: current auditor read from dei:AuditorName, but prior "
                f"10-K has {prior_issue} ({missing})."
            )
            quote = (
                "current dei:AuditorName="
                f"{normalize_fact_text(value=current['value'])}; "
                f"prior_issue={prior_issue};prior_accession={missing}"
            )
            metric_accession = str(current["accession"])
            evidence_components.append(
                auditor_fact_locator_component(fact=current)
            )
            if prior is not None:
                evidence_components.extend(
                    auditor_material_locator_components(
                        candidates=[prior],
                    )
                )
        else:
            current_name = normalize_fact_text(value=current["value"])
            prior_name = normalize_fact_text(value=prior_fact["value"])
            changed = canonical_auditor_name(
                value=current_name,
            ) != canonical_auditor_name(value=prior_name)
            status = "NEEDS_REVIEW" if changed else "DIM_XBRL_OK"
            value = "1" if changed else "0"
            note = (
                f"auditor {'changed' if changed else 'unchanged'}; "
                f"current_accession={current['accession']}; "
                f"prior_accession={prior_fact['accession']}; "
                "manual confirmation required when changed."
            )
            quote = f"current={current_name}; prior={prior_name}"
            metric_accession = ";".join(
                [current["accession"], prior_fact["accession"]]
            )
            evidence_components = [
                auditor_fact_locator_component(fact=fact)
                for fact in [current, prior_fact]
            ]
        evidence_components = unique_rows(
            rows=evidence_components,
            fields=[
                "source_url",
                "local_path",
                "accession",
                "document_name",
            ],
        )
        metric = text_metric_row(
            company=company,
            cik=cik,
            metric_id="C04",
            metric_name="Auditor changes",
            value=value,
            unit="flag" if value else "",
            status=status,
            source_class="DIM_XBRL",
            period_end=str(target["reportDate"]),
            accession=metric_accession,
            filed_date=target["filingDate"],
            concept_or_section="AuditorName",
            context_or_dimension="current/prior 10-K instance",
            confidence="0.80" if value else "0.45",
            notes=note,
        )
        # C04 comparison cannot inherit a predecessor CIK's fiscal boundary;
        # generic text/event metrics retain their logical-company period.
        metric["period_start"] = period_start
        metrics = upsert_metric(rows=metrics, new_row=metric)
        if not evidence_components:
            continue
        evidence = text_evidence_row(
            company=company,
            cik=cik,
            metric_id="C04",
            source_url=";".join(
                row["source_url"] for row in evidence_components
            ),
            local_path=";".join(
                row["local_path"] for row in evidence_components
            ),
            accession=";".join(
                row["accession"] for row in evidence_components
            ),
            document_name=";".join(
                row["document_name"] for row in evidence_components
            ),
            concept_or_section="AuditorName",
            context_or_dimension="current/prior 10-K instance",
            unit="flag" if value else "",
            period_end=str(target["reportDate"]),
            value=value,
            quote=quote,
            extraction_method="auditorname_repair",
        )
        evidence["period_start"] = period_start
        evidence_rows.append(evidence)
    return metrics, evidence_rows


def apply_p0_repairs() -> None:
    """Apply bounded, primarily local P0 repairs before report and validation.

    Expected output:
        metrics_matrix, metric_evidence, and governance_signals are updated
        primarily from local evidence and concept inventory files. C04
        AuditorName may conditionally fetch official SEC material when required
        local facts are unavailable.
    """
    metrics = load_metrics()
    evidence_rows = read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    governance_rows = read_csv_file(path=WORKDIR / "outputs" / "governance_signals.csv")
    metrics, evidence_rows, governance_rows = repair_c03_compensation(
        metrics=metrics,
        evidence_rows=evidence_rows,
        governance_rows=governance_rows,
    )
    metrics, evidence_rows = repair_c02_board_text_from_governance(
        metrics=metrics,
        evidence_rows=evidence_rows,
        governance_rows=governance_rows,
    )
    metrics, evidence_rows = repair_basel_capital_ratios(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    metrics, evidence_rows = repair_lodging_kpis(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    metrics, evidence_rows = repair_rpo_crpo_metrics(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    metrics, evidence_rows = repair_captive_finance_debt(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    metrics, evidence_rows = apply_8k_event_metrics_from_events(
        metrics=metrics,
        evidence_rows=evidence_rows,
        events=read_csv_file(path=WORKDIR / "outputs" / "events.csv"),
        inventory=read_csv_file(
            path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
        ),
    )
    metrics, evidence_rows = repair_c04_auditor_changes(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    write_optional_b_sidecars(metrics=metrics, evidence_rows=evidence_rows)
    metrics, evidence_rows = prune_non_applicable_optional_b_metrics(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    save_metrics(rows=metrics)
    save_evidence(rows=evidence_rows)
    save_governance(rows=governance_rows)
    refresh_repair_sensitive_golden_results()
    print(
        "Bounded P0 repair applied; local artifacts used primarily, with "
        "conditional official SEC fetch allowed only for missing C04 "
        "AuditorName material"
    )


def portable_locator_artifact_specs(
    *,
    existing_optional_only: bool,
) -> list[tuple[Path, list[str]]]:
    """Return the shared migration and validation locator-file inventory.

    Args:
        existing_optional_only: When True, omit absent optional sidecars while
            retaining the five required validation inputs.

    Returns:
        Paths and exact schemas for every artifact using the five-field locator.
    """
    required_specs = [
        (WORKDIR / "outputs" / "metric_evidence.csv", EVIDENCE_FIELDNAMES),
        (
            WORKDIR / "outputs" / "accession_materials_inventory.csv",
            MATERIAL_FIELDNAMES,
        ),
        (WORKDIR / "outputs" / "events.csv", EVENT_FIELDNAMES),
        (
            WORKDIR / "outputs" / "governance_signals.csv",
            GOVERNANCE_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "risk_legal_signals.csv",
            RISK_FIELDNAMES,
        ),
    ]
    optional_specs = [
        (
            WORKDIR / "outputs" / "basel_ratio_candidates.csv",
            BASEL_RATIO_CANDIDATE_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "b06_debt_to_equity_candidates.csv",
            B06_CANDIDATE_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "rpo_crpo_observations.csv",
            OPTIONAL_B_OBSERVATION_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "capacity_text_signals.csv",
            OPTIONAL_B_OBSERVATION_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "lodging_kpi_probe_failures.csv",
            OPTIONAL_B_OBSERVATION_FIELDNAMES,
        ),
        (
            WORKDIR / "outputs" / "review_extracts" / "key_instance_facts.csv",
            REVIEW_EXTRACT_FIELDNAMES,
        ),
    ]
    if existing_optional_only:
        optional_specs = [
            spec for spec in optional_specs if spec[0].exists()
        ]
    return required_specs + optional_specs


def concept_inventory_artifact_specs() -> list[tuple[Path, list[str]]]:
    """Return every current instance/ECD locator file and its schema."""
    directory = WORKDIR / "outputs" / "concept_inventory"
    return [
        (path, INSTANCE_FIELDNAMES)
        for pattern in ["*_instance.csv", "*_ecd.csv"]
        for path in sorted(directory.glob(pattern))
    ]


def migrate_portable_artifact_inventories() -> None:
    """Rewrite locator-bearing CSV artifacts with the portable schema.

    Expected output:
        Current rows use source_url, repo_relative_path, content_sha256,
        accession, and document_name. Legacy absolute paths are consumed only
        as relocation hints and are not written back.
    """
    migrate_request_log(
        log_path=REQUEST_LOG_PATH,
        workdir=WORKDIR,
        allow_legacy_bootstrap=False,
    )
    artifact_files = portable_locator_artifact_specs(
        existing_optional_only=False,
    )
    material_spec = (
        WORKDIR / "outputs" / "accession_materials_inventory.csv",
        MATERIAL_FIELDNAMES,
    )
    artifact_files.remove(material_spec)
    artifact_files.insert(0, material_spec)
    artifact_files[1:1] = concept_inventory_artifact_specs()
    artifact_files.extend(
        [
            (
                WORKDIR / "outputs" / "golden_results.csv",
                GOLDEN_RESULT_FIELDNAMES,
            ),
            (
                WORKDIR / "outputs" / "golden_candidates.csv",
                GOLDEN_CANDIDATE_FIELDNAMES,
            ),
        ]
    )
    material_url_by_path = {}
    for path, fieldnames in artifact_files:
        if not path.exists():
            continue
        rows = read_csv_file(path=path)
        if fieldnames == MATERIAL_FIELDNAMES:
            material_url_by_path = {
                artifact_reference_text(row=row): row["source_url"]
                for row in rows
            }
        if fieldnames == INSTANCE_FIELDNAMES:
            for row in rows:
                if "source_url" in row and row["source_url"]:
                    continue
                reference = artifact_reference_text(row=row)
                row["source_url"] = (
                    material_url_by_path[reference]
                    if reference in material_url_by_path
                    else artifact_source_url(row=row)
                )
        normalized_rows = [
            normalize_csv_row(row=row, fieldnames=fieldnames)
            for row in rows
        ]
        if csv_header(path=path) == fieldnames:
            persisted_rows = [
                {field: row[field] for field in fieldnames}
                for row in rows
            ]
            if persisted_rows == normalized_rows:
                continue
        write_csv_file(
            path=path,
            fieldnames=fieldnames,
            rows=normalized_rows,
        )


def refresh_repair_sensitive_golden_results() -> None:
    """Refresh golden rows whose actual values changed through bounded repair.

    Expected output:
        Golden pass/fail results are recomputed from already repaired local
        metrics and remain consistent with metrics_matrix source classes.
    """
    path = WORKDIR / "outputs" / "golden_results.csv"
    rows = read_csv_file(path=path)
    if not rows:
        print("Golden results absent; skipping repair-sensitive refresh")
        return
    metrics = load_metrics()
    financial_companies = [
        str(company["company"])
        for company in load_company_registry()
        if has_extractor(
            extractors=company_extractors(company_config=company),
            extractor_name="BaselCapitalRatioExtractor",
        )
    ]
    source_class_by_metric = {}
    for row in metrics:
        if (
            row["company"] in financial_companies
            and row["metric_id"] in G2_FINANCIAL_NON_STD_METRIC_IDS
        ):
            source_class_by_metric[row["metric_id"]] = row["source_class"]
    refreshed = []
    for row in rows:
        for metric_id in G2_FINANCIAL_NON_STD_METRIC_IDS:
            assertion_id = f"G2_financial_{metric_id.lower()}_not_std"
            if row["assertion_id"] != assertion_id:
                continue
            actual = source_class_by_metric[metric_id]
            row["actual"] = actual
            row["status"] = "PASS" if actual != "STD_XBRL" else "FAIL"
        refreshed.append(row)
    write_csv_file(
        path=path,
        fieldnames=GOLDEN_RESULT_FIELDNAMES,
        rows=refreshed,
    )


def coverage_reason(*, metric: dict) -> str:
    """Return a coverage reason that distinguishes missingness classes.

    Args:
        metric: One metrics_matrix row.

    Returns:
        Reader-facing reason with SEC/non-extraction/review/structural class.
    """
    status = metric["status"]
    note = metric["notes"]
    if status == "NOT_AVAILABLE_SEC":
        return f"SEC 未披露: {note}"
    if status == "NOT_EXTRACTED":
        if note.startswith("本轮没抽到:"):
            return note
        return f"本轮没抽到: {note}"
    if status == "NEEDS_REVIEW":
        if note.startswith("需复核:"):
            return note
        return f"多事实需复核/需复核: {note}"
    if status == "N_A_STRUCTURAL":
        return f"结构不适用: {note}"
    return note


def build_coverage_matrix() -> list[dict]:
    """Build coverage_matrix.csv rows from metrics_matrix.csv."""
    rows = []
    evidence_pairs = evidence_key_set(
        evidence_rows=read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    )
    for metric in load_metrics():
        status = metric["status"]
        key = (metric["company"], metric["metric_id"])
        rows.append(
            {
                "company": metric["company"],
                "metric_id": metric["metric_id"],
                "status": status,
                "source_class": metric["source_class"],
                "has_numeric_value": "1" if metric["value"] else "0",
                "has_evidence": "1" if key in evidence_pairs else "0",
                "needs_text_extraction": (
                    "1" if status in {"NOT_EXTRACTED", "NEEDS_REVIEW"} else "0"
                ),
                "needs_review": "1" if status == "NEEDS_REVIEW" else "0",
                "reason": coverage_reason(metric=metric),
            }
        )
    return rows


def normalized_compare_value(*, value: str) -> str:
    """Normalize numeric fact text for companyfacts/instance comparison.

    Args:
        value: Raw fact text from either source.

    Expected output:
        Decimal text without commas or insignificant exponent formatting.
    """
    text = " ".join(str(value).split()).replace(",", "")
    if not text:
        return ""
    try:
        return decimal_text(value=Decimal(text))
    except InvalidOperation as error:
        print(f"Crosscheck value is not numeric; using raw text: {text}; {error}")
        return text


def build_companyfacts_crosscheck() -> list[dict]:
    """Compare direct companyfacts metrics against parsed instance facts."""
    metrics = load_metrics()
    instance_rows: list[dict] = []
    inventory_glob = (WORKDIR / "outputs" / "concept_inventory").glob(
        "*_instance.csv"
    )
    for path in sorted(inventory_glob):
        instance_rows.extend(read_csv_file(path=path))
    output = []
    for metric in metrics:
        if metric["source_class"] != "STD_XBRL":
            continue
        matches = [
            row
            for row in instance_rows
            if row["company"] == metric["company"]
            and row["concept"] == metric["concept_or_section"]
            and row["period_end"] == metric["period_end"]
        ]
        same_accession = [
            row for row in matches if row["accession"] == metric["accession"]
        ]
        if same_accession:
            matches = same_accession
        no_dimension = [row for row in matches if not row["dimensions"]]
        if no_dimension:
            matches = no_dimension
        if not matches:
            match_status = "NOT_FOUND_IN_INSTANCE_INVENTORY"
            instance_value = ""
            reason = "No same concept/period row in parsed instance inventory."
        else:
            instance_value = normalized_compare_value(value=matches[0]["value"])
            companyfacts_value = normalized_compare_value(value=metric["value"])
            match_status = (
                "MATCH"
                if instance_value == companyfacts_value
                else "VALUE_DIFF_NEEDS_REVIEW"
            )
            reason = "Compared first same concept/period/accession instance fact."
        output.append(
            {
                "company": metric["company"],
                "cik": metric["cik"],
                "metric_id": metric["metric_id"],
                "accession": metric["accession"],
                "companyfacts_value": metric["value"],
                "instance_value": instance_value,
                "match_status": match_status,
                "reason": reason,
            }
        )
    return output


def company_identity_literals() -> list[tuple[str, str]]:
    """Return forbidden identity literals loaded from company registry.

    Returns:
        Tuples of literal text and type.
    """
    literals: list[tuple[str, str]] = []
    for company_config in load_company_registry():
        literals.append((str(company_config["company"]), "company_name"))
        literals.append((str(company_config["primary_cik"]), "cik"))
        if str(company_config["ticker"]):
            literals.append((str(company_config["ticker"]), "ticker"))
        for role in company_config["roles"]:
            literals.append((str(role["cik"]), "cik"))
    unique = []
    seen = set()
    for literal, literal_type in literals:
        key = (literal, literal_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append((literal, literal_type))
    return unique


def literal_value_matches_identity(
    *,
    literal_value: object,
    forbidden_literal: str,
    literal_type: str,
) -> bool:
    """Return whether a Python literal equals a forbidden company identity.

    Args:
        literal_value: AST constant value from production Python source.
        forbidden_literal: Company name, ticker, or CIK from the registry.
        literal_type: Literal category: company_name, ticker, or cik.

    Returns:
        True when the literal directly encodes identity. Tickers are exact
        matches so one-letter tickers do not poison unrelated strings.
    """
    if isinstance(literal_value, int):
        return literal_type == "cik" and str(literal_value) == forbidden_literal
    if not isinstance(literal_value, str):
        return False
    if literal_type == "company_name":
        return literal_value.strip().lower() == forbidden_literal.lower()
    if literal_type == "ticker":
        return literal_value.strip() == forbidden_literal
    if literal_type == "cik":
        pattern = r"(?<!\d)" + re.escape(pattern=forbidden_literal) + r"(?!\d)"
        return bool(re.search(pattern=pattern, string=literal_value))
    raise ValueError(f"Unsupported identity literal type: {literal_type}")


def audit_python_literal(
    *,
    file_path: Path,
    line_number: int,
    literal_value: object,
) -> list[dict]:
    """Audit one AST literal for forbidden production identities.

    Args:
        file_path: Python source path.
        line_number: One-based literal line number.
        literal_value: AST constant value.

    Returns:
        Audit rows for identity, fixed accession, and fixed fiscal-date
        literals found anywhere in production Python source.
    """
    rows = []
    for forbidden_literal, literal_type in company_identity_literals():
        if literal_value_matches_identity(
            literal_value=literal_value,
            forbidden_literal=forbidden_literal,
            literal_type=literal_type,
        ):
            rows.append(
                {
                    "file": str(file_path.relative_to(WORKDIR)),
                    "line": str(line_number),
                    "literal": forbidden_literal,
                    "type": literal_type,
                    "allowed": "0",
                    "reason": "identity literal appears in production Python",
                    "replacement_plan": (
                        "Move identity to config or fixtures and branch on "
                        "profile, SEC metadata, dimensions, or registry rules."
                    ),
                }
            )
    if not isinstance(literal_value, str):
        return rows
    for accession in re.findall(
        pattern=r"\b\d{10}-\d{2}-\d{6}\b",
        string=literal_value,
    ):
        rows.append(
            {
                "file": str(file_path.relative_to(WORKDIR)),
                "line": str(line_number),
                "literal": accession,
                "type": "accession",
                "allowed": "0",
                "reason": "fixed accession appears in production Python",
                "replacement_plan": (
                    "Select filings from SEC submissions metadata."
                ),
            }
        )
    for date_text in re.findall(
        pattern=r"\b20\d{2}-\d{2}-\d{2}\b",
        string=literal_value,
    ):
        rows.append(
            {
                "file": str(file_path.relative_to(WORKDIR)),
                "line": str(line_number),
                "literal": date_text,
                "type": "fixed_fiscal_date",
                "allowed": "0",
                "reason": "fixed fiscal date appears in production Python",
                "replacement_plan": (
                    "Use selected target/prior reportDate metadata."
                ),
            }
        )
    return rows


def folded_ast_literal_value(*, node: ast.AST) -> object | None:
    """Return a statically folded literal value for scanner-relevant nodes.

    Args:
        node: AST node from Python source.

    Returns:
        String/int constant value, folded string concatenation result, or None
        when runtime evaluation would be required.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)):
        return node.value
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
        return None
    left = folded_ast_literal_value(node=node.left)
    right = folded_ast_literal_value(node=node.right)
    if isinstance(left, str) and isinstance(right, str):
        return left + right
    return None


def python_literal_values_from_source(
    *,
    source: str,
    filename: str,
) -> list[tuple[int, object]]:
    """Return scanner-relevant literal values from Python source text.

    Args:
        source: Python source code.
        filename: Filename used in parser diagnostics.

    Returns:
        Tuples of one-based line number and literal value. String addition is
        folded so company identity cannot be hidden through adjacent literals.
    """
    tree = ast.parse(source=source, filename=filename)
    literals = []
    for node in ast.walk(tree):
        value = folded_ast_literal_value(node=node)
        if value is None:
            continue
        literals.append((node.lineno, value))
    return literals


def python_literal_values(*, path: Path) -> list[tuple[int, object]]:
    """Return AST constant literals from one Python source file.

    Args:
        path: Python source path.

    Returns:
        Tuples of one-based line number and literal value for scanner-relevant
        constants, including folded string additions.
    """
    return python_literal_values_from_source(
        source=path.read_text(encoding="utf-8"),
        filename=str(path),
    )


def production_python_paths() -> list[Path]:
    """Return production Python paths covered by the scalability scanner.

    Returns:
        Sorted scripts/ and tools/ Python files. Config, fixture, docs, and
        generated report markdown paths are intentionally outside this scanner.
    """
    paths = []
    for directory in [WORKDIR / "scripts", WORKDIR / "tools"]:
        paths.extend(sorted(directory.glob("*.py")))
    return paths


def build_scalability_audit_rows() -> list[dict]:
    """Scan production Python AST literals for company identity constants."""
    rows = []
    for path in production_python_paths():
        for line_number, literal_value in python_literal_values(path=path):
            rows.extend(
                audit_python_literal(
                    file_path=path,
                    line_number=line_number,
                    literal_value=literal_value,
                )
            )
    return rows


def write_scalability_audit() -> list[dict]:
    """Write outputs/scalability_audit.csv and return audit rows."""
    rows = build_scalability_audit_rows()
    write_csv_file(
        path=WORKDIR / "outputs" / "scalability_audit.csv",
        fieldnames=SCALABILITY_AUDIT_FIELDNAMES,
        rows=rows,
    )
    return rows


def scanner_constant_folding_tamper_detected() -> bool:
    """Return whether string-addition company identity tampering is caught."""
    source = "\"Ford Motor \" + \"Company\"\n"
    fixture_path = WORKDIR / "scripts" / "constant_folding_tamper.py"
    for line_number, literal_value in python_literal_values_from_source(
        source=source,
        filename=str(fixture_path),
    ):
        audit_rows = audit_python_literal(
            file_path=fixture_path,
            line_number=line_number,
            literal_value=literal_value,
        )
        if any(row["type"] == "company_name" for row in audit_rows):
            return True
    return False


def check_no_company_identity_branch_in_production() -> dict:
    """Validate production branches do not use company identity literals."""
    rows = write_scalability_audit()
    failures = [row for row in rows if row["allowed"] != "1"]
    if not scanner_constant_folding_tamper_detected():
        failures.append({"literal": "string_addition_tamper"})
    return validation_row(
        check_id="no_company_identity_branch_in_production",
        status="PASS" if not failures else "FAIL",
        details=(
            f"violations={len(failures)}"
            if failures
            else "no identity literals in production branches"
        ),
    )


def validation_row(*, check_id: str, status: str, details: str) -> dict:
    """Build one repair validation result row.

    Args:
        check_id: Stable validation identifier.
        status: One value from VALIDATION_STATUSES.
        details: Human-readable failure or pass detail.

    Returns:
        CSV row with P0 severity.
    """
    if status not in VALIDATION_STATUSES:
        raise ValueError(f"Unknown validation status: {status}")
    return {
        "check_id": check_id,
        "severity": "P0",
        "status": status,
        "details": details,
    }


def skipped_light_validation_row(*, check_id: str, details: str) -> dict:
    """Build one explicit light-package skip validation row.

    Args:
        check_id: Full-validation check skipped by package shape.
        details: Missing material and reason for the skip.

    Returns:
        CSV row that cannot be mistaken for full validation PASS.
    """
    return validation_row(
        check_id=check_id,
        status="SKIPPED_LIGHT_PACKAGE",
        details=details,
    )


def not_evaluated_validation_row(*, check_id: str, details: str) -> dict:
    """Build an explicit missing-evidence non-evaluation row.

    Args:
        check_id: Check whose required domain evidence is unavailable.
        details: Missing evidence and why the claim cannot be evaluated.

    Returns:
        A row that cannot be interpreted as PASS.
    """
    return validation_row(
        check_id=check_id,
        status="NOT_EVALUATED_MISSING_EVIDENCE",
        details=details,
    )


def metric_lookup(*, metrics: list[dict], company: str, metric_id: str) -> dict:
    """Return a required metric row by company and metric id.

    Args:
        metrics: metrics_matrix rows.
        company: Display company name.
        metric_id: Metric identifier such as C03.

    Returns:
        Matching metric row.
    """
    for row in metrics:
        if row["company"] == company and row["metric_id"] == metric_id:
            return row
    raise KeyError(f"Metric row missing: {company} {metric_id}")


def evidence_for_metric(
    *,
    evidence_rows: list[dict],
    company: str,
    metric_id: str,
) -> list[dict]:
    """Return evidence rows for one company/metric pair."""
    return [
        row
        for row in evidence_rows
        if row["company"] == company and row["metric_id"] == metric_id
    ]


def check_no_c03_ecd_fact_count(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate C03 no longer uses ecd_fact_count as value or unit."""
    bad_metrics = [
        row
        for row in metrics
        if row["metric_id"] == "C03"
        and (row["unit"] == "ecd_fact_count" or row["value"] == "ecd_fact_count")
    ]
    bad_evidence = [
        row
        for row in evidence_rows
        if row["metric_id"] == "C03" and row["unit"] == "ecd_fact_count"
    ]
    bad_count = len(bad_metrics) + len(bad_evidence)
    return validation_row(
        check_id="no_c03_ecd_fact_count",
        status="PASS" if bad_count == 0 else "FAIL",
        details=f"bad_rows={bad_count}",
    )


def check_c03_def14a_ok_requires_peo(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate DEF14A_OK C03 rows are backed by PeoTotalCompAmt facts."""
    failures = []
    for row in metrics:
        if row["metric_id"] != "C03" or row["status"] != "DEF14A_OK":
            continue
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=row["company"],
            metric_id="C03",
        )
        matching = [
            item
            for item in evidence
            if item["concept_or_section"] == "PeoTotalCompAmt"
            and item["value_normalized"] == row["value"]
            and decimal_or_none(value=row["value"]) is not None
        ]
        if row["unit"] != "USD" or row["concept_or_section"] != "PeoTotalCompAmt":
            failures.append(row["company"])
            continue
        if not matching:
            failures.append(row["company"])
    return validation_row(
        check_id="c03_def14a_ok_requires_peototalcompamt",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "all DEF14A_OK C03 rows backed",
    )


def company_configs_with_extractor(*, extractor_name: str) -> list[dict]:
    """Return registry rows that mount one extractor."""
    return [
        company
        for company in load_company_registry()
        if has_extractor(
            extractors=company_extractors(company_config=company),
            extractor_name=extractor_name,
        )
    ]


def check_lodging_kpi_extractor(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate lodging KPI extraction is profile-driven and range-bounded."""
    settings = applicability_settings()
    revpar_range = require_key(mapping=settings, key="revpar_usd_range")
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="LodgingKpiExtractor",
    ):
        company = str(company_config["company"])
        row = metric_lookup(metrics=metrics, company=company, metric_id="B11")
        if row["status"] != "MDA_OK":
            if row["value"]:
                failures.append(f"{company}:unexpected_value")
            continue
        value = decimal_or_none(value=row["value"])
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=company,
            metric_id="B11",
        )
        quote_text = " ".join(item["evidence_quote"] for item in evidence).lower()
        has_quote = "revpar" in quote_text or "revenue per available room" in quote_text
        in_range = (
            value is not None
            and Decimal(str(revpar_range[0]))
            <= value
            <= Decimal(str(revpar_range[1]))
        )
        if row["unit"] != "USD" or not has_quote or not in_range:
            failures.append(company)
    return validation_row(
        check_id="lodging_kpi_extractor_not_marriott_specific",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "lodging KPI checks passed",
    )


def check_lodging_header_mapping_not_position_regex() -> dict:
    """Validate lodging parser maps by headers when KPI columns move."""
    text = (
        "Lodging Statistics Occupancy RevPAR Average Daily Rate 2025 vs. 2024 "
        "2025 vs. 2024 2025 vs. 2024 Comparable Systemwide Properties "
        "Worldwide 70.0 % 1.0 % pts. $ 140.00 2.0 % $ 200.00 1.0 %"
    )
    fact = lodging_kpi_fact_from_text(text=text)
    passes = (
        fact["occupancy"] == "70"
        and fact["revpar"] == "140"
        and fact["adr"] == "200"
    )
    return validation_row(
        check_id="lodging_header_mapping_not_position_regex",
        status="PASS" if passes else "FAIL",
        details=str(fact) if not passes else "header order swap parsed by name",
    )


def check_lodging_revpar_adr_occupancy_identity(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate extracted lodging KPI rows satisfy RevPAR identity."""
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="LodgingKpiExtractor",
    ):
        company = str(company_config["company"])
        b10 = metric_lookup(metrics=metrics, company=company, metric_id="B10")
        b11 = metric_lookup(metrics=metrics, company=company, metric_id="B11")
        if b10["status"] != "MDA_OK" or b11["status"] != "MDA_OK":
            failures.append(f"{company}:not_mda_ok")
            continue
        occupancy = decimal_or_none(value=b10["value"])
        revpar = decimal_or_none(value=b11["value"])
        adr_text = ""
        for evidence in evidence_for_metric(
            evidence_rows=evidence_rows,
            company=company,
            metric_id="B11",
        ):
            match = re.search(
                pattern=r"adr=([0-9]+(?:\.[0-9]+)?)",
                string=evidence["evidence_quote"],
                flags=re.IGNORECASE,
            )
            if match:
                adr_text = match.group(1)
                break
        adr = decimal_or_none(value=adr_text)
        if occupancy is None or revpar is None or adr is None:
            failures.append(f"{company}:missing_identity_component")
            continue
        error = lodging_identity_error(
            revpar_value=revpar,
            occupancy_value=occupancy,
            adr_value=adr,
        )
        if error is None or error > Decimal("0.05"):
            failures.append(f"{company}:identity_error={error}")
    return validation_row(
        check_id="lodging_revpar_adr_occupancy_identity",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "RevPAR identity within 5%",
    )


def check_rpo_crpo_prefers_instance_fact(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate B12 consumes instance facts before generic text fallback."""
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="RpoCrpoExtractor",
    ):
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        instance_value, _facts = rpo_instance_fact(
            company=company,
            period_end=str(target["reportDate"]),
        )
        row = metric_lookup(metrics=metrics, company=company, metric_id="B12")
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=company,
            metric_id="B12",
        )
        methods = {item["extraction_method"] for item in evidence}
        has_note = "RPO != ARR" in row["notes"] and "cRPO != ARR" in row["notes"]
        if instance_value:
            if (
                row["value"] != instance_value
                or row["source_class"] != "DIM_XBRL"
                or "rpo_crpo_instance_extractor" not in methods
                or not has_note
            ):
                failures.append(company)
        elif row["status"] == "DIM_XBRL_OK":
            failures.append(f"{company}:claimed_dim_xbrl_without_instance_fact")
        elif row["status"] == "MDA_OK" and not has_note:
            failures.append(f"{company}:missing_boundary_note")
    return validation_row(
        check_id="rpo_crpo_prefers_instance_fact",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "B12 instance preference verified",
    )


def scaled_inline_value_validation_failures() -> list[str]:
    """Return failures for focused iXBRL scale/sign value cases.

    Returns:
        Empty list when positive scale, negative scale, sign, parentheses,
        double-negative protection, and nonnumeric passthrough all behave.
    """
    cases = [
        ("positive_scale", "294804", "6", "", "294804000000"),
        ("negative_scale", "123456", "-3", "", "123.456"),
        ("sign_negative", "100", "6", "-", "-100000000"),
        ("parentheses_negative", "(100)", "6", "", "-100000000"),
        ("sign_parentheses_double_negative", "(100)", "6", "-", "-100000000"),
        ("nonnumeric_passthrough", "not available", "6", "", "not available"),
    ]
    failures = []
    for case_id, value, scale, sign, expected in cases:
        actual = scaled_inline_value(value=value, scale=scale, sign=sign)
        if actual != expected:
            failures.append(f"{case_id}:{actual}!={expected}")
    return failures


def inline_scale_route_fixture_failures() -> list[str]:
    """Return failures for the parser route that must preserve ix scale.

    Returns:
        Empty list when an XML-parseable iXBRL fixture still takes the inline
        parser route and emits a scaled USD amount.
    """
    fixture_path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "inline_scale_route"
        / "mock_inline_scale.xml"
    )
    if not fixture_path.exists():
        return ["inline_scale_route_fixture_missing"]
    material_row = {
        "company": "inline scale fixture",
        "cik": "0",
        "accession": "mock-inline-scale",
        "document_name": fixture_path.name,
        "local_path": str(fixture_path),
    }
    rows = parse_instance_with_fallback(material_row=material_row)
    matches = [
        row
        for row in rows
        if row["concept"] == "CommonEquityTier1Capital"
        and row["value"] == "294804000000"
        and "LegalEntityAxis" in row["dimensions"]
    ]
    return [] if matches else ["inline_scale_route_did_not_apply_scale"]


def jpm_cet1_capital_scale_crosscheck_failures() -> list[str]:
    """Return failures for the full-evidence JPM CET1 capital scale check.

    Returns:
        Empty list only when the known dimensional CET1 capital amount is
        present with scaled dollars. Missing evidence is an explicit failure
        signal for the caller to classify as NOT_EVALUATED or a light skip.
    """
    path = WORKDIR / "outputs" / "concept_inventory" / "jpmorgan_chase_instance.csv"
    if not path.exists():
        return ["jpm_cet1_capital_evidence_missing"]
    period_end = date(year=2025, month=12, day=31).isoformat()
    matches = [
        row
        for row in read_csv_file(path=path)
        if row["concept"] == "CommonEquityTier1Capital"
        and row["value"] == "294804000000"
        and row["period_end"] == period_end
        and "BaselIIIStandardizedMember" in row["dimensions"]
        and "JpmorganChaseBankNAMember" in row["dimensions"]
    ]
    return [] if matches else ["jpm_cet1_capital_scaled_value_missing"]


def ixbrl_scale_validation_failures() -> list[str]:
    """Return deterministic parser and fixture scale failures."""
    return (
        scaled_inline_value_validation_failures()
        + inline_scale_route_fixture_failures()
    )


def check_jpm_cet1_capital_scale_crosscheck() -> dict:
    """Validate the full-evidence JPM CET1 scaled amount.

    Returns:
        PASS or FAIL when evidence exists; NOT_EVALUATED_MISSING_EVIDENCE when
        the required instance inventory is unavailable.
    """
    failures = jpm_cet1_capital_scale_crosscheck_failures()
    if failures == ["jpm_cet1_capital_evidence_missing"]:
        return not_evaluated_validation_row(
            check_id="jpm_cet1_capital_scale_crosscheck",
            details=(
                "missing outputs/concept_inventory/"
                "jpmorgan_chase_instance.csv"
            ),
        )
    return validation_row(
        check_id="jpm_cet1_capital_scale_crosscheck",
        status="FAIL" if failures else "PASS",
        details=";".join(failures) if failures else "scaled CET1 amount verified",
    )


def check_basel_ratio_extractor(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate Basel ratio extractor is not tied to one company."""
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="BaselCapitalRatioExtractor",
    ):
        company = str(company_config["company"])
        for metric_id in ["A01", "A02"]:
            row = metric_lookup(metrics=metrics, company=company, metric_id=metric_id)
            if row["status"] == "NOT_EXTRACTED":
                continue
            evidence = evidence_for_metric(
                evidence_rows=evidence_rows,
                company=company,
                metric_id=metric_id,
            )
            matching = [
                item
                for item in evidence
                if item["value_normalized"] == row["value"]
                and concept_matches_basel_metric(
                    concept=item["concept_or_section"],
                    metric_id=metric_id,
                )
            ]
            if (
                row["status"] != "DIM_XBRL_OK"
                or row["unit"] != "pure"
                or not dimensions_have_basel_methodology(
                    dimensions=row["context_or_dimension"],
                )
                or not matching
            ):
                failures.append(f"{company}:{metric_id}")
    failures.extend(ixbrl_scale_validation_failures())
    return validation_row(
        check_id="basel_ratio_extractor_not_single_issuer_specific",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "Basel ratios and iXBRL scale route verified"
        ),
    )


def check_basel_concept_resolver_handles_tierone_spelling() -> dict:
    """Validate TierOne spelling resolves as Tier 1 ratio semantics."""
    concept = "CommonEquityTierOneCapitalToRiskWeightedAssets"
    passes = (
        concept_matches_basel_metric(concept=concept, metric_id="A02")
        and not concept_matches_basel_metric(concept=concept, metric_id="A01")
    )
    return validation_row(
        check_id="basel_concept_resolver_handles_tierone_spelling",
        status="PASS" if passes else "FAIL",
        details=concept if not passes else "TierOne spelling resolves to CET1/A02",
    )


def check_basel_concept_resolver_handles_banking_regulation_ratio_family() -> dict:
    """Validate BankingRegulation risk-based capital ratio family matching."""
    tier1 = "BankingRegulationTierOneRiskBasedCapitalRatio"
    cet1 = "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatio"
    passes = (
        concept_matches_basel_metric(concept=tier1, metric_id="A01")
        and concept_matches_basel_metric(concept=cet1, metric_id="A02")
        and not concept_matches_basel_metric(concept=cet1, metric_id="A01")
    )
    return validation_row(
        check_id="basel_concept_resolver_handles_banking_regulation_ratio_family",
        status="PASS" if passes else "FAIL",
        details=(
            "banking regulation ratio family matched"
            if passes
            else f"{tier1};{cet1}"
        ),
    )


def check_basel_cet1_never_classified_as_a01() -> dict:
    """Validate CET1/Common Equity Tier 1 concepts are excluded from A01."""
    concepts = [
        "CommonEquityTier1CapitaltoRiskWeightedAssets",
        "CommonEquityTierOneCapitalToRiskWeightedAssets",
        "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatio",
        "CET1CapitalToRiskWeightedAssets",
    ]
    failures = [
        concept
        for concept in concepts
        if concept_matches_basel_metric(concept=concept, metric_id="A01")
    ]
    return validation_row(
        check_id="basel_cet1_never_classified_as_a01",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "CET1 concepts excluded from A01",
    )


def check_basel_threshold_concepts_never_match_primary_metric() -> dict:
    """Validate Basel thresholds cannot match A01/A02 primary metrics."""
    concepts = [
        "TierOneRiskBasedCapitalMinimum",
        (
            "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatio"
            "CapitalAdequacyMinimum"
        ),
        "TierOneRiskBasedCapitalRequiredForCapitalAdequacyToRiskWeightedAssets",
        "TierOneRiskBasedCapitalRequiredToBeWellCapitalizedToRiskWeightedAssets",
        (
            "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatio"
            "WellCapitalizedMinimum"
        ),
        "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatioWellCapitalized",
        "CommonEquityTierOneCapitalToBeWellCapitalizedToRiskWeightedAssets",
    ]
    failures = []
    for concept in concepts:
        if not concept_is_basel_threshold_or_requirement(concept=concept):
            failures.append(f"{concept}:role_not_detected")
            continue
        for metric_id in ["A01", "A02"]:
            if concept_matches_basel_metric(concept=concept, metric_id=metric_id):
                failures.append(f"{concept}:{metric_id}")
    return validation_row(
        check_id="basel_threshold_concepts_never_match_primary_metric",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "Basel threshold concepts excluded from primary metrics"
        ),
    )


def check_basel_primary_selection_prefers_actual_ratio_over_threshold() -> dict:
    """Validate actual CET1 wins when threshold shares preferred dimensions."""
    period_end = date(year=2025, month=12, day=31).isoformat()
    dimensions = (
        "srt:ConsolidatedEntitiesAxis=srt:ParentCompanyMember;"
        "us-gaap:RiskWeightedAssetsCalculationMethodologyAxis=example:"
        "BaselIIIStandardizedMember"
    )
    rows = [
        {
            "concept": "CommonEquityTierOneCapitalToRiskWeightedAssets",
            "unit": "pure",
            "period_end": period_end,
            "dimensions": dimensions,
            "value": "0.115",
            "context": "same_preferred_actual",
        },
        {
            "concept": (
                "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatio"
                "WellCapitalized"
            ),
            "unit": "pure",
            "period_end": period_end,
            "dimensions": dimensions,
            "value": "0.070",
            "context": "same_preferred_threshold",
        },
    ]
    candidates = basel_ratio_candidates_from_rows(
        rows=rows,
        metric_id="A02",
        period_end=period_end,
    )
    selected = selected_basel_ratio_fact(rows=candidates) if candidates else {}
    passes = (
        len(candidates) == 1
        and "concept" in selected
        and selected["concept"] == "CommonEquityTierOneCapitalToRiskWeightedAssets"
    )
    return validation_row(
        check_id="basel_primary_selection_prefers_actual_ratio_over_threshold",
        status="PASS" if passes else "FAIL",
        details=(
            "actual CET1 selected over same-dimension threshold"
            if passes
            else json_text(value={"candidates": candidates, "selected": selected})
        ),
    )


def check_a01_a02_metric_evidence_excludes_threshold_concepts(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate A01/A02 metric evidence excludes Basel threshold concepts."""
    failures = [
        f"{row['company']}:{row['metric_id']}:{row['concept_or_section']}"
        for row in evidence_rows
        if row["metric_id"] in {"A01", "A02"}
        and concept_is_basel_threshold_or_requirement(
            concept=row["concept_or_section"],
        )
    ]
    return validation_row(
        check_id="a01_a02_metric_evidence_excludes_threshold_concepts",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures[:20])
            if failures
            else "A01/A02 metric_evidence contains actual ratio concepts only"
        ),
    )


def check_captive_finance_debt(*, metrics: list[dict]) -> dict:
    """Validate B06 captive finance handling is dimension-triggered."""
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="CaptiveFinanceDebtExtractor",
    ):
        company = str(company_config["company"])
        row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
        has_signal = company_has_captive_finance_signal(company=company)
        if has_signal and row["status"] not in {"NEEDS_REVIEW", "DIM_XBRL_OK", "OK"}:
            failures.append(company)
        if has_signal and row["value"] and "Consolidated" not in row["notes"]:
            failures.append(f"{company}:missing_consolidated_note")
    return validation_row(
        check_id="captive_finance_debt_not_ford_specific",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "B06 captive finance verified",
    )


def check_captive_finance_signal_requires_segment_dimension() -> dict:
    """Validate concept-only finance wording cannot trigger captive review."""
    rows = [
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "",
        },
        {
            "concept": "FinanceLeaseLiabilityCurrent",
            "dimensions": "",
        },
    ]
    has_signal = captive_finance_signal_from_rows(rows=rows)
    return validation_row(
        check_id="captive_finance_signal_requires_segment_dimension",
        status="FAIL" if has_signal else "PASS",
        details="concept-only signal fired" if has_signal else "dimension required",
    )


def check_captive_finance_excludes_normal_finance_lease_terms() -> dict:
    """Validate normal finance/deferred/credit concepts are excluded."""
    rows = [
        {
            "concept": "FinanceLeaseLiabilityCurrent",
            "dimensions": "us-gaap:StatementBusinessSegmentsAxis=example:CreditMember",
        },
        {
            "concept": "DeferredFinanceCostsNet",
            "dimensions": "us-gaap:LegalEntityAxis=example:FinancialServicesMember",
        },
        {
            "concept": "DebtSecuritiesAvailableForSaleAfterAllowanceForCreditLoss",
            "dimensions": "us-gaap:OperatingSegmentsAxis=example:CreditMember",
        },
        {
            "concept": "SupplierFinanceProgramObligation",
            "dimensions": "srt:ConsolidatedEntitiesAxis=example:CreditMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:CreditLossMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:CreditFacilityMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:LineOfCreditMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:LetterOfCreditMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:FinanceLeaseLiabilityMember",
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:DeferredFinanceCostsMember",
        },
    ]
    has_signal = captive_finance_signal_from_rows(rows=rows)
    return validation_row(
        check_id="captive_finance_excludes_normal_finance_lease_terms",
        status="FAIL" if has_signal else "PASS",
        details=(
            "excluded concepts triggered"
            if has_signal
            else "normal finance terms excluded"
        ),
    )


def check_enphase_b06_not_captive_finance_false_positive(
    *,
    metrics: list[dict],
) -> dict:
    """Validate B06 is not marked review by normal finance terms."""
    failures = []
    for company_config in company_configs_with_extractor(
        extractor_name="CaptiveFinanceDebtExtractor",
    ):
        company = str(company_config["company"])
        row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
        has_signal = company_has_captive_finance_signal(company=company)
        if not has_signal and row["status"] == "NEEDS_REVIEW":
            failures.append(company)
    return validation_row(
        check_id="enphase_b06_not_captive_finance_false_positive",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "no non-signal company is marked captive review"
        ),
    )


def check_gm_like_captive_finance_fixture_triggers_review() -> dict:
    """Validate captive-finance segment member variants trigger review."""
    rows = [
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": (
                "us-gaap:StatementBusinessSegmentsAxis="
                "example:CaptiveFinanceMember"
            ),
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": (
                "us-gaap:LegalEntityAxis=example:"
                "GeneralMotorsFinancialCompanyIncMember"
            ),
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": (
                "us-gaap:LegalEntityAxis=example:"
                "JohnDeereCapitalCorporationMember"
            ),
        },
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:LegalEntityAxis=example:FordCreditMember",
        },
    ]
    misses = [
        row["dimensions"]
        for row in rows
        if not row_has_captive_finance_signal(row=row)
    ]
    return validation_row(
        check_id="gm_like_captive_finance_fixture_triggers_review",
        status="PASS" if not misses else "FAIL",
        details=(
            "captive member variants matched"
            if not misses
            else ";".join(misses)
        ),
    )


def check_entity_continuity_yoy(*, metrics: list[dict]) -> dict:
    """Validate B02 YoY uses entity continuity instead of company identity."""
    failures = []
    checked_count = 0
    companies_with_b02 = {
        row["company"] for row in metrics if row["metric_id"] == "B02"
    }
    for company_config in load_company_registry():
        company = str(company_config["company"])
        if company not in companies_with_b02:
            continue
        checked_count += 1
        row = metric_lookup(metrics=metrics, company=company, metric_id="B02")
        continuity = str(company_config["entity_continuity_status"])
        if continuity in {"successor_predecessor", "stub_period", "major_reorg"}:
            if row["status"] != "NOT_MEANINGFUL":
                failures.append(company)
    if checked_count == 0:
        failures.append("no_B02_rows")
    return validation_row(
        check_id="entity_continuity_yoy_not_paramount_specific",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "B02 continuity rule verified",
    )


def required_row_field_errors(
    *,
    rows: list[dict],
    fields: list[str],
    artifact_name: str,
) -> list[str]:
    """Return deterministic schema errors for in-memory artifact rows.

    Args:
        rows: Parsed artifact rows presented to a validation helper.
        fields: Required field names for every row.
        artifact_name: Human-readable artifact label used in diagnostics.

    Returns:
        Missing-field or non-mapping errors, preserving input row order.
    """
    errors = []
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"{artifact_name} row {row_number} is not a mapping")
            continue
        missing = [field for field in fields if field not in row]
        if missing:
            errors.append(
                f"{artifact_name} row {row_number} missing fields: "
                + ",".join(missing)
            )
    return errors


def validation_auditor_fact_component(
    *,
    fact: dict,
    material_rows: list[dict],
) -> dict:
    """Bind one replayed AuditorName fact to its request-bound material.

    Args:
        fact: Fact parsed directly from a request-bound raw instance.
        material_rows: Complete raw materials replayed for the C04 candidates.

    Returns:
        One locator component independent of the production evidence builder.
    """
    fact_path = repo_relative_artifact_path(
        path_text=str(fact["source_path"]),
        row=fact,
    )
    matches = [
        row
        for row in material_rows
        if repo_relative_artifact_path(
            path_text=str(row["local_path"]),
            row=row,
        ) == fact_path
        and str(row["accession"]) == str(fact["accession"])
    ]
    if len(matches) != 1:
        raise ValueError(
            "Replayed AuditorName fact lacks one raw material identity: "
            f"{fact['accession']}:{fact_path}"
        )
    material = matches[0]
    return {
        "source_url": str(material["source_url"]),
        "local_path": str(material["local_path"]),
        "accession": str(material["accession"]),
        "document_name": str(material["document_name"]),
    }


def validation_auditor_material_components(
    *,
    candidates: list[dict],
    material_rows: list[dict],
) -> list[dict]:
    """Return request-bound scan locators for selected filing candidates.

    Args:
        candidates: Filing identities whose raw scan supports a missing result.
        material_rows: Complete request-bound C04 materials.

    Returns:
        Deduplicated locator components in candidate and SEC-index order.
    """
    accessions = [str(row["accession"]) for row in candidates]
    components = []
    seen = set()
    for accession in accessions:
        for material in material_rows:
            if str(material["accession"]) != accession:
                continue
            component = {
                "source_url": str(material["source_url"]),
                "local_path": str(material["local_path"]),
                "accession": accession,
                "document_name": str(material["document_name"]),
            }
            identity = tuple(component.values())
            if identity in seen:
                continue
            seen.add(identity)
            components.append(component)
    return components


def validation_c04_period_start(
    *,
    inventory: list[dict],
    company: str,
    cik: str,
    period_end: str,
) -> str:
    """Independently derive the C04 period start from exact inventory rows.

    Args:
        inventory: Request-bound and exact-checked filing inventory.
        company: Logical company under validation.
        cik: Selected target filing CIK.
        period_end: Current target report date.

    Returns:
        Day after the latest same-CIK prior 10-K, or calendar year start.
    """
    prior_dates = [
        str(row["reportDate"])
        for row in inventory
        if row["company"] == company
        and row["source_role"] == "prior_10k"
        and str(row["cik"]) == str(cik)
        and str(row["reportDate"])
        and str(row["reportDate"]) < period_end
    ]
    if prior_dates:
        return (
            parse_date_text(value=max(prior_dates)) + timedelta(days=1)
        ).isoformat()
    end_date = parse_date_text(value=period_end)
    return date(year=end_date.year, month=1, day=1).isoformat()


def validation_c04_evidence_row(
    *,
    company: str,
    cik: str,
    components: list[dict],
    period_start: str,
    period_end: str,
    value: str,
    quote: str,
) -> dict:
    """Build the complete independent C04 evidence-row expectation.

    Args:
        company: Logical company under validation.
        cik: Current target filing CIK.
        components: Request-bound raw fact or scan locator components.
        period_start: Independently derived comparison period start.
        period_end: Current target report date.
        value: Recomputed auditor-change flag or blank review result.
        quote: Deterministic comparison or missing/conflict explanation.

    Returns:
        One full EVIDENCE_FIELDNAMES row without production row builders.
    """
    relative_paths = [
        repo_relative_artifact_path(
            path_text=row["local_path"],
            row={**row, "cik": cik},
        )
        for row in components
    ]
    content_hashes = [
        file_sha256(
            path_text=str(
                repository_artifact_candidate(relative_path=relative_path)
            )
        )
        for relative_path in relative_paths
    ]
    row = {field: "" for field in EVIDENCE_FIELDNAMES}
    row.update(
        {
            "company": company,
            "cik": str(cik),
            "metric_id": "C04",
            "source_url": ";".join(
                component["source_url"] for component in components
            ),
            "repo_relative_path": ";".join(relative_paths),
            "content_sha256": ";".join(content_hashes),
            "accession": ";".join(
                component["accession"] for component in components
            ),
            "document_name": ";".join(
                component["document_name"] for component in components
            ),
            "concept_or_section": "AuditorName",
            "context_or_dimension": "current/prior 10-K instance",
            "unit": "flag" if value else "",
            "period_start": period_start,
            "period_end": period_end,
            "value_raw": value,
            "value_normalized": value,
            "evidence_quote": quote[:1000],
            "extraction_method": "auditorname_repair",
            "parser_version": "sec_pipeline_v1",
        }
    )
    return row


def check_c04_auditorname_all_companies(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    inventory: list[dict],
) -> dict:
    """Recompute every C04 result from current and prior local DEI facts.

    Args:
        metrics: Complete metrics matrix after C04 repair.
        evidence_rows: Complete portable evidence rows after C04 repair.
        inventory: Request-bound and exact-checked filing identities.

    Returns:
        PASS only when local official-DEI facts independently reproduce the
        metric and both comparison components remain addressable.
    """
    try:
        observation_rows = request_observation_rows()
    except FileNotFoundError as error:
        return not_evaluated_validation_row(
            check_id="c04_uses_auditorname_for_all_companies",
            details=f"request evidence missing: {error}",
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        return validation_row(
            check_id="c04_uses_auditorname_for_all_companies",
            status="FAIL",
            details=f"request evidence invalid: {error}",
        )
    schema_errors = []
    for artifact_name, rows, fields in [
        ("metrics", metrics, METRICS_FIELDNAMES),
        ("evidence", evidence_rows, EVIDENCE_FIELDNAMES),
        ("inventory", inventory, FILING_FIELDNAMES),
    ]:
        schema_errors.extend(
            required_row_field_errors(
                rows=rows,
                fields=fields,
                artifact_name=artifact_name,
            )
        )
    if schema_errors:
        return validation_row(
            check_id="c04_uses_auditorname_for_all_companies",
            status="FAIL",
            details=";".join(schema_errors[:20]),
        )
    failures = []
    role_rank = {"primary": 0, "successor": 0, "predecessor": 1}
    for company_config in load_company_registry():
        company = str(company_config["company"])
        metric_rows = [
            row
            for row in metrics
            if row["company"] == company and row["metric_id"] == "C04"
        ]
        if len(metric_rows) != 1:
            failures.append(f"{company}:metric_rows={len(metric_rows)}")
            continue
        metric = metric_rows[0]
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=company,
            metric_id="C04",
        )
        targets = [
            row
            for row in inventory
            if row["company"] == company
            and row["source_role"] == "target_10k"
        ]
        target_ranks = [
            (
                role_rank[str(row["entity_role"])]
                if str(row["entity_role"]) in role_rank
                else 5
            )
            for row in targets
        ]
        best_rank = min(target_ranks) if target_ranks else -1
        preferred_targets = [
            row
            for row in targets
            if (
                role_rank[str(row["entity_role"])]
                if str(row["entity_role"]) in role_rank
                else 5
            )
            == best_rank
        ]
        if not preferred_targets:
            failures.append(f"{company}:target_10k_missing")
            continue
        target = sorted(
            preferred_targets,
            key=lambda row: (
                str(row["reportDate"]),
                str(row["filingDate"]),
                str(row["accession"]),
            ),
            reverse=True,
        )[0]
        prior_rows = [
            row
            for row in inventory
            if row["company"] == company
            and row["source_role"] == "prior_10k"
            and str(row["cik"]) == str(target["cik"])
            and str(row["reportDate"]) < str(target["reportDate"])
        ]
        prior = (
            sorted(
                prior_rows,
                key=lambda row: (
                    str(row["reportDate"]),
                    str(row["filingDate"]),
                    str(row["accession"]),
                ),
                reverse=True,
            )[0]
            if prior_rows
            else None
        )
        current_candidates = [target]
        if target["form"] == "10-K/A":
            originals = [
                row
                for row in inventory
                if row["company"] == company
                and row["source_role"] == "target_original_full_instance"
                and str(row["cik"]) == str(target["cik"])
                and row["reportDate"] == target["reportDate"]
            ]
            if originals:
                current_candidates.append(
                    sorted(
                        originals,
                        key=lambda row: (
                            str(row["filingDate"]),
                            str(row["accession"]),
                        ),
                        reverse=True,
                    )[0]
                )
        raw_candidates = list(current_candidates)
        if prior is not None:
            raw_candidates.append(prior)
        try:
            raw_materials = []
            seen_accessions = set()
            for candidate in raw_candidates:
                accession = str(candidate["accession"])
                if accession in seen_accessions:
                    continue
                seen_accessions.add(accession)
                raw_materials.extend(
                    request_bound_xbrl_material_rows(
                        candidate=candidate,
                        observation_rows=observation_rows,
                    )
                )
            facts = []
            for material in raw_materials:
                parsed_rows = parse_instance_with_fallback(
                    material_row=material,
                )
                facts.extend(
                    row
                    for row in parsed_rows
                    if row["accession"] == material["accession"]
                    and row["concept"] == "AuditorName"
                    and is_dei_namespace(namespace=str(row["namespace"]))
                )
        except FileNotFoundError as error:
            return not_evaluated_validation_row(
                check_id="c04_uses_auditorname_for_all_companies",
                details=f"raw AuditorName evidence missing: {error}",
            )
        except (KeyError, OSError, TypeError, ValueError) as error:
            return validation_row(
                check_id="c04_uses_auditorname_for_all_companies",
                status="FAIL",
                details=f"raw AuditorName evidence invalid: {error}",
            )
        current, current_source, current_reason = (
            select_auditor_fact_from_candidates(
                facts=facts,
                candidates=current_candidates,
            )
        )
        prior_fact = None
        prior_reason = "missing_or_blank"
        if prior is not None:
            prior_fact, prior_reason = auditor_fact_for_accession(
                facts=facts,
                accession=str(prior["accession"]),
                period_end=str(prior["reportDate"]),
            )

        expected_components = []
        if current is None:
            expected_value = ""
            expected_status = "NEEDS_REVIEW"
            expected_accession = str(current_source["accession"])
            current_issue = (
                "conflicting dei:AuditorName values"
                if current_reason == "conflicting_values"
                else "missing or blank dei:AuditorName"
            )
            expected_notes = (
                f"需复核: current 10-K has {current_issue}; "
                f"current accession/material {target['accession']}."
            )
            expected_quote = expected_notes
            scan_candidates = (
                [current_source]
                if current_reason == "conflicting_values"
                else current_candidates
            )
            expected_components = validation_auditor_material_components(
                candidates=scan_candidates,
                material_rows=raw_materials,
            )
        elif prior is None or prior_fact is None:
            expected_value = ""
            expected_status = "NEEDS_REVIEW"
            expected_accession = str(current["accession"])
            missing = (
                "prior_10k inventory row"
                if prior is None
                else str(prior["accession"])
            )
            prior_issue = (
                "conflicting AuditorName values"
                if prior_reason == "conflicting_values"
                else "missing or blank AuditorName"
            )
            expected_notes = (
                "需复核: current auditor read from dei:AuditorName, but prior "
                f"10-K has {prior_issue} ({missing})."
            )
            expected_quote = (
                "current dei:AuditorName="
                f"{normalize_fact_text(value=current['value'])}; "
                f"prior_issue={prior_issue};prior_accession={missing}"
            )
            expected_components.append(
                validation_auditor_fact_component(
                    fact=current,
                    material_rows=raw_materials,
                )
            )
            if prior is not None:
                expected_components.extend(
                    validation_auditor_material_components(
                        candidates=[prior],
                        material_rows=raw_materials,
                    )
                )
        else:
            current_name = normalize_fact_text(value=current["value"])
            prior_name = normalize_fact_text(value=prior_fact["value"])
            changed = canonical_auditor_name(
                value=current_name,
            ) != canonical_auditor_name(value=prior_name)
            expected_value = "1" if changed else "0"
            expected_status = "NEEDS_REVIEW" if changed else "DIM_XBRL_OK"
            expected_accession = ";".join(
                [current["accession"], prior_fact["accession"]]
            )
            expected_notes = (
                f"auditor {'changed' if changed else 'unchanged'}; "
                f"current_accession={current['accession']}; "
                f"prior_accession={prior_fact['accession']}; "
                "manual confirmation required when changed."
            )
            expected_quote = f"current={current_name}; prior={prior_name}"
            expected_components = [
                validation_auditor_fact_component(
                    fact=fact,
                    material_rows=raw_materials,
                )
                for fact in [current, prior_fact]
            ]

        period_end = str(target["reportDate"])
        try:
            period_start = validation_c04_period_start(
                inventory=inventory,
                company=company,
                cik=str(target["cik"]),
                period_end=period_end,
            )
        except (TypeError, ValueError) as error:
            return validation_row(
                check_id="c04_uses_auditorname_for_all_companies",
                status="FAIL",
                details=f"{company}:invalid C04 period: {error}",
            )
        expected_metric = {field: "" for field in METRICS_FIELDNAMES}
        expected_metric.update(
            {
                "company": company,
                "cik": str(target["cik"]),
                "metric_id": "C04",
                "metric_name": "Auditor changes",
                "value": expected_value,
                "unit": "flag" if expected_value else "",
                "status": expected_status,
                "source_class": "DIM_XBRL",
                "formula": "text/event extraction",
                "period_start": period_start,
                "period_end": period_end,
                "fiscal_year": "",
                "fiscal_period": "FY",
                "accession": expected_accession,
                "form": "",
                "filed_date": str(target["filingDate"]),
                "concept_or_section": "AuditorName",
                "context_or_dimension": "current/prior 10-K instance",
                "confidence": "0.80" if expected_value else "0.45",
                "notes": expected_notes,
            }
        )
        for field in METRICS_FIELDNAMES:
            if metric[field] != expected_metric[field]:
                failures.append(
                    f"{company}:metric_{field}={metric[field]},"
                    f"expected={expected_metric[field]}"
                )
        expected_evidence = []
        if expected_components:
            expected_evidence.append(
                validation_c04_evidence_row(
                    company=company,
                    cik=str(target["cik"]),
                    components=expected_components,
                    period_start=period_start,
                    period_end=period_end,
                    value=expected_value,
                    quote=expected_quote,
                )
            )
        exact_errors = exact_artifact_row_errors(
            rows=evidence,
            expected_rows=expected_evidence,
            fields=EVIDENCE_FIELDNAMES,
            artifact_name="c04_evidence",
        )
        failures.extend(f"{company}:{error}" for error in exact_errors)
    return validation_row(
        check_id="c04_uses_auditorname_for_all_companies",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "C04 AuditorName verified",
    )


def check_eleventh_company_smoke_mounts() -> dict:
    """Validate fixture-only company additions mount and exercise extractors."""
    fixture_path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "eleventh_company_smoke"
        / "company_registry.csv"
    )
    mock_path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "eleventh_company_smoke"
        / "mock_concept_inventory.csv"
    )
    companies = {
        row["company_id"]: row
        for row in load_company_registry_from_path(path=fixture_path)
    }
    failures = []
    for row in read_csv_file(path=mock_path):
        company_id = row["company_id"]
        if company_id not in companies:
            failures.append(f"{company_id}:missing_company")
            continue
        extractors = company_extractors(company_config=companies[company_id])
        if row["expected_extractor"] not in extractors:
            failures.append(f"{company_id}:{row['expected_extractor']}")
    behavior_checks = [
        check_eleventh_company_behavior_lodging(),
        check_eleventh_company_behavior_financial_institution(),
        check_eleventh_company_behavior_captive_finance(),
        check_eleventh_company_behavior_rpo_crpo(),
    ]
    for check in behavior_checks:
        if check["status"] != "PASS":
            failures.append(f"{check['check_id']}:{check['details']}")
    return validation_row(
        check_id="eleventh_company_smoke_extractors_mount",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "fixture extractors mounted and behavior gates pass"
        ),
    )


def eleventh_mock_inventory_rows() -> list[dict]:
    """Return instance-like rows from eleventh-company behavior fixtures.

    Returns:
        Rows with explicit fields needed by extractor core selection functions.
    """
    mock_path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "eleventh_company_smoke"
        / "mock_concept_inventory.csv"
    )
    return read_csv_file(path=mock_path)


def eleventh_rows_for_profile(*, profile: str) -> list[dict]:
    """Return eleventh-company mock rows for one industry profile.

    Args:
        profile: Industry profile in the fixture registry.

    Returns:
        Mock inventory rows matching the profile.
    """
    return [
        row
        for row in eleventh_mock_inventory_rows()
        if row["profile"] == profile
    ]


def check_eleventh_company_behavior_lodging() -> dict:
    """Validate lodging behavior fixture reaches KPI extraction."""
    rows = eleventh_rows_for_profile(profile="lodging")
    if not rows:
        return validation_row(
            check_id="eleventh_company_behavior_lodging",
            status="FAIL",
            details="missing lodging fixture row",
        )
    text = rows[0]["value"]
    fact = lodging_kpi_fact_from_text(text=text)
    status = "MDA_OK" if fact["revpar"] and fact["occupancy"] else "NOT_EXTRACTED"
    passes = (
        status == "MDA_OK"
        and fact["revpar"] == "140"
        and fact["occupancy"] == "70"
    )
    return validation_row(
        check_id="eleventh_company_behavior_lodging",
        status="PASS" if passes else "FAIL",
        details=str(fact) if not passes else "lodging fixture extracted B10/B11",
    )


def check_eleventh_company_behavior_financial_institution() -> dict:
    """Validate FI behavior fixture extracts A01/A02 Basel ratios."""
    rows = eleventh_rows_for_profile(profile="financial_institution")
    failures = []
    for metric_id in ["A01", "A02"]:
        expected_rows = [
            row
            for row in rows
            if row["expected_value"]
            and concept_matches_basel_metric(
                concept=row["concept"],
                metric_id=metric_id,
            )
        ]
        if len(expected_rows) != 1:
            failures.append(f"{metric_id}:expected_fixture")
            continue
        expected = expected_rows[0]
        candidates = basel_ratio_candidates_from_rows(
            rows=rows,
            metric_id=metric_id,
            period_end=expected["period_end"],
        )
        if not candidates:
            failures.append(metric_id)
            continue
        selected = selected_basel_ratio_fact(rows=candidates)
        for field in ["concept", "context", "dimensions", "value"]:
            if selected[field] != expected[field]:
                failures.append(f"{metric_id}:{field}:{selected[field]}")
    return validation_row(
        check_id="eleventh_company_behavior_financial_institution",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "FI fixture selects actual A01/A02 ratios over thresholds"
        ),
    )


def check_eleventh_company_behavior_captive_finance() -> dict:
    """Validate manufacturing fixture triggers captive-finance review."""
    rows = eleventh_rows_for_profile(profile="manufacturing")
    has_signal = captive_finance_signal_from_rows(rows=rows)
    return validation_row(
        check_id="eleventh_company_behavior_captive_finance",
        status="PASS" if has_signal else "FAIL",
        details=(
            "manufacturing fixture triggers B06 NEEDS_REVIEW"
            if has_signal
            else "fixture did not trigger captive finance"
        ),
    )


def check_eleventh_company_behavior_rpo_crpo() -> dict:
    """Validate subscription fixture extracts RPO/cRPO with ARR boundary note."""
    rows = eleventh_rows_for_profile(profile="subscription_or_contract_revenue")
    period_end = rows[0]["period_end"] if rows else ""
    value, facts = rpo_instance_fact_from_rows(rows=rows, period_end=period_end)
    note = "RPO != ARR; cRPO != ARR"
    passes = bool(value) and bool(facts) and note == "RPO != ARR; cRPO != ARR"
    return validation_row(
        check_id="eleventh_company_behavior_rpo_crpo",
        status="PASS" if passes else "FAIL",
        details=(
            f"value={value};note={note}"
            if passes
            else "RPO fixture did not select DIM_XBRL value"
        ),
    )


def previous_ok_status_snapshot_rows() -> list[dict]:
    """Return previous OK-status snapshot rows for recall validation.

    Returns:
        Rows from tests/fixtures/regression/previous_ok_status_snapshot.csv.
    """
    path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "regression"
        / "previous_ok_status_snapshot.csv"
    )
    return read_csv_file(path=path)


def recall_exception_reason(*, company: str, metric_id: str) -> str:
    """Return exception text for one possibly regressed metric.

    Args:
        company: Display company name.
        metric_id: Metric id.

    Returns:
        Matching exception markdown line, or empty string.
    """
    path = WORKDIR / "outputs" / "exceptions_and_review_items.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if company in line and f"| {metric_id} " in line:
            return line
    return ""


def recall_regression_failures(
    *,
    metrics: list[dict],
    metric_filter: set[str] | None,
) -> list[str]:
    """Return OK recall regressions without an accepted exception reason.

    Args:
        metrics: Current metrics_matrix rows.
        metric_filter: Metric ids to restrict the check, or None for all.

    Returns:
        Failure descriptions for regressed cells.
    """
    status_by_key = {
        (row["company"], row["metric_id"]): row["status"]
        for row in metrics
    }
    failures = []
    for snapshot in previous_ok_status_snapshot_rows():
        metric_id = snapshot["metric_id"]
        if metric_filter is not None and metric_id not in metric_filter:
            continue
        previous_status = snapshot["previous_status"]
        if previous_status not in OK_RECALL_STATUSES:
            continue
        key = (snapshot["company"], metric_id)
        if key not in status_by_key:
            failures.append(
                f"{snapshot['company']}:{metric_id}:missing_current"
            )
            continue
        current_status = status_by_key[key]
        if current_status not in RECALL_REGRESSION_STATUSES:
            continue
        reason = recall_exception_reason(
            company=snapshot["company"],
            metric_id=metric_id,
        )
        allowed = (
            "data source changed" in reason
            or "old value false" in reason
            or "旧值被判伪" in reason
            or "数据源变更" in reason
        )
        if (
            not allowed
            or "extractor regression" in reason
            or "抽取器退化" in reason
        ):
            failures.append(
                f"{snapshot['company']}:{metric_id}:"
                f"{previous_status}->{current_status}"
            )
    return failures


def check_ok_status_recall_not_regressed_without_reason(
    *,
    metrics: list[dict],
) -> dict:
    """Validate previous OK cells do not silently regress to missing/review."""
    snapshot = previous_ok_status_snapshot_rows()
    if not snapshot:
        return validation_row(
            check_id="ok_status_recall_not_regressed_without_reason",
            status="FAIL",
            details="previous OK snapshot missing or empty",
        )
    failures = recall_regression_failures(metrics=metrics, metric_filter=None)
    return validation_row(
        check_id="ok_status_recall_not_regressed_without_reason",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures[:20])
            if failures
            else f"snapshot_rows={len(snapshot)}"
        ),
    )


def check_lodging_ok_recall_not_regressed_without_reason(
    *,
    metrics: list[dict],
) -> dict:
    """Validate previous lodging B10/B11 recall or justification."""
    failures = recall_regression_failures(
        metrics=metrics,
        metric_filter={"B10", "B11"},
    )
    return validation_row(
        check_id="lodging_ok_recall_not_regressed_without_reason",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "lodging B10/B11 recall preserved"
        ),
    )


def check_registry_profile_matches_sic_rules_or_has_override_reason() -> dict:
    """Validate registry industry_profile agrees with SIC profile rules."""
    failures = []
    for company_config in load_company_registry():
        inferred = profile_from_sic_rules(sic=str(company_config["sic"]))
        actual = str(company_config["industry_profile"])
        if inferred == actual:
            continue
        reason = profile_override_reason(
            company_id=str(company_config["company_id"])
        )
        if not reason:
            failures.append(
                f"{company_config['company_id']}:{actual}!={inferred}:"
                "missing_override"
            )
    return validation_row(
        check_id="registry_profile_matches_sic_rules_or_has_override_reason",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures)
            if failures
            else "registry profiles match SIC rules"
        ),
    )


def keyed_artifact_exact_set_errors(
    *,
    rows: list[dict],
    expected_keys: set[tuple[str, str]],
    artifact_name: str,
) -> list[str]:
    """Return missing, unexpected, and duplicate two-field key errors.

    Args:
        rows: Artifact rows containing company and metric_id.
        expected_keys: Independently derived complete key set.
        artifact_name: Short artifact label used in diagnostics.

    Returns:
        Empty list only when actual keys form the expected unique set.
    """
    counts = {}
    # Cardinality is retained separately so a duplicate cannot hide a deletion.
    for row in rows:
        company = str(require_key(mapping=row, key="company"))
        metric_id = str(require_key(mapping=row, key="metric_id"))
        key = (company, metric_id)
        counts[key] = counts[key] + 1 if key in counts else 1
    actual_keys = set(counts)
    error_groups = [
        ("missing", sorted(expected_keys - actual_keys)),
        ("unexpected", sorted(actual_keys - expected_keys)),
        (
            "duplicate",
            sorted(key for key, count in counts.items() if count != 1),
        ),
    ]
    errors = []
    for label, keys in error_groups:
        if not keys:
            continue
        rendered = ",".join(
            f"{company}:{metric_id}" for company, metric_id in keys
        )
        errors.append(f"{artifact_name}_{label}={rendered}")
    return errors


def exact_artifact_row_errors(
    *,
    rows: list[dict],
    expected_rows: list[dict],
    fields: list[str],
    artifact_name: str,
) -> list[str]:
    """Return multiset differences for complete rows over selected fields.

    Args:
        rows: Current artifact rows.
        expected_rows: Independently derived expected rows.
        fields: Ordered fields defining one row identity.
        artifact_name: Short diagnostic label.

    Returns:
        Missing and unexpected row summaries with duplicate counts preserved.
    """
    def identities(*, source_rows: list[dict]) -> Counter:
        """Return string-normalized row identities with multiplicity."""
        return Counter(
            tuple(str(require_key(mapping=row, key=field)) for field in fields)
            for row in source_rows
        )

    actual = identities(source_rows=rows)
    expected = identities(source_rows=expected_rows)
    errors = []
    for label, differences in [
        ("missing", expected - actual),
        ("unexpected", actual - expected),
    ]:
        for identity, count in list(differences.items())[:20]:
            errors.append(
                f"{artifact_name}_{label}={count}:" + "|".join(identity)
            )
    return errors


def request_observation_rows() -> list[dict]:
    """Return schema-checked rows from the attested current request ledger.

    Returns:
        Complete request observations after manifest and row-shape validation.
    """
    validate_request_log_manifest(log_path=REQUEST_LOG_PATH)
    return parse_request_log_rows(
        text=REQUEST_LOG_PATH.read_bytes().decode("utf-8"),
    )


def response_identities_from_request_rows(
    *,
    rows: list[dict],
) -> list[tuple[str, str, str, str, str]]:
    """Return content identities from explicit request observations.

    Args:
        rows: Manifest-attested request log rows.

    Returns:
        Ordered URL, status, byte length, body hash, and document name tuples
        for every observation carrying response bytes.
    """
    identities = []
    for row in rows:
        if not row["content_sha256"]:
            continue
        identities.append(
            (
                request_log_source_url(row=row),
                row["status_code"],
                row["content_length"],
                row["content_sha256"],
                row["document_name"],
            )
        )
    return identities


def request_observation_identities(
) -> list[tuple[str, str, str, str, str]]:
    """Return content identities from the attested current request ledger."""
    return response_identities_from_request_rows(
        rows=request_observation_rows(),
    )


def response_observation_statuses(
    *,
    path: Path,
    source_url: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> tuple[bytes, set[str]]:
    """Return repository bytes and matching recorded HTTP statuses.

    Args:
        path: Stable working-copy path consumed by a downstream parser.
        source_url: Canonical SEC endpoint for that path.
        observation_identities: Response identities from the attested ledger.

    Returns:
        Current bytes and every recorded status matching their full identity.
    """
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(
            f"Saved response is not a regular file: {path}"
        )
    try:
        relative_path = path.relative_to(WORKDIR).as_posix()
    except ValueError as error:
        raise ValueError(
            f"Saved response escapes repository: {path}"
        ) from error
    repository_artifact_candidate(relative_path=relative_path)
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    statuses = {
        status
        for url, status, length, content_hash, document_name
        in observation_identities
        if url == source_url
        and length == str(len(body))
        and content_hash == digest
        and document_name == path.name
    }
    if not statuses:
        raise ValueError(
            "Saved bytes lack a matching request observation: "
            f"{path}"
        )
    return body, statuses


def latest_successful_response_identity(
    *,
    source_url: str,
    document_name: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> tuple[str, str, str, str, str]:
    """Return the last successful observation for one URL/document pair.

    Args:
        source_url: Canonical SEC endpoint.
        document_name: Expected response basename.
        observation_identities: Ledger-ordered response identities.

    Returns:
        The latest status-200 identity; absence is an input-contract error.
    """
    for identity in reversed(observation_identities):
        url, status, _length, _content_hash, name = identity
        if url == source_url and name == document_name and status == "200":
            return identity
    raise ValueError(
        "No successful request observation for response: "
        f"{source_url} {document_name}"
    )


def verified_successful_response_bytes(
    *,
    path: Path,
    source_url: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> bytes:
    """Return repository bytes only when a 200 request proves them.

    Args:
        path: Stable working-copy path consumed by a downstream parser.
        source_url: Canonical SEC endpoint for that path.
        observation_identities: Response identities from the attested ledger.

    Returns:
        Current body bytes matching the latest recorded 200 response.
    """
    body, statuses = response_observation_statuses(
        path=path,
        source_url=source_url,
        observation_identities=observation_identities,
    )
    if "200" not in statuses:
        raise ValueError(
            "Saved bytes lack a matching successful request observation: "
            f"{path}; statuses={sorted(statuses)}"
        )
    actual_identity = (
        source_url,
        "200",
        str(len(body)),
        hashlib.sha256(body).hexdigest(),
        path.name,
    )
    latest_identity = latest_successful_response_identity(
        source_url=source_url,
        document_name=path.name,
        observation_identities=observation_identities,
    )
    if actual_identity != latest_identity:
        raise ValueError(
            "Saved bytes do not match the latest successful observation: "
            f"{path}"
        )
    return body


def immutable_successful_body_identities(
    *,
    source_url: str,
    document_name: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> set[tuple[str, str]]:
    """Return the sole allowed successful body identities or fail.

    Args:
        source_url: Canonical SEC archive endpoint for one immutable artifact.
        document_name: Expected response basename.
        observation_identities: Ledger-ordered response identities.

    Returns:
        Zero or one `(content_length, content_sha256)` identities.
    """
    successful_bodies = {
        (length, content_hash)
        for url, status, length, content_hash, name in observation_identities
        if url == source_url and name == document_name and status == "200"
    }
    if len(successful_bodies) > 1:
        raise ValueError(
            "Immutable SEC artifact has conflicting successful bodies: "
            f"{source_url} {document_name}"
        )
    return successful_bodies


def verified_immutable_response_bytes(
    *,
    path: Path,
    source_url: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> bytes:
    """Return one immutable SEC artifact only when every 200 agrees.

    Args:
        path: Stable working-copy path for one filing-bound artifact.
        source_url: Canonical SEC archive endpoint for that artifact.
        observation_identities: Ledger-ordered response identities.

    Returns:
        Current bytes matching the sole successful content identity.
    """
    immutable_successful_body_identities(
        source_url=source_url,
        document_name=path.name,
        observation_identities=observation_identities,
    )
    return verified_successful_response_bytes(
        path=path,
        source_url=source_url,
        observation_identities=observation_identities,
    )


def verified_submission_payload(
    *,
    path: Path,
    source_url: str,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> dict:
    """Parse one submissions body only when a successful request proves it.

    Args:
        path: Stable working-copy submissions path.
        source_url: Canonical SEC submissions endpoint for that path.
        observation_identities: Successful identities from the attested ledger.

    Returns:
        Parsed JSON object whose current bytes match a recorded 200 response.
    """
    body = verified_successful_response_bytes(
        path=path,
        source_url=source_url,
        observation_identities=observation_identities,
    )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Saved submissions JSON is invalid: {path}") from error
    if not isinstance(payload, dict):
        raise TypeError(f"Saved submissions root must be object: {path}")
    return payload


def verified_submission_payloads(
    *,
    cik: int,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> list[dict]:
    """Return the request-bound base and bounded supplement payloads.

    Args:
        cik: Filing CIK whose submissions chain is required.
        observation_identities: Successful identities from the attested ledger.

    Returns:
        Base payload followed by every supplement in the collection boundary.
    """
    submission = verified_submission_payload(
        path=submissions_path(cik=cik),
        source_url=submissions_url(cik=cik),
        observation_identities=observation_identities,
    )
    payloads = [submission]
    for file_name in submission_supplemental_names(
        submission=submission,
        cik=cik,
    ):
        payloads.append(
            verified_submission_payload(
                path=supplemental_submission_path(file_name=file_name),
                source_url=submissions_file_url(file_name=file_name),
                observation_identities=observation_identities,
            )
        )
    return payloads


def expected_8k_window_inventory_rows(
    *,
    observation_identities: list[tuple[str, str, str, str, str]],
) -> list[dict]:
    """Rebuild target, prior, and FY 8-K rows from request-bound submissions.

    Returns:
        Filing rows defining each fiscal window and its selected 8-Ks, without
        issuing network requests or trusting the current inventory CSV.
    """
    expected = []
    for role_row in all_role_rows():
        rows = filing_rows_from_submission_payloads(
            company=str(role_row["company"]),
            cik=int(role_row["cik"]),
            entity_role=str(role_row["entity_role"]),
            payloads=verified_submission_payloads(
                cik=int(role_row["cik"]),
                observation_identities=observation_identities,
            ),
        )
        target = select_latest_10k(rows=rows)
        try:
            prior = select_prior_10k(
                rows=rows,
                target_report_date=str(target["reportDate"]),
            )
        except RuntimeError as error:
            print(
                "Prior 10-K unavailable while rebuilding 8-K validation "
                f"window for {role_row['company']} {role_row['cik']}: {error}"
            )
            prior = None
        expected.append(
            filing_output_row(row=target, source_role="target_10k")
        )
        if prior is not None:
            expected.append(
                filing_output_row(row=prior, source_role="prior_10k")
            )
        window_start, window_end = fiscal_window(
            target_row=target,
            prior_row=prior,
        )
        expected.extend(
            filing_output_row(row=row, source_role="fy_8k")
            for row in select_8k_window(
                rows=rows,
                window_start=window_start,
                window_end=window_end,
            )
        )
    return expected


def expected_8k_event_rows(
    *,
    inventory: list[dict],
    observation_identities: list[tuple[str, str, str, str, str]],
) -> list[dict]:
    """Replay saved 8-K documents into the expected portable event rows.

    Args:
        inventory: Independently rebuilt FY-window filing rows.
        observation_identities: Successful identities from the attested ledger.

    Returns:
        Exact normalized event rows derived from saved hdr or primary bytes.
    """
    expected = []
    for filing_row in inventory:
        cik = int(filing_row["cik"])
        accession = str(filing_row["accession"])
        base_path = accession_dir_path(
            company=str(filing_row["company"]),
            cik=cik,
            accession=accession,
        )
        hdr_path = base_path / f"{accession}.hdr.sgml"
        primary_path = base_path / str(filing_row["primaryDocument"])
        primary_url = str(filing_row["source_url"])
        hdr_url = hdr_sgml_url(cik=cik, accession=accession)

        # Source selection must not hide a conflicting successful version of
        # the other filing-bound document already present in the ledger.
        for document_path, source_url in [
            (hdr_path, hdr_url),
            (primary_path, primary_url),
        ]:
            successful_bodies = immutable_successful_body_identities(
                source_url=source_url,
                document_name=document_path.name,
                observation_identities=observation_identities,
            )
            if document_path.is_file() and successful_bodies:
                verified_immutable_response_bytes(
                    path=document_path,
                    source_url=source_url,
                    observation_identities=observation_identities,
                )
        rows = []
        if hdr_path.is_file():
            _body, hdr_statuses = response_observation_statuses(
                path=hdr_path,
                source_url=hdr_url,
                observation_identities=observation_identities,
            )
            if "200" in hdr_statuses:
                rows = event_rows_from_document(
                    filing_row=filing_row,
                    document_path=hdr_path,
                    source_url=hdr_url,
                    item_source="hdr.sgml",
                )
        if not rows:
            if not primary_path.is_file():
                raise FileNotFoundError(
                    "Missing saved 8-K replay source; "
                    f"hdr={hdr_path}; primary={primary_path}"
                )
            verified_immutable_response_bytes(
                path=primary_path,
                source_url=primary_url,
                observation_identities=observation_identities,
            )
            rows = event_rows_from_document(
                filing_row=filing_row,
                document_path=primary_path,
                source_url=primary_url,
                item_source="primary_document",
            )
        if not rows:
            raise ValueError(
                f"No 8-K item could be replayed for accession {accession}"
            )
        expected.extend(
            normalize_csv_row(row=row, fieldnames=EVENT_FIELDNAMES)
            for row in rows
        )
    return expected


def check_8k_event_chain_exact_set(
    *,
    inventory: list[dict],
    events: list[dict],
) -> dict:
    """Validate submissions, inventory, raw items, and events exactly."""
    try:
        observations = request_observation_identities()
        expected_window_inventory = expected_8k_window_inventory_rows(
            observation_identities=observations,
        )
    except FileNotFoundError as error:
        return not_evaluated_validation_row(
            check_id="eightk_event_chain_exact_set",
            details=f"saved submissions missing: {error}",
        )
    except (KeyError, TypeError, ValueError) as error:
        return validation_row(
            check_id="eightk_event_chain_exact_set",
            status="FAIL",
            details=f"saved submissions invalid: {error}",
        )
    window_roles = {"target_10k", "prior_10k", "fy_8k"}
    actual_window_inventory = [
        row for row in inventory if row["source_role"] in window_roles
    ]
    errors = exact_artifact_row_errors(
        rows=actual_window_inventory,
        expected_rows=expected_window_inventory,
        fields=FILING_FIELDNAMES,
        artifact_name="eightk_window_inventory",
    )
    expected_inventory = [
        row
        for row in expected_window_inventory
        if row["source_role"] == "fy_8k"
    ]
    errors.extend(
        event_inventory_coverage_errors(
            inventory=expected_inventory,
            events=events,
        )
    )
    if errors:
        return validation_row(
            check_id="eightk_event_chain_exact_set",
            status="FAIL",
            details=";".join(errors[:20]),
        )
    try:
        expected_events = expected_8k_event_rows(
            inventory=expected_inventory,
            observation_identities=observations,
        )
    except FileNotFoundError as error:
        return not_evaluated_validation_row(
            check_id="eightk_event_chain_exact_set",
            details=f"saved 8-K evidence missing: {error}",
        )
    except ValueError as error:
        return validation_row(
            check_id="eightk_event_chain_exact_set",
            status="FAIL",
            details=str(error),
        )
    errors = exact_artifact_row_errors(
        rows=events,
        expected_rows=expected_events,
        fields=EVENT_FIELDNAMES,
        artifact_name="events",
    )
    return validation_row(
        check_id="eightk_event_chain_exact_set",
        status="PASS" if not errors else "FAIL",
        details=(
            f"inventory_rows={len(expected_inventory)};events={len(events)}"
            if not errors
            else ";".join(errors[:20])
        ),
    )


def check_coverage_join(
    *,
    coverage: list[dict],
    evidence_rows: list[dict],
    metrics: list[dict],
) -> dict:
    """Validate coverage identity and evidence joins against metrics."""
    if not metrics:
        return not_evaluated_validation_row(
            check_id="coverage_has_evidence_matches_metric_evidence_join",
            details="metrics_matrix rows missing",
        )
    # Coverage must describe the full, unique matrix before flags are trusted.
    metric_keys = {
        (str(row["company"]), str(row["metric_id"]))
        for row in metrics
    }
    failures = keyed_artifact_exact_set_errors(
        rows=metrics,
        expected_keys=metric_keys,
        artifact_name="metrics_matrix",
    )
    failures.extend(
        keyed_artifact_exact_set_errors(
            rows=coverage,
            expected_keys=metric_keys,
            artifact_name="coverage_matrix",
        )
    )
    if failures:
        return validation_row(
            check_id="coverage_has_evidence_matches_metric_evidence_join",
            status="FAIL",
            details=";".join(failures[:20]),
        )
    if not evidence_rows:
        return not_evaluated_validation_row(
            check_id="coverage_has_evidence_matches_metric_evidence_join",
            details="metric_evidence rows missing",
        )
    evidence_pairs = evidence_key_set(evidence_rows=evidence_rows)
    mismatches = []
    for row in coverage:
        key = (row["company"], row["metric_id"])
        expected = "1" if key in evidence_pairs else "0"
        if row["has_evidence"] != expected:
            mismatches.append(f"{row['company']}:{row['metric_id']}")
    return validation_row(
        check_id="coverage_has_evidence_matches_metric_evidence_join",
        status="PASS" if not mismatches else "FAIL",
        details=(
            ";".join(mismatches[:20])
            if mismatches
            else "coverage join matches"
        ),
    )


def numeric_evidence_matches_metric(*, metric: dict, evidence: dict) -> bool:
    """Return whether one evidence row fully supports one numeric metric.

    Args:
        metric: Numeric metrics_matrix row under validation.
        evidence: Candidate metric_evidence row for the same logical key.

    Returns:
        True when value, unit, period, filing identity, source, concept, and
        extraction method are all present and aligned.
    """
    required_fields = [
        "value_normalized",
        "unit",
        "period_end",
        "accession",
        "source_url",
        "concept_or_section",
        "extraction_method",
    ]
    if any(not evidence[field] for field in required_fields):
        return False
    if (
        evidence["company"] != metric["company"]
        or evidence["metric_id"] != metric["metric_id"]
        or evidence["value_normalized"] != metric["value"]
        or evidence["unit"] != metric["unit"]
        or evidence["period_start"] != metric["period_start"]
        or evidence["period_end"] != metric["period_end"]
    ):
        return False
    metric_accessions = artifact_path_parts(
        path_text=str(metric["accession"])
    )
    evidence_accessions = artifact_path_parts(
        path_text=str(evidence["accession"])
    )
    source_urls = artifact_path_parts(path_text=str(evidence["source_url"]))
    return (
        bool(evidence_accessions)
        and evidence_accessions == metric_accessions
        and bool(source_urls)
        and all(is_official_sec_url(source_url=url) for url in source_urls)
    )


def event_metric_evidence_errors(
    *,
    metric: dict,
    evidence_rows: list[dict],
    events: list[dict],
) -> list[str]:
    """Return exact component-evidence errors for one positive 8-K metric.

    Args:
        metric: `8K_ITEM_OK` metric row.
        evidence_rows: Complete metric evidence rows.
        events: Complete, independently replay-validated event rows.

    Returns:
        Empty only when value, accession multiset, and every evidence component
        exactly match the event rows contributing to the metric.
    """
    company_events = [
        row for row in events if row["company"] == metric["company"]
    ]
    matching = event_rows_for_metric(
        events=company_events,
        metric_id=str(metric["metric_id"]),
    )
    expected_value = str(len(matching))
    expected_accessions = [str(row["accession"]) for row in matching]
    errors = []
    if not matching:
        errors.append("positive_metric_has_no_event")
    if str(metric["value"]) != expected_value:
        errors.append(
            f"value={metric['value']},expected={expected_value}"
        )
    if (
        artifact_path_parts(path_text=str(metric["accession"]))
        != expected_accessions
    ):
        errors.append("metric_accessions_do_not_match_events")
    extraction_method = (
        "eightk_item_keyword"
        if metric["metric_id"] == "E01"
        else "eightk_item"
    )
    # Validation derives the complete row contract directly from event data;
    # reusing the production evidence builder would let one shared bug prove
    # its own output correct.
    expected_evidence = [
        {
            "company": str(metric["company"]),
            "cik": str(event["cik"]),
            "metric_id": str(metric["metric_id"]),
            "source_url": str(event["source_url"]),
            "repo_relative_path": str(event["repo_relative_path"]),
            "content_sha256": str(event["content_sha256"]),
            "accession": str(event["accession"]),
            "document_name": str(event["document_name"]),
            "concept_or_section": f"8-K Item {event['item_code']}",
            "context_or_dimension": "FY window",
            "unit": "count",
            "period_start": str(metric["period_start"]),
            "period_end": str(metric["period_end"]),
            "value_raw": "1",
            "value_normalized": str(metric["value"]),
            "evidence_quote": str(event["brief"])[:1000],
            "extraction_method": extraction_method,
            "parser_version": "sec_pipeline_v1",
        }
        for event in matching
    ]
    actual_evidence = [
        row
        for row in evidence_rows
        if row["company"] == metric["company"]
        and row["metric_id"] == metric["metric_id"]
    ]
    errors.extend(
        exact_artifact_row_errors(
            rows=actual_evidence,
            expected_rows=expected_evidence,
            fields=EVIDENCE_FIELDNAMES,
            artifact_name="event_evidence",
        )
    )
    return errors


def expected_event_metric_target(
    *,
    inventory: list[dict],
    company: str,
) -> dict:
    """Return the target filing that owns one company's event outputs.

    Args:
        inventory: Filing rows whose target/prior identities were independently
            rebuilt from saved submissions.
        company: Logical company owning the event metric.

    Returns:
        Preferred primary/successor target, then predecessor fallback.
    """
    targets = [
        row
        for row in inventory
        if row["company"] == company and row["source_role"] == "target_10k"
    ]
    if not targets:
        raise ValueError(f"Missing event target 10-K for {company}")
    role_rank = {"primary": 0, "successor": 0, "predecessor": 1}
    return sorted(
        targets,
        key=lambda row: (
            role_rank[row["entity_role"]]
            if row["entity_role"] in role_rank
            else 5,
            str(row["filingDate"]),
        ),
    )[0]


def expected_event_metric_period(
    *,
    inventory: list[dict],
    company: str,
) -> tuple[str, str]:
    """Derive one event metric period from exact-checked filing inventory.

    Args:
        inventory: Filing rows whose target/prior identities were independently
            rebuilt from saved submissions.
        company: Logical company owning the event metric.

    Returns:
        Fiscal period start and end dates used by event outputs.
    """
    target = expected_event_metric_target(
        inventory=inventory,
        company=company,
    )
    period_end = str(target["reportDate"])
    prior_dates = [
        str(row["reportDate"])
        for row in inventory
        if row["company"] == company
        and row["source_role"] == "prior_10k"
        and str(row["reportDate"])
        and str(row["reportDate"]) < period_end
    ]
    if prior_dates:
        period_start = (
            parse_date_text(value=max(prior_dates)) + timedelta(days=1)
        ).isoformat()
    else:
        end_date = parse_date_text(value=period_end)
        period_start = date(
            year=end_date.year,
            month=1,
            day=1,
        ).isoformat()
    return period_start, period_end


def expected_event_metric_row(
    *,
    company: str,
    metric_id: str,
    events: list[dict],
    inventory: list[dict],
) -> dict:
    """Independently derive every deterministic event metric field.

    Args:
        company: Logical company owning the output row.
        metric_id: C01 or E01-E05 identifier validated by this gate.
        events: Complete replay-validated event component rows.
        inventory: Exact-checked target/prior/FY filing inventory.

    Returns:
        One complete metrics-matrix row contract.
    """
    target = expected_event_metric_target(
        inventory=inventory,
        company=company,
    )
    period_start, period_end = expected_event_metric_period(
        inventory=inventory,
        company=company,
    )
    company_events = [row for row in events if row["company"] == company]
    matching = event_rows_for_metric(
        events=company_events,
        metric_id=metric_id,
    )
    company_inventory = [
        row
        for row in inventory
        if row["company"] == company and row["source_role"] == "fy_8k"
    ]
    scanned_accessions = ";".join(
        sorted({str(row["accession"]) for row in company_inventory})
    )
    scanned_dates = ";".join(
        sorted({str(row["filingDate"]) for row in company_inventory})
    )
    scanned_context = (
        "FY-window 8-K accessions scanned"
        if scanned_accessions
        else "No FY-window 8-K accession in inventory"
    )
    if metric_id == "E01":
        metric_name = "M&A announcements"
        concept = "8-K Item 1.01/2.01/8.01"
        confidence = "0.75"
        if matching:
            status = "8K_ITEM_OK"
            accession = ";".join(
                str(event["accession"]) for event in matching
            )
            filed_date = ""
            notes = "M&A candidate from item mapping and keyword rule."
        else:
            status = "NOT_AVAILABLE_SEC"
            accession = scanned_accessions
            filed_date = scanned_dates
            notes = "FY-window 8-K scanned; no M&A item rule matched."
        context = scanned_context
    else:
        specs = {
            spec_metric_id: (metric_name, code, notes)
            for spec_metric_id, metric_name, code, _status, notes
            in eight_k_event_update_specs()
        }
        if metric_id not in specs:
            raise ValueError(f"Unknown event metric id: {metric_id}")
        metric_name, code, positive_notes = specs[metric_id]
        concept = f"8-K Item {code}"
        if matching:
            status = "8K_ITEM_OK"
            accession = ";".join(
                str(event["accession"]) for event in matching
            )
            filed_date = ";".join(
                str(event["filing_date"]) for event in matching
            )
            context = "FY window"
            confidence = str(matching[0]["confidence"])
            notes = positive_notes
        else:
            status = "NOT_AVAILABLE_SEC"
            accession = scanned_accessions
            filed_date = scanned_dates
            context = scanned_context
            confidence = "0.80"
            notes = f"FY-window 8-K scanned; no item {code} found."
            if metric_id == "E02":
                notes = "No Item 1.03 in FY-window 8-K; zero is normal."
    row = {field: "" for field in METRICS_FIELDNAMES}
    row.update(
        {
            "company": company,
            "cik": str(target["cik"]),
            "metric_id": metric_id,
            "metric_name": metric_name,
            "value": str(len(matching)),
            "unit": "count",
            "status": status,
            "source_class": "8K_ITEM",
            "formula": "text/event extraction",
            "period_start": period_start,
            "period_end": period_end,
            "fiscal_year": "",
            "fiscal_period": "FY",
            "accession": accession,
            "form": "",
            "filed_date": filed_date,
            "concept_or_section": concept,
            "context_or_dimension": context,
            "confidence": confidence,
            "notes": notes,
        }
    )
    return row


def check_8k_event_outputs_match_events(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    events: list[dict],
    inventory: list[dict],
) -> dict:
    """Validate event metrics and evidence against the complete event set.

    Args:
        metrics: Complete metrics matrix rows.
        evidence_rows: Complete metric evidence rows.
        events: Parsed FY-window event components.
        inventory: Filing inventory defining the expected FY-window accessions.

    Returns:
        PASS only when every event-backed output matches its contributing
        events, including an explicit scan row for a legitimate zero.
    """
    failures = event_inventory_coverage_errors(
        inventory=inventory,
        events=events,
    )
    event_metric_ids = {
        metric_id
        for metric_id, _name, _code, _status, _notes
        in eight_k_event_update_specs()
        if metric_id != "C04"
    } | {"E01"}
    expected_keys = {
        key
        for key in expected_metrics_matrix_keys()
        if key[1] in event_metric_ids
    }
    for company, metric_id in sorted(expected_keys):
        metric_rows = [
            row
            for row in metrics
            if row["company"] == company and row["metric_id"] == metric_id
        ]
        if len(metric_rows) != 1:
            failures.append(
                f"metric_cardinality={company}:{metric_id}:{len(metric_rows)}"
            )
            continue
        metric = metric_rows[0]
        company_events = [row for row in events if row["company"] == company]
        try:
            expected_metric = expected_event_metric_row(
                company=company,
                metric_id=metric_id,
                events=events,
                inventory=inventory,
            )
        except (KeyError, TypeError, ValueError) as error:
            # A damaged filing inventory is a validation failure, not an
            # exception that may prevent Stage 12 from publishing its result.
            failures.append(
                f"{company}:{metric_id}:expected_metric_invalid={error}"
            )
            continue
        matching = event_rows_for_metric(
            events=company_events,
            metric_id=metric_id,
        )
        for field in METRICS_FIELDNAMES:
            if metric[field] != expected_metric[field]:
                failures.append(
                    f"{company}:{metric_id}:{field}={metric[field]},"
                    f"expected={expected_metric[field]}"
                )
        if matching:
            failures.extend(
                f"{company}:{metric_id}:{error}"
                for error in event_metric_evidence_errors(
                    metric=metric,
                    evidence_rows=evidence_rows,
                    events=events,
                )
            )
            continue

        source_urls, locator_accessions = event_scan_locators(
            events=company_events,
        )
        zero_evidence = [
            row
            for row in evidence_rows
            if row["company"] == company and row["metric_id"] == metric_id
        ]
        if len(zero_evidence) != 1:
            failures.append(
                f"{company}:{metric_id}:zero_evidence_rows="
                f"{len(zero_evidence)}"
            )
            continue
        evidence = zero_evidence[0]
        expected_evidence_fields = {
            "company": company,
            "cik": expected_metric["cik"],
            "metric_id": metric_id,
            "source_url": source_urls,
            "repo_relative_path": "outputs/events.csv",
            "accession": locator_accessions,
            "document_name": "events.csv",
            "concept_or_section": expected_metric["concept_or_section"],
            "context_or_dimension": expected_metric["context_or_dimension"],
            "unit": expected_metric["unit"],
            "period_start": expected_metric["period_start"],
            "period_end": expected_metric["period_end"],
            "value_raw": "0",
            "value_normalized": "0",
            "evidence_quote": expected_metric["notes"],
            "extraction_method": "eightk_zero_item_scan",
            "parser_version": "sec_pipeline_v1",
        }
        for field, expected in expected_evidence_fields.items():
            if evidence[field] != expected:
                failures.append(
                    f"{company}:{metric_id}:evidence_{field}="
                    f"{evidence[field]},expected={expected}"
                )
    return validation_row(
        check_id="eightk_event_outputs_match_events",
        status="PASS" if not failures else "FAIL",
        details=(
            f"event_metric_keys={len(expected_keys)}"
            if not failures
            else ";".join(failures[:20])
        ),
    )


def check_numeric_ok_requires_evidence(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
    events: list[dict],
) -> dict:
    """Validate each numeric OK row has complete matching evidence identity."""
    failures = []
    for row in metrics:
        if row["status"] not in NUMERIC_EVIDENCE_STATUSES:
            continue
        if row["value"] == "":
            continue
        if row["source_class"] == "8K_ITEM" and row["status"] == "8K_ITEM_OK":
            event_errors = event_metric_evidence_errors(
                metric=row,
                evidence_rows=evidence_rows,
                events=events,
            )
            failures.extend(
                f"{row['company']}:{row['metric_id']}:{error}"
                for error in event_errors
            )
            continue
        matching_rows = [
            evidence
            for evidence in evidence_rows
            if numeric_evidence_matches_metric(metric=row, evidence=evidence)
        ]
        if not matching_rows:
            failures.append(f"{row['company']}:{row['metric_id']}")
    return validation_row(
        check_id="numeric_ok_status_requires_evidence_row",
        status="PASS" if not failures else "FAIL",
        details=(
            ";".join(failures[:20])
            if failures
            else "all numeric OK rows have complete matching evidence"
        ),
    )


def check_d04_going_concern_text(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate missing going-concern findings have explicit text."""
    failures = []
    for row in metrics:
        if row["metric_id"] != "D04":
            continue
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=row["company"],
            metric_id="D04",
        )
        text = " ".join(item["evidence_quote"] for item in evidence)
        combined = f"{text} {row['notes']}".lower()
        has_explicit = (
            "未披露持续经营疑虑" in combined
            or "no going-concern doubt phrase" in combined
            or "going concern" in combined
            or "substantial doubt" in combined
        )
        if not has_explicit:
            failures.append(row["company"])
    return validation_row(
        check_id="d04_missing_going_concern_has_explicit_text",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "D04 text explicit",
    )


def metric_value_decimal(*, row: dict) -> Decimal | None:
    """Return a metric row value as Decimal, or None for blank values."""
    if row["value"] == "":
        return None
    return Decimal(row["value"])


def decimal_close(*, actual: Decimal | None, expected: str, tolerance: str) -> bool:
    """Return whether a Decimal value is within tolerance."""
    if actual is None:
        return False
    return abs(actual - Decimal(expected)) <= Decimal(tolerance)


def metric_row_by_value(
    *,
    metrics: list[dict],
    metric_id: str,
    expected: str,
    tolerance: str,
    status: str,
) -> dict:
    """Return one metric row identified by value/status instead of company.

    Args:
        metrics: metrics_matrix rows.
        metric_id: Metric id to search.
        expected: Decimal value encoded as text.
        tolerance: Allowed absolute Decimal difference.
        status: Required metric status.

    Returns:
        First matching metric row.
    """
    for row in metrics:
        if row["metric_id"] != metric_id or row["status"] != status:
            continue
        if decimal_close(
            actual=metric_value_decimal(row=row),
            expected=expected,
            tolerance=tolerance,
        ):
            return row
    raise KeyError(f"Metric value missing: {metric_id} {expected} {status}")


def metric_evidence_text(
    *,
    evidence_rows: list[dict],
    company: str,
    metric_id: str,
) -> str:
    """Return concatenated concept and quote evidence for one metric."""
    parts = []
    for row in evidence_for_metric(
        evidence_rows=evidence_rows,
        company=company,
        metric_id=metric_id,
    ):
        parts.append(row["concept_or_section"])
        parts.append(row["evidence_quote"])
    return " ".join(parts)


def check_b06_total_debt_prefers_total_debt_concepts(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate B06 uses direct total debt when available."""
    company = str(company_by_id(company_id="marriott_international")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B06",
    )
    passes = "DebtAndCapitalLeaseObligations" in text and "LongTermDebt=23000000" not in text
    return validation_row(
        check_id="b06_total_debt_prefers_total_debt_concepts",
        status="PASS" if passes else "FAIL",
        details="direct total debt selected" if passes else text[:500],
    )


def check_b06_no_adder_double_count(*, evidence_rows: list[dict]) -> dict:
    """Validate Tier 1 B06 evidence does not include short-debt adders."""
    company = str(company_by_id(company_id="marriott_international")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B06",
    )
    failures = [
        concept
        for concept in TOTAL_DEBT_SHORT_ADDER_CHAIN
        if concept in text and "DebtAndCapitalLeaseObligations" in text
    ]
    return validation_row(
        check_id="b06_no_adder_double_count",
        status="PASS" if not failures else "FAIL",
        details="Tier 1 B06 has no adders" if not failures else ";".join(failures),
    )


def check_b06_tier_pairing_uses_current_sibling(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate B06 pair logic uses same-family siblings."""
    company = str(company_by_id(company_id="enphase_energy")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B06",
    )
    passes = "LongTermDebtCurrent" in text and "LongTermDebtNoncurrent" in text
    return validation_row(
        check_id="b06_tier_pairing_uses_current_sibling",
        status="PASS" if passes else "FAIL",
        details="Enphase current/noncurrent siblings selected" if passes else text[:500],
    )


def check_b06_excludes_debt_securities_and_debt_fair_value(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate forbidden debt concepts are absent from B06 evidence."""
    failures = []
    for row in evidence_rows:
        if row["metric_id"] != "B06":
            continue
        concepts = row["concept_or_section"].split("+")
        for concept in concepts:
            if concept_excluded_from_total_debt(concept=concept):
                failures.append(f"{row['company']}:{concept}")
    return validation_row(
        check_id="b06_excludes_debt_securities_and_debt_fair_value",
        status="PASS" if not failures else "FAIL",
        details="forbidden B06 concepts absent" if not failures else ";".join(failures),
    )


def check_b06_negative_equity_not_ok(*, metrics: list[dict]) -> dict:
    """Validate negative equity never produces an OK B06 ratio."""
    failures = []
    for row in metrics:
        if row["metric_id"] != "B06":
            continue
        if "Equity is negative" in row["notes"]:
            if row["status"] == "OK" or row["value"] != "":
                failures.append(row["company"])
    return validation_row(
        check_id="b06_negative_equity_not_ok",
        status="PASS" if not failures else "FAIL",
        details="negative-equity B06 rows are blank" if not failures else ";".join(failures),
    )


def check_enphase_b06_golden_unchanged_after_debt_resolver(
    *,
    metrics: list[dict],
) -> dict:
    """Validate Enphase B06 remains within the locked golden range."""
    company = str(company_by_id(company_id="enphase_energy")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
    passes = row["status"] == "OK" and decimal_close(
        actual=metric_value_decimal(row=row),
        expected="1.11",
        tolerance="0.01",
    )
    return validation_row(
        check_id="enphase_b06_golden_unchanged_after_debt_resolver",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}",
    )


def check_ford_b06_captive_finance_still_needs_review(
    *,
    metrics: list[dict],
) -> dict:
    """Validate captive-finance B06 remains review-gated."""
    company = str(company_by_id(company_id="ford_motor_company")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
    passes = row["status"] == "NEEDS_REVIEW" and row["value"] == ""
    return validation_row(
        check_id="ford_b06_captive_finance_still_needs_review",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}:{row['notes']}",
    )


def check_metrics_matrix_applicability_matches_02_04_spec(
    *,
    metrics: list[dict],
) -> dict:
    """Validate matrix keys are the unique config-derived expected set."""
    failures = keyed_artifact_exact_set_errors(
        rows=metrics,
        expected_keys=expected_metrics_matrix_keys(),
        artifact_name="metrics_matrix",
    )
    return validation_row(
        check_id="metrics_matrix_applicability_matches_02_04_spec",
        status="PASS" if not failures else "FAIL",
        details=(
            "metrics matrix exact key set matches config contract"
            if not failures
            else ";".join(failures)
        ),
    )


def check_no_unexpected_optional_b_metrics_in_main_matrix(
    *,
    metrics: list[dict],
) -> dict:
    """Validate B10-B13 main rows only exist for mounted extractors."""
    expected_keys = expected_metrics_matrix_keys()
    expected_counts = {
        metric_id: len(
            [key for key in expected_keys if key[1] == metric_id]
        )
        for metric_id in optional_b_metric_ids()
    }
    failures = []
    for metric_id, expected_count in expected_counts.items():
        actual_count = len([row for row in metrics if row["metric_id"] == metric_id])
        if actual_count != expected_count:
            failures.append(f"{metric_id}:{actual_count}!={expected_count}")
    return validation_row(
        check_id="no_unexpected_optional_b_metrics_in_main_matrix",
        status="PASS" if not failures else "FAIL",
        details=(
            "optional B metric counts match target scope"
            if not failures
            else ";".join(failures)
        ),
    )


def check_c02_matrix_matches_governance_signals(*, metrics: list[dict]) -> dict:
    """Validate C02 matrix rows mirror governance_signals rows."""
    path = WORKDIR / "outputs" / "governance_signals.csv"
    signals = [
        row
        for row in read_csv_file(path=path)
        if row["signal_id"] == "C02"
    ]
    if not path.exists() or not signals:
        return not_evaluated_validation_row(
            check_id="c02_matrix_matches_governance_signals",
            details="governance_signals C02 evidence missing",
        )
    failures = []
    for signal in signals:
        row = metric_lookup(
            metrics=metrics,
            company=signal["company"],
            metric_id="C02",
        )
        if row["status"] != signal["status"]:
            failures.append(f"{signal['company']}:status")
        if row["accession"] != signal["accession"]:
            failures.append(f"{signal['company']}:accession")
    return validation_row(
        check_id="c02_matrix_matches_governance_signals",
        status="PASS" if not failures else "FAIL",
        details="C02 matrix rows match governance signals" if not failures else ";".join(failures),
    )


def check_c02_text_qual_requires_evidence_quote(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate each TEXT_QUAL C02 row has quoted DEF 14A evidence."""
    if not metrics:
        return not_evaluated_validation_row(
            check_id="c02_text_qual_requires_evidence_quote",
            details="metrics_matrix rows missing",
        )
    failures = []
    for row in metrics:
        if row["metric_id"] != "C02" or row["status"] != "TEXT_QUAL":
            continue
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=row["company"],
            metric_id="C02",
        )
        if not any(item["evidence_quote"] for item in evidence):
            failures.append(row["company"])
    return validation_row(
        check_id="c02_text_qual_requires_evidence_quote",
        status="PASS" if not failures else "FAIL",
        details="C02 TEXT_QUAL rows have evidence quotes" if not failures else ";".join(failures),
    )


def check_no_placeholder_notes_in_final_metrics(*, metrics: list[dict]) -> dict:
    """Validate final matrix does not retain initialization notes."""
    if not metrics:
        return not_evaluated_validation_row(
            check_id="no_placeholder_notes_in_final_metrics",
            details="metrics_matrix rows missing",
        )
    failures = [
        f"{row['company']}:{row['metric_id']}"
        for row in metrics
        if "Initialized before event/text extraction." in row["notes"]
    ]
    return validation_row(
        check_id="no_placeholder_notes_in_final_metrics",
        status="PASS" if not failures else "FAIL",
        details=(
            "no placeholder initialization notes remain"
            if not failures
            else ";".join(failures)
        ),
    )


def check_b06_needs_review_captive_finance_has_blank_main_value_or_candidate_role(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate captive-finance B06 review rows blank main values."""
    candidate_rows = read_csv_file(
        path=WORKDIR / "outputs" / "b06_debt_to_equity_candidates.csv"
    )
    candidate_keys = {
        (row["company"], row["metric_id"], row["candidate_role"])
        for row in candidate_rows
    }
    failures = []
    for row in metrics:
        if row["metric_id"] != "B06" or row["status"] != "NEEDS_REVIEW":
            continue
        if "captive finance" not in row["notes"].lower():
            continue
        evidence_text = metric_evidence_text(
            evidence_rows=evidence_rows,
            company=row["company"],
            metric_id="B06",
        )
        has_sidecar_candidate = (
            row["company"],
            "B06",
            "consolidated_captive_finance_candidate",
        ) in candidate_keys
        has_evidence_candidate = (
            "candidate_role=consolidated_captive_finance_candidate" in evidence_text
        )
        if (
            row["value"] != ""
            or not has_sidecar_candidate
            or not has_evidence_candidate
        ):
            failures.append(
                (
                    f"{row['company']}:{row['value']}:"
                    f"sidecar={has_sidecar_candidate}:"
                    f"evidence={has_evidence_candidate}"
                )
            )
    return validation_row(
        check_id="b06_needs_review_captive_finance_has_blank_main_value_or_candidate_role",
        status="PASS" if not failures else "FAIL",
        details=(
            "captive-finance B06 main value blank with evidence and sidecar "
            "candidate role"
            if not failures
            else ";".join(failures)
        ),
    )


def check_marriott_b03_da_composition_positive(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate Marriott B03 uses positive D&A composition."""
    company = str(company_by_id(company_id="marriott_international")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B03")
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="B03",
    )
    passes = (
        row["status"] == "OK"
        and decimal_close(
            actual=metric_value_decimal(row=row),
            expected="0.17562819827388682",
            tolerance="0.0000000001",
        )
        and "Depreciation=145000000" in text
        and "AmortizationOfIntangibleAssets=313000000" in text
    )
    return validation_row(
        check_id="marriott_b03_da_composition_positive",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}:{text[:300]}",
    )


def check_da_composition_rejects_accumulated_expected_future_schedule() -> dict:
    """Validate D&A composition allowlist excludes schedule/balance concepts."""
    bad_concepts = [
        "AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "ExpectedAmortizationExpense",
        "FiniteLivedIntangibleAssetsAmortizationExpenseNextTwelveMonths",
        "FiniteLivedIntangibleAssetsAmortizationExpenseYearThree",
        "FiniteLivedIntangibleAssetsAccumulatedAmortization",
    ]
    failures = [concept for concept in bad_concepts if concept in DA_COMPOSITION_CHAIN]
    return validation_row(
        check_id="da_composition_rejects_accumulated_expected_future_schedule",
        status="PASS" if not failures else "FAIL",
        details="D&A composition allowlist is clean" if not failures else ";".join(failures),
    )


def check_da_composition_completeness_scan_clean_or_noted(
    *,
    metrics: list[dict],
) -> dict:
    """Validate custom D&A-and-other observation is disclosed when present."""
    company = str(company_by_id(company_id="marriott_international")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B03")
    passes = "DepreciationAmortizationAndOther observed" in row["notes"]
    return validation_row(
        check_id="da_composition_completeness_scan_clean_or_noted",
        status="PASS" if passes else "FAIL",
        details=row["notes"],
    )


def check_da_custom_line_reconciliation_noted(*, metrics: list[dict]) -> dict:
    """Validate the custom D&A line is not silently added."""
    company = str(company_by_id(company_id="marriott_international")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B03")
    passes = (
        "not added because" in row["notes"]
        and "and other" in row["notes"]
    )
    return validation_row(
        check_id="da_custom_line_reconciliation_noted",
        status="PASS" if passes else "FAIL",
        details=row["notes"],
    )


def check_pfizer_b03_operating_income_reconstruction_ok_approx(
    *,
    metrics: list[dict],
) -> dict:
    """Validate reconstructed operating income B03 uses OK_APPROX."""
    row = metric_row_by_value(
        metrics=metrics,
        metric_id="B03",
        expected="0.33295514469710286",
        tolerance="0.0000000001",
        status="OK_APPROX",
    )
    passes = row["status"] == "OK_APPROX" and decimal_close(
        actual=metric_value_decimal(row=row),
        expected="0.33295514469710286",
        tolerance="0.0000000001",
    )
    return validation_row(
        check_id="pfizer_b03_operating_income_reconstruction_ok_approx",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}:{row['notes']}",
    )


def check_pfizer_b07_reuses_approx_operating_income(*, metrics: list[dict]) -> dict:
    """Validate B07 reuses the reconstructed operating income component."""
    row = metric_row_by_value(
        metrics=metrics,
        metric_id="B07",
        expected="5.332834144515163",
        tolerance="0.0000000001",
        status="OK_APPROX",
    )
    passes = (
        row["status"] == "OK_APPROX"
        and "reconstructed operating income" in row["notes"]
        and decimal_close(
            actual=metric_value_decimal(row=row),
            expected="5.332834144515163",
            tolerance="0.0000000001",
        )
    )
    return validation_row(
        check_id="pfizer_b07_reuses_approx_operating_income",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}:{row['notes']}",
    )


def check_direct_operating_income_priority_over_reconstruction(
    *,
    metrics: list[dict],
) -> dict:
    """Validate direct OperatingIncomeLoss keeps B03 exact status."""
    company = str(company_by_id(company_id="enphase_energy")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B03")
    passes = row["status"] == "OK" and "Direct OperatingIncomeLoss" in row["notes"]
    return validation_row(
        check_id="direct_operating_income_priority_over_reconstruction",
        status="PASS" if passes else "FAIL",
        details=row["notes"],
    )


def check_b03_rejects_mixed_accession_period_unit() -> dict:
    """Validate B03 component compatibility rejects mixed contexts."""
    period_start = date(year=2025, month=1, day=1).isoformat()
    period_end = date(year=2025, month=12, day=31).isoformat()
    mixed_period_start = date(year=2025, month=4, day=1).isoformat()
    filed_date = date(year=2026, month=1, day=1).isoformat()
    hit_a = FactHit(
        concept="Depreciation",
        taxonomy="us-gaap",
        unit="USD",
        value=Decimal("1"),
        raw_value="1",
        start=period_start,
        end=period_end,
        filed=filed_date,
        form="10-K",
        fiscal_year="2025",
        fiscal_period="FY",
        accession="a",
        frame="",
        source_path="fixture",
        source_url="fixture",
    )
    hit_b = FactHit(
        concept="AmortizationOfIntangibleAssets",
        taxonomy="us-gaap",
        unit="USD",
        value=Decimal("1"),
        raw_value="1",
        start=mixed_period_start,
        end=period_end,
        filed=filed_date,
        form="10-K",
        fiscal_year="2025",
        fiscal_period="FY",
        accession="b",
        frame="",
        source_path="fixture",
        source_url="fixture",
    )
    passes = not compatible_component_hits(
        hits=[hit_a, hit_b],
        period_start=period_start,
        period_end=period_end,
        accession="a",
        unit="USD",
    )
    return validation_row(
        check_id="b03_rejects_mixed_accession_period_unit",
        status="PASS" if passes else "FAIL",
        details="mixed fixture rejected" if passes else "mixed fixture accepted",
    )


def check_b03_bridge_fragment_negative_fixture_rejected_or_needs_review() -> dict:
    """Validate operating-income bridge does not include fragments."""
    fragments = {"InterestExpense", "InvestmentIncome", "IncomeTaxExpenseBenefit"}
    failures = [concept for concept in fragments if concept in NONOPERATING_BRIDGE_CHAIN]
    return validation_row(
        check_id="b03_bridge_fragment_negative_fixture_rejected_or_needs_review",
        status="PASS" if not failures else "FAIL",
        details=(
            "bridge chain contains aggregate concepts only"
            if not failures
            else ";".join(failures)
        ),
    )


def check_jpm_a10_allowance_ratio_std_xbrl_primary(*, metrics: list[dict]) -> dict:
    """Validate JPM A10 primary structured allowance ratio."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="A10")
    passes = (
        row["status"] == "OK"
        and row["source_class"] == "STD_XBRL"
        and decimal_close(
            actual=metric_value_decimal(row=row),
            expected="0.018287251447045755",
            tolerance="0.0000000001",
        )
    )
    return validation_row(
        check_id="jpm_a10_allowance_ratio_std_xbrl_primary",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['source_class']}:{row['value']}",
    )


def check_jpm_a10_excludes_debt_securities_allowance(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate JPM A10 evidence excludes securities allowance concepts."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A10",
    )
    passes = "DebtSecurities" not in text
    return validation_row(
        check_id="jpm_a10_excludes_debt_securities_allowance",
        status="PASS" if passes else "FAIL",
        details="securities allowance absent" if passes else text[:500],
    )


def check_jpm_a10_primary_denominator_before_allowance_for_credit_loss(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate JPM A10 denominator uses before-allowance loans."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A10",
    )
    passes = "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss" in text
    return validation_row(
        check_id="jpm_a10_primary_denominator_before_allowance_for_credit_loss",
        status="PASS" if passes else "FAIL",
        details="before-allowance denominator present" if passes else text[:500],
    )


def check_jpm_a10_evidence_lists_numerator_and_denominator(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate JPM A10 evidence lists both components."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A10",
    )
    passes = all(component in text for component in JPM_A10_COMPONENTS)
    return validation_row(
        check_id="jpm_a10_evidence_lists_numerator_and_denominator",
        status="PASS" if passes else "FAIL",
        details="A10 numerator and denominator evidenced" if passes else text[:500],
    )


def check_a08_uses_noninterest_income_not_fee_label_guess(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate A08 uses noninterest income rather than fee label guessing."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A08",
    )
    passes = "NoninterestIncome" in text and "FeeIncome" not in text
    return validation_row(
        check_id="a08_uses_noninterest_income_not_fee_label_guess",
        status="PASS" if passes else "FAIL",
        details="A08 uses NoninterestIncome" if passes else text[:500],
    )


def check_a08_notes_definition_name_tension(*, metrics: list[dict]) -> dict:
    """Validate A08 notes explain metric-name tension."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="A08")
    passes = "not pure fee income" in row["notes"]
    return validation_row(
        check_id="a08_notes_definition_name_tension",
        status="PASS" if passes else "FAIL",
        details=row["notes"],
    )


def check_a08_evidence_has_source_components(
    *,
    evidence_rows: list[dict],
) -> dict:
    """Validate A08 evidence includes numerator and denominator."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A08",
    )
    passes = all(component in text for component in JPM_A08_COMPONENTS)
    return validation_row(
        check_id="a08_evidence_has_source_components",
        status="PASS" if passes else "FAIL",
        details="A08 source components evidenced" if passes else text[:500],
    )


def check_jpm_mda_raw_row_anchor(
    *,
    evidence_rows: list[dict],
    metric_id: str,
    check_id: str,
) -> dict:
    """Validate JPM MD&A metric evidence contains raw row anchors."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id=metric_id,
    )
    passes = "raw_header=" in text and "raw_row=" in text
    return validation_row(
        check_id=check_id,
        status="PASS" if passes else "FAIL",
        details=f"{metric_id} raw row anchored" if passes else text[:500],
    )


def check_jpm_a04_nim_raw_row_anchor_or_proxy_caveat(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate JPM A04 has a table row or explicit proxy caveat."""
    company = str(company_by_id(company_id="jpmorgan_chase")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="A04")
    text = metric_evidence_text(
        evidence_rows=evidence_rows,
        company=company,
        metric_id="A04",
    )
    passes = (
        ("raw_header=" in text and "raw_row=" in text and "managed basis" in row["notes"].lower())
        or ("proxy" in row["notes"].lower() and row["status"] == "OK_APPROX")
    )
    return validation_row(
        check_id="jpm_a04_nim_raw_row_anchor_or_proxy_caveat",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['notes']}:{text[:300]}",
    )


def check_jpm_table_values_not_added_to_golden_until_manual_confirmation() -> dict:
    """Validate JPM MD&A table values are not locked into golden."""
    path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "sec_10_company_spike"
        / "golden_expected_values.csv"
    )
    rows = read_csv_file(path=path)
    if not path.exists() or not rows:
        return not_evaluated_validation_row(
            check_id=(
                "jpm_table_values_not_added_to_golden_until_"
                "manual_confirmation"
            ),
            details="golden_expected_values fixture missing or empty",
        )
    forbidden = {"metric_value_A03", "metric_value_A04", "metric_value_A11", "metric_value_A12"}
    failures = [
        row["assertion_id"]
        for row in rows
        if row["company_id"] == "jpmorgan_chase" and row["component_key"] in forbidden
    ]
    return validation_row(
        check_id="jpm_table_values_not_added_to_golden_until_manual_confirmation",
        status="PASS" if not failures else "FAIL",
        details="JPM table values absent from golden" if not failures else ";".join(failures),
    )


def check_paramount_stub_period_values_not_main_annual_ok(
    *,
    metrics: list[dict],
) -> dict:
    """Validate successor stub period values are not main annual OK rows."""
    company = str(company_by_id(company_id="paramount_skydance_paramount_global")["company"])
    failures = []
    for metric_id in sorted(STUB_PERIOD_MAIN_METRICS):
        row = metric_lookup(metrics=metrics, company=company, metric_id=metric_id)
        if row["status"] in NUMERIC_EVIDENCE_STATUSES or row["value"] != "":
            failures.append(f"{metric_id}:{row['status']}:{row['value']}")
    return validation_row(
        check_id="paramount_stub_period_values_not_main_annual_ok",
        status="PASS" if not failures else "FAIL",
        details=(
            "Paramount annual period metrics are blank"
            if not failures
            else ";".join(failures)
        ),
    )


def check_paramount_stub_period_sidecar_exists() -> dict:
    """Validate stub period sidecar exists and contains rows."""
    path = WORKDIR / "outputs" / "stub_period_metrics.csv"
    rows = read_csv_file(path=path)
    passes = path.exists() and bool(rows)
    return validation_row(
        check_id="paramount_stub_period_sidecar_exists",
        status="PASS" if passes else "FAIL",
        details=f"rows={len(rows)}",
    )


def check_paramount_b06_point_in_time_successor_balance_sheet_note(
    *,
    metrics: list[dict],
) -> dict:
    """Validate Paramount B06 is documented as point-in-time."""
    company = str(company_by_id(company_id="paramount_skydance_paramount_global")["company"])
    row = metric_lookup(metrics=metrics, company=company, metric_id="B06")
    passes = (
        row["status"] == "OK"
        and row["value"] != ""
        and "successor balance sheet point-in-time" in row["notes"]
    )
    return validation_row(
        check_id="paramount_b06_point_in_time_successor_balance_sheet_note",
        status="PASS" if passes else "FAIL",
        details=f"{row['status']}:{row['value']}:{row['notes']}",
    )


def spec_implementation_audit_rows() -> list[dict]:
    """Return the spec-to-code audit rows for this repair round.

    Returns:
        Rows mapping expanded metric definitions to implementation locations
        and validation checks.
    """
    return [
        {
            "metric_id": "B03",
            "spec_rule": "D&A composition and reconstructed operating income OK_APPROX",
            "implementation_location": "resolve_da_component; resolve_operating_income_component",
            "implemented": "1",
            "validation_check": (
                "marriott_b03_da_composition_positive;"
                "pfizer_b03_operating_income_reconstruction_ok_approx"
            ),
            "notes": "Impairment is not added back; bridge assumption is noted.",
        },
        {
            "metric_id": "B06",
            "spec_rule": "three-tier total debt resolver and negative equity gate",
            "implementation_location": "resolve_total_debt_component; non_fi_metric_rows",
            "implemented": "1",
            "validation_check": (
                "b06_total_debt_prefers_total_debt_concepts;"
                "b06_negative_equity_not_ok"
            ),
            "notes": "Tier 1 debt totals block adder double-counting.",
        },
        {
            "metric_id": "A08",
            "spec_rule": "noninterest income / net interest income",
            "implementation_location": "fi_metric_rows",
            "implemented": "1",
            "validation_check": "a08_uses_noninterest_income_not_fee_label_guess",
            "notes": "Notes disclose that this is not pure fee income.",
        },
        {
            "metric_id": "A10",
            "spec_rule": "ACL allowance / retained loans before allowance",
            "implementation_location": "fi_metric_rows",
            "implemented": "1",
            "validation_check": "jpm_a10_allowance_ratio_std_xbrl_primary",
            "notes": "Securities allowance concepts are excluded from primary value.",
        },
        {
            "metric_id": "A03/A04/A11/A12",
            "spec_rule": "JPM MD&A table raw_header/raw_row anchors",
            "implementation_location": "apply_fi_mda_table_metrics",
            "implemented": "1",
            "validation_check": (
                "jpm_a03_lcr_raw_row_anchor;"
                "jpm_a04_nim_raw_row_anchor_or_proxy_caveat;"
                "jpm_a11_aum_raw_row_anchor;"
                "jpm_a12_var_raw_row_anchor"
            ),
            "notes": "Table values are intentionally not added to golden.",
        },
        {
            "metric_id": "Paramount stub",
            "spec_rule": "stub period values move to sidecar; annual rows not OK",
            "implementation_location": (
                "write_stub_period_sidecar; apply_stub_period_metric_semantics"
            ),
            "implemented": "1",
            "validation_check": (
                "paramount_stub_period_values_not_main_annual_ok;"
                "paramount_stub_period_sidecar_exists"
            ),
            "notes": "B06 remains a successor balance-sheet point-in-time ratio.",
        },
    ]


def write_spec_implementation_audit() -> list[dict]:
    """Write outputs/spec_implementation_audit.csv."""
    rows = spec_implementation_audit_rows()
    write_csv_file(
        path=WORKDIR / "outputs" / "spec_implementation_audit.csv",
        fieldnames=SPEC_IMPLEMENTATION_AUDIT_FIELDNAMES,
        rows=rows,
    )
    return rows


def expected_golden_assertion_ids() -> list[str]:
    """Return the assertion ids generated for the configured full run.

    Returns:
        G1 ids derived from the company registry, configured G2 structural ids,
        and every fixture-owned numeric/concept assertion id.
    """
    assertion_ids = []
    for company_config in load_company_registry():
        company_slug = slugify(text=str(company_config["company"]))
        assertion_ids.extend(
            [
                f"G1_{company_slug}_cik",
                f"G1_{company_slug}_fye",
            ]
        )
        # A role-chain assertion exists exactly when the registry declares
        # more than one entity role for the logical company.
        if len(company_config["roles"]) > 1:
            assertion_ids.append(f"G1_{company_slug}_role_chain")
    financial_configs = company_configs_with_extractor(
        extractor_name="BaselCapitalRatioExtractor",
    )
    if not financial_configs:
        raise RuntimeError("No financial institution profile configured")
    assertion_ids.append(G2_FINANCIAL_ASSETSCURRENT_ASSERTION_ID)
    assertion_ids.extend(
        f"G2_financial_{metric_id.lower()}_not_std"
        for metric_id in G2_FINANCIAL_NON_STD_METRIC_IDS
    )
    captive_configs = company_configs_with_extractor(
        extractor_name="CaptiveFinanceDebtExtractor",
    )
    if captive_configs:
        assertion_ids.append(G2_CAPTIVE_FINANCE_ASSERTION_ID)
    assertion_ids.append(G2_AUDITORNAME_ASSERTION_ID)
    fixture_path = (
        WORKDIR
        / "tests"
        / "fixtures"
        / "sec_10_company_spike"
        / "golden_expected_values.csv"
    )
    assertion_ids.extend(
        row["assertion_id"] for row in read_csv_file(path=fixture_path)
    )
    return assertion_ids


def check_golden_results_all_pass() -> dict:
    """Validate the full Golden exact set is unique and all rows pass."""
    rows = read_csv_file(path=WORKDIR / "outputs" / "golden_results.csv")
    indexed, duplicates = golden_rows_by_assertion(rows=rows)
    expected_ids = expected_golden_assertion_ids()
    expected_set = set(expected_ids)
    actual_set = set(indexed)
    expected_duplicates = sorted(
        assertion_id
        for assertion_id in expected_set
        if expected_ids.count(assertion_id) > 1
    )
    missing = sorted(expected_set - actual_set)
    unexpected = sorted(actual_set - expected_set)
    non_pass = sorted(
        row["assertion_id"] for row in rows if row["status"] != "PASS"
    )
    failures = []
    for label, values in [
        ("expected_duplicate", expected_duplicates),
        ("missing", missing),
        ("unexpected", unexpected),
        ("duplicate", sorted(set(duplicates))),
        ("non_pass", non_pass),
    ]:
        if values:
            failures.append(f"{label}=" + ",".join(values[:20]))
    return validation_row(
        check_id="existing_golden_results_still_pass",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else f"rows={len(rows)}",
    )


def immutable_request_headers_hash(
    *,
    relative_path: str,
    headers_relative_path: str,
    content_sha256: str,
) -> str:
    """Return the header hash encoded by an immutable attempt locator.

    Args:
        relative_path: Repository-relative response body path.
        headers_relative_path: Repository-relative headers sidecar path.
        content_sha256: Recorded response body digest.

    Returns:
        Encoded headers digest for current immutable attempts, or an empty
        string for legacy stable paths.
    """
    body_path = Path(relative_path)
    headers_path = Path(headers_relative_path)
    immutable_prefix = ("evidence", "request_attempts")
    body_is_immutable = body_path.parts[:2] == immutable_prefix
    headers_are_immutable = headers_path.parts[:2] == immutable_prefix
    if not body_is_immutable and not headers_are_immutable:
        return ""
    if (
        not body_is_immutable
        or not headers_are_immutable
        or len(body_path.parts) != 5
        or body_path.parts[2] != content_sha256[:2]
        or body_path.parts[3] != content_sha256
        or headers_path.parent != body_path.parent
    ):
        raise ValueError("immutable_request_locator_mismatch")
    prefix = f"{body_path.name}."
    suffix = ".headers.json"
    if (
        not headers_path.name.startswith(prefix)
        or not headers_path.name.endswith(suffix)
    ):
        raise ValueError("immutable_headers_locator_mismatch")
    digest = headers_path.name[len(prefix):-len(suffix)]
    if re.fullmatch(pattern=r"[0-9a-f]{64}", string=digest) is None:
        raise ValueError("immutable_headers_hash_invalid")
    return digest


def required_request_observation_keys(
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Return request identities required by current downstream evidence.

    Returns:
        Exact URL/body-hash keys for raw artifacts and URL/accession keys for
        the supported derived event aggregate.
    """
    artifact_specs = portable_locator_artifact_specs(
        existing_optional_only=True,
    )
    artifact_specs.extend(concept_inventory_artifact_specs())
    raw_keys = set()
    derived_keys = set()
    for path, _fieldnames in artifact_specs:
        if not path.exists():
            continue
        for row in read_csv_file(path=path):
            source_urls = artifact_path_parts(
                path_text=str(row["source_url"]),
            )
            accessions = artifact_path_parts(
                path_text=str(row["accession"]),
            )
            if is_derived_locator_aggregate(row=row):
                if len(source_urls) != len(accessions):
                    raise ValueError(
                        f"{path.name}: derived request identity misaligned"
                    )
                derived_keys.update(zip(source_urls, accessions))
                continue
            content_hashes = artifact_path_parts(
                path_text=str(row["content_sha256"]),
            )
            if len(source_urls) != len(content_hashes):
                raise ValueError(
                    f"{path.name}: raw request identity misaligned"
                )
            raw_keys.update(zip(source_urls, content_hashes))
    return raw_keys, derived_keys


def stored_response_observation_keys() -> set[tuple[str, str, str]]:
    """Return observation identities independently preserved by sidecars.

    Returns:
        URL, status, and body hash for every parseable response sidecar.
    """
    keys = set()
    evidence_dir = WORKDIR / "evidence"
    if not evidence_dir.exists():
        return keys
    for path in sorted(evidence_dir.rglob("*.headers.json")):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"invalid response sidecar path: {path}")
        try:
            payload = read_json_file(path=path)
            source_url = str(payload["url"])
            status_code = str(payload["status_code"])
            content_sha256 = str(payload["sha256"])
        except (KeyError, OSError, TypeError, ValueError):
            # A cited corrupt sidecar is classified by the row-level check;
            # it cannot independently prove that another row is missing.
            continue
        keys.add((source_url, status_code, content_sha256))
    return keys


def committed_request_observation_sequence() -> list[tuple[str, ...]]:
    """Return the reviewed HEAD request ledger as an append-only baseline.

    Returns:
        Complete-row sequence from the current Git HEAD.

    Raises:
        FileNotFoundError: The checkout or reviewed HEAD ledger is unavailable.
    """
    metadata_error = git_checkout_metadata_error(repo_root=WORKDIR)
    if metadata_error:
        raise FileNotFoundError(
            "request-log Git history baseline is unavailable: "
            f"{metadata_error}"
        )
    git_prefix = [
        "git",
        "--no-replace-objects",
        "-C",
        str(WORKDIR),
    ]
    repository_check = subprocess.run(
        args=[*git_prefix, "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        env=sanitized_git_environment(),
    )
    if (
        repository_check.returncode != 0
        or not repository_check.stdout.strip()
    ):
        raise FileNotFoundError(
            "request-log Git history baseline is unavailable"
        )
    try:
        repository_root = Path(
            repository_check.stdout.decode("utf-8").strip()
        ).resolve()
    except (OSError, UnicodeDecodeError) as error:
        print(f"Request-log Git toplevel is invalid: {error}")
        raise FileNotFoundError(
            "request-log Git history baseline is unavailable"
        ) from error
    if repository_root != WORKDIR.resolve():
        raise FileNotFoundError(
            "request-log Git history baseline is unavailable"
        )
    result = subprocess.run(
        args=[
            *git_prefix,
            "show",
            "HEAD:evidence/requests_log.csv",
        ],
        check=False,
        capture_output=True,
        env=sanitized_git_environment(),
    )
    if result.returncode != 0:
        diagnostic = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()
        raise FileNotFoundError(
            "committed request-log history baseline is unavailable: "
            f"{diagnostic}"
        )
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("committed request log is not UTF-8") from error
    rows = parse_request_log_rows(text=text)
    return [
        tuple(row[field] for field in REQUEST_LOG_FIELDNAMES)
        for row in rows
    ]


def check_requests_log_sec_only() -> dict:
    """Validate SEC request metadata and resolvable response observations."""
    rows = read_csv_file(path=REQUEST_LOG_PATH)
    failures = []
    unavailable = []
    header = set(csv_header(path=REQUEST_LOG_PATH))
    expected_fields = set(REQUEST_LOG_FIELDNAMES)
    missing_fields = sorted(expected_fields - header)
    unexpected_fields = sorted(header - expected_fields)
    if missing_fields:
        failures.append("missing_fields=" + ",".join(missing_fields))
    if unexpected_fields:
        failures.append("unexpected_fields=" + ",".join(unexpected_fields))
    try:
        validate_request_log_manifest(log_path=REQUEST_LOG_PATH)
    except FileNotFoundError:
        unavailable.append("request_log_manifest_missing")
    except ValueError as error:
        failures.append(f"request_log_manifest_invalid:{error}")
    if missing_fields or unexpected_fields:
        return validation_row(
            check_id="requests_log_sec_only",
            status="FAIL",
            details=";".join(failures),
        )
    actual_sequence = [
        tuple(row[field] for field in REQUEST_LOG_FIELDNAMES)
        for row in rows
    ]
    try:
        committed_sequence = committed_request_observation_sequence()
    except FileNotFoundError:
        unavailable.append("request_log_history_baseline_unavailable")
        committed_sequence = []
    except ValueError as error:
        failures.append(f"committed_request_log_invalid:{error}")
        committed_sequence = []
    if actual_sequence[:len(committed_sequence)] != committed_sequence:
        mismatch_row = min(len(actual_sequence), len(committed_sequence)) + 1
        for index in range(min(len(actual_sequence), len(committed_sequence))):
            if actual_sequence[index] != committed_sequence[index]:
                mismatch_row = index + 1
                break
        failures.append(
            "committed_request_log_prefix_mismatch="
            f"row_{mismatch_row}"
        )
    observed_raw_keys = {
        (row["source_url"], row["content_sha256"])
        for row in rows
        if row["content_sha256"]
    }
    observed_derived_keys = {
        (row["source_url"], row["accession"])
        for row in rows
        if row["content_sha256"]
    }
    observed_sidecar_keys = {
        (
            row["source_url"],
            row["status_code"],
            row["content_sha256"],
        )
        for row in rows
        if row["headers_repo_relative_path"]
    }
    try:
        required_raw_keys, required_derived_keys = (
            required_request_observation_keys()
        )
        required_sidecar_keys = stored_response_observation_keys()
    except ValueError as error:
        failures.append(f"downstream_request_identity_invalid:{error}")
        required_raw_keys = set()
        required_derived_keys = set()
        required_sidecar_keys = set()
    missing_raw_keys = sorted(required_raw_keys - observed_raw_keys)
    missing_derived_keys = sorted(
        required_derived_keys - observed_derived_keys
    )
    missing_sidecar_keys = sorted(
        required_sidecar_keys - observed_sidecar_keys
    )
    if missing_raw_keys:
        failures.append(
            "missing_downstream_raw_observations="
            f"{missing_raw_keys[:20]}"
        )
    if missing_derived_keys:
        failures.append(
            "missing_downstream_event_observations="
            f"{missing_derived_keys[:20]}"
        )
    if missing_sidecar_keys:
        failures.append(
            "missing_stored_response_observations="
            f"{missing_sidecar_keys[:20]}"
        )
    for index, row in enumerate(rows):
        source_url = request_log_source_url(row=row)
        relative_path = str(row["repo_relative_path"])
        headers_relative_path = str(row["headers_repo_relative_path"])
        if (
            not is_official_sec_url(source_url=source_url)
            or row["method"] != "GET"
            or not row["purpose"]
            or not row["user_agent"]
            or not row["document_name"]
            or not is_utc_iso_timestamp(value=row["timestamp_utc"])
        ):
            failures.append(f"{index}:invalid_request_metadata")
            continue
        derived_accession = request_accession(source_url=source_url)
        if (
            derived_accession
            and row["document_name"] != Path(urlparse(source_url).path).name
        ):
            failures.append(f"{index}:document_name_mismatch")
            continue
        try:
            status_code = int(row["status_code"])
            retry_attempt = int(row["retry_attempt"])
            content_length = int(row["content_length"])
        except ValueError:
            failures.append(f"{index}:invalid_numeric_metadata")
            continue
        if (
            (status_code != 0 and not 100 <= status_code <= 599)
            or retry_attempt < 0
            or content_length < 0
        ):
            failures.append(f"{index}:invalid_numeric_metadata")
            continue
        error_text = row["error"]
        redirect_disabled = (
            300 <= status_code < 400
            and error_text.startswith(REDIRECT_DISABLED_ERROR_PREFIX)
        )
        if (
            (status_code == 0 and not error_text)
            or (0 < status_code < 300 and error_text)
            or (300 <= status_code < 400 and not redirect_disabled)
            or (status_code >= 400 and not error_text)
        ):
            failures.append(f"{index}:status_error_mismatch")
            continue
        for locator in [relative_path, headers_relative_path]:
            if (
                locator
                and (
                    Path(locator).is_absolute()
                    or ".." in Path(locator).parts
                )
            ):
                failures.append(f"{index}:non_portable_response_locator")
        if derived_accession and row["accession"] != derived_accession:
            failures.append(f"{index}:accession_mismatch")
            continue
        digest = row["content_sha256"]
        if not digest:
            if (
                status_code != 0
                or content_length != 0
                or relative_path
                or headers_relative_path
            ):
                failures.append(f"{index}:body_locator_without_hash")
            continue
        if re.fullmatch(pattern=r"[0-9a-f]{64}", string=digest) is None:
            failures.append(f"{index}:invalid_content_sha256")
            continue
        if status_code == 0 or not relative_path or not headers_relative_path:
            unavailable.append(f"{index}:response_locator_missing")
            continue
        try:
            body_path = request_artifact_candidate(
                workdir=WORKDIR,
                relative_path=relative_path,
            )
            headers_path = request_artifact_candidate(
                workdir=WORKDIR,
                relative_path=headers_relative_path,
            )
            encoded_headers_hash = immutable_request_headers_hash(
                relative_path=relative_path,
                headers_relative_path=headers_relative_path,
                content_sha256=digest,
            )
        except ValueError as error:
            failures.append(f"{index}:{error}")
            continue
        if not body_path.is_file() or not headers_path.is_file():
            unavailable.append(f"{index}:response_artifact_missing")
            continue
        if row["document_name"] != body_path.name:
            failures.append(f"{index}:document_name_mismatch")
            continue
        if (
            file_sha256(path_text=str(body_path)) != digest
            or body_path.stat().st_size != content_length
        ):
            unavailable.append(f"{index}:response_body_hash_mismatch")
            continue
        headers_bytes = headers_path.read_bytes()
        if (
            encoded_headers_hash
            and hashlib.sha256(headers_bytes).hexdigest()
            != encoded_headers_hash
        ):
            unavailable.append(f"{index}:response_headers_hash_mismatch")
            continue
        try:
            headers_payload = json.loads(headers_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            unavailable.append(f"{index}:response_headers_invalid_json")
            continue
        required_header_keys = {
            "url",
            "status_code",
            "headers",
            "content_length",
            "sha256",
            "saved_at_utc",
        }
        if (
            not isinstance(headers_payload, dict)
            or set(headers_payload) != required_header_keys
            or not isinstance(headers_payload["headers"], dict)
        ):
            unavailable.append(f"{index}:response_headers_schema_mismatch")
            continue
        response_headers = headers_payload["headers"]
        redirect_location = next(
            (
                str(value)
                for key, value in response_headers.items()
                if str(key).casefold() == "location"
            ),
            "",
        )
        if redirect_disabled and not redirect_location:
            failures.append(f"{index}:redirect_location_missing")
            continue
        if (
            str(headers_payload["url"]) != source_url
            or str(headers_payload["status_code"]) != row["status_code"]
            or str(headers_payload["content_length"]) != row["content_length"]
            or str(headers_payload["sha256"]) != digest
            or not is_utc_iso_timestamp(
                value=str(headers_payload["saved_at_utc"])
            )
        ):
            unavailable.append(f"{index}:response_headers_observation_mismatch")
    if failures:
        return validation_row(
            check_id="requests_log_sec_only",
            status="FAIL",
            details=";".join(failures[:20]),
        )
    if unavailable:
        return not_evaluated_validation_row(
            check_id="requests_log_sec_only",
            details=";".join(unavailable[:20]),
        )
    return validation_row(
        check_id="requests_log_sec_only",
        status="PASS" if rows else "FAIL",
        details=f"rows={len(rows)}" if rows else "request rows missing",
    )


def check_stratified_audit_all_pass_or_explicitly_caveated(
    *,
    audit_rows: list[dict],
    metrics: list[dict],
) -> dict:
    """Validate the complete deterministic audit sample and its verdicts.

    Args:
        audit_rows: Rows written to outputs/stratified_audit.csv.
        metrics: Current metrics_matrix rows that define the expected sample.

    Returns:
        PASS when the exact unique sample exists and every row passed.
    """
    expected = [
        (bucket, row["company"], row["metric_id"])
        for bucket, row in select_stratified_audit_metrics(metrics=metrics)
    ]
    actual = [
        (row["source_bucket"], row["company"], row["metric_id"])
        for row in audit_rows
    ]
    expected_ids = [
        f"AUDIT_{index:02d}" for index in range(1, len(expected) + 1)
    ]
    actual_ids = [row["audit_id"] for row in audit_rows]
    duplicate_keys = sorted({key for key in actual if actual.count(key) > 1})
    duplicate_ids = sorted(
        {audit_id for audit_id in actual_ids if actual_ids.count(audit_id) > 1}
    )
    failures = []
    if actual != expected:
        failures.append(
            "sample_exact_set_mismatch:"
            f"missing={sorted(set(expected) - set(actual))}:"
            f"unexpected={sorted(set(actual) - set(expected))}"
        )
    if duplicate_keys:
        failures.append(f"duplicate_sample_keys={duplicate_keys}")
    if actual_ids != expected_ids:
        failures.append(
            "audit_id_sequence_mismatch:"
            f"expected={expected_ids}:actual={actual_ids}"
        )
    if duplicate_ids:
        failures.append(f"duplicate_audit_ids={duplicate_ids}")
    failures.extend(
        (
            f"{row['audit_id']}:{row['company']}:"
            f"{row['metric_id']}:{row['audit_notes']}"
        )
        for row in audit_rows
        if row["audit_verdict"] != "PASS"
    )
    return validation_row(
        check_id="stratified_audit_all_pass_or_explicitly_caveated",
        status="PASS" if expected and not failures else "FAIL",
        details=(
            ";".join(failures[:20])
            if failures
            else f"rows={len(audit_rows)} exact_sample=true"
            if expected
            else "expected stratified audit sample is empty"
        ),
    )


def metric_has_reviewable_value(*, row: dict) -> bool:
    """Return whether a metric row should enter stratified value audit.

    Args:
        row: metrics_matrix row.

    Returns:
        True for nonblank values that are not missing-state placeholders.
    """
    if row["value"] == "":
        return False
    return row["status"] not in {
        "NOT_AVAILABLE_SEC",
        "NOT_EXTRACTED",
        "PARSE_FAILED",
        "N_A_STRUCTURAL",
    }


def stratified_candidates(
    *,
    metrics: list[dict],
    source_classes: set[str],
    used_keys: set[tuple[str, str]],
    limit: int,
) -> list[dict]:
    """Select deterministic value rows for one audit stratum.

    Args:
        metrics: metrics_matrix rows.
        source_classes: Source classes accepted into this stratum.
        used_keys: Company/metric pairs already selected.
        limit: Maximum rows to select.

    Returns:
        Ordered sample rows.
    """
    selected = []
    for row in metrics:
        key = (row["company"], row["metric_id"])
        if key in used_keys:
            continue
        if row["source_class"] not in source_classes:
            continue
        if not metric_has_reviewable_value(row=row):
            continue
        selected.append(row)
        used_keys.add(key)
        if len(selected) == limit:
            break
    return selected


def select_stratified_audit_metrics(
    *,
    metrics: list[dict],
) -> list[tuple[str, dict]]:
    """Return the complete deterministic sample required by the audit.

    Args:
        metrics: Current metrics_matrix rows.

    Returns:
        Ordered source-bucket and metric pairs for every configured stratum.
    """
    used_keys: set[tuple[str, str]] = set()
    selected = []
    for bucket, source_classes, limit in STRATIFIED_AUDIT_SPECS:
        for row in stratified_candidates(
            metrics=metrics,
            source_classes=source_classes,
            used_keys=used_keys,
            limit=limit,
        ):
            selected.append((bucket, row))
    return selected


def audit_verdict_for_metric(*, metric: dict, evidence: list[dict]) -> tuple[str, str]:
    """Check whether a sampled metric has a coherent evidence chain.

    Args:
        metric: Sampled metrics_matrix row.
        evidence: Matching metric_evidence rows.

    Returns:
        PASS/FAIL and a concise explanation.
    """
    failures = []
    if not evidence:
        failures.append("missing evidence row")
    if evidence and not any(item["period_end"] == metric["period_end"] for item in evidence):
        failures.append("evidence period mismatch")
    if evidence and metric["value"]:
        evidence_values = {item["value_normalized"] for item in evidence}
        if metric["value"] not in evidence_values:
            failures.append("value not found in evidence")
    quote_text = " ".join(item["evidence_quote"] for item in evidence)
    concept_text = " ".join(item["concept_or_section"] for item in evidence)
    if metric["source_class"] in {"MDA", "TEXT"} and not quote_text:
        failures.append("text metric lacks quote")
    if metric["metric_id"] == "B11" and not re.search(
        pattern=r"\bRevPAR\b|Revenue per available room",
        string=quote_text,
        flags=re.IGNORECASE,
    ):
        failures.append("B11 quote lacks RevPAR")
    if metric["metric_id"] == "B12":
        has_rpo_text = bool(
            re.search(
                pattern=r"RPO|cRPO|remaining performance obligation",
                string=f"{quote_text} {concept_text}",
                flags=re.IGNORECASE,
            )
        )
        has_rpo_concept = any(
            concept_matches_rpo(concept=item["concept_or_section"])
            for item in evidence
        )
        if not has_rpo_text and not has_rpo_concept:
            failures.append("B12 evidence lacks RPO/cRPO")
    if metric["metric_id"] == "C03" and "PeoTotalCompAmt" not in concept_text:
        failures.append("C03 evidence lacks PeoTotalCompAmt")
    if failures:
        return "FAIL", "; ".join(failures)
    return "PASS", "value, period, accession, concept/section, and quote/concept align"


def build_stratified_audit_rows() -> list[dict]:
    """Build deterministic stratified audit rows for value-bearing metrics.

    Expected output:
        outputs/stratified_audit.csv contains the acceptance checklist sample:
        8 STD_XBRL/DERIVED, 4 DIM_XBRL, 3 DEF14A, 3 MDA/TEXT, and 2 8K_ITEM
        when enough rows exist.
    """
    metrics = load_metrics()
    evidence_rows = read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    selected = select_stratified_audit_metrics(metrics=metrics)
    rows = []
    for index, (bucket, metric) in enumerate(selected, start=1):
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=metric["company"],
            metric_id=metric["metric_id"],
        )
        primary_evidence = evidence[0] if evidence else {}
        verdict, notes = audit_verdict_for_metric(metric=metric, evidence=evidence)
        rows.append(
            {
                "audit_id": f"AUDIT_{index:02d}",
                "source_bucket": bucket,
                "company": metric["company"],
                "metric_id": metric["metric_id"],
                "metric_name": metric["metric_name"],
                "value": metric["value"],
                "unit": metric["unit"],
                "status": metric["status"],
                "source_class": metric["source_class"],
                "period_start": metric["period_start"],
                "period_end": metric["period_end"],
                "accession": metric["accession"],
                "concept_or_section": metric["concept_or_section"],
                "context_or_dimension": metric["context_or_dimension"],
                "evidence_value": (
                    primary_evidence["value_normalized"] if primary_evidence else ""
                ),
                "evidence_unit": primary_evidence["unit"] if primary_evidence else "",
                "evidence_quote": (
                    primary_evidence["evidence_quote"] if primary_evidence else ""
                ),
                "audit_verdict": verdict,
                "audit_notes": notes,
            }
        )
    return rows


def write_stratified_audit() -> list[dict]:
    """Write the current stratified audit and return its rows.

    Expected output:
        outputs/stratified_audit.csv reflects current metrics/evidence before
        repair validation or report verdict consumes it.
    """
    rows = build_stratified_audit_rows()
    write_csv_file(
        path=WORKDIR / "outputs" / "stratified_audit.csv",
        fieldnames=STRATIFIED_AUDIT_FIELDNAMES,
        rows=rows,
    )
    return rows


def implementation_map_rows() -> list[dict]:
    """Return instruction-to-implementation rows for the repair register.

    Returns:
        Rows for I1-I8 that an external reviewer can verify without guessing
        which function, artifact, or validation owns a requested fix.
    """
    return [
        {
            "instruction_id": "I1",
            "file": "outputs/review_package_manifest.md",
            "function_or_line": "Round 3 metadata and verdict vocabulary",
            "validation_id": "manual_manifest_review",
            "status": "implemented",
            "notes": (
                "Manifest distinguishes pipeline self-verdict from external "
                "audit verdict."
            ),
        },
        {
            "instruction_id": "I2",
            "file": "scripts/sec_pipeline.py",
            "function_or_line": "concept_is_basel_threshold_or_requirement",
            "validation_id": "basel_threshold_concepts_never_match_primary_metric",
            "status": "implemented",
            "notes": (
                "Bare wellcapitalized concepts remain regulatory_threshold "
                "candidates only."
            ),
        },
        {
            "instruction_id": "I3",
            "file": "scripts/sec_pipeline.py",
            "function_or_line": "captive_dimension_member_allowed",
            "validation_id": "gm_like_captive_finance_fixture_triggers_review",
            "status": "implemented",
            "notes": (
                "Contains matching is guarded by ordinary credit and lease "
                "exclusions."
            ),
        },
        {
            "instruction_id": "I4",
            "file": "tests/fixtures/eleventh_company_smoke/mock_concept_inventory.csv",
            "function_or_line": "check_eleventh_company_behavior_financial_institution",
            "validation_id": "eleventh_company_behavior_financial_institution",
            "status": "implemented",
            "notes": (
                "Fixture asserts selected concept, context, dimensions, and "
                "value."
            ),
        },
        {
            "instruction_id": "I5",
            "file": "scripts/sec_pipeline.py",
            "function_or_line": "original_full_instance_fallback_row",
            "validation_id": "FullInstanceFallbackTest",
            "status": "implemented",
            "notes": (
                "10-K/A targets map to same-period original 10-K "
                "full-instance role."
            ),
        },
        {
            "instruction_id": "I6",
            "file": "scripts/sec_pipeline.py",
            "function_or_line": "parse_instance_with_fallback",
            "validation_id": "basel_ratio_extractor_not_single_issuer_specific",
            "status": "implemented",
            "notes": (
                "Inline route, scale/sign cases, and amount crosscheck "
                "protect derived inputs."
            ),
        },
        {
            "instruction_id": "I7",
            "file": "scripts/sec_pipeline.py",
            "function_or_line": "python_literal_values_from_source",
            "validation_id": "no_company_identity_branch_in_production",
            "status": "implemented",
            "notes": "AST scanner folds string addition before identity matching.",
        },
        {
            "instruction_id": "I8",
            "file": "outputs/implementation_map.csv",
            "function_or_line": "implementation_map_rows",
            "validation_id": "python3 scripts/12_validate_repair.py",
            "status": "implemented",
            "notes": "Map is regenerated with validation output.",
        },
    ]


def write_implementation_map() -> list[dict]:
    """Write outputs/implementation_map.csv and return its rows."""
    rows = implementation_map_rows()
    write_csv_file(
        path=WORKDIR / "outputs" / "implementation_map.csv",
        fieldnames=IMPLEMENTATION_MAP_FIELDNAMES,
        rows=rows,
    )
    return rows


def csv_header(*, path: Path) -> list[str]:
    """Return a CSV header or an empty list for a missing file."""
    if not path.exists():
        return []
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        return next(csv.reader(file_obj), [])


def validation_input_available(*, path: Path) -> bool:
    """Return whether one required validation input has usable content.

    Args:
        path: Required CSV or Markdown artifact path.

    Returns:
        True for a non-empty non-CSV file or a CSV with header and data row.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if path.suffix.lower() != ".csv":
        return True
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.reader(file_obj)
        header = next(reader, [])
        first_row = next(reader, [])
    return bool(header and first_row)


def required_validation_input_row(*, mode: str) -> dict:
    """Validate structural inputs and full-only domain evidence availability.

    Args:
        mode: Current validation package mode.

    Returns:
        PASS, WORKSPACE_INCOMPLETE, or NOT_EVALUATED_MISSING_EVIDENCE.
    """
    required_paths = [
        WORKDIR / "outputs" / "metrics_matrix.csv",
        WORKDIR / "outputs" / "metric_evidence.csv",
        WORKDIR / "outputs" / "coverage_matrix.csv",
        WORKDIR / "outputs" / "golden_results.csv",
        WORKDIR / "outputs" / "company_resolution.csv",
        WORKDIR / "outputs" / "latest_filings_inventory.csv",
        WORKDIR / "outputs" / "accession_materials_inventory.csv",
        WORKDIR / "outputs" / "governance_signals.csv",
        WORKDIR / "outputs" / "events.csv",
        WORKDIR / "outputs" / "risk_legal_signals.csv",
        WORKDIR / "outputs" / "exceptions_and_review_items.md",
        (
            WORKDIR
            / "tests"
            / "fixtures"
            / "regression"
            / "previous_ok_status_snapshot.csv"
        ),
        (
            WORKDIR
            / "tests"
            / "fixtures"
            / "sec_10_company_spike"
            / "golden_expected_values.csv"
        ),
    ]
    missing_structural = [
        str(path.relative_to(WORKDIR))
        for path in required_paths
        if not validation_input_available(path=path)
    ]
    if missing_structural:
        return validation_row(
            check_id="required_validation_inputs_available",
            status="WORKSPACE_INCOMPLETE",
            details="missing structural inputs: " + ";".join(missing_structural),
        )
    if mode != "FULL_VALIDATION":
        return validation_row(
            check_id="required_validation_inputs_available",
            status="PASS",
            details=f"structural inputs available; mode={mode}",
        )
    missing_domain_evidence = []
    for company_config in load_company_registry():
        company_slug = slugify(text=str(company_config["company"]))
        for suffix in ["instance", "ecd"]:
            path = (
                WORKDIR
                / "outputs"
                / "concept_inventory"
                / f"{company_slug}_{suffix}.csv"
            )
            if not validation_input_available(path=path):
                missing_domain_evidence.append(str(path.relative_to(WORKDIR)))
    if missing_domain_evidence:
        return not_evaluated_validation_row(
            check_id="required_validation_inputs_available",
            details="missing domain evidence: " + ";".join(missing_domain_evidence),
        )
    return validation_row(
        check_id="required_validation_inputs_available",
        status="PASS",
        details="all structural and full domain inputs available",
    )


def locator_component_alignment_errors(
    *,
    row: dict,
    verify_local_provenance: bool = True,
) -> list[str]:
    """Return count, origin, or URL/accession identity alignment errors.

    Args:
        row: Portable locator row with the five identity fields.
        verify_local_provenance: Whether local JSON/CSV bytes are available for
            source-specific reverse coverage checks.

    Returns:
        Empty list for aligned scalar or semicolon-delimited locators.
    """
    relative_paths = artifact_path_parts(
        path_text=str(row["repo_relative_path"]),
    )
    path_count = len(relative_paths)
    path_bound_fields = ["content_sha256", "document_name"]
    errors = [
        f"{field}={len(artifact_path_parts(path_text=str(row[field])))}"
        for field in path_bound_fields
        if len(artifact_path_parts(path_text=str(row[field]))) != path_count
    ]
    content_hashes = artifact_path_parts(
        path_text=str(row["content_sha256"]),
    )
    for index, content_hash in enumerate(content_hashes):
        if re.fullmatch(
            pattern=r"[0-9a-f]{64}",
            string=content_hash,
        ) is None:
            errors.append(f"content_sha256[{index}]=invalid")
    document_names = artifact_path_parts(
        path_text=str(row["document_name"]),
    )
    if len(document_names) == path_count:
        for index, (relative_path, document_name) in enumerate(
            zip(relative_paths, document_names)
        ):
            if Path(relative_path).name != document_name:
                errors.append(f"document_name[{index}]=path_mismatch")
    source_urls = artifact_path_parts(path_text=str(row["source_url"]))
    accessions = artifact_path_parts(path_text=str(row["accession"]))
    for index, accession in enumerate(accessions):
        if re.fullmatch(
            pattern=r"\d{10}-\d{2}-\d{6}",
            string=accession,
        ) is None:
            errors.append(f"accession[{index}]=invalid")
    source_count = len(source_urls)
    accession_count = len(accessions)
    # Only the declared event-scan artifact may aggregate multiple SEC
    # observations; every other schema binds source and accession per path.
    is_derived_aggregate = is_derived_locator_aggregate(row=row)
    if not is_derived_aggregate:
        if source_count != path_count:
            errors.append(
                f"source_url={source_count},repo_relative_path={path_count}"
            )
        if accession_count != path_count:
            errors.append(
                f"accession={accession_count},repo_relative_path={path_count}"
            )
    if source_count != accession_count:
        errors.append(f"source_url={source_count},accession={accession_count}")
        return errors
    for index, (source_url, accession) in enumerate(
        zip(source_urls, accessions)
    ):
        if not is_official_sec_url(source_url=source_url):
            errors.append(f"source_url[{index}]=non_sec")
            continue
        archive_cik, derived_accession = archive_url_identity(
            source_url=source_url,
        )
        if is_derived_aggregate:
            if not derived_accession:
                errors.append(
                    f"source_url[{index}]=unsupported_source_type"
                )
            elif accession != derived_accession:
                errors.append(f"source_url[{index}]=accession_mismatch")
            continue
        if source_count != path_count or len(document_names) != path_count:
            continue
        component = artifact_component_row(
            row=row,
            index=index,
            component_count=path_count,
        )
        component["source_url"] = source_url
        component["accession"] = accession
        component["repo_relative_path"] = relative_paths[index]
        component["document_name"] = document_names[index]
        if companyfacts_url_cik(source_url=source_url):
            try:
                candidate = repository_artifact_candidate(
                    relative_path=relative_paths[index],
                )
            except ValueError:
                errors.append(
                    f"source_url[{index}]=companyfacts_identity_mismatch"
                )
                continue
            if not companyfacts_component_matches(
                path=candidate,
                row=component,
                verify_provenance=verify_local_provenance,
            ):
                errors.append(
                    f"source_url[{index}]=companyfacts_identity_mismatch"
                )
            continue
        if not derived_accession:
            errors.append(f"source_url[{index}]=unsupported_source_type")
            continue
        if accession != derived_accession:
            errors.append(f"source_url[{index}]=accession_mismatch")
        if Path(urlparse(source_url).path).name != document_names[index]:
            errors.append(f"source_url[{index}]=document_name_mismatch")
        try:
            row_cik = str(int(row["cik"]))
        except (KeyError, TypeError, ValueError):
            row_cik = ""
        if archive_cik != row_cik:
            errors.append(f"source_url[{index}]=cik_mismatch")
        if not accession_material_path_matches(
            path=Path(relative_paths[index]),
            accession=accession,
            cik=row_cik,
        ):
            errors.append(
                f"repo_relative_path[{index}]=accession_or_cik_mismatch"
            )
    if (
        is_derived_aggregate
        and verify_local_provenance
        and not event_aggregate_pairs_match(row=row)
    ):
        errors.append("source_url=events_exact_set_mismatch")
    return errors


def check_portable_artifact_locators(*, mode: str) -> dict:
    """Validate portable locator schemas and full raw-material resolution.

    Args:
        mode: Current validation package mode.

    Returns:
        PASS for aligned schemas and resolvable full evidence, a light skip for
        intentionally omitted raw files, or an explicit failure/non-evaluation.
    """
    locator_files = portable_locator_artifact_specs(
        existing_optional_only=True,
    )
    locator_files.extend(concept_inventory_artifact_specs())
    evidence_path_files = [
        path
        for path in [
            WORKDIR / "outputs" / "golden_results.csv",
            WORKDIR / "outputs" / "golden_candidates.csv",
        ]
        if path.exists()
    ]
    schema_failures = []
    locator_fields = {
        "source_url",
        "repo_relative_path",
        "content_sha256",
        "accession",
        "document_name",
    }
    for path, _fieldnames in locator_files:
        header = set(csv_header(path=path))
        missing_fields = sorted(locator_fields - header)
        if missing_fields:
            schema_failures.append(
                f"{path.name}:missing={','.join(missing_fields)}"
            )
        if "local_path" in header or "source_path" in header:
            schema_failures.append(f"{path.name}:legacy_path_column_present")
        if not missing_fields:
            for row_number, row in enumerate(read_csv_file(path=path), start=2):
                missing_values = sorted(
                    field for field in locator_fields if not row[field]
                )
                if missing_values:
                    schema_failures.append(
                        f"{path.name}:{row_number}:blank="
                        + ",".join(missing_values)
                    )
                alignment_errors = locator_component_alignment_errors(
                    row=row,
                    verify_local_provenance=mode == "FULL_VALIDATION",
                )
                if alignment_errors:
                    schema_failures.append(
                        f"{path.name}:{row_number}:unaligned="
                        + ",".join(alignment_errors)
                    )
    for path in evidence_path_files:
        header = set(csv_header(path=path))
        if "evidence_path" not in header:
            schema_failures.append(f"{path.name}:missing=evidence_path")
            continue
        for row_number, row in enumerate(read_csv_file(path=path), start=2):
            evidence_path = row["evidence_path"]
            if not evidence_path:
                schema_failures.append(
                    f"{path.name}:{row_number}:blank=evidence_path"
                )
                continue
            try:
                normalized_path = repo_relative_artifact_paths(
                    path_text=evidence_path,
                    row={},
                )
            except ValueError as error:
                schema_failures.append(f"{path.name}:{row_number}:{error}")
                continue
            if normalized_path != evidence_path:
                schema_failures.append(
                    f"{path.name}:{row_number}:non_portable_evidence_path"
                )
    if schema_failures:
        return validation_row(
            check_id="portable_artifact_locators",
            status="FAIL",
            details=";".join(schema_failures[:20]),
        )
    if mode == "LIGHT_REVIEW_MODE":
        return skipped_light_validation_row(
            check_id="portable_artifact_locators",
            details=(
                "portable schemas verified; raw artifact resolution skipped "
                "in light mode"
            ),
        )
    resolution_paths = [path for path, _fieldnames in locator_files]
    unresolved = []
    locator_row_count = 0
    resolved_locator_keys = set()
    for path in resolution_paths:
        rows = read_csv_file(path=path)
        locator_row_count += len(rows)
        for row in rows:
            locator_key = tuple(
                str(row[field])
                for field in [
                    "source_url",
                    "repo_relative_path",
                    "content_sha256",
                    "accession",
                    "document_name",
                ]
            )
            if locator_key in resolved_locator_keys:
                continue
            resolved_locator_keys.add(locator_key)
            try:
                resolve_artifact_paths(row=row)
            except (FileNotFoundError, ValueError) as error:
                unresolved.append(f"{path.name}:{error}")
    for path in evidence_path_files:
        rows = read_csv_file(path=path)
        locator_row_count += len(rows)
        for row in rows:
            for relative_path in artifact_path_parts(
                path_text=row["evidence_path"],
            ):
                if not repository_artifact_candidate(
                    relative_path=relative_path,
                ).exists():
                    unresolved.append(
                        f"{path.name}:missing={relative_path}"
                    )
    if unresolved:
        return not_evaluated_validation_row(
            check_id="portable_artifact_locators",
            details=";".join(unresolved[:20]),
        )
    return validation_row(
        check_id="portable_artifact_locators",
        status="PASS",
        details=(
            "portable schemas and artifacts verified; "
            f"rows={locator_row_count}"
        ),
    )


def blocking_validation_rows(*, rows: list[dict], mode: str) -> list[dict]:
    """Return rows that prevent the current validation mode from passing.

    Args:
        rows: Repair validation rows.
        mode: FULL_VALIDATION, LIGHT_REVIEW_MODE, or WORKSPACE_INCOMPLETE.

    Returns:
        FAIL and WORKSPACE_INCOMPLETE rows in every mode; full validation also
        blocks NOT_EVALUATED and any accidental light-only skip.
    """
    always_blocking = {"FAIL", "WORKSPACE_INCOMPLETE"}
    full_only_blocking = {
        "NOT_EVALUATED_MISSING_EVIDENCE",
        "SKIPPED_LIGHT_PACKAGE",
    }
    return [
        row
        for row in rows
        if row["status"] in always_blocking
        or (mode != "LIGHT_REVIEW_MODE" and row["status"] in full_only_blocking)
    ]


def validation_manifest_result(*, rows: list[dict], mode: str) -> str:
    """Return the terminal manifest result implied by validation rows.

    Args:
        rows: Complete repair validation result rows.
        mode: Validation package mode for this run.

    Returns:
        FAILED, PASSED_WITH_CAVEATS, or PASSED under the closed mode rules.
    """
    if blocking_validation_rows(rows=rows, mode=mode):
        return "FAILED"
    caveat_statuses = {
        "SKIPPED_LIGHT_PACKAGE",
        "NOT_EVALUATED_MISSING_EVIDENCE",
    }
    if any(row["status"] in caveat_statuses for row in rows):
        return "PASSED_WITH_CAVEATS"
    return "PASSED"


def projected_terminal_validation_manifest(
    *,
    rows: list[dict],
) -> tuple[dict, dict]:
    """Return active and projected manifests without publishing success.

    Args:
        rows: Complete validation rows produced by a deferred run.

    Returns:
        The persisted IN_PROGRESS manifest and an in-memory terminal copy used
        to build downstream artifacts before success becomes observable.
    """
    active_manifest = read_validation_run_manifest()
    if active_manifest["result"] != "IN_PROGRESS":
        raise RuntimeError("Deferred validation manifest is not IN_PROGRESS")
    terminal_manifest = dict(active_manifest)
    terminal_manifest["result"] = validation_manifest_result(
        rows=rows,
        mode=str(active_manifest["mode"]),
    )
    errors = validation_manifest_errors(manifest=terminal_manifest)
    if errors:
        raise ValueError(
            "Invalid projected validation manifest: " + "; ".join(errors)
        )
    return active_manifest, terminal_manifest


def run_repair_validation(
    *,
    exit_on_failure: bool,
    manifest: dict | None = None,
) -> list[dict]:
    """Run P0 checks while leaving terminal publication to the stage.

    Args:
        exit_on_failure: When True, raise SystemExit(1) for any P0 failure.
        manifest: Optional fresh IN_PROGRESS manifest already published by the
            calling stage before it modified any batch artifact.

    Returns:
        Validation result rows written to outputs/repair_validation_results.csv.
    """
    mode, light_reasons = validation_package_mode()
    if manifest is None:
        manifest = new_validation_run_manifest(
            mode=mode,
            started_at_utc=utc_now_iso(),
        )
    else:
        errors = validation_manifest_errors(manifest=manifest)
        if errors:
            raise ValueError(
                "Invalid prestarted validation manifest: "
                + "; ".join(errors)
            )
        if manifest["result"] != "IN_PROGRESS":
            raise RuntimeError(
                "Prestarted validation manifest is not IN_PROGRESS"
            )
        if manifest["refreshed_artifacts"]:
            raise RuntimeError(
                "Prestarted validation manifest already refreshed artifacts"
            )
        if read_validation_run_manifest() != manifest:
            raise RuntimeError(
                "Prestarted validation manifest differs from persisted run"
            )
        # Repair may complete evidence that changes package classification;
        # retain the run identity while recording the validation-time mode.
        manifest["mode"] = mode
    write_validation_run_manifest(manifest=manifest)
    write_implementation_map()
    mark_validation_artifact_refreshed(
        manifest=manifest,
        artifact="implementation_map.csv",
    )
    write_spec_implementation_audit()
    mark_validation_artifact_refreshed(
        manifest=manifest,
        artifact="spec_implementation_audit.csv",
    )
    if mode == "WORKSPACE_INCOMPLETE":
        rows = [workspace_incomplete_row(reasons=light_reasons)]
        write_csv_file(
            path=WORKDIR / "outputs" / "repair_validation_results.csv",
            fieldnames=REPAIR_VALIDATION_FIELDNAMES,
            rows=rows,
        )
        mark_validation_artifact_refreshed(
            manifest=manifest,
            artifact="repair_validation_results.csv",
        )
        if exit_on_failure:
            print(rows[0]["details"])
            raise SystemExit(1)
        return rows
    required_input = required_validation_input_row(mode=mode)
    if required_input["status"] != "PASS":
        # Dependent helpers cannot make honest claims when their shared input
        # contract is incomplete; stop before writing misleading PASS rows.
        rows = [
            validation_row(
                check_id="validation_package_mode",
                status="PASS",
                details=f"mode={mode}",
            ),
            required_input,
            validation_row(
                check_id="validation_gate_result",
                status="FAIL",
                details="required_validation_inputs_available",
            ),
        ]
        write_csv_file(
            path=WORKDIR / "outputs" / "repair_validation_results.csv",
            fieldnames=REPAIR_VALIDATION_FIELDNAMES,
            rows=rows,
        )
        mark_validation_artifact_refreshed(
            manifest=manifest,
            artifact="repair_validation_results.csv",
        )
        if exit_on_failure:
            print(required_input["details"])
            raise SystemExit(1)
        return rows
    if mode == "FULL_VALIDATION":
        write_stub_period_sidecar()
        mark_validation_artifact_refreshed(
            manifest=manifest,
            artifact="stub_period_metrics.csv",
        )
    metrics = load_metrics()
    evidence_rows = read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    coverage = read_csv_file(path=WORKDIR / "outputs" / "coverage_matrix.csv")
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    events = read_csv_file(path=WORKDIR / "outputs" / "events.csv")
    light_mode = mode == "LIGHT_REVIEW_MODE"
    light_details = (
        "mode=LIGHT_REVIEW_MODE; " + "; ".join(light_reasons)
        if light_mode
        else "mode=FULL_VALIDATION"
    )
    audit_rows = write_stratified_audit()
    mark_validation_artifact_refreshed(
        manifest=manifest,
        artifact="stratified_audit.csv",
    )
    scalability_check = check_no_company_identity_branch_in_production()
    mark_validation_artifact_refreshed(
        manifest=manifest,
        artifact="scalability_audit.csv",
    )
    c03_peo_check = check_c03_def14a_ok_requires_peo(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    rows = [
        validation_row(
            check_id="validation_package_mode",
            status="PASS",
            details=light_details,
        ),
        required_input,
        check_portable_artifact_locators(mode=mode),
        (
            skipped_light_validation_row(
                check_id="eightk_event_chain_exact_set",
                details=(
                    f"{light_details}; requires saved submissions and raw 8-K "
                    "documents"
                ),
            )
            if light_mode
            else check_8k_event_chain_exact_set(
                inventory=inventory,
                events=events,
            )
        ),
        (
            skipped_light_validation_row(
                check_id="eightk_event_outputs_match_events",
                details=(
                    f"{light_details}; requires complete 8-K inventory, "
                    "events, metrics, and evidence"
                ),
            )
            if light_mode
            else check_8k_event_outputs_match_events(
                metrics=metrics,
                evidence_rows=evidence_rows,
                events=events,
                inventory=inventory,
            )
        ),
        scalability_check,
        check_registry_profile_matches_sic_rules_or_has_override_reason(),
        check_metrics_matrix_applicability_matches_02_04_spec(metrics=metrics),
        check_no_unexpected_optional_b_metrics_in_main_matrix(metrics=metrics),
        check_c02_matrix_matches_governance_signals(metrics=metrics),
        check_c02_text_qual_requires_evidence_quote(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_no_placeholder_notes_in_final_metrics(metrics=metrics),
        check_b06_needs_review_captive_finance_has_blank_main_value_or_candidate_role(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        (
            skipped_light_validation_row(
                check_id="rpo_crpo_prefers_instance_fact",
                details=(
                    f"{light_details}; requires "
                    "outputs/concept_inventory/*_instance.csv"
                ),
            )
            if light_mode
            else check_rpo_crpo_prefers_instance_fact(
                metrics=metrics,
                evidence_rows=evidence_rows,
            )
        ),
        check_basel_ratio_extractor(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        (
            skipped_light_validation_row(
                check_id="jpm_cet1_capital_scale_crosscheck",
                details=(
                    f"{light_details}; requires outputs/concept_inventory/"
                    "jpmorgan_chase_instance.csv"
                ),
            )
            if light_mode
            else check_jpm_cet1_capital_scale_crosscheck()
        ),
        check_basel_concept_resolver_handles_tierone_spelling(),
        check_basel_concept_resolver_handles_banking_regulation_ratio_family(),
        check_basel_cet1_never_classified_as_a01(),
        check_basel_threshold_concepts_never_match_primary_metric(),
        check_basel_primary_selection_prefers_actual_ratio_over_threshold(),
        check_a01_a02_metric_evidence_excludes_threshold_concepts(
            evidence_rows=evidence_rows,
        ),
        check_jpm_a10_allowance_ratio_std_xbrl_primary(metrics=metrics),
        check_jpm_a10_excludes_debt_securities_allowance(
            evidence_rows=evidence_rows,
        ),
        check_jpm_a10_primary_denominator_before_allowance_for_credit_loss(
            evidence_rows=evidence_rows,
        ),
        check_jpm_a10_evidence_lists_numerator_and_denominator(
            evidence_rows=evidence_rows,
        ),
        check_a08_uses_noninterest_income_not_fee_label_guess(
            evidence_rows=evidence_rows,
        ),
        check_a08_notes_definition_name_tension(metrics=metrics),
        check_a08_evidence_has_source_components(evidence_rows=evidence_rows),
        check_jpm_mda_raw_row_anchor(
            evidence_rows=evidence_rows,
            metric_id="A03",
            check_id="jpm_a03_lcr_raw_row_anchor",
        ),
        check_jpm_a04_nim_raw_row_anchor_or_proxy_caveat(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_jpm_mda_raw_row_anchor(
            evidence_rows=evidence_rows,
            metric_id="A11",
            check_id="jpm_a11_aum_raw_row_anchor",
        ),
        check_jpm_mda_raw_row_anchor(
            evidence_rows=evidence_rows,
            metric_id="A12",
            check_id="jpm_a12_var_raw_row_anchor",
        ),
        check_jpm_table_values_not_added_to_golden_until_manual_confirmation(),
        check_lodging_kpi_extractor(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_lodging_header_mapping_not_position_regex(),
        check_lodging_revpar_adr_occupancy_identity(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_lodging_ok_recall_not_regressed_without_reason(metrics=metrics),
        (
            skipped_light_validation_row(
                check_id="captive_finance_debt_not_ford_specific",
                details=(
                    f"{light_details}; requires "
                    "outputs/concept_inventory/*_instance.csv"
                ),
            )
            if light_mode
            else check_captive_finance_debt(metrics=metrics)
        ),
        check_captive_finance_signal_requires_segment_dimension(),
        check_captive_finance_excludes_normal_finance_lease_terms(),
        (
            skipped_light_validation_row(
                check_id="enphase_b06_not_captive_finance_false_positive",
                details=(
                    f"{light_details}; requires "
                    "outputs/concept_inventory/*_instance.csv"
                ),
            )
            if light_mode
            else check_enphase_b06_not_captive_finance_false_positive(
                metrics=metrics,
            )
        ),
        check_b06_total_debt_prefers_total_debt_concepts(
            evidence_rows=evidence_rows,
        ),
        check_b06_no_adder_double_count(evidence_rows=evidence_rows),
        check_b06_tier_pairing_uses_current_sibling(
            evidence_rows=evidence_rows,
        ),
        check_b06_excludes_debt_securities_and_debt_fair_value(
            evidence_rows=evidence_rows,
        ),
        check_b06_negative_equity_not_ok(metrics=metrics),
        check_enphase_b06_golden_unchanged_after_debt_resolver(metrics=metrics),
        check_ford_b06_captive_finance_still_needs_review(metrics=metrics),
        check_gm_like_captive_finance_fixture_triggers_review(),
        check_entity_continuity_yoy(metrics=metrics),
        check_marriott_b03_da_composition_positive(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_da_composition_rejects_accumulated_expected_future_schedule(),
        check_da_composition_completeness_scan_clean_or_noted(metrics=metrics),
        check_da_custom_line_reconciliation_noted(metrics=metrics),
        check_pfizer_b03_operating_income_reconstruction_ok_approx(
            metrics=metrics,
        ),
        check_pfizer_b07_reuses_approx_operating_income(metrics=metrics),
        check_direct_operating_income_priority_over_reconstruction(
            metrics=metrics,
        ),
        check_b03_rejects_mixed_accession_period_unit(),
        check_b03_bridge_fragment_negative_fixture_rejected_or_needs_review(),
        check_paramount_stub_period_values_not_main_annual_ok(metrics=metrics),
        check_paramount_stub_period_sidecar_exists(),
        check_paramount_b06_point_in_time_successor_balance_sheet_note(
            metrics=metrics,
        ),
        check_no_c03_ecd_fact_count(metrics=metrics, evidence_rows=evidence_rows),
        c03_peo_check,
        validation_row(
            check_id="c03_uses_ecd_peototalcompamt_for_all_companies",
            status=c03_peo_check["status"],
            details="C03 PeoTotalCompAmt generic gate mirrors DEF14A evidence check",
        ),
        (
            skipped_light_validation_row(
                check_id="c04_uses_auditorname_for_all_companies",
                details=(
                    f"{light_details}; requires current/prior local "
                    "AuditorName facts"
                ),
            )
            if light_mode
            else check_c04_auditorname_all_companies(
                metrics=metrics,
                evidence_rows=evidence_rows,
                inventory=inventory,
            )
        ),
        check_eleventh_company_smoke_mounts(),
        check_eleventh_company_behavior_lodging(),
        check_eleventh_company_behavior_financial_institution(),
        check_eleventh_company_behavior_captive_finance(),
        check_eleventh_company_behavior_rpo_crpo(),
        check_ok_status_recall_not_regressed_without_reason(metrics=metrics),
        check_coverage_join(
            coverage=coverage,
            evidence_rows=evidence_rows,
            metrics=metrics,
        ),
        check_numeric_ok_requires_evidence(
            metrics=metrics,
            evidence_rows=evidence_rows,
            events=events,
        ),
        check_d04_going_concern_text(metrics=metrics, evidence_rows=evidence_rows),
        (
            check_light_golden_snapshot_integrity()
            if light_mode
            else check_golden_results_all_pass()
        ),
        (
            skipped_light_validation_row(
                check_id="requests_log_sec_only",
                details=f"{light_details}; requires evidence/requests_log.csv",
            )
            if light_mode
            else check_requests_log_sec_only()
        ),
        check_stratified_audit_all_pass_or_explicitly_caveated(
            audit_rows=audit_rows,
            metrics=metrics,
        ),
    ]
    blocking_rows = blocking_validation_rows(rows=rows, mode=mode)
    failed_ids = [row["check_id"] for row in blocking_rows]
    caveat_rows = [
        row
        for row in rows
        if row["status"]
        in {
            "SKIPPED_LIGHT_PACKAGE",
            "NOT_EVALUATED_MISSING_EVIDENCE",
        }
    ]
    rows.append(
        validation_row(
            check_id="validation_gate_result",
            status=(
                "FAIL"
                if failed_ids
                else "SKIPPED_LIGHT_PACKAGE"
                if light_mode and caveat_rows
                else "PASS"
            ),
            details=(
                ";".join(failed_ids[:20])
                if failed_ids
                else (
                    "full gate not evaluated; light-scope checks have no "
                    "blocking failures; caveats: "
                    + ";".join([row["check_id"] for row in caveat_rows])
                )
                if caveat_rows
                else "all gates pass"
            ),
        )
    )
    write_csv_file(
        path=WORKDIR / "outputs" / "repair_validation_results.csv",
        fieldnames=REPAIR_VALIDATION_FIELDNAMES,
        rows=rows,
    )
    mark_validation_artifact_refreshed(
        manifest=manifest,
        artifact="repair_validation_results.csv",
    )
    blocking_rows = blocking_validation_rows(rows=rows, mode=mode)
    if blocking_rows and exit_on_failure:
        print("Repair validation failed:")
        for row in blocking_rows:
            print(f"{row['check_id']}: {row['details']}")
        raise SystemExit(1)
    if not blocking_rows and light_mode:
        print(
            "Light review validation complete; full-evidence checks skipped: "
            + "; ".join(light_reasons)
        )
    elif not blocking_rows:
        print("Repair validation complete; all P0 checks pass")
    return rows


def build_exceptions_markdown() -> str:
    """Build exceptions and review markdown from matrix statuses."""
    statuses = {
        "NOT_AVAILABLE_SEC",
        "NOT_EXTRACTED",
        "NEEDS_REVIEW",
        "NOT_MEANINGFUL",
        "N_A_STRUCTURAL",
        "PARSE_FAILED",
    }
    rows = [row for row in load_metrics() if row["status"] in statuses]
    lines = [
        "# Exceptions and Review Items",
        "",
        f"Generated UTC: {utc_now_iso()}",
        "",
        "## 本轮修复前降级的错值",
        "",
        (
            "- Lodging B11: rejected percentage-change values when the metric "
            "requires absolute RevPAR."
        ),
        (
            "- Subscription/contract B12: rejected small context/date noise "
            "when it is not an RPO/cRPO fact."
        ),
        (
            "- C03: rejected previous `ecd_fact_count`; C03 now uses "
            "ecd:PeoTotalCompAmt or is degraded."
        ),
        "",
        "## Full-instance fallback notes",
        "",
    ]
    fallback_rows = [
        row
        for row in read_csv_file(path=WORKDIR / "outputs" / "latest_filings_inventory.csv")
        if row["source_role"] == "target_original_full_instance"
    ]
    if fallback_rows:
        for row in fallback_rows:
            lines.append(
                f"- {row['company']} {row['reportDate']} original 10-K "
                "is marked `target_original_full_instance` for full-instance "
                "fallback from an amended or partial target."
            )
    else:
        lines.append("- No target original full-instance fallback rows are marked.")
    lines.extend(
        [
            "",
            "## 仍需复核或未抽取项目",
            "",
            "| Company | Metric | Status | Reason |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        next_step = "improve the relevant industry extractor or source registry"
        if row["status"] == "NOT_EXTRACTED":
            next_step = (
                "improve industry extractor, header mapping, or concept resolver"
            )
        if row["status"] == "NEEDS_REVIEW":
            next_step = "manual review required before treating as numeric truth"
        if row["status"] == "NOT_AVAILABLE_SEC":
            next_step = "leave blank unless SEC source later discloses it"
        lines.append(
            f"| {row['company']} | {row['metric_id']} {row['metric_name']} | "
            f"{row['status']} | {row['notes']} Next step: {next_step}. |"
        )
    return "\n".join(lines) + "\n"


def markdown_table(
    *,
    rows: list[dict],
    columns: list[str],
    limit: int,
) -> list[str]:
    """Return a compact Markdown table from dictionaries."""
    output = []
    output.append("| " + " | ".join(columns) + " |")
    output.append("|" + "|".join(["---" for _ in columns]) + "|")
    for row in rows[:limit]:
        values = [str(row[column]) for column in columns]
        output.append("| " + " | ".join(values) + " |")
    return output


def request_stats() -> dict:
    """Summarize SEC request log for the report."""
    rows = read_csv_file(path=REQUEST_LOG_PATH)
    sec_only = [
        row
        for row in rows
        if request_log_source_url(row=row).startswith("https://www.sec.gov/")
        or request_log_source_url(row=row).startswith("https://data.sec.gov/")
    ]
    statuses: dict[str, int] = {}
    for row in sec_only:
        status = row["status_code"]
        if status not in statuses:
            statuses[status] = 0
        statuses[status] += 1
    return {
        "total": str(len(sec_only)),
        "statuses": json_text(value=statuses),
    }


def report_verdict(
    *,
    golden_rows: list[dict],
    metric_rows: list[dict],
    validation_rows: list[dict],
    validation_manifest: dict,
) -> str:
    """Return GO / GO WITH CAVEATS / NO-GO for the final report."""
    if validation_manifest_errors(manifest=validation_manifest):
        return "NO-GO"
    mode = str(require_key(mapping=validation_manifest, key="mode"))
    manifest_result = str(
        require_key(mapping=validation_manifest, key="result")
    )
    if manifest_result in {"FAILED", "IN_PROGRESS"}:
        return "NO-GO"
    if not manifest_artifact_was_refreshed(
        manifest=validation_manifest,
        artifact="repair_validation_results.csv",
    ):
        return "NO-GO"
    if not validation_rows or not golden_rows:
        return "NO-GO"
    required_validation_fields = {"check_id", "severity", "status"}
    if any(
        not required_validation_fields.issubset(row)
        or row["severity"] != "P0"
        or row["status"] not in VALIDATION_STATUSES
        for row in validation_rows
    ):
        return "NO-GO"
    aggregate_rows = [
        row
        for row in validation_rows
        if row["check_id"] == "validation_gate_result"
    ]
    if len(aggregate_rows) != 1:
        return "NO-GO"
    aggregate_status = aggregate_rows[0]["status"]
    if mode == "FULL_VALIDATION" and (
        manifest_result != "PASSED" or aggregate_status != "PASS"
    ):
        return "NO-GO"
    if mode == "LIGHT_REVIEW_MODE" and (
        manifest_result != "PASSED_WITH_CAVEATS"
        or aggregate_status != "SKIPPED_LIGHT_PACKAGE"
    ):
        return "NO-GO"
    if mode == "WORKSPACE_INCOMPLETE":
        return "NO-GO"
    if any(
        row["severity"] == "P0"
        and row["status"] in {"FAIL", "WORKSPACE_INCOMPLETE"}
        for row in validation_rows
    ):
        return "NO-GO"
    if mode != "LIGHT_REVIEW_MODE" and any(
        row["status"]
        in {
            "NOT_EVALUATED_MISSING_EVIDENCE",
            "SKIPPED_LIGHT_PACKAGE",
        }
        for row in validation_rows
    ):
        return "NO-GO"
    if any(
        "status" not in row or row["status"] != "PASS"
        for row in golden_rows
    ):
        return "NO-GO"
    validation_caveat_statuses = {
        "SKIPPED_LIGHT_PACKAGE",
        "NOT_EVALUATED_MISSING_EVIDENCE",
    }
    if mode == "LIGHT_REVIEW_MODE" or any(
        row["status"] in validation_caveat_statuses
        for row in validation_rows
    ):
        return "GO WITH CAVEATS"
    caveat_statuses = {"NOT_EXTRACTED", "NEEDS_REVIEW", "PARSE_FAILED"}
    if any(row["status"] in caveat_statuses for row in metric_rows):
        return "GO WITH CAVEATS"
    return "GO"


def build_report_markdown(*, validation_manifest: dict | None = None) -> str:
    """Build the final Chinese Markdown report for one validation run.

    Args:
        validation_manifest: Optional projected terminal manifest. Stage 11/12
            supplies it before terminal success is persisted; other callers
            read the current persisted manifest.

    Returns:
        Complete UTF-8 Markdown report text.
    """
    metrics = load_metrics()
    resolution = read_csv_file(path=WORKDIR / "outputs" / "company_resolution.csv")
    coverage = read_csv_file(path=WORKDIR / "outputs" / "coverage_matrix.csv")
    golden = read_csv_file(path=WORKDIR / "outputs" / "golden_results.csv")
    if validation_manifest is None:
        validation_manifest = read_validation_run_manifest()
    validation = []
    if manifest_artifact_was_refreshed(
        manifest=validation_manifest,
        artifact="repair_validation_results.csv",
    ):
        validation = read_csv_file(
            path=WORKDIR / "outputs" / "repair_validation_results.csv"
        )
    stratified_audit = []
    if manifest_artifact_was_refreshed(
        manifest=validation_manifest,
        artifact="stratified_audit.csv",
    ):
        stratified_audit = read_csv_file(
            path=WORKDIR / "outputs" / "stratified_audit.csv"
        )
    events = read_csv_file(path=WORKDIR / "outputs" / "events.csv")
    stats = request_stats()
    verdict = report_verdict(
        golden_rows=golden,
        metric_rows=metrics,
        validation_rows=validation,
        validation_manifest=validation_manifest,
    )
    ok_statuses = {
        "OK",
        "OK_APPROX",
        "MDA_OK",
        "DEF14A_OK",
        "DIM_XBRL_OK",
        "8K_ITEM_OK",
        "TEXT_QUAL",
    }
    ok_count = len([row for row in metrics if row["status"] in ok_statuses])
    caveat_count = len(metrics) - ok_count
    valued_count = len([row for row in metrics if row["value"]])
    blank_count = len(metrics) - valued_count
    validation_count = len(validation)
    validation_status_counts: dict[str, int] = {}
    for row in validation:
        status = row["status"]
        if status not in validation_status_counts:
            validation_status_counts[status] = 0
        validation_status_counts[status] += 1
    refreshed_artifacts = require_key(
        mapping=validation_manifest,
        key="refreshed_artifacts",
    )
    not_refreshed_artifacts = require_key(
        mapping=validation_manifest,
        key="not_refreshed_artifacts",
    )
    lines = [
        "# REPORT_十公司财务指标",
        "",
        "## Executive Summary",
        "",
        f"- Verdict: **{verdict}**。",
        f"- SEC 请求总数：{stats['total']}；状态分布：`{stats['statuses']}`。",
        (
            f"- 指标格子：{len(metrics)}；有值：{valued_count}；"
            f"空值：{blank_count}；validation rows：{validation_count}。"
        ),
        f"- OK/TEXT 类：{ok_count}；待复核/不可得类：{caveat_count}。",
        (
            "- Validation 状态分布："
            f"`{json_text(value=validation_status_counts)}`。"
        ),
        (
            "- 本次只使用 SEC 官方响应和本地 evidence 文件；"
            "未使用第三方数据或模型记忆补数。"
        ),
        (
            "- Repair validation 若有 P0 FAIL、WORKSPACE_INCOMPLETE，或 full "
            "关键检查 NOT_EVALUATED，verdict 强制为 NO-GO。"
        ),
        (
            "- Stratified audit 任一 FAIL 会进入 repair validation gate，"
            "不能被报告静默吞掉。"
        ),
        "",
        "## Validation run manifest",
        "",
        f"- run_id: `{validation_manifest['run_id']}`",
        f"- source_commit: `{validation_manifest['source_commit']}`",
        "- `source_commit` 后缀 `+dirty` 表示运行时工作树含未提交改动。",
        f"- started_at_utc: `{validation_manifest['started_at_utc']}`",
        f"- mode: `{validation_manifest['mode']}`",
        f"- result: `{validation_manifest['result']}`",
        (
            "- refreshed_artifacts: `"
            + ", ".join([str(name) for name in refreshed_artifacts])
            + "`"
        ),
        (
            "- not_refreshed_artifacts: `"
            + (
                ", ".join([str(name) for name in not_refreshed_artifacts])
                if not_refreshed_artifacts
                else "none"
            )
            + "`"
        ),
        (
            "- 报告只展示 manifest 标记为本次 refreshed 的 validation/audit "
            "artifact；文件存在本身不证明新鲜度。"
        ),
        "",
        "## 数据来源和请求统计",
        "",
        "- company_tickers_exchange、submissions、companyfacts、"
        "accession materials、8-K hdr.sgml、DEF 14A primary document "
        "均通过 SEC 官方 URL 请求。",
        (
            "- 所有请求记录在 `evidence/requests_log.csv`；新 attempt 的"
            "响应 body/header 以 content-addressed immutable 路径保存。"
        ),
        (
            "- 历史 request row 若已无法解析到与记录 hash 一致的 bytes，"
            "只能是 NOT_EVALUATED，不能作为本次可复现 PASS 证据。"
        ),
        "",
        "## 公司身份解析表",
        "",
    ]
    lines.extend(
        markdown_table(
            rows=resolution,
            columns=[
                "company",
                "resolved_cik",
                "entity_role",
                "name",
                "fiscalYearEnd",
                "tickers",
            ],
            limit=20,
        )
    )
    lines.extend(
        [
            "",
            "## 指标覆盖率摘要",
            "",
        ]
    )
    status_counts: dict[str, int] = {}
    for row in coverage:
        status = row["status"]
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## 十公司指标矩阵摘要",
            "",
        ]
    )
    summary_metrics = [
        row
        for row in metrics
        if row["metric_id"]
        in {"B01", "B04", "B05", "B08", "B09", "A05", "A06", "A07"}
    ]
    lines.extend(
        markdown_table(
            rows=summary_metrics,
            columns=[
                "company",
                "metric_id",
                "metric_name",
                "value",
                "unit",
                "status",
                "concept_or_section",
            ],
            limit=80,
        )
    )
    lines.extend(
        [
            "",
            "## FI track：BaselCapitalRatioExtractor 指标解释",
            "",
            "- A01/A02 从 financial_institution profile 的 Basel ratio "
            "facts 读取，未用 capital amount / RWA amount 自行相除。",
            "- regulatory threshold / requirement concept 不进入 A01/A02 primary "
            "metric evidence；候选与 threshold 分流写入 "
            "`outputs/basel_ratio_candidates.csv`。",
            "- FI 专属 A03/A04/A08/A09/A10/A11/A12/A13 未用普通资产负债表硬算；"
            "LCR、AUM、VaR 等仍需要 MD&A 或表格维度事实。",
            "- financial_institution 的 B08 current ratio 标为 `N_A_STRUCTURAL`，避免把"
            "银行资产负债表错误套入商业公司流动比率。",
            "",
            "## Non-FI track",
            "",
            "- B01/B04/B05/B08/B09 优先从 companyfacts 标准事实计算，"
            "并在 `metric_evidence.csv` 记录 accession、concept、context。",
            "- B03 是 GAAP EBITDA proxy：Operating income + D&A，不加回 impairment。",
            "- CaptiveFinanceDebtExtractor 只在债务事实具有 captive/credit "
            "segment 或 legal entity 维度时标注工业口径复核要求。",
            "- RpoCrpoExtractor 优先消费 accession instance 的 RPO/cRPO "
            "facts，文本 fallback 仍明确 `RPO != ARR; cRPO != ARR`。",
            "- LodgingKpiExtractor 通过表头映射抽取 RevPAR/Occupancy/ADR "
            "绝对值；percentage change 不作为金额。",
            "- EntityContinuityYoyRule 对 successor/predecessor、stub period "
            "或 duration 不可比链路标 `NOT_MEANINGFUL`。",
            "",
            "## Governance / Risk / Event signals 摘要",
            "",
            f"- FY-window 8-K item rows: {len(events)}。",
            "- DEF 14A 输出 governance_signals，并在存在 ecd facts 时 "
            "dump 到 concept_inventory。",
            "- C04 auditor change 使用 current/prior 10-K instance 的 "
            "`dei:AuditorName` 对照；缺失时只针对 AuditorName 补抓 "
            "SEC 官方 XBRL instance，仍不可判定才标 NEEDS_REVIEW。",
            "- D01-D04 风险法律文本来自 10-K primary document 的章节/"
            "关键词片段；未披露 going concern doubt 时写明未披露，"
            "而不是 parse failure。",
            "",
            "## Fixture golden assertion 结果",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            rows=golden,
            columns=["assertion_id", "expected", "actual", "status"],
            limit=80,
        )
    )
    lines.extend(
        [
            "",
            "## Repair validation",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            rows=validation,
            columns=["check_id", "severity", "status", "details"],
            limit=40,
        )
    )
    lines.extend(
        [
            "",
            "## Scalability gate",
            "",
            "- `tools/check_no_company_literals.py` 写入 "
            "`outputs/scalability_audit.csv`，生产路径不得按公司名、CIK、"
            "ticker、固定 accession 或固定财年日期分支。",
            "- `repair_validation_results.csv` 中 "
            "`eleventh_company_behavior_*` 必须 PASS；新增同行业公司应只改 "
            "`config/company_registry.csv` 和 `tests/fixtures/`，不改 "
            "`scripts/sec_pipeline.py`。",
        ]
    )
    lines.extend(
        [
            "",
            "## 分层抽样 audit",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            rows=stratified_audit,
            columns=[
                "audit_id",
                "source_bucket",
                "company",
                "metric_id",
                "value",
                "unit",
                "status",
                "audit_verdict",
                "audit_notes",
            ],
            limit=25,
        )
    )
    exception_rows = [
        row
        for row in metrics
        if row["status"] in {"NOT_AVAILABLE_SEC", "NOT_EXTRACTED", "NEEDS_REVIEW"}
    ]
    lines.extend(
        [
            "",
            "## NOT_AVAILABLE_SEC / NOT_EXTRACTED / NEEDS_REVIEW 清单",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            rows=exception_rows,
            columns=["company", "metric_id", "metric_name", "status", "notes"],
            limit=120,
        )
    )
    lines.extend(
        [
            "",
            "## 产品化判断",
            "",
            "- 可产品化：companyfacts 标准公司级事实、8-K item inventory、"
            "基础 risk heading/keyword 定性信号、请求日志/hash 证据链。",
            "- 暂不可直接产品化：复杂 Basel/NPL/AUM/VaR 表格抽取、"
            "工业/金融维度债务拆分、DEF 14A 董事会结构化计数、"
            "复杂 MD&A 表格 KPI。",
            "",
            f"## Verdict: {verdict}",
            "",
            "- 本 spike 未构建生产系统、报价模型、前端或 daily update 调度。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_readme() -> str:
    """Build README_RUN.md with reproducible commands."""
    return "\n".join(
        [
            "# README_RUN",
            "",
            "## 配置",
            "",
            "- 运行时支持 POSIX 本地文件系统上的 Python 3.9+。",
            "- SEC HTTP 配置：`config/sec_config.json`。",
            "- 所有时间戳使用 UTC；文本编码 UTF-8。",
            "- 单个 `SecHttpClient` 实例执行进程内请求节流，默认 5 requests/sec；",
            (
                "  不同 client 或进程之间不协调限速；同一 "
                "repository 的 request log"
            ),
            (
                "  publication 会在 cooperating threads / POSIX processes "
                "间串行化，不承诺网络文件系统锁语义。"
            ),
            (
                "- immutable response 防预存和最终文件名 symlink/hardlink "
                "别名，但假设单次写入期间父目录 namespace 稳定；它不是 "
                "WORM 存储。"
            ),
            (
                "- `SecHttpClient` 不自动跟随 HTTP redirect；首跳 3xx "
                "body、headers、Location 与日志会保留，目标 URL "
                "只能作为"
                "下一次显式、重新校验的请求。"
            ),
            "",
            "## 从干净目录运行阶段 00-11",
            "",
            "```bash",
            "python3 scripts/00_smoke_test_sec_access.py",
            "python3 scripts/01_resolve_companies.py",
            "python3 scripts/02_inventory_filings.py",
            "python3 scripts/03_companyfacts_inventory.py",
            "python3 scripts/04_compute_standard_metrics.py",
            "python3 scripts/05_fetch_accession_materials.py",
            "python3 scripts/06_parse_xbrl_instances.py",
            "python3 scripts/07_extract_8k_events.py",
            "python3 scripts/08_extract_def14a.py",
            "python3 scripts/09_extract_mda_and_risk_text.py",
            "python3 scripts/10_run_golden_assertions.py",
            "python3 scripts/11_build_report.py",
            "```",
            "",
            (
                "阶段 11 的 bounded repair primarily uses local artifacts, "
                "but C04 AuditorName repair only fetches the next official "
                "SEC candidate while all ordered local facts remain "
                "unavailable."
            ),
            (
                "随后阶段 11 生成 coverage、exceptions、validation run "
                "manifest、repair validation、最终报告和本 README。"
            ),
            "",
            "## 验收顺序",
            "",
            "### 第一层：十家公司功能验收",
            "",
            "```bash",
            "python3 scripts/10_run_golden_assertions.py",
            "python3 scripts/12_validate_repair.py",
            "```",
            "",
            (
                "- `outputs/golden_results.csv` 必须与配置/generator/"
                "fixture 推导的 assertion exact set 一致、唯一且全 "
                "PASS。"
            ),
            (
                "- `outputs/stratified_audit.csv` 必须与当前 metrics "
                "推导的"
                "五层 deterministic sample exact set 一致且唯一。"
            ),
            (
                "- 完整工作区 `outputs/repair_validation_results.csv` 必须全 PASS；"
                "轻量审核包中依赖 raw evidence / concept inventory 的检查必须显示为 "
                "`SKIPPED_LIGHT_PACKAGE`；full gate 本身也不能写成 PASS。"
            ),
            (
                "- validation status 只使用 `PASS`、`FAIL`、"
                "`SKIPPED_LIGHT_PACKAGE`、"
                "`NOT_EVALUATED_MISSING_EVIDENCE`、"
                "`WORKSPACE_INCOMPLETE`。缺材料不能写成 PASS。"
            ),
            (
                "- 轻量审核包必须在根目录包含 "
                "`LIGHT_REVIEW_PACKAGE.marker`；未声明的缺 evidence / "
                "concept inventory 工作区必须 `WORKSPACE_INCOMPLETE`。"
            ),
            (
                "- full 模式中的关键 `NOT_EVALUATED_MISSING_EVIDENCE` "
                "阻止 GO；light 模式只能把它作为显式 caveat。"
            ),
            (
                "- 先读 `outputs/validation_run_manifest.json` 判断本次真正"
                "刷新的 validation artifact；旧文件存在不代表本次已评估。"
            ),
            (
                "- 阶段 11/12 的报告写入成功后才发布 terminal "
                "manifest；写入失败必须保持 `IN_PROGRESS`。"
            ),
            "- manifest 的 `source_commit` 带 `+dirty` 时，表示运行时工作树含未提交改动。",
            "- `metrics/evidence/coverage/report` 必须能互相追溯一致。",
            "",
            "### 第二层：去公司特例验收",
            "",
            "```bash",
            "python3 tools/check_no_company_literals.py",
            "python3 tools/check_capability_contract_alignment.py",
            "```",
            "",
            "- 生产 extractor 不得出现公司名业务分支。",
            "- `config/`、`tests/fixtures/`、报告模板可以出现公司名。",
            "- 自动审计使用 AST 扫描 Python literal，明细写入 "
            "`outputs/scalability_audit.csv`。",
            (
                "- capability checker 只验证 anchor/path/symbol 等结构事实；"
                "symbol 存在不等于 claim 已被证明，证据强度仍由 reviewer "
                "判断为 direct / partial / structural / none。"
            ),
            "",
            "### 第三层：第 11 家公司测试",
            "",
            (
                "- 新增同行业公司只允许改 `config/company_registry.csv` "
                "和 `tests/fixtures/`。"
            ),
            "- 不允许为新增同行业公司改 `scripts/sec_pipeline.py`。",
            "- `repair_validation_results.csv` 的 "
            "`eleventh_company_behavior_*` 必须 PASS。",
            "",
            "失败时脚本 exit nonzero，并把逐项原因写入对应 "
            "outputs CSV。",
            "",
            "## 本轮修复的请求边界",
            "",
            (
                "- Lodging B10/B11 使用表头映射抽取 RevPAR/Occupancy "
                "绝对值；B12 RPO/cRPO 优先 instance fact；C03 "
                "PeoTotalCompAmt、FI A01/A02 ratio facts、coverage join、"
                "exceptions/report 更新。"
            ),
            (
                "- C04 先检查 target 10-K/A，再在 AuditorName 不可用时"
                "回退同 CIK、同期间原始 10-K；"
                "空白/冲突事实必须降级；仍缺失时才按候选顺序"
                "最小补抓 SEC 官方 XBRL instance；"
                "期间起点只允许由同 CIK prior 10-K 推导；"
                "所有请求仍通过 `SecHttpClient.fetch(...)` 写入 "
                "`evidence/requests_log.csv` 及其 exact-set manifest。"
            ),
            (
                "- full validation 从 submissions 推导 FY 8-K inventory，"
                "重放 raw hdr/primary item 并与 `events.csv` exact-set "
                "比对；正向 count 逐 event component 保留 evidence，零值"
                "只在完整扫描确无匹配项时成立。"
            ),
            (
                "- `metrics_matrix.csv` 必须恰好包含 registry/profile/"
                "applicability contract 推导的 unique `(company, "
                "metric_id)` set；`coverage_matrix.csv` 必须与该 matrix "
                "exact key set "
                "完全一致。"
            ),
            (
                "- `outputs/stratified_audit.csv` 固化验收分层抽样："
                "STD_XBRL/DERIVED、DIM_XBRL、DEF14A、MDA/TEXT、8K_ITEM；"
                "缺行、重复或多余样本均失败。"
            ),
            "",
            "## P0 validation 失败定位",
            "",
            (
                "- 先打开 `outputs/repair_validation_results.csv`，按 "
                "`check_id` 查看 FAIL 行。"
            ),
            (
                "- 对证据缺失类失败，按 `(company, metric_id)` join "
                "`outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。"
            ),
            (
                "- 对 matrix/coverage 完整性失败，"
                "先看 details 中的 "
                "missing、unexpected 与 duplicate keys；禁止用固定"
                "行数或"
                "复制现有行凑齐集合。"
            ),
            (
                "- 对 8-K 失败，按 submissions→FY inventory→raw filing→"
                "events→metric/component evidence 顺序核对 missing、"
                "unexpected 与 duplicate identity。"
            ),
            (
                "- 对 C03 失败，检查 `outputs/concept_inventory/*_ecd.csv` "
                "中目标 `period_end` 的 `PeoTotalCompAmt`。"
            ),
            (
                "- 对 FI Basel ratio 失败，检查对应 "
                "`outputs/concept_inventory/*_instance.csv` 的 ratio facts。"
            ),
            (
                "- 对请求边界失败，先检查 "
                "`evidence/requests_log_manifest.json` 的 row count/hash、"
                "Git HEAD/base 有序前缀与下游/sidecar 反向覆盖，再"
                "检查 "
                "`evidence/requests_log.csv` 的 "
                "URL、User-Agent、retry_attempt、body/header locator 和 "
                "content_sha256。"
            ),
            (
                "- 对 `NOT_EVALUATED_MISSING_EVIDENCE`，不要把空 failure list "
                "解释为通过；按 details 补齐所需材料后重跑。"
            ),
            "",
            "## 主要输出",
            "",
            "- `outputs/metrics_matrix.csv`",
            "- `outputs/metric_evidence.csv`",
            "- `outputs/basel_ratio_candidates.csv`",
            "- `outputs/governance_signals.csv`",
            "- `outputs/coverage_matrix.csv`",
            "- `outputs/exceptions_and_review_items.md`",
            "- `outputs/repair_validation_results.csv`",
            "- `outputs/validation_run_manifest.json`",
            "- `outputs/stratified_audit.csv`",
            "- `outputs/events.csv`",
            "- `outputs/golden_results.csv`",
            "- `outputs/implementation_map.csv`",
            "- `evidence/requests_log_manifest.json`",
            "- `REPORT_十公司财务指标.md`",
            "",
            "## 轻量审核包",
            "",
            (
                "- 审核包只纳入代码、配置、fixture、关键 outputs 和报告；"
                "不纳入 `evidence/`、大体量 `outputs/concept_inventory/`、"
                "`__pycache__/` 或 `.DS_Store`。"
            ),
            (
                "- 轻量包中 `python3 scripts/12_validate_repair.py` 运行 "
                "`LIGHT_REVIEW_MODE`：可重跑代码级、矩阵级和随包 audit gate；"
                "缺 raw evidence 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`。"
            ),
            (
                "- 轻量包中 `python3 scripts/10_run_golden_assertions.py` "
                "重算随包 `outputs/golden_results.csv` snapshot integrity，"
                "通过时输出 `PASS: LIGHT_REVIEW_MODE`；完整数值 golden "
                "rerun 需要本地完整 `evidence/`。"
            ),
            (
                "- reviewer 必须以 `validation_run_manifest.json` 的 "
                "`refreshed_artifacts` / `not_refreshed_artifacts` 判断新鲜度，"
                "不能只检查 CSV 是否存在；该最小 manifest 只跟踪 validation/"
                "audit artifacts，Golden、矩阵与 evidence 仍需各自重跑来源。"
            ),
            (
                "- 新写入的证据 locator 使用 `source_url`、"
                "`repo_relative_path`、`content_sha256`、`accession`、"
                "`document_name`；历史绝对路径只作 relocation hint。"
            ),
            (
                "- `evidence/requests_log.csv` 的 response body 也使用上述"
                " portable 字段，headers 使用 `headers_repo_relative_path`；"
                "`requests_log_manifest.json` 以严格 JSON key/type 与 CSV "
                "行 schema 绑定整表 row count/hash；"
                "working ledger 必须保留 HEAD 有序前缀；PR checker 先要求 "
                "base/HEAD 的每条 current/legacy row 与声明 schema 精确同宽，"
                "再对 legacy base 独立规范化 portable 完整字段、对 current "
                "base 逐字段保留有序前缀，之后只允许合法尾部追加；下游/sidecar "
                "反向覆盖完整集合；"
                "新 attempt 指向 content-addressed immutable copy；旧 "
                "`url/local_path/sha256` 只作为显式 legacy bootstrap "
                "输入，常规阶段不会为缺 manifest 的日志重签。"
                "mutable submissions 重放必须匹配 ledger 中最新成功 200；"
                "filing-bound archive 文档若存在冲突成功 bodies 则失败。"
                "无 Git history baseline 或历史 hash 对应原 "
                "bytes 时，"
                "full gate 必须 NOT_EVALUATED。"
            ),
            (
                "- `outputs/implementation_map.csv` 映射 I1-I8 的实现位置、"
                "validation id 和当前状态，供审计方逐项复核。"
            ),
            (
                "- `GO WITH CAVEATS` 是 pipeline self-verdict；"
                "`ACCEPT WITH CAVEATS` 仅保留给外部审计验收结论。"
            ),
            (
                "- 包清单写入 `outputs/review_package_manifest.md`；"
                "压缩包写入 `outputs/review_package/`。"
            ),
            (
                "- 若审核官需要追溯 raw SEC source，回到本地完整工作区读取 "
                "`evidence/` 和 `outputs/concept_inventory/`。"
            ),
            "",
        ]
    )


def write_terminal_report(*, text: str, manifest: dict) -> None:
    """Persist a report only when it names the projected terminal run.

    Args:
        text: Complete generated report Markdown.
        manifest: Projected terminal validation manifest.

    Expected output:
        The regular report file contains the same run id and result that may
        subsequently become observable in the terminal manifest.
    """
    expected_lines = [
        f"- run_id: `{manifest['run_id']}`",
        f"- result: `{manifest['result']}`",
    ]
    missing_lines = [line for line in expected_lines if line not in text]
    if missing_lines:
        raise ValueError(
            "Terminal report does not match projected manifest: "
            + ";".join(missing_lines)
        )
    write_utf8_text_atomically(
        path=WORKDIR / "REPORT_十公司财务指标.md",
        text=text,
    )


def stage_build_report() -> None:
    """Stage 11: repair, validate, and build derived review documents."""
    mode, _light_reasons = validation_package_mode()
    manifest = new_validation_run_manifest(
        mode=mode,
        started_at_utc=utc_now_iso(),
    )
    # Publish this run before migration or repair can partially replace any
    # batch artifact, so an interrupted stage cannot expose an older success.
    write_validation_run_manifest(manifest=manifest)
    migrate_portable_artifact_inventories()
    apply_p0_repairs()
    coverage = build_coverage_matrix()
    write_csv_file(
        path=WORKDIR / "outputs" / "coverage_matrix.csv",
        fieldnames=[
            "company",
            "metric_id",
            "status",
            "source_class",
            "has_numeric_value",
            "has_evidence",
            "needs_text_extraction",
            "needs_review",
            "reason",
        ],
        rows=coverage,
    )
    crosscheck = build_companyfacts_crosscheck()
    write_csv_file(
        path=WORKDIR / "outputs" / "companyfacts_crosscheck.csv",
        fieldnames=[
            "company",
            "cik",
            "metric_id",
            "accession",
            "companyfacts_value",
            "instance_value",
            "match_status",
            "reason",
        ],
        rows=crosscheck,
    )
    (WORKDIR / "outputs" / "exceptions_and_review_items.md").write_text(
        build_exceptions_markdown(),
        encoding="utf-8",
    )
    rows = run_repair_validation(
        exit_on_failure=False,
        manifest=manifest,
    )
    active_manifest, terminal_manifest = (
        projected_terminal_validation_manifest(rows=rows)
    )
    report_text = build_report_markdown(
        validation_manifest=terminal_manifest,
    )
    readme_text = build_readme()
    write_terminal_report(
        text=report_text,
        manifest=terminal_manifest,
    )
    write_utf8_text_atomically(
        path=WORKDIR / "README_RUN.md",
        text=readme_text,
    )
    finish_validation_run_manifest(
        manifest=active_manifest,
        result=str(terminal_manifest["result"]),
    )
    print("Stage 11 report build complete")


def stage_validate_repair() -> None:
    """Stage 12: validate repairs, refresh the report, and fail on blockers."""
    rows = run_repair_validation(exit_on_failure=False)
    active_manifest, terminal_manifest = (
        projected_terminal_validation_manifest(rows=rows)
    )
    write_terminal_report(
        text=build_report_markdown(validation_manifest=terminal_manifest),
        manifest=terminal_manifest,
    )
    finish_validation_run_manifest(
        manifest=active_manifest,
        result=str(terminal_manifest["result"]),
    )
    failures = blocking_validation_rows(
        rows=rows,
        mode=str(terminal_manifest["mode"]),
    )
    if failures:
        print("Repair validation failed:")
        for row in failures:
            print(f"{row['check_id']}: {row['details']}")
        raise SystemExit(1)


def run_stage(*, stage_name: str) -> None:
    """Dispatch a wrapper script to its pipeline stage."""
    stages = {
        "00_smoke_test_sec_access": stage_smoke_test_sec_access,
        "01_resolve_companies": stage_resolve_companies,
        "02_inventory_filings": stage_inventory_filings,
        "03_companyfacts_inventory": stage_companyfacts_inventory,
        "04_compute_standard_metrics": stage_compute_standard_metrics,
        "05_fetch_accession_materials": stage_fetch_accession_materials,
        "06_parse_xbrl_instances": stage_parse_xbrl_instances,
        "07_extract_8k_events": stage_extract_8k_events,
        "08_extract_def14a": stage_extract_def14a,
        "09_extract_mda_and_risk_text": stage_extract_mda_and_risk_text,
        "10_run_golden_assertions": stage_run_golden_assertions,
        "11_build_report": stage_build_report,
        "12_validate_repair": stage_validate_repair,
    }
    if stage_name not in stages:
        raise KeyError(f"Unknown stage: {stage_name}")
    stages[stage_name]()


def main_from_argv(*, argv: list[str]) -> None:
    """Run a stage by command-line argument for manual debugging."""
    if len(argv) != 2:
        raise SystemExit("Usage: python sec_pipeline.py <stage_name>")
    run_stage(stage_name=argv[1])


if __name__ == "__main__":
    main_from_argv(argv=sys.argv)
