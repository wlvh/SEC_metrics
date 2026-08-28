"""Encode every expanded table-grid into a reversible compact transport form.

The module is called by ``reader_input`` to construct the model payload and by
``evidence`` / ``ai_adapter`` to independently recover the local expanded
Evidence Authority.  ``table_grid`` remains the only source of table meaning;
this module only removes representation redundancy that the decoder restores
without searching filing text.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Mapping, Sequence, Tuple

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
_TABLE_SHARD_FIELDS = {
    "decoder_semantic_version",
    "end_table_order",
    "expanded_derived_asset_id",
    "expanded_grid_sha256",
    "parent_compact_payload_sha256",
    "shard_count",
    "shard_id",
    "shard_index",
    "shard_payload_sha256",
    "start_table_order",
    "table_ids",
    "table_payload_serialization_version",
    "tables",
}
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
    return _compact_payload_receipt_from_validated_transport(
        transport=transport,
    )


def _compact_payload_receipt_from_validated_transport(
    *, transport: Mapping[str, object],
) -> Dict[str, object]:
    """Return receipt fields after one caller-owned strict round trip."""
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


def _table_shard_core(*, shard: Mapping[str, object]) -> Dict[str, object]:
    """Return the exact hash preimage for one internal contiguous shard."""
    return {
        key: shard[key]
        for key in sorted(_TABLE_SHARD_FIELDS - {"shard_id", "shard_payload_sha256"})
    }


def _build_contiguous_table_shard_from_validated_parent(
    *, parent_transport: Mapping[str, object],
    parent_tables: Sequence[Mapping[str, object]], shard_index: int,
    shard_count: int, start_table_order: int, end_table_order: int,
) -> Dict[str, object]:
    """Slice entries after the caller has authenticated the full parent once."""
    tables = parent_transport["tables"]
    if (
        type(shard_index) is not int
        or type(shard_count) is not int
        or type(start_table_order) is not int
        or type(end_table_order) is not int
        or shard_count < 1
        or shard_index < 0
        or shard_index >= shard_count
        or start_table_order < 0
        or end_table_order < start_table_order
        or end_table_order >= len(tables)
    ):
        raise TablePayloadError("Compact table shard range is invalid")
    selected = [
        dict(table)
        for table in tables[start_table_order:end_table_order + 1]
    ]
    expected_orders = list(range(start_table_order, end_table_order + 1))
    if [table["o"] for table in selected] != expected_orders:
        raise TablePayloadError("Compact table shard order differs")
    body = {
        "table_payload_serialization_version": parent_transport[
            "table_payload_serialization_version"
        ],
        "decoder_semantic_version": parent_transport[
            "decoder_semantic_version"
        ],
        "expanded_derived_asset_id": parent_transport[
            "expanded_derived_asset_id"
        ],
        "expanded_grid_sha256": parent_transport["expanded_grid_sha256"],
        "parent_compact_payload_sha256": parent_transport[
            "compact_payload_sha256"
        ],
        "shard_index": shard_index,
        "shard_count": shard_count,
        "start_table_order": start_table_order,
        "end_table_order": end_table_order,
        "table_ids": [str(table["i"]) for table in selected],
        "tables": selected,
    }
    payload_sha256 = sha256_bytes(content=canonical_json_bytes(value=body))
    provisional = {**body, "shard_payload_sha256": payload_sha256}
    shard = {
        **provisional,
        "shard_id": content_hash(value=provisional),
    }
    return shard


def build_contiguous_table_shard(
    *, parent_transport: Mapping[str, object], shard_index: int,
    shard_count: int, start_table_order: int, end_table_order: int,
) -> Dict[str, object]:
    """Slice serializer-v2 table entries without changing any table bytes."""
    parent_tables = decode_compact_table_payload(transport=parent_transport)
    shard = _build_contiguous_table_shard_from_validated_parent(
        parent_transport=parent_transport,
        parent_tables=parent_tables,
        shard_index=shard_index,
        shard_count=shard_count,
        start_table_order=start_table_order,
        end_table_order=end_table_order,
    )
    _decode_contiguous_table_shard_from_validated_parent(
        shard=shard,
        parent_transport=parent_transport,
        parent_tables=parent_tables,
    )
    return shard


def _decode_contiguous_table_shard_from_validated_parent(
    *, shard: Mapping[str, object], parent_transport: Mapping[str, object],
    parent_tables: Sequence[Mapping[str, object]],
) -> List[Dict[str, object]]:
    """Authenticate one shard while reusing an already verified parent."""
    value = _require_exact_mapping(
        value=shard, fields=_TABLE_SHARD_FIELDS,
        label="compact table shard",
    )
    if (
        value["table_payload_serialization_version"]
        != parent_transport["table_payload_serialization_version"]
        or value["decoder_semantic_version"]
        != parent_transport["decoder_semantic_version"]
        or value["expanded_derived_asset_id"]
        != parent_transport["expanded_derived_asset_id"]
        or value["expanded_grid_sha256"]
        != parent_transport["expanded_grid_sha256"]
        or value["parent_compact_payload_sha256"]
        != parent_transport["compact_payload_sha256"]
    ):
        raise TablePayloadError("Compact table shard parent binding differs")
    for key in (
        "shard_index", "shard_count", "start_table_order", "end_table_order",
    ):
        if type(value[key]) is not int:
            raise TablePayloadError("Compact table shard index is invalid")
    start = value["start_table_order"]
    end = value["end_table_order"]
    if (
        value["shard_count"] < 1
        or value["shard_index"] < 0
        or value["shard_index"] >= value["shard_count"]
        or start < 0
        or end < start
        or end >= len(parent_tables)
        or type(value["tables"]) is not list
        or type(value["table_ids"]) is not list
    ):
        raise TablePayloadError("Compact table shard range is invalid")
    expected_compact = parent_transport["tables"][start:end + 1]
    if value["tables"] != expected_compact:
        raise TablePayloadError("Compact table shard entries differ")
    if value["table_ids"] != [str(table["i"]) for table in expected_compact]:
        raise TablePayloadError("Compact table shard identities differ")
    core = _table_shard_core(shard=value)
    if (
        value["shard_payload_sha256"]
        != sha256_bytes(content=canonical_json_bytes(value=core))
        or value["shard_id"]
        != content_hash(value={**core, "shard_payload_sha256": value[
            "shard_payload_sha256"
        ]})
    ):
        raise TablePayloadError("Compact table shard digest differs")
    decoded = [_decode_compact_table(compact=table) for table in value["tables"]]
    if decoded != parent_tables[start:end + 1]:
        raise TablePayloadError("Compact table shard round trip differs")
    return decoded


def decode_contiguous_table_shard(
    *, shard: Mapping[str, object], parent_transport: Mapping[str, object],
) -> List[Dict[str, object]]:
    """Authenticate one shard against its complete serializer-v2 parent."""
    parent_tables = decode_compact_table_payload(transport=parent_transport)
    return _decode_contiguous_table_shard_from_validated_parent(
        shard=shard,
        parent_transport=parent_transport,
        parent_tables=parent_tables,
    )


def validate_contiguous_table_shard_set(
    *, shards: Sequence[Mapping[str, object]],
    parent_transport: Mapping[str, object],
) -> Dict[str, object]:
    """Prove all parent tables occur once across contiguous ordered shards."""
    parent_tables = decode_compact_table_payload(transport=parent_transport)
    return _validate_contiguous_table_shard_set_from_validated_parent(
        shards=shards,
        parent_transport=parent_transport,
        parent_tables=parent_tables,
    )


def _validate_contiguous_table_shard_set_from_validated_parent(
    *, shards: Sequence[Mapping[str, object]],
    parent_transport: Mapping[str, object],
    parent_tables: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Prove full shard coverage after one caller-owned parent validation."""
    if not shards:
        raise TablePayloadError("Compact table shard set is empty")
    expected_count = len(shards)
    next_order = 0
    shard_ids = []
    covered_ids = []
    for shard_index, shard in enumerate(shards):
        value = dict(shard)
        _decode_contiguous_table_shard_from_validated_parent(
            shard=value,
            parent_transport=parent_transport,
            parent_tables=parent_tables,
        )
        if (
            value["shard_index"] != shard_index
            or value["shard_count"] != expected_count
            or value["start_table_order"] != next_order
        ):
            raise TablePayloadError("Compact table shard set order differs")
        next_order = int(value["end_table_order"]) + 1
        shard_ids.append(str(value["shard_id"]))
        covered_ids.extend(str(table_id) for table_id in value["table_ids"])
    parent_ids = [str(table["table_id"]) for table in parent_tables]
    if next_order != len(parent_tables) or covered_ids != parent_ids:
        raise TablePayloadError("Compact table shard coverage differs")
    body = {
        "parent_compact_payload_sha256": parent_transport[
            "compact_payload_sha256"
        ],
        "expanded_derived_asset_id": parent_transport[
            "expanded_derived_asset_id"
        ],
        "expanded_grid_sha256": parent_transport["expanded_grid_sha256"],
        "table_count": len(parent_tables),
        "shard_count": expected_count,
        "shard_ids": shard_ids,
        "covered_table_ids": covered_ids,
    }
    return {**body, "shard_set_id": content_hash(value=body)}


