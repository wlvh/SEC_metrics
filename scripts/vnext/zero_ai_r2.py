"""Publish the Issue #15 R2 deterministic 22-metric ratchet.

Purpose:
    Build complete multi-source SEC plans, adapt exact immutable bytes into
    deterministic claims, calculate the fourteen post-R1 financial metrics,
    project six fiscal-year 8-K event metrics, materialize structural Results,
    and commit one successor over the active R1 publication without any model
    provider call.

Call relationships:
    ``tools/vnext_zero_ai_release.py r2`` calls :func:`publish_r2`.
    Source adapters live in ``deterministic_router``; Result/Trace construction
    uses the vNext calculator and record validators; publication reuses the
    formal CAS primitive and zero-AI bundle verifier.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from git_workspace import sanitized_git_environment
from sec_http import parse_request_log_rows, request_accession
from sec_http import request_log_attempt_id, validate_request_log_manifest
from validation_provenance import capture_source_snapshot
from validation_provenance import publish_validation_snapshot

from .batch_workflow import BatchWorkflowError, _verified_request_locator
from .calculator import calculate_observation_metric, metric_is_applicable
from .canonical import atomic_write_bytes, content_hash, decimal_text
from .canonical import execution_semantics_hash, parse_decimal, sha256_bytes
from .canonical import sha256_file, strict_json_file
from .deterministic_router import adapt_8k_item_index, adapt_accession_xbrl
from .deterministic_router import adapt_companyfacts
from .deterministic_router import build_multi_source_release_input_plan
from .deterministic_router import load_event_route_catalog
from .deterministic_router import matched_event_key_set, project_event_result
from .deterministic_router import normalize_event_text
from .deterministic_router import source_role_plan, source_set_manifest
from .deterministic_router import validate_source_set_manifest
from .invocation_control import structured_only_result
from .observations import scope_key, structured_observation
from .publication import PublicationView, REQUIRED_BUNDLE_FILES
from .publication import ZERO_AI_FORMAL_MANIFEST, _commit_publication
from .publication import _write_prepared_publication_bundle
from .publication import publication_layout
from .records import metric_result_contract_hash, validate_record
from .requirements import load_requirement_snapshot
from .source_strategy import load_issue15_release_plan
from .specs import compile_spec
from .sources import raw_blob_record, source_reference_record
from .traits import repository_company_ciks, repository_company_traits
from .zero_ai_release import COVERAGE_FIELDS, METRICS_FIELDS
from .zero_ai_release import ZeroAiReleaseError, _append_csv_rows
from .zero_ai_release import _append_publication_note, _csv_rows
from .zero_ai_release import _internal_bindings, _json_bytes, _ledger_binding
from .zero_ai_release import _public_key_proof, _read_back_proof
from .zero_ai_release import _receipt, _registry_rows, _retirement_receipt
from .zero_ai_release import _source_commit_binding
from .zero_ai_release import _source_reference


R2_METRIC_IDS = (
    "A01", "A02", "A05", "A06", "A07", "A08", "A10",
    "B01", "B02", "B03", "B04", "B05", "B07", "B08", "B09", "B12",
    "C01", "E01", "E02", "E03", "E04", "E05",
)
R2_ADDED_METRIC_IDS = tuple(
    metric_id for metric_id in R2_METRIC_IDS
    if metric_id not in {"B01", "B03"}
)
R2_DETERMINISTIC_METRIC_IDS = tuple(
    metric_id for metric_id in R2_ADDED_METRIC_IDS
    if not metric_id.startswith("E") and metric_id != "C01"
)
R2_EVENT_METRIC_IDS = ("C01", "E01", "E02", "E03", "E04", "E05")
R2_EXPECTED_COORDINATES = 220
R2_EXPECTED_LEGACY_ROWS = 141
R2_EXPECTED_NEW_KEYS = 79
R2_EXPECTED_PUBLIC_ROWS = 309
R2_EXPECTED_ADDED_COORDINATES = 200
DETERMINISTIC_CATALOG_FIELDS = {
    "metrics", "record_type", "schema_version",
}
DETERMINISTIC_ROUTE_FIELDS = {
    "adapter_id",
    "applicability",
    "branches",
    "canonical_unit",
    "continuity_policy",
    "name",
    "result_period_role",
    "source_class",
    "source_role",
    "success_status",
}
DETERMINISTIC_BRANCH_FIELDS = {
    "branch_id", "components", "formula_id", "quality",
}
DETERMINISTIC_COMPONENT_FIELDS = {
    "accession_role",
    "approved_concepts",
    "dimension_policy",
    "period_role",
    "required_dimensions",
    "role",
    "unit",
}
FORMULA_IDS = {
    "average_denominator_ratio",
    "difference",
    "direct",
    "growth",
    "interest_coverage",
    "ratio",
}
FORMULA_ARITIES = {
    "average_denominator_ratio": {3},
    "difference": {2},
    "direct": {1},
    "growth": {2},
    "interest_coverage": {2, 3},
    "ratio": {2},
}


def _required_text(*, value: object, label: str) -> str:
    """Return one required catalog text value.

    Args:
        value: Candidate catalog value.
        label: Stable diagnostic field name.

    Returns:
        Non-empty text.
    """
    if not isinstance(value, str) or not value:
        raise ZeroAiReleaseError(label + " must be non-empty text")
    return value


def _validate_deterministic_component(
    *, component: object,
) -> Dict[str, object]:
    """Validate one catalog-owned fact selection component."""
    if not isinstance(component, dict) or set(component) != (
        DETERMINISTIC_COMPONENT_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic component fields differ")
    value = dict(component)
    _required_text(value=value["role"], label="Component role")
    _required_text(value=value["unit"], label="Component unit")
    if value["accession_role"] not in {"current", "prior"}:
        raise ZeroAiReleaseError("Component accession role is invalid")
    if value["period_role"] not in {
        "current_annual", "current_instant",
        "prior_annual", "prior_instant",
    }:
        raise ZeroAiReleaseError("Component period role is invalid")
    concepts = value["approved_concepts"]
    if (
        not isinstance(concepts, list)
        or not concepts
        or any(not isinstance(item, str) or not item for item in concepts)
        or len(concepts) != len(set(concepts))
    ):
        raise ZeroAiReleaseError("Component concept priority is invalid")
    dimensions = value["required_dimensions"]
    if (
        not isinstance(dimensions, dict)
        or any(
            not isinstance(axis, str)
            or not axis
            or not isinstance(member, str)
            or not member
            for axis, member in dimensions.items()
        )
    ):
        raise ZeroAiReleaseError("Component dimensions are invalid")
    if value["dimension_policy"] not in {"EXACT", "NONE"}:
        raise ZeroAiReleaseError("Component dimension policy is invalid")
    if value["dimension_policy"] == "NONE" and dimensions:
        raise ZeroAiReleaseError("NONE dimension policy cannot name dimensions")
    return value


def _validate_deterministic_branch(*, branch: object) -> Dict[str, object]:
    """Validate one ordered deterministic calculation branch."""
    if not isinstance(branch, dict) or set(branch) != (
        DETERMINISTIC_BRANCH_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic branch fields differ")
    value = dict(branch)
    _required_text(value=value["branch_id"], label="Branch id")
    if value["formula_id"] not in FORMULA_IDS:
        raise ZeroAiReleaseError("Deterministic branch formula is invalid")
    if value["quality"] not in {"EXACT", "APPROX"}:
        raise ZeroAiReleaseError("Deterministic branch quality is invalid")
    if not isinstance(value["components"], list):
        raise ZeroAiReleaseError("Deterministic branch components differ")
    components = [
        _validate_deterministic_component(component=component)
        for component in value["components"]
    ]
    if len(components) not in FORMULA_ARITIES[value["formula_id"]]:
        raise ZeroAiReleaseError("Deterministic formula arity differs")
    roles = [str(component["role"]) for component in components]
    if len(roles) != len(set(roles)):
        raise ZeroAiReleaseError("Deterministic component role is duplicated")
    value["components"] = components
    return value


def _load_deterministic_catalog(*, repo_root: Path) -> Dict[str, object]:
    """Load and validate the fourteen-metric deterministic catalog.

    Args:
        repo_root: Repository containing catalog authority.

    Returns:
        Strict catalog mapping.
    """
    payload = strict_json_file(
        path=repo_root / "catalog" / "deterministic_metrics.json"
    )
    if not isinstance(payload, dict) or set(payload) != (
        DETERMINISTIC_CATALOG_FIELDS
    ):
        raise ZeroAiReleaseError("Deterministic metric catalog fields differ")
    catalog = dict(payload)
    if (
        catalog["schema_version"] != 2
        or catalog["record_type"] != "DETERMINISTIC_METRIC_CATALOG"
        or not isinstance(catalog["metrics"], dict)
        or set(catalog["metrics"]) != set(R2_DETERMINISTIC_METRIC_IDS)
    ):
        raise ZeroAiReleaseError("Deterministic metric catalog exact set differs")
    for metric_id, route_value in catalog["metrics"].items():
        if not isinstance(route_value, dict) or set(route_value) != (
            DETERMINISTIC_ROUTE_FIELDS
        ):
            raise ZeroAiReleaseError("Deterministic metric route fields differ")
        route = dict(route_value)
        for field in ("canonical_unit", "name", "source_class"):
            _required_text(
                value=route[field], label="Deterministic route " + field,
            )
        expected_source_role = {
            "accession_xbrl": "target_accession_instance",
            "companyfacts": "companyfacts",
        }
        applicability = route["applicability"]
        if (
            route["adapter_id"] not in expected_source_role
            or route["source_role"] != expected_source_role[
                route["adapter_id"]
            ]
            or route["result_period_role"] not in {
                "current_annual", "current_instant",
            }
            or route["continuity_policy"] not in {
                "ALLOW", "REQUIRE_CONTINUOUS",
            }
            or route["success_status"] not in {"DIM_XBRL_OK", "OK"}
            or not isinstance(applicability, dict)
            or set(applicability) != {"all", "none"}
            or any(
                not isinstance(values, list)
                or any(not isinstance(item, str) or not item for item in values)
                or len(values) != len(set(values))
                for values in applicability.values()
            )
            or not isinstance(route["branches"], list)
            or not route["branches"]
        ):
            raise ZeroAiReleaseError(
                "Deterministic metric route is invalid: " + metric_id
            )
        branches = [
            _validate_deterministic_branch(branch=branch)
            for branch in route["branches"]
        ]
        branch_ids = [str(branch["branch_id"]) for branch in branches]
        if len(branch_ids) != len(set(branch_ids)):
            raise ZeroAiReleaseError("Deterministic branch id is duplicated")
        route["branches"] = branches
        catalog["metrics"][metric_id] = route
    return catalog


def _legacy_publication_context(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Load active R1 B and its verified frozen predecessor A.

    Args:
        repo_root: Formal publication root.

    Returns:
        Active view, marker, predecessor directory, and legacy public rows.
    """
    view = PublicationView.open(publication_root=repo_root)
    marker = json.loads(
        view.read_bytes(relative_path=ZERO_AI_FORMAL_MANIFEST).decode("utf-8")
    )
    if (
        marker["release_stage"] != "R1"
        or marker["cumulative_metric_ids"] != ["B01", "B03"]
        or any(marker["counters"].values())
    ):
        raise ZeroAiReleaseError("R2 requires the exact active R1 predecessor")
    predecessor_id = str(view.manifest["previous_publication_id"])
    predecessor_dir = (
        repo_root / "outputs" / "publications" / predecessor_id
    )
    metrics_bytes = (predecessor_dir / "metrics_matrix.csv").read_bytes()
    return {
        "active_view": view,
        "r1_marker": marker,
        "legacy_predecessor_id": predecessor_id,
        "legacy_predecessor_dir": predecessor_dir,
        "legacy_metrics_bytes": metrics_bytes,
        "legacy_metrics": _csv_rows(
            content=metrics_bytes, fields=METRICS_FIELDS,
        ),
    }


