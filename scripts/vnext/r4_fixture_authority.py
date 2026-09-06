"""Strict closure-free R4 fixture inputs, separate from historical matrices."""

from pathlib import Path
from typing import Mapping

from .canonical import content_hash, sha256_file, strict_json_file
from .requirement_profile import validate_execution_authority
from .r4_task_contracts import CATALOG_PATH, inspect_r4_task_catalog, _r4_metrics
from .sources import resolve_repository_file


MATRIX_PATH = "config/r4_fixture_matrix_v1.json"
MATRIX_FIELDS = {"record_type", "schema_version", "ratchet_id", "task_catalog_path", "metric_ids",
                 "sources", "fixtures", "qualification_credit", "provider_paid_sec_authorized"}
FIXTURE_FIELDS = {"fixture_id", "metric_id", "source_id", "task_contract_id", "fixture_class",
                  "artifact_kind", "recipe_path", "recipe_sha256"}
SOURCE_FIELDS = {"source_id", "company_id", "cik", "accession", "document_name", "source_url",
    "source_repo_relative_path", "source_sha256", "source_size", "media_type",
    "full_derived_asset_id", "table_count", "target_table_metadata", "structured_source_authority"}
RECIPE_FIELDS = {"record_type", "schema_version", "fixture_id", "metric_id", "source_id",
    "task_contract_id", "fixture_class", "artifact_kind", "period", "target", "reference",
    "scope_labels", "numeric_locator", "composite_scope_recipe", "disclosed_period_recipe",
    "candidate_rows", "structured_route_input", "windows", "navigation_paths"}
CLASSES = {"POSITIVE_PRODUCTION", "POSITIVE_ALTERNATE_LAYOUT", "NEGATIVE_EXPECTED",
           "NOT_APPLICABLE", "QUALITATIVE_ONLY", "AMBIGUOUS_EXCLUDED"}


class R4FixtureAuthorityError(ValueError):
    """Reject scope/task/source inputs that are not one exact R4 fixture matrix."""


