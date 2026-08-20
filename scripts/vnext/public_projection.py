"""Render zero-AI public rows independently and compare frozen legacy rows.

Production rendering consumes only registry identities, MetricResult,
ExecutionTrace, claims/observations, SourceReference/raw SEC bytes, filing
inventory, and the repository projection catalog. Frozen legacy rows enter a
separate compatibility function after rendering and never select a field.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .canonical import content_hash, sha256_file, strict_json_file
from .records import validate_record
from .sources import companyfacts_structured_facts, load_raw_blob_bytes


METRICS_FIELDS = (
    "company", "cik", "metric_id", "metric_name", "value", "unit",
    "status", "source_class", "formula", "period_start", "period_end",
    "fiscal_year", "fiscal_period", "accession", "form", "filed_date",
    "concept_or_section", "context_or_dimension", "confidence", "notes",
)
COVERAGE_FIELDS = (
    "company", "metric_id", "status", "source_class",
    "has_numeric_value", "has_evidence", "needs_text_extraction",
    "needs_review", "reason",
)
ZERO_AI_METRIC_IDS = {
    "A01", "A02", "A05", "A06", "A07", "A08", "A10", "B01", "B02",
    "B03", "B04", "B05", "B07", "B08", "B09", "B12", "C01", "E01",
    "E02", "E03", "E04", "E05",
}
CATALOG_FIELDS = {
    "approved_deltas", "common_continuity_projection",
    "common_structural_projection", "event_window_policy_by_continuity",
    "metrics", "record_type", "renderer_semantic_version", "schema_version",
}
METRIC_FIELDS = {
    "approximate_overlay", "continuity_overlay", "formula", "metric_name",
    "not_meaningful_overlay", "role_overlays", "structural_overlay",
    "success_projection", "zero_overlay",
}
PROJECTION_FIELDS = {
    "accession_policy", "concept_policy", "confidence", "context_policy",
    "filed_date_policy", "fiscal_period", "fiscal_year_policy", "form_policy",
    "formula", "note_enrichment", "notes_template", "source_class", "status",
}
ROLE_OVERLAY_FIELDS = {"overlay", "semantic_roles_exact"}


class PublicProjectionError(ValueError):
    """Report invalid authority, graph bindings, rendering, or compatibility."""


def _object(*, value: object, label: str) -> Dict[str, object]:
    """Return one isolated object or fail fast."""
    if not isinstance(value, dict):
        raise PublicProjectionError("{} must be an object".format(label))
    return dict(value)


def _text(*, value: object, label: str) -> str:
    """Return one required text scalar, allowing an explicit empty value."""
    if not isinstance(value, str):
        raise PublicProjectionError("{} must be text".format(label))
    return value


def _validate_overlay(*, value: object, label: str) -> Optional[Dict[str, object]]:
    """Validate one optional projection overlay."""
    if value is None:
        return None
    overlay = _object(value=value, label=label)
    if not set(overlay).issubset(PROJECTION_FIELDS):
        raise PublicProjectionError("{} fields differ".format(label))
    return overlay


def _validate_projection(*, value: object, label: str) -> Dict[str, object]:
    """Validate one complete projection policy."""
    projection = _object(value=value, label=label)
    if set(projection) != PROJECTION_FIELDS:
        raise PublicProjectionError("{} fields are not exact".format(label))
    for field in PROJECTION_FIELDS - {"note_enrichment"}:
        _text(value=projection[field], label="{}.{}".format(label, field))
    enrichment = projection["note_enrichment"]
    if enrichment is not None and not isinstance(enrichment, dict):
        raise PublicProjectionError("{} enrichment is invalid".format(label))
    return projection


def load_public_projection_catalog(
    *, repo_root: Path, expected_metric_ids: Sequence[str],
) -> Dict[str, object]:
    """Load and validate the exact zero-AI public projection authority."""
    path = repo_root / "catalog" / "zero_ai_public_projection.json"
    if path.is_symlink() or not path.is_file():
        raise PublicProjectionError("Public projection catalog is unsafe")
    value = _object(
        value=strict_json_file(path=path), label="public projection catalog"
    )
    if (
        set(value) != CATALOG_FIELDS
        or value["schema_version"] != 1
        or value["record_type"] != "ZERO_AI_PUBLIC_PROJECTION_CATALOG"
        or value["renderer_semantic_version"] != "1"
        or value["approved_deltas"] != []
    ):
        raise PublicProjectionError("Public projection catalog root differs")
    metrics = _object(value=value["metrics"], label="projection metrics")
    if (
        set(metrics) != ZERO_AI_METRIC_IDS
        or not set(expected_metric_ids).issubset(set(metrics))
    ):
        raise PublicProjectionError("Public projection metric exact set differs")
    common_structural = _validate_projection(
        value=value["common_structural_projection"],
        label="common structural projection",
    )
    common_continuity = _validate_projection(
        value=value["common_continuity_projection"],
        label="common continuity projection",
    )
    validated_metrics = {}
    for metric_id in sorted(metrics):
        metric = _object(
            value=metrics[metric_id], label="metric projection " + metric_id
        )
        if set(metric) != METRIC_FIELDS:
            raise PublicProjectionError("Metric projection fields differ")
        _text(value=metric["metric_name"], label="metric name")
        _text(value=metric["formula"], label="metric formula")
        metric["success_projection"] = _validate_projection(
            value=metric["success_projection"],
            label=metric_id + " success projection",
        )
        for field in (
            "approximate_overlay", "continuity_overlay",
            "not_meaningful_overlay", "structural_overlay", "zero_overlay",
        ):
            metric[field] = _validate_overlay(
                value=metric[field], label=metric_id + " " + field,
            )
        if not isinstance(metric["role_overlays"], list):
            raise PublicProjectionError("Role overlays must be an array")
        role_overlays = []
        for role_value in metric["role_overlays"]:
            role = _object(value=role_value, label="role overlay")
            if set(role) != ROLE_OVERLAY_FIELDS:
                raise PublicProjectionError("Role overlay fields differ")
            roles = role["semantic_roles_exact"]
            if (
                not isinstance(roles, list)
                or not roles
                or any(not isinstance(item, str) or not item for item in roles)
                or roles != sorted(set(roles))
            ):
                raise PublicProjectionError("Role overlay set is invalid")
            role_overlays.append({
                "semantic_roles_exact": list(roles),
                "overlay": _validate_overlay(
                    value=role["overlay"], label="role projection overlay",
                ),
            })
        metric["role_overlays"] = role_overlays
        validated_metrics[metric_id] = metric
    windows = _object(
        value=value["event_window_policy_by_continuity"],
        label="event window policies",
    )
    if set(windows) != {"continuous", "successor_predecessor"}:
        raise PublicProjectionError("Event window policy exact set differs")
    return {
        **value,
        "metrics": validated_metrics,
        "common_structural_projection": common_structural,
        "common_continuity_projection": common_continuity,
        "catalog_sha256": sha256_file(path=path),
        "approved_delta_authority_hash": content_hash(value=[]),
    }


def projection_xbrl_concepts(
    *, catalog: Mapping[str, object],
) -> List[str]:
    """Return the exact catalog-declared projection-only XBRL concepts."""
    concepts = []
    for metric in catalog["metrics"].values():
        projections = [metric["success_projection"]]
        projections.extend(
            metric[field]
            for field in (
                "approximate_overlay", "continuity_overlay",
                "not_meaningful_overlay", "structural_overlay",
                "zero_overlay",
            )
            if metric[field] is not None
        )
        projections.extend(
            role["overlay"] for role in metric["role_overlays"]
        )
        for projection in projections:
            enrichment = (
                projection["note_enrichment"]
                if "note_enrichment" in projection else None
            )
            if enrichment is None or enrichment["kind"] != (
                "ACCESSION_XBRL_CONCEPT_VALUES"
            ):
                continue
            for concept in enrichment["concepts"]:
                if concept not in concepts:
                    concepts.append(str(concept))
    return concepts


def event_target_period(
    *, target_period: Mapping[str, object], continuity_status: str,
    catalog: Mapping[str, object],
) -> Dict[str, object]:
    """Derive an event window from target period and continuity authority."""
    policies = catalog["event_window_policy_by_continuity"]
    if continuity_status not in policies:
        raise PublicProjectionError("Event continuity policy is absent")
    policy = policies[continuity_status]
    if policy == "TARGET_PERIOD":
        period_start = str(target_period["period_start"])
    elif policy == "PRIOR_CALENDAR_YEAR_START_TO_TARGET_END":
        period_start = "{}-01-01".format(
            int(target_period["fiscal_year"]) - 1
        )
    else:
        raise PublicProjectionError("Event window policy is unsupported")
    return {
        "fiscal_year": target_period["fiscal_year"],
        "period_start": period_start,
        "period_end": str(target_period["period_end"]),
    }


def _record_indexes(
    *, records: Sequence[Mapping[str, object]],
    source_references: Sequence[Mapping[str, object]],
    projection_claims: Sequence[Mapping[str, object]],
) -> Dict[str, Dict[str, Mapping[str, object]]]:
    """Build exact record indexes needed by projection."""
    result = {}
    trace = {}
    observation = {}
    claim = {}
    source = {}
    raw_blob = {}
    for record_value in list(records) + list(projection_claims):
        record = dict(record_value)
        record_type = str(record["record_type"])
        if record_type in {
            "METRIC_RESULT", "EXECUTION_TRACE", "VERIFIED_OBSERVATION",
            "DETERMINISTIC_VERIFIED_CLAIM", "SOURCE_REFERENCE", "RAW_BLOB",
        }:
            validate_record(record=record)
        if record_type == "METRIC_RESULT":
            result[str(record["result_id"])] = record
        elif record_type == "EXECUTION_TRACE":
            trace[str(record["trace_id"])] = record
        elif record_type == "VERIFIED_OBSERVATION":
            observation[str(record["observation_id"])] = record
        elif record_type == "DETERMINISTIC_VERIFIED_CLAIM":
            claim[str(record["verified_claim_id"])] = record
        elif record_type == "SOURCE_REFERENCE":
            source[str(record["source_reference_id"])] = record
        elif record_type == "RAW_BLOB":
            raw_blob[str(record["raw_asset_id"])] = record
    for reference_value in source_references:
        reference = validate_record(record=reference_value)
        source[str(reference["source_reference_id"])] = reference
    return {
        "result": result, "trace": trace, "observation": observation,
        "claim": claim, "source": source, "raw_blob": raw_blob,
    }


def _local_name(*, value: str) -> str:
    """Return the local concept token while preserving original case."""
    return value.split(":", maxsplit=1)[-1]


def _filing_dates(
    *, filing_inventory: Sequence[Mapping[str, str]],
) -> Dict[str, str]:
    """Return accession-to-filed-date mapping from SEC filing inventory."""
    output = {}
    for row in filing_inventory:
        accession = str(row["accession"])
        filed = str(row["filingDate"])
        if accession in output and output[accession] != filed:
            raise PublicProjectionError("Filing date identity is ambiguous")
        output[accession] = filed
    return output


def _companyfacts_frame(
    *, repo_root: Path, source_binding: Mapping[str, object],
    indexes: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> str:
    """Recover one exact CompanyFacts frame from immutable raw bytes."""
    if "frame" in source_binding and isinstance(source_binding["frame"], str):
        return str(source_binding["frame"])
    source_id = str(source_binding["source_reference_id"])
    if source_id not in indexes["source"]:
        raise PublicProjectionError("CompanyFacts SourceReference is absent")
    reference = indexes["source"][source_id]
    raw_id = str(reference["raw_asset_id"])
    if raw_id not in indexes["raw_blob"]:
        raise PublicProjectionError("CompanyFacts RawBlob is absent")
    raw_blob = indexes["raw_blob"][raw_id]
    raw_bytes = load_raw_blob_bytes(repo_root=repo_root, raw_blob=raw_blob)
    facts = companyfacts_structured_facts(
        raw_bytes=raw_bytes,
        source_reference=reference,
        approved_concepts=[str(source_binding["concept"])],
        allowed_ciks=[str(source_binding["entity"])],
        include_instant=True,
    )
    matches = [
        fact for fact in facts
        if fact["fact_id"] == source_binding["fact_id"]
    ]
    if len(matches) != 1:
        raise PublicProjectionError("CompanyFacts frame fact is ambiguous")
    return str(matches[0]["source_binding"]["frame"])


def _claim_entry(
    *, claim: Mapping[str, object], indexes: Mapping[str, object],
    filing_dates: Mapping[str, str], repo_root: Path,
) -> Dict[str, str]:
    """Normalize one selected deterministic claim for public projection."""
    reference = indexes["source"][str(claim["source_reference_id"])]
    attributes = claim["attributes"]
    claim_kind = str(claim["claim_kind"])
    if claim_kind == "COMPANYFACTS_NUMERIC_FACT":
        binding = {
            "source_reference_id": claim["source_reference_id"],
            "concept": claim["locator"]["concept"],
            "entity": attributes["entity"],
            "fact_id": claim["locator"]["fact_id"],
        }
        if "frame" in attributes:
            binding["frame"] = attributes["frame"]
        frame = _companyfacts_frame(
            repo_root=repo_root, source_binding=binding, indexes=indexes,
        )
        return {
            "accession": str(attributes["accession"]),
            "form": str(attributes["form"]),
            "filed_date": str(attributes["filed"]),
            "concept": _local_name(value=str(claim["locator"]["concept"])),
            "context": "companyfacts:{}:{}".format(claim["unit"], frame),
        }
    if "canonical_name" not in attributes:
        raise PublicProjectionError("XBRL claim canonical name is absent")
    context = attributes["context"]
    dimensions = context["dimensions"]
    context_text = (
        ";".join(
            "{}={}".format(name, dimensions[name]) for name in dimensions
        )
        if dimensions else str(context["context_ref"])
    )
    accession = str(reference["accession"])
    return {
        "accession": accession,
        "form": "",
        "filed_date": filing_dates[accession]
        if accession in filing_dates else "",
        "concept": _local_name(value=str(attributes["canonical_name"])),
        "context": context_text,
    }


def _observation_entry(
    *, observation: Mapping[str, object], indexes: Mapping[str, object],
    repo_root: Path,
) -> Dict[str, str]:
    """Normalize one R1 structured observation for public projection."""
    binding = observation["source_binding"]
    frame = _companyfacts_frame(
        repo_root=repo_root, source_binding=binding, indexes=indexes,
    )
    return {
        "accession": str(binding["accession"]),
        "form": str(binding["form"]),
        "filed_date": str(binding["filed"]),
        "concept": _local_name(value=str(binding["concept"])),
        "context": "companyfacts:{}:{}".format(observation["unit"], frame),
    }


def _selected_evidence(
    *, trace: Mapping[str, object], indexes: Mapping[str, object],
    filing_dates: Mapping[str, str], repo_root: Path,
) -> Tuple[List[Dict[str, str]], List[Mapping[str, object]], List[str]]:
    """Return ordered public evidence entries, observations, and claim IDs."""
    observations = []
    for observation_id in trace["input_observation_ids"]:
        if observation_id not in indexes["observation"]:
            raise PublicProjectionError("Trace observation is absent")
        observations.append(indexes["observation"][observation_id])
    verified_claim_ids = []
    entries = []
    for observation in observations:
        binding = observation["source_binding"]
        if "matched_verified_claim_ids" in binding:
            continue
        claim_ids = list(
            binding["verified_claim_ids"]
            if "verified_claim_ids" in binding else []
        )
        if claim_ids:
            for claim_id in claim_ids:
                if claim_id not in indexes["claim"]:
                    raise PublicProjectionError("Selected claim is absent")
                entry = _claim_entry(
                    claim=indexes["claim"][claim_id], indexes=indexes,
                    filing_dates=filing_dates, repo_root=repo_root,
                )
                entry["role"] = str(observation["semantic_role"])
                entries.append(entry)
                verified_claim_ids.append(claim_id)
        else:
            entry = _observation_entry(
                observation=observation, indexes=indexes,
                repo_root=repo_root,
            )
            entry["role"] = str(observation["semantic_role"])
            entries.append(entry)
    return entries, observations, verified_claim_ids


def _merge_projection(
    *, base: Mapping[str, object], overlay: Optional[Mapping[str, object]],
) -> Dict[str, object]:
    """Merge one catalog-validated optional overlay onto a complete policy."""
    output = dict(base)
    if overlay is not None:
        output.update(dict(overlay))
    if set(output) != PROJECTION_FIELDS:
        raise PublicProjectionError("Merged projection fields differ")
    return output


def _projection_policy(
    *, metric: Mapping[str, object], result: Mapping[str, object],
    observations: Sequence[Mapping[str, object]], catalog: Mapping[str, object],
) -> Dict[str, object]:
    """Select one declarative projection using only Result/Trace state."""
    if result["applicability"] == "N_A_STRUCTURAL":
        return _merge_projection(
            base=catalog["common_structural_projection"],
            overlay=metric["structural_overlay"],
        )
    if result["reason_code"] == "ENTITY_CONTINUITY_NOT_COMPARABLE":
        if metric["continuity_overlay"] is None:
            raise PublicProjectionError("Continuity projection is absent")
        return _merge_projection(
            base=catalog["common_continuity_projection"],
            overlay=metric["continuity_overlay"],
        )
    projection = dict(metric["success_projection"])
    if result["quality"] == "NOT_MEANINGFUL":
        return _merge_projection(
            base=catalog["common_continuity_projection"],
            overlay=metric["not_meaningful_overlay"],
        )
    if result["value"] == "0" and metric["zero_overlay"] is not None:
        return _merge_projection(
            base=projection, overlay=metric["zero_overlay"],
        )
    if result["quality"] == "APPROX" and metric["approximate_overlay"] is not None:
        return _merge_projection(
            base=projection, overlay=metric["approximate_overlay"],
        )
    roles = sorted(str(observation["semantic_role"]) for observation in observations)
    matches = [
        role for role in metric["role_overlays"]
        if role["semantic_roles_exact"] == roles
    ]
    if len(matches) > 1:
        raise PublicProjectionError("Role projection is ambiguous")
    return _merge_projection(
        base=projection,
        overlay=matches[0]["overlay"] if matches else None,
    )


def _event_references(
    *, observation: Mapping[str, object], indexes: Mapping[str, object],
    policy: str,
) -> List[Mapping[str, object]]:
    """Return matched or complete event SourceReferences without duplicates."""
    binding = observation["source_binding"]
    if policy == "MATCHED_EVENTS":
        reference_ids = [
            indexes["claim"][claim_id]["source_reference_id"]
            for claim_id in binding["matched_verified_claim_ids"]
        ]
    elif policy == "ALL_EVENTS":
        reference_ids = list(binding["ordered_source_reference_ids"])
    else:
        return []
    output = []
    accessions = set()
    for reference_id in reference_ids:
        reference = indexes["source"][str(reference_id)]
        accession = str(reference["accession"])
        if accession.startswith("SUBMISSIONS-") or accession in accessions:
            continue
        accessions.add(accession)
        output.append(reference)
    if policy == "MATCHED_EVENTS":
        inventory = indexes["source"][str(binding["source_reference_id"])]
        document_name = str(inventory["document_name"])
        if not document_name.startswith("CIK") or not document_name.endswith(
            ".json"
        ):
            raise PublicProjectionError("Event inventory CIK is invalid")
        primary_cik = str(int(document_name[3:-5]))
        return sorted(
            output,
            key=lambda reference: (
                0 if "/data/{}/".format(primary_cik) in str(
                    reference["source_url"]
                ) else 1,
                str(reference["accession"]),
            ),
        )
    return sorted(output, key=lambda reference: str(reference["accession"]))


def _policy_value(
    *, policy: str, field: str, evidence: Sequence[Mapping[str, str]],
    trace: Mapping[str, object], observation: Optional[Mapping[str, object]],
    indexes: Mapping[str, object], filing_dates: Mapping[str, str],
) -> str:
    """Resolve one declared source-field policy without legacy input."""
    if policy == "EMPTY":
        return ""
    if policy.startswith("STATIC:") or policy.startswith("LITERAL:"):
        return policy.split(":", maxsplit=1)[1]
    if policy == "TRACE_ACCESSION":
        accession = trace["calculation_target"]["accession"]
        return "" if accession is None else str(accession)
    if policy in {"MATCHED_EVENTS", "ALL_EVENTS"}:
        if observation is None:
            raise PublicProjectionError("Event observation is absent")
        references = _event_references(
            observation=observation, indexes=indexes, policy=policy,
        )
        if field == "accession":
            return ";".join(str(reference["accession"]) for reference in references)
        if field == "filed_date":
            observed_dates = [
                filing_dates[str(reference["accession"])]
                for reference in references
                if str(reference["accession"]) in filing_dates
            ]
            dates = (
                sorted(set(observed_dates))
                if policy == "ALL_EVENTS" else observed_dates
            )
            return ";".join(dates)
        raise PublicProjectionError("Event policy owns no requested field")
    if policy.startswith("EVIDENCE_ROLES:"):
        roles = policy.split(":", maxsplit=1)[1].split(",")
        order = {role: ordinal for ordinal, role in enumerate(roles)}
        selected = sorted(
            evidence,
            key=lambda entry: (
                order[str(entry["role"])]
                if str(entry["role"]) in order else len(order)
            ),
        )
        separator = "+" if field == "concept" else ";"
        return separator.join(str(entry[field]) for entry in selected)
    if policy == "EVIDENCE":
        separator = "+" if field == "concept" else ";"
        return separator.join(str(entry[field]) for entry in evidence)
    if policy == "EVIDENCE_UNIQUE":
        values = []
        for entry in evidence:
            value = str(entry[field])
            if value and value not in values:
                values.append(value)
        if len(values) > 1:
            raise PublicProjectionError("Evidence unique value is ambiguous")
        return values[0] if values else ""
    raise PublicProjectionError("Projection field policy is unsupported")


def _unselected_xbrl_enrichment(
    *, company_id: str, selected_claim_ids: Sequence[str],
    indexes: Mapping[str, object],
) -> str:
    """Format unselected same-concept XBRL candidates from claim authority."""
    if not selected_claim_ids:
        raise PublicProjectionError("Basel selected claim is absent")
    selected = indexes["claim"][selected_claim_ids[0]]
    canonical_name = selected["attributes"]["canonical_name"]
    selected_context = selected["attributes"]["context"]
    candidates = [
        claim for claim in indexes["claim"].values()
        if claim["company_id"] == company_id
        and claim["verified_claim_id"] not in set(selected_claim_ids)
        and "canonical_name" in claim["attributes"]
        and claim["attributes"]["canonical_name"] == canonical_name
        and claim["attributes"]["context"]["period_start"]
        == selected_context["period_start"]
        and claim["attributes"]["context"]["period_end"]
        == selected_context["period_end"]
    ]
    candidates.sort(key=lambda claim: int(claim["locator"]["ordinal"]))
    output = []
    for claim in candidates:
        context = claim["attributes"]["context"]
        dimensions = ";".join(
            "{}={}".format(name, context["dimensions"][name])
            for name in context["dimensions"]
        )
        output.append("{} {}={}".format(
            context["context_ref"], dimensions,
            (
                claim["attributes"]["lexical_value"]
                if "lexical_value" in claim["attributes"] else claim["value"]
            ),
        ))
    if not output:
        raise PublicProjectionError("Basel candidate projection is empty")
    return " | ".join(output)


def _accession_xbrl_enrichment(
    *, config: Mapping[str, object], company_id: str,
    coordinate: Mapping[str, object], indexes: Mapping[str, object],
) -> str:
    """Format current-period projection-only accession XBRL values."""
    target_start = str(coordinate["period_start"])
    target_end = str(coordinate["period_end"])
    values = []
    for concept in config["concepts"]:
        matches = [
            claim for claim in indexes["claim"].values()
            if claim["company_id"] == company_id
            and "canonical_name" in claim["attributes"]
            and claim["attributes"]["canonical_name"] == concept
            and claim["attributes"]["context"]["period_start"] == target_start
            and claim["attributes"]["context"]["period_end"] == target_end
            and claim["attributes"]["context"]["dimensions"] == {}
        ]
        if len(matches) != 1:
            raise PublicProjectionError(
                "Projection XBRL enrichment is ambiguous: {}:{}:{}".format(
                    company_id, concept, len(matches),
                )
            )
        values.append("{}={}".format(concept, matches[0]["value"]))
    return "{}{}{}".format(
        config["prefix"], config["separator"].join(values), config["suffix"],
    )


def _notes(
    *, projection: Mapping[str, object], company_id: str,
    coordinate: Mapping[str, object], observations: Sequence[Mapping[str, object]],
    selected_claim_ids: Sequence[str], indexes: Mapping[str, object],
    repo_root: Path,
) -> str:
    """Render catalog-owned notes and deterministic optional enrichment."""
    enrichment_config = projection["note_enrichment"]
    enrichment = ""
    if enrichment_config is not None:
        kind = str(enrichment_config["kind"])
        if kind == "UNSELECTED_XBRL_CANDIDATES":
            enrichment = _unselected_xbrl_enrichment(
                company_id=company_id,
                selected_claim_ids=selected_claim_ids,
                indexes=indexes,
            )
        elif kind == "ACCESSION_XBRL_CONCEPT_VALUES":
            enrichment = _accession_xbrl_enrichment(
                config=enrichment_config,
                company_id=company_id,
                coordinate=coordinate,
                indexes=indexes,
            )
        else:
            raise PublicProjectionError("Note enrichment is unsupported")
    return str(projection["notes_template"]).format(
        enrichment=enrichment,
        period_start=coordinate["period_start"],
        period_end=coordinate["period_end"],
    )


def render_public_rows(
    *, repo_root: Path, metric_ids: Sequence[str],
    registry_rows: Sequence[Mapping[str, str]],
    coordinates: Sequence[Mapping[str, object]],
    records: Sequence[Mapping[str, object]],
    source_references: Sequence[Mapping[str, object]],
    filing_inventory: Sequence[Mapping[str, str]],
    projection_claims: Sequence[Mapping[str, object]] = (),
) -> Dict[str, object]:
    """Render the complete migrated row set with no legacy semantic input."""
    catalog = load_public_projection_catalog(
        repo_root=repo_root, expected_metric_ids=metric_ids,
    )
    indexes = _record_indexes(
        records=records,
        source_references=source_references,
        projection_claims=projection_claims,
    )
    filing_dates = _filing_dates(filing_inventory=filing_inventory)
    registry = {str(row["company_id"]): row for row in registry_rows}
    expected_keys = {
        (company_id, metric_id)
        for company_id in registry for metric_id in metric_ids
    }
    coordinate_index = {
        (str(row["company_id"]), str(row["metric_id"])): row
        for row in coordinates
    }
    if set(coordinate_index) != expected_keys:
        raise PublicProjectionError("Rendered coordinate exact set differs")
    rows = []
    bindings = []
    for company_id, metric_id in sorted(expected_keys):
        coordinate = coordinate_index[(company_id, metric_id)]
        if coordinate["result_id"] not in indexes["result"]:
            raise PublicProjectionError("Projection Result is absent")
        result = indexes["result"][coordinate["result_id"]]
        if coordinate["trace_id"] not in indexes["trace"]:
            raise PublicProjectionError("Projection Trace is absent")
        trace = indexes["trace"][coordinate["trace_id"]]
        if (
            result["trace_id"] != trace["trace_id"]
            or result["metric_id"] != metric_id
            or result["company_id"] != company_id
        ):
            raise PublicProjectionError("Result/Trace coordinate differs")
        evidence, observations, claim_ids = _selected_evidence(
            trace=trace, indexes=indexes, filing_dates=filing_dates,
            repo_root=repo_root,
        )
        metric = catalog["metrics"][metric_id]
        projection = _projection_policy(
            metric=metric, result=result, observations=observations,
            catalog=catalog,
        )
        formula = (
            metric["formula"]
            if projection["formula"] == "$FORMULA"
            else projection["formula"]
        )
        event_observation = observations[0] if observations and (
            "matched_verified_claim_ids" in observations[0]["source_binding"]
        ) else None
        row = {
            "company": str(registry[company_id]["display_name"]),
            "cik": str(int(registry[company_id]["primary_cik"])),
            "metric_id": metric_id,
            "metric_name": str(metric["metric_name"]),
            "value": "" if result["value"] is None else str(result["value"]),
            "unit": "" if result["unit"] is None else str(result["unit"]),
            "status": str(projection["status"]),
            "source_class": str(projection["source_class"]),
            "formula": str(formula),
            "period_start": str(result["period_start"]),
            "period_end": str(result["period_end"]),
            "fiscal_year": str(coordinate["fiscal_year"])
            if projection["fiscal_year_policy"] == "COORDINATE" else "",
            "fiscal_period": str(projection["fiscal_period"]),
            "accession": _policy_value(
                policy=str(projection["accession_policy"]),
                field="accession", evidence=evidence, trace=trace,
                observation=event_observation, indexes=indexes,
                filing_dates=filing_dates,
            ),
            "form": _policy_value(
                policy=str(projection["form_policy"]), field="form",
                evidence=evidence, trace=trace, observation=event_observation,
                indexes=indexes, filing_dates=filing_dates,
            ),
            "filed_date": _policy_value(
                policy=str(projection["filed_date_policy"]),
                field="filed_date", evidence=evidence, trace=trace,
                observation=event_observation, indexes=indexes,
                filing_dates=filing_dates,
            ),
            "concept_or_section": _policy_value(
                policy=str(projection["concept_policy"]), field="concept",
                evidence=evidence, trace=trace, observation=event_observation,
                indexes=indexes, filing_dates=filing_dates,
            ),
            "context_or_dimension": _policy_value(
                policy=str(projection["context_policy"]), field="context",
                evidence=evidence, trace=trace, observation=event_observation,
                indexes=indexes, filing_dates=filing_dates,
            ),
            "confidence": str(projection["confidence"]),
            "notes": _notes(
                projection=projection, company_id=company_id,
                coordinate=coordinate, observations=observations,
                selected_claim_ids=claim_ids, indexes=indexes,
                repo_root=repo_root,
            ),
        }
        if set(row) != set(METRICS_FIELDS):
            raise PublicProjectionError("Rendered public row fields differ")
        rows.append(row)
        bindings.append({
            "company_id": company_id, "metric_id": metric_id,
            "result_id": result["result_id"], "trace_id": trace["trace_id"],
            "rendered_row_hash": content_hash(value=row),
        })
    return {
        "rows": rows,
        "row_bindings": bindings,
        "rendered_row_set_hash": content_hash(value=rows),
        "projection_catalog_sha256": catalog["catalog_sha256"],
        "approved_delta_authority_hash": catalog[
            "approved_delta_authority_hash"
        ],
        "approved_deltas": catalog["approved_deltas"],
        "renderer_semantic_version": catalog["renderer_semantic_version"],
    }


def render_coverage_rows(
    *, rendered_rows: Sequence[Mapping[str, str]],
) -> List[Dict[str, str]]:
    """Derive migrated coverage rows from independently rendered metric rows."""
    output = []
    for row in rendered_rows:
        evidence = bool(row["accession"] or row["concept_or_section"]) and not (
            row["status"] == "N_A_STRUCTURAL"
        )
        if row["status"] == "N_A_STRUCTURAL" and row["source_class"] != "STRUCTURAL":
            reason = "结构不适用: " + row["notes"]
        elif row["status"] == "NOT_AVAILABLE_SEC":
            reason = "SEC 未披露: " + row["notes"]
        else:
            reason = row["notes"]
        output.append({
            "company": row["company"], "metric_id": row["metric_id"],
            "status": row["status"], "source_class": row["source_class"],
            "has_numeric_value": "1" if row["value"] else "0",
            "has_evidence": "1" if evidence else "0",
            "needs_text_extraction": "0", "needs_review": "0",
            "reason": reason,
        })
    return output


def assemble_public_rows(
    *, predecessor_rows: Sequence[Mapping[str, str]],
    rendered_rows: Sequence[Mapping[str, str]], metric_ids: Sequence[str],
) -> List[Dict[str, str]]:
    """Replace migrated ordinals and append new keys deterministically."""
    rendered = {
        (row["company"], row["metric_id"]): dict(row)
        for row in rendered_rows
    }
    if len(rendered) != len(rendered_rows):
        raise PublicProjectionError("Rendered public keys are duplicated")
    migrated = set(metric_ids)
    output = []
    consumed = set()
    for row_value in predecessor_rows:
        row = dict(row_value)
        key = (row["company"], row["metric_id"])
        if row["metric_id"] in migrated:
            if key not in rendered:
                raise PublicProjectionError("Migrated replacement is absent")
            output.append(rendered[key])
            consumed.add(key)
        else:
            output.append(row)
    additions = [
        rendered[key] for key in sorted(set(rendered) - consumed)
    ]
    output.extend(additions)
    if len(output) != len({(row["company"], row["metric_id"]) for row in output}):
        raise PublicProjectionError("Assembled public keys are duplicated")
    return output


def csv_bytes(
    *, rows: Sequence[Mapping[str, str]], fields: Sequence[str],
) -> bytes:
    """Serialize a complete deterministic UTF-8 CSV with LF endings."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(fields), lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(fields):
            raise PublicProjectionError("CSV row fields differ")
        writer.writerow(dict(row))
    return stream.getvalue().encode("utf-8")