def _inventory_reference(
    *, repo_root: Path, registry_row: Mapping[str, str],
    fiscal_year: object,
) -> Tuple[Dict[str, object], Dict[str, object], bytes]:
    """Build one immutable SEC submissions inventory observation.

    Args:
        repo_root: Repository containing submissions bytes and ledger.
        registry_row: Company identity authority.
        fiscal_year: Release target fiscal year label.

    Returns:
        SourceReference, locator binding, and exact bytes.
    """
    cik = str(int(registry_row["primary_cik"])).zfill(10)
    document_name = "CIK{}.json".format(cik)
    relative = "evidence/submissions/" + document_name
    reference, binding = _source_reference(
        repo_root=repo_root,
        company_id=registry_row["company_id"],
        repo_relative_path=relative,
        source_url="https://data.sec.gov/submissions/" + document_name,
        accession="SUBMISSIONS-{}".format(fiscal_year),
        document_name=document_name,
        source_role="sec_submissions_inventory",
        media_type="application/json",
    )
    return reference, binding, (repo_root / relative).read_bytes()


def _inventory_for_accession(
    *, repo_root: Path, registry_row: Mapping[str, str], accession: str,
    fiscal_year: object, current_reference: Mapping[str, object],
    current_bytes: bytes,
) -> Tuple[Dict[str, object], Dict[str, object], bytes]:
    """Select current submissions or one exact historical shard.

    Args:
        repo_root: Repository containing SEC submissions artifacts.
        registry_row: Company identity authority.
        accession: Filing that the source set must discover.
        fiscal_year: Release fiscal-year label for the observation identity.
        current_reference: Main submissions SourceReference.
        current_bytes: Main submissions bytes.

    Returns:
        Inventory SourceReference, locator proof, and exact bytes.
    """
    try:
        _filing_from_inventory(
            inventory_bytes=current_bytes, accession=accession,
        )
        return current_reference, {}, current_bytes
    except ZeroAiReleaseError:
        pass
    cik = str(int(registry_row["primary_cik"])).zfill(10)
    candidates = []
    for path in sorted(
        (repo_root / "evidence" / "submissions").glob(
            "CIK{}-submissions-*.json".format(cik)
        )
    ):
        content = path.read_bytes()
        try:
            _filing_from_inventory(
                inventory_bytes=content, accession=accession,
            )
        except ZeroAiReleaseError:
            continue
        candidates.append((path, content))
    if len(candidates) != 1:
        raise ZeroAiReleaseError(
            "Historical submissions shard is absent or ambiguous: " + accession
        )
    path, content = candidates[0]
    reference, binding = _event_source_reference(
        repo_root=repo_root,
        company_id=registry_row["company_id"],
        repo_relative_path=path.relative_to(repo_root).as_posix(),
        source_url="https://data.sec.gov/submissions/" + path.name,
        accession="SUBMISSIONS-HISTORY-{}".format(fiscal_year),
        document_name=path.name,
        source_role="sec_submissions_inventory_" + path.stem,
        media_type="application/json",
    )
    return reference, binding, content


def _exact_filing_source_set(
    *, company_id: str, source_role: str, reference: Mapping[str, object],
    inventory_reference: Mapping[str, object], inventory_bytes: bytes,
) -> Dict[str, object]:
    """Build one exact-filing source set from pinned submissions bytes.

    Args:
        company_id: Logical company identity.
        source_role: Deterministic adapter role.
        reference: Filing-bound SourceReference.
        inventory_reference: Pinned submissions observation.
        inventory_bytes: Exact submissions bytes.

    Returns:
        Complete content-addressed SourceSetManifest.
    """
    form, filed = _filing_from_inventory(
        inventory_bytes=inventory_bytes,
        accession=str(reference["accession"]),
    )
    return source_set_manifest(
        company_id=company_id,
        source_role=source_role,
        form_types=[form],
        fiscal_or_date_window={"period_start": filed, "period_end": filed},
        discovery_policy="PINNED_SUBMISSIONS_EXACT_FILING_V1",
        inventory_source_reference=inventory_reference,
        inventory_bytes=inventory_bytes,
        ordered_source_references=[reference],
        cutoff_timestamp_or_pinned_submissions_attempt=str(
            inventory_reference["request_attempt_id"]
        ),
    )


def _filing_from_inventory(
    *, inventory_bytes: bytes, accession: str,
) -> Tuple[str, str]:
    """Return form and filing date for one unique submissions accession."""
    try:
        payload = json.loads(inventory_bytes.decode("utf-8"))
        if "filings" in payload:
            recent = payload["filings"]["recent"]
        else:
            recent = payload
        matches = [
            (str(recent["form"][index]), str(recent["filingDate"][index]))
            for index, candidate in enumerate(recent["accessionNumber"])
            if candidate == accession
        ]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("SEC submissions inventory is invalid") from error
    if len(matches) != 1 or any(not value for value in matches[0]):
        raise ZeroAiReleaseError(
            "Filing accession is absent from submissions: " + accession
        )
    return matches[0]


def _submission_filing_rows(*, inventory_bytes: bytes) -> List[Dict[str, str]]:
    """Return strict filing rows from one SEC submissions payload.

    Args:
        inventory_bytes: Current or historical submissions JSON bytes.

    Returns:
        Ordered filing identity rows needed by deterministic discovery.
    """
    try:
        payload = json.loads(inventory_bytes.decode("utf-8"))
        recent = payload["filings"]["recent"] if "filings" in payload else payload
        required = {
            "accessionNumber", "filingDate", "form", "primaryDocument",
            "reportDate",
        }
        if not isinstance(recent, dict) or not required.issubset(recent):
            raise ZeroAiReleaseError("SEC submissions filing fields differ")
        lengths = {len(recent[field]) for field in required}
        if len(lengths) != 1:
            raise ZeroAiReleaseError("SEC submissions columns are misaligned")
        rows = []
        for index in range(next(iter(lengths))):
            row = {
                "accession": str(recent["accessionNumber"][index]),
                "filing_date": str(recent["filingDate"][index]),
                "form": str(recent["form"][index]),
                "primary_document": str(recent["primaryDocument"][index]),
                "report_date": str(recent["reportDate"][index]),
            }
            rows.append(row)
        return rows
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("SEC submissions inventory is invalid") from error


def _annual_filing_pair(
    *, repo_root: Path, inventory_bytes: bytes,
) -> Dict[str, object]:
    """Discover the latest two original 10-K filings without legacy rows.

    Args:
        repo_root: Repository containing pinned submissions shards.
        inventory_bytes: Current SEC submissions inventory.

    Returns:
        Current original 10-K and an optional prior original 10-K.
    """
    rows = _submission_filing_rows(inventory_bytes=inventory_bytes)
    try:
        payload = json.loads(inventory_bytes.decode("utf-8"))
        history = payload["filings"]["files"]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("SEC submissions history index is invalid") from error
    if not isinstance(history, list):
        raise ZeroAiReleaseError("SEC submissions history index differs")
    for entry in history:
        if not isinstance(entry, dict) or "name" not in entry:
            raise ZeroAiReleaseError("SEC submissions history entry is invalid")
        name = str(entry["name"])
        path = repo_root / "evidence" / "submissions" / name
        if path.name != name or path.is_symlink():
            raise ZeroAiReleaseError("SEC submissions history shard is unsafe")
        if not path.is_file():
            continue
        rows.extend(_submission_filing_rows(inventory_bytes=path.read_bytes()))
    originals = {}
    for row in rows:
        if row["form"] != "10-K" or any(not value for value in row.values()):
            continue
        accession = row["accession"]
        if accession in originals and originals[accession] != row:
            raise ZeroAiReleaseError("Original 10-K identity conflicts")
        originals[accession] = row
    ordered = sorted(
        originals.values(),
        key=lambda row: (
            row["report_date"], row["filing_date"], row["accession"],
        ),
        reverse=True,
    )
    if not ordered:
        raise ZeroAiReleaseError("Original 10-K filing is absent")
    current = ordered[0]
    prior_candidates = [
        row for row in ordered if row["report_date"] < current["report_date"]
    ]
    return {
        "current": dict(current),
        "prior": dict(prior_candidates[0]) if prior_candidates else None,
    }


def _deterministic_concepts(
    *, catalog: Mapping[str, object], adapter_id: str,
) -> List[str]:
    """Return the ordered unique concept closure for one adapter."""
    concepts = []
    for route in catalog["metrics"].values():
        if route["adapter_id"] != adapter_id:
            continue
        for branch in route["branches"]:
            for component in branch["components"]:
                for concept in component["approved_concepts"]:
                    if concept not in concepts:
                        concepts.append(str(concept))
    if not concepts:
        raise ZeroAiReleaseError("Deterministic adapter concept set is empty")
    return concepts


def _period_from_companyfacts_claims(
    *, claims: Sequence[Mapping[str, object]], filing: Mapping[str, str],
) -> Dict[str, str]:
    """Derive one target annual period from catalog-selected SEC facts.

    Args:
        claims: Claims emitted solely from catalog concept candidates.
        filing: Submissions-discovered original 10-K identity.

    Returns:
        Unique highest-coverage annual period ending on the report date.
    """
    concept_sets: Dict[Tuple[str, str], set[str]] = {}
    for claim in claims:
        locator = claim["locator"]
        attributes = claim["attributes"]
        period_start = str(locator["period_start"])
        period_end = str(locator["period_end"])
        if (
            attributes["accession"] != filing["accession"]
            or attributes["form"] != "10-K"
            or attributes["fiscal_period"] != "FY"
            or period_start == period_end
            or period_end != filing["report_date"]
        ):
            continue
        key = (period_start, period_end)
        if key not in concept_sets:
            concept_sets[key] = set()
        concept_sets[key].add(_claim_concept(claim=claim))
    if not concept_sets:
        raise ZeroAiReleaseError("Catalog facts lack an annual target period")
    coverage = Counter({key: len(value) for key, value in concept_sets.items()})
    maximum = max(coverage.values())
    winners = sorted(key for key, count in coverage.items() if count == maximum)
    if len(winners) != 1:
        raise ZeroAiReleaseError("Annual target period is ambiguous")
    period_start, period_end = winners[0]
    return {"period_start": period_start, "period_end": period_end}


def _accession_instance_descriptor(
    *, repo_root: Path, company_id: str, cik: str,
    filing: Mapping[str, str],
) -> Dict[str, str]:
    """Resolve one submissions-declared 10-K to its local XBRL instance."""
    accession_digits = filing["accession"].replace("-", "")
    suffix = "_{}_{}".format(str(int(cik)), accession_digits)
    directories = [
        path
        for path in (repo_root / "evidence" / "accession_materials").iterdir()
        if path.is_dir() and path.name.endswith(suffix)
    ]
    if len(directories) != 1:
        raise ZeroAiReleaseError(
            "10-K accession directory is ambiguous: " + company_id
        )
    primary = str(filing["primary_document"])
    if "." not in primary:
        raise ZeroAiReleaseError("10-K primary document name is invalid")
    document_name = primary.rsplit(".", maxsplit=1)[0] + "_htm.xml"
    path = directories[0] / document_name
    if path.is_symlink() or not path.is_file():
        raise ZeroAiReleaseError("10-K XBRL instance is absent")
    return {
        "accession": filing["accession"],
        "document_name": document_name,
        "repo_relative_path": path.relative_to(repo_root).as_posix(),
        "source_url": (
            "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
                str(int(cik)), accession_digits, document_name,
            )
        ),
    }


