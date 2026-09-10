"""Native R4 delta projection without changing retained projector semantics.

Only a verified private release context selects production Runs. Presentation
is bound separately from the original MetricSpecs, and legacy rows enter only
the comparison/ordered replacement stage after native rendering.
"""

from __future__ import annotations

from copy import deepcopy
import csv
import io
from pathlib import Path
from typing import Mapping

from .calculator import calculate_metric, metric_is_applicable
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .projector import _project_result, _record_indexes, project_metric_rows, project_evidence_rows
from .public_projection import METRICS_FIELDS, csv_bytes
from .records import validate_record
from .replay import replay_frozen_results
from .run_store import create_run, append_run_records_atomically, load_frozen_run, validate_and_freeze_run
from .specs import compile_spec_file
from .traits import repository_company_traits


POLICY_PATH = "config/r4_public_projection_v1.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_FIELDS = (
    "company", "cik", "metric_id", "source_url", "repo_relative_path", "content_sha256",
    "accession", "document_name", "concept_or_section", "context_or_dimension", "unit",
    "period_start", "period_end", "value_raw", "value_normalized", "evidence_quote",
    "extraction_method", "parser_version",
)
PROJECTION_FIELDS = {
    "unit", "value_multiplier", "status_exact", "status_approx", "source_class", "formula",
    "form", "confidence", "concept_or_section", "metric_context_style", "evidence_context_style",
    "context_or_dimension", "evidence_unit_policy", "evidence_extraction_method", "parser_version",
    "notes_template",
}
FIELD_CATEGORIES = {
    "company": "EXACT_IDENTITY", "cik": "EXACT_IDENTITY", "metric_id": "EXACT_IDENTITY",
    "period_start": "EXACT_PERIOD", "period_end": "EXACT_PERIOD",
    "value": "ANCHOR_EXACT_OR_APPROVED_NATIVE_BACKFILL",
    "unit": "ANCHOR_EXACT_OR_APPROVED_NATIVE_BACKFILL",
    "metric_name": "SPEC_PRESENTATION", "status": "NATIVE_RESULT_QUALITY",
    "source_class": "SOURCE_METHOD_PRESENTATION", "formula": "NATIVE_FORMULA_PRESENTATION",
    "fiscal_year": "COMMON_PRODUCTION_PERIOD_LABEL", "fiscal_period": "COMMON_PRODUCTION_PERIOD_LABEL",
    "accession": "NATIVE_SOURCE_BINDING", "form": "SOURCE_DOCUMENT_PRESENTATION",
    "filed_date": "NATIVE_SOURCE_METADATA_OR_EMPTY", "concept_or_section": "NATIVE_SOURCE_OR_SPEC_PRESENTATION",
    "context_or_dimension": "NATIVE_EVIDENCE_PRESENTATION", "confidence": "DECLARED_PRESENTATION_CONFIDENCE",
    "notes": "NATIVE_METHOD_DESCRIPTION",
}
EVIDENCE_CATEGORIES = {
    **{field: "ANCHOR_EXACT_OR_NATIVE_BACKFILL" for field in (
        "company", "cik", "metric_id", "source_url", "content_sha256", "accession", "document_name",
        "unit", "period_start", "period_end", "value_normalized")},
    "repo_relative_path": "IMMUTABLE_NATIVE_SOURCE_LOCATOR", "concept_or_section": "NATIVE_SOURCE_OR_SPEC_PRESENTATION",
    "context_or_dimension": "NATIVE_EVIDENCE_PRESENTATION", "value_raw": "NATIVE_CANONICAL_OBSERVATION_VALUE",
    "evidence_quote": "NATIVE_OBSERVATION_QUOTE", "extraction_method": "NATIVE_EXTRACTION_METHOD",
    "parser_version": "NATIVE_PROJECTION_VERSION",
}


class R4ProjectionError(ValueError):
    """An incomplete, forged, unsafe or incompatible R4 projection."""


def _require(condition, message):
    if not condition:
        raise R4ProjectionError(message)


def _context(context):
    from .r4_release import validate_r4_release_context
    validate_r4_release_context(context)
    return context