def compare_public_rows(
    *, rendered_rows: Sequence[Mapping[str, str]],
    frozen_legacy_rows: Sequence[Mapping[str, str]],
    approved_deltas: Sequence[Mapping[str, object]],
    approved_delta_authority_hash: str,
) -> Dict[str, object]:
    """Compare every METRICS_FIELDS cell after independent rendering."""
    if approved_deltas:
        raise PublicProjectionError("Unapproved public deltas are forbidden")
    rendered = {
        (row["company"], row["metric_id"]): dict(row)
        for row in rendered_rows
    }
    legacy = {
        (row["company"], row["metric_id"]): dict(row)
        for row in frozen_legacy_rows
    }
    if set(rendered) != set(legacy) or len(rendered) != len(rendered_rows):
        raise PublicProjectionError("Compatibility key exact set differs")
    per_field = {
        field: {"equal": 0, "approved_delta": 0, "unexpected_delta": 0}
        for field in METRICS_FIELDS
    }
    matrix = []
    unexpected = []
    for key in sorted(rendered):
        for field in METRICS_FIELDS:
            equal = rendered[key][field] == legacy[key][field]
            per_field[field]["equal" if equal else "unexpected_delta"] += 1
            comparison = {
                "company": key[0], "metric_id": key[1], "field": field,
                "legacy_value": legacy[key][field],
                "vnext_value": rendered[key][field], "equal": equal,
            }
            matrix.append(comparison)
            if not equal:
                unexpected.append(comparison)
    if unexpected:
        first = unexpected[0]
        raise PublicProjectionError(
            "Unexpected public delta: {}:{}:{}".format(
                first["company"], first["metric_id"], first["field"],
            )
        )
    body = {
        "compared_key_count": len(rendered),
        "compared_field_count": len(matrix),
        "compared_key_exact_set": [
            {"company": company, "metric_id": metric_id}
            for company, metric_id in sorted(rendered)
        ],
        "compared_field_exact_set": list(METRICS_FIELDS),
        "per_field_counts": per_field,
        "unexpected_delta_exact_set": [],
        "approved_delta_exact_set": [],
        "approved_delta_authority_hash": approved_delta_authority_hash,
        "canonical_comparison_matrix_hash": content_hash(value=matrix),
        "vnext_rendered_row_set_hash": content_hash(
            value=[rendered[key] for key in sorted(rendered)]
        ),
        "frozen_legacy_row_set_hash": content_hash(
            value=[legacy[key] for key in sorted(legacy)]
        ),
    }
    return {**body, "strict_compatibility_hash": content_hash(value=body)}
