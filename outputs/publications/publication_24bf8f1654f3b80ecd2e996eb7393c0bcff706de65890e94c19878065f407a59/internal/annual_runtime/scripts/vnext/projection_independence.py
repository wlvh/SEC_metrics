"""Prove zero-AI producers and public rendering exclude legacy semantics."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Mapping, Sequence

from .canonical import content_hash, sha256_file


TARGETS = {
    "scripts/vnext/public_projection.py": ("render_public_rows",),
    "scripts/vnext/zero_ai_r2.py": (
        "_deterministic_metric_graph", "_event_graphs",
    ),
    "scripts/vnext/zero_ai_release.py": ("_freeze_r1_runs",),
}
FORBIDDEN_IDENTIFIERS = {
    "expected_value", "legacy_evidence", "legacy_metric_template",
    "legacy_metrics", "legacy_row", "legacy_rows", "value_raw",
}
ORCHESTRATORS = {
    "scripts/vnext/zero_ai_r2.py": "_r2_public_candidate",
    "scripts/vnext/zero_ai_release.py": "_prepare_r1_successor",
}


class ProjectionIndependenceError(ValueError):
    """Report a mixed production/oracle call graph or semantic input."""


def _function(*, tree: ast.AST, name: str) -> ast.FunctionDef:
    """Return one uniquely named top-level function."""
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise ProjectionIndependenceError("Projection symbol is ambiguous")
    return matches[0]


def _identifiers(*, function: ast.FunctionDef) -> set[str]:
    """Return semantic identifiers used by one function AST."""
    identifiers = {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name)
    }
    identifiers.update(argument.arg for argument in function.args.args)
    identifiers.update(argument.arg for argument in function.args.kwonlyargs)
    return identifiers


def _call_lines(
    *, function: ast.FunctionDef, names: Sequence[str],
) -> Dict[str, int]:
    """Return the first line for every required direct function call."""
    lines = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id in names and node.func.id not in lines:
            lines[node.func.id] = node.lineno
    if set(lines) != set(names):
        raise ProjectionIndependenceError("Projection call edge is absent")
    return lines


def build_projection_independence_receipt(
    *, repo_root: Path,
) -> Dict[str, object]:
    """Build a content-addressed AST proof for producer/oracle separation."""
    target_bindings = []
    parsed: Dict[str, ast.Module] = {}
    for relative, symbols in TARGETS.items():
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise ProjectionIndependenceError("Projection source is unsafe")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            raise ProjectionIndependenceError(
                "Projection source is invalid"
            ) from error
        parsed[relative] = tree
        for symbol in symbols:
            function = _function(tree=tree, name=symbol)
            forbidden = sorted(
                _identifiers(function=function).intersection(
                    FORBIDDEN_IDENTIFIERS
                )
            )
            if forbidden:
                raise ProjectionIndependenceError(
                    "Projection producer accepts legacy semantics"
                )
            if any(
                isinstance(node, ast.Name) and node.id == "compare_public_rows"
                for node in ast.walk(function)
            ):
                raise ProjectionIndependenceError(
                    "Projection producer calls its compatibility oracle"
                )
            target_bindings.append({
                "symbol": relative + "::" + symbol,
                "argument_exact_set": sorted(
                    argument.arg for argument in function.args.kwonlyargs
                ),
                "function_ast_hash": content_hash(
                    value=ast.dump(function, include_attributes=False)
                ),
                "source_sha256": sha256_file(path=path),
            })
    orchestrator_bindings = []
    for relative, symbol in ORCHESTRATORS.items():
        function = _function(tree=parsed[relative], name=symbol)
        lines = _call_lines(
            function=function,
            names=("render_public_rows", "compare_public_rows"),
        )
        if lines["render_public_rows"] >= lines["compare_public_rows"]:
            raise ProjectionIndependenceError(
                "Compatibility oracle precedes independent rendering"
            )
        orchestrator_bindings.append({
            "symbol": relative + "::" + symbol,
            "render_call_line": lines["render_public_rows"],
            "compatibility_call_line": lines["compare_public_rows"],
        })
    body = {
        "schema_version": 1,
        "record_type": "ZERO_AI_PROJECTION_INDEPENDENCE_RECEIPT",
        "status": "PASSED",
        "forbidden_identifier_exact_set": sorted(FORBIDDEN_IDENTIFIERS),
        "production_target_bindings": target_bindings,
        "orchestrator_bindings": orchestrator_bindings,
        "compatibility_oracle_exact_set": [
            "scripts/vnext/public_projection.py::compare_public_rows"
        ],
    }
    return {
        **body,
        "projection_independence_receipt_id": content_hash(value=body),
    }