def _safe_path(*, root: Path, path: Path, allow_missing=False) -> Path:
    _require(isinstance(path, Path) and path.is_absolute() and ".." not in path.parts,
             "R4 projection requires an absolute contained path")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise R4ProjectionError("R4 projection path is outside the release root") from error
    _require(bool(relative.parts), "R4 projection cannot write the release root itself")
    current = root
    for part in relative.parts:
        current /= part
        _require(not current.is_symlink(), "R4 projection path contains a symlink")
    if not allow_missing:
        _require(path.is_file() or path.is_dir(), "R4 projection path is missing")
    return path


def _load_presentation(*, root: Path, specs: Mapping, metric_ids: list) -> dict:
    path = _safe_path(root=root, path=root / POLICY_PATH)
    policy = strict_json_file(path=path)
    _require(set(policy) == {"schema_version", "record_type", "presentation_semantic_version", "metric_ids",
             "metrics", "compatibility_field_categories", "structural_coverage_policy",
             "evidence_field_categories", "legacy_metadata_fallback_allowed", "native_values_only"}, "R4 presentation fields differ")
    _require(policy["schema_version"] == 1 and policy["record_type"] == "R4_PUBLIC_PROJECTION_POLICY"
             and policy["presentation_semantic_version"] == "1", "R4 presentation identity differs")
    _require(policy["metric_ids"] == sorted(set(metric_ids)) and set(policy["metrics"]) == set(metric_ids)
             and len(metric_ids) == 6 and set(specs) == set(metric_ids), "R4 presentation metric exact set differs")
    _require(policy["native_values_only"] is True and policy["legacy_metadata_fallback_allowed"] is False
             and policy["compatibility_field_categories"] == FIELD_CATEGORIES
             and policy["evidence_field_categories"] == EVIDENCE_CATEGORIES
             and policy["structural_coverage_policy"] == "COMPLETE_REGISTRY_BY_R4_METRIC_GRID_ZERO_SOURCE_ZERO_AI",
             "R4 presentation cannot weaken native/compatibility rules")
    classes = []
    for metric_id, entry in policy["metrics"].items():
        _require(set(entry) == {"spec_path", "spec_semantic_hash", "spec_closure_hash",
                               "compatibility_class", "projection"}, "R4 presentation metric fields differ")
        relative = entry["spec_path"]
        _require(type(relative) is str and relative.startswith("catalog/r4_v2/"), "R4 Spec path is not original")
        spec_path = _safe_path(root=root, path=root / relative)
        compiled = compile_spec_file(path=spec_path, dependency_specs={})
        _require(compiled == specs[metric_id] and compiled["compiled"]["metric_id"] == metric_id
                 and compiled["compiled"]["legacy_projection"] == {}
                 and entry["spec_semantic_hash"] == compiled["spec_semantic_hash"]
                 and entry["spec_closure_hash"] == compiled["spec_closure_hash"], "R4 original Spec identity differs")
        projection = entry["projection"]
        _require(set(projection) == PROJECTION_FIELDS and all(type(v) is str for v in projection.values()),
                 "R4 presentation mapping fields differ")
        _require(projection["unit"] == compiled["compiled"]["canonical_unit"]
                 and projection["value_multiplier"] == "1" and projection["evidence_unit_policy"] == "observation"
                 and projection["metric_context_style"] == projection["evidence_context_style"] == "constant"
                 and projection["status_exact"] == "MDA_OK" and projection["status_approx"] == "APPROX",
                 "R4 presentation changes native numeric/unit semantics")
        classes.append(entry["compatibility_class"])
    _require(classes.count("STRICT_HISTORICAL_ANCHOR") == 4 and classes.count("APPROVED_NATIVE_BACKFILL") == 2,
             "R4 anchor/backfill classification differs")
    return {**policy, "policy_sha256": sha256_file(path=path)}


def _csv_rows(*, content: bytes, fields) -> list:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8"), newline=""))
    _require(reader.fieldnames == list(fields), "R4 predecessor CSV schema differs")
    rows = list(reader)
    _require(all(set(row) == set(fields) and all(type(v) is str for v in row.values()) for row in rows),
             "R4 predecessor CSV rows are malformed")
    _require(csv_bytes(rows=rows, fields=fields) == content, "R4 predecessor CSV is not byte-preserving canonical input")
    return rows


def _key(row):
    return row["company"], row["metric_id"]


def _native_identity(requirement):
    return {"artifact_requirement_generation": "EXPLICIT_REQUIREMENT_V1",
            "requirement_id": requirement["requirement_id"],
            "requirement_closure_hash": requirement["requirement_closure_hash"],
            "requirement_hashes": requirement["hashes"]}


