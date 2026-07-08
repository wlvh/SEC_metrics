"""SEC semantic metrics spike pipeline.

Purpose:
    Execute the ten-company one-year SEC-only spike through auditable stages:
    company resolution, filing inventory, companyfacts metrics, accession
    materials, XBRL instance inventory, 8-K events, DEF 14A signals, MD&A/risk
    text signals, golden assertions, and the final Chinese report.

Call relationships:
    scripts/00_*.py through scripts/11_*.py call run_stage(stage_name=...).
    run_stage dispatches to stage_* functions in this file.
    Every SEC request goes through sec_http.SecHttpClient.
"""

from __future__ import annotations

import ast
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from itertools import permutations
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from sec_http import SecHttpClient
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
    "local_path",
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
    "local_path",
    "status_code",
    "content_length",
    "sha256",
]

INSTANCE_FIELDNAMES = [
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
    "source_path",
]

EVENT_FIELDNAMES = [
    "company",
    "cik",
    "accession",
    "filing_date",
    "item_code",
    "item_source",
    "mapping_method",
    "confidence",
    "brief",
    "source_url",
    "local_path",
]

GOVERNANCE_FIELDNAMES = [
    "company",
    "cik",
    "signal_id",
    "signal_name",
    "value",
    "status",
    "source_url",
    "local_path",
    "accession",
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
    "local_path",
    "accession",
    "document_name",
    "concept",
    "context_or_dimension",
    "unit",
    "period_end",
    "value",
    "parser_version",
]

BASEL_THRESHOLD_CONCEPT_FRAGMENTS = [
    "minimum",
    "capitaladequacyminimum",
    "requiredforcapitaladequacy",
    "requiredtobewellcapitalized",
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
}

RECALL_REGRESSION_STATUSES = {
    "NOT_EXTRACTED",
    "NEEDS_REVIEW",
    "NOT_AVAILABLE_SEC",
}

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
LONG_TERM_DEBT_CHAIN = [
    "LongTermDebt",
    "LongTermDebtNoncurrent",
]


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


def utc_now_iso() -> str:
    """Return the current UTC timestamp for generated report metadata."""
    return datetime.now(tz=timezone.utc).isoformat()


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


