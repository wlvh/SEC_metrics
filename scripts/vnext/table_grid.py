"""Transform every HTML table into a metric-neutral content-addressed grid."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .canonical import content_hash
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS


TABLE_GRID_CONTENT_TYPE = "application/vnd.secmetrics.table-grid+json"
TABLE_GRID_TRANSFORM = "html_to_table_grid"
TABLE_GRID_VERSION = "1"


class TableGridError(ValueError):
    """Report malformed HTML table structure or an invalid grid locator."""


def _resource_error(*, resource: str) -> TableGridError:
    """Build one stable fail-closed resource-budget diagnostic.

    Args:
        resource: Human-readable budget dimension.

    Returns:
        TableGridError ready to raise at the pre-allocation boundary.
    """
    return TableGridError(
        "Table-grid resource budget exceeded: {}".format(resource)
    )


@dataclass
class _RawCell:
    """Accumulate one source cell before merged-cell expansion."""

    header: bool
    rowspan: int
    colspan: int
    raw_parts: List[str] = field(default_factory=list)
    raw_char_count: int = 0


@dataclass
class _TableBuilder:
    """Accumulate one table in source document order."""

    order: int
    rows: List[List[_RawCell]] = field(default_factory=list)
    current_row: Optional[List[_RawCell]] = None
    current_row_column_count: int = 0
    current_cell: Optional[_RawCell] = None
    caption_parts: List[str] = field(default_factory=list)
    in_caption: bool = False
    text_char_count: int = 0
    raw_cell_count: int = 0


def _positive_span(*, attributes: Mapping[str, str], key: str) -> int:
    """Parse a positive rowspan/colspan value or use one.

    Args:
        attributes: Lowercase HTML attributes.
        key: ``rowspan`` or ``colspan``.

    Returns:
        Positive span.

    Raises:
        TableGridError: On zero, negative, or non-integer spans.
    """
    if key not in attributes or attributes[key] == "":
        return 1
    if len(attributes[key]) > RESOURCE_LIMITS.max_span_attribute_chars:
        raise _resource_error(resource="{}".format(key))
    try:
        value = int(attributes[key])
    except ValueError as error:
        raise TableGridError("Invalid {} value".format(key)) from error
    if value < 1:
        raise TableGridError("{} must be positive".format(key))
    maximum = (
        RESOURCE_LIMITS.max_rows_per_table
        if key == "rowspan"
        else RESOURCE_LIMITS.max_columns_per_table
    )
    if value > maximum:
        raise _resource_error(resource="{}".format(key))
    return value


class _AllTablesParser(HTMLParser):
    """Capture all tables without applying metric or keyword filtering."""

    def __init__(self) -> None:
        """Initialize a parser that preserves entity spelling in raw text."""
        super().__init__(convert_charrefs=False)
        self._stack: List[_TableBuilder] = []
        self._total_raw_cell_count = 0
        self._total_text_char_count = 0
        self.tables: List[_TableBuilder] = []

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        """Open table structure while ignoring non-structural tags.

        Args:
            tag: Lowercase HTML tag.
            attrs: Source attributes.
        """
        attributes = {
            key.lower(): value if value is not None else ""
            for key, value in attrs
        }
        if tag == "table":
            if len(self.tables) >= RESOURCE_LIMITS.max_tables:
                raise _resource_error(resource="table count")
            builder = _TableBuilder(order=len(self.tables))
            self.tables.append(builder)
            self._stack.append(builder)
            return
        if not self._stack:
            return
        current = self._stack[-1]
        if tag == "caption":
            current.in_caption = True
        elif tag == "tr":
            if current.current_row is not None:
                self._finish_row(builder=current)
            current.current_row = []
            current.current_row_column_count = 0
        elif tag in {"td", "th"}:
            if current.current_row is None:
                current.current_row = []
            if current.current_cell is not None:
                self._finish_cell(builder=current)
            if current.raw_cell_count >= RESOURCE_LIMITS.max_cells_per_table:
                raise _resource_error(resource="source cells")
            if self._total_raw_cell_count >= RESOURCE_LIMITS.max_total_cells:
                raise _resource_error(resource="total source cells")
            rowspan = _positive_span(
                attributes=attributes, key="rowspan",
            )
            colspan = _positive_span(
                attributes=attributes, key="colspan",
            )
            if (
                current.current_row_column_count + colspan
                > RESOURCE_LIMITS.max_columns_per_table
            ):
                raise _resource_error(resource="source row columns")
            current.current_cell = _RawCell(
                header=tag == "th",
                rowspan=rowspan,
                colspan=colspan,
            )
            current.current_row_column_count += colspan
            current.raw_cell_count += 1
            self._total_raw_cell_count += 1
        elif tag in {"br", "p", "div", "li"}:
            self._append_raw(text="\n")

    def handle_endtag(self, tag: str) -> None:
        """Close table structure and tolerate ordinary filing HTML omissions.

        Args:
            tag: Lowercase closing tag.
        """
        if not self._stack:
            return
        current = self._stack[-1]
        if tag in {"td", "th"}:
            self._finish_cell(builder=current)
        elif tag == "tr":
            self._finish_row(builder=current)
        elif tag == "caption":
            current.in_caption = False
        elif tag == "table":
            self._finish_cell(builder=current)
            self._finish_row(builder=current)
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        """Preserve source text in every enclosing table cell/caption.

        Args:
            data: Decoded HTML data token.
        """
        self._append_raw(text=data)

    def handle_entityref(self, name: str) -> None:
        """Preserve named entity spelling before semantic text decoding.

        Args:
            name: Entity name without delimiters.
        """
        if (
            any(
                builder.current_cell is not None or builder.in_caption
                for builder in self._stack
            )
            and len(name) > RESOURCE_LIMITS.max_entity_reference_chars
        ):
            raise _resource_error(resource="entity reference")
        self._append_raw(text="&{};".format(name))

    def handle_charref(self, name: str) -> None:
        """Preserve numeric entity spelling before semantic text decoding.

        Args:
            name: Numeric reference without delimiters.
        """
        if (
            any(
                builder.current_cell is not None or builder.in_caption
                for builder in self._stack
            )
            and len(name) > RESOURCE_LIMITS.max_entity_reference_chars
        ):
            raise _resource_error(resource="entity reference")
        self._append_raw(text="&#{};".format(name))

    def close(self) -> None:
        """Finalize unclosed filing tables after the parser consumes input."""
        super().close()
        while self._stack:
            current = self._stack[-1]
            self._finish_cell(builder=current)
            self._finish_row(builder=current)
            self._stack.pop()

    def _append_raw(self, *, text: str) -> None:
        """Append text to every enclosing cell and active caption.

        Args:
            text: Source token.

        Why:
            Nested tables remain separately addressable while the parent cell
            still reflects the text a human sees in that cell.
        """
        updates = []
        total_increment = 0
        for builder in self._stack:
            cell_increment = (
                len(text) if builder.current_cell is not None else 0
            )
            caption_increment = len(text) if builder.in_caption else 0
            if (
                builder.current_cell is not None
                and builder.current_cell.raw_char_count + cell_increment
                > RESOURCE_LIMITS.max_cell_text_chars
            ):
                raise _resource_error(resource="cell text")
            if (
                builder.text_char_count
                + cell_increment
                + caption_increment
                > RESOURCE_LIMITS.max_table_text_chars
            ):
                raise _resource_error(resource="table text")
            updates.append(
                (builder, cell_increment, caption_increment,)
            )
            total_increment += cell_increment + caption_increment
        if (
            self._total_text_char_count + total_increment
            > RESOURCE_LIMITS.max_total_table_text_chars
        ):
            raise _resource_error(resource="total table text")

        # Preflight every enclosing table first so nested input never leaves a
        # partially mutated parser state when one outer budget is exceeded.
        for builder, cell_increment, caption_increment in updates:
            if builder.current_cell is not None and cell_increment:
                builder.current_cell.raw_parts.append(text)
                builder.current_cell.raw_char_count += cell_increment
            if builder.in_caption and caption_increment:
                builder.caption_parts.append(text)
            builder.text_char_count += cell_increment + caption_increment
        self._total_text_char_count += total_increment

    @staticmethod
    def _finish_cell(*, builder: _TableBuilder) -> None:
        """Append the active cell once and clear its mutable slot.

        Args:
            builder: Table being parsed.
        """
        if builder.current_cell is None:
            return
        if builder.current_row is None:
            builder.current_row = []
        builder.current_row.append(builder.current_cell)
        builder.current_cell = None

    @classmethod
    def _finish_row(cls, *, builder: _TableBuilder) -> None:
        """Append the active row, including a deliberately empty row.

        Args:
            builder: Table being parsed.
        """
        cls._finish_cell(builder=builder)
        if builder.current_row is None:
            return
        if len(builder.rows) >= RESOURCE_LIMITS.max_rows_per_table:
            raise _resource_error(resource="row count")
        builder.rows.append(builder.current_row)
        builder.current_row = None
        builder.current_row_column_count = 0


def _semantic_text(*, raw_text: str) -> str:
    """Decode HTML entities and normalize layout whitespace for model input.

    Args:
        raw_text: Parser-preserved cell text.

    Returns:
        Visible semantic text. The separate ``raw_text`` field remains in the
        grid and is never represented as the original filing bytes.
    """
    decoded = html.unescape(raw_text)
    return re.sub(pattern=r"\s+", repl=" ", string=decoded).strip()


def _expanded_table(
    *,
    builder: _TableBuilder,
    remaining_total_cells: int,
    remaining_expanded_text_chars: int,
) -> Tuple[Dict[str, object], int]:
    """Expand rowspan/colspan into a deterministic rectangular grid.

    Args:
        builder: Raw table builder.
        remaining_total_cells: Filing-wide cells still available before this
            table is materialized.
        remaining_expanded_text_chars: Filing-wide raw-plus-semantic expanded
            text still available.

    Returns:
        One table payload with stable coordinate locators and its expanded
        text-character charge.

    Raises:
        TableGridError: When merged spans overlap inconsistently.
    """
    occupied: Dict[Tuple[int, int], Dict[str, object]] = {}
    maximum_column = -1
    maximum_row = len(builder.rows) - 1
    expanded_text_chars = 0
    for row_index, row in enumerate(builder.rows):
        column_index = 0
        for cell in row:
            while (row_index, column_index) in occupied:
                column_index += 1
                if column_index >= RESOURCE_LIMITS.max_columns_per_table:
                    raise _resource_error(resource="column count")
            row_end = row_index + cell.rowspan
            column_end = column_index + cell.colspan
            if row_end > RESOURCE_LIMITS.max_rows_per_table:
                raise _resource_error(resource="row count")
            if column_end > RESOURCE_LIMITS.max_columns_per_table:
                raise _resource_error(resource="column count")
            span_cells = cell.rowspan * cell.colspan
            if (
                span_cells > RESOURCE_LIMITS.max_cells_per_table
                or len(occupied) + span_cells
                > RESOURCE_LIMITS.max_cells_per_table
            ):
                raise _resource_error(resource="expanded cells")
            raw_text = "".join(cell.raw_parts)
            semantic_text = _semantic_text(raw_text=raw_text)
            expanded_text_chars += span_cells * (
                len(raw_text) + len(semantic_text)
            )
            if expanded_text_chars > remaining_expanded_text_chars:
                raise _resource_error(resource="expanded text")
            origin = {
                "origin_row_index": row_index,
                "origin_column_index": column_index,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "header": cell.header,
                "raw_text": raw_text,
                "text": semantic_text,
            }
            for row_offset in range(cell.rowspan):
                for column_offset in range(cell.colspan):
                    coordinate = (
                        row_index + row_offset,
                        column_index + column_offset,
                    )
                    if coordinate in occupied:
                        raise TableGridError("Overlapping merged table cells")
                    occupied[coordinate] = origin
                    maximum_row = max(maximum_row, coordinate[0])
                    maximum_column = max(maximum_column, coordinate[1])
            column_index += cell.colspan
    rectangular_cells = (
        (maximum_row + 1) * (maximum_column + 1)
        if maximum_row >= 0 and maximum_column >= 0
        else 0
    )
    if rectangular_cells > RESOURCE_LIMITS.max_cells_per_table:
        raise _resource_error(resource="expanded cells")
    if rectangular_cells > remaining_total_cells:
        raise _resource_error(resource="total expanded cells")
    caption_raw_text = "".join(builder.caption_parts)
    caption = _semantic_text(raw_text=caption_raw_text)
    expanded_text_chars += len(caption_raw_text) + len(caption)
    if expanded_text_chars > remaining_expanded_text_chars:
        raise _resource_error(resource="expanded text")
    rows: List[Dict[str, object]] = []
    for row_index in range(maximum_row + 1):
        cells: List[Dict[str, object]] = []
        for column_index in range(maximum_column + 1):
            coordinate = (row_index, column_index)
            if coordinate not in occupied:
                cell_payload = {
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
            else:
                source = occupied[coordinate]
                cell_payload = dict(source)
                cell_payload["row_index"] = row_index
                cell_payload["column_index"] = column_index
                cell_payload["is_origin"] = all(
                    (
                        source["origin_row_index"] == row_index,
                        source["origin_column_index"] == column_index,
                    )
                )
            cells.append(cell_payload)
        rows.append({"row_index": row_index, "cells": cells})
    table = {
        "table_id": "table_{:06d}".format(builder.order + 1),
        "order": builder.order,
        "caption_raw_text": caption_raw_text,
        "caption": caption,
        "row_count": len(rows),
        "column_count": maximum_column + 1 if maximum_column >= 0 else 0,
        "rows": rows,
    }
    table["grid_sha256"] = content_hash(value=table)
    return table, expanded_text_chars


def build_table_grid(
    *,
    html_bytes: bytes,
    parent_raw_asset_ids: Sequence[str],
    storage_uri: str,
) -> Dict[str, object]:
    """Build a DerivedAsset containing every source table in document order.

    Args:
        html_bytes: Exact filing bytes, decoded strictly as UTF-8 for this PoC
            transform.
        parent_raw_asset_ids: Parent RawBlob identities.
        storage_uri: Planned content-addressed derived-asset location.

    Returns:
        Strict ``DERIVED_ASSET`` record. No metric terms or filter parameters
        are accepted by this API.

    Raises:
        TableGridError: On invalid UTF-8 or duplicate/missing parent identity.
    """
    if (
        not parent_raw_asset_ids
        or any(
            not isinstance(item, str) or not item
            for item in parent_raw_asset_ids
        )
        or len(parent_raw_asset_ids) != len(set(parent_raw_asset_ids))
    ):
        raise TableGridError(
            "Parent RawBlob identities must be non-empty and unique"
        )
    if not storage_uri:
        raise TableGridError("DerivedAsset storage_uri is required")
    if not isinstance(html_bytes, bytes):
        raise TableGridError("HTML table transform requires bytes")
    if len(html_bytes) > RESOURCE_LIMITS.max_html_bytes:
        raise _resource_error(resource="HTML bytes")
    try:
        text = html_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TableGridError(
            "HTML table transform requires UTF-8 bytes"
        ) from error
    parser = _AllTablesParser()
    parser.feed(text)
    parser.close()
    tables = []
    remaining_total_cells = RESOURCE_LIMITS.max_total_cells
    remaining_expanded_text_chars = RESOURCE_LIMITS.max_expanded_text_chars
    for builder in parser.tables:
        table, expanded_text_chars = _expanded_table(
            builder=builder,
            remaining_total_cells=remaining_total_cells,
            remaining_expanded_text_chars=remaining_expanded_text_chars,
        )
        remaining_total_cells -= (
            int(table["row_count"]) * int(table["column_count"])
        )
        remaining_expanded_text_chars -= expanded_text_chars
        tables.append(table)
    identity = {
        "parent_raw_asset_ids": list(parent_raw_asset_ids),
        "transform_id": TABLE_GRID_TRANSFORM,
        "transform_semantic_version": TABLE_GRID_VERSION,
        "content_type": TABLE_GRID_CONTENT_TYPE,
        "tables": tables,
    }
    record = {
        "record_type": "DERIVED_ASSET",
        "derived_asset_id": content_hash(value=identity),
        "parent_raw_asset_ids": list(parent_raw_asset_ids),
        "transform_id": TABLE_GRID_TRANSFORM,
        "transform_semantic_version": TABLE_GRID_VERSION,
        "content_type": TABLE_GRID_CONTENT_TYPE,
        "storage_uri": storage_uri,
        "tables": tables,
    }
    return validate_record(record=record)


def resolve_cell(
    *, derived_asset: Mapping[str, object], locator: Mapping[str, object]
) -> Dict[str, object]:
    """Resolve only the exact table/row/column locator supplied by a Reader.

    Args:
        derived_asset: Valid table-grid DerivedAsset.
        locator: Exact ``derived_asset_id``, ``table_id``, ``row_index``, and
            ``column_index`` mapping.

    Returns:
        Addressed grid cell.

    Raises:
        TableGridError: On unknown fields, wrong asset, missing table, or an
            out-of-range coordinate. The function never searches elsewhere.
    """
    validate_record(record=derived_asset)
    required = {
        "derived_asset_id",
        "table_id",
        "row_index",
        "column_index",
        "origin_row_index",
        "origin_column_index",
        "rowspan",
        "colspan",
    }
    if set(locator) != required:
        raise TableGridError("Cell locator fields are not exact")
    if locator["derived_asset_id"] != derived_asset["derived_asset_id"]:
        raise TableGridError("Cell locator names a different derived asset")
    matches = [
        table
        for table in derived_asset["tables"]
        if table["table_id"] == locator["table_id"]
    ]
    if len(matches) != 1:
        raise TableGridError("Cell locator table is missing or ambiguous")
    table = matches[0]
    row_index = locator["row_index"]
    column_index = locator["column_index"]
    if any(
        type(locator[field]) is not int
        for field in (
            "row_index",
            "column_index",
            "origin_row_index",
            "origin_column_index",
            "rowspan",
            "colspan",
        )
    ):
        raise TableGridError("Cell coordinates/spans must be integers")
    if row_index < 0 or row_index >= table["row_count"]:
        raise TableGridError("Cell row is out of range")
    if column_index < 0 or column_index >= table["column_count"]:
        raise TableGridError("Cell column is out of range")
    cell = dict(table["rows"][row_index]["cells"][column_index])
    for locator_field in (
        "origin_row_index",
        "origin_column_index",
        "rowspan",
        "colspan",
    ):
        if locator[locator_field] != cell[locator_field]:
            raise TableGridError("Cell locator span/origin differs")
    return cell