def load_r4_fixture_authority(*, repo_root: Path, requirement: Mapping = None) -> dict:
    """Read pinned inputs; execution callers must supply their checked Requirement."""
    path = resolve_repository_file(repo_root=repo_root, repo_relative_path=MATRIX_PATH)
    matrix = strict_json_file(path=path)
    if (type(matrix) is not dict or set(matrix) != MATRIX_FIELDS
            or matrix["record_type"] != "R4_FIXTURE_INPUT_MATRIX"
            or type(matrix["schema_version"]) is not int or matrix["schema_version"] != 1
            or matrix["ratchet_id"] != "R4" or matrix["task_catalog_path"] != CATALOG_PATH
            or matrix["qualification_credit"] != "NONE_INPUTS_ONLY"
            or matrix["provider_paid_sec_authorized"] is not False):
        raise R4FixtureAuthorityError("R4 fixture input matrix fields differ")
    tasks = inspect_r4_task_catalog(repo_root=repo_root)["contracts"]
    expected = {task["metric_ids"][0]: task["task_contract_id"] for task in tasks}
    if matrix["metric_ids"] != sorted(expected):
        raise R4FixtureAuthorityError("Fixture matrix metric set is not exact R4")
    source_ids = [s["source_id"] for s in matrix["sources"]]
    if any(type(s) is not dict or set(s) != SOURCE_FIELDS or type(s["table_count"]) is not int
           or s["table_count"] <= 0 or type(s["source_size"]) is not int or s["source_size"] <= 0
           for s in matrix["sources"]):
        raise R4FixtureAuthorityError("Fixture source declaration fields differ")
    if len(source_ids) != len(set(source_ids)):
        raise R4FixtureAuthorityError("Fixture source ID is duplicated")
    for source in matrix["sources"]:
        structured = source["structured_source_authority"]
        if structured is not None and (type(structured) is not dict or set(structured) != {
                "record_type", "accession_xbrl", "submissions", "source_set_manifest_id", "filing_date_window"}
                or structured["record_type"] != "PINNED_NATIVE_SUBMISSIONS_FILING"
                or set(structured["accession_xbrl"]) != {"path", "sha256", "size", "source_reference_id", "request_attempt_id"}
                or set(structured["submissions"]) != {"path", "sha256", "size", "request_attempt_id", "accession", "source_url"}
                or set(structured["filing_date_window"]) != {"period_start", "period_end"}):
            raise R4FixtureAuthorityError("Pinned native structured source identity is incomplete")
    seen, recipes, classes, pairs = set(), {}, set(), {}
    for fixture in matrix["fixtures"]:
        if (type(fixture) is not dict or set(fixture) != FIXTURE_FIELDS
                or fixture["fixture_id"] in seen or fixture["fixture_class"] not in CLASSES
                or expected.get(fixture["metric_id"]) != fixture["task_contract_id"]
                or fixture["source_id"] not in source_ids
                or not fixture["recipe_path"].startswith("tests/fixtures/vnext/r4_offline/inputs/")):
            raise R4FixtureAuthorityError("Fixture identity/class/task/source differs")
        seen.add(fixture["fixture_id"])
        classes.add(fixture["fixture_class"])
        recipe_path = resolve_repository_file(repo_root=repo_root,
                                               repo_relative_path=fixture["recipe_path"])
        if sha256_file(path=recipe_path) != fixture["recipe_sha256"]:
            raise R4FixtureAuthorityError("Fixture recipe bytes differ")
        recipe = strict_json_file(path=recipe_path)
        positive = fixture["fixture_class"].startswith("POSITIVE_")
        fields = RECIPE_FIELDS if positive else RECIPE_FIELDS | {"zero_call_reason", "negative_probe"}
        if (type(recipe) is not dict or set(recipe) != fields
                or recipe["record_type"] != "R4_OFFLINE_AUDIT_RECIPE"
                or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1):
            raise R4FixtureAuthorityError("Fixture recipe schema/generation differs")
        if any(recipe.get(key) != fixture[key] for key in FIXTURE_FIELDS - {"recipe_path", "recipe_sha256"}):
            raise R4FixtureAuthorityError("Recipe identity differs from matrix")
        if positive:
            key = (fixture["metric_id"], fixture["fixture_class"])
            if key in pairs:
                raise R4FixtureAuthorityError("Production/alternate pair is duplicated")
            pairs[key] = fixture["source_id"]
            if fixture["artifact_kind"] not in {"SCOPED_EXTRACTION", "STRUCTURED_PRIMARY"}:
                raise R4FixtureAuthorityError("Positive fixture kind is invalid")
        elif fixture["artifact_kind"] != "ZERO_CALL_CLASSIFICATION":
            raise R4FixtureAuthorityError("Non-positive fixture is not zero-call")
        if not positive and (recipe["fixture_class"] in {"NEGATIVE_EXPECTED", "AMBIGUOUS_EXCLUDED"}) != isinstance(recipe["negative_probe"], dict):
            raise R4FixtureAuthorityError("Negative fixture native probe coverage differs")
        recipes[fixture["fixture_id"]] = recipe
    if classes != CLASSES:
        raise R4FixtureAuthorityError("Fixture class coverage is incomplete")
    sources = {s["source_id"]: s for s in matrix["sources"]}
    for metric in expected:
        try:
            first = sources[pairs[(metric, "POSITIVE_PRODUCTION")]]
            second = sources[pairs[(metric, "POSITIVE_ALTERNATE_LAYOUT")]]
        except KeyError as error:
            raise R4FixtureAuthorityError("R4 positive pair is incomplete") from error
        if first["cik"] == second["cik"] or first["source_sha256"] == second["source_sha256"]:
            raise R4FixtureAuthorityError("Alternate is not an independent issuer/source")
    if requirement is not None:
        validate_execution_authority(repo_root=repo_root, requirement=requirement)
        if MATRIX_PATH not in requirement["execution_authority"]["files"]:
            raise R4FixtureAuthorityError("Requirement does not bind the successor fixture matrix")
        if sorted(_r4_metrics(requirement)) != matrix["metric_ids"]:
            raise R4FixtureAuthorityError("Fixture matrix differs from the Requirement R4 exact set")
    return {"matrix_id": content_hash(value=matrix), "matrix": matrix,
            "sources": sources, "recipes": recipes, "fixtures": list(matrix["fixtures"])}