def _validate_grid(*, context, policy):
    registry = {row["company_id"]: row for row in context.registry}
    _require(len(registry) == len(context.registry) == 10, "R4 registry must have ten unique companies")
    expected = {}
    traits = {company: repository_company_traits(repo_root=context.root, company_id=company) for company in registry}
    for row in context.expected_keys:
        _require(set(row) == {"company_id", "metric_id", "applicability"}, "R4 expected coordinate fields differ")
        key = row["company_id"], row["metric_id"]
        _require(key not in expected and key[0] in registry and key[1] in context.specs,
                 "R4 expected coordinate is duplicate or foreign")
        applicable = metric_is_applicable(applicability=context.specs[key[1]]["compiled"]["applicability"],
                                          traits=traits[key[0]])
        _require(row["applicability"] == ("APPLICABLE" if applicable else "N_A_STRUCTURAL"),
                 "R4 declared applicability differs from native Spec/traits")
        expected[key] = row["applicability"]
    _require(set(expected) == {(company, metric) for company in registry for metric in policy["metric_ids"]}
             and list(expected.values()).count("APPLICABLE") == 6
             and list(expected.values()).count("N_A_STRUCTURAL") == 54, "R4 complete 6+54 grid differs")
    return registry, traits, expected


def _production_runs(*, context, policy, expected):
    entries = context.production_runs
    _require(len(entries) == 6, "R4 requires exactly six production Runs")
    matrix = strict_json_file(path=context.root / "config/r4_fixture_matrix_v1.json")
    fixture_rows = {row["fixture_id"]: row for row in matrix["fixtures"]}
    seen, runs, bindings = set(), [], []
    identity = _native_identity(context.requirement)
    for entry in entries:
        key = entry["company_id"], entry["metric_id"]
        _require(key not in seen and expected.get(key) == "APPLICABLE", "R4 production coordinates are not exact")
        seen.add(key)
        fixture = fixture_rows.get(entry["fixture_id"], {})
        _require(fixture.get("fixture_class") == "POSITIVE_PRODUCTION"
                 and fixture.get("metric_id") == key[1], "R4 cannot project alternate or stability Runs")
        manifest, records = entry["manifest"], entry["records"]
        run_dir = _safe_path(root=context.root, path=Path(entry["run_dir"]))
        _require(manifest["record_type"] in {"R4_SCOPED_RUN", "R4_STRUCTURED_RUN"}
                 and manifest["status"] == "FROZEN" and manifest["company_id"] == key[0]
                 and manifest["target_period"] == context.target_period
                 and all(manifest.get(field) == value for field, value in identity.items()),
                 "R4 production Run identity differs")
        policy_entry = policy["metrics"][key[1]]
        spec_path = policy_entry["spec_path"]
        _require(set(manifest["spec_file_hashes"]) == {spec_path}
                 and manifest["spec_file_hashes"][spec_path] == sha256_file(path=context.root / spec_path),
                 "R4 production Run does not bind its original Spec")
        results = [row for row in records if row["record_type"] == "METRIC_RESULT"]
        _require(len(results) == 1, "R4 production Run must own exactly one Result")
        result = validate_record(record=results[0])
        _require((result["company_id"], result["metric_id"]) == key and result["applicability"] == "APPLICABLE"
                 and result["publication"] == "PUBLISHED" and result["quality"] == "EXACT"
                 and result["spec_closure_hash"] == policy_entry["spec_closure_hash"]
                 and result["value"] is not None and result["unit"] == context.specs[key[1]]["compiled"]["canonical_unit"],
                 "R4 production Result is incomplete or belongs to another Spec")
        runs.append((manifest, records))
        bindings.append(_run_binding(context=context, run_dir=run_dir, manifest=manifest,
                                     result=result, kind="VERIFIED_PRODUCTION", fixture_id=entry["fixture_id"]))
    _require(seen == {key for key, value in expected.items() if value == "APPLICABLE"},
             "R4 production exact set differs")
    return runs, bindings


