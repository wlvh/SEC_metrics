#!/usr/bin/env python3
"""Count the complete JPM table grid without materializing expanded objects.

The tool reuses the production raw HTML parser and text transform, but replaces
full expanded cell allocation with per-row non-overlapping span intervals.  It
does not change parser limits, select tables, fetch bytes, or implement any of
the option matrix choices recorded in its receipt.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.canonical import atomic_write_json  # noqa: E402
from vnext.canonical import canonical_json_bytes, content_hash  # noqa: E402
from vnext.canonical import sha256_bytes, sha256_file  # noqa: E402
from vnext.resource_limits import RESOURCE_LIMITS  # noqa: E402
from vnext.table_grid import _AllTablesParser, _semantic_text  # noqa: E402


SOURCE_RELATIVE = Path(
    "evidence/request_attempts/4d/"
    "4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/"
    "jpm-20251231.htm"
)
SOURCE_SHA256 = (
    "4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23"
)
OUTPUT_ROOT = (
    Path("artifacts/vnext/table_stage_b_investigation/financial_grid_census")
)
TOOL_RELATIVE = Path("tools/investigate_jpm_financial_grid.py")
TABLE_GRID_RELATIVE = Path("scripts/vnext/table_grid.py")
RESOURCE_LIMITS_RELATIVE = Path("scripts/vnext/resource_limits.py")
PRODUCTION_GATE = 100000
GRID_HASH_PLACEHOLDER = "sha256:" + "0" * 64
DERIVED_ASSET_HASH_PLACEHOLDER = "sha256:" + "0" * 64


class FinancialGridCensusError(RuntimeError):
    """Report invalid source structure or a non-reproducible census."""


class _NestingCounter(HTMLParser):
    """Count nested table depth without retaining non-table HTML state."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.depth_by_order: List[int] = []
        self.nested_table_count = 0
        self.maximum_depth = 0

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]],
    ) -> None:
        del attrs
        if tag != "table":
            return
        self.depth += 1
        self.depth_by_order.append(self.depth)
        if self.depth > 1:
            self.nested_table_count += 1
        self.maximum_depth = max(self.maximum_depth, self.depth)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.depth:
            self.depth -= 1