def plan_contiguous_table_shards(
    *, parent_transport: Mapping[str, object],
    max_estimated_input_tokens: int,
    estimate_shard_input_tokens: Callable[[Mapping[str, object]], int],
) -> Dict[str, object]:
    """Greedily pack maximal contiguous ranges using only exact request size."""
    parent_tables = decode_compact_table_payload(transport=parent_transport)
    return _plan_contiguous_table_shards_from_validated_parent(
        parent_transport=parent_transport,
        parent_tables=parent_tables,
        max_estimated_input_tokens=max_estimated_input_tokens,
        estimate_shard_input_tokens=estimate_shard_input_tokens,
    )


def _plan_contiguous_table_shards_from_validated_parent(
    *, parent_transport: Mapping[str, object],
    parent_tables: Sequence[Mapping[str, object]],
    max_estimated_input_tokens: int,
    estimate_shard_input_tokens: Callable[[Mapping[str, object]], int],
) -> Dict[str, object]:
    """Plan shards after one caller-owned parent/grid round-trip proof."""
    if (
        type(max_estimated_input_tokens) is not int
        or max_estimated_input_tokens < 1
        or not callable(estimate_shard_input_tokens)
        or not parent_tables
    ):
        raise TablePayloadError("Compact table shard planner input is invalid")

    def boundaries(*, assumed_count: int) -> List[Tuple[int, int]]:
        ranges = []
        start = 0
        while start < len(parent_tables):
            low = start
            high = len(parent_tables) - 1
            accepted = None
            while low <= high:
                end = (low + high) // 2
                provisional = _build_contiguous_table_shard_from_validated_parent(
                    parent_transport=parent_transport,
                    parent_tables=parent_tables,
                    shard_index=len(ranges),
                    shard_count=max(assumed_count, len(ranges) + 1),
                    start_table_order=start,
                    end_table_order=end,
                )
                estimate = estimate_shard_input_tokens(provisional)
                if type(estimate) is not int or estimate < 0:
                    raise TablePayloadError(
                        "Compact table shard estimate is invalid"
                    )
                if estimate <= max_estimated_input_tokens:
                    accepted = end
                    low = end + 1
                else:
                    high = end - 1
            if accepted is None:
                raise TablePayloadError(
                    "One compact table exceeds the shard request ceiling"
                )
            ranges.append((start, accepted))
            start = accepted + 1
        return ranges

    assumed_count = 1
    ranges: List[Tuple[int, int]] = []
    for _iteration in range(8):
        ranges = boundaries(assumed_count=assumed_count)
        if len(ranges) == assumed_count:
            break
        assumed_count = len(ranges)
    else:
        raise TablePayloadError("Compact table shard count did not converge")
    planned = []
    for shard_index, (start, end) in enumerate(ranges):
        shard = _build_contiguous_table_shard_from_validated_parent(
            parent_transport=parent_transport,
            parent_tables=parent_tables,
            shard_index=shard_index,
            shard_count=len(ranges),
            start_table_order=start,
            end_table_order=end,
        )
        estimate = estimate_shard_input_tokens(shard)
        if type(estimate) is not int or estimate > max_estimated_input_tokens:
            raise TablePayloadError("Compact table shard exceeds request ceiling")
        if end + 1 < len(parent_tables):
            expanded = _build_contiguous_table_shard_from_validated_parent(
                parent_transport=parent_transport,
                parent_tables=parent_tables,
                shard_index=shard_index,
                shard_count=len(ranges),
                start_table_order=start,
                end_table_order=end + 1,
            )
            if estimate_shard_input_tokens(expanded) <= max_estimated_input_tokens:
                raise TablePayloadError("Compact table shard is not maximal")
        planned.append({
            "shard": shard,
            "estimated_input_tokens": estimate,
        })
    coverage = _validate_contiguous_table_shard_set_from_validated_parent(
        shards=[row["shard"] for row in planned],
        parent_transport=parent_transport,
        parent_tables=parent_tables,
    )
    body = {
        "packing_algorithm": (
            "GREEDY_MAXIMAL_CONTIGUOUS_PREFIX_BY_EXACT_PROVIDER_REQUEST_"
            "UTF8_BYTE_UPPER_BOUND_V1"
        ),
        "max_estimated_input_tokens": max_estimated_input_tokens,
        "coverage": coverage,
        "shards": planned,
    }
    return {**body, "shard_plan_id": content_hash(value=body)}