def _run_binding(*, context, run_dir, manifest, result, kind, fixture_id=None):
    validation = strict_json_file(path=run_dir / "validation.json")
    _require(validation["status"] == "PASSED", "R4 projection requires a PASSED native Run")
    return {"company_id": result["company_id"], "metric_id": result["metric_id"], "kind": kind,
            "fixture_id": fixture_id, "run_id": manifest["run_id"],
            "run_record_type": manifest["record_type"],
            **{field: manifest[field] for field in _native_identity(context.requirement)},
            "spec_file_hashes": manifest["spec_file_hashes"],
            "task_contract_bindings": manifest["task_contract_bindings"],
            "run_path": run_dir.relative_to(context.root).as_posix(),
            "run_manifest_sha256": sha256_file(path=run_dir / "manifest.json"),
            "content_manifest_hash": manifest["content_manifest_hash"], "audit_manifest_hash": manifest["audit_manifest_hash"],
            "validation_receipt_id": validation["validation_receipt_id"],
            "result_id": result["result_id"], "trace_id": result["trace_id"],
            "spec_closure_hash": result["spec_closure_hash"], "applicability": result["applicability"]}


def _structural_run(*, context, workspace, company_id, metric_id, traits, policy):
    # Called only after the public boundary validates the private capability.
    # Replaying the aggregate for every N/A coordinate would add 54 full scans.
    spec = context.specs[metric_id]
    requested_scope = deepcopy(spec["compiled"]["required_claims"])
    target = {"company_id": company_id, "period_start": context.target_period["period_start"],
              "period_end": context.target_period["period_end"], "accession": None, "entity": None,
              "scope": requested_scope, "scope_key": content_hash(value=requested_scope)}
    result, trace, observations = calculate_metric(compiled_spec=spec, target=target, company_traits=traits,
                                                   structured_facts=[], verified_observations=[])
    _require(result["applicability"] == "N_A_STRUCTURAL" and not observations,
             "R4 structural coordinate was not rejected by native applicability")
    run_identity = content_hash(value={"release_context_id": context.release_context_id,
        "result_id": result["result_id"], "target_period": context.target_period})
    run_dir = _safe_path(root=context.root, path=workspace / "structural_runs" / run_identity.split(":", 1)[1],
                         allow_missing=True)
    spec_path = policy["metrics"][metric_id]["spec_path"]
    identity = {"run_id": "run:r4:structural:" + run_identity.split(":", 1)[1],
        "company_id": company_id, "company_traits": traits, "target_period": context.target_period,
        "source_references": [], "missing_required_source_roles": [], "task_contract_bindings": [],
        "spec_file_hashes": {spec_path: sha256_file(path=context.root / spec_path)},
        **_native_identity(context.requirement)}
    if not run_dir.exists():
        _require(not getattr(context, "_read_only", False),
                 "Read-only R4 projection cannot create a missing structural Run")
        manifest = create_run(run_dir=run_dir, **identity)
        append_run_records_atomically(run_dir=run_dir, records=[result, trace],
            expected_records_file_hash=manifest["records_file_hash"],
            expected_review_decisions_file_hash=manifest["review_decisions_file_hash"])
        validate_and_freeze_run(run_dir=run_dir, repo_root=context.root)
    manifest, records, decisions = load_frozen_run(run_dir=run_dir, repo_root=context.root)
    _require(manifest["record_type"] == "SUCCESSOR_RUN" and all(manifest.get(k) == v for k, v in identity.items())
             and not decisions and records == [result, trace], "R4 structural Run has foreign identity or records")
    replay_frozen_results(run_dir=run_dir, repo_root=context.root)
    return run_dir, (manifest, records), _run_binding(context=context, run_dir=run_dir, manifest=manifest,
        result=result, kind="NATIVE_STRUCTURAL")