def _json_size(*, value: object) -> int:
    """Return compact canonical JSON size without the trailing LF."""
    return len(json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8"))


def _mapping_size(*, value_sizes: Mapping[str, int]) -> int:
    """Return exact object size from precomputed canonical value sizes."""
    if not value_sizes:
        return 2
    return (
        2
        + len(value_sizes) - 1
        + sum(
            _json_size(value=key) + 1 + int(value_sizes[key])
            for key in sorted(value_sizes)
        )
    )


def _array_size(*, item_sizes: Sequence[int]) -> int:
    """Return exact array size from ordered canonical item sizes."""
    return 2 + max(0, len(item_sizes) - 1) + sum(item_sizes)


def _ratio(*, numerator: int, denominator: int) -> str:
    """Return one stable eight-decimal ratio without binary float drift."""
    if denominator == 0:
        return "0.00000000"
    value = (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.00000001"),
        rounding=ROUND_HALF_EVEN,
    )
    return format(value, "f")


def _overlaps(
    *, intervals: Sequence[Mapping[str, object]], start: int, end: int,
) -> bool:
    """Return whether one half-open column interval overlaps a placed span."""
    return any(
        start < int(interval["end"]) and end > int(interval["start"])
        for interval in intervals
    )


def _next_free_column(
    *, intervals: Sequence[Mapping[str, object]], start: int,
) -> int:
    """Skip prior rowspans exactly as the production expander does."""
    column = start
    for interval in sorted(intervals, key=lambda item: int(item["start"])):
        interval_start = int(interval["start"])
        interval_end = int(interval["end"])
        if column < interval_start:
            break
        if interval_start <= column < interval_end:
            column = interval_end
    return column


def _cell_for_coordinate(
    *, row_index: int, column_index: int,
    intervals: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Construct only one expanded cell for canonical-size accounting."""
    match = next(
        (
            interval for interval in intervals
            if int(interval["start"]) <= column_index < int(interval["end"])
        ),
        None,
    )
    if match is None:
        return {
            "row_index": row_index,
            "column_index": column_index,
            "origin_row_index": row_index,
            "origin_column_index": column_index,
            "rowspan": 1,
            "colspan": 1,
            "header": False,
            "is_origin": True,
            "raw_text": "",
            "text": "",
        }
    origin = match["origin"]
    return {
        "row_index": row_index,
        "column_index": column_index,
        "origin_row_index": origin["origin_row_index"],
        "origin_column_index": origin["origin_column_index"],
        "rowspan": origin["rowspan"],
        "colspan": origin["colspan"],
        "header": origin["header"],
        "is_origin": (
            row_index == origin["origin_row_index"]
            and column_index == origin["origin_column_index"]
        ),
        "raw_text": origin["raw_text"],
        "text": origin["text"],
    }


def _table_census(
    *, builder: object, nesting_depth: int,
) -> Dict[str, object]:
    """Count one table using row intervals rather than expanded cell dicts."""
    intervals_by_row: Dict[int, List[Dict[str, object]]] = {}
    maximum_row = len(builder.rows) - 1
    maximum_column = -1
    origin_cell_count = 0
    span_duplicate_count = 0
    raw_text_chars = 0
    normalized_text_chars = 0
    expanded_raw_text_chars = 0
    expanded_normalized_text_chars = 0
    for row_index, source_row in enumerate(builder.rows):
        column_index = 0
        for cell in source_row:
            row_intervals = intervals_by_row.setdefault(row_index, [])
            column_index = _next_free_column(
                intervals=row_intervals,
                start=column_index,
            )
            row_end = row_index + cell.rowspan
            column_end = column_index + cell.colspan
            for target_row in range(row_index, row_end):
                target = intervals_by_row.setdefault(target_row, [])
                if _overlaps(
                    intervals=target,
                    start=column_index,
                    end=column_end,
                ):
                    raise FinancialGridCensusError(
                        "Census found overlapping merged cells"
                    )
            raw_text = "".join(cell.raw_parts)
            text = _semantic_text(raw_text=raw_text)
            origin = {
                "origin_row_index": row_index,
                "origin_column_index": column_index,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "header": cell.header,
                "raw_text": raw_text,
                "text": text,
            }
            for target_row in range(row_index, row_end):
                intervals_by_row[target_row].append({
                    "start": column_index,
                    "end": column_end,
                    "origin": origin,
                })
                intervals_by_row[target_row].sort(
                    key=lambda item: int(item["start"])
                )
            span_cells = cell.rowspan * cell.colspan
            origin_cell_count += 1
            span_duplicate_count += span_cells - 1
            raw_text_chars += len(raw_text)
            normalized_text_chars += len(text)
            expanded_raw_text_chars += span_cells * len(raw_text)
            expanded_normalized_text_chars += span_cells * len(text)
            maximum_row = max(maximum_row, row_end - 1)
            maximum_column = max(maximum_column, column_end - 1)
            column_index = column_end
    row_count = maximum_row + 1 if maximum_row >= 0 else 0
    column_count = maximum_column + 1 if maximum_column >= 0 else 0
    rectangular_cells = row_count * column_count
    occupied_cells = sum(
        int(interval["end"]) - int(interval["start"])
        for intervals in intervals_by_row.values()
        for interval in intervals
    )
    synthetic_blanks = rectangular_cells - occupied_cells
    if synthetic_blanks < 0:
        raise FinancialGridCensusError("Synthetic blank count is negative")
    caption_raw_text = "".join(builder.caption_parts)
    caption = _semantic_text(raw_text=caption_raw_text)
    raw_text_chars += len(caption_raw_text)
    normalized_text_chars += len(caption)
    expanded_raw_text_chars += len(caption_raw_text)
    expanded_normalized_text_chars += len(caption)

    row_sizes = []
    for row_index in range(row_count):
        cells = [
            _cell_for_coordinate(
                row_index=row_index,
                column_index=column_index,
                intervals=intervals_by_row.get(row_index, []),
            )
            for column_index in range(column_count)
        ]
        row_sizes.append(_json_size(value={
            "row_index": row_index,
            "cells": cells,
        }))
    rows_size = _array_size(item_sizes=row_sizes)
    table_id = "table_{:06d}".format(builder.order + 1)
    table_size = _mapping_size(value_sizes={
        "caption": _json_size(value=caption),
        "caption_raw_text": _json_size(value=caption_raw_text),
        "column_count": _json_size(value=column_count),
        "grid_sha256": _json_size(value=GRID_HASH_PLACEHOLDER),
        "order": _json_size(value=builder.order),
        "row_count": _json_size(value=row_count),
        "rows": rows_size,
        "table_id": _json_size(value=table_id),
    })
    return {
        "order": builder.order,
        "table_id_candidate": table_id,
        "nesting_depth": nesting_depth,
        "rows": row_count,
        "columns": column_count,
        "source_cells": builder.raw_cell_count,
        "rectangular_cells": rectangular_cells,
        "origin_cells": origin_cell_count,
        "synthetic_blanks": synthetic_blanks,
        "span_duplicate_coordinates": span_duplicate_count,
        "raw_text_chars": raw_text_chars,
        "normalized_text_chars": normalized_text_chars,
        "expanded_raw_text_chars": expanded_raw_text_chars,
        "expanded_normalized_text_chars": expanded_normalized_text_chars,
        "estimated_canonical_json_bytes": table_size,
    }


def _full_grid_size_estimate(
    *, tables: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Estimate table-set and DerivedAsset bytes from exact per-table sizes."""
    table_set_size = _array_size(item_sizes=[
        int(table["estimated_canonical_json_bytes"]) for table in tables
    ])
    # canonical_json_bytes adds one LF at the outer boundary.
    table_set_canonical = table_set_size + 1
    storage_uri = (
        "artifacts/vnext/table_qualification_freeze/"
        "financial_statement:financial_assets_under_management_table_v1.json"
    )
    derived_size = _mapping_size(value_sizes={
        "content_type": _json_size(
            value="application/vnd.secmetrics.table-grid+json"
        ),
        "derived_asset_id": _json_size(
            value=DERIVED_ASSET_HASH_PLACEHOLDER
        ),
        "parent_raw_asset_ids": _json_size(
            value=["sha256:" + SOURCE_SHA256]
        ),
        "record_type": _json_size(value="DERIVED_ASSET"),
        "storage_uri": _json_size(value=storage_uri),
        "tables": table_set_size,
        "transform_id": _json_size(value="html_to_table_grid"),
        "transform_semantic_version": _json_size(value="1"),
    }) + 1
    return {
        "expanded_table_set_canonical_json_bytes_estimate": (
            table_set_canonical
        ),
        "full_derived_asset_canonical_json_bytes_estimate": derived_size,
        "method": (
            "Exact canonical scalar/container sizing with one-row-at-a-time "
            "cell construction; content hashes use equal-length placeholders."
        ),
        "complete_expanded_object_materialized": False,
    }


def _memory_interval(
    *, canonical_bytes: int, expanded_cells: int, table_count: int,
    row_count: int,
) -> Dict[str, object]:
    """Return a transparent deterministic CPython materialization interval."""
    fixed_containers = table_count * 2048 + row_count * 256
    lower = canonical_bytes + expanded_cells * 256 + fixed_containers
    upper = canonical_bytes + expanded_cells * 1024 + fixed_containers
    return {
        "estimated_lower_bytes": lower,
        "estimated_upper_bytes": upper,
        "formula": (
            "canonical_derived_asset_bytes + expanded_cells*(256..1024) + "
            "table_count*2048 + expanded_row_count*256"
        ),
        "scope": "64-bit CPython dict/list materialization planning interval",
        "allocator_fragmentation_included": False,
    }


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Bind protected active/root bytes before and after the census."""
    paths = (
        Path("outputs/active_publication.json"),
        Path("outputs/metrics_matrix.csv"),
        Path("outputs/metric_evidence.csv"),
        Path("REPORT_十公司财务指标.md"),
    )
    return {
        path.as_posix(): {
            "sha256": sha256_file(path=repo_root / path),
            "size": (repo_root / path).stat().st_size,
        }
        for path in paths
    }


def build_financial_grid_census_receipt(
    *, repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Build a deterministic complete JPM census and neutral option matrix."""
    before_root = _root_state(repo_root=repo_root)
    source_path = repo_root / SOURCE_RELATIVE
    if source_path.is_symlink() or not source_path.is_file():
        raise FinancialGridCensusError("JPM source is absent or unsafe")
    html_bytes = source_path.read_bytes()
    if sha256_bytes(content=html_bytes) != SOURCE_SHA256:
        raise FinancialGridCensusError("JPM source hash differs")
    try:
        text = html_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FinancialGridCensusError("JPM source is not UTF-8") from error
    parser = _AllTablesParser()
    parser.feed(text)
    parser.close()
    nesting = _NestingCounter()
    nesting.feed(text)
    nesting.close()
    if len(parser.tables) != len(nesting.depth_by_order):
        raise FinancialGridCensusError(
            "Nesting and parser table counts differ")
    tables = [
        _table_census(
            builder=builder,
            nesting_depth=nesting.depth_by_order[builder.order],
        )
        for builder in parser.tables
    ]
    table_count = len(tables)
    source_cells = sum(int(table["source_cells"]) for table in tables)
    rectangular_cells = sum(
        int(table["rectangular_cells"]) for table in tables
    )
    origin_cells = sum(int(table["origin_cells"]) for table in tables)
    synthetic_blanks = sum(
        int(table["synthetic_blanks"]) for table in tables
    )
    span_duplicates = sum(
        int(table["span_duplicate_coordinates"]) for table in tables
    )
    if origin_cells != source_cells:
        raise FinancialGridCensusError("Origin/source cell counts differ")
    if rectangular_cells != origin_cells + span_duplicates + synthetic_blanks:
        raise FinancialGridCensusError(
            "Expanded coordinate accounting differs")
    cumulative = 0
    trigger = None
    for table in tables:
        previous = cumulative
        cumulative += int(table["rectangular_cells"])
        if trigger is None and cumulative > PRODUCTION_GATE:
            trigger = {
                "production_max_total_cells": PRODUCTION_GATE,
                "order": table["order"],
                "table_id_candidate": table["table_id_candidate"],
                "previous_cumulative_rectangular_cells": previous,
                "trigger_table_rectangular_cells": table[
                    "rectangular_cells"
                ],
                "attempted_cumulative_rectangular_cells": cumulative,
                "production_error": (
                    "Table-grid resource budget exceeded: total expanded cells"
                ),
            }
    if trigger is None:
        raise FinancialGridCensusError("JPM does not trigger the current gate")
    top_50 = sorted(
        tables,
        key=lambda table: (
            -int(table["rectangular_cells"]), int(table["order"])
        ),
    )[:50]
    size_estimate = _full_grid_size_estimate(tables=tables)
    expanded_rows = sum(int(table["rows"]) for table in tables)
    memory = _memory_interval(
        canonical_bytes=int(
            size_estimate["full_derived_asset_canonical_json_bytes_estimate"]
        ),
        expanded_cells=rectangular_cells,
        table_count=table_count,
        row_count=expanded_rows,
    )
    minimum_safe = rectangular_cells
    option_matrix = [
        {
            "option_id": "OPTION-A",
            "title": "Raise max_total_cells",
            "implementation_selected": False,
            "minimum_safe_value_for_this_exact_source": minimum_safe,
            "margin_1_5x": (minimum_safe * 3 + 1) // 2,
            "margin_2x": minimum_safe * 2,
            "estimated_memory_interval": memory,
            "estimated_time": {
                "complexity": "O(html_bytes + source_cells + expanded_cells)",
                "exact_expanded_coordinate_visits": rectangular_cells,
                "wall_time_seconds": "NOT_ESTIMATED_NO_SAFE_FULL_BENCHMARK",
            },
            "other_resource_guardrails_retained": {
                key: value
                for key, value in RESOURCE_LIMITS.__dict__.items()
                if key != "max_total_cells"
            },
            "risks": [
                (
                    "larger worst-case allocation in the current "
                    "all-at-once model"
                ),
                "memory estimate is planning evidence, not measured peak RSS",
                "future sources may exceed this exact-source minimum",
            ],
        },
        {
            "option_id": "OPTION-B",
            "title": "Per-table immutable shard plus ordered manifest",
            "implementation_selected": False,
            "required_hash_and_replay_contracts": [
                (
                    "each table shard binds table_id/order/grid_sha256/"
                    "source hash"
                ),
                "ordered manifest binds exact complete table ID/hash sequence",
                "replay rejects missing/extra/reordered/tampered shards",
                (
                    "Evidence locator resolves through manifest without "
                    "table search"
                ),
            ],
            "application_cache_required": False,
            "minimum_change_surface": {
                "files": [
                    "scripts/vnext/table_grid.py",
                    "scripts/vnext/records.py",
                    "scripts/vnext/reader_input.py",
                    "scripts/vnext/table_payload.py",
                    "scripts/vnext/evidence.py",
                    "scripts/vnext/replay.py",
                    "scripts/vnext/table_qualification_freeze.py",
                ],
                "records_or_schemas": [
                    "per-table immutable shard",
                    "ordered complete-table manifest",
                    "shard-aware DerivedAsset/Reader/Evidence bindings",
                ],
            },
            "estimated_engineering_complexity": "HIGH_MULTI_BOUNDARY_CHANGE",
            "risks": [
                (
                    "new integrity and recovery states across "
                    "Reader/Evidence/replay"
                ),
                "qualification invalidation for every dependent table family",
                (
                    "incorrect lazy boundary could become an unauthorized "
                    "selector"
                ),
            ],
        },
        {
            "option_id": "OPTION-C",
            "title": "Use a smaller development source",
            "implementation_selected": False,
            "qualification_fixture_only": True,
            "solves_jpm_final_production_processing": False,
            "must_not_claim_product_problem_solved": True,
            "risks": [
                (
                    "qualification may no longer exercise the "
                    "production-scale case"
                ),
                (
                    "JPM still fails the unchanged production "
                    "max_total_cells gate"
                ),
            ],
        },
    ]
    after_root = _root_state(repo_root=repo_root)
    body = {
        "schema_version": 1,
        "record_type": "TABLE_STAGE_B_FINANCIAL_GRID_CENSUS_RECEIPT",
        "status": "DECISION_NEUTRAL_OFFLINE_EVIDENCE",
        "source": {
            "source_repo_relative_path": SOURCE_RELATIVE.as_posix(),
            "source_sha256": SOURCE_SHA256,
            "exact_html_bytes": len(html_bytes),
        },
        "authority": {
            "research_tool_sha256": sha256_file(
                path=repo_root / TOOL_RELATIVE
            ),
            "production_table_grid_sha256": sha256_file(
                path=repo_root / TABLE_GRID_RELATIVE
            ),
            "production_resource_limits_sha256": sha256_file(
                path=repo_root / RESOURCE_LIMITS_RELATIVE
            ),
            "production_max_total_cells": RESOURCE_LIMITS.max_total_cells,
            "production_limits_changed": False,
            "production_parser_semantics_changed": False,
        },
        "census": {
            "exact_table_count": table_count,
            "exact_source_cell_count": source_cells,
            "exact_total_rectangular_expanded_cell_count": rectangular_cells,
            "origin_cell_count": origin_cells,
            "rowspan_colspan_duplicate_coordinate_count": span_duplicates,
            "synthetic_blank_count": synthetic_blanks,
            "synthetic_blank_ratio": _ratio(
                numerator=synthetic_blanks,
                denominator=rectangular_cells,
            ),
            "span_duplicate_ratio": _ratio(
                numerator=span_duplicates,
                denominator=rectangular_cells,
            ),
            "nested_table_count": nesting.nested_table_count,
            "maximum_nesting_depth": nesting.maximum_depth,
            "expanded_row_count": expanded_rows,
            **size_estimate,
            "estimated_python_dict_list_memory_interval": memory,
        },
        "tables": tables,
        "top_50_largest_tables": top_50,
        "production_gate_trigger": trigger,
        "full_materialization_benchmark": {
            "outcome": "NOT_RUN_RESOURCE_SAFETY",
            "peak_rss_bytes": "NOT_RUN",
            "wall_time_seconds": "NOT_RUN",
            "reason": (
                "This PR does not authorize raising production limits or "
                "constructing the complete giant expanded dict/list object."
            ),
        },
        "decision_neutral_option_matrix": option_matrix,
        "selected_option": None,
        "forbidden_actions_performed": {
            "tables_deleted": False,
            "keyword_table_filter": False,
            "semantic_selector": False,
            "max_total_cells_modified": False,
            "resource_limits_modified": False,
            "sharding_or_lazy_implementation": False,
            "qualification_source_replaced": False,
        },
        "root_business_artifacts_before": before_root,
        "root_business_artifacts_after": after_root,
        "root_business_artifacts_byte_equal": before_root == after_root,
        "egress_counts": {
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_sec_egress_count": 0,
        },
    }
    if body["authority"]["production_max_total_cells"] != PRODUCTION_GATE:
        raise FinancialGridCensusError("Production max_total_cells changed")
    if not body["root_business_artifacts_byte_equal"]:
        raise FinancialGridCensusError(
            "Financial census changed root artifacts")
    receipt_id = content_hash(value=body)
    return {"receipt_id": receipt_id, **body}


def write_financial_grid_census_receipt(
    *, repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Write the deterministic financial census under its content ID."""
    receipt = build_financial_grid_census_receipt(repo_root=repo_root)
    digest = str(receipt["receipt_id"]).split(":", maxsplit=1)[1]
    relative = OUTPUT_ROOT / (digest + ".json")
    atomic_write_json(path=repo_root / relative, value=receipt)
    return {**receipt, "receipt_path": relative.as_posix()}


def main(*, argv: Sequence[str]) -> int:
    """Run the safe offline census and print its exact decision inputs."""
    parser = argparse.ArgumentParser()
    parser.parse_args(list(argv))
    try:
        receipt = write_financial_grid_census_receipt(repo_root=REPO_ROOT)
    except (FinancialGridCensusError, OSError, ValueError) as error:
        print(json.dumps({
            "status": "FAILED",
            "error_code": type(error).__name__,
            "message": str(error),
        }, ensure_ascii=False, sort_keys=True))
        return 2
    census = receipt["census"]
    print(json.dumps({
        "status": receipt["status"],
        "receipt_id": receipt["receipt_id"],
        "receipt_path": receipt["receipt_path"],
        "exact_total_rectangular_expanded_cell_count": census[
            "exact_total_rectangular_expanded_cell_count"
        ],
        "synthetic_blank_ratio": census["synthetic_blank_ratio"],
        "span_duplicate_ratio": census["span_duplicate_ratio"],
        "full_materialization_benchmark": receipt[
            "full_materialization_benchmark"
        ],
        "egress_counts": receipt["egress_counts"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
