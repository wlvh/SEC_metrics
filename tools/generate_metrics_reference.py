#!/usr/bin/env python3
"""Generate and check the SIC × Metrics map and the Metrics definition table.

Purpose:
    Build ``catalog/reference/generated/`` deterministically from committed
    inputs only: the explicit source selection, the hand-maintained bilingual
    metadata, the single hand-maintained SIC-rule file, and the machine
    authorities they point at (MetricSpec front matter, deterministic catalog,
    event routes, source strategy registry, release plans, applicability
    config, company traits, and the text definition document).  The generated
    tables are reference data; nothing here selects, extracts, calculates or
    publishes a metric.

Call relationships:
    ``main`` parses the CLI.  ``build_reference`` loads inputs through
    ``load_inputs`` (digest verified against ``source_selection.json``), then
    ``build_sic_metric_map`` expands rules and ``build_metric_definitions``
    assembles one record per metric ID.  ``--check`` renders in memory and
    compares bytes with the committed files without writing anything.
    ``--refresh-source-digests`` is the only command that rewrites
    ``source_selection.json`` and only its ``sha256`` fields.
    ``tests/test_metrics_reference.py`` imports the module directly.

Determinism:
    No timestamps, no absolute paths, no git calls, no network, sorted keys,
    fixed CSV column order and LF line endings.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


REFERENCE_DIR = Path("catalog") / "reference"
GENERATED_DIR = REFERENCE_DIR / "generated"
SOURCE_SELECTION_PATH = REFERENCE_DIR / "source_selection.json"
METADATA_PATH = REFERENCE_DIR / "metric_metadata.json"
RULES_PATH = REFERENCE_DIR / "sic_metric_rules.json"
MAP_JSON_PATH = GENERATED_DIR / "sic_metric_map.json"
MAP_CSV_PATH = GENERATED_DIR / "sic_metric_map.csv"
DEFINITIONS_JSON_PATH = GENERATED_DIR / "metric_definitions.json"
DEFINITIONS_CSV_PATH = GENERATED_DIR / "metric_definitions.csv"

EXPECTED_METRIC_IDS = tuple(
    ["A{:02d}".format(index) for index in range(1, 14)]
    + ["B{:02d}".format(index) for index in range(1, 14)]
    + ["C{:02d}".format(index) for index in range(1, 5)]
    + ["D{:02d}".format(index) for index in range(1, 5)]
    + ["E{:02d}".format(index) for index in range(1, 6)]
)
APPLICABILITY_VALUES = (
    "APPLICABLE",
    "CONDITIONAL",
    "NOT_APPLICABLE",
    "PENDING_CONFIRMATION",
)
PRIORITY_VALUES = ("CORE", "SUPPLEMENTARY")
DEFINITION_SOURCE_KINDS = (
    "MAIN_STRUCTURED_SPEC",
    "MAIN_DETERMINISTIC_CATALOG",
    "MAIN_EVENT_ROUTE",
    "MAIN_TEXT_DEFINITION",
)
STRUCTURAL_VALUES = (
    "STRUCTURAL_APPLICABLE",
    "STRUCTURAL_NOT_APPLICABLE",
    "NO_TRAIT_RESTRICTION",
    "NO_STRUCTURAL_RULE",
)
# Closed set from config/source_strategy_registry.json; the test proves every
# registry route id is described here.  Descriptions stay at route level: the
# concepts, filings and fallback representation of one metric are bound by its
# selected definition, config/source_strategy_fallback_representation.json or
# a verified legacy code citation, never inferred from the route id.
STRUCTURED_ROUTE_DESCRIPTIONS = {
    "companyfacts_v1": "SourceStrategy structured route companyfacts_v1 (SEC companyfacts entity-level facts); per-metric concept chains are bound by the selected definition, not by the route",
    "accession_xbrl_v1": "SourceStrategy structured route accession_xbrl_v1 (XBRL instance facts of the target accession); per-metric concepts and dimensions are bound by the selected definition, not by the route",
    "8k_item_index_v1": "SourceStrategy structured route 8k_item_index_v1 (8-K filing index item codes); item codes are bound by catalog/event_routes.json",
    "ecd_xbrl_v1": "SourceStrategy structured route ecd_xbrl_v1 (executive compensation disclosure XBRL facts); the concept is bound by the selected definition or a verified legacy code citation, not by the route",
    "auditor_fact_v1": "SourceStrategy structured route auditor_fact_v1 (auditor-report fact family); the fact used is bound per metric by its selected definition or a verified legacy code citation, not by the route",
}
# Roles that a metric's primary definition path may carry, per definition kind.
PRIMARY_ROLES_BY_KIND = {
    "MAIN_STRUCTURED_SPEC": {"metric_spec"},
    "MAIN_DETERMINISTIC_CATALOG": {"deterministic_catalog"},
    "MAIN_EVENT_ROUTE": {"event_routes"},
    "MAIN_TEXT_DEFINITION": {"text_definition"},
}
VARIANT_ROLES = {"metric_spec", "metric_spec_historical", "disclosure_group"}
# A NOT_APPLICABLE business rule may only rest on definition-level sources:
# Spec / catalog applicability, the trait configuration or the definition
# document.  Evidence directories, release plans and authorization flags
# describe implementation or data state and can never make an industry
# "inapplicable" (Issue #44 acceptance finding on bank B06).
DEFINITION_LEVEL_BASIS_PREFIXES = (
    "catalog/",
    "config/metric_applicability.yaml",
    "02_指标定义_SEC_10公司单年指标.md",
)
IMPLEMENTATION_STATE_MARKERS = (
    "docs/evidence/",
    "release_plans/",
    "production_authorized",
    "complete=false",
    "NOT_ESTABLISHED",
)
LEGACY_LOCATOR_METHOD_TYPES = {
    "text_regex": "LEGACY_TEXT_KEYWORD_RULE",
    "xbrl_concept": "LEGACY_XBRL_FACT_RULE",
    "8k_item_code": "LEGACY_8K_ITEM_RULE",
}
DETERMINISTIC_ADAPTER_DESCRIPTIONS = {
    "companyfacts": "SEC companyfacts API (entity-level standard taxonomy facts)",
    "accession_xbrl": "target 10-K accession XBRL instance",
}
# Positional templates mirror scripts/vnext/zero_ai_r2.py::_formula_value; the
# test evaluates each template against that function.
DETERMINISTIC_FORMULA_TEMPLATES = {
    ("direct", 1): "{0}",
    ("difference", 2): "{0} - {1}",
    ("ratio", 2): "{0} / {1}",
    ("growth", 2): "({0} - {1}) / {1}",
    ("average_denominator_ratio", 3): "{0} / (({1} + {2}) / 2)",
    ("interest_coverage", 2): "{0} / {1}",
    ("interest_coverage", 3): "({0} - {1}) / {2}",
}
MAP_CSV_COLUMNS = [
    "sic_start",
    "sic_end",
    "sic_range_label_zh",
    "sic_range_label_en",
    "profile",
    "industry_zh",
    "industry_en",
    "traits",
    "metric_id",
    "metric_name_en",
    "metric_name_zh",
    "business_applicability",
    "business_priority",
    "structural_applicability",
    "condition_zh",
    "condition_en",
    "rule_clause_id",
    "basis",
    "baseline_sample_company_ids",
]
DEFINITIONS_CSV_COLUMNS = [
    "metric_id",
    "group",
    "name_en",
    "name_zh",
    "description_zh",
    "description_en",
    "method_types",
    "source_mode",
    "reader_family_id",
    "structured_route_id",
    "ai_fallback_representation",
    "definition_source_kind",
    "definition_source_path",
    "binding_authority",
    "binding_state_label",
    "data_sources",
    "formula_expression",
    "canonical_unit",
    "reported_unit",
    "period_role",
    "entity_or_business_scope",
    "expected_statuses",
    "applicable_sic_ranges",
    "vnext_release_state",
    "legacy_producer_state",
    "limitations_zh",
]


class ReferenceError(ValueError):
    """Report an invalid reference input, rule, citation or drift."""


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase hex SHA-256 of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def _read_bytes(repo_root: Path, relative: str) -> bytes:
    """Read one declared repository file; refuse symlinks and absolute paths."""
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ReferenceError("Declared input must be a relative repository path: {}".format(relative))
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise ReferenceError("Declared input is missing or not a regular file: {}".format(relative))
    return path.read_bytes()


def _json(payload: bytes, label: str) -> Any:
    """Parse strict JSON and fail with the offending label."""
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ReferenceError("{} is not valid UTF-8 JSON: {}".format(label, error)) from error


def parse_front_matter(text: str, label: str) -> Tuple[Dict[str, Any], str]:
    """Split a MetricSpec Markdown file into its JSON front matter and body."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if match is None:
        raise ReferenceError("{} has no JSON front matter".format(label))
    try:
        front = json.loads(match.group(1))
    except ValueError as error:
        raise ReferenceError("{} front matter is not JSON: {}".format(label, error)) from error
    if not isinstance(front, dict):
        raise ReferenceError("{} front matter must be an object".format(label))
    return front, match.group(2)


def input_digest(
    relative: str, payload: bytes, entry: Mapping[str, Any], cited_symbols: Sequence[str]
) -> str:
    """Return the digest that source_selection.json records for one input.

    ``digest_scope`` ``file`` hashes the whole file.  ``cited_symbols`` hashes
    only the top-level source blocks that the metadata cites, so unrelated
    edits elsewhere in a large code file do not count as reference drift while
    any change inside a cited symbol still does.
    """
    scope = entry.get("digest_scope", "file")
    if scope == "file":
        return sha256_bytes(payload)
    if scope != "cited_symbols":
        raise ReferenceError("{}: unknown digest_scope {}".format(relative, scope))
    if not cited_symbols:
        raise ReferenceError("{}: digest_scope cited_symbols needs at least one cited symbol".format(relative))
    source = payload.decode("utf-8")
    blocks = ["{}\n{}".format(symbol, _symbol_block(source, symbol, relative)) for symbol in sorted(cited_symbols)]
    return sha256_bytes("\n\x00\n".join(blocks).encode("utf-8"))


