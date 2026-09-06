"""Centralize fail-closed resource budgets for untrusted vNext filing data.

``table_grid`` applies the parsing and expansion limits before allocation;
``render`` applies the review-output limits before returning bytes. Callers
cannot override these production budgets through public workflow parameters.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    """Declare deterministic parser, grid, and renderer resource ceilings.

    Attributes:
        max_html_bytes: Maximum exact filing payload accepted by the table
            transform.
        max_tables: Maximum number of source tables in one filing.
        max_rows_per_table: Maximum raw or span-expanded rows in one table.
        max_columns_per_table: Maximum span-expanded columns in one table.
        max_span_attribute_chars: Maximum source characters parsed as one
            rowspan or colspan integer.
        max_entity_reference_chars: Maximum source characters decoded as one
            named or numeric HTML entity reference.
        max_cells_per_table: Maximum source or rectangular expanded cells in
            one table.
        max_total_cells: Maximum source or expanded cells across the complete
            filing.
        max_cell_text_chars: Maximum decoded source characters accumulated in
            one cell.
        max_table_text_chars: Maximum decoded source characters accumulated
            across one table, including deliberate nested-table duplication.
        max_total_table_text_chars: Maximum decoded characters accumulated
            across every enclosing table before expansion.
        max_expanded_text_chars: Maximum raw-plus-semantic characters after
            applying each cell span across the complete filing grid.
        max_rendered_review_bytes: Maximum complete rendered review size.
        max_rendered_line_bytes: Maximum physical UTF-8 line size for a table
            cell in the rendered review.
    """

    max_html_bytes: int
    max_tables: int
    max_rows_per_table: int
    max_columns_per_table: int
    max_span_attribute_chars: int
    max_entity_reference_chars: int
    max_cells_per_table: int
    max_total_cells: int
    max_cell_text_chars: int
    max_table_text_chars: int
    max_total_table_text_chars: int
    max_expanded_text_chars: int
    max_rendered_review_bytes: int
    max_rendered_line_bytes: int


# These ceilings retain complete in-budget content while bounding the largest
# materialized grid to a predictable audit-workstation resource envelope.
RESOURCE_LIMITS = ResourceLimits(
    max_html_bytes=64 * 1024 * 1024,
    max_tables=2048,
    max_rows_per_table=4096,
    max_columns_per_table=256,
    max_span_attribute_chars=32,
    max_entity_reference_chars=64,
    max_cells_per_table=25000,
    max_total_cells=210000,
    max_cell_text_chars=1024 * 1024,
    max_table_text_chars=16 * 1024 * 1024,
    max_total_table_text_chars=32 * 1024 * 1024,
    max_expanded_text_chars=64 * 1024 * 1024,
    max_rendered_review_bytes=64 * 1024 * 1024,
    max_rendered_line_bytes=8192,
)