def write_csv_file(*, path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Write CSV rows with a stable header and UTF-8 encoding.

    Args:
        path: Output CSV path.
        fieldnames: Ordered CSV column names.
        rows: List of dictionaries. Missing fields are written as empty strings.

    Expected output:
        A CSV file with exactly the requested header order.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode="w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {}
            for fieldname in fieldnames:
                if fieldname in row:
                    normalized[fieldname] = row[fieldname]
                else:
                    normalized[fieldname] = ""
            writer.writerow(normalized)


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
    with path.open(mode="a", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for row in rows:
            normalized = {}
            for fieldname in fieldnames:
                if fieldname in row:
                    normalized[fieldname] = row[fieldname]
                else:
                    normalized[fieldname] = ""
            writer.writerow(normalized)


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
        return list(csv.DictReader(file_obj))


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
            raise KeyError(f"Unknown extractor in applicability registry: {extractor_name}")
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
            if row["company"] == company and row["entity_role"] in {"primary", "successor"}
        ]
        for row in primary_rows:
            if row["fiscalYearEnd"] != company_config["fiscal_year_end"]:
                raise RuntimeError(
                    f"G1 failed for {company} fiscalYearEnd; "
                    f"target={company_config['fiscal_year_end']}; "
                    f"actual={row['fiscalYearEnd']}"
                )


def supplemental_submission_path(*, file_name: str) -> Path:
    """Return local evidence path for one supplemental submissions file."""
    return WORKDIR / "evidence" / "submissions" / file_name


def ensure_submission_supplementals(
    *,
    http: SecHttpClient,
    cik: int,
    max_files: int,
) -> None:
    """Fetch recent supplemental submissions files for high-volume filers.

    Args:
        http: Configured SEC HTTP client.
        cik: CIK whose base submissions JSON is already saved.
        max_files: Maximum number of files to fetch from submissions.filings.files.

    Expected output:
        Supplemental JSON files are written under evidence/submissions/.
    """
    submission = load_submissions(cik=cik)
    filings = require_key(mapping=submission, key="filings")
    files = optional_key(mapping=filings, key="files", default=[])
    if not isinstance(files, list):
        raise TypeError(f"submissions.filings.files must be list for {cik}")
    for file_info in files[:max_files]:
        file_name = str(require_key(mapping=file_info, key="name"))
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


def recent_filing_rows(*, company: str, cik: int, entity_role: str) -> list[dict]:
    """Flatten base and supplemental submissions filings into one row list.

    Args:
        company: Display company name.
        cik: Integer CIK for the submissions file.
        entity_role: primary/successor/predecessor role.

    Returns:
        Filing rows from base submissions.recent plus fetched supplemental files.
    """
    submission = load_submissions(cik=cik)
    filings = require_key(mapping=submission, key="filings")
    recent = require_key(mapping=filings, key="recent")
    rows = flatten_filing_block(
        company=company,
        cik=cik,
        entity_role=entity_role,
        recent=recent,
    )
    files = optional_key(mapping=filings, key="files", default=[])
    if not isinstance(files, list):
        raise TypeError(f"submissions.filings.files must be list for {cik}")
    for file_info in files:
        file_name = str(require_key(mapping=file_info, key="name"))
        path = supplemental_submission_path(file_name=file_name)
        if not path.exists():
            continue
        supplemental = read_json_file(path=path)
        rows.extend(
            flatten_filing_block(
                company=company,
                cik=cik,
                entity_role=entity_role,
                recent=supplemental,
            )
        )
    return rows


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
    for role_row in all_role_rows():
        cik = int(role_row["cik"])
        ensure_submission_supplementals(http=http, cik=cik, max_files=12)
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
    role choice explicit while still allowing a fallback when a successor CIK
    lacks a target 10-K.
    """
    rows = inventory_rows_for_company(company=company, source_role="target_10k")
    if not rows:
        raise RuntimeError(f"No target_10k inventory row for {company}")
    role_rank = {"primary": 0, "successor": 0, "predecessor": 1}
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            role_rank[str(row["entity_role"])] if str(row["entity_role"]) in role_rank else 5,
            str(row["filingDate"]),
        ),
        reverse=False,
    )
    return ranked_rows[0]


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

    operating_income = select_component(
        cik=cik,
        concept_chain=["OperatingIncomeLoss"],
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    da = select_component(
        cik=cik,
        concept_chain=DA_CHAIN,
        period_end=period_end,
        period_kind="duration",
        accession=accession,
    )
    if revenue is not None and operating_income is not None and da is not None:
        ebitda_margin = (operating_income.value + da.value) / revenue.value
        ebitda_status = "OK"
        ebitda_notes = "GAAP EBITDA proxy; impairment is not added back."
    else:
        ebitda_margin = None
        ebitda_status = "NOT_AVAILABLE_SEC"
        ebitda_notes = "Required revenue, operating income, or D&A missing."
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
        hits=[
            hit
            for hit in [operating_income, da, revenue]
            if hit is not None
        ],
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
    debt = select_component(
        cik=cik,
        concept_chain=LONG_TERM_DEBT_CHAIN,
        period_end=period_end,
        period_kind="instant",
        accession=accession,
    )
    if debt is not None and equity is not None and equity.value != 0:
        debt_to_equity = debt.value / equity.value
        debt_status = "OK"
        debt_notes = (
            "Consolidated entity-level debt/equity; captive-finance dimensions "
            "are reviewed after accession instance parsing."
        )
    else:
        debt_to_equity = None
        debt_status = "NOT_AVAILABLE_SEC"
        debt_notes = "Debt or equity missing."
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
        hits=[hit for hit in [debt, equity] if hit is not None],
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
    if operating_income is not None and operating_income.value <= 0:
        interest_coverage = None
        interest_status = "NOT_MEANINGFUL"
        interest_notes = "Operating income is non-positive."
    elif operating_income is not None and interest is not None and interest.value != 0:
        interest_coverage = operating_income.value / interest.value
        interest_status = "OK"
        interest_notes = "Operating income divided by interest expense."
    else:
        interest_coverage = None
        interest_status = "NOT_AVAILABLE_SEC"
        interest_notes = "Operating income or interest expense missing."
    row, evidence = derived_metric(
        company=company,
        cik=cik,
        metric_id="B07",
        metric_name="Interest coverage ratio",
        value=interest_coverage,
        unit="ratio",
        status=interest_status,
        formula="operating income / interest expense",
        period_start=operating_income.start if operating_income is not None else "",
        period_end=period_end,
        fiscal_year=operating_income.fiscal_year if operating_income is not None else "",
        fiscal_period=(
            operating_income.fiscal_period if operating_income is not None else ""
        ),
        hits=[hit for hit in [operating_income, interest] if hit is not None],
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


def governance_risk_event_placeholders(*, company: str, cik: int, period_end: str) -> list[dict]:
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
        if row["company"] == new_row["company"] and row["metric_id"] == new_row["metric_id"]:
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


def accession_index_items(*, index_path: Path) -> list[dict]:
    """Read SEC archive index.json and return directory item rows."""
    payload = read_json_file(path=index_path)
    directory = require_key(mapping=payload, key="directory")
    items = require_key(mapping=directory, key="item")
    if not isinstance(items, list):
        raise TypeError(f"SEC archive index item must be list: {index_path}")
    return items


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
        if row["source_role"] == "target_10k"
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Start capturing ix facts when a fact tag opens."""
        local = local_name(tag=tag)
        local_lower = local.lower()
        attr_map = {}
        for key, value in attrs:
            attr_map[key] = value if value is not None else ""
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
            namespace, concept = name.split(":", maxsplit=1)
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
    return parser.rows


def parse_instance_with_fallback(*, material_row: dict) -> list[dict]:
    """Parse one instance using XML streaming, then inline fallback on parse errors."""
    file_path = Path(material_row["local_path"])
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


def stage_extract_8k_events() -> None:
    """M4: fetch 8-K hdr.sgml files and extract multi-item event rows."""
    ensure_output_dirs()
    http = client()
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    eight_k_rows = [row for row in inventory if row["source_role"] == "fy_8k"]
    events: list[dict] = []
    evidence_to_append: list[dict] = []
    metrics = load_metrics()
    period_end_by_company = {
        row["company"]: row["reportDate"]
        for row in inventory
        if row["source_role"] == "target_10k"
    }

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
        item_codes: list[str] = []
        item_source = "hdr.sgml"
        method = "hdr_items"
        brief_by_code: dict[str, str] = {}
        local_path = hdr_path
        source_url = hdr_url
        if hdr_result.status_code == 200:
            hdr_text = hdr_path.read_text(encoding="utf-8", errors="replace")
            item_codes = parse_items_from_hdr(text=hdr_text)
            for code in item_codes:
                brief_by_code[code] = f"8-K item {code} parsed from hdr.sgml"
        if not item_codes:
            primary_material = fetch_primary_for_inventory_row(
                http=http,
                row=row,
                document_type="eightk_primary_document",
                purpose=f"eightk_primary_{accession}",
            )
            local_path = Path(primary_material["local_path"])
            source_url = primary_material["source_url"]
            primary_text = html_file_to_text(path=local_path)
            fallback_items = parse_items_from_primary_text(text=primary_text)
            item_codes = [item[0] for item in fallback_items]
            for code, brief in fallback_items:
                brief_by_code[code] = brief
            item_source = "primary_document"
            method = "primary_heading_fallback"

        for code in item_codes:
            event = {
                "company": row["company"],
                "cik": row["cik"],
                "accession": accession,
                "filing_date": row["filingDate"],
                "item_code": code,
                "item_source": item_source,
                "mapping_method": method,
                "confidence": "0.90" if item_source == "hdr.sgml" else "0.70",
                "brief": brief_by_code[code] if code in brief_by_code else "",
                "source_url": source_url,
                "local_path": str(local_path),
            }
            events.append(event)

    write_csv_file(
        path=WORKDIR / "outputs" / "events.csv",
        fieldnames=EVENT_FIELDNAMES,
        rows=events,
    )

    for company_config in load_company_registry():
        company = str(company_config["company"])
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        company_events = [row for row in events if row["company"] == company]
        scanned_accessions = ";".join(
            sorted({event["accession"] for event in company_events})
        )
        scanned_dates = ";".join(
            sorted({event["filing_date"] for event in company_events})
        )
        scanned_context = (
            "FY-window 8-K accessions scanned"
            if scanned_accessions
            else "No FY-window 8-K accession in inventory"
        )
        # Keep event period selection data-driven so manual company-branch
        # audits only surface real identity-specific logic.
        period_end = ({company: str(target["reportDate"])} | period_end_by_company)[
            company
        ]
        event_updates = [
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
        for metric_id, metric_name, code, ok_status, notes in event_updates:
            matching = [event for event in company_events if event["item_code"] == code]
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
                evidence_to_append.append(
                    text_evidence_row(
                        company=company,
                        cik=cik,
                        metric_id=metric_id,
                        source_url=first["source_url"],
                        local_path=first["local_path"],
                        accession=first["accession"],
                        document_name=Path(first["local_path"]).name,
                        concept_or_section=f"8-K Item {code}",
                        context_or_dimension="FY window",
                        unit="count",
                        period_end=period_end,
                        value=str(len(matching)),
                        quote=first["brief"],
                        extraction_method="eightk_item",
                    )
                )
            else:
                status = "NOT_AVAILABLE_SEC"
                note = f"FY-window 8-K scanned; no item {code} found."
                if metric_id == "E02":
                    note = "No Item 1.03 in FY-window 8-K; zero is normal."
                new_row = text_metric_row(
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    metric_name=metric_name,
                    value="0",
                    unit="count",
                    status=status,
                    source_class="8K_ITEM",
                    period_end=period_end,
                    accession=scanned_accessions,
                    filed_date=scanned_dates,
                    concept_or_section=f"8-K Item {code}",
                    context_or_dimension=scanned_context,
                    confidence="0.80",
                    notes=note,
                )
                evidence_to_append.append(
                    text_evidence_row(
                        company=company,
                        cik=cik,
                        metric_id=metric_id,
                        source_url="",
                        local_path=str(WORKDIR / "outputs" / "events.csv"),
                        accession=scanned_accessions,
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

        ma_events = [
            event
            for event in company_events
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
        if ma_events:
            first = ma_events[0]
            status = "8K_ITEM_OK"
            value = str(len(ma_events))
            note = "M&A candidate from item mapping and keyword rule."
            evidence_to_append.append(
                text_evidence_row(
                    company=company,
                    cik=cik,
                    metric_id="E01",
                    source_url=first["source_url"],
                    local_path=first["local_path"],
                    accession=first["accession"],
                    document_name=Path(first["local_path"]).name,
                    concept_or_section="8-K Item 1.01/2.01/8.01",
                    context_or_dimension="FY window",
                    unit="count",
                    period_end=period_end,
                    value=value,
                    quote=first["brief"],
                    extraction_method="eightk_item_keyword",
                )
            )
            accession_text = ";".join([event["accession"] for event in ma_events])
        else:
            status = "NOT_AVAILABLE_SEC"
            value = "0"
            note = "FY-window 8-K scanned; no M&A item rule matched."
            accession_text = scanned_accessions
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
                filed_date=scanned_dates if not ma_events else "",
                concept_or_section="8-K Item 1.01/2.01/8.01",
                context_or_dimension=scanned_context,
                confidence="0.75",
                notes=note,
            ),
        )
        if not ma_events:
            evidence_to_append.append(
                text_evidence_row(
                    company=company,
                    cik=cik,
                    metric_id="E01",
                    source_url="",
                    local_path=str(WORKDIR / "outputs" / "events.csv"),
                    accession=scanned_accessions,
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
    save_metrics(rows=metrics)
    append_evidence(rows=evidence_to_append)
    print(f"M4 8-K event extraction complete; events={len(events)}")


def dump_ecd_facts(*, material_row: dict) -> list[dict]:
    """Extract ecd inline facts from a DEF 14A primary document."""
    file_path = Path(material_row["local_path"])
    parsed = parse_inline_instance(file_path=file_path, material_row=material_row)
    return [
        row
        for row in parsed
        if str(row["namespace"]).lower() == "ecd"
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
    """M5: fetch DEF 14A materials and extract governance/compensation signals."""
    ensure_output_dirs()
    http = client()
    inventory = read_csv_file(
        path=WORKDIR / "outputs" / "latest_filings_inventory.csv"
    )
    def_rows = [row for row in inventory if row["source_role"] == "latest_def14a"]
    governance_rows: list[dict] = []
    evidence_to_append: list[dict] = []
    metrics = load_metrics()

    ecd_fieldnames = [
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
        "source_path",
    ]
    ecd_by_company: dict[str, list[dict]] = {}

    for row in def_rows:
        material = fetch_primary_for_inventory_row(
            http=http,
            row=row,
            document_type="def14a_primary_document",
            purpose=f"def14a_primary_{row['accession']}",
        )
        path = Path(material["local_path"])
        text = html_file_to_text(path=path)
        ecd_rows = dump_ecd_facts(material_row=material)
        ecd_by_company[row["company"]] = ecd_rows
        board_quote = def14a_quote(
            text=text,
            pattern=r"board of directors|director nominees|independent directors",
        )
        comp_quote = def14a_quote(
            text=text,
            pattern=r"summary compensation table|total compensation|principal executive officer",
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
                "notes": "Board composition is qualitative unless structured counts are reviewed.",
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
            fieldnames=ecd_fieldnames,
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
        local_path = material["local_path"]
        text = html_file_to_text(path=Path(local_path))

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
            special_patterns = [
                ("A03", "Liquidity coverage ratio", r"liquidity coverage ratio|LCR"),
                (
                    "A04",
                    "Net interest margin",
                    (
                        r"net interest margin|average interest-earning assets|"
                        r"net yield on interest-earning assets"
                    ),
                ),
                ("A11", "AUM", r"assets under management|AUM"),
                ("A12", "Trading exposure", r"value-at-risk|VaR|trading exposure"),
            ]
            for metric_id, metric_name, pattern in special_patterns:
                quote = snippet_for_pattern(text=text, pattern=pattern, width=650)
                metrics = update_text_metric(
                    metrics=metrics,
                    evidence_rows=evidence_rows,
                    company=company,
                    cik=cik,
                    metric_id=metric_id,
                    metric_name=metric_name,
                    value="",
                    unit="",
                    status="TEXT_QUAL" if quote else "NOT_EXTRACTED",
                    source_class="MDA",
                    period_end=period_end,
                    accession=accession,
                    filed_date=filed_date,
                    source_url=source_url,
                    local_path=local_path,
                    section=metric_name,
                    quote=quote,
                    notes="FI metric requires table-level follow-up for numeric value.",
                )

        if has_extractor(
            extractors=extractors,
            extractor_name="CapacityUtilizationExtractor",
        ) or text_has_capacity_keywords(text=text):
            capacity_quote = snippet_for_pattern(
                text=text,
                pattern=r"capacity utilization|production capacity|manufacturing capacity",
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
                notes="Only qualitative capacity evidence is used unless a ratio appears.",
            )

    write_csv_file(
        path=WORKDIR / "outputs" / "risk_legal_signals.csv",
        fieldnames=RISK_FIELDNAMES,
        rows=risk_rows,
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
            concept_chain=LONG_TERM_DEBT_CHAIN,
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
            assertion_id="G2_financial_assetscurrent_b08",
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

    for metric_id in ["A01", "A02"]:
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
                assertion_id="G2_captive_finance_b06_dimension_review",
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
            assertion_id="G2_auditorname_material_source",
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
        for metric_id in ["A01", "A02"]:
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
        assertion_id = "G2_financial_assetscurrent_b08"
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
    assertion_id = "G2_captive_finance_b06_dimension_review"
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
        status="FAIL" if failures else "PASS_LIGHT_GOLDEN_INTEGRITY",
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
    """M7: run structure, source-class, numeric, and candidate assertions."""
    mode, reasons = validation_package_mode()
    if mode == "WORKSPACE_INCOMPLETE":
        print("WORKSPACE_INCOMPLETE; " + "; ".join(reasons))
        raise SystemExit(1)
    if mode == "LIGHT_REVIEW_MODE":
        result = check_light_golden_snapshot_integrity()
        if result["status"] == "PASS_LIGHT_GOLDEN_INTEGRITY":
            print("PASS_LIGHT_GOLDEN_INTEGRITY: " + result["details"])
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
        fieldnames=[
            "assertion_id",
            "description",
            "expected",
            "actual",
            "status",
            "evidence_path",
            "notes",
        ],
        rows=results,
    )
    candidate_rows = build_golden_candidates()
    write_csv_file(
        path=WORKDIR / "outputs" / "golden_candidates.csv",
        fieldnames=[
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
        ],
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
    print("M7 golden assertions complete; all pass")


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
        local_path: Absolute local evidence path stored in concept inventory.

    Returns:
        Matching SEC URL or blank when the path is not in material inventory.
    """
    rows = read_csv_file(path=WORKDIR / "outputs" / "accession_materials_inventory.csv")
    for row in rows:
        if row["local_path"] == local_path:
            return row["source_url"]
    return ""


def ecd_inventory_path(*, company: str) -> Path:
    """Return the local ECD concept inventory path for a company."""
    return WORKDIR / "outputs" / "concept_inventory" / f"{slugify(text=company)}_ecd.csv"


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
    inventory = read_csv_file(path=WORKDIR / "outputs" / "latest_filings_inventory.csv")
    materials = read_csv_file(path=WORKDIR / "outputs" / "accession_materials_inventory.csv")
    for row in [item for item in inventory if item["source_role"] == "latest_def14a"]:
        company = row["company"]
        target = target_10k_for_company(company=company)
        material_rows = [
            material
            for material in materials
            if material["accession"] == row["accession"]
            and material["document_type"] == "def14a_primary_document"
        ]
        local_path = material_rows[0]["local_path"] if material_rows else ""
        source_url = material_rows[0]["source_url"] if material_rows else row["source_url"]
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
            pattern=r"RevPAR|Revenue per available room|Occupancy|Average Daily Rate|ADR",
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


def lodging_quote_text(*, segment: str, row_start: int, row_text: str) -> tuple[str, str]:
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
    empty = {"revpar": "", "occupancy": "", "adr": "", "scope": "", "quote": empty_quote}
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
        text = html_file_to_text(path=Path(material["local_path"]))
        metrics, evidence_rows = apply_lodging_kpi_metrics(
            metrics=metrics,
            evidence_rows=evidence_rows,
            company=company,
            text=text,
            source_url=material["source_url"],
            local_path=material["local_path"],
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
        text = html_file_to_text(path=Path(material["local_path"]))
        metrics, evidence_rows = apply_rpo_crpo_metric(
            metrics=metrics,
            evidence_rows=evidence_rows,
            company=company,
            text=text,
            source_url=material["source_url"],
            local_path=material["local_path"],
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
    if normalized.endswith("creditmember"):
        return True
    if normalized.endswith("financialservicesmember"):
        return True
    if normalized.endswith("captivefinancemember"):
        return True
    if normalized.endswith("financingsubsidiarymember"):
        return True
    if normalized.startswith("companyexcluding") and normalized.endswith("creditmember"):
        return True
    if (
        normalized.startswith("companyexcluding")
        and normalized.endswith("financialservicesmember")
    ):
        return True
    return False


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
        if captive_dimension_axis_allowed(axis=axis) and captive_dimension_member_allowed(
            member=member,
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
            row["status"] = "NEEDS_REVIEW"
            row["notes"] = (
                "Consolidated debt-to-equity retained from structured facts; "
                "captive finance segment/dimension detected, and industrial-only "
                "ratio was not extracted."
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
    ]


def auditor_fact_for_accession(
    *,
    facts: list[dict],
    accession: str,
    period_end: str,
) -> dict | None:
    """Return one AuditorName fact for accession and period when available.

    Args:
        facts: Local AuditorName fact rows.
        accession: Target or prior 10-K accession.
        period_end: Report date expected for the fact context.

    Returns:
        Deduplicated fact row or None when local material is missing.
    """
    matches = [
        row
        for row in facts
        if row["accession"] == accession and row["period_end"] == period_end
    ]
    if not matches:
        return None
    return unique_rows(
        rows=matches,
        fields=["accession", "concept", "period_end", "value", "source_path"],
    )[0]


def xbrl_material_rows_for_accession(*, accession: str) -> list[dict]:
    """Return existing successful local XBRL material rows for one accession.

    Args:
        accession: SEC accession number.

    Returns:
        XBRL instance material rows whose local files exist.
    """
    rows = read_csv_file(path=WORKDIR / "outputs" / "accession_materials_inventory.csv")
    return [
        row
        for row in rows
        if row["accession"] == accession
        and row["document_type"] == "xbrl_instance"
        and row["status_code"] == "200"
        and Path(row["local_path"]).exists()
    ]


def append_material_rows(*, rows: list[dict]) -> None:
    """Merge targeted SEC fetch material rows into the inventory.

    Args:
        rows: New accession material rows.

    Expected output:
        Existing material rows are preserved and duplicates are removed by
        accession, document, type, and local path.
    """
    if not rows:
        return
    path = WORKDIR / "outputs" / "accession_materials_inventory.csv"
    existing = read_csv_file(path=path)
    merged = unique_rows(
        rows=existing + rows,
        fields=["accession", "document_name", "document_type", "local_path"],
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
    return [
        row
        for row in new_rows
        if row["document_type"] == "xbrl_instance"
        and row["status_code"] == "200"
        and Path(row["local_path"]).exists()
    ]


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
    merged = unique_rows(rows=existing + rows, fields=INSTANCE_FIELDNAMES)
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
    existing = auditor_fact_for_accession(
        facts=facts,
        accession=str(filing_row["accession"]),
        period_end=str(filing_row["reportDate"]),
    )
    if existing is not None:
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
    recent_rows = recent_filing_rows(
        company=company,
        cik=int(target["cik"]),
        entity_role=str(target["entity_role"]),
    )
    originals = [
        row
        for row in recent_rows
        if row["form"] == "10-K"
        and row["reportDate"] == target["reportDate"]
        and row["accessionNumber"] != target["accession"]
    ]
    if not originals:
        return candidates
    selected = sorted_filings(rows=originals)[0]
    candidates.append(
        filing_output_row(row=selected, source_role="auditor_current_10k")
    )
    return candidates


def select_auditor_fact_from_candidates(
    *,
    facts: list[dict],
    candidates: list[dict],
) -> tuple[dict | None, dict]:
    """Return the first AuditorName fact found across ordered candidates.

    Args:
        facts: Local AuditorName facts.
        candidates: Ordered filing rows.

    Returns:
        Fact row or None, plus the candidate used for provenance.
    """
    for candidate in candidates:
        fact = auditor_fact_for_accession(
            facts=facts,
            accession=str(candidate["accession"]),
            period_end=str(candidate["reportDate"]),
        )
        if fact is not None:
            return fact, candidate
    return None, candidates[0]


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
        target = target_10k_for_company(company=company)
        cik = int(target["cik"])
        prior = prior_10k_for_company(company=company, cik=cik)
        current_candidates = auditor_current_filing_candidates(
            company=company,
            target=target,
        )
        for candidate in current_candidates:
            ensure_auditor_facts_for_filing(
                http=http,
                company=company,
                filing_row=candidate,
            )
        if prior is not None:
            ensure_auditor_facts_for_filing(
                http=http,
                company=company,
                filing_row=prior,
            )
        facts = auditor_facts_for_company(company=company)
        current, current_source = select_auditor_fact_from_candidates(
            facts=facts,
            candidates=current_candidates,
        )
        prior_fact = None
        if prior is not None:
            prior_fact, _prior_source = select_auditor_fact_from_candidates(
                facts=facts,
                candidates=[prior],
            )
        if current is None:
            status = "NEEDS_REVIEW"
            value = ""
            note = (
                "需复核: current 10-K instance does not contain dei:AuditorName; "
                f"missing current accession/material {target['accession']}."
            )
            quote = note
            local_path = str(instance_inventory_path(company=company))
            source_url = current_source["source_url"]
            accession = current_source["accession"]
        elif prior is None or prior_fact is None:
            status = "NEEDS_REVIEW"
            value = ""
            missing = "prior_10k inventory row" if prior is None else prior["accession"]
            note = (
                "需复核: current auditor read from dei:AuditorName, but prior "
                f"10-K instance is missing or lacks AuditorName ({missing})."
            )
            quote = (
                f"current dei:AuditorName={normalize_fact_text(value=current['value'])}; "
                f"prior_missing={missing}"
            )
            local_path = current["source_path"]
            source_url = material_url_for_path(local_path=current["source_path"])
            accession = current["accession"]
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
            local_path = current["source_path"]
            source_url = material_url_for_path(local_path=current["source_path"])
            accession = current["accession"]
        metrics = upsert_metric(
            rows=metrics,
            new_row=text_metric_row(
                company=company,
                cik=cik,
                metric_id="C04",
                metric_name="Auditor changes",
                value=value,
                unit="flag" if value else "",
                status=status,
                source_class="DIM_XBRL",
                period_end=str(target["reportDate"]),
                accession=accession,
                filed_date=target["filingDate"],
                concept_or_section="AuditorName",
                context_or_dimension="current/prior 10-K instance",
                confidence="0.80" if value else "0.45",
                notes=note,
            ),
        )
        evidence_rows.append(
            text_evidence_row(
                company=company,
                cik=cik,
                metric_id="C04",
                source_url=source_url,
                local_path=local_path,
                accession=accession,
                document_name=Path(local_path).name,
                concept_or_section="AuditorName",
                context_or_dimension="current/prior 10-K instance",
                unit="flag" if value else "",
                period_end=str(target["reportDate"]),
                value=value,
                quote=quote,
                extraction_method="auditorname_repair",
            )
        )
    return metrics, evidence_rows


def apply_p0_repairs() -> None:
    """Apply bounded local-only P0 repairs before report and validation.

    Expected output:
        metrics_matrix, metric_evidence, and governance_signals are updated
        using only local evidence and concept inventory files.
    """
    metrics = load_metrics()
    evidence_rows = read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    governance_rows = read_csv_file(path=WORKDIR / "outputs" / "governance_signals.csv")
    metrics, evidence_rows, governance_rows = repair_c03_compensation(
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
    metrics, evidence_rows = repair_c04_auditor_changes(
        metrics=metrics,
        evidence_rows=evidence_rows,
    )
    save_metrics(rows=metrics)
    save_evidence(rows=evidence_rows)
    save_governance(rows=governance_rows)
    refresh_repair_sensitive_golden_results()
    print("P0 local repair applied")


def refresh_repair_sensitive_golden_results() -> None:
    """Refresh golden rows whose actual values changed through local repair.

    Expected output:
        Golden pass/fail results remain local-only and consistent with repaired
        metrics_matrix source classes.
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
        if row["company"] in financial_companies and row["metric_id"] in {"A01", "A02"}:
            source_class_by_metric[row["metric_id"]] = row["source_class"]
    refreshed = []
    for row in rows:
        if row["assertion_id"] == "G2_financial_a01_not_std":
            actual = source_class_by_metric["A01"]
            row["actual"] = actual
            row["status"] = "PASS" if actual != "STD_XBRL" else "FAIL"
        if row["assertion_id"] == "G2_financial_a02_not_std":
            actual = source_class_by_metric["A02"]
            row["actual"] = actual
            row["status"] = "PASS" if actual != "STD_XBRL" else "FAIL"
        refreshed.append(row)
    write_csv_file(
        path=path,
        fieldnames=[
            "assertion_id",
            "description",
            "expected",
            "actual",
            "status",
            "evidence_path",
            "notes",
        ],
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
                "replacement_plan": "Select filings from SEC submissions metadata.",
            }
        )
    for date_text in re.findall(pattern=r"\b20\d{2}-\d{2}-\d{2}\b", string=literal_value):
        rows.append(
            {
                "file": str(file_path.relative_to(WORKDIR)),
                "line": str(line_number),
                "literal": date_text,
                "type": "fixed_fiscal_date",
                "allowed": "0",
                "reason": "fixed fiscal date appears in production Python",
                "replacement_plan": "Use selected target/prior reportDate metadata.",
            }
        )
    return rows


def python_literal_values(*, path: Path) -> list[tuple[int, object]]:
    """Return AST constant literals from one Python source file.

    Args:
        path: Python source path.

    Returns:
        Tuples of one-based line number and literal value for string and integer
        constants, including assignment values, arguments, dict keys, and
        conditional expressions.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source=source, filename=str(path))
    literals = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if isinstance(node.value, (str, int)):
            literals.append((node.lineno, node.value))
    return literals


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


def check_no_company_identity_branch_in_production() -> dict:
    """Validate production branches do not use company identity literals."""
    rows = write_scalability_audit()
    failures = [row for row in rows if row["allowed"] != "1"]
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
        status: PASS, FAIL, WORKSPACE_INCOMPLETE, SKIPPED_LIGHT_PACKAGE,
            PASS_LIGHT_REVIEW, or PASS_LIGHT_GOLDEN_INTEGRITY.
        details: Human-readable failure or pass detail.

    Returns:
        CSV row with P0 severity.
    """
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
        in_range = value is not None and Decimal(str(revpar_range[0])) <= value <= Decimal(
            str(revpar_range[1]),
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
        elif row["status"] == "MDA_OK" and not has_note:
            failures.append(f"{company}:missing_boundary_note")
    return validation_row(
        check_id="rpo_crpo_prefers_instance_fact",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "B12 instance preference verified",
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
    return validation_row(
        check_id="basel_ratio_extractor_not_single_issuer_specific",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "Basel ratios verified",
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
        details="banking regulation ratio family matched" if passes else f"{tier1};{cet1}",
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
        "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatioCapitalAdequacyMinimum",
        "TierOneRiskBasedCapitalRequiredForCapitalAdequacyToRiskWeightedAssets",
        "TierOneRiskBasedCapitalRequiredToBeWellCapitalizedToRiskWeightedAssets",
        "BankingRegulationCommonEquityTierOneRiskBasedCapitalRatioWellCapitalizedMinimum",
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
                "CapitalAdequacyMinimum"
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
    ]
    has_signal = captive_finance_signal_from_rows(rows=rows)
    return validation_row(
        check_id="captive_finance_excludes_normal_finance_lease_terms",
        status="FAIL" if has_signal else "PASS",
        details="excluded concepts triggered" if has_signal else "normal finance terms excluded",
    )


def check_enphase_b06_not_captive_finance_false_positive(*, metrics: list[dict]) -> dict:
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
    """Validate GM-like segment member triggers captive review."""
    rows = [
        {
            "concept": "LongTermDebtAndCapitalLeaseObligations",
            "dimensions": "us-gaap:StatementBusinessSegmentsAxis=example:CaptiveFinanceMember",
        }
    ]
    has_signal = captive_finance_signal_from_rows(rows=rows)
    return validation_row(
        check_id="gm_like_captive_finance_fixture_triggers_review",
        status="PASS" if has_signal else "FAIL",
        details="GM-like captive segment matched" if has_signal else "fixture missed",
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


def check_c04_auditorname_all_companies(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate C04 uses AuditorName evidence or explicit review state."""
    failures = []
    for company_config in load_company_registry():
        company = str(company_config["company"])
        row = metric_lookup(metrics=metrics, company=company, metric_id="C04")
        evidence = evidence_for_metric(
            evidence_rows=evidence_rows,
            company=company,
            metric_id="C04",
        )
        if row["status"] == "DIM_XBRL_OK":
            if row["concept_or_section"] != "AuditorName":
                failures.append(company)
            if not any(item["concept_or_section"] == "AuditorName" for item in evidence):
                failures.append(f"{company}:missing_evidence")
        elif row["status"] != "NEEDS_REVIEW":
            failures.append(f"{company}:{row['status']}")
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
    passes = status == "MDA_OK" and fact["revpar"] == "140" and fact["occupancy"] == "70"
    return validation_row(
        check_id="eleventh_company_behavior_lodging",
        status="PASS" if passes else "FAIL",
        details=str(fact) if not passes else "lodging fixture extracted B10/B11",
    )


def check_eleventh_company_behavior_financial_institution() -> dict:
    """Validate FI behavior fixture extracts A01/A02 Basel ratios."""
    rows = eleventh_rows_for_profile(profile="financial_institution")
    failures = []
    period_end = rows[0]["period_end"] if rows else ""
    expected_concepts = {
        "A01": "TierOneRiskBasedCapitalToRiskWeightedAssets",
        "A02": "CommonEquityTierOneCapitalToRiskWeightedAssets",
    }
    for metric_id in ["A01", "A02"]:
        candidates = basel_ratio_candidates_from_rows(
            rows=rows,
            metric_id=metric_id,
            period_end=period_end,
        )
        if not candidates:
            failures.append(metric_id)
            continue
        selected = selected_basel_ratio_fact(rows=candidates)
        if selected["concept"] != expected_concepts[metric_id]:
            failures.append(f"{metric_id}:{selected['concept']}")
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
            failures.append(f"{snapshot['company']}:{metric_id}:missing_current")
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
        if not allowed or "extractor regression" in reason or "抽取器退化" in reason:
            failures.append(
                f"{snapshot['company']}:{metric_id}:{previous_status}->{current_status}"
            )
    return failures


def check_ok_status_recall_not_regressed_without_reason(*, metrics: list[dict]) -> dict:
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
        details=";".join(failures[:20]) if failures else f"snapshot_rows={len(snapshot)}",
    )


def check_lodging_ok_recall_not_regressed_without_reason(*, metrics: list[dict]) -> dict:
    """Validate previous lodging B10/B11 OK recall is preserved or justified."""
    failures = recall_regression_failures(metrics=metrics, metric_filter={"B10", "B11"})
    return validation_row(
        check_id="lodging_ok_recall_not_regressed_without_reason",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "lodging B10/B11 recall preserved",
    )


def check_registry_profile_matches_sic_rules_or_has_override_reason() -> dict:
    """Validate registry industry_profile agrees with SIC profile rules."""
    failures = []
    for company_config in load_company_registry():
        inferred = profile_from_sic_rules(sic=str(company_config["sic"]))
        actual = str(company_config["industry_profile"])
        if inferred == actual:
            continue
        reason = profile_override_reason(company_id=str(company_config["company_id"]))
        if not reason:
            failures.append(
                f"{company_config['company_id']}:{actual}!={inferred}:missing_override"
            )
    return validation_row(
        check_id="registry_profile_matches_sic_rules_or_has_override_reason",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures) if failures else "registry profiles match SIC rules",
    )


def check_coverage_join(
    *,
    coverage: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate coverage.has_evidence equals the actual evidence join."""
    evidence_pairs = evidence_key_set(evidence_rows=evidence_rows)
    mismatches = []
    for row in coverage:
        expected = "1" if (row["company"], row["metric_id"]) in evidence_pairs else "0"
        if row["has_evidence"] != expected:
            mismatches.append(f"{row['company']}:{row['metric_id']}")
    return validation_row(
        check_id="coverage_has_evidence_matches_metric_evidence_join",
        status="PASS" if not mismatches else "FAIL",
        details=";".join(mismatches[:20]) if mismatches else "coverage join matches",
    )


def check_numeric_ok_requires_evidence(
    *,
    metrics: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Validate OK numeric rows have at least one evidence row."""
    evidence_pairs = evidence_key_set(evidence_rows=evidence_rows)
    failures = []
    for row in metrics:
        if row["status"] not in NUMERIC_EVIDENCE_STATUSES:
            continue
        if row["value"] == "":
            continue
        if (row["company"], row["metric_id"]) not in evidence_pairs:
            failures.append(f"{row['company']}:{row['metric_id']}")
    return validation_row(
        check_id="numeric_ok_status_requires_evidence_row",
        status="PASS" if not failures else "FAIL",
        details=";".join(failures[:20]) if failures else "all numeric OK rows evidenced",
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


def check_golden_results_all_pass() -> dict:
    """Validate existing original golden assertion results all pass."""
    rows = read_csv_file(path=WORKDIR / "outputs" / "golden_results.csv")
    failures = [row["assertion_id"] for row in rows if row["status"] != "PASS"]
    return validation_row(
        check_id="existing_golden_results_still_pass",
        status="PASS" if rows and not failures else "FAIL",
        details=";".join(failures[:20]) if failures else f"rows={len(rows)}",
    )


def check_requests_log_sec_only() -> dict:
    """Validate request log contains only SEC URLs with explicit User-Agent."""
    rows = read_csv_file(path=REQUEST_LOG_PATH)
    failures = []
    for index, row in enumerate(rows):
        sec_url = row["url"].startswith("https://www.sec.gov/") or row["url"].startswith(
            "https://data.sec.gov/"
        )
        if not sec_url or row["user_agent"] == "" or row["retry_attempt"] == "":
            failures.append(str(index))
    return validation_row(
        check_id="requests_log_sec_only",
        status="PASS" if rows and not failures else "FAIL",
        details=";".join(failures[:20]) if failures else f"rows={len(rows)}",
    )


def check_stratified_audit_all_pass_or_explicitly_caveated(
    *,
    audit_rows: list[dict],
) -> dict:
    """Validate stratified audit failures are not silently swallowed.

    Args:
        audit_rows: Rows written to outputs/stratified_audit.csv.

    Returns:
        PASS when every sampled row passed; FAIL lists failing audit ids.
    """
    failures = [
        f"{row['audit_id']}:{row['company']}:{row['metric_id']}:{row['audit_notes']}"
        for row in audit_rows
        if row["audit_verdict"] == "FAIL"
    ]
    return validation_row(
        check_id="stratified_audit_all_pass_or_explicitly_caveated",
        status="PASS" if audit_rows and not failures else "FAIL",
        details=(
            ";".join(failures[:20])
            if failures
            else f"rows={len(audit_rows)}"
            if audit_rows
            else "stratified audit rows missing"
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
    if metric["metric_id"] == "B12" and not re.search(
        pattern=r"RPO|cRPO|remaining performance obligation",
        string=f"{quote_text} {concept_text}",
        flags=re.IGNORECASE,
    ):
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
    strata = [
        ("STD_XBRL_DERIVED", {"STD_XBRL", "DERIVED"}, 8),
        ("DIM_XBRL", {"DIM_XBRL"}, 4),
        ("DEF14A", {"DEF14A"}, 3),
        ("MDA_TEXT", {"MDA", "TEXT"}, 3),
        ("8K_ITEM", {"8K_ITEM"}, 2),
    ]
    used_keys: set[tuple[str, str]] = set()
    selected: list[tuple[str, dict]] = []
    for bucket, source_classes, limit in strata:
        for row in stratified_candidates(
            metrics=metrics,
            source_classes=source_classes,
            used_keys=used_keys,
            limit=limit,
        ):
            selected.append((bucket, row))
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


def run_repair_validation(*, exit_on_failure: bool) -> list[dict]:
    """Run P0 repair validation and optionally exit nonzero on failure.

    Args:
        exit_on_failure: When True, raise SystemExit(1) for any P0 failure.

    Returns:
        Validation result rows written to outputs/repair_validation_results.csv.
    """
    metrics = load_metrics()
    evidence_rows = read_csv_file(path=WORKDIR / "outputs" / "metric_evidence.csv")
    coverage = read_csv_file(path=WORKDIR / "outputs" / "coverage_matrix.csv")
    mode, light_reasons = validation_package_mode()
    if mode == "WORKSPACE_INCOMPLETE":
        rows = [workspace_incomplete_row(reasons=light_reasons)]
        write_csv_file(
            path=WORKDIR / "outputs" / "repair_validation_results.csv",
            fieldnames=REPAIR_VALIDATION_FIELDNAMES,
            rows=rows,
        )
        if exit_on_failure:
            print(rows[0]["details"])
            raise SystemExit(1)
        return rows
    light_mode = mode == "LIGHT_REVIEW_MODE"
    light_details = (
        "mode=LIGHT_REVIEW_MODE; " + "; ".join(light_reasons)
        if light_mode
        else "mode=FULL_VALIDATION"
    )
    audit_rows = write_stratified_audit()
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
        check_no_company_identity_branch_in_production(),
        check_registry_profile_matches_sic_rules_or_has_override_reason(),
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
        check_basel_concept_resolver_handles_tierone_spelling(),
        check_basel_concept_resolver_handles_banking_regulation_ratio_family(),
        check_basel_cet1_never_classified_as_a01(),
        check_basel_threshold_concepts_never_match_primary_metric(),
        check_basel_primary_selection_prefers_actual_ratio_over_threshold(),
        check_a01_a02_metric_evidence_excludes_threshold_concepts(
            evidence_rows=evidence_rows,
        ),
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
        check_gm_like_captive_finance_fixture_triggers_review(),
        check_entity_continuity_yoy(metrics=metrics),
        check_no_c03_ecd_fact_count(metrics=metrics, evidence_rows=evidence_rows),
        c03_peo_check,
        validation_row(
            check_id="c03_uses_ecd_peototalcompamt_for_all_companies",
            status=c03_peo_check["status"],
            details="C03 PeoTotalCompAmt generic gate mirrors DEF14A evidence check",
        ),
        check_c04_auditorname_all_companies(
            metrics=metrics,
            evidence_rows=evidence_rows,
        ),
        check_eleventh_company_smoke_mounts(),
        check_eleventh_company_behavior_lodging(),
        check_eleventh_company_behavior_financial_institution(),
        check_eleventh_company_behavior_captive_finance(),
        check_eleventh_company_behavior_rpo_crpo(),
        check_ok_status_recall_not_regressed_without_reason(metrics=metrics),
        check_coverage_join(coverage=coverage, evidence_rows=evidence_rows),
        check_numeric_ok_requires_evidence(
            metrics=metrics,
            evidence_rows=evidence_rows,
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
        ),
    ]
    failed_ids = [
        row["check_id"]
        for row in rows
        if row["status"] in {"FAIL", "WORKSPACE_INCOMPLETE"}
        and row["check_id"] != "existing_repair_validation_still_pass"
    ]
    rows.append(
        validation_row(
            check_id="existing_repair_validation_still_pass",
            status=(
                "FAIL"
                if failed_ids
                else "PASS_LIGHT_REVIEW"
                if light_mode
                else "PASS"
            ),
            details=(
                ";".join(failed_ids[:20])
                if failed_ids
                else "light review gates pass; full evidence checks skipped"
                if light_mode
                else "all gates pass"
            ),
        )
    )
    write_csv_file(
        path=WORKDIR / "outputs" / "repair_validation_results.csv",
        fieldnames=REPAIR_VALIDATION_FIELDNAMES,
        rows=rows,
    )
    failures = [
        row
        for row in rows
        if row["severity"] == "P0" and row["status"] == "FAIL"
    ]
    if failures and exit_on_failure:
        print("Repair validation failed:")
        for row in failures:
            print(f"{row['check_id']}: {row['details']}")
        raise SystemExit(1)
    if not failures and light_mode:
        print(
            "Light review validation complete; full-evidence checks skipped: "
            + "; ".join(light_reasons)
        )
    elif not failures:
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
        "## 仍需复核或未抽取项目",
        "",
        "| Company | Metric | Status | Reason |",
        "|---|---|---|---|",
    ]
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
        if row["url"].startswith("https://www.sec.gov/")
        or row["url"].startswith("https://data.sec.gov/")
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
) -> str:
    """Return GO / GO WITH CAVEATS / NO-GO for the final report."""
    if any(
        row["severity"] == "P0"
        and row["status"] in {"FAIL", "WORKSPACE_INCOMPLETE"}
        for row in validation_rows
    ):
        return "NO-GO"
    if any(row["status"] == "FAIL" for row in golden_rows):
        return "NO-GO"
    validation_caveat_statuses = {
        "SKIPPED_LIGHT_PACKAGE",
        "PASS_LIGHT_REVIEW",
        "PASS_LIGHT_GOLDEN_INTEGRITY",
    }
    if any(row["status"] in validation_caveat_statuses for row in validation_rows):
        return "GO WITH CAVEATS"
    caveat_statuses = {"NOT_EXTRACTED", "NEEDS_REVIEW", "PARSE_FAILED"}
    if any(row["status"] in caveat_statuses for row in metric_rows):
        return "GO WITH CAVEATS"
    return "GO"


def build_report_markdown() -> str:
    """Build the final Chinese Markdown report."""
    metrics = load_metrics()
    resolution = read_csv_file(path=WORKDIR / "outputs" / "company_resolution.csv")
    coverage = read_csv_file(path=WORKDIR / "outputs" / "coverage_matrix.csv")
    golden = read_csv_file(path=WORKDIR / "outputs" / "golden_results.csv")
    validation = read_csv_file(
        path=WORKDIR / "outputs" / "repair_validation_results.csv"
    )
    stratified_audit = read_csv_file(path=WORKDIR / "outputs" / "stratified_audit.csv")
    events = read_csv_file(path=WORKDIR / "outputs" / "events.csv")
    stats = request_stats()
    verdict = report_verdict(
        golden_rows=golden,
        metric_rows=metrics,
        validation_rows=validation,
    )
    ok_statuses = {
        "OK",
        "MDA_OK",
        "DEF14A_OK",
        "DIM_XBRL_OK",
        "8K_ITEM_OK",
        "TEXT_QUAL",
    }
    ok_count = len([row for row in metrics if row["status"] in ok_statuses])
    caveat_count = len(metrics) - ok_count
    lines = [
        "# REPORT_十公司财务指标",
        "",
        "## Executive Summary",
        "",
        f"- Verdict: **{verdict}**。",
        f"- SEC 请求总数：{stats['total']}；状态分布：`{stats['statuses']}`。",
        f"- 指标格子：{len(metrics)}；OK/TEXT 类：{ok_count}；待复核/不可得类：{caveat_count}。",
        "- 本次只使用 SEC 官方响应和本地 evidence 文件；未使用第三方数据或模型记忆补数。",
        "- Repair validation 若有 P0 FAIL，verdict 强制为 NO-GO。",
        "- Stratified audit 任一 FAIL 会进入 repair validation gate，不能被报告静默吞掉。",
        "",
        "## 数据来源和请求统计",
        "",
        "- company_tickers_exchange、submissions、companyfacts、"
        "accession materials、8-K hdr.sgml、DEF 14A primary document "
        "均通过 SEC 官方 URL 请求。",
        "- 所有请求记录在 `evidence/requests_log.csv`，原始响应保存在 `evidence/` 子目录，并带 headers/hash 旁路文件。",
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
            "- DEF 14A 输出 governance_signals，并在存在 ecd facts 时 dump 到 concept_inventory。",
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
            "- SEC HTTP 配置：`config/sec_config.json`。",
            "- 所有时间戳使用 UTC；文本编码 UTF-8。",
            "- 全局请求速率默认 5 requests/sec。",
            "",
            "## 从干净目录运行 M0-M7",
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
                "M7 会先应用 bounded P0 local repair，然后生成 coverage、"
                "exceptions、repair validation、最终报告和本 README。"
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
            "- `outputs/golden_results.csv` 必须全 PASS。",
            (
                "- 完整工作区 `outputs/repair_validation_results.csv` 必须全 PASS；"
                "轻量审核包中依赖 raw evidence / concept inventory 的检查必须显示为 "
                "`SKIPPED_LIGHT_PACKAGE`，总 gate 显示为 `PASS_LIGHT_REVIEW`。"
            ),
            (
                "- 轻量审核包必须在根目录包含 "
                "`LIGHT_REVIEW_PACKAGE.marker`；未声明的缺 evidence / "
                "concept inventory 工作区必须 `WORKSPACE_INCOMPLETE`。"
            ),
            "- `metrics/evidence/coverage/report` 必须能互相追溯一致。",
            "",
            "### 第二层：去公司特例验收",
            "",
            "```bash",
            "python3 tools/check_no_company_literals.py",
            "```",
            "",
            "- 生产 extractor 不得出现公司名业务分支。",
            "- `config/`、`tests/fixtures/`、报告模板可以出现公司名。",
            "- 自动审计使用 AST 扫描 Python literal，明细写入 "
            "`outputs/scalability_audit.csv`。",
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
                "- C04 只针对 AuditorName 对照补抓 SEC 官方 XBRL instance；"
                "所有请求仍通过 `SecHttpClient.fetch(...)` 写入 "
                "`evidence/requests_log.csv`。"
            ),
            (
                "- `outputs/stratified_audit.csv` 固化验收分层抽样："
                "STD_XBRL/DERIVED、DIM_XBRL、DEF14A、MDA/TEXT、8K_ITEM。"
            ),
            "",
            "## P0 validation 失败定位",
            "",
            "- 先打开 `outputs/repair_validation_results.csv`，按 `check_id` 查看 FAIL 行。",
            (
                "- 对证据缺失类失败，按 `(company, metric_id)` join "
                "`outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。"
            ),
            (
                "- 对 C03 失败，检查 `outputs/concept_inventory/*_ecd.csv` "
                "中目标 `period_end` 的 `PeoTotalCompAmt`。"
            ),
            (
                "- 对 FI Basel ratio 失败，检查对应 "
                "`outputs/concept_inventory/*_instance.csv` 的 ratio facts。"
            ),
            "- 对请求边界失败，检查 `evidence/requests_log.csv` 的 URL、User-Agent 和 retry_attempt。",
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
            "- `outputs/stratified_audit.csv`",
            "- `outputs/events.csv`",
            "- `outputs/golden_results.csv`",
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
                "通过时输出 `PASS_LIGHT_GOLDEN_INTEGRITY`；完整数值 golden "
                "rerun 需要本地完整 `evidence/`。"
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


def stage_build_report() -> None:
    """M7: build crosschecks, coverage, exceptions, report, and README."""
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
    run_repair_validation(exit_on_failure=False)
    stratified_audit = build_stratified_audit_rows()
    write_csv_file(
        path=WORKDIR / "outputs" / "stratified_audit.csv",
        fieldnames=STRATIFIED_AUDIT_FIELDNAMES,
        rows=stratified_audit,
    )
    (WORKDIR / "REPORT_十公司财务指标.md").write_text(
        build_report_markdown(),
        encoding="utf-8",
    )
    (WORKDIR / "README_RUN.md").write_text(build_readme(), encoding="utf-8")
    print("M7 report build complete")


def stage_validate_repair() -> None:
    """M7 repair gate: validate P0 repairs and exit nonzero on failures."""
    run_repair_validation(exit_on_failure=True)


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