def _event_accessions(
    *, inventory_bytes: bytes, period_start: str, period_end: str,
) -> List[str]:
    """Return the complete unique fiscal-window 8-K accession set."""
    try:
        payload = json.loads(inventory_bytes.decode("utf-8"))
        if "filings" in payload:
            recent = payload["filings"]["recent"]
        else:
            recent = payload
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZeroAiReleaseError("SEC submissions inventory is invalid") from error
    accessions = [
        str(accession)
        for accession, filed, form in zip(
            recent["accessionNumber"], recent["filingDate"], recent["form"]
        )
        if form in {"8-K", "8-K/A"} and period_start <= filed <= period_end
    ]
    if len(accessions) != len(set(accessions)):
        raise ZeroAiReleaseError("Fiscal-year 8-K accession is duplicated")
    return sorted(accessions)


def _event_collection_manifest(
    *, company_id: str, target: Mapping[str, object],
    inventory_reference: Mapping[str, object],
    event_sets: Sequence[Mapping[str, object]],
    ordered_accessions: Sequence[str],
) -> Dict[str, object]:
    """Bind the exact union of current and historical submissions shards.

    Args:
        company_id: Logical company identity.
        target: Exact fiscal-year date window.
        inventory_reference: Main submissions observation indexing shards.
        event_sets: Individually verified shard source sets.
        ordered_accessions: Complete unique union discovered from those sets.

    Returns:
        Content-addressed collection manifest used by event projection.
    """
    source_ids = [
        str(reference["source_reference_id"])
        for event_set in event_sets
        for reference in event_set["references"]
    ]
    shard_ids = [
        str(event_set["manifest"]["source_set_manifest_id"])
        for event_set in event_sets
    ]
    body = {
        "schema_version": 1,
        "record_type": "SOURCE_SET_MANIFEST",
        "company_id": company_id,
        "source_role": "fy_8k_item_inventory",
        "form_types": ["8-K", "8-K/A"],
        "fiscal_or_date_window": {
            "period_start": target["period_start"],
            "period_end": target["period_end"],
        },
        "discovery_policy": "PINNED_SUBMISSIONS_SHARD_UNION_V1",
        "discovered_accession_set_hash": content_hash(
            value=list(ordered_accessions)
        ),
        "sec_submissions_inventory_hash": inventory_reference["raw_asset_id"],
        "inventory_source_reference_id": inventory_reference[
            "source_reference_id"
        ],
        "ordered_source_reference_ids": source_ids,
        "cutoff_timestamp_or_pinned_submissions_attempt": content_hash(
            value=shard_ids
        ),
    }
    manifest = {**body, "source_set_manifest_id": content_hash(value=body)}
    return validate_source_set_manifest(manifest=manifest)