def load_inputs(
    repo_root: Path,
    selection: Mapping[str, Any],
    *,
    verify_digests: bool,
    cited_symbols_by_path: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, bytes]:
    """Read every declared input and verify its recorded digest.

    Args:
        repo_root: Repository root that contains the declared inputs.
        selection: Parsed ``source_selection.json``.
        verify_digests: When true, a missing or different digest is drift.
        cited_symbols_by_path: Symbols cited per code file for the
            ``cited_symbols`` digest scope.

    Returns:
        Relative path to raw bytes for every declared input.
    """
    inputs = selection.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ReferenceError("source_selection.json inputs must be a non-empty object")
    cited = cited_symbols_by_path or {}
    loaded: Dict[str, bytes] = {}
    drift: List[str] = []
    for relative in sorted(inputs):
        entry = inputs[relative]
        if not isinstance(entry, dict) or not {"sha256", "role"} <= set(entry) or not set(entry) <= {"sha256", "role", "digest_scope"}:
            raise ReferenceError("Input entry must have sha256, role and optional digest_scope: {}".format(relative))
        if (entry["role"] == "code_citation_target") != (entry.get("digest_scope") == "cited_symbols"):
            raise ReferenceError("{}: code_citation_target inputs must use digest_scope cited_symbols and nothing else may".format(relative))
        payload = _read_bytes(repo_root, relative)
        loaded[relative] = payload
        if verify_digests:
            recorded = entry["sha256"]
            actual = input_digest(relative, payload, entry, cited.get(relative, []))
            if recorded is None:
                drift.append("{}: no recorded digest (run --refresh-source-digests)".format(relative))
            elif recorded != actual:
                drift.append("{}: recorded {} != actual {} (scope {})".format(relative, recorded, actual, entry.get("digest_scope", "file")))
    if drift:
        raise ReferenceError("SOURCE_DRIFT\n" + "\n".join(drift))
    return loaded