def _compatibility(*, policy, predecessor_rows, predecessor_evidence, rendered_rows, projected_rows,
                   projected_evidence, indexes, registry):
    old = {_key(row): row for row in predecessor_rows}
    new = {_key(row): row for row in rendered_rows}
    _require(len(old) == len(predecessor_rows) and len(new) == len(rendered_rows), "R4 compatibility duplicate rows")
    r4 = set(policy["metric_ids"])
    _require({key for key in old if key[1] in r4}.issubset(new), "R4 predecessor contains an unowned coordinate")
    unchanged_rows = [row for row in predecessor_rows if row["metric_id"] not in r4]
    unchanged_evidence = [row for row in predecessor_evidence if row["metric_id"] not in r4]
    _require(unchanged_rows == [row for row in projected_rows if row["metric_id"] not in r4]
             and unchanged_evidence == [row for row in projected_evidence if row["metric_id"] not in r4],
             "R4 projection changed a retained R1-R3/non-R4 row")
    cells, additions = [], []
    logical_by_display = {row["display_name"]: company for company, row in registry.items()}
    anchor_count = backfill_count = 0
    for key in sorted(new):
        row = new[key]
        result = indexes["results"][(logical_by_display[key[0]], key[1])]
        if result["applicability"] == "APPLICABLE":
            _require(row["value"] == result["value"] and row["unit"] == result["unit"],
                     "R4 projected numeric value/unit differs from native Result")
        if key not in old:
            _require(result["applicability"] == "N_A_STRUCTURAL" and row["value"] == ""
                     and row["status"] == "N_A_STRUCTURAL", "Only zero-source structural coverage may add a row")
            additions.append({"company_id": result["company_id"], "metric_id": key[1],
                              "class": "NATIVE_STRUCTURAL_COVERAGE_ADDITION", "row_hash": content_hash(value=row)})
            continue
        before = old[key]
        kind = policy["metrics"][key[1]]["compatibility_class"]
        if result["applicability"] == "APPLICABLE":
            if kind == "STRICT_HISTORICAL_ANCHOR":
                anchor_count += 1
                _require(before["value"] == row["value"] and before["unit"] == row["unit"],
                         "R4 historical anchor value/unit changed")
            else:
                backfill_count += 1
                _require(before["status"] == "NOT_EXTRACTED" and before["value"] == before["unit"] == ""
                         and row["value"] != "", "R4 backfill has no approved missing-value predecessor")
        else:
            _require(before["status"] == row["status"] == "N_A_STRUCTURAL" and before["value"] == row["value"] == "",
                     "R4 structural replacement changed business meaning")
        for field in METRICS_FIELDS:
            category = FIELD_CATEGORIES[field]
            if category in {"EXACT_IDENTITY", "EXACT_PERIOD"}:
                _require(before[field] == row[field], "R4 identity/period changed: " + field)
            if field in {"value", "unit"}:
                category = kind if result["applicability"] == "APPLICABLE" else "STRUCTURAL_NULL_VALUE"
            cells.append({"company_id": result["company_id"], "metric_id": key[1], "field": field,
                          "class": category, "old": before[field], "new": row[field],
                          "changed": before[field] != row[field]})
    _require(anchor_count == 4 and backfill_count == 2, "R4 strict anchor/native backfill exact set differs")
    evidence_changes = []
    for key in sorted(new):
        result = indexes["results"][(logical_by_display[key[0]], key[1])]
        before = [row for row in predecessor_evidence if _key(row) == key]
        after = [row for row in projected_evidence if _key(row) == key]
        if result["applicability"] == "N_A_STRUCTURAL":
            _require(not before and not after, "R4 structural coverage cannot contain or discard source evidence")
            continue
        _require(len(after) == 1, "R4 direct native Result requires one evidence row")
        _require(after[0]["value_normalized"] == result["value"] and after[0]["unit"] == result["unit"],
                 "R4 evidence value/unit differs from native Result")
        kind = policy["metrics"][key[1]]["compatibility_class"]
        if kind == "STRICT_HISTORICAL_ANCHOR":
            _require(len(before) == 1, "R4 historical anchor evidence is absent or ambiguous")
            for field, category in EVIDENCE_CATEGORIES.items():
                if category == "ANCHOR_EXACT_OR_NATIVE_BACKFILL":
                    _require(before[0][field] == after[0][field], "R4 anchor evidence changed: " + field)
        else:
            _require(not before, "R4 approved backfill cannot replace existing legacy evidence")
        evidence_changes.append({"company_id": result["company_id"], "metric_id": key[1], "class": kind,
            "old_rows_hash": content_hash(value=before), "new_rows_hash": content_hash(value=after),
            "cells": [{"field": field, "class": category,
                       "old": before[0][field] if before else None, "new": after[0][field],
                       "changed": not before or before[0][field] != after[0][field]}
                      for field, category in EVIDENCE_CATEGORIES.items()]})
    body = {"record_type": "R4_COMPATIBILITY_RECEIPT", "schema_version": 1, "status": "PASS",
        "strict_historical_anchor_count": anchor_count, "approved_native_backfill_count": backfill_count,
        "cells": cells, "coverage_additions": additions, "evidence_replacements": evidence_changes,
        "retained_metric_rows": len(unchanged_rows), "retained_evidence_rows": len(unchanged_evidence),
        "retained_metric_bytes_sha256": sha256_bytes(content=csv_bytes(rows=unchanged_rows, fields=METRICS_FIELDS)),
        "retained_evidence_bytes_sha256": sha256_bytes(content=csv_bytes(rows=unchanged_evidence, fields=EVIDENCE_FIELDS)),
        "retirement_credit": "NONE_THIS_RECEIPT", "historical_legacy_anchor_credit_for_backfill": "NONE"}
    return {**body, "compatibility_receipt_id": content_hash(value=body)}