def _event_documents(
    *, repo_root: Path, company_id: str, accessions: Sequence[str],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    """Load every immutable hdr/primary pair for one complete 8-K set.

    Args:
        repo_root: Repository containing accession materials and ledger.
        company_id: Logical company identity.
        accessions: Exact fiscal-window accession set.

    Returns:
        Adapter document rows, SourceReferences, and locator proofs.
    """
    documents = []
    references = []
    proofs = {}
    material_root = repo_root / "evidence" / "accession_materials"
    for accession in accessions:
        suffix = "_" + accession.replace("-", "")
        directories = [
            path for path in material_root.iterdir()
            if path.is_dir() and path.name.endswith(suffix)
        ]
        if len(directories) != 1:
            raise ZeroAiReleaseError(
                "8-K accession directory is ambiguous: {}:{}:{}".format(
                    company_id, accession, len(directories),
                )
            )
        directory = directories[0]
        parts = directory.name.rsplit("_", maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit():
            raise ZeroAiReleaseError("8-K accession directory identity differs")
        archive_cik = str(int(parts[1]))
        files = [
            path for path in directory.iterdir()
            if path.is_file() and not path.name.endswith(".headers.json")
        ]
        hdrs = [path for path in files if path.name.endswith(".hdr.sgml")]
        primaries = [
            path for path in files
            if path.suffix.casefold() in {".htm", ".html"}
            and not path.name.endswith("-index.html")
        ]
        if len(hdrs) != 1 or len(primaries) != 1:
            raise ZeroAiReleaseError("8-K hdr/primary pair is incomplete")
        base_url = (
            "https://www.sec.gov/Archives/edgar/data/{}/{}/".format(
                archive_cik, accession.replace("-", ""),
            )
        )
        pair = {}
        for role, path, media_type in (
            ("hdr", hdrs[0], "text/plain"),
            ("primary", primaries[0], "text/html"),
        ):
            relative = path.relative_to(repo_root).as_posix()
            reference, binding = _event_source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=relative,
                source_url=base_url + path.name,
                accession=accession,
                document_name=path.name,
                source_role=(
                    "fy_8k_hdr" if role == "hdr" else "fy_8k_primary"
                ),
                media_type=media_type,
            )
            references.append(reference)
            proofs[str(reference["source_reference_id"])] = {
                **binding,
                "source_reference": reference,
            }
            pair[role + "_source_reference"] = reference
            pair[role + "_bytes"] = path.read_bytes()
        documents.append(
            {
                "hdr_source_reference": pair["hdr_source_reference"],
                "hdr_bytes": pair["hdr_bytes"],
                "primary_source_reference": pair[
                    "primary_source_reference"
                ],
                "primary_document_bytes": pair["primary_bytes"],
            }
        )
    return documents, references, proofs


def _git_blob_binding(
    *, repo_root: Path, relative_path: str, expected_bytes: bytes,
) -> Dict[str, str]:
    """Bind one working source to its exact immutable committed Git blob.

    Args:
        repo_root: Current Git repository.
        relative_path: Tracked repository-relative source path.
        expected_bytes: Working bytes already used by the adapter.

    Returns:
        Commit and blob object identities.
    """
    environment = sanitized_git_environment()
    commands = {
        "commit": ["git", "rev-parse", "HEAD"],
        "blob": ["git", "rev-parse", "HEAD:" + relative_path],
        "mode": ["git", "ls-files", "-s", "--", relative_path],
        "bytes": ["git", "cat-file", "blob", "HEAD:" + relative_path],
    }
    outputs = {}
    for label, command in commands.items():
        completed = subprocess.run(
            args=command,
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            env=environment,
        )
        if completed.returncode != 0:
            raise ZeroAiReleaseError("Git blob authority is unavailable")
        outputs[label] = completed.stdout
    mode = outputs["mode"].decode("utf-8").split(maxsplit=1)[0]
    if mode != "100644" or outputs["bytes"] != expected_bytes:
        raise ZeroAiReleaseError("Working SEC source differs from Git blob")
    return {
        "git_commit": outputs["commit"].decode("utf-8").strip(),
        "git_blob_oid": outputs["blob"].decode("utf-8").strip(),
    }


def _event_source_reference(
    *, repo_root: Path, company_id: str, repo_relative_path: str,
    source_url: str, accession: str, document_name: str, source_role: str,
    media_type: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Use immutable attempt bytes or a commit-bound Git-blob fallback.

    Args:
        repo_root: Repository containing SEC bytes, ledger, and Git objects.
        company_id: Logical company identity.
        repo_relative_path: Exact tracked event source path.
        source_url: Official SEC archive URL.
        accession: Filing accession.
        document_name: Filing document name.
        source_role: hdr or primary role.
        media_type: Explicit RawBlob media type.

    Returns:
        SourceReference and immutable locator proof.  The fallback performs no
        network call and binds both body/header bytes to the current commit.
    """
    try:
        reference, binding = _source_reference(
            repo_root=repo_root,
            company_id=company_id,
            repo_relative_path=repo_relative_path,
            source_url=source_url,
            accession=accession,
            document_name=document_name,
            source_role=source_role,
            media_type=media_type,
        )
    except (BatchWorkflowError, ZeroAiReleaseError):
        reference = {}
        binding = {}
    if binding and binding["request_locator_kind"] == "IMMUTABLE_ATTEMPT":
        return reference, binding
    log_path = repo_root / "evidence" / "requests_log.csv"
    validate_request_log_manifest(log_path=log_path)
    rows = parse_request_log_rows(text=log_path.read_text(encoding="utf-8"))
    archive_accession = request_accession(source_url=source_url)
    source_bytes = (repo_root / repo_relative_path).read_bytes()
    content_sha256 = sha256_bytes(content=source_bytes)
    matches = []
    for row_index, row in enumerate(rows):
        if (
            row["method"] != "GET"
            or row["status_code"] != "200"
            or row["error"]
            or row["source_url"] != source_url
            or row["content_sha256"] != content_sha256
            or row["document_name"] != document_name
            or (
                row["accession"] != archive_accession == accession
                if archive_accession
                else row["accession"] not in {"", accession}
            )
        ):
            continue
        proof = _verified_request_locator(
            repo_root=repo_root,
            row=row,
            source_url=source_url,
            content_sha256=content_sha256,
            document_name=document_name,
        )
        if proof["request_repo_relative_path"] != repo_relative_path:
            continue
        matches.append((row_index, row, proof))
    if not matches:
        raise ZeroAiReleaseError("Tracked event source lacks a ledger observation")
    row_index, row, proof = matches[-1]
    raw = raw_blob_record(
        repo_root=repo_root,
        repo_relative_path=repo_relative_path,
        media_type=media_type,
    )
    reference = source_reference_record(
        raw_blob=raw,
        company_id=company_id,
        source_url=source_url,
        accession=accession,
        document_name=document_name,
        source_role=source_role,
        request_attempt_id=request_log_attempt_id(
            row_index=row_index, row=row,
        ),
    )
    body_git = _git_blob_binding(
        repo_root=repo_root,
        relative_path=repo_relative_path,
        expected_bytes=source_bytes,
    )
    headers_path = str(proof["request_headers_repo_relative_path"])
    headers_bytes = (repo_root / headers_path).read_bytes()
    headers_git = _git_blob_binding(
        repo_root=repo_root,
        relative_path=headers_path,
        expected_bytes=headers_bytes,
    )
    if body_git["git_commit"] != headers_git["git_commit"]:
        raise ZeroAiReleaseError("Event body/header Git commits differ")
    return reference, {
        **proof,
        "request_attempt_id": reference["request_attempt_id"],
        "request_locator_kind": "IMMUTABLE_GIT_BLOB",
        "git_commit": body_git["git_commit"],
        "git_body_blob_oid": body_git["git_blob_oid"],
        "git_headers_blob_oid": headers_git["git_blob_oid"],
    }


def build_r2_source_plan(*, repo_root: Path) -> Dict[str, object]:
    """Build the complete 22-metric, ten-company multi-source plan.

    Args:
        repo_root: Repository authority and active R1 root.

    Returns:
        Plan plus exact adapter contexts and frozen compatibility rows.
    """
    legacy = _legacy_publication_context(repo_root=repo_root)
    issue_plan = load_issue15_release_plan(
        repo_root=repo_root, release_plan_id="issue_15_zero_ai_r2",
    )
    if tuple(issue_plan["cumulative_metric_ids"]) != R2_METRIC_IDS:
        raise ZeroAiReleaseError("R2 cumulative metric exact set differs")
    deterministic_catalog = _load_deterministic_catalog(repo_root=repo_root)
    event_catalog = load_event_route_catalog(repo_root=repo_root)
    registry_rows = _registry_rows(repo_root=repo_root)
    registry = {row["company_id"]: row for row in registry_rows}
    display_to_id = {
        row["display_name"]: row["company_id"] for row in registry_rows
    }
    legacy_metric_index = {
        (row["company"], row["metric_id"]): row
        for row in legacy["legacy_metrics"]
    }
    companyfacts_concepts = _deterministic_concepts(
        catalog=deterministic_catalog, adapter_id="companyfacts",
    )
    targets = {}
    target_periods = {}
    filings_by_company = {}
    event_targets = {}
    events_path = repo_root / "outputs" / "events.csv"
    with events_path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        legacy_events = [dict(row) for row in csv.DictReader(file_obj)]
    filing_inventory_path = repo_root / "outputs" / "latest_filings_inventory.csv"
    with filing_inventory_path.open(
        mode="r", encoding="utf-8", newline=""
    ) as file_obj:
        filing_inventory = [dict(row) for row in csv.DictReader(file_obj)]
    references = []
    manifests = []
    proofs = {}
    company_rows = []
    role_context = {}
    for company_id in [row["company_id"] for row in registry_rows]:
        registry_row = registry[company_id]
        padded_cik = str(int(registry_row["primary_cik"])).zfill(10)
        inventory_path = (
            repo_root / "evidence" / "submissions"
            / "CIK{}.json".format(padded_cik)
        )
        if inventory_path.is_symlink() or not inventory_path.is_file():
            raise ZeroAiReleaseError("SEC submissions inventory is absent")
        discovered_filings = _annual_filing_pair(
            repo_root=repo_root, inventory_bytes=inventory_path.read_bytes(),
        )
        filings_by_company[company_id] = discovered_filings
        inventory, inventory_binding, inventory_bytes = _inventory_reference(
            repo_root=repo_root,
            registry_row=registry_row,
            fiscal_year=str(
                discovered_filings["current"]["report_date"]
            )[:4],
        )
        references.append(inventory)
        proofs[str(inventory["source_reference_id"])] = {
            **inventory_binding,
            "source_reference": inventory,
        }
        document_name = "CIK{}.json".format(padded_cik)
        descriptor = {
            "document_name": document_name,
            "repo_relative_path": "evidence/companyfacts/" + document_name,
            "source_url": (
                "https://data.sec.gov/api/xbrl/companyfacts/"
                + document_name
            ),
        }
        raw_companyfacts = (
            repo_root / descriptor["repo_relative_path"]
        ).read_bytes()
        filing_roles = [("current", discovered_filings["current"])]
        if discovered_filings["prior"] is not None:
            filing_roles.append(("prior", discovered_filings["prior"]))
        companyfacts_sources = []
        source_roles = []
        period_claims = {}
        for accession_role, filing in filing_roles:
            accession = str(filing["accession"])
            source_role = "companyfacts_" + accession_role
            companyfacts, companyfacts_binding = _source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=descriptor["repo_relative_path"],
                source_url=descriptor["source_url"],
                accession=accession,
                document_name=descriptor["document_name"],
                source_role=source_role,
                media_type="application/json",
            )
            (
                filing_inventory_reference,
                filing_inventory_binding,
                filing_inventory_bytes,
            ) = _inventory_for_accession(
                repo_root=repo_root,
                registry_row=registry_row,
                accession=accession,
                fiscal_year=str(filing["report_date"])[:4],
                current_reference=inventory,
                current_bytes=inventory_bytes,
            )
            filing_inventory_id = str(
                filing_inventory_reference["source_reference_id"]
            )
            if filing_inventory_id not in proofs:
                references.append(filing_inventory_reference)
                proofs[filing_inventory_id] = {
                    **filing_inventory_binding,
                    "source_reference": filing_inventory_reference,
                }
            companyfacts_manifest = _exact_filing_source_set(
                company_id=company_id,
                source_role=source_role,
                reference=companyfacts,
                inventory_reference=filing_inventory_reference,
                inventory_bytes=filing_inventory_bytes,
            )
            references.append(companyfacts)
            manifests.append(companyfacts_manifest)
            proofs[str(companyfacts["source_reference_id"])] = {
                **companyfacts_binding,
                "source_reference": companyfacts,
            }
            companyfacts_sources.append(
                {
                    "accession_role": accession_role,
                    "manifest": companyfacts_manifest,
                    "reference": companyfacts,
                }
            )
            period_claims[accession_role] = adapt_companyfacts(
                raw_bytes=raw_companyfacts,
                source_reference=companyfacts,
                source_set_manifest=companyfacts_manifest,
                approved_concepts=companyfacts_concepts,
                allowed_ciks=repository_company_ciks(
                    repo_root=repo_root, company_id=company_id,
                ),
                include_instant=True,
            )
            source_roles.append(
                source_role_plan(
                    manifest=companyfacts_manifest,
                    source_mode="STRUCTURED_JSON",
                )
            )
        current_period = _period_from_companyfacts_claims(
            claims=period_claims["current"],
            filing=discovered_filings["current"],
        )
        periods = {"current": current_period, "prior": None}
        if discovered_filings["prior"] is not None:
            periods["prior"] = _period_from_companyfacts_claims(
                claims=period_claims["prior"],
                filing=discovered_filings["prior"],
            )
        target_periods[company_id] = periods
        target = {
            "fiscal_year": int(current_period["period_start"][:4]),
            "period_start": current_period["period_start"],
            "period_end": current_period["period_end"],
        }
        targets[company_id] = target
        role_context[(company_id, "companyfacts")] = {
            "claims_by_accession_role": period_claims,
            "sources": companyfacts_sources,
            "raw_bytes": raw_companyfacts,
        }
        traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
        requires_instance = any(
            route["adapter_id"] == "accession_xbrl"
            and metric_is_applicable(
                applicability=route["applicability"], traits=traits,
            )
            for route in deterministic_catalog["metrics"].values()
        )
        if requires_instance:
            instance_descriptor = _accession_instance_descriptor(
                repo_root=repo_root,
                company_id=company_id,
                cik=registry_row["primary_cik"],
                filing=discovered_filings["current"],
            )
            instance, instance_binding = _source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=instance_descriptor["repo_relative_path"],
                source_url=instance_descriptor["source_url"],
                accession=instance_descriptor["accession"],
                document_name=instance_descriptor["document_name"],
                source_role="target_accession_instance",
                media_type="application/xml",
            )
            instance_manifest = _exact_filing_source_set(
                company_id=company_id,
                source_role="target_accession_instance",
                reference=instance,
                inventory_reference=inventory,
                inventory_bytes=inventory_bytes,
            )
            references.append(instance)
            manifests.append(instance_manifest)
            proofs[str(instance["source_reference_id"])] = {
                **instance_binding,
                "source_reference": instance,
            }
            role_context[(company_id, "target_accession_instance")] = {
                "claims_by_accession_role": {
                    "current": adapt_accession_xbrl(
                        raw_bytes=(
                            repo_root
                            / instance_descriptor["repo_relative_path"]
                        ).read_bytes(),
                        source_reference=instance,
                        source_set_manifest=instance_manifest,
                        fact_names=_deterministic_concepts(
                            catalog=deterministic_catalog,
                            adapter_id="accession_xbrl",
                        ),
                    )
                },
                "manifest": instance_manifest,
                "references": [instance],
                "raw_bytes": (
                    repo_root / instance_descriptor["repo_relative_path"]
                ).read_bytes(),
            }
            source_roles.append(
                source_role_plan(
                    manifest=instance_manifest,
                    source_mode="ACCESSION_XBRL",
                )
            )
        event_row = legacy_metric_index[(registry_row["display_name"], "E01")]
        event_target = {
            "fiscal_year": target["fiscal_year"],
            "period_start": event_row["period_start"],
            "period_end": event_row["period_end"],
        }
        event_targets[company_id] = event_target
        base_inventories = []
        primary_cik = str(int(registry[company_id]["primary_cik"]))
        company_ciks = repository_company_ciks(
            repo_root=repo_root, company_id=company_id,
        )
        expected_event_rows = [
            row for row in filing_inventory
            if row["company"] == registry[company_id]["display_name"]
            and row["source_role"] == "fy_8k"
        ]
        for event_cik in company_ciks:
            cik_rows = [
                row for row in expected_event_rows
                if str(int(row["cik"])) == str(int(event_cik))
            ]
            if not cik_rows:
                raise ZeroAiReleaseError("Event CIK lacks its frozen inventory")
            if len(company_ciks) == 1:
                cik_window = {
                    "period_start": event_target["period_start"],
                    "period_end": event_target["period_end"],
                }
            else:
                years = sorted({row["filingDate"][:4] for row in cik_rows})
                cik_window = {
                    "period_start": years[0] + "-01-01",
                    "period_end": years[-1] + "-12-31",
                }
            if event_cik == primary_cik:
                base_inventories.append(
                    (inventory, inventory_bytes, cik_window, cik_rows)
                )
                continue
            padded = str(int(event_cik)).zfill(10)
            event_inventory_name = "CIK{}.json".format(padded)
            event_inventory_path = (
                repo_root / "evidence" / "submissions" / event_inventory_name
            )
            event_inventory, event_inventory_binding = _event_source_reference(
                repo_root=repo_root,
                company_id=company_id,
                repo_relative_path=event_inventory_path.relative_to(
                    repo_root
                ).as_posix(),
                source_url=(
                    "https://data.sec.gov/submissions/" + event_inventory_name
                ),
                accession="SUBMISSIONS-{}".format(event_target["fiscal_year"]),
                document_name=event_inventory_name,
                source_role=(
                    "sec_submissions_inventory_events_" + padded
                ),
                media_type="application/json",
            )
            event_inventory_id = str(event_inventory["source_reference_id"])
            if event_inventory_id not in proofs:
                references.append(event_inventory)
                proofs[event_inventory_id] = {
                    **event_inventory_binding,
                    "source_reference": event_inventory,
                }
            base_inventories.append(
                (
                    event_inventory,
                    event_inventory_path.read_bytes(),
                    cik_window,
                    cik_rows,
                )
            )
        inventory_candidates = []
        for base_reference, base_bytes, cik_window, cik_rows in base_inventories:
            inventory_candidates.append(
                {
                    "name": str(base_reference["document_name"]),
                    "reference": base_reference,
                    "bytes": base_bytes,
                    "coverage": "CURRENT_RECENT",
                    "window": cik_window,
                    "expected_accessions": sorted(
                        row["accession"] for row in cik_rows
                    ),
                }
            )
            main_payload = json.loads(base_bytes.decode("utf-8"))
            history_files = main_payload["filings"]["files"]
            if not isinstance(history_files, list):
                raise ZeroAiReleaseError("Submissions history index is invalid")
            for history in history_files:
                if not isinstance(history, dict) or not {
                    "name", "filingFrom", "filingTo",
                }.issubset(history):
                    raise ZeroAiReleaseError(
                        "Submissions history entry is invalid"
                    )
                if (
                    str(history["filingTo"]) < str(cik_window["period_start"])
                    or str(history["filingFrom"]) > str(cik_window["period_end"])
                ):
                    continue
                history_name = str(history["name"])
                history_path = (
                    repo_root / "evidence" / "submissions" / history_name
                )
                history_reference, history_binding = _event_source_reference(
                    repo_root=repo_root,
                    company_id=company_id,
                    repo_relative_path=history_path.relative_to(
                        repo_root
                    ).as_posix(),
                    source_url=(
                        "https://data.sec.gov/submissions/" + history_name
                    ),
                    accession="SUBMISSIONS-HISTORY-{}".format(
                        event_target["fiscal_year"]
                    ),
                    document_name=history_name,
                    source_role=(
                        "sec_submissions_inventory_" + history_path.stem
                    ),
                    media_type="application/json",
                )
                history_id = str(history_reference["source_reference_id"])
                if history_id not in proofs:
                    references.append(history_reference)
                    proofs[history_id] = {
                        **history_binding,
                        "source_reference": history_reference,
                    }
                inventory_candidates.append(
                    {
                        "name": history_name,
                        "reference": history_reference,
                        "bytes": history_path.read_bytes(),
                        "coverage": {
                            "filingFrom": history["filingFrom"],
                            "filingTo": history["filingTo"],
                        },
                        "window": cik_window,
                        "expected_accessions": sorted(
                            row["accession"] for row in cik_rows
                        ),
                    }
                )
        event_sets = []
        event_accessions = set()
        for ordinal, candidate in enumerate(inventory_candidates, start=1):
            accessions = _event_accessions(
                inventory_bytes=candidate["bytes"],
                period_start=str(candidate["window"]["period_start"]),
                period_end=str(candidate["window"]["period_end"]),
            )
            if event_accessions.intersection(accessions):
                raise ZeroAiReleaseError("8-K accession spans inventory shards")
            event_accessions.update(accessions)
            documents, event_references, event_proofs = _event_documents(
                repo_root=repo_root,
                company_id=company_id,
                accessions=accessions,
            )
            source_role = "fy_8k_item_inventory_{:02d}".format(ordinal)
            event_manifest = source_set_manifest(
                company_id=company_id,
                source_role=source_role,
                form_types=["8-K", "8-K/A"],
                fiscal_or_date_window={
                    "period_start": candidate["window"]["period_start"],
                    "period_end": candidate["window"]["period_end"],
                },
                discovery_policy="PINNED_SUBMISSIONS_FISCAL_WINDOW_V1",
                inventory_source_reference=candidate["reference"],
                inventory_bytes=candidate["bytes"],
                ordered_source_references=event_references,
                cutoff_timestamp_or_pinned_submissions_attempt=str(
                    candidate["reference"]["request_attempt_id"]
                ),
            )
            references.extend(event_references)
            manifests.append(event_manifest)
            proofs.update(event_proofs)
            event_sets.append(
                {
                    "manifest": event_manifest,
                    "references": event_references,
                    "documents": documents,
                    "inventory_reference": candidate["reference"],
                    "inventory_bytes": candidate["bytes"],
                    "inventory_name": candidate["name"],
                    "inventory_coverage": candidate["coverage"],
                }
            )
            source_roles.append(
                source_role_plan(
                    manifest=event_manifest,
                    source_mode="ITEM_CODE_INDEX",
                )
            )
        expected_event_accessions = {
            row["accession"] for row in expected_event_rows
        }
        if event_accessions != expected_event_accessions:
            raise ZeroAiReleaseError(
                "Submissions-derived 8-K set differs from frozen inventory"
            )
        role_context[(company_id, "fy_8k_item_inventory")] = {
            "sets": event_sets,
            "ordered_accessions": sorted(event_accessions),
        }
        collection_manifest = _event_collection_manifest(
            company_id=company_id,
            target=event_target,
            inventory_reference=inventory,
            event_sets=event_sets,
            ordered_accessions=sorted(event_accessions),
        )
        manifests.append(collection_manifest)
        role_context[(company_id, "fy_8k_item_inventory")].update(
            {
                "collection_manifest": collection_manifest,
                "inventory_reference": inventory,
            }
        )
        source_roles.append(
            source_role_plan(
                manifest=collection_manifest,
                source_mode="ITEM_CODE_INDEX",
            )
        )
        source_roles.sort(key=lambda role: str(role["source_role"]))
        company_rows.append(
            {
                "company_id": company_id,
                "result_metric_ids": list(R2_METRIC_IDS),
                "sources": source_roles,
                "target_period": target,
            }
        )
    authority = {
        **issue_plan["authority_hashes"],
        "deterministic_metric_catalog_sha256": sha256_file(
            path=repo_root / "catalog" / "deterministic_metrics.json"
        ),
    }
    plan = build_multi_source_release_input_plan(
        release_plan_id=str(issue_plan["release_plan"]["release_plan_id"]),
        release_plan_content_id=str(issue_plan["release_plan_content_id"]),
        requirement_id="issue_15_v1",
        authority_hashes=authority,
        companies=company_rows,
        source_references=references,
        source_set_manifests=manifests,
        event_route_catalog_sha256=sha256_file(
            path=repo_root / "catalog" / "event_routes.json"
        ),
    )
    if sorted(proofs) != sorted(
        str(reference["source_reference_id"])
        for reference in plan["source_references"]
    ):
        raise ZeroAiReleaseError("R2 immutable source proof exact set differs")
    return {
        **legacy,
        "repo_root": repo_root,
        "plan": plan,
        "proofs": proofs,
        "role_context": role_context,
        "targets": targets,
        "target_periods": target_periods,
        "filings_by_company": filings_by_company,
        "event_targets": event_targets,
        "registry_rows": registry_rows,
        "registry": registry,
        "display_to_id": display_to_id,
        "deterministic_catalog": deterministic_catalog,
        "event_catalog": event_catalog,
        "legacy_events": legacy_events,
        "legacy_events_sha256": sha256_file(path=events_path),
        "filing_inventory": filing_inventory,
        "filing_inventory_sha256": sha256_file(path=filing_inventory_path),
    }


def _formula_value(*, formula_id: str, values: Sequence[Decimal]) -> Decimal:
    """Evaluate one catalog-owned deterministic arithmetic formula.

    Args:
        formula_id: Validated formula identity.
        values: Ordered exact claim values.

    Returns:
        Decimal result under canonical precision and rounding.
    """
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        if formula_id == "direct" and len(values) == 1:
            return +values[0]
        if formula_id == "difference" and len(values) == 2:
            return +(values[0] - values[1])
        if formula_id == "ratio" and len(values) == 2:
            return +(values[0] / values[1])
        if formula_id == "growth" and len(values) == 2:
            return +((values[0] - values[1]) / values[1])
        if formula_id == "average_denominator_ratio" and len(values) == 3:
            return +(values[0] / ((values[1] + values[2]) / Decimal(2)))
        if formula_id == "interest_coverage" and len(values) == 2:
            return +(values[0] / values[1])
        if formula_id == "interest_coverage" and len(values) == 3:
            return +((values[0] - values[1]) / values[2])
    raise ZeroAiReleaseError("Deterministic formula arity differs")


def _claim_concept(*, claim: Mapping[str, object]) -> str:
    """Return one adapter-neutral local concept name."""
    locator = claim["locator"]
    if "concept" in locator:
        return str(locator["concept"])
    qualified = str(locator["qualified_name"])
    if "}" in qualified:
        return qualified.rsplit("}", maxsplit=1)[1]
    return qualified.split(":", maxsplit=1)[-1]


class _BranchUnavailable(ValueError):
    """Allow one declared deterministic branch to fall through when absent."""


def _period_for_role(
    *, periods: Mapping[str, object], period_role: str,
) -> Tuple[str, str]:
    """Resolve one catalog period role to exact start/end dates."""
    accession_role, grain = period_role.split("_", maxsplit=1)
    if accession_role not in periods or periods[accession_role] is None:
        raise _BranchUnavailable("Required filing period is absent")
    period = periods[accession_role]
    if grain == "annual":
        return str(period["period_start"]), str(period["period_end"])
    if grain == "instant":
        end = str(period["period_end"])
        return end, end
    raise ZeroAiReleaseError("Catalog period role is invalid")


def _claim_period(*, claim: Mapping[str, object]) -> Tuple[str, str]:
    """Return one adapter-neutral deterministic claim period."""
    locator = claim["locator"]
    if "period_start" in locator and "period_end" in locator:
        return str(locator["period_start"]), str(locator["period_end"])
    attributes = claim["attributes"]
    if "context" not in attributes:
        raise ZeroAiReleaseError("XBRL claim context is absent")
    context = attributes["context"]
    return str(context["period_start"]), str(context["period_end"])


def _claim_matches_component(
    *, claim: Mapping[str, object], component: Mapping[str, object],
    periods: Mapping[str, object], accession_roles: Mapping[str, str],
    allowed_ciks: Sequence[str],
) -> bool:
    """Match one SEC claim using catalog period, unit, entity, and dimensions."""
    reference_id = str(claim["source_reference_id"])
    if (
        reference_id not in accession_roles
        or accession_roles[reference_id] != component["accession_role"]
        or claim["unit"] != component["unit"]
        or _claim_period(claim=claim) != _period_for_role(
            periods=periods, period_role=str(component["period_role"]),
        )
    ):
        return False
    attributes = claim["attributes"]
    if claim["claim_kind"] == "COMPANYFACTS_NUMERIC_FACT":
        return (
            component["dimension_policy"] == "NONE"
            and attributes["form"] == "10-K"
            and attributes["fiscal_period"] == "FY"
        )
    if "context" not in attributes:
        return False
    context = attributes["context"]
    normalized_ciks = {str(int(cik)) for cik in allowed_ciks}
    entity = str(context["entity_identifier"])
    if not entity.isdigit() or str(int(entity)) not in normalized_ciks:
        return False
    return (
        component["dimension_policy"] == "EXACT"
        and context["dimensions"] == component["required_dimensions"]
        and context["typed_dimension_count"] == 0
    )


def _select_component_claim(
    *, component: Mapping[str, object],
    claims: Sequence[Mapping[str, object]], periods: Mapping[str, object],
    accession_roles: Mapping[str, str], allowed_ciks: Sequence[str],
) -> Dict[str, object]:
    """Select one fact by catalog concept priority without expected values."""
    for concept in component["approved_concepts"]:
        candidates = [
            dict(claim)
            for claim in claims
            if _claim_concept(claim=claim).casefold() == str(concept).casefold()
            and _claim_matches_component(
                claim=claim,
                component=component,
                periods=periods,
                accession_roles=accession_roles,
                allowed_ciks=allowed_ciks,
            )
        ]
        if not candidates:
            continue
        values = {(str(claim["value"]), str(claim["unit"])) for claim in candidates}
        if len(values) != 1:
            raise ZeroAiReleaseError(
                "Catalog-selected SEC fact is value-ambiguous: " + str(concept)
            )
        candidates.sort(key=lambda claim: str(claim["verified_claim_id"]))
        return candidates[0]
    raise _BranchUnavailable(
        "Catalog concept chain is absent for " + str(component["role"])
    )


def _select_deterministic_branch(
    *, route: Mapping[str, object], claims: Sequence[Mapping[str, object]],
    periods: Mapping[str, object], accession_roles: Mapping[str, str],
    allowed_ciks: Sequence[str],
) -> Tuple[Dict[str, object], List[Dict[str, object]], List[Dict[str, str]]]:
    """Resolve the first complete declared branch and record rejections."""
    rejected = []
    for branch in route["branches"]:
        try:
            selected = [
                _select_component_claim(
                    component=component,
                    claims=claims,
                    periods=periods,
                    accession_roles=accession_roles,
                    allowed_ciks=allowed_ciks,
                )
                for component in branch["components"]
            ]
            return dict(branch), selected, rejected
        except _BranchUnavailable as error:
            rejected.append(
                {"branch_id": str(branch["branch_id"]), "reason": str(error)}
            )
    raise ZeroAiReleaseError("No deterministic catalog branch is complete")


def _compiled_deterministic_spec(
    *, metric_id: str, route: Mapping[str, object],
) -> Dict[str, object]:
    """Compile one direct projection Spec solely from catalog semantics."""
    front = {
        "metric_id": metric_id,
        "name": route["name"],
        "kind": "direct_numeric",
        "canonical_unit": route["canonical_unit"],
        "unit_policy": "fixed_canonical",
        "source_mode": "structured",
        "applicability": route["applicability"],
        "identity_constraints": [],
        "legacy_projection": {
            "status": route["success_status"],
            "source_class": route["source_class"],
        },
        "dependencies": [],
    }
    text = "---\n{}\n---\n\n# {}\n".format(
        json.dumps(front, ensure_ascii=False, indent=2), route["name"],
    )
    return compile_spec(text=text)


def _manual_result_trace(
    *, metric_id: str, company_id: str, period_start: str,
    period_end: str, scope: Mapping[str, object], spec_closure_hash: str,
    applicability: str, quality: str, reason_code: str,
    input_observation_ids: Sequence[str], steps: Sequence[Mapping[str, object]],
    accession: object, entity: object,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Build a validated null Result and its exact ExecutionTrace.

    Args:
        metric_id: Result metric identity.
        company_id: Logical company identity.
        period_start: Inclusive target start.
        period_end: Inclusive target end.
        scope: Canonical result scope.
        spec_closure_hash: Catalog-bound semantic identity.
        applicability: APPLICABLE or N_A_STRUCTURAL.
        quality: NOT_MEANINGFUL or NONE.
        reason_code: Stable non-PASS reason.
        input_observation_ids: Exact deterministic observations used.
        steps: Ordered trace events explaining the null result.
        accession: Optional source accession paired with entity.
        entity: Optional source entity paired with accession.

    Returns:
        Strict MetricResult and ExecutionTrace.
    """
    scoped_key = scope_key(scope=scope)
    contract = {
        "company_id": company_id,
        "metric_id": metric_id,
        "period_start": period_start,
        "period_end": period_end,
        "scope_key": scoped_key,
        "spec_closure_hash": spec_closure_hash,
        "applicability": applicability,
        "quality": quality,
        "publication": "PUBLISHED",
        "reason_code": reason_code,
        "value": None,
        "unit": None,
    }
    trace_body = {
        "metric_id": metric_id,
        "calculation_target": {
            "accession": accession,
            "company_id": company_id,
            "entity": entity,
            "period_end": period_end,
            "period_start": period_start,
            "scope": dict(scope),
            "scope_key": scoped_key,
        },
        "input_observation_ids": list(input_observation_ids),
        "steps": [dict(step) for step in steps],
        "quality": quality,
        "result": None,
        "spec_closure_hash": spec_closure_hash,
        "execution_semantics_hash": execution_semantics_hash(),
        "result_contract_hash": metric_result_contract_hash(result=contract),
    }
    trace_id = content_hash(value=trace_body)
    trace = validate_record(
        record={"record_type": "EXECUTION_TRACE", "trace_id": trace_id, **trace_body}
    )
    result_body = {**contract, "trace_id": trace_id}
    result = validate_record(
        record={
            "record_type": "METRIC_RESULT",
            "result_id": content_hash(value=result_body),
            **result_body,
        }
    )
    return result, trace


def _coordinate(
    *, company_id: str, metric_id: str, result: Mapping[str, object],
    trace: Mapping[str, object], period: Mapping[str, object],
) -> Dict[str, object]:
    """Render one result/trace binding for the complete coordinate index."""
    return {
        "company_id": company_id,
        "metric_id": metric_id,
        "result_id": result["result_id"],
        "trace_id": trace["trace_id"],
        "applicability": result["applicability"],
        "publication": result["publication"],
        "quality": result["quality"],
        "value": result["value"],
        "unit": result["unit"],
        "fiscal_year": period["fiscal_year"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
    }


def _deterministic_metric_graph(
    *, context: Mapping[str, object], company_id: str, metric_id: str,
) -> Dict[str, object]:
    """Build one financial graph without legacy rows or expected values."""
    catalog_route = context["deterministic_catalog"]["metrics"][metric_id]
    role = str(catalog_route["source_role"])
    source = context["role_context"][(company_id, role)]
    source_by_reference = {}
    accession_roles = {}
    if role == "companyfacts":
        for companyfacts_source in source["sources"]:
            reference = companyfacts_source["reference"]
            manifest = companyfacts_source["manifest"]
            reference_id = str(reference["source_reference_id"])
            source_by_reference[reference_id] = (reference, manifest)
            accession_roles[reference_id] = str(
                companyfacts_source["accession_role"]
            )
    else:
        reference = source["references"][0]
        manifest = source["manifest"]
        reference_id = str(reference["source_reference_id"])
        source_by_reference[reference_id] = (reference, manifest)
        accession_roles[reference_id] = "current"
    claims = [
        dict(claim)
        for accession_claims in source["claims_by_accession_role"].values()
        for claim in accession_claims
    ]
    periods = context["target_periods"][company_id]
    period_start, period_end = _period_for_role(
        periods=periods,
        period_role=str(catalog_route["result_period_role"]),
    )
    scope = {
        "coverage": "deterministic_source_set",
        "fiscal_year": context["targets"][company_id]["fiscal_year"],
    }
    spec = _compiled_deterministic_spec(
        metric_id=metric_id, route=catalog_route,
    )
    traits = repository_company_traits(
        repo_root=context["repo_root"], company_id=company_id,
    )
    registry_row = context["registry"][company_id]
    if (
        catalog_route["continuity_policy"] == "REQUIRE_CONTINUOUS"
        and registry_row["entity_continuity_status"] != "continuous"
    ):
        result, trace = _manual_result_trace(
            metric_id=metric_id,
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
            scope=scope,
            spec_closure_hash=str(spec["spec_closure_hash"]),
            applicability="APPLICABLE",
            quality="NOT_MEANINGFUL",
            reason_code="ENTITY_CONTINUITY_NOT_COMPARABLE",
            input_observation_ids=[],
            steps=[{"event": "ENTITY_CONTINUITY_NOT_COMPARABLE"}],
            accession=context["filings_by_company"][company_id]["current"][
                "accession"
            ],
            entity=str(int(registry_row["primary_cik"])),
        )
        return {
            "claims": [],
            "observation": None,
            "result": result,
            "trace": trace,
        }
    allowed_ciks = repository_company_ciks(
        repo_root=context["repo_root"], company_id=company_id,
    )
    branch, selected, rejected = _select_deterministic_branch(
        route=catalog_route,
        claims=claims,
        periods=periods,
        accession_roles=accession_roles,
        allowed_ciks=allowed_ciks,
    )
    values = [parse_decimal(value=str(claim["value"])) for claim in selected]
    computed = _formula_value(
        formula_id=str(branch["formula_id"]), values=values,
    )
    selected_reference_id = str(selected[0]["source_reference_id"])
    if selected_reference_id not in source_by_reference:
        raise ZeroAiReleaseError("Selected claim source is outside its role")
    reference, manifest = source_by_reference[selected_reference_id]
    source_binding = {
        "raw_asset_id": reference["raw_asset_id"],
        "source_reference_id": reference["source_reference_id"],
        "accession": reference["accession"],
        "document_name": reference["document_name"],
        "source_role": reference["source_role"],
        "source_set_manifest_id": manifest["source_set_manifest_id"],
        "selected_branch_id": branch["branch_id"],
        "rejected_branches": rejected,
        "verified_claim_ids": [claim["verified_claim_id"] for claim in selected],
        "source_reference_ids": sorted(
            {str(claim["source_reference_id"]) for claim in selected}
        ),
        "source_set_manifest_ids": sorted(
            {str(claim["source_set_manifest_id"]) for claim in selected}
        ),
    }
    observation = structured_observation(
        metric_id=metric_id,
        semantic_role="deterministic_value",
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        scope=scope,
        value=decimal_text(value=computed),
        unit=str(catalog_route["canonical_unit"]),
        quality=str(branch["quality"]),
        source_binding=source_binding,
    )
    not_meaningful = (
        branch["formula_id"] == "interest_coverage" and computed <= 0
    )
    if not not_meaningful:
        result, trace = calculate_observation_metric(
            compiled_spec=spec,
            target={
                "company_id": company_id,
                "period_start": period_start,
                "period_end": period_end,
                "scope": scope,
                "scope_key": scope_key(scope=scope),
            },
            company_traits=traits,
            observation=observation,
        )
    else:
        result, trace = _manual_result_trace(
            metric_id=metric_id,
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
            scope=scope,
            spec_closure_hash=str(spec["spec_closure_hash"]),
            applicability="APPLICABLE",
            quality="NOT_MEANINGFUL",
            reason_code="RATIO_NUMERATOR_NOT_POSITIVE",
            input_observation_ids=[str(observation["observation_id"])],
            steps=[
                {
                    "event": "NOT_MEANINGFUL",
                    "computed_value": observation["value"],
                }
            ],
            accession=reference["accession"],
            entity=str(int(registry_row["primary_cik"])),
        )
    return {
        "claims": selected,
        "observation": observation,
        "result": result,
        "trace": trace,
    }


def _structural_graph(
    *, context: Mapping[str, object], company_id: str, metric_id: str,
) -> Dict[str, object]:
    """Build one catalog-bound structural Result/Trace with no fake source."""
    target = context["targets"][company_id]
    scope = {
        "coverage": "metric_applicability_v1",
        "fiscal_year": target["fiscal_year"],
    }
    closure = content_hash(
        value={
            "metric_id": metric_id,
            "applicability_rule_id": "metric_applicability_v1",
            "deterministic_metric_catalog_sha256": sha256_file(
                path=context["repo_root"]
                / "catalog"
                / "deterministic_metrics.json"
            ),
        }
    )
    result, trace = _manual_result_trace(
        metric_id=metric_id,
        company_id=company_id,
        period_start=str(target["period_start"]),
        period_end=str(target["period_end"]),
        scope=scope,
        spec_closure_hash=closure,
        applicability="N_A_STRUCTURAL",
        quality="NONE",
        reason_code="TRAIT_NOT_APPLICABLE",
        input_observation_ids=[],
        steps=[{"event": "N_A_STRUCTURAL"}],
        accession=None,
        entity=None,
    )
    return {"claims": [], "observation": None, "result": result, "trace": trace}


def _event_graphs(
    *, context: Mapping[str, object], company_id: str,
    legacy_index: Mapping[Tuple[str, str], Mapping[str, str]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    """Project six event metrics and prove exact legacy event-key parity."""
    source = context["role_context"][(company_id, "fy_8k_item_inventory")]
    claims = []
    for event_set in source["sets"]:
        claims.extend(
            adapt_8k_item_index(
                filing_documents=event_set["documents"],
                source_set_manifest=event_set["manifest"],
                inventory_source_reference=event_set["inventory_reference"],
                inventory_bytes=event_set["inventory_bytes"],
            )
        )
    claims.sort(
        key=lambda claim: (
            str(claim["attributes"]["source_url"]),
            str(claim["attributes"]["accession"]),
            str(claim["attributes"]["item_code"]),
        )
    )
    display_name = context["registry"][company_id]["display_name"]
    target = context["event_targets"][company_id]
    all_events = [
        row for row in context["legacy_events"]
        if row["company"] == display_name
        and target["period_start"] <= row["filing_date"] <= target["period_end"]
    ]
    graphs = []
    parity = {}
    for metric_id in R2_EVENT_METRIC_IDS:
        projected = project_event_result(
            metric_id=metric_id,
            claims=claims,
            source_set_manifest=source["collection_manifest"],
            inventory_source_reference=source["inventory_reference"],
            target_period=target,
            catalog=context["event_catalog"],
        )
        legacy_row = legacy_index[(display_name, metric_id)]
        if projected["result"]["value"] != legacy_row["value"]:
            raise ZeroAiReleaseError(
                "Event Result differs from legacy: {}:{}:{}!={}".format(
                    company_id,
                    metric_id,
                    projected["result"]["value"],
                    legacy_row["value"],
                )
            )
        actual_keys = matched_event_key_set(
            metric_id=metric_id,
            claims=claims,
            catalog=context["event_catalog"],
        )
        route = context["event_catalog"]["routes"][metric_id]
        direct_codes = set(route["direct_item_codes"])
        keyword_rules = {
            str(rule["item_code"]): [
                normalize_event_text(value=str(alias))
                for alias in rule["aliases"]
            ]
            for rule in route["keyword_item_rules"]
        }
        expected_rows = []
        for row in all_events:
            item_code = str(row["item_code"])
            aliases = (
                keyword_rules[item_code] if item_code in keyword_rules else []
            )
            brief = normalize_event_text(value=str(row["brief"]))
            if item_code in direct_codes or any(
                alias in brief for alias in aliases
            ):
                expected_rows.append(row)
        expected_keys = sorted([
            {
                "source_url": row["source_url"],
                "accession": row["accession"],
                "item_code": row["item_code"],
            }
            for row in expected_rows
        ], key=lambda row: (
            row["source_url"], row["accession"], row["item_code"],
        ))
        if actual_keys != expected_keys:
            raise ZeroAiReleaseError(
                "Event key-set parity differs: {}:{}".format(
                    company_id, metric_id,
                )
            )
        parity[metric_id] = {
            "matched_event_keys": actual_keys,
            "matched_event_key_set_hash": content_hash(value=actual_keys),
        }
        graphs.append(projected)
    if graphs[0]["matched_verified_claim_ids"] != graphs[3][
        "matched_verified_claim_ids"
    ]:
        raise ZeroAiReleaseError("Shared event routes do not reuse exact claims")
    return claims, graphs, parity


def build_r2_execution_graph(
    *, repo_root: Path, source_context: Mapping[str, object],
) -> Dict[str, object]:
    """Build and validate all 220 cumulative Result coordinates.

    Args:
        repo_root: Repository authority root.
        source_context: Output of :func:`build_r2_source_plan`.

    Returns:
        Content-addressable graph, coordinates, and parity evidence.
    """
    context = {**dict(source_context), "repo_root": repo_root}
    legacy_rows = context["legacy_metrics"]
    legacy_index = {
        (row["company"], row["metric_id"]): row for row in legacy_rows
    }
    r1_coordinates = json.loads(
        context["active_view"].read_bytes(
            relative_path="internal/coordinate_index.json"
        ).decode("utf-8")
    )["coordinates"]
    if len(r1_coordinates) != 20:
        raise ZeroAiReleaseError("R1 coordinate predecessor differs")
    coordinates = [dict(row) for row in r1_coordinates]
    graph_records = []
    event_parity = {}
    missing_public_key_count = 2
    for registry_row in context["registry_rows"]:
        company_id = registry_row["company_id"]
        display_name = registry_row["display_name"]
        traits = repository_company_traits(
            repo_root=repo_root, company_id=company_id,
        )
        for metric_id in R2_DETERMINISTIC_METRIC_IDS:
            key = (display_name, metric_id)
            route = context["deterministic_catalog"]["metrics"][metric_id]
            if metric_is_applicable(
                applicability=route["applicability"], traits=traits,
            ):
                graph = _deterministic_metric_graph(
                    context=context,
                    company_id=company_id,
                    metric_id=metric_id,
                )
            else:
                graph = _structural_graph(
                    context=context,
                    company_id=company_id,
                    metric_id=metric_id,
                )
            if key not in legacy_index:
                missing_public_key_count += 1
            graph_records.extend(graph["claims"])
            if graph["observation"] is not None:
                graph_records.append(graph["observation"])
            graph_records.extend([graph["trace"], graph["result"]])
            coordinates.append(
                _coordinate(
                    company_id=company_id,
                    metric_id=metric_id,
                    result=graph["result"],
                    trace=graph["trace"],
                    period=context["targets"][company_id],
                )
            )
        claims, event_graphs, parity = _event_graphs(
            context=context,
            company_id=company_id,
            legacy_index=legacy_index,
        )
        graph_records.extend(claims)
        for metric_id, graph in zip(R2_EVENT_METRIC_IDS, event_graphs):
            graph_records.extend(
                [graph["observation"], graph["trace"], graph["result"]]
            )
            coordinates.append(
                _coordinate(
                    company_id=company_id,
                    metric_id=metric_id,
                    result=graph["result"],
                    trace=graph["trace"],
                    period=context["event_targets"][company_id],
                )
            )
        event_parity[company_id] = parity
    coordinates.sort(key=lambda row: (row["company_id"], row["metric_id"]))
    if (
        len(coordinates) != R2_EXPECTED_COORDINATES
        or len({(row["company_id"], row["metric_id"]) for row in coordinates})
        != R2_EXPECTED_COORDINATES
        or missing_public_key_count != R2_EXPECTED_NEW_KEYS
    ):
        raise ZeroAiReleaseError("R2 result coordinate exact set differs")
    graph_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_DETERMINISTIC_EXECUTION_GRAPH",
        "release_stage": "R2",
        "release_input_plan_id": context["plan"]["release_input_plan_id"],
        "predecessor_publication_id": context["active_view"].publication_id,
        "records": graph_records,
        "event_key_parity": event_parity,
        "legacy_events_sha256": context["legacy_events_sha256"],
        "filing_inventory_sha256": context["filing_inventory_sha256"],
    }
    return {
        **graph_body,
        "execution_graph_id": content_hash(value=graph_body),
        "coordinates": coordinates,
    }


def _r2_public_candidate(
    *, context: Mapping[str, object], graph: Mapping[str, object],
) -> Dict[str, object]:
    """Append the remaining structural keys and prove the exact public union."""
    view = context["active_view"]
    public_files = {
        relative: view.read_bytes(relative_path=relative)
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }
    # R2 changes executable semantics, so its active bundle must carry the
    # gates generated from this exact source tree rather than R1 gate bytes.
    for audit_relative in (
        "scalability_audit.csv", "semantic_audit_receipt.json",
    ):
        public_files[audit_relative] = (
            context["repo_root"] / "outputs" / audit_relative
        ).read_bytes()
    current_rows = _csv_rows(
        content=public_files["metrics_matrix.csv"], fields=METRICS_FIELDS,
    )
    current_keys = {(row["company"], row["metric_id"]) for row in current_rows}
    legacy_index = {
        (row["company"], row["metric_id"]): row
        for row in context["legacy_metrics"]
    }
    coordinates = {
        (row["company_id"], row["metric_id"]): row
        for row in graph["coordinates"]
    }
    metric_templates = {
        metric_id: next(
            row for row in context["legacy_metrics"]
            if row["metric_id"] == metric_id
        )
        for metric_id in R2_METRIC_IDS
    }
    additions = []
    coverage_additions = []
    for registry_row in context["registry_rows"]:
        company_id = registry_row["company_id"]
        display_name = registry_row["display_name"]
        for metric_id in R2_METRIC_IDS:
            key = (display_name, metric_id)
            if key in current_keys:
                continue
            coordinate = coordinates[(company_id, metric_id)]
            if (
                coordinate["applicability"] != "N_A_STRUCTURAL"
                or coordinate["value"] is not None
                or coordinate["unit"] is not None
            ):
                raise ZeroAiReleaseError("R2 added key is not structural")
            template = metric_templates[metric_id]
            reason = "Metric is structurally inapplicable to this company profile."
            additions.append(
                {
                    "company": display_name,
                    "cik": str(int(registry_row["primary_cik"])),
                    "metric_id": metric_id,
                    "metric_name": template["metric_name"],
                    "value": "",
                    "unit": "",
                    "status": "N_A_STRUCTURAL",
                    "source_class": "STRUCTURAL",
                    "formula": template["formula"],
                    "period_start": str(coordinate["period_start"]),
                    "period_end": str(coordinate["period_end"]),
                    "fiscal_year": str(coordinate["fiscal_year"]),
                    "fiscal_period": "FY",
                    "accession": "",
                    "form": "",
                    "filed_date": "",
                    "concept_or_section": "metric_applicability_v1",
                    "context_or_dimension": "company_traits",
                    "confidence": "1.00",
                    "notes": reason,
                }
            )
            coverage_additions.append(
                {
                    "company": display_name,
                    "metric_id": metric_id,
                    "status": "N_A_STRUCTURAL",
                    "source_class": "STRUCTURAL",
                    "has_numeric_value": "0",
                    "has_evidence": "0",
                    "needs_text_extraction": "0",
                    "needs_review": "0",
                    "reason": reason,
                }
            )
    additions.sort(key=lambda row: (row["company"], row["metric_id"]))
    coverage_additions.sort(key=lambda row: (row["company"], row["metric_id"]))
    if len(additions) != R2_EXPECTED_NEW_KEYS - 2:
        raise ZeroAiReleaseError("R2 incremental structural key count differs")
    public_files["metrics_matrix.csv"] = _append_csv_rows(
        original=public_files["metrics_matrix.csv"],
        fields=METRICS_FIELDS,
        rows=additions,
    )
    public_files["coverage_matrix.csv"] = _append_csv_rows(
        original=public_files["coverage_matrix.csv"],
        fields=COVERAGE_FIELDS,
        rows=coverage_additions,
    )
    row_count, key_hash = _public_key_proof(
        metrics_bytes=public_files["metrics_matrix.csv"]
    )
    companies = [row["display_name"] for row in context["registry_rows"]]
    expected_keys = {
        (row["company"], row["metric_id"])
        for row in context["legacy_metrics"]
    } | {
        (company, metric_id)
        for company in companies
        for metric_id in R2_METRIC_IDS
    }
    candidate_rows = _csv_rows(
        content=public_files["metrics_matrix.csv"], fields=METRICS_FIELDS,
    )
    actual_keys = {(row["company"], row["metric_id"]) for row in candidate_rows}
    if (
        row_count != R2_EXPECTED_PUBLIC_ROWS
        or actual_keys != expected_keys
        or len(actual_keys) != R2_EXPECTED_PUBLIC_ROWS
    ):
        raise ZeroAiReleaseError("R2 public key union differs")
    compatibility = []
    display_to_id = context["display_to_id"]
    for key in sorted(
        (key for key in legacy_index if key[1] in set(R2_METRIC_IDS))
    ):
        row = legacy_index[key]
        coordinate = coordinates[(display_to_id[key[0]], key[1])]
        expected_value = row["value"] if row["value"] else None
        if coordinate["value"] != expected_value:
            raise ZeroAiReleaseError("R2 strict compatibility value differs")
        compatibility.append(
            {
                "legacy_row": row,
                "result_id": coordinate["result_id"],
                "trace_id": coordinate["trace_id"],
            }
        )
    if len(compatibility) != R2_EXPECTED_LEGACY_ROWS:
        raise ZeroAiReleaseError("R2 replaced legacy row count differs")
    strict_hash = content_hash(value=compatibility)
    for markdown_path in ("README_RUN.md", "REPORT_十公司财务指标.md"):
        public_files[markdown_path] = _append_publication_note(
            original=public_files[markdown_path],
            release_stage="R2",
            cumulative_metric_ids=R2_METRIC_IDS,
            public_matrix_row_count=row_count,
        )
    return {
        "public_files": public_files,
        "public_matrix_row_count": row_count,
        "public_key_set_hash": key_hash,
        "strict_compatibility_hash": strict_hash,
        "compatibility": compatibility,
    }


def prepare_r2_successor(
    *, repo_root: Path, publication_root: Path, source_commit: str,
    validated_at_utc: str,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Prepare one verified R2 successor without committing the pointer.

    Args:
        repo_root: Repository authority and active R1 source root.
        publication_root: Bundle storage root; may be temporary for dry runs.
        source_commit: Clean committed R2 implementation SHA.
        validated_at_utc: Explicit UTC receipt time.

    Returns:
        Prepared PublicationManifest and evidence summary.
    """
    source_binding = _source_commit_binding(
        repo_root=repo_root, source_commit=source_commit,
    )
    context = build_r2_source_plan(repo_root=repo_root)
    graph = build_r2_execution_graph(
        repo_root=repo_root, source_context=context,
    )
    candidate = _r2_public_candidate(context=context, graph=graph)
    retirement = _retirement_receipt(
        repo_root=repo_root,
        cumulative_metric_ids=R2_METRIC_IDS,
        publication_stage="R2",
    )
    invocation = structured_only_result(
        repo_root=repo_root,
        workspace_dir=(
            repo_root / "artifacts" / "vnext" / "zero_ai_release" / "r2"
        ),
        release_input_plan_id=str(context["plan"]["release_input_plan_id"]),
        cumulative_metric_ids=R2_METRIC_IDS,
        result_coordinate_count=R2_EXPECTED_COORDINATES,
    )
    issue_release = load_issue15_release_plan(
        repo_root=repo_root, release_plan_id="issue_15_zero_ai_r2",
    )
    coordinate_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_COORDINATE_INDEX",
        "release_stage": "R2",
        "release_input_plan_id": context["plan"]["release_input_plan_id"],
        "coordinates": graph["coordinates"],
    }
    coordinate_index = _receipt(
        body=coordinate_body, identity_field="batch_manifest_id",
    )
    ledger_binding, locator_bytes = _ledger_binding(
        repo_root=repo_root,
        plan=context["plan"],
        locator_proofs=context["proofs"],
    )
    graph_bytes = _json_bytes(
        value={
            field: graph[field]
            for field in graph
            if field != "coordinates"
        }
    )
    internal_files = {
        "internal/release_input_plan.json": _json_bytes(value=context["plan"]),
        "internal/coordinate_index.json": _json_bytes(value=coordinate_index),
        "internal/deterministic_execution_graph.json": graph_bytes,
        "internal/issue15_release_plan.json": (
            repo_root / "config" / "release_plans"
            / "issue_15_zero_ai_r2.json"
        ).read_bytes(),
        "internal/request_locator_provenance.json": locator_bytes,
        "internal/retirement_receipt.json": _json_bytes(value=retirement),
        "internal/structured_only_invocation.json": _json_bytes(value=invocation),
    }
    issue = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "issue_15_v1"
    )
    active_view = context["active_view"]
    projection_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_PROJECTION_MANIFEST",
        "status": "PUBLISHABLE",
        "release_stage": "R2",
        "release_input_plan_id": context["plan"]["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "previous_publication_id": active_view.publication_id,
        "cumulative_metric_ids": list(R2_METRIC_IDS),
        "result_coordinate_count": R2_EXPECTED_COORDINATES,
        "replaced_legacy_row_count": R2_EXPECTED_LEGACY_ROWS,
        "new_public_key_count": R2_EXPECTED_NEW_KEYS,
        "public_matrix_row_count": candidate["public_matrix_row_count"],
        "public_key_set_hash": candidate["public_key_set_hash"],
        "strict_compatibility_hash": candidate["strict_compatibility_hash"],
        "requirement_closure_hash": issue["requirement_closure_hash"],
    }
    projection = _receipt(
        body=projection_body, identity_field="projection_manifest_id",
    )
    migration = _receipt(
        body={
            "schema_version": 1,
            "record_type": "ZERO_AI_STRICT_COMPATIBILITY_RECEIPT",
            "status": "PASSED",
            "release_stage": "R2",
            "projection_manifest_id": projection["projection_manifest_id"],
            "replaced_legacy_row_count": R2_EXPECTED_LEGACY_ROWS,
            "new_public_key_count": R2_EXPECTED_NEW_KEYS,
            "removed_metric_ids": [],
            "removed_public_keys": [],
            "strict_compatibility_hash": candidate["strict_compatibility_hash"],
            "public_key_set_hash": candidate["public_key_set_hash"],
            "retirement_receipt_id": retirement["retirement_receipt_id"],
        },
        identity_field="strict_compatibility_receipt_id",
    )
    validation = _receipt(
        body={
            "schema_version": 1,
            "record_type": "ZERO_AI_PUBLICATION_VALIDATION_RECEIPT",
            "status": "PASSED",
            "release_stage": "R2",
            "projection_manifest_id": projection["projection_manifest_id"],
            "batch_manifest_id": coordinate_index["batch_manifest_id"],
            "checks": [
                "IMMUTABLE_SOURCE_ATTEMPTS",
                "SOURCE_SET_COMPLETENESS",
                "DETERMINISTIC_RESULT_TRACE_EXACT_SET",
                "EVENT_KEY_SET_LEGACY_PARITY",
                "STRICT_COMPATIBILITY",
                "PUBLIC_KEY_UNION",
                "PUBLICATION_BOUND_RETIREMENT",
                "STRUCTURED_ONLY_ZERO_PROVIDER",
            ],
            "counters": dict(invocation["counters"]),
            "validated_at_utc": validated_at_utc,
        },
        identity_field="validation_receipt_id",
    )
    public_files = dict(candidate["public_files"])
    public_files["projection_manifest.json"] = _json_bytes(value=projection)
    public_files["legacy_invariant_migration_receipt.json"] = _json_bytes(
        value=migration
    )
    public_files["publication_validation_receipt.json"] = _json_bytes(
        value=validation
    )
    public_files["validation_run_manifest.json"] = _json_bytes(
        value={
            "run_id": str(coordinate_index["batch_manifest_id"]),
            "source_commit": source_commit,
            "started_at_utc": validated_at_utc,
            "mode": "LIGHT_REVIEW_MODE",
            "refreshed_artifacts": sorted(
                [
                    "coverage_matrix.csv",
                    "legacy_invariant_migration_receipt.json",
                    "metrics_matrix.csv",
                    "projection_manifest.json",
                    "publication_validation_receipt.json",
                    "validation_run_manifest.json",
                ]
            ),
            "not_refreshed_artifacts": [
                "issue_15_full_acceptance.not_run"
            ],
            "result": "PASSED_WITH_CAVEATS",
        }
    )
    public_hashes = {
        relative: sha256_bytes(content=public_files[relative])
        for relative in sorted(REQUIRED_BUNDLE_FILES)
    }
    marker_body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_FORMAL_RELEASE_RECEIPT",
        "status": "PASSED",
        "release_stage": "R2",
        "source_commit": source_binding["source_commit"],
        "source_tree_oid": source_binding["source_tree_oid"],
        "release_input_plan_id": context["plan"]["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "projection_manifest_id": projection["projection_manifest_id"],
        "validation_receipt_id": validation["validation_receipt_id"],
        "previous_publication_id": active_view.publication_id,
        "cumulative_metric_ids": list(R2_METRIC_IDS),
        "result_coordinate_count": R2_EXPECTED_COORDINATES,
        "replaced_legacy_row_count": R2_EXPECTED_LEGACY_ROWS,
        "new_public_key_count": R2_EXPECTED_NEW_KEYS,
        "public_matrix_row_count": candidate["public_matrix_row_count"],
        "public_key_set_hash": candidate["public_key_set_hash"],
        "strict_compatibility_hash": candidate["strict_compatibility_hash"],
        "requirement_closure_hash": issue["requirement_closure_hash"],
        "issue15_release_plan_id": issue_release["release_plan"][
            "release_plan_id"
        ],
        "issue15_release_plan_content_id": issue_release[
            "release_plan_content_id"
        ],
        "issue15_release_plan_sha256": issue_release[
            "release_plan_sha256"
        ],
        "source_locator_classes": sorted(
            {
                str(proof["request_locator_kind"])
                for proof in context["proofs"].values()
            }
        ),
        "invocation_observation_id": invocation[
            "invocation_observation_id"
        ],
        "counters": dict(invocation["counters"]),
        "public_artifact_hashes": public_hashes,
        "internal_files": _internal_bindings(files=internal_files),
    }
    marker = _receipt(
        body=marker_body, identity_field="zero_ai_release_receipt_id",
    )
    files = {
        **public_files,
        **internal_files,
        ZERO_AI_FORMAL_MANIFEST: _json_bytes(value=marker),
    }
    parent = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements" / "ai_first_v3_3_1"
    )
    layout = publication_layout(publication_root=publication_root)
    successor = _write_prepared_publication_bundle(
        publications_dir=Path(layout["publications_dir"]),
        files=files,
        requirement_hashes=parent["hashes"],
        batch_manifest_id=str(coordinate_index["batch_manifest_id"]),
        projection_manifest_id=str(projection["projection_manifest_id"]),
        validation_receipt_id=str(validation["validation_receipt_id"]),
        ledger_binding=ledger_binding,
        previous_publication_id=active_view.publication_id,
    )
    summary = {
        "release_stage": "R2",
        "source_commit": source_binding["source_commit"],
        "source_tree_oid": source_binding["source_tree_oid"],
        "release_input_plan_id": context["plan"]["release_input_plan_id"],
        "batch_manifest_id": coordinate_index["batch_manifest_id"],
        "projection_manifest_id": projection["projection_manifest_id"],
        "validation_receipt_id": validation["validation_receipt_id"],
        "zero_ai_release_receipt_id": marker["zero_ai_release_receipt_id"],
        "retirement_receipt_id": retirement["retirement_receipt_id"],
        "strict_compatibility_receipt_id": migration[
            "strict_compatibility_receipt_id"
        ],
        "public_matrix_row_count": candidate["public_matrix_row_count"],
        "public_key_set_hash": candidate["public_key_set_hash"],
        "strict_compatibility_hash": candidate["strict_compatibility_hash"],
        "invocation_observation_id": invocation[
            "invocation_observation_id"
        ],
        "counters": dict(invocation["counters"]),
        "retirement_receipt": retirement,
        "strict_compatibility_receipt": migration,
    }
    return successor, summary


def _persist_r2_receipts(
    *, repo_root: Path, receipts: Mapping[str, Mapping[str, object]],
    counters: Mapping[str, object],
) -> Dict[str, object]:
    """Persist immutable R2 receipts plus one stable role index."""
    receipt_dir = repo_root / "outputs" / "zero_ai_release_receipts" / "r2"
    if receipt_dir.is_symlink() or (
        receipt_dir.exists() and not receipt_dir.is_dir()
    ):
        raise ZeroAiReleaseError("R2 receipt directory is unsafe")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    bindings = {}
    for role in sorted(receipts):
        content = _json_bytes(value=receipts[role])
        digest = sha256_bytes(content=content)
        path = receipt_dir / "{}.json".format(digest)
        if path.exists() and path.read_bytes() != content:
            raise ZeroAiReleaseError("R2 content-addressed receipt differs")
        if not path.exists():
            atomic_write_bytes(path=path, content=content)
        bindings[role] = {
            "path": path.relative_to(repo_root).as_posix(),
            "sha256": digest,
            "size": len(content),
        }
    index = _receipt(
        body={
            "schema_version": 1,
            "record_type": "ZERO_AI_R2_RECEIPT_INDEX",
            "status": "PASSED",
            "receipts": bindings,
            "counters": dict(counters),
        },
        identity_field="receipt_index_id",
    )
    atomic_write_bytes(
        path=receipt_dir / "index.json", content=_json_bytes(value=index),
    )
    return index


def publish_r2(
    *, repo_root: Path, source_commit: str, committed_at_utc: str,
) -> Dict[str, object]:
    """Prepare, commit, and read back the formal R2 successor.

    Args:
        repo_root: Repository-owned formal publication root.
        source_commit: Clean committed R2 implementation SHA.
        committed_at_utc: Explicit UTC validation and commit timestamp.

    Returns:
        Final active ID, matrix/key proof, counters, and receipt index.
    """
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ZeroAiReleaseError("R2 source commit must be a full SHA")
    source_snapshot = capture_source_snapshot(workdir=repo_root)
    predecessor = PublicationView.open(publication_root=repo_root)
    successor, summary = prepare_r2_successor(
        repo_root=repo_root,
        publication_root=repo_root,
        source_commit=source_commit,
        validated_at_utc=committed_at_utc,
    )
    retirement = summary.pop("retirement_receipt")
    compatibility = summary.pop("strict_compatibility_receipt")
    pointer = _commit_publication(
        publication_root=repo_root,
        publication_id=str(successor["publication_id"]),
        expected_active_publication_id=predecessor.publication_id,
        committed_at_utc=committed_at_utc,
    )
    read_back = _read_back_proof(
        repo_root=repo_root,
        expected_publication_id=str(successor["publication_id"]),
    )
    index = _persist_r2_receipts(
        repo_root=repo_root,
        counters=summary["counters"],
        receipts={
            "predecessor_r1": predecessor.manifest,
            "successor_publication": successor,
            "active_terminal": pointer,
            "immutable_read_back": read_back,
            "retirement": retirement,
            "strict_compatibility": compatibility,
        },
    )
    publish_validation_snapshot(
        workdir=repo_root, source_snapshot=source_snapshot,
    )
    return {
        **summary,
        "previous_publication_id": predecessor.publication_id,
        "active_publication_id": successor["publication_id"],
        "receipt_index_id": index["receipt_index_id"],
        "receipt_index_path": "outputs/zero_ai_release_receipts/r2/index.json",
        "committed_at_utc": committed_at_utc,
    }