def cited_symbols(metadata: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Collect every cited (path, symbol) pair from the metadata file."""
    citations: List[Mapping[str, Any]] = list(metadata.get("shared_citations", {}).values())
    for label in ("legacy", "vnext"):
        citations.append(metadata["status_vocabulary"][label]["citation"])
    for entry in metadata.get("metrics", {}).values():
        citations.extend(entry.get("legacy_method", {}).get("citations", []))
    result: Dict[str, List[str]] = {}
    for citation in citations:
        if not isinstance(citation, dict) or "path" not in citation or "symbol" not in citation:
            raise ReferenceError("Citation must have path and symbol")
        if citation["symbol"] is None:
            continue
        symbols = result.setdefault(str(citation["path"]), [])
        if citation["symbol"] not in symbols:
            symbols.append(str(citation["symbol"]))
    return result


# ---------------------------------------------------------------------------
# Citation verification
# ---------------------------------------------------------------------------


_AST_CACHE: Dict[str, ast.Module] = {}


def _binding_span(node: ast.AST, symbol: str) -> Optional[Tuple[int, int, str]]:
    """Return (start_line, end_line, kind) when a top-level node binds ``symbol``."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if node.name != symbol:
            return None
        start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
        return (start, int(node.end_lineno), type(node).__name__)
    targets: List[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        bound = [alias.asname or alias.name.split(".")[0] for alias in node.names]
        return (node.lineno, int(node.end_lineno), type(node).__name__) if symbol in bound else None
    names: List[str] = []
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.append(child.id)
    if symbol in names:
        return (node.lineno, int(node.end_lineno), type(node).__name__)
    return None


def _symbol_block(source: str, symbol: str, label: str) -> str:
    """Return the complete top-level source block that binds ``symbol``.

    The block is located with the standard-library ``ast`` module (function,
    class, assignment, import, for/with targets), includes decorators, and is
    cut by the parser's own ``end_lineno`` so column-0 comments inside a body
    cannot truncate it.  A symbol that is bound more than once at module level
    (duplicate definition, direct rebinding) is rejected instead of silently
    taking the first binding.  Conditional or nested definitions are outside
    the supported forms and are reported as undefined.
    """
    cache_key = sha256_bytes(source.encode("utf-8"))
    tree = _AST_CACHE.get(cache_key)
    if tree is None:
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            raise ReferenceError("{}: cited source is not parseable Python: {}".format(label, error)) from error
        _AST_CACHE[cache_key] = tree
    spans = [span for span in (_binding_span(node, symbol) for node in tree.body) if span is not None]
    if not spans:
        raise ReferenceError("{}: symbol {} is not defined at top level".format(label, symbol))
    if len(spans) > 1:
        raise ReferenceError(
            "{}: symbol {} is bound {} times at top level (lines {}); ambiguous binding is not supported".format(
                label, symbol, len(spans), ", ".join(str(span[0]) for span in spans)
            )
        )
    start, end, _kind = spans[0]
    lines = source.split("\n")
    return "\n".join(lines[start - 1:end])


def verify_citation(
    loaded: Mapping[str, bytes], citation: Mapping[str, Any], label: str
) -> None:
    """Prove that a cited path/symbol/literal set exists in the declared input."""
    if not isinstance(citation, dict) or set(citation) != {"path", "symbol", "literals"}:
        raise ReferenceError("{}: citation must have path, symbol and literals".format(label))
    path = citation["path"]
    if path not in loaded:
        raise ReferenceError("{}: cited path {} is not a declared input".format(label, path))
    source = loaded[path].decode("utf-8")
    literals = citation["literals"]
    if not isinstance(literals, list) or any(type(item) is not str or not item for item in literals):
        raise ReferenceError("{}: literals must be non-empty strings".format(label))
    scope = source
    if citation["symbol"] is not None:
        scope = _symbol_block(source, str(citation["symbol"]), label)
    for literal in literals:
        if literal not in scope:
            raise ReferenceError(
                "{}: literal {!r} not found in {}{}".format(
                    label, literal, path,
                    "" if citation["symbol"] is None else "::{}".format(citation["symbol"]),
                )
            )


# ---------------------------------------------------------------------------
# Applicability, rules and the SIC × Metrics map
# ---------------------------------------------------------------------------


def evaluate_trait_applicability(applicability: Mapping[str, Any], traits: Sequence[str]) -> str:
    """Mirror scripts/vnext/calculator.py::metric_is_applicable as a label."""
    required = list(applicability.get("all", []))
    forbidden = list(applicability.get("none", []))
    if not required and not forbidden:
        return "NO_TRAIT_RESTRICTION"
    trait_set = set(traits)
    if set(required).issubset(trait_set) and not (set(forbidden) & trait_set):
        return "STRUCTURAL_APPLICABLE"
    return "STRUCTURAL_NOT_APPLICABLE"


def _clause_matches(when: Any, profile: str, traits: Sequence[str]) -> bool:
    """Evaluate one rule clause predicate against a profile."""
    if when == "DEFAULT":
        return True
    if not isinstance(when, dict) or len(when) != 1:
        raise ReferenceError("Rule clause predicate must be DEFAULT or one keyed object")
    key, value = next(iter(when.items()))
    if not isinstance(value, list) or not value or any(type(v) is not str for v in value):
        raise ReferenceError("Rule clause predicate values must be a non-empty string list")
    trait_set = set(traits)
    if key == "traits_all":
        return set(value).issubset(trait_set)
    if key == "traits_any":
        return bool(set(value) & trait_set)
    if key == "profiles":
        return profile in value
    raise ReferenceError("Unknown rule clause predicate: {}".format(key))


def _validate_clauses(metric_id: str, clauses: Any, known_traits: Sequence[str], known_profiles: Sequence[str]) -> None:
    """Validate clause shape, vocabulary, ordering and uniqueness."""
    if not isinstance(clauses, list) or not clauses:
        raise ReferenceError("{}: clauses must be a non-empty list".format(metric_id))
    seen = set()
    required_fields = {"clause_id", "when", "applicability", "priority", "condition_zh", "condition_en", "basis"}
    for index, clause in enumerate(clauses):
        if not isinstance(clause, dict) or set(clause) != required_fields:
            raise ReferenceError("{}: clause fields must be exactly {}".format(metric_id, sorted(required_fields)))
        if clause["clause_id"] in seen:
            raise ReferenceError("{}: duplicate clause_id {}".format(metric_id, clause["clause_id"]))
        seen.add(clause["clause_id"])
        if clause["applicability"] not in APPLICABILITY_VALUES:
            raise ReferenceError("{}: unknown applicability {}".format(metric_id, clause["applicability"]))
        if clause["priority"] is not None and clause["priority"] not in PRIORITY_VALUES:
            raise ReferenceError("{}: unknown priority {}".format(metric_id, clause["priority"]))
        if clause["applicability"] in ("APPLICABLE", "CONDITIONAL") and clause["priority"] is None:
            raise ReferenceError("{}: {} rows need a priority".format(metric_id, clause["applicability"]))
        if clause["applicability"] not in ("APPLICABLE", "CONDITIONAL") and clause["priority"] is not None:
            raise ReferenceError("{}: {} rows must not carry a priority".format(metric_id, clause["applicability"]))
        if clause["applicability"] in ("CONDITIONAL", "PENDING_CONFIRMATION", "NOT_APPLICABLE") and not clause["condition_zh"]:
            raise ReferenceError("{}: {} rows need condition_zh".format(metric_id, clause["applicability"]))
        if not isinstance(clause["basis"], list) or not clause["basis"] or any(type(item) is not str or not item for item in clause["basis"]):
            raise ReferenceError("{}: basis must be a non-empty list of strings".format(metric_id))
        if clause["applicability"] == "NOT_APPLICABLE":
            for basis in clause["basis"]:
                if not basis.startswith(DEFINITION_LEVEL_BASIS_PREFIXES):
                    raise ReferenceError(
                        "{}: NOT_APPLICABLE clause {} needs a definition-level basis (one of {}); got {!r}".format(
                            metric_id, clause["clause_id"], ", ".join(DEFINITION_LEVEL_BASIS_PREFIXES), basis
                        )
                    )
                if any(marker in basis for marker in IMPLEMENTATION_STATE_MARKERS):
                    raise ReferenceError(
                        "{}: NOT_APPLICABLE clause {} cites an implementation/authorization state ({!r}); incomplete data or missing production authorization must be CONDITIONAL or PENDING_CONFIRMATION".format(
                            metric_id, clause["clause_id"], basis
                        )
                    )
        is_last = index == len(clauses) - 1
        if is_last and clause["when"] != "DEFAULT":
            raise ReferenceError("{}: last clause must be DEFAULT".format(metric_id))
        if not is_last and clause["when"] == "DEFAULT":
            raise ReferenceError("{}: DEFAULT clause must be last".format(metric_id))
        if isinstance(clause["when"], dict):
            key, value = next(iter(clause["when"].items()))
            universe = known_profiles if key == "profiles" else known_traits
            unknown = sorted(set(value) - set(universe))
            if unknown:
                raise ReferenceError("{}: clause {} references unknown {}: {}".format(metric_id, clause["clause_id"], key, unknown))


def load_sic_ranges(applicability_config: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Return sorted, validated, non-overlapping SIC ranges from the baseline config."""
    rules = applicability_config.get("profile_rules")
    if not isinstance(rules, list) or not rules:
        raise ReferenceError("metric_applicability profile_rules must be a non-empty list")
    ranges: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"sic_start", "sic_end", "profile"}:
            raise ReferenceError("profile_rules entries must have sic_start, sic_end, profile")
        start = int(rule["sic_start"])
        end = int(rule["sic_end"])
        if not (0 <= start <= end <= 9999):
            raise ReferenceError("SIC range is invalid: {}-{}".format(start, end))
        ranges.append({"sic_start": "{:04d}".format(start), "sic_end": "{:04d}".format(end), "profile": str(rule["profile"])})
    ranges.sort(key=lambda item: (item["sic_start"], item["sic_end"]))
    for previous, current in zip(ranges, ranges[1:]):
        if current["sic_start"] <= previous["sic_end"]:
            raise ReferenceError(
                "SIC ranges overlap: {}-{} and {}-{}".format(
                    previous["sic_start"], previous["sic_end"], current["sic_start"], current["sic_end"]
                )
            )
    return ranges


def _profile_traits(trait_catalog: Mapping[str, Any]) -> Dict[str, List[str]]:
    """Return profile → ordered traits from catalog/company_traits.yaml."""
    traits = trait_catalog.get("profile_traits")
    if not isinstance(traits, dict) or not traits:
        raise ReferenceError("company_traits profile_traits must be a non-empty object")
    result: Dict[str, List[str]] = {}
    for profile in sorted(traits):
        values = traits[profile]
        if not isinstance(values, list) or any(type(v) is not str for v in values) or len(set(values)) != len(values):
            raise ReferenceError("profile_traits.{} must be a unique string list".format(profile))
        result[profile] = list(values)
    return result


def _registry_companies(payload: bytes) -> List[Dict[str, str]]:
    """Parse config/company_registry.csv rows."""
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    rows = []
    for row in reader:
        for field in ("company_id", "sic", "industry_profile"):
            if not row.get(field):
                raise ReferenceError("company_registry.csv row lacks {}".format(field))
        rows.append(row)
    return rows


def structural_applicability_for(
    metric_id: str, definition_sources: Mapping[str, Any], traits: Sequence[str]
) -> str:
    """Return the structural applicability label of a metric for a trait set."""
    source = definition_sources[metric_id]
    applicability = source.get("applicability")
    if applicability is None:
        return "NO_STRUCTURAL_RULE"
    return evaluate_trait_applicability(applicability, traits)


def build_sic_metric_map(
    *,
    rules: Mapping[str, Any],
    sic_ranges: Sequence[Mapping[str, Any]],
    profile_traits: Mapping[str, Sequence[str]],
    registry_rows: Sequence[Mapping[str, str]],
    definition_sources: Mapping[str, Any],
    metric_names: Mapping[str, Tuple[str, str]],
) -> Dict[str, Any]:
    """Expand the single rule file into long-format SIC × Metrics rows."""
    metric_rules = rules.get("metric_rules")
    if not isinstance(metric_rules, dict) or sorted(metric_rules) != sorted(EXPECTED_METRIC_IDS):
        raise ReferenceError("metric_rules must cover exactly the 39 metric IDs")
    known_profiles = sorted(profile_traits)
    known_traits = sorted({trait for traits in profile_traits.values() for trait in traits})
    for metric_id in EXPECTED_METRIC_IDS:
        entry = metric_rules[metric_id]
        if not isinstance(entry, dict) or set(entry) != {"clauses"}:
            raise ReferenceError("{}: metric rule must have exactly clauses".format(metric_id))
        _validate_clauses(metric_id, entry["clauses"], known_traits, known_profiles)
    labels = rules.get("industry_labels")
    range_labels = rules.get("sic_range_labels")
    if not isinstance(labels, dict) or not isinstance(range_labels, dict):
        raise ReferenceError("industry_labels and sic_range_labels must be objects")
    range_keys = ["{}-{}".format(item["sic_start"], item["sic_end"]) for item in sic_ranges]
    if sorted(range_labels) != sorted(range_keys):
        raise ReferenceError("sic_range_labels must match baseline ranges exactly: {} vs {}".format(sorted(range_labels), sorted(range_keys)))
    used_profiles = sorted({item["profile"] for item in sic_ranges})
    for profile in used_profiles:
        if profile not in profile_traits:
            raise ReferenceError("Baseline profile {} has no trait projection".format(profile))
        if profile not in labels:
            raise ReferenceError("Baseline profile {} has no industry label".format(profile))
    for profile, label in labels.items():
        if profile not in profile_traits:
            raise ReferenceError("industry_labels references unknown profile {}".format(profile))
        if not isinstance(label, dict) or set(label) != {"zh", "en"}:
            raise ReferenceError("industry label for {} must have zh and en".format(profile))
    sample_by_range: Dict[str, List[str]] = {key: [] for key in range_keys}
    for row in registry_rows:
        sic = int(row["sic"])
        matched = [item for item in sic_ranges if int(item["sic_start"]) <= sic <= int(item["sic_end"])]
        if len(matched) == 1:
            key = "{}-{}".format(matched[0]["sic_start"], matched[0]["sic_end"])
            sample_by_range[key].append(row["company_id"])
            if row["industry_profile"] != matched[0]["profile"]:
                raise ReferenceError("Registry profile for {} differs from SIC rule".format(row["company_id"]))
    rows: List[Dict[str, Any]] = []
    for item in sic_ranges:
        profile = item["profile"]
        traits = list(profile_traits[profile])
        key = "{}-{}".format(item["sic_start"], item["sic_end"])
        for metric_id in EXPECTED_METRIC_IDS:
            clauses = metric_rules[metric_id]["clauses"]
            chosen = None
            for clause in clauses:
                if _clause_matches(clause["when"], profile, traits):
                    chosen = clause
                    break
            if chosen is None:  # pragma: no cover - DEFAULT clause is mandatory
                raise ReferenceError("{}: no clause matched profile {}".format(metric_id, profile))
            structural = structural_applicability_for(metric_id, definition_sources, traits)
            if structural == "STRUCTURAL_NOT_APPLICABLE" and chosen["applicability"] != "NOT_APPLICABLE":
                raise ReferenceError(
                    "{}: clause {} marks profile {} as {} but the bound definition is structurally inapplicable".format(
                        metric_id, chosen["clause_id"], profile, chosen["applicability"]
                    )
                )
            name_en, name_zh = metric_names[metric_id]
            rows.append({
                "sic_start": item["sic_start"],
                "sic_end": item["sic_end"],
                "sic_range_label_zh": range_labels[key]["zh"],
                "sic_range_label_en": range_labels[key]["en"],
                "profile": profile,
                "industry_zh": labels[profile]["zh"],
                "industry_en": labels[profile]["en"],
                "traits": traits,
                "metric_id": metric_id,
                "metric_name_en": name_en,
                "metric_name_zh": name_zh,
                "business_applicability": chosen["applicability"],
                "business_priority": chosen["priority"],
                "structural_applicability": structural,
                "condition_zh": chosen["condition_zh"],
                "condition_en": chosen["condition_en"],
                "rule_clause_id": chosen["clause_id"],
                "basis": list(chosen["basis"]),
                "baseline_sample_company_ids": sorted(sample_by_range[key]),
            })
    unmatched = rules.get("unmatched_sic")
    if not isinstance(unmatched, dict) or unmatched.get("applicability") not in APPLICABILITY_VALUES:
        raise ReferenceError("unmatched_sic policy must declare a valid applicability")
    default_profile = unmatched.get("legacy_pipeline_default_profile")
    if default_profile not in profile_traits:
        raise ReferenceError("unmatched_sic default profile is not a known profile")
    return {
        "schema_version": 1,
        "record_type": "SIC_METRIC_MAP",
        "generated_by": "tools/generate_metrics_reference.py",
        "not_a_production_pointer": True,
        "sic_range_authority": rules.get("sic_range_authority"),
        "trait_authority": rules.get("trait_authority"),
        "trait_semantics": rules.get("trait_semantics"),
        "applicability_values": rules.get("applicability_values"),
        "priority_values": rules.get("priority_values"),
        "priority_basis": rules.get("priority_basis"),
        "structural_applicability_values": {
            "STRUCTURAL_APPLICABLE": "所选定义的 applicability traits 对该行业成立。",
            "STRUCTURAL_NOT_APPLICABLE": "所选定义的 applicability traits 对该行业不成立（预期 N_A_STRUCTURAL）。",
            "NO_TRAIT_RESTRICTION": "所选定义 applicability.all/none 均为空，没有 trait 限制。",
            "NO_STRUCTURAL_RULE": "所选定义（事件路由或文字定义）没有 trait applicability 字段。",
        },
        "sic_format": "四位字符串，保留前导零；范围含端点；未命中 SIC 见 unmatched_sic_policy。",
        "unmatched_sic_policy": {
            "applicability": unmatched["applicability"],
            "legacy_pipeline_default_profile": default_profile,
            "legacy_default_traits": list(profile_traits[default_profile]),
            "basis": list(unmatched.get("basis", [])),
            "note_zh": unmatched.get("note_zh"),
            "note_en": unmatched.get("note_en"),
        },
        "sic_ranges": [
            {
                "sic_start": item["sic_start"],
                "sic_end": item["sic_end"],
                "profile": item["profile"],
                "traits": list(profile_traits[item["profile"]]),
                "label_zh": range_labels["{}-{}".format(item["sic_start"], item["sic_end"])]["zh"],
                "label_en": range_labels["{}-{}".format(item["sic_start"], item["sic_end"])]["en"],
                "baseline_sample_company_ids": sorted(sample_by_range["{}-{}".format(item["sic_start"], item["sic_end"])]),
            }
            for item in sic_ranges
        ],
        "row_count": len(rows),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Definition sources
# ---------------------------------------------------------------------------


def _render_expression(node: Any) -> str:
    """Render a MetricSpec arithmetic tree as infix text."""
    if type(node) is str:
        return node
    if not isinstance(node, dict) or "op" not in node or "args" not in node:
        raise ReferenceError("Formula node must be a role string or an op/args object")
    symbols = {"add": " + ", "subtract": " - ", "multiply": " * ", "divide": " / "}
    if node["op"] not in symbols:
        raise ReferenceError("Unknown formula op {}".format(node["op"]))
    rendered = symbols[node["op"]].join(_render_expression(arg) for arg in node["args"])
    return "(" + rendered + ")"


def _spec_role_sources(inputs: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Return (formula inputs, ordered fallback branches, dependencies) of a MetricSpec."""
    formula_inputs: List[Dict[str, Any]] = []
    branches: List[Dict[str, Any]] = []
    dependencies: List[str] = []

    def describe_role(role: str, spec: Mapping[str, Any], ordinal: Optional[int]) -> None:
        if "reuse_metric_observation" in spec:
            dependencies.append(str(spec["reuse_metric_observation"]))
            formula_inputs.append({
                "role": role,
                "kind": "reuse_metric_observation",
                "reuses_metric": spec["reuse_metric_observation"],
                "cardinality": spec.get("cardinality"),
            })
            return
        if "structured_role" in spec:
            inner = spec["structured_role"]
            formula_inputs.append({
                "role": role,
                "kind": "structured_role",
                "approved_concepts": list(inner.get("approved_concepts", [])),
                "cardinality": inner.get("cardinality"),
                "quality": inner.get("quality"),
            })
            return
        if "extraction_role" in spec:
            inner = spec["extraction_role"]
            entry = {
                "role": role,
                "kind": "extraction_role",
                "approved_concepts": list(inner.get("approved_concepts", [])),
                "cardinality": inner.get("cardinality"),
                "quality": inner.get("quality"),
            }
            if ordinal is None:
                formula_inputs.append(entry)
            else:
                branches.append(dict(entry, branch_ordinal=ordinal, expression=role))
            return
        if "derived_role" in spec:
            inner = spec["derived_role"]
            components = {
                name: list(component.get("approved_concepts", []))
                for name, component in inner.get("inputs", {}).items()
            }
            expression = _render_expression({"op": inner["op"], "args": inner["args"]})
            entry: Dict[str, Any] = {
                "role": role,
                "kind": "derived_role",
                "expression": expression,
                "component_concepts": components,
                "quality": inner.get("quality"),
                "quality_reason": inner.get("quality_reason"),
                "guards": list(inner.get("guards", [])),
            }
            if "cross_check" in inner:
                check = inner["cross_check"]
                entry["cross_check"] = {
                    "role": check.get("role"),
                    "approved_concepts": list(check.get("approved_concepts", [])),
                    "expected": _render_expression(check["expression"]["expected"]),
                    "actual": check["expression"]["actual"],
                    "denominator": check.get("denominator"),
                    "relative_tolerance": check.get("relative_tolerance"),
                    "when_available": check.get("when_available"),
                }
            if ordinal is None:
                formula_inputs.append(entry)
            else:
                branches.append(dict(entry, branch_ordinal=ordinal))
            return
        if "choose_first" in spec:
            for ordinal_index, option in enumerate(spec["choose_first"], start=1):
                describe_role(role, option, ordinal_index)
            formula_inputs.append({"role": role, "kind": "choose_first", "branch_count": len(spec["choose_first"])})
            return
        raise ReferenceError("Unknown MetricSpec input role shape for {}".format(role))

    for role in inputs:
        describe_role(role, inputs[role], None)
    return formula_inputs, branches, dependencies


def describe_spec_source(front: Mapping[str, Any], path: str, sha256: str) -> Dict[str, Any]:
    """Project the machine-readable parts of one MetricSpec front matter."""
    kind = front.get("kind")
    formula: Optional[Dict[str, Any]] = None
    inputs = front.get("inputs")
    if isinstance(inputs, dict) and inputs:
        formula_inputs, branches, dependencies = _spec_role_sources(inputs)
        formula = {
            "expression": _render_expression(front["formula"]) if "formula" in front else None,
            "inputs": formula_inputs,
            "fallback_branches": branches,
            "top_level_guards": list(front.get("top_level_guards", [])),
            "quality_rule": front.get("quality_rule"),
            "dependencies": sorted(set(list(front.get("dependencies", [])) + dependencies)),
        }
    scope = front.get("scope_contract") or {}
    return {
        "path": path,
        "sha256": sha256,
        "name": front.get("name"),
        "kind": kind,
        "source_mode": front.get("source_mode"),
        "canonical_unit": front.get("canonical_unit"),
        "reported_unit": front.get("reported_unit"),
        "unit_policy": front.get("unit_policy"),
        "applicability": front.get("applicability"),
        "selection_policy": front.get("selection_policy"),
        "disclosure_group": front.get("disclosure_group"),
        "required_claims": front.get("required_claims"),
        "scope_dimensions": list(scope.get("required_dimensions", [])),
        "scope_aliases": scope.get("exact_enum_aliases"),
        "forbidden_confusions": list(front.get("forbidden_confusions", [])),
        "identity_constraints": front.get("identity_constraints"),
        "review_policy": front.get("review_policy"),
        "legacy_projection": front.get("legacy_projection"),
        "formula": formula,
    }


def describe_deterministic_source(member: Mapping[str, Any], path: str, member_id: str, sha256: str) -> Dict[str, Any]:
    """Project one deterministic catalog member."""
    branches = []
    for branch in member.get("branches", []):
        roles = [component["role"] for component in branch.get("components", [])]
        key = (branch.get("formula_id"), len(roles))
        if key not in DETERMINISTIC_FORMULA_TEMPLATES:
            raise ReferenceError("{}: unsupported deterministic formula {}".format(member_id, key))
        branches.append({
            "branch_id": branch.get("branch_id"),
            "formula_id": branch.get("formula_id"),
            "quality": branch.get("quality"),
            "expression": DETERMINISTIC_FORMULA_TEMPLATES[key].format(*roles),
            "components": [
                {
                    "role": component["role"],
                    "approved_concepts": list(component.get("approved_concepts", [])),
                    "accession_role": component.get("accession_role"),
                    "period_role": component.get("period_role"),
                    "unit": component.get("unit"),
                    "dimension_policy": component.get("dimension_policy"),
                    "required_dimensions": component.get("required_dimensions"),
                }
                for component in branch.get("components", [])
            ],
        })
    return {
        "path": path,
        "member": member_id,
        "sha256": sha256,
        "name": member.get("name"),
        "kind": "deterministic_catalog_member",
        "adapter_id": member.get("adapter_id"),
        "source_role": member.get("source_role"),
        "canonical_unit": member.get("canonical_unit"),
        "result_period_role": member.get("result_period_role"),
        "applicability": member.get("applicability"),
        "continuity_policy": member.get("continuity_policy"),
        "success_status": member.get("success_status"),
        "source_class": member.get("source_class"),
        "branches": branches,
    }


def describe_event_route(route: Mapping[str, Any], catalog: Mapping[str, Any], path: str, member_id: str, sha256: str) -> Dict[str, Any]:
    """Project one event route member together with catalog-level matching rules."""
    return {
        "path": path,
        "member": member_id,
        "sha256": sha256,
        "name": route.get("metric_name"),
        "kind": "event_route",
        "direct_item_codes": list(route.get("direct_item_codes", [])),
        "keyword_item_rules": route.get("keyword_item_rules", []),
        "shared_claim_group_id": route.get("shared_claim_group_id"),
        "legacy_projection": route.get("legacy_projection"),
        "text_normalization": catalog.get("text_normalization"),
        "match_mode": catalog.get("match_mode"),
        "brief_source_priority": list(catalog.get("brief_source_priority", [])),
        "applicability": None,
    }


def extract_definition_section(document: str, metric_id: str) -> str:
    """Return the verbatim definition text for one metric ID from the definition doc."""
    heading = re.compile(r"^### {}\b.*$".format(re.escape(metric_id)), re.M)
    match = heading.search(document)
    if match is not None:
        rest = document[match.end():]
        stop = re.search(r"^(### |## |---$)", rest, re.M)
        body = rest if stop is None else rest[: stop.start()]
        return (match.group(0) + body).strip()
    row = re.search(r"^\| {} \|.*$".format(re.escape(metric_id)), document, re.M)
    if row is None:
        raise ReferenceError("Definition document has no section or table row for {}".format(metric_id))
    return row.group(0).strip()


# ---------------------------------------------------------------------------
# Definition table
# ---------------------------------------------------------------------------


def _release_state(metric_id: str, context: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the explicit vNext release binding state for a metric."""
    if metric_id in context["active_metric_ids"]:
        return {
            "vnext_release_state": "ACTIVE_VNEXT_RELEASE_R3",
            "release_plan_id": context["active_plan_id"],
            "binding_paths": ["config/issue_15_release_plan.json", "config/release_plans/issue_15_lodging_r3.json"],
            "note_zh": "在 active 发布计划 cumulative_metric_ids 中；这证明 24 指标 partial ratchet，不证明 39 指标最终 Cutover。",
        }
    if metric_id in context["r4_metric_ids"]:
        return {
            "vnext_release_state": "R4_OFFLINE_PLAN_NOT_ACTIVE",
            "release_plan_id": context["r4_plan_id"],
            "binding_paths": ["config/release_plans/issue_28_r4_scoped_engine_v3.json"],
            "note_zh": "只在 Issue #28 R4 离线发布计划中；未激活、无 live 信用。",
        }
    if metric_id in context["r5_metric_ids"]:
        return {
            "vnext_release_state": "R5_STRUCTURED_DRAFT_NOT_AUTHORIZED",
            "release_plan_id": context["r5_draft_plan_status"],
            "binding_paths": ["config/r5_b06_structured_v1.json", "config/release_plans/issue_28_b06_structured_draft.json"],
            "note_zh": "R5 结构化主路径政策已合入 main，production_authorized={}，草案发布计划状态 {}。".format(
                context["r5_production_authorized"], context["r5_draft_plan_status"]
            ),
        }
    return {
        "vnext_release_state": "NOT_IN_VNEXT_RELEASE_PLAN",
        "release_plan_id": None,
        "binding_paths": [],
        "note_zh": "main 上没有把该指标纳入任何 vNext 发布计划；不推断生产状态。",
    }


def _data_sources_for(
    metric_id: str,
    kind: str,
    source: Mapping[str, Any],
    registry_entry: Mapping[str, Any],
    contracts_by_metric: Mapping[str, List[Dict[str, Any]]],
    metadata_entry: Mapping[str, Any],
    projection_entry: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Derive the data-source list for one metric from its bound definition."""
    sources: List[Dict[str, Any]] = []
    route_id = registry_entry.get("structured_route_id")
    if kind == "MAIN_DETERMINISTIC_CATALOG":
        for branch in source["branches"]:
            for component in branch["components"]:
                sources.append({
                    "role": component["role"],
                    "branch_id": branch["branch_id"],
                    "filing_types": ["10-K"],
                    "location": DETERMINISTIC_ADAPTER_DESCRIPTIONS[source["adapter_id"]],
                    "locator_kind": "xbrl_dimensioned_fact" if component["dimension_policy"] == "EXACT" else "xbrl_concept",
                    "concepts": component["approved_concepts"],
                    "required_dimensions": component["required_dimensions"] or None,
                    "accession_role": component["accession_role"],
                    "period_role": component["period_role"],
                    "unit": component["unit"],
                    "priority": "ordered_concept_chain",
                })
    elif kind == "MAIN_EVENT_ROUTE":
        sources.append({
            "role": "direct_item_codes",
            "filing_types": ["8-K"],
            "location": "8-K header item codes (HDR_SGML_ITEM_CODE) with primary-document heading fallback",
            "locator_kind": "8k_item_code",
            "item_codes": source["direct_item_codes"],
            "priority": source["brief_source_priority"],
        })
        for rule in source["keyword_item_rules"]:
            sources.append({
                "role": "keyword_item_rule",
                "filing_types": ["8-K"],
                "location": "8-K item {} text".format(rule.get("item_code")),
                "locator_kind": "8k_item_code_plus_keyword",
                "item_codes": [rule.get("item_code")],
                "keywords": list(rule.get("aliases", [])),
                "match_mode": source["match_mode"],
                "text_normalization": source["text_normalization"],
                "priority": None,
            })
    elif kind == "MAIN_STRUCTURED_SPEC":
        formula = source.get("formula")
        if source.get("selection_policy") == "legacy_companyfacts_v1":
            structured_location = "SEC companyfacts annual facts selected by legacy_companyfacts_v1 (10-K form prefix, fiscal-year target period, target accession priority, filed/accession/unit tie-break)"
        else:
            structured_location = "structured XBRL facts selected per the Spec's own roles and guards (registry structured route {})".format(route_id)
        if formula:
            for entry in formula["inputs"]:
                if entry["kind"] in ("structured_role", "extraction_role"):
                    sources.append({
                        "role": entry["role"],
                        "filing_types": ["10-K"],
                        "location": structured_location,
                        "locator_kind": "xbrl_concept",
                        "concepts": entry["approved_concepts"],
                        "cardinality": entry["cardinality"],
                        "priority": "ordered_concept_chain",
                    })
                elif entry["kind"] == "reuse_metric_observation":
                    sources.append({
                        "role": entry["role"],
                        "filing_types": ["10-K"],
                        "location": "verified observation reused from metric {}".format(entry["reuses_metric"]),
                        "locator_kind": "metric_dependency",
                        "concepts": [],
                        "priority": "dependency",
                    })
                elif entry["kind"] == "choose_first":
                    for branch in formula["fallback_branches"]:
                        if branch["role"] != entry["role"]:
                            continue
                        sources.append({
                            "role": branch["role"],
                            "branch_ordinal": branch["branch_ordinal"],
                            "filing_types": ["10-K"],
                            "location": structured_location,
                            "locator_kind": "xbrl_concept",
                            "concepts": branch.get("approved_concepts") or sorted(
                                {concept for concepts in branch.get("component_concepts", {}).values() for concept in concepts}
                            ),
                            "expression": branch.get("expression"),
                            "quality": branch.get("quality"),
                            "priority": "choose_first ordinal {}".format(branch["branch_ordinal"]),
                        })
        if source.get("source_mode") == "structured_first_ai_fallback" and not formula:
            sources.append({
                "role": "structured_first_route",
                "filing_types": [],
                "location": STRUCTURED_ROUTE_DESCRIPTIONS[route_id],
                "locator_kind": "source_strategy_route",
                "concepts": [],
                "concept_binding_on_main": "NOT_BOUND_ON_MAIN",
                "note": "declared structured-first route in config/source_strategy_registry.json; no main definition binds approved concepts for this route, so nothing more specific is stated",
                "priority": "structured_first",
            })
        if source.get("source_mode") in ("ai_table",) or (
            source.get("source_mode") == "structured_first_ai_fallback" and not formula
        ):
            contract_ids = [contract["task_contract_id"] for contract in contracts_by_metric.get(metric_id, [])]
            sources.append({
                "role": "table_claim",
                "filing_types": ["10-K"],
                "location": "reviewed table read from the selected disclosure table (disclosure_group={})".format(source.get("disclosure_group")),
                "locator_kind": "table_cell_locator",
                "required_claims": source.get("required_claims"),
                "scope_dimensions": source.get("scope_dimensions"),
                "table_task_contract_ids": contract_ids,
                "priority": "structured_first_then_table_fallback" if source.get("source_mode") == "structured_first_ai_fallback" else "ai_table_primary",
            })
    elif kind == "MAIN_TEXT_DEFINITION":
        for text_source in metadata_entry.get("text_sources", []):
            sources.append(dict(text_source))
        if route_id is not None:
            cited_concepts = sorted({
                concept
                for text_source in metadata_entry.get("text_sources", [])
                if text_source.get("locator_kind") == "xbrl_concept" and text_source.get("role") in ("primary", "secondary")
                for concept in text_source.get("concepts", [])
            })
            sources.append({
                "role": "registry_structured_route",
                "filing_types": [],
                "location": STRUCTURED_ROUTE_DESCRIPTIONS[route_id],
                "locator_kind": "source_strategy_route",
                "concepts": [],
                "concept_binding_on_main": "LEGACY_CODE_CITATION" if cited_concepts else "NOT_BOUND_ON_MAIN",
                "note": (
                    "declared target route in config/source_strategy_registry.json; the concrete fact is bound only by the verified legacy code citation above ({})".format(", ".join(cited_concepts))
                    if cited_concepts else
                    "declared target route in config/source_strategy_registry.json; main has no MetricSpec or verified legacy citation that binds a concept for this route, so no concept or filing is stated"
                ),
                "priority": "declared_target_route",
            })
    if kind == "MAIN_STRUCTURED_SPEC" and source.get("source_mode") == "structured_first_ai_fallback" and source.get("formula"):
        contract_ids = [contract["task_contract_id"] for contract in contracts_by_metric.get(metric_id, [])]
        sources.append({
            "role": "table_claim_fallback",
            "filing_types": ["10-K"],
            "location": "reviewed table read; only after fallback trigger {}".format(registry_entry.get("fallback_trigger_codes")),
            "locator_kind": "table_cell_locator",
            "table_task_contract_ids": contract_ids,
            "priority": "fallback_only",
        })
    if projection_entry is not None and projection_entry.get("zero_overlay"):
        sources.append({
            "role": "zero_hit_projection",
            "filing_types": ["8-K"],
            "location": "FY-window scan with no matching item",
            "locator_kind": "projection_rule",
            "status": projection_entry["zero_overlay"].get("status"),
            "priority": None,
        })
    return sources


def _period_and_scope(kind: str, source: Mapping[str, Any], projection_entry: Optional[Mapping[str, Any]], window_policy: Mapping[str, Any]) -> Dict[str, Any]:
    """Derive the period / scope block for one metric."""
    if kind == "MAIN_DETERMINISTIC_CATALOG":
        periods = sorted({component["period_role"] for branch in source["branches"] for component in branch["components"]})
        return {
            "period_role": source["result_period_role"],
            "component_period_roles": periods,
            "continuity_policy": source["continuity_policy"],
            "entity_or_business_scope": "consolidated registrant (undimensioned facts)" if source["adapter_id"] == "companyfacts" else "dimensioned instance facts per required_dimensions",
        }
    if kind == "MAIN_EVENT_ROUTE":
        return {
            "period_role": "fiscal_year_window_8k",
            "event_window_policy_by_continuity": dict(window_policy),
            "entity_or_business_scope": "all 8-K filings of the registrant within the window",
        }
    if kind == "MAIN_STRUCTURED_SPEC":
        guards = (source.get("formula") or {}).get("top_level_guards", [])
        annual = [guard for guard in guards if isinstance(guard, dict) and "annual_duration" in guard]
        claims = source.get("required_claims") or {}
        quality_rule = (source.get("formula") or {}).get("quality_rule")
        measurement_basis = quality_rule.get("measurement_basis") if isinstance(quality_rule, dict) else None
        if claims.get("period_role"):
            period_role = claims["period_role"]
        elif annual:
            period_role = "current_annual"
        elif measurement_basis:
            period_role = "current_instant"
        elif source.get("formula"):
            period_role = "target_period_per_selection_policy"
        else:
            period_role = "current_fiscal_year_table_claim"
        return {
            "period_role": period_role,
            "annual_duration_days": annual[0]["annual_duration"] if annual else None,
            "measurement_basis": measurement_basis,
            "top_level_guards": guards,
            "entity_or_business_scope": {k: v for k, v in claims.items() if k != "period_role"} or None,
            "selection_policy": source.get("selection_policy"),
        }
    return {
        "period_role": "target_fiscal_year_filing",
        "entity_or_business_scope": "registrant-level text of the selected filing",
    }


def _method_block(
    *,
    metric_id: str,
    kind: str,
    source: Mapping[str, Any],
    registry_entry: Mapping[str, Any],
    contracts_by_metric: Mapping[str, List[Dict[str, Any]]],
    metadata_entry: Mapping[str, Any],
    fallback_representation: Mapping[str, str],
    chosen: Mapping[str, Any],
) -> Dict[str, Any]:
    """Describe the selected reference implementation and the registry target route separately.

    The reference implementation is what the selected main definition (or the
    verified legacy code citation) actually does.  The registry target route
    is only what config/source_strategy_registry.json declares; its AI
    fallback representation comes from
    config/source_strategy_fallback_representation.json, never from the route
    id or the reader family name.
    """
    contract_ids = [contract["task_contract_id"] for contract in contracts_by_metric.get(metric_id, [])]
    source_mode = registry_entry["source_mode"]
    route_id = registry_entry["structured_route_id"]
    if kind == "MAIN_DETERMINISTIC_CATALOG":
        formula_ids = {branch["formula_id"] for branch in source["branches"]}
        method_types = ["DIRECT_XBRL_FACT" if formula_ids == {"direct"} else "XBRL_FORMULA"]
        basis = "catalog/deterministic_metrics.json member {} (adapter {}, formula ids {})".format(
            metric_id, source["adapter_id"], ", ".join(sorted(formula_ids))
        )
        binding = "DETERMINISTIC_CATALOG_MEMBER"
    elif kind == "MAIN_EVENT_ROUTE":
        method_types = ["EVENT_ITEM_RULE"]
        basis = "catalog/event_routes.json member {} (direct item codes {})".format(metric_id, ", ".join(source["direct_item_codes"]))
        binding = "EVENT_ROUTE_MEMBER"
    elif kind == "MAIN_STRUCTURED_SPEC" and source.get("formula"):
        method_types = ["XBRL_FORMULA" if source["kind"] == "derived_numeric" else "DIRECT_XBRL_FACT"]
        basis = "MetricSpec {} (kind {}, source_mode {})".format(source["path"], source["kind"], source.get("source_mode"))
        fallback_variants = [variant for variant in chosen["variants"] if variant["role"] == "ai_table_fallback_contract"]
        if fallback_variants:
            if not contract_ids:
                raise ReferenceError("{}: ai_table fallback variant declared without a table task contract".format(metric_id))
            method_types.append("AI_TABLE_READ_FALLBACK")
            basis += "; table fallback contract {} bound to variant {}".format(", ".join(contract_ids), fallback_variants[0]["path"])
        binding = "SPEC:{}".format(source["path"])
    elif kind == "MAIN_STRUCTURED_SPEC":
        if not contract_ids:
            raise ReferenceError("{}: table contract spec without a table task contract".format(metric_id))
        if source_mode == "ai_table":
            method_types = ["AI_TABLE_READ"]
            binding = "SPEC:{}".format(source["path"])
        elif source_mode == "structured_first_ai_fallback":
            method_types = ["AI_TABLE_READ_FALLBACK"]
            binding = "NOT_BOUND_ON_MAIN"
        else:
            raise ReferenceError("{}: table contract spec with unexpected registry source_mode {}".format(metric_id, source_mode))
        basis = "MetricSpec {} is the table task contract {} (disclosure_group {})".format(
            source["path"], ", ".join(contract_ids), source.get("disclosure_group")
        )
    else:
        method_types = []
        for text_source in metadata_entry.get("text_sources", []):
            if text_source.get("role") not in ("primary", "secondary"):
                continue
            method_type = LEGACY_LOCATOR_METHOD_TYPES.get(text_source.get("locator_kind"))
            if method_type is None:
                raise ReferenceError("{}: text source locator_kind {} has no method type".format(metric_id, text_source.get("locator_kind")))
            if method_type not in method_types:
                method_types.append(method_type)
        citations = metadata_entry.get("legacy_method", {}).get("citations", [])
        basis = "legacy pipeline code cited in metric_metadata.json ({}); no MetricSpec on main".format(
            ", ".join("{}::{}".format(c["path"], c["symbol"]) for c in citations if c.get("symbol"))
        )
        has_concept = any(
            text_source.get("locator_kind") == "xbrl_concept" and text_source.get("role") in ("primary", "secondary")
            for text_source in metadata_entry.get("text_sources", [])
        )
        binding = "LEGACY_CODE_CITATION" if has_concept else ("NOT_BOUND_ON_MAIN" if route_id else "NO_STRUCTURED_ROUTE")
    if source_mode == "structured_only":
        representation, representation_basis = None, "registry source_mode structured_only declares no AI fallback"
    elif source_mode == "ai_table":
        representation, representation_basis = "table", "registry source_mode ai_table"
    elif source_mode == "ai_text":
        representation, representation_basis = "text", "registry source_mode ai_text"
    else:
        representation = fallback_representation[metric_id]
        representation_basis = "config/source_strategy_fallback_representation.json#fallback_representation_by_metric.{}".format(metric_id)
    if representation == "table" and source_mode != "ai_text" and kind == "MAIN_STRUCTURED_SPEC" and not contract_ids:
        raise ReferenceError("{}: table representation declared without a table task contract".format(metric_id))
    return {
        "reference_implementation": {
            "method_types": method_types,
            "basis": basis,
        },
        "registry_target_route": {
            "source_mode": source_mode,
            "reader_family_id": registry_entry["reader_family_id"],
            "structured_route_id": route_id,
            "structured_route_description": STRUCTURED_ROUTE_DESCRIPTIONS.get(route_id),
            "structured_concept_binding_on_main": binding,
            "fallback_trigger_codes": list(registry_entry["fallback_trigger_codes"]),
            "ai_fallback_representation": representation,
            "ai_fallback_representation_basis": representation_basis,
            "coverage_mode": registry_entry["coverage_mode"],
            "note": "declared target strategy only; it does not state which concepts, filings or reviewers the current main implementation uses",
        },
    }


def build_metric_definitions(
    *,
    selection: Mapping[str, Any],
    metadata: Mapping[str, Any],
    loaded: Mapping[str, bytes],
    definition_sources: Mapping[str, Dict[str, Any]],
    sic_map: Mapping[str, Any],
    registry: Mapping[str, Any],
    contracts_by_metric: Mapping[str, List[Dict[str, Any]]],
    projection: Mapping[str, Any],
    release_context: Mapping[str, Any],
    migrated_metric_ids: Sequence[str],
    definition_document: str,
    fallback_representation: Mapping[str, str],
    text_definition_path: str,
) -> Dict[str, Any]:
    """Assemble one definition record per metric ID."""
    groups = metadata["groups"]
    metric_metadata = metadata["metrics"]
    if sorted(metric_metadata) != sorted(EXPECTED_METRIC_IDS):
        raise ReferenceError("metric_metadata must cover exactly the 39 metric IDs")
    status_values = set(metadata["status_vocabulary"]["legacy"]["values"]) | set(metadata["status_vocabulary"]["vnext"]["values"])
    rows_by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for row in sic_map["rows"]:
        rows_by_metric.setdefault(row["metric_id"], []).append(row)
    records = []
    for metric_id in EXPECTED_METRIC_IDS:
        chosen = selection["metrics"][metric_id]
        kind = chosen["definition_source_kind"]
        source = definition_sources[metric_id]
        meta = metric_metadata[metric_id]
        registry_entry = registry["metrics"][metric_id]
        projection_entry = projection["metrics"].get(metric_id)
        for status in meta["expected_statuses"]:
            if status not in status_values:
                raise ReferenceError("{}: expected status {} is not in the status vocabulary".format(metric_id, status))
        for citation in meta.get("legacy_method", {}).get("citations", []):
            verify_citation(loaded, citation, "{} legacy_method".format(metric_id))
        if kind == "MAIN_TEXT_DEFINITION" and not meta.get("text_sources"):
            raise ReferenceError("{}: text-defined metrics need text_sources in metadata".format(metric_id))
        if kind != "MAIN_TEXT_DEFINITION" and meta.get("text_sources"):
            raise ReferenceError("{}: text_sources are only allowed for text-defined metrics".format(metric_id))
        method = _method_block(
            metric_id=metric_id, kind=kind, source=source, registry_entry=registry_entry,
            contracts_by_metric=contracts_by_metric, metadata_entry=meta,
            fallback_representation=fallback_representation, chosen=chosen,
        )
        name_en = source.get("name")
        formula_block: Optional[Dict[str, Any]] = None
        if kind == "MAIN_DETERMINISTIC_CATALOG":
            formula_block = {
                "expression": source["branches"][0]["expression"],
                "branches": source["branches"],
                "legacy_formula_text": projection_entry["formula"] if projection_entry else None,
                "evaluator_citation": metadata["shared_citations"]["deterministic_formula_evaluator"],
            }
        elif kind == "MAIN_STRUCTURED_SPEC" and source.get("formula"):
            formula_block = dict(source["formula"])
            formula_block["identity_constraints"] = source.get("identity_constraints")
            formula_block["legacy_formula_text"] = (source.get("legacy_projection") or {}).get("formula")
        elif kind == "MAIN_STRUCTURED_SPEC":
            formula_block = {
                "expression": None,
                "note": "direct table claim; no arithmetic formula",
                "identity_constraints": source.get("identity_constraints"),
                "legacy_formula_text": (source.get("legacy_projection") or {}).get("formula"),
            }
        unit_block = {
            "canonical_unit": source.get("canonical_unit"),
            "reported_unit": source.get("reported_unit", source.get("canonical_unit")),
            "unit_policy": source.get("unit_policy"),
            "value_multiplier_to_legacy": (source.get("legacy_projection") or {}).get("value_multiplier"),
        }
        if kind == "MAIN_EVENT_ROUTE":
            unit_block = {"canonical_unit": "event_count", "reported_unit": "event_count", "unit_policy": None, "value_multiplier_to_legacy": None, "note": "event list / count; no monetary unit"}
        elif kind == "MAIN_TEXT_DEFINITION":
            explicit = meta.get("unit")
            unit_block = {"canonical_unit": explicit, "reported_unit": explicit, "unit_policy": None, "value_multiplier_to_legacy": None, "note": "text/flag metric; unit null unless stated"}
        applicable_rows = [
            {
                "sic_start": row["sic_start"],
                "sic_end": row["sic_end"],
                "profile": row["profile"],
                "applicability": row["business_applicability"],
                "priority": row["business_priority"],
                "rule_clause_id": row["rule_clause_id"],
            }
            for row in rows_by_metric.get(metric_id, [])
            if row["business_applicability"] != "NOT_APPLICABLE"
        ]
        industries: Dict[str, List[str]] = {value: [] for value in APPLICABILITY_VALUES}
        for row in rows_by_metric.get(metric_id, []):
            if row["profile"] not in industries[row["business_applicability"]]:
                industries[row["business_applicability"]].append(row["profile"])
        release = _release_state(metric_id, release_context)
        legacy = meta.get("legacy_method")
        records.append({
            "metric_id": metric_id,
            "group": metric_id[0],
            "group_label_zh": groups[metric_id[0]]["zh"],
            "group_label_en": groups[metric_id[0]]["en"],
            "name_en": name_en,
            "name_zh": meta["name_zh"],
            "description_zh": meta["description_zh"],
            "description_en": meta["description_en"],
            "method": method,
            "definition_source": {
                "kind": kind,
                "primary": {k: v for k, v in source.items() if k in ("path", "member", "section", "sha256", "name", "kind", "source_mode")},
                "binding_authority": chosen["binding_authority"],
                "binding_state_label": selection["binding_authorities"][chosen["binding_authority"]]["state_label"],
                "binding_paths": list(selection["binding_authorities"][chosen["binding_authority"]]["paths"]),
                "selection_reason_zh": chosen["selection_reason_zh"],
                "variants": [
                    dict(variant, sha256=sha256_bytes(loaded[variant["path"]]), name=definition_sources["__variants__"][variant["path"]]["name"], source_mode=definition_sources["__variants__"][variant["path"]]["source_mode"])
                    for variant in chosen["variants"]
                ],
                "development_references": [
                    dict(reference, commit=selection["read_only_development_reference"]["commit"], pull_request=selection["read_only_development_reference"]["pull_request"], verified_by_generator=False)
                    for reference in chosen["development_references"]
                ],
            },
            "data_sources": _data_sources_for(metric_id, kind, source, registry_entry, contracts_by_metric, meta, projection_entry),
            "formula": formula_block,
            "unit": unit_block,
            "period_and_scope": _period_and_scope(kind, source, projection_entry, projection["event_window_policy_by_continuity"]),
            "statuses": {
                "expected": list(meta["expected_statuses"]),
                "legacy_success_status": (projection_entry or {}).get("success_projection", {}).get("status") or (source.get("legacy_projection") or {}).get("status") or (source.get("legacy_projection") or {}).get("status_exact") or source.get("success_status") or meta.get("legacy_success_status"),
                "legacy_source_class": (projection_entry or {}).get("success_projection", {}).get("source_class") or (source.get("legacy_projection") or {}).get("source_class") or source.get("source_class") or meta.get("legacy_source_class"),
            },
            "applicable_sic_ranges": applicable_rows,
            "industries_by_applicability": industries,
            "implementation_status": {
                "vnext": release,
                "legacy_pipeline": {
                    "producer_state": "LEGACY_PRODUCER_RETIRED_FAIL_CLOSED" if metric_id in migrated_metric_ids else "LEGACY_PRODUCER_CODE_PRESENT",
                    "producer_state_basis": "config/vnext_release_plan.json#migrated_metric_ids" if metric_id in migrated_metric_ids else "scripts/sec_pipeline.py (not in migrated set)",
                    "method_summary_zh": legacy["summary_zh"] if legacy else None,
                    "citations": legacy["citations"] if legacy else [],
                },
                "verification_scope_zh": metadata["verification_scope_note"]["zh"],
            },
            "limitations_zh": list(meta.get("limitations_zh", [])),
            "definition_text_excerpt": extract_definition_section(definition_document, metric_id),
            "definition_text_excerpt_source": {
                "path": text_definition_path,
                "sha256": sha256_bytes(loaded[text_definition_path]),
                "section": metric_id,
            },
        })
    return {
        "schema_version": 1,
        "record_type": "METRIC_DEFINITIONS",
        "generated_by": "tools/generate_metrics_reference.py",
        "not_a_production_pointer": True,
        "selection_principle": selection["selection_principle"],
        "baseline_commit_recorded": selection["baseline"]["commit"],
        "development_reference_commit_recorded": selection["read_only_development_reference"]["commit"],
        "definition_source_kinds": {
            "MAIN_STRUCTURED_SPEC": "main 上的 MetricSpec 前置 JSON（结构化或表格合同）。",
            "MAIN_DETERMINISTIC_CATALOG": "main 上 catalog/deterministic_metrics.json 的成员。",
            "MAIN_EVENT_ROUTE": "main 上 catalog/event_routes.json 的成员。",
            "MAIN_TEXT_DEFINITION": "main 上没有结构化定义；以 02_指标定义 文本与 legacy 代码引用为准。",
        },
        "status_vocabulary": metadata["status_vocabulary"],
        "verification_scope_note": metadata["verification_scope_note"],
        "metric_count": len(records),
        "metrics": records,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_reference(repo_root: Path, *, verify_digests: bool = True) -> Dict[str, Any]:
    """Load every input and return the two rendered tables and their bytes."""
    selection = _json(_read_bytes(repo_root, SOURCE_SELECTION_PATH.as_posix()), "source_selection.json")
    metadata = _json(_read_bytes(repo_root, METADATA_PATH.as_posix()), "metric_metadata.json")
    rules = _json(_read_bytes(repo_root, RULES_PATH.as_posix()), "sic_metric_rules.json")
    if selection.get("record_type") != "METRICS_REFERENCE_SOURCE_SELECTION" or selection.get("not_a_production_pointer") is not True:
        raise ReferenceError("source_selection.json must declare record_type and not_a_production_pointer=true")
    if metadata.get("record_type") != "METRIC_REFERENCE_METADATA":
        raise ReferenceError("metric_metadata.json record_type differs")
    if rules.get("record_type") != "SIC_METRIC_RULES":
        raise ReferenceError("sic_metric_rules.json record_type differs")
    loaded = load_inputs(
        repo_root, selection, verify_digests=verify_digests, cited_symbols_by_path=cited_symbols(metadata),
    )
    for label, citation in metadata["shared_citations"].items():
        verify_citation(loaded, citation, "shared_citations.{}".format(label))
    for label in ("legacy", "vnext"):
        verify_citation(loaded, metadata["status_vocabulary"][label]["citation"], "status_vocabulary.{}".format(label))

    registry = _json(loaded["config/source_strategy_registry.json"], "source_strategy_registry")
    if sorted(registry["metrics"]) != sorted(EXPECTED_METRIC_IDS):
        raise ReferenceError("source_strategy_registry must cover exactly the 39 metric IDs")
    for route_id in {entry["structured_route_id"] for entry in registry["metrics"].values()} - {None}:
        if route_id not in STRUCTURED_ROUTE_DESCRIPTIONS:
            raise ReferenceError("Structured route {} has no description".format(route_id))
    projection = _json(loaded["catalog/zero_ai_public_projection.json"], "zero_ai_public_projection")
    fallback_authority = _json(loaded["config/source_strategy_fallback_representation.json"], "source_strategy_fallback_representation")
    fallback_representation = _fallback_representation(fallback_authority, registry, loaded["config/source_strategy_registry.json"])
    contracts = _json(loaded["catalog/table_task_contracts.json"], "table_task_contracts")
    contracts_by_metric: Dict[str, List[Dict[str, Any]]] = {}
    for contract in contracts["contracts"]:
        for metric_id in contract["metric_ids"]:
            contracts_by_metric.setdefault(metric_id, []).append(contract)
    applicability_config = _json(loaded["config/metric_applicability.yaml"], "metric_applicability")
    trait_catalog = _json(loaded["catalog/company_traits.yaml"], "company_traits")
    registry_rows = _registry_companies(loaded["config/company_registry.csv"])
    release_index = _json(loaded["config/issue_15_release_plan.json"], "issue_15_release_plan")
    active_plan = _json(loaded["config/release_plans/issue_15_lodging_r3.json"], "issue_15_lodging_r3")
    if release_index["active_release_plan_id"] != active_plan["release_plan_id"]:
        raise ReferenceError("Active release plan id differs from the declared R3 plan")
    r4_plan = _json(loaded["config/release_plans/issue_28_r4_scoped_engine_v3.json"], "issue_28_r4_scoped_engine_v3")
    r5_policy = _json(loaded["config/r5_b06_structured_v1.json"], "r5_b06_structured_v1")
    r5_draft = _json(loaded["config/release_plans/issue_28_b06_structured_draft.json"], "issue_28_b06_structured_draft")
    migrated = _json(loaded["config/vnext_release_plan.json"], "vnext_release_plan")["migrated_metric_ids"]
    text_definition_paths = [relative for relative, entry in selection["inputs"].items() if entry["role"] == "text_definition"]
    if len(text_definition_paths) != 1:
        raise ReferenceError("Exactly one declared input must carry role text_definition")
    text_definition_path = text_definition_paths[0]
    definition_document = loaded[text_definition_path].decode("utf-8")
    parsed_cache: Dict[str, Any] = {}

    definition_sources: Dict[str, Any] = {"__variants__": {}}
    selected_metrics = selection.get("metrics")
    if not isinstance(selected_metrics, dict) or sorted(selected_metrics) != sorted(EXPECTED_METRIC_IDS):
        raise ReferenceError("source_selection metrics must cover exactly the 39 metric IDs")
    for metric_id in EXPECTED_METRIC_IDS:
        chosen = selected_metrics[metric_id]
        required = {"definition_source_kind", "primary", "binding_authority", "selection_reason_zh", "variants", "development_references"}
        if not isinstance(chosen, dict) or set(chosen) != required:
            raise ReferenceError("{}: selection fields must be exactly {}".format(metric_id, sorted(required)))
        kind = chosen["definition_source_kind"]
        if kind not in DEFINITION_SOURCE_KINDS:
            raise ReferenceError("{}: unknown definition_source_kind {}".format(metric_id, kind))
        if chosen["binding_authority"] not in selection["binding_authorities"]:
            raise ReferenceError("{}: unknown binding_authority {}".format(metric_id, chosen["binding_authority"]))
        primary = chosen["primary"]
        if not isinstance(primary, dict) or "path" not in primary:
            raise ReferenceError("{}: primary must be an object with a path".format(metric_id))
        path = primary["path"]
        if path not in loaded:
            raise ReferenceError("{}: primary path {} is not a declared input".format(metric_id, path))
        role = selection["inputs"][path]["role"]
        if role not in PRIMARY_ROLES_BY_KIND[kind]:
            raise ReferenceError(
                "{}: primary path {} has input role {} which is not allowed for {} (allowed: {})".format(
                    metric_id, path, role, kind, ", ".join(sorted(PRIMARY_ROLES_BY_KIND[kind]))
                )
            )
        digest = sha256_bytes(loaded[path])
        if kind == "MAIN_STRUCTURED_SPEC":
            if set(primary) != {"path"}:
                raise ReferenceError("{}: spec primary must have only a path".format(metric_id))
            front, _body = parse_front_matter(loaded[path].decode("utf-8"), path)
            if front.get("metric_id") != metric_id:
                raise ReferenceError("{}: spec {} declares metric_id {}".format(metric_id, path, front.get("metric_id")))
            definition_sources[metric_id] = describe_spec_source(front, path, digest)
        elif kind == "MAIN_DETERMINISTIC_CATALOG":
            if set(primary) != {"path", "member"} or primary["member"] != metric_id:
                raise ReferenceError("{}: deterministic primary needs path and member == metric id".format(metric_id))
            catalog = parsed_cache.setdefault(path, _json(loaded[path], path))
            if not isinstance(catalog, dict) or catalog.get("record_type") != "DETERMINISTIC_METRIC_CATALOG" or not isinstance(catalog.get("metrics"), dict):
                raise ReferenceError("{}: {} is not a DETERMINISTIC_METRIC_CATALOG".format(metric_id, path))
            member = catalog["metrics"].get(metric_id)
            if member is None:
                raise ReferenceError("{}: deterministic member {} is missing in {}".format(metric_id, metric_id, path))
            definition_sources[metric_id] = describe_deterministic_source(member, path, metric_id, digest)
        elif kind == "MAIN_EVENT_ROUTE":
            if set(primary) != {"path", "member"} or primary["member"] != metric_id:
                raise ReferenceError("{}: event primary needs path and member == metric id".format(metric_id))
            catalog = parsed_cache.setdefault(path, _json(loaded[path], path))
            if not isinstance(catalog, dict) or catalog.get("record_type") != "DETERMINISTIC_EVENT_ROUTE_CATALOG" or not isinstance(catalog.get("routes"), dict):
                raise ReferenceError("{}: {} is not a DETERMINISTIC_EVENT_ROUTE_CATALOG".format(metric_id, path))
            route = catalog["routes"].get(metric_id)
            if route is None:
                raise ReferenceError("{}: event route {} is missing in {}".format(metric_id, metric_id, path))
            definition_sources[metric_id] = describe_event_route(route, catalog, path, metric_id, digest)
        else:
            if set(primary) != {"path", "section"} or primary["section"] != metric_id:
                raise ReferenceError("{}: text primary needs path and section == metric id".format(metric_id))
            document = loaded[path].decode("utf-8")
            section_text = extract_definition_section(document, metric_id)
            definition_sources[metric_id] = {
                "path": path,
                "section": metric_id,
                "sha256": digest,
                "name": _text_definition_name(document, metric_id),
                "kind": "text_definition",
                "source_mode": registry["metrics"][metric_id]["source_mode"],
                "applicability": None,
                "section_sha256": sha256_bytes(section_text.encode("utf-8")),
            }
        for variant in chosen["variants"]:
            if set(variant) != {"role", "path", "binding_authority"}:
                raise ReferenceError("{}: variant fields must be role, path, binding_authority".format(metric_id))
            if variant["path"] not in loaded:
                raise ReferenceError("{}: variant path {} is not a declared input".format(metric_id, variant["path"]))
            if selection["inputs"][variant["path"]]["role"] not in VARIANT_ROLES:
                raise ReferenceError("{}: variant path {} has role {} which is not a spec role".format(metric_id, variant["path"], selection["inputs"][variant["path"]]["role"]))
            if variant["binding_authority"] is not None and variant["binding_authority"] not in selection["binding_authorities"]:
                raise ReferenceError("{}: unknown variant binding_authority".format(metric_id))
            front, _body = parse_front_matter(loaded[variant["path"]].decode("utf-8"), variant["path"])
            expected_id = metric_id if front.get("kind") != "disclosure_group" else front.get("metric_id")
            if front.get("metric_id") != expected_id:
                raise ReferenceError("{}: variant {} declares metric_id {}".format(metric_id, variant["path"], front.get("metric_id")))
            definition_sources["__variants__"][variant["path"]] = {"name": front.get("name"), "source_mode": front.get("source_mode")}
        for reference in chosen["development_references"]:
            if set(reference) != {"path", "sha256", "note_zh"} or not re.fullmatch(r"[0-9a-f]{64}", str(reference["sha256"])):
                raise ReferenceError("{}: development references need path, 64-hex sha256 and note_zh".format(metric_id))

    metric_names = {
        metric_id: (definition_sources[metric_id]["name"], metadata["metrics"][metric_id]["name_zh"])
        for metric_id in EXPECTED_METRIC_IDS
    }
    sic_map = build_sic_metric_map(
        rules=rules,
        sic_ranges=load_sic_ranges(applicability_config),
        profile_traits=_profile_traits(trait_catalog),
        registry_rows=registry_rows,
        definition_sources=definition_sources,
        metric_names=metric_names,
    )
    release_context = {
        "active_metric_ids": list(active_plan["cumulative_metric_ids"]),
        "active_plan_id": active_plan["release_plan_id"],
        "r4_metric_ids": [m for m in r4_plan["cumulative_metric_ids"] if m not in active_plan["cumulative_metric_ids"]],
        "r4_plan_id": r4_plan["release_plan_id"],
        "r5_metric_ids": list(r5_policy["metric_ids"]),
        "r5_production_authorized": r5_policy["production_authorized"],
        "r5_draft_plan_status": r5_draft["status"],
    }
    if r5_policy["primary_spec"] != selected_metrics["B06"]["primary"]["path"]:
        raise ReferenceError("B06 primary must equal config/r5_b06_structured_v1.json primary_spec")
    definitions = build_metric_definitions(
        selection=selection,
        metadata=metadata,
        loaded=loaded,
        definition_sources=definition_sources,
        sic_map=sic_map,
        registry=registry,
        contracts_by_metric=contracts_by_metric,
        projection=projection,
        release_context=release_context,
        migrated_metric_ids=migrated,
        definition_document=definition_document,
        fallback_representation=fallback_representation,
        text_definition_path=text_definition_path,
    )
    return {
        "sic_metric_map": sic_map,
        "metric_definitions": definitions,
        "files": {
            MAP_JSON_PATH.as_posix(): render_json(sic_map),
            MAP_CSV_PATH.as_posix(): render_csv(MAP_CSV_COLUMNS, sic_map["rows"]),
            DEFINITIONS_JSON_PATH.as_posix(): render_json(definitions),
            DEFINITIONS_CSV_PATH.as_posix(): render_csv(DEFINITIONS_CSV_COLUMNS, [definition_csv_row(record) for record in definitions["metrics"]]),
        },
    }


def _fallback_representation(authority: Mapping[str, Any], registry: Mapping[str, Any], registry_bytes: bytes) -> Dict[str, str]:
    """Return the per-metric AI fallback representation bound to the registry.

    Mirrors the structural checks of scripts/vnext/table_task_contracts.py:
    exact fields, record type, registry SHA-256 binding, metric set equal to
    every structured_first_ai_fallback route, values in {table, text}.
    """
    expected_fields = {"schema_version", "record_type", "source_strategy_registry_sha256", "fallback_representation_by_metric"}
    if not isinstance(authority, dict) or set(authority) != expected_fields:
        raise ReferenceError("Fallback representation fields are not exact")
    if authority["record_type"] != "ISSUE_15_SOURCE_STRATEGY_FALLBACK_REPRESENTATION":
        raise ReferenceError("Fallback representation record_type differs")
    if authority["source_strategy_registry_sha256"] != sha256_bytes(registry_bytes):
        raise ReferenceError("Fallback representation is bound to a different source_strategy_registry.json")
    representations = authority["fallback_representation_by_metric"]
    expected = {metric_id for metric_id, entry in registry["metrics"].items() if entry["source_mode"] == "structured_first_ai_fallback"}
    if not isinstance(representations, dict) or set(representations) != expected:
        raise ReferenceError("Fallback representation metric set differs from the registry")
    if any(value not in ("table", "text") for value in representations.values()):
        raise ReferenceError("Fallback representation value is invalid")
    return {metric_id: str(value) for metric_id, value in representations.items()}


def _text_definition_name(document: str, metric_id: str) -> str:
    """Return the English heading name of a text-defined metric."""
    section = extract_definition_section(document, metric_id)
    first = section.split("\n", 1)[0]
    return first[len("### {} ".format(metric_id)):].strip()


def definition_csv_row(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten one definition record for the derived CSV view."""
    period = record["period_and_scope"]
    return {
        "metric_id": record["metric_id"],
        "group": record["group"],
        "name_en": record["name_en"],
        "name_zh": record["name_zh"],
        "description_zh": record["description_zh"],
        "description_en": record["description_en"],
        "method_types": record["method"]["reference_implementation"]["method_types"],
        "source_mode": record["method"]["registry_target_route"]["source_mode"],
        "reader_family_id": record["method"]["registry_target_route"]["reader_family_id"],
        "structured_route_id": record["method"]["registry_target_route"]["structured_route_id"],
        "ai_fallback_representation": record["method"]["registry_target_route"]["ai_fallback_representation"],
        "definition_source_kind": record["definition_source"]["kind"],
        "definition_source_path": record["definition_source"]["primary"]["path"],
        "binding_authority": record["definition_source"]["binding_authority"],
        "binding_state_label": record["definition_source"]["binding_state_label"],
        "data_sources": [
            "{}: {} [{}]".format(source.get("role"), source.get("location"), ", ".join(source.get("concepts") or source.get("item_codes") or source.get("patterns") or []))
            for source in record["data_sources"]
        ],
        "formula_expression": (record["formula"] or {}).get("expression"),
        "canonical_unit": record["unit"]["canonical_unit"],
        "reported_unit": record["unit"]["reported_unit"],
        "period_role": period.get("period_role"),
        "entity_or_business_scope": period.get("entity_or_business_scope"),
        "expected_statuses": record["statuses"]["expected"],
        "applicable_sic_ranges": ["{}-{} {} {}".format(r["sic_start"], r["sic_end"], r["profile"], r["applicability"]) for r in record["applicable_sic_ranges"]],
        "vnext_release_state": record["implementation_status"]["vnext"]["vnext_release_state"],
        "legacy_producer_state": record["implementation_status"]["legacy_pipeline"]["producer_state"],
        "limitations_zh": record["limitations_zh"],
    }


def render_json(payload: Mapping[str, Any]) -> bytes:
    """Serialize deterministically: sorted keys, UTF-8, two-space indent, LF."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _csv_cell(value: Any) -> str:
    """Render one CSV cell; lists join with ' | ', None becomes empty."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(_csv_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def render_csv(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    """Render rows with a fixed column order and LF line endings."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_cell(row.get(column)) for column in columns])
    return buffer.getvalue().encode("utf-8")


def check_reference(repo_root: Path) -> List[str]:
    """Return mismatch messages between rendered bytes and committed files."""
    rendered = build_reference(repo_root, verify_digests=True)["files"]
    problems = []
    for relative in sorted(rendered):
        path = repo_root / relative
        if not path.is_file():
            problems.append("{}: missing generated file".format(relative))
            continue
        if path.read_bytes() != rendered[relative]:
            problems.append("{}: committed bytes differ from generator output".format(relative))
    return problems


def write_reference(repo_root: Path) -> List[str]:
    """Write generated files and return the paths written."""
    rendered = build_reference(repo_root, verify_digests=True)["files"]
    written = []
    for relative in sorted(rendered):
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered[relative])
        written.append(relative)
    return written


def refresh_source_digests(repo_root: Path) -> List[str]:
    """Rewrite only the sha256 fields of source_selection.json and report changes."""
    selection_path = repo_root / SOURCE_SELECTION_PATH
    selection = _json(_read_bytes(repo_root, SOURCE_SELECTION_PATH.as_posix()), "source_selection.json")
    metadata = _json(_read_bytes(repo_root, METADATA_PATH.as_posix()), "metric_metadata.json")
    cited = cited_symbols(metadata)
    loaded = load_inputs(repo_root, selection, verify_digests=False, cited_symbols_by_path=cited)
    changed = []
    for relative in sorted(selection["inputs"]):
        actual = input_digest(relative, loaded[relative], selection["inputs"][relative], cited.get(relative, []))
        if selection["inputs"][relative]["sha256"] != actual:
            changed.append("{}: {} -> {}".format(relative, selection["inputs"][relative]["sha256"], actual))
            selection["inputs"][relative]["sha256"] = actual
    selection_path.write_bytes((json.dumps(selection, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return changed


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", default=None, help="Repository root (default: parent of tools/)")
    parser.add_argument("--check", action="store_true", help="Read-only: verify digests and compare committed generated files")
    parser.add_argument("--refresh-source-digests", action="store_true", help="Explicitly rewrite sha256 fields in source_selection.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    arguments = build_parser().parse_args(argv)
    repo_root = Path(arguments.repo_root).resolve() if arguments.repo_root else Path(__file__).resolve().parents[1]
    try:
        if arguments.refresh_source_digests:
            for line in refresh_source_digests(repo_root):
                print("digest updated: " + line)
            print("source digests refreshed")
        if arguments.check:
            problems = check_reference(repo_root)
            if problems:
                for problem in problems:
                    print("CHECK FAIL: " + problem)
                return 1
            print("CHECK PASS: generated reference tables match committed inputs")
            return 0
        if not arguments.refresh_source_digests:
            for relative in write_reference(repo_root):
                print("wrote " + relative)
        return 0
    except ReferenceError as error:
        print("REFERENCE ERROR: {}".format(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