def build_r4_projection(context, workspace: Path) -> dict:
    """Build exact native 6+54 rows and metadata; never switch publication."""
    context = _context(context)
    root = context.root
    read_only = getattr(context, "_read_only", False)
    _require(type(read_only) is bool, "R4 projection read-only state is malformed")
    _require(context.mode in {"LIVE", "RECORDED_REHEARSAL"}, "R4 projection mode is unknown")
    _require(read_only or context.mode == "LIVE" or root.resolve() != REPOSITORY_ROOT,
             "R4 rehearsal projection requires an isolated repository")
    workspace = _safe_path(root=root, path=workspace, allow_missing=not read_only)
    _require(not workspace.exists() or workspace.is_dir(), "R4 projection workspace is not a directory")
    plan = context.release_plan
    policy = _load_presentation(root=root, specs=context.specs, metric_ids=plan["added_metric_ids"])
    registry, traits, expected = _validate_grid(context=context, policy=policy)
    runs, bindings = _production_runs(context=context, policy=policy, expected=expected)
    predecessor = context.predecessor
    predecessor_rows = _csv_rows(content=predecessor.read_bytes(relative_path="metrics_matrix.csv"), fields=METRICS_FIELDS)
    predecessor_evidence = _csv_rows(content=predecessor.read_bytes(relative_path="metric_evidence.csv"), fields=EVIDENCE_FIELDS)
    from .r4_release import _verified_r3_plan
    parent_plan = _verified_r3_plan(predecessor)
    _require(parent_plan["release_plan_content_id"] == plan["parent_release_plan_content_id"],
             "R4 predecessor release plan differs")
    parent_keys = {(row["company_id"], row["metric_id"]) for row in parent_plan["cumulative_vnext_result_keys"]}
    cumulative_keys = {(row["company_id"], row["metric_id"]) for row in plan["cumulative_vnext_result_keys"]}
    _require(len(parent_keys) == len(parent_plan["cumulative_vnext_result_keys"]) == 240
             and not parent_keys.intersection(expected) and parent_keys | set(expected) == cumulative_keys
             and len(cumulative_keys) == len(plan["cumulative_vnext_result_keys"]) == 300,
             "R4 cumulative 240+60 exact key proof differs")
    structural_dirs = []
    for (company_id, metric_id), applicability in sorted(expected.items()):
        if applicability != "N_A_STRUCTURAL":
            continue
        run_dir, native_run, binding = _structural_run(context=context, workspace=workspace,
            company_id=company_id, metric_id=metric_id, traits=traits[company_id], policy=policy)
        structural_dirs.append(run_dir)
        runs.append(native_run)
        bindings.append(binding)
    indexes = _record_indexes(runs=runs)
    _require(set(indexes["results"]) == set(expected), "R4 native Result index is not exact")
    rendered_rows, evidence_by_key = [], {}
    for company_id, metric_id in sorted(expected):
        result = indexes["results"][(company_id, metric_id)]
        trace = indexes["traces"].get(result["trace_id"])
        _require(trace is not None and trace["spec_closure_hash"] == context.specs[metric_id]["spec_closure_hash"],
                 "R4 native Trace or original Spec is absent")
        view = deepcopy(context.specs[metric_id])
        view["compiled"]["legacy_projection"] = policy["metrics"][metric_id]["projection"]
        row, evidence, _ = _project_result(result=result, trace=trace, company=registry[company_id], spec=view,
            baseline_row={field: "" for field in METRICS_FIELDS}, indexes=indexes,
            fiscal_year=str(context.target_period["fiscal_year"]), metric_fields=METRICS_FIELDS)
        _require(result["applicability"] != "N_A_STRUCTURAL" or not evidence, "R4 structural Result acquired fake evidence")
        rendered_rows.append(row)
        evidence_by_key[_key(row)] = evidence
    replacement = {_key(row): row for row in rendered_rows}
    migrated_keys = set(replacement)
    projected_rows = project_metric_rows(legacy_rows=predecessor_rows, migrated_keys=migrated_keys,
                                         replacement_rows=replacement, fieldnames=METRICS_FIELDS)
    projected_evidence = project_evidence_rows(legacy_rows=predecessor_evidence, migrated_keys=migrated_keys,
        replacement_rows=evidence_by_key, fieldnames=EVIDENCE_FIELDS)
    compatibility = _compatibility(policy=policy, predecessor_rows=predecessor_rows,
        predecessor_evidence=predecessor_evidence, rendered_rows=rendered_rows, projected_rows=projected_rows,
        projected_evidence=projected_evidence, indexes=indexes, registry=registry)
    compatibility_body = {k: v for k, v in compatibility.items() if k != "compatibility_receipt_id"}
    compatibility_body.update({**_native_identity(context.requirement),
        "release_context_id": context.release_context_id, "release_plan_content_id": plan["release_plan_content_id"],
        "execution_mode": context.mode, "predecessor_publication_id": predecessor.publication_id,
        "presentation_policy_sha256": policy["policy_sha256"]})
    compatibility = {**compatibility_body, "compatibility_receipt_id": content_hash(value=compatibility_body)}
    bindings.sort(key=lambda row: (row["company_id"], row["metric_id"]))
    _require(len(bindings) == 60 and all(len({row[field] for row in bindings}) == 60
             for field in ("run_id", "result_id", "trace_id", "run_path")),
             "R4 native Run/Result/Trace identities are missing or duplicated")
    proof = {"production_result_count": 6, "structural_result_count": len(structural_dirs),
             "delta_result_count": len(indexes["results"]), "predecessor_result_count": len(parent_keys),
             "cumulative_result_count": len(cumulative_keys),
             "cumulative_result_keys": [{"company_id": c, "metric_id": m} for c, m in sorted(cumulative_keys)],
             "structural_source_count": 0, "structural_ai_attempt_count": 0}
    batch_body = {"record_type": "R4_PROJECTION_BATCH_MANIFEST", "schema_version": 1,
        **_native_identity(context.requirement), "release_context_id": context.release_context_id,
        "release_plan_content_id": plan["release_plan_content_id"], "execution_mode": context.mode,
        "target_period": context.target_period, "expected_result_keys": context.expected_keys,
        "native_result_bindings": bindings, "completeness_proof": proof}
    batch = {**batch_body, "batch_manifest_id": content_hash(value=batch_body)}
    files = {"metrics_matrix.csv": csv_bytes(rows=projected_rows, fields=METRICS_FIELDS),
             "metric_evidence.csv": csv_bytes(rows=projected_evidence, fields=EVIDENCE_FIELDS)}
    projection_body = {"record_type": "R4_PROJECTION_RECEIPT", "schema_version": 1,
        **_native_identity(context.requirement), "release_context_id": context.release_context_id,
        "release_plan_content_id": plan["release_plan_content_id"], "execution_mode": context.mode,
        "batch_manifest_id": batch["batch_manifest_id"], "compatibility_receipt_id": compatibility["compatibility_receipt_id"],
        "predecessor_publication_id": predecessor.publication_id, "presentation_policy_path": POLICY_PATH,
        "presentation_policy_sha256": policy["policy_sha256"], "public_row_count": len(projected_rows),
        "public_evidence_row_count": len(projected_evidence), "completeness_proof": proof,
        "files": {path: {"sha256": sha256_bytes(content=data), "size": len(data)} for path, data in files.items()},
        "publication_credit": "NONE_PREPARED_CANDIDATE"}
    _context(context)
    return {"files": files, "batch_manifest": batch,
        "projection_receipt": {**projection_body, "projection_receipt_id": content_hash(value=projection_body)},
        "compatibility_receipt": compatibility, "structural_run_dirs": structural_dirs,
        "record_indexes": indexes, "native_result_bindings": bindings, "completeness_proof": proof}
