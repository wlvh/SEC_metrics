"""Encode every expanded table-grid into a reversible compact transport form.

The module is called by ``reader_input`` to construct the model payload and by
``evidence`` / ``ai_adapter`` to independently recover the local expanded
Evidence Authority.  ``table_grid`` remains the only source of table meaning;
this module only removes representation redundancy that the decoder restores
without searching filing text.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence, Tuple

from .canonical import canonical_json_bytes, content_hash, sha256_bytes
from .records import validate_record


TABLE_PAYLOAD_SERIALIZATION_VERSION = "2"
DECODER_SEMANTIC_VERSION = "1"
_TRANSPORT_FIELDS = {
    "compact_payload_sha256",
    "decoder_semantic_version",
    "expanded_derived_asset_id",
    "expanded_grid_sha256",
    "round_trip_receipt_id",
    "table_payload_serialization_version",
    "tables",
}
_TRANSPORT_CORE_FIELDS = _TRANSPORT_FIELDS - {
    "compact_payload_sha256",
    "round_trip_receipt_id",
}
_COMPACT_TABLE_FIELDS = {"c", "i", "o", "s", "x"}
_TABLE_FIELDS = {
    "caption",
    "caption_raw_text",
    "column_count",
    "grid_sha256",
    "order",
    "row_count",
    "rows",
    "table_id",
}


class TablePayloadError(ValueError):
    """Report a non-reversible or substituted compact table transport."""


def expanded_grid_sha256(*, tables: Sequence[Mapping[str, object]]) -> str:
    """Return the canonical identity of a complete expanded table set.

    Args:
        tables: Expanded tables in document order, including every cell.

    Returns:
        Content-addressed identity used to bind compact transport to local
        Evidence Authority.
    """
    return content_hash(value=[dict(table) for table in tables])


def _require_exact_mapping(
    *, value: object, fields: set, label: str,
) -> Dict[str, object]:
    """Return a copy only when one compact object has an exact field set.

    Args:
        value: Untrusted compact object.
        fields: Required field names.
        label: Stable diagnostic label.

    Returns:
        Isolated compact object.

    Raises:
        TablePayloadError: If a field is missing, added, or malformed.
    """
    if type(value) is not dict or set(value) != fields:
        raise TablePayloadError("{} fields are not exact".format(label))
    return dict(value)


def _validate_expanded_table(*, table: Mapping[str, object]) -> Dict[str, object]:
    """Validate one local expanded table before redundancy is removed.

    Args:
        table: One expanded table from a strict DerivedAsset.

    Returns:
        Isolated table dictionary.

    Raises:
        TablePayloadError: If the table no longer has table-grid shape.
    """
    value = _require_exact_mapping(
        value=table, fields=_TABLE_FIELDS, label="expanded table",
    )
    if (
        type(value["table_id"]) is not str
        or not value["table_id"]
        or type(value["order"]) is not int
        or value["order"] < 0
        or type(value["caption"]) is not str
        or type(value["caption_raw_text"]) is not str
        or type(value["row_count"]) is not int
        or type(value["column_count"]) is not int
        or value["row_count"] < 0
        or value["column_count"] < 0
        or type(value["rows"]) is not list
        or type(value["grid_sha256"]) is not str
        or not value["grid_sha256"]
    ):
        raise TablePayloadError("Expanded table scalar fields are invalid")
    if len(value["rows"]) != value["row_count"]:
        raise TablePayloadError("Expanded table row count differs")
    expected_table = {
        key: value[key] for key in value if key != "grid_sha256"
    }
    if value["grid_sha256"] != content_hash(value=expected_table):
        raise TablePayloadError("Expanded table digest differs")
    for row_index, row in enumerate(value["rows"]):
        if (
            type(row) is not dict
            or set(row) != {"cells", "row_index"}
            or row["row_index"] != row_index
            or type(row["cells"]) is not list
            or len(row["cells"]) != value["column_count"]
        ):
            raise TablePayloadError("Expanded table rows are invalid")
        for column_index, cell in enumerate(row["cells"]):
            required_cell = {
                "column_index",
                "colspan",
                "header",
                "is_origin",
                "origin_column_index",
                "origin_row_index",
                "raw_text",
                "row_index",
                "rowspan",
                "text",
            }
            if type(cell) is not dict or set(cell) != required_cell:
                raise TablePayloadError("Expanded table cells are invalid")
            if (
                cell["row_index"] != row_index
                or cell["column_index"] != column_index
                or type(cell["origin_row_index"]) is not int
                or type(cell["origin_column_index"]) is not int
                or type(cell["rowspan"]) is not int
                or type(cell["colspan"]) is not int
                or cell["rowspan"] < 1
                or cell["colspan"] < 1
                or type(cell["header"]) is not bool
                or type(cell["is_origin"]) is not bool
                or type(cell["raw_text"]) is not str
                or type(cell["text"]) is not str
            ):
                raise TablePayloadError("Expanded table cell fields are invalid")
    return value


def _compact_origin_cells(*, table: Mapping[str, object]) -> List[List[object]]:
    """Encode only origin cells because spans restore every expansion copy.

    Args:
        table: Validated expanded table.

    Returns:
        Ordered positional records for true source-origin cells only.
    """
    origins: List[List[object]] = []
    for row in table["rows"]:
        for cell in row["cells"]:
            if cell["is_origin"] is not True:
                continue
            if (
                cell["origin_row_index"] != cell["row_index"]
                or cell["origin_column_index"] != cell["column_index"]
            ):
                raise TablePayloadError("Origin cell coordinates differ")
            # Positional fields reduce duplicate JSON keys while retaining all
            # source-origin facts required to rebuild every expanded cell.
            origins.append(
                [
                    cell["row_index"],
                    cell["column_index"],
                    cell["rowspan"],
                    cell["colspan"],
                    cell["header"],
                    cell["raw_text"],
                    cell["text"],
                ]
            )
    return origins


def _compact_table(*, table: Mapping[str, object]) -> Dict[str, object]:
    """Encode one entire table without selecting cells or semantic slices.

    Args:
        table: Expanded table in document order.

    Returns:
        Compact table object containing caption, rectangle shape, and origins.
    """
    expanded = _validate_expanded_table(table=table)
    return {
        "i": expanded["table_id"],
        "o": expanded["order"],
        "c": [expanded["caption"], expanded["caption_raw_text"]],
        "s": [expanded["row_count"], expanded["column_count"]],
        "x": _compact_origin_cells(table=expanded),
    }


def _transport_core(*, transport: Mapping[str, object]) -> Dict[str, object]:
    """Extract the hash-preimage fields from one compact transport object.

    Args:
        transport: Full compact transport including digest bindings.

    Returns:
        Exact core object whose canonical bytes are digest-bound.
    """
    return {field: transport[field] for field in sorted(_TRANSPORT_CORE_FIELDS)}


def _round_trip_receipt_body(*, transport: Mapping[str, object]) -> Dict[str, object]:
    """Build the complete deterministic round-trip receipt preimage.

    Args:
        transport: Validated compact transport.

    Returns:
        Fields that identify the encoder/decoder pair and full table identity.
    """
    return {
        "table_payload_serialization_version": transport[
            "table_payload_serialization_version"
        ],
        "expanded_derived_asset_id": transport["expanded_derived_asset_id"],
        "expanded_grid_sha256": transport["expanded_grid_sha256"],
        "compact_payload_sha256": transport["compact_payload_sha256"],
        "decoder_semantic_version": transport["decoder_semantic_version"],
        "round_trip_status": "PASSED",
    }


def compact_payload_receipt(*, transport: Mapping[str, object]) -> Dict[str, object]:
    """Return the content-addressed receipt for a verified compact transport.

    Args:
        transport: Compact transport accepted by the strict decoder.

    Returns:
        Receipt carrying every required compact/expanded identity binding.
    """
    decode_compact_table_payload(transport=transport)
    body = _round_trip_receipt_body(transport=transport)
    return {"round_trip_receipt_id": content_hash(value=body), **body}


def encode_compact_table_payload(
    *, derived_asset: Mapping[str, object],
) -> Dict[str, object]:
    """Encode every table in an expanded DerivedAsset into compact transport.

    Args:
        derived_asset: Local Evidence Authority containing every expanded table.

    Returns:
        Versioned compact transport with independent expanded/compact/dedoder
        identities and a deterministic round-trip receipt ID.

    Raises:
        TablePayloadError: If the source is not an exact table-grid asset.
    """
    try:
        asset = validate_record(record=dict(derived_asset))
    except ValueError as error:
        raise TablePayloadError("Expanded DerivedAsset is invalid") from error
    if asset["record_type"] != "DERIVED_ASSET":
        raise TablePayloadError("Compact transport requires a DerivedAsset")
    tables = asset["tables"]
    if type(tables) is not list:
        raise TablePayloadError("Expanded table set is invalid")
    compact_tables = [_compact_table(table=table) for table in tables]
    if [table["o"] for table in compact_tables] != list(range(len(tables))):
        raise TablePayloadError("Expanded table order is not contiguous")
    core = {
        "table_payload_serialization_version": (
            TABLE_PAYLOAD_SERIALIZATION_VERSION
        ),
        "expanded_derived_asset_id": asset["derived_asset_id"],
        "expanded_grid_sha256": expanded_grid_sha256(tables=tables),
        "decoder_semantic_version": DECODER_SEMANTIC_VERSION,
        "tables": compact_tables,
    }
    compact_sha256 = sha256_bytes(content=canonical_json_bytes(value=core))
    provisional = {**core, "compact_payload_sha256": compact_sha256}
    receipt_body = _round_trip_receipt_body(transport=provisional)
    transport = {
        **provisional,
        "round_trip_receipt_id": content_hash(value=receipt_body),
    }
    decoded = decode_compact_table_payload(transport=transport)
    if decoded != tables:
        raise TablePayloadError("Compact table round trip differs")
    return transport


def _decode_compact_table(*, compact: object) -> Dict[str, object]:
    """Rebuild one exact expanded table from shape plus source origins.

    Args:
        compact: Untrusted compact table mapping.

    Returns:
        Full expanded table with every synthetic blank and span duplicate.
    """
    table = _require_exact_mapping(
        value=compact, fields=_COMPACT_TABLE_FIELDS, label="compact table",
    )
    table_id = table["i"]
    order = table["o"]
    caption = table["c"]
    shape = table["s"]
    origins = table["x"]
    if (
        type(table_id) is not str
        or not table_id
        or type(order) is not int
        or order < 0
        or type(caption) is not list
        or len(caption) != 2
        or any(type(value) is not str for value in caption)
        or type(shape) is not list
        or len(shape) != 2
        or any(type(value) is not int or value < 0 for value in shape)
        or type(origins) is not list
    ):
        raise TablePayloadError("Compact table scalar fields are invalid")
    row_count, column_count = shape
    occupied: Dict[Tuple[int, int], Dict[str, object]] = {}
    for origin in origins:
        if (
            type(origin) is not list
            or len(origin) != 7
            or type(origin[0]) is not int
            or type(origin[1]) is not int
            or type(origin[2]) is not int
            or type(origin[3]) is not int
            or type(origin[4]) is not bool
            or type(origin[5]) is not str
            or type(origin[6]) is not str
        ):
            raise TablePayloadError("Compact origin cell is invalid")
        row_index, column_index, rowspan, colspan = origin[:4]
        if (
            row_index < 0
            or column_index < 0
            or rowspan < 1
            or colspan < 1
            or row_index + rowspan > row_count
            or column_index + colspan > column_count
        ):
            raise TablePayloadError("Compact origin cell exceeds table shape")
        source = {
            "origin_row_index": row_index,
            "origin_column_index": column_index,
            "rowspan": rowspan,
            "colspan": colspan,
            "header": origin[4],
            "raw_text": origin[5],
            "text": origin[6],
        }
        for row_offset in range(rowspan):
            for column_offset in range(colspan):
                coordinate = (row_index + row_offset, column_index + column_offset)
                if coordinate in occupied:
                    raise TablePayloadError("Compact origin spans overlap")
                occupied[coordinate] = source
    rows = []
    for row_index in range(row_count):
        cells = []
        for column_index in range(column_count):
            coordinate = (row_index, column_index)
            source = occupied[coordinate] if coordinate in occupied else None
            if source is None:
                # Only absent rectangle coordinates are synthetic blanks. This
                # avoids storing cells which shape reconstructs losslessly.
                cell = {
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
                cell = dict(source)
                cell["row_index"] = row_index
                cell["column_index"] = column_index
                cell["is_origin"] = (
                    source["origin_row_index"] == row_index
                    and source["origin_column_index"] == column_index
                )
            cells.append(cell)
        rows.append({"row_index": row_index, "cells": cells})
    expanded = {
        "table_id": table_id,
        "order": order,
        "caption_raw_text": caption[1],
        "caption": caption[0],
        "row_count": row_count,
        "column_count": column_count,
        "rows": rows,
    }
    expanded["grid_sha256"] = content_hash(value=expanded)
    return expanded


def decode_compact_table_payload(
    *, transport: Mapping[str, object],
) -> List[Dict[str, object]]:
    """Decode and authenticate a compact payload back to expanded tables.

    Args:
        transport: Versioned compact model transport representation.

    Returns:
        Complete expanded table set in original document order.

    Raises:
        TablePayloadError: If versions, hashes, receipt, shape, or the
        decoded expanded grid differ from their bound identity.
    """
    value = _require_exact_mapping(
        value=transport, fields=_TRANSPORT_FIELDS, label="compact transport",
    )
    if (
        value["table_payload_serialization_version"]
        != TABLE_PAYLOAD_SERIALIZATION_VERSION
        or value["decoder_semantic_version"] != DECODER_SEMANTIC_VERSION
        or type(value["expanded_derived_asset_id"]) is not str
        or not value["expanded_derived_asset_id"]
        or type(value["expanded_grid_sha256"]) is not str
        or not value["expanded_grid_sha256"]
        or type(value["compact_payload_sha256"]) is not str
        or not value["compact_payload_sha256"]
        or type(value["round_trip_receipt_id"]) is not str
        or not value["round_trip_receipt_id"]
        or type(value["tables"]) is not list
    ):
        raise TablePayloadError("Compact transport identity fields are invalid")
    if sha256_bytes(content=canonical_json_bytes(value=_transport_core(
        transport=value,
    ))) != value["compact_payload_sha256"]:
        raise TablePayloadError("Compact payload digest differs")
    receipt_body = _round_trip_receipt_body(transport=value)
    if content_hash(value=receipt_body) != value["round_trip_receipt_id"]:
        raise TablePayloadError("Compact round-trip receipt differs")
    tables = [_decode_compact_table(compact=table) for table in value["tables"]]
    if [table["order"] for table in tables] != list(range(len(tables))):
        raise TablePayloadError("Compact table order is not contiguous")
    if len({table["table_id"] for table in tables}) != len(tables):
        raise TablePayloadError("Compact table identities are duplicated")
    if expanded_grid_sha256(tables=tables) != value["expanded_grid_sha256"]:
        raise TablePayloadError("Decoded expanded grid digest differs")
    return tables
