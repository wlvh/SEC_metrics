#!/usr/bin/env python3
"""Build decision-neutral, offline evidence for lodging payload minimization.

The module is a research tool only.  It rebuilds the current production-v2
Reader/provider envelope from existing repository bytes, then evaluates four
reversible serialization candidates and one research-only merged-task
estimate.  No candidate is imported by Reader, Workflow, or the provider
adapter, and this tool has no network or credential path.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.ai_adapter import approved_transport_policy  # noqa: E402
from vnext.ai_adapter import build_provider_request_body  # noqa: E402
from vnext.canonical import atomic_write_json  # noqa: E402
from vnext.canonical import canonical_json_bytes, content_hash  # noqa: E402
from vnext.canonical import sha256_bytes, sha256_file  # noqa: E402
from vnext.canonical import strict_json_file  # noqa: E402
from vnext.reader_input import READER_SYSTEM_CONTRACT  # noqa: E402
from vnext.reader_input import build_reader_input_manifest  # noqa: E402
from vnext.reader_input import build_reader_payload  # noqa: E402
from vnext.requirements import load_requirement_snapshot  # noqa: E402
from vnext.table_grid import _semantic_text, build_table_grid  # noqa: E402
from vnext.table_payload import decode_compact_table_payload  # noqa: E402
from vnext.table_payload import expanded_grid_sha256  # noqa: E402
from vnext.table_task_contracts import (  # noqa: E402
    RUNTIME_TASK_CONTRACT_FIELDS,
)
from vnext.table_task_contracts import (  # noqa: E402
    resolve_table_task_contract,
)


OUTPUT_ROOT = (
    Path("artifacts/vnext/table_stage_b_investigation/context_minimization")
)
MATRIX_PATH = Path("config/table_qualification_matrix.json")
CATALOG_PATH = Path("catalog/table_task_contracts.json")
PROVIDER_RUNTIME_PATH = Path("config/provider_model_runtime.json")
PRODUCTION_SERIALIZER_PATH = Path("scripts/vnext/table_payload.py")
RESEARCH_TOOL_PATH = Path("tools/investigate_table_context_minimization.py")
TASK_IDS = (
    "lodging_occupancy_table_v2",
    "lodging_revpar_table_v2",
)
THRESHOLD = 200000
TEXT_TRANSFORM_VERSION = "table_grid_semantic_text_v1"
CURRENT_SERIALIZER_SHA256 = (
    "7571bbf5121989effc4a3eb0ba38a42ef1dfc5ea9a839b65220bbbafb7aa2bb8"
)


class ContextInvestigationError(RuntimeError):
    """Report a non-reproducible or non-reversible research result."""


def _json_tokens(
    *, value: object, path: Tuple[object, ...] = (), newline: bool = True,
) -> List[Dict[str, object]]:
    """Return canonical JSON fragments with paths and structural labels."""
    tokens: List[Dict[str, object]] = []

    def append(
        *, token_path: Tuple[object, ...], kind: str, text: str,
    ) -> None:
        tokens.append({"path": token_path, "kind": kind, "text": text})

    def walk(*, item: object, item_path: Tuple[object, ...]) -> None:
        if type(item) is dict:
            append(token_path=item_path, kind="structural", text="{")
            for ordinal, key in enumerate(sorted(item)):
                if ordinal:
                    append(token_path=item_path, kind="structural", text=",")
                key_path = item_path + (key,)
                append(
                    token_path=key_path,
                    kind="key",
                    text=json.dumps(key, ensure_ascii=False),
                )
                append(token_path=key_path, kind="structural", text=":")
                walk(item=item[key], item_path=key_path)
            append(token_path=item_path, kind="structural", text="}")
            return
        if type(item) is list:
            append(token_path=item_path, kind="structural", text="[")
            for ordinal, child in enumerate(item):
                if ordinal:
                    append(token_path=item_path, kind="structural", text=",")
                walk(item=child, item_path=item_path + (ordinal,))
            append(token_path=item_path, kind="structural", text="]")
            return
        if type(item) is str:
            encoded = json.dumps(item, ensure_ascii=False)
            append(token_path=item_path, kind="structural", text='"')
            append(token_path=item_path, kind="scalar", text=encoded[1:-1])
            append(token_path=item_path, kind="structural", text='"')
            return
        if item is None or type(item) in {bool, int}:
            append(
                token_path=item_path,
                kind="scalar",
                text=json.dumps(item, ensure_ascii=False),
            )
            return
        raise ContextInvestigationError("Unsupported canonical JSON value")

    walk(item=value, item_path=path)
    if newline:
        append(token_path=path, kind="structural", text="\n")
    rendered = "".join(str(token["text"]) for token in tokens).encode("utf-8")
    if rendered != canonical_json_bytes(value=value):
        raise ContextInvestigationError(
            "Annotated JSON differs from canonical bytes")
    return tokens


def _escaped_fragment(*, text: str) -> str:
    """Escape a string fragment exactly as JSON without adding quotes."""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _provider_layer_decomposition(
    *, provider_envelope: bytes, reader_body: Mapping[str, object],
    output_schema_bytes: bytes,
) -> Dict[str, object]:
    """Partition every provider-envelope byte into stable layer categories."""
    envelope = json.loads(provider_envelope.decode("utf-8"))
    reader_text = canonical_json_bytes(value=dict(reader_body)).decode("utf-8")
    schema_text = output_schema_bytes.decode("utf-8")
    pieces: List[Tuple[str, str]] = []

    def emit(*, category: str, text: str) -> None:
        pieces.append((category, text))

    def generic_walk(*, item: object, path: Tuple[object, ...]) -> None:
        if path == ("messages", 0, "content"):
            if type(item) is not str or item.count(schema_text) != 1:
                raise ContextInvestigationError(
                    "Provider system output-schema embedding differs"
                )
            prefix, suffix = item.split(schema_text, maxsplit=1)
            emit(category="provider_envelope_other", text='"')
            emit(
                category="system_message_excluding_output_schema",
                text=_escaped_fragment(text=prefix),
            )
            emit(
                category="output_schema_embedded_in_system_message",
                text=_escaped_fragment(text=schema_text),
            )
            emit(
                category="system_message_excluding_output_schema",
                text=_escaped_fragment(text=suffix),
            )
            emit(category="provider_envelope_other", text='"')
            return
        if path == ("messages", 1, "content"):
            if item != reader_text:
                raise ContextInvestigationError("Provider Reader text differs")
            emit(category="provider_envelope_other", text='"')
            for token in _json_tokens(value=dict(reader_body)):
                token_path = tuple(token["path"])
                first = token_path[0] if token_path else None
                category = {
                    "system_contract": "reader_system_contract",
                    "task_contract": "task_contract",
                    "reader_input_manifest": "reader_input_manifest",
                    "untrusted_table_data": "compact_table_payload",
                }.get(first, "provider_envelope_other")
                emit(
                    category=category,
                    text=_escaped_fragment(text=str(token["text"])),
                )
            emit(category="provider_envelope_other", text='"')
            return
        if type(item) is dict:
            emit(category="provider_envelope_other", text="{")
            for ordinal, key in enumerate(sorted(item)):
                if ordinal:
                    emit(category="provider_envelope_other", text=",")
                emit(
                    category="provider_envelope_other",
                    text=json.dumps(key, ensure_ascii=False) + ":",
                )
                generic_walk(item=item[key], path=path + (key,))
            emit(category="provider_envelope_other", text="}")
            return
        if type(item) is list:
            emit(category="provider_envelope_other", text="[")
            for ordinal, child in enumerate(item):
                if ordinal:
                    emit(category="provider_envelope_other", text=",")
                generic_walk(item=child, path=path + (ordinal,))
            emit(category="provider_envelope_other", text="]")
            return
        emit(
            category="provider_envelope_other",
            text=json.dumps(item, ensure_ascii=False),
        )

    generic_walk(item=envelope, path=())
    emit(category="provider_envelope_other", text="\n")
    rendered = "".join(text for _category, text in pieces).encode("utf-8")
    if rendered != provider_envelope:
        raise ContextInvestigationError(
            "Provider layer attribution does not reproduce exact envelope"
        )
    counts: Counter[str] = Counter()
    for category, text in pieces:
        counts[category] += len(text.encode("utf-8"))
    return {
        "exact_provider_envelope_bytes": len(provider_envelope),
        "exact_provider_envelope_sha256": sha256_bytes(
            content=provider_envelope,
        ),
        "attributed_bytes": dict(sorted(counts.items())),
        "attributed_byte_sum": sum(counts.values()),
        "standalone_output_schema_bytes": len(output_schema_bytes),
        "standalone_output_schema_sha256": sha256_bytes(
            content=output_schema_bytes,
        ),
    }


def _compact_payload_decomposition(
    *, transport: Mapping[str, object],
) -> Dict[str, object]:
    """Partition exact compact-v2 JSON into requested table components."""
    counts: Counter[str] = Counter()
    for token in _json_tokens(value=dict(transport)):
        path = tuple(token["path"])
        kind = str(token["kind"])
        text_bytes = len(str(token["text"]).encode("utf-8"))
        if kind != "scalar":
            category = "json_keys_punctuation_structural_overhead"
        elif len(path) >= 3 and path[0] == "tables":
            table_field = path[2]
            if table_field == "i":
                category = "table_id"
            elif table_field == "o":
                category = "order"
            elif table_field == "c":
                category = "caption"
            elif table_field == "s":
                category = "shape"
            elif table_field == "x" and len(path) >= 5:
                position = path[4]
                category = {
                    0: "origin_coordinates",
                    1: "origin_coordinates",
                    2: "rowspan_colspan",
                    3: "rowspan_colspan",
                    4: "header_flags",
                    5: "raw_text",
                    6: "normalized_text",
                }.get(position, "transport_identity")
            else:
                category = "transport_identity"
        else:
            category = "transport_identity"
        counts[category] += text_bytes
    exact = canonical_json_bytes(value=dict(transport))
    if sum(counts.values()) != len(exact):
        raise ContextInvestigationError(
            "Compact decomposition byte sum differs")
    return {
        "exact_compact_transport_bytes": len(exact),
        "exact_compact_transport_sha256": sha256_bytes(content=exact),
        "component_bytes": dict(sorted(counts.items())),
        "component_byte_sum": sum(counts.values()),
    }


def _origin_rows(
    *, tables: Sequence[Mapping[str, object]],
) -> List[Dict[str, object]]:
    """Return every current-v2 origin cell in table/document order."""
    rows = []
    for table in tables:
        for row in table["rows"]:
            for cell in row["cells"]:
                if cell["is_origin"] is True:
                    rows.append({
                        "table_id": table["table_id"],
                        "order": table["order"],
                        "row_index": cell["row_index"],
                        "column_index": cell["column_index"],
                        "rowspan": cell["rowspan"],
                        "colspan": cell["colspan"],
                        "header": cell["header"],
                        "raw_text": cell["raw_text"],
                        "text": cell["text"],
                    })
    return rows


def _text_and_repetition_census(
    *, tables: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Count exact raw/normalized equality and repeated full-table strings."""
    origins = _origin_rows(tables=tables)
    raw_equal = [row for row in origins if row["raw_text"] == row["text"]]
    deterministic = [
        row for row in origins
        if _semantic_text(raw_text=str(row["raw_text"])) == row["text"]
    ]
    strings = []
    for table in tables:
        strings.extend([table["caption_raw_text"], table["caption"]])
    for row in origins:
        strings.extend([row["raw_text"], row["text"]])
    counts = Counter(str(value) for value in strings)
    repeated = []
    for value in sorted(
        (text for text, count in counts.items() if count > 1),
        key=lambda text: (text.encode("utf-8"), text),
    ):
        utf8_bytes = len(value.encode("utf-8"))
        repeated.append({
            "value": value,
            "value_sha256": sha256_bytes(content=value.encode("utf-8")),
            "utf8_bytes": utf8_bytes,
            "occurrences": counts[value],
            "potential_utf8_bytes_saved_before_reference_overhead": (
                (counts[value] - 1) * utf8_bytes
            ),
        })
    current_coordinates = []
    delta_coordinates = []
    previous = (0, 0)
    for row in origins:
        coordinate = (int(row["row_index"]), int(row["column_index"]))
        current_coordinates.append(list(coordinate))
        delta_coordinates.append([
            coordinate[0] - previous[0], coordinate[1] - previous[1],
        ])
        previous = coordinate
    current_coordinate_bytes = len(canonical_json_bytes(
        value=current_coordinates,
    ))
    delta_coordinate_bytes = len(canonical_json_bytes(
        value=delta_coordinates,
    ))
    return {
        "origin_cell_count": len(origins),
        "raw_text_equals_normalized_text_count": len(raw_equal),
        "raw_text_equals_normalized_text_utf8_bytes": sum(
            len(str(row["raw_text"]).encode("utf-8")) for row in raw_equal
        ),
        "raw_text_deterministically_generates_normalized_text_count": len(
            deterministic
        ),
        "raw_text_deterministically_generates_normalized_text_utf8_bytes": sum(
            len(str(row["text"]).encode("utf-8")) for row in deterministic
        ),
        "all_origin_raw_text_utf8_bytes": sum(
            len(str(row["raw_text"]).encode("utf-8")) for row in origins
        ),
        "all_origin_normalized_text_utf8_bytes": sum(
            len(str(row["text"]).encode("utf-8")) for row in origins
        ),
        "repeated_string_exact_set": repeated,
        "repeated_string_exact_set_hash": content_hash(value=repeated),
        "potential_repeated_utf8_bytes_saved_before_reference_overhead": sum(
            row["potential_utf8_bytes_saved_before_reference_overhead"]
            for row in repeated
        ),
        "consecutive_coordinate_count": len(origins),
        "current_coordinate_json_bytes": current_coordinate_bytes,
        "delta_coordinate_json_bytes": delta_coordinate_bytes,
        "potential_delta_coordinate_json_bytes_saved": (
            current_coordinate_bytes - delta_coordinate_bytes
        ),
    }


def _expanded_table_from_origins(
    *, table_id: str, order: int, caption: str, caption_raw_text: str,
    row_count: int, column_count: int,
    origins: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Rebuild one exact expanded table from research candidate origins."""
    occupied: Dict[Tuple[int, int], Dict[str, object]] = {}
    for origin in origins:
        row_index = int(origin["row_index"])
        column_index = int(origin["column_index"])
        rowspan = int(origin["rowspan"])
        colspan = int(origin["colspan"])
        source = {
            "origin_row_index": row_index,
            "origin_column_index": column_index,
            "rowspan": rowspan,
            "colspan": colspan,
            "header": origin["header"],
            "raw_text": origin["raw_text"],
            "text": origin["text"],
        }
        for row_offset in range(rowspan):
            for column_offset in range(colspan):
                coordinate = (
                    row_index + row_offset,
                    column_index + column_offset,
                )
                if coordinate in occupied:
                    raise ContextInvestigationError("Candidate spans overlap")
                occupied[coordinate] = source
    rows = []
    for row_index in range(row_count):
        cells = []
        for column_index in range(column_count):
            source = occupied.get((row_index, column_index))
            if source is None:
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
    table = {
        "table_id": table_id,
        "order": order,
        "caption_raw_text": caption_raw_text,
        "caption": caption,
        "row_count": row_count,
        "column_count": column_count,
        "rows": rows,
    }
    table["grid_sha256"] = content_hash(value=table)
    return table


def _candidate_common(
    *, candidate_id: str, asset: Mapping[str, object],
    tables: Sequence[Mapping[str, object]], extra: Mapping[str, object],
) -> Dict[str, object]:
    """Finalize a research candidate with fair compact/round-trip bindings."""
    core = {
        "research_candidate_id": candidate_id,
        "text_transform_version": TEXT_TRANSFORM_VERSION,
        "expanded_derived_asset_id": asset["derived_asset_id"],
        "expanded_grid_sha256": expanded_grid_sha256(tables=asset["tables"]),
        "tables": list(tables),
        **dict(extra),
    }
    payload_sha256 = sha256_bytes(content=canonical_json_bytes(value=core))
    round_trip_body = {
        "research_candidate_id": candidate_id,
        "expanded_derived_asset_id": asset["derived_asset_id"],
        "expanded_grid_sha256": core["expanded_grid_sha256"],
        "candidate_payload_sha256": payload_sha256,
        "round_trip_status": "PASSED",
    }
    return {
        **core,
        "candidate_payload_sha256": payload_sha256,
        "round_trip_receipt_id": content_hash(value=round_trip_body),
    }


def _candidate_one(*, asset: Mapping[str, object]) -> Dict[str, object]:
    """Encode raw text only; normalized text is restored by fixed transform."""
    tables = []
    for table in asset["tables"]:
        origins = _origin_rows(tables=[table])
        tables.append({
            "i": table["table_id"],
            "o": table["order"],
            "c": [table["caption_raw_text"]],
            "s": [table["row_count"], table["column_count"]],
            "x": [[
                row["row_index"], row["column_index"], row["rowspan"],
                row["colspan"], row["header"], row["raw_text"],
            ] for row in origins],
        })
    return _candidate_common(
        candidate_id="CANDIDATE-1",
        asset=asset,
        tables=tables,
        extra={"raw_text_only": True},
    )


def _candidate_two(*, asset: Mapping[str, object]) -> Dict[str, object]:
    """Encode normalized text plus a raw override only when it differs."""
    tables = []
    for table in asset["tables"]:
        caption = [table["caption"]]
        if table["caption_raw_text"] != table["caption"]:
            caption.append(table["caption_raw_text"])
        rows = []
        for origin in _origin_rows(tables=[table]):
            value = [
                origin["row_index"], origin["column_index"], origin["rowspan"],
                origin["colspan"], origin["header"], origin["text"],
            ]
            if origin["raw_text"] != origin["text"]:
                value.append(origin["raw_text"])
            rows.append(value)
        tables.append({
            "i": table["table_id"], "o": table["order"], "c": caption,
            "s": [table["row_count"], table["column_count"]], "x": rows,
        })
    return _candidate_common(
        candidate_id="CANDIDATE-2",
        asset=asset,
        tables=tables,
        extra={"raw_override_only_when_different": True},
    )


def _candidate_three(*, asset: Mapping[str, object]) -> Dict[str, object]:
    """Intern every caption/raw/normalized string and encode references."""
    strings = []
    for table in asset["tables"]:
        strings.extend([table["caption"], table["caption_raw_text"]])
        for origin in _origin_rows(tables=[table]):
            strings.extend([origin["raw_text"], origin["text"]])
    dictionary = sorted(set(strings), key=lambda text: (
        text.encode("utf-8"), text))
    reference = {text: index for index, text in enumerate(dictionary)}
    tables = []
    for table in asset["tables"]:
        tables.append({
            "i": table["table_id"],
            "o": table["order"],
            "c": [
                reference[table["caption"]],
                reference[table["caption_raw_text"]],
            ],
            "s": [table["row_count"], table["column_count"]],
            "x": [[
                row["row_index"], row["column_index"], row["rowspan"],
                row["colspan"], row["header"], reference[row["raw_text"]],
                reference[row["text"]],
            ] for row in _origin_rows(tables=[table])],
        })
    return _candidate_common(
        candidate_id="CANDIDATE-3",
        asset=asset,
        tables=tables,
        extra={"string_dictionary": dictionary},
    )


def _candidate_four(*, asset: Mapping[str, object]) -> Dict[str, object]:
    """Keep current text fields while delta-encoding origin coordinates."""
    tables = []
    for table in asset["tables"]:
        previous = (0, 0)
        rows = []
        for origin in _origin_rows(tables=[table]):
            coordinate = (origin["row_index"], origin["column_index"])
            rows.append([
                coordinate[0] - previous[0],
                coordinate[1] - previous[1],
                origin["rowspan"], origin["colspan"], origin["header"],
                origin["raw_text"], origin["text"],
            ])
            previous = coordinate
        tables.append({
            "i": table["table_id"], "o": table["order"],
            "c": [table["caption"], table["caption_raw_text"]],
            "s": [table["row_count"], table["column_count"]], "x": rows,
        })
    return _candidate_common(
        candidate_id="CANDIDATE-4",
        asset=asset,
        tables=tables,
        extra={"coordinate_encoding": "DELTA_FROM_PREVIOUS_ORIGIN"},
    )


def _decode_candidate(
    *, candidate: Mapping[str, object],
) -> List[Dict[str, object]]:
    """Decode and authenticate one research serialization candidate."""
    body = dict(candidate)
    payload_sha256 = str(body.pop("candidate_payload_sha256"))
    round_trip_id = str(body.pop("round_trip_receipt_id"))
    if (
        sha256_bytes(content=canonical_json_bytes(value=body))
        != payload_sha256
    ):
        raise ContextInvestigationError("Candidate payload hash differs")
    round_trip_body = {
        "research_candidate_id": body["research_candidate_id"],
        "expanded_derived_asset_id": body["expanded_derived_asset_id"],
        "expanded_grid_sha256": body["expanded_grid_sha256"],
        "candidate_payload_sha256": payload_sha256,
        "round_trip_status": "PASSED",
    }
    if content_hash(value=round_trip_body) != round_trip_id:
        raise ContextInvestigationError(
            "Candidate round-trip identity differs")
    candidate_id = str(body["research_candidate_id"])
    dictionary = body.get("string_dictionary")
    tables = []
    for encoded in body["tables"]:
        caption_value = encoded["c"]
        origins = []
        previous = (0, 0)
        for row in encoded["x"]:
            if candidate_id == "CANDIDATE-1":
                raw_text = row[5]
                text = _semantic_text(raw_text=raw_text)
                coordinate = (row[0], row[1])
            elif candidate_id == "CANDIDATE-2":
                text = row[5]
                raw_text = row[6] if len(row) == 7 else text
                coordinate = (row[0], row[1])
            elif candidate_id == "CANDIDATE-3":
                if type(dictionary) is not list:
                    raise ContextInvestigationError(
                        "String dictionary is absent")
                raw_text = dictionary[row[5]]
                text = dictionary[row[6]]
                coordinate = (row[0], row[1])
            elif candidate_id == "CANDIDATE-4":
                coordinate = (previous[0] + row[0], previous[1] + row[1])
                previous = coordinate
                raw_text = row[5]
                text = row[6]
            else:
                raise ContextInvestigationError("Unknown research candidate")
            origins.append({
                "row_index": coordinate[0],
                "column_index": coordinate[1],
                "rowspan": row[2],
                "colspan": row[3],
                "header": row[4],
                "raw_text": raw_text,
                "text": text,
            })
        if candidate_id == "CANDIDATE-1":
            caption_raw_text = caption_value[0]
            caption = _semantic_text(raw_text=caption_raw_text)
        elif candidate_id == "CANDIDATE-2":
            caption = caption_value[0]
            caption_raw_text = (
                caption_value[1] if len(caption_value) == 2 else caption
            )
        elif candidate_id == "CANDIDATE-3":
            caption = dictionary[caption_value[0]]
            caption_raw_text = dictionary[caption_value[1]]
        else:
            caption, caption_raw_text = caption_value
        tables.append(_expanded_table_from_origins(
            table_id=str(encoded["i"]),
            order=int(encoded["o"]),
            caption=str(caption),
            caption_raw_text=str(caption_raw_text),
            row_count=int(encoded["s"][0]),
            column_count=int(encoded["s"][1]),
            origins=origins,
        ))
    if expanded_grid_sha256(tables=tables) != body["expanded_grid_sha256"]:
        raise ContextInvestigationError("Candidate expanded grid hash differs")
    return tables


def _semantic_projection(*, tables: Sequence[Mapping[str, object]]) -> bytes:
    """Return ordered model-semantic text bytes independent of encoding."""
    return canonical_json_bytes(value=[
        {
            "caption": table["caption"],
            "rows": [[cell["text"] for cell in row["cells"]]
                     for row in table["rows"]],
        }
        for table in tables
    ])


def _source_set(*, repo_root: Path) -> List[Dict[str, object]]:
    """Return Marriott plus each distinct existing Hilton/Hyatt source hash."""
    matrix = strict_json_file(path=repo_root / MATRIX_PATH)
    lodging = next(
        row for row in matrix["families"]
        if row["family_id"] == "lodging_kpi_table"
    )
    development = dict(lodging["development_source"])
    sources = [{
        "source_id": "marriott-development",
        "source_kind": "DEVELOPMENT_IMMUTABLE_ATTEMPT",
        "source_repo_relative_path": development["source_repo_relative_path"],
        "source_sha256": development["source_sha256"],
        "fixture_ids": [],
        "co_table_response_path": (
            "fixtures/vnext/recorded/marriott_2025_reader_response.json"
        ),
    }]
    by_hash: Dict[str, List[Mapping[str, object]]] = {}
    layout_root = repo_root / "fixtures/vnext/layouts"
    for manifest_path in sorted(layout_root.glob("*/fixture_manifest.json")):
        manifest = strict_json_file(path=manifest_path)
        fixture_id = str(manifest["fixture_id"])
        if not (
            fixture_id.startswith("hilton-")
            or fixture_id.startswith("hyatt-")
        ):
            continue
        by_hash.setdefault(str(manifest["source_sha256"]), []).append({
            **manifest,
            "manifest_path": manifest_path.relative_to(repo_root).as_posix(),
        })
    for source_sha256 in sorted(by_hash):
        manifests = sorted(by_hash[source_sha256],
                           key=lambda row: row["fixture_id"])
        representative = manifests[0]
        source_path = Path(str(representative["source_repo_relative_path"]))
        # Prefer immutable attempts when fixture copies share the same hash.
        immutable_root = (
            repo_root / "evidence/request_attempts" / source_sha256[:2]
            / source_sha256
        )
        immutable = list(immutable_root.glob("*.htm"))
        if immutable:
            source_path = immutable[0].relative_to(repo_root)
        sources.append({
            "source_id": "{}-distinct-{}".format(
                "hilton"
                if str(representative["fixture_id"]).startswith("hilton-")
                else "hyatt",
                source_sha256[:12],
            ),
            "source_kind": "DISTINCT_EXISTING_LAYOUT_SOURCE_HASH",
            "source_repo_relative_path": source_path.as_posix(),
            "source_sha256": source_sha256,
            "fixture_ids": [row["fixture_id"] for row in manifests],
            "fixture_manifest_paths": [
                row["manifest_path"] for row in manifests
            ],
            "co_table_response_path": (
                Path("fixtures/vnext/layouts")
                / str(representative["fixture_id"])
                / "recorded_response.json"
            ).as_posix(),
        })
    if len(sources) != 4:
        raise ContextInvestigationError(
            "Expected Marriott plus three distinct Hilton/Hyatt sources"
        )
    for source in sources:
        path = repo_root / str(source["source_repo_relative_path"])
        if path.is_symlink() or not path.is_file():
            raise ContextInvestigationError(
                "Research source is absent or unsafe")
        if sha256_file(path=path) != source["source_sha256"]:
            raise ContextInvestigationError("Research source hash differs")
    return sources


def _co_table_evidence(
    *, repo_root: Path, sources: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    """Prove existing responses locate occupancy and RevPAR in one table."""
    rows = []
    for source in sources:
        relative = Path(str(source["co_table_response_path"]))
        response = strict_json_file(path=repo_root / relative)
        selected = {
            str(candidate["role"]): str(candidate["locator"]["table_id"])
            for candidate in response["candidates"]
            if candidate["role"] in {"occupancy", "revpar"}
        }
        if (
            set(selected) != {"occupancy", "revpar"}
            or len(set(selected.values())) != 1
            or next(iter(selected.values()))
            != response["table_locator"]["table_id"]
        ):
            raise ContextInvestigationError(
                "Existing roles are not stably co-table")
        rows.append({
            "source_id": source["source_id"],
            "response_path": relative.as_posix(),
            "response_sha256": sha256_file(path=repo_root / relative),
            "table_id": next(iter(selected.values())),
            "role_table_ids": dict(sorted(selected.items())),
        })
    return {
        "stable_co_table_for_all_sources": True,
        "source_evidence": rows,
        "source_evidence_hash": content_hash(value=rows),
    }


def _combined_task_contract(
    *, occupancy: Mapping[str, object], revpar: Mapping[str, object],
) -> Dict[str, object]:
    """Build a research-only two-role task without changing the catalog."""
    if (
        set(occupancy) != RUNTIME_TASK_CONTRACT_FIELDS
        or set(revpar) != RUNTIME_TASK_CONTRACT_FIELDS
        or occupancy["required_claims"] != revpar["required_claims"]
        or occupancy["scope_contract"] != revpar["scope_contract"]
        or occupancy["output_schema_hash"] != revpar["output_schema_hash"]
        or occupancy["system_prompt"] != revpar["system_prompt"]
    ):
        raise ContextInvestigationError(
            "Lodging tasks cannot be research-merged")
    combined = copy.deepcopy(dict(occupancy))
    combined.update({
        "task_contract_id": "research_lodging_occupancy_revpar_combined_v1",
        "metric_ids": (
            list(occupancy["metric_ids"]) + list(revpar["metric_ids"])
        ),
        "metric_spec_paths": (
            list(occupancy["metric_spec_paths"])
            + list(revpar["metric_spec_paths"])
        ),
        "metric_spec_semantic_hashes": (
            list(occupancy["metric_spec_semantic_hashes"])
            + list(revpar["metric_spec_semantic_hashes"])
        ),
        "metric_spec_closure_hashes": (
            list(occupancy["metric_spec_closure_hashes"])
            + list(revpar["metric_spec_closure_hashes"])
        ),
        "required_roles": ["occupancy", "revpar"],
        "identity_constraints": sorted(set(
            list(occupancy["identity_constraints"])
            + list(revpar["identity_constraints"])
        )),
        "forbidden_confusions": sorted(set(
            list(occupancy["forbidden_confusions"])
            + list(revpar["forbidden_confusions"])
        )),
    })
    semantic = {
        key: combined[key]
        for key in sorted(combined)
        if key not in {"catalog_task_contract_hash", "task_spec_semantic_hash"}
    }
    combined["task_spec_semantic_hash"] = content_hash(value={
        "research_combined_task": semantic,
    })
    combined["catalog_task_contract_hash"] = content_hash(value={
        key: combined[key]
        for key in sorted(combined)
        if key != "catalog_task_contract_hash"
    })
    if set(combined) != RUNTIME_TASK_CONTRACT_FIELDS:
        raise ContextInvestigationError("Combined task fields differ")
    return combined


def _root_state(*, repo_root: Path) -> Dict[str, object]:
    """Bind protected active/root bytes without modifying them."""
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


def _request_body(
    *, manifest: Mapping[str, object], task: Mapping[str, object],
    transport: Mapping[str, object],
) -> Dict[str, object]:
    """Build the same four-layer Reader body with a research transport."""
    return {
        "system_contract": dict(READER_SYSTEM_CONTRACT),
        "task_contract": dict(task),
        "reader_input_manifest": dict(manifest),
        "untrusted_table_data": dict(transport),
    }


def _result_row(
    *, source: Mapping[str, object], task_id: str,
    reader_body: Mapping[str, object], provider_envelope: bytes,
    transport: Mapping[str, object], expanded_equal: bool,
    semantic_equal: bool,
) -> Dict[str, object]:
    """Return one exact candidate/source/task envelope measurement."""
    reader_bytes = canonical_json_bytes(value=dict(reader_body))
    transport_bytes = canonical_json_bytes(value=dict(transport))
    return {
        "source_id": source["source_id"],
        "source_sha256": source["source_sha256"],
        "task_contract_id": task_id,
        "reader_request_bytes": len(reader_bytes),
        "reader_request_sha256": sha256_bytes(content=reader_bytes),
        "candidate_transport_bytes": len(transport_bytes),
        "candidate_transport_sha256": sha256_bytes(content=transport_bytes),
        "exact_provider_envelope_bytes": len(provider_envelope),
        "exact_provider_envelope_sha256": sha256_bytes(
            content=provider_envelope,
        ),
        "estimated_input_tokens": len(provider_envelope),
        "below_or_equal_200000": len(provider_envelope) <= THRESHOLD,
        "decode_candidate_field_equal_current_expanded_authority": (
            expanded_equal
        ),
        "machine_decoded_semantic_text_byte_equal": semantic_equal,
        "actual_prompt_tokens": "NOT_RUN",
    }


def build_context_minimization_receipt(
    *, repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Build the complete deterministic offline investigation receipt."""
    before_root = _root_state(repo_root=repo_root)
    requirement = load_requirement_snapshot(
        snapshot_dir=repo_root / "requirements/issue_15_v1",
    )
    policy = approved_transport_policy(requirement=requirement)
    sources = _source_set(repo_root=repo_root)
    tasks = {
        task_id: resolve_table_task_contract(
            repo_root=repo_root, task_contract_id=task_id,
        )
        for task_id in TASK_IDS
    }
    co_table = _co_table_evidence(repo_root=repo_root, sources=sources)
    combined_task = _combined_task_contract(
        occupancy=tasks[TASK_IDS[0]], revpar=tasks[TASK_IDS[1]],
    )
    baseline_rows = []
    decompositions = []
    candidate_rows: Dict[str, List[Dict[str, object]]] = {
        "CANDIDATE-1": [], "CANDIDATE-2": [],
        "CANDIDATE-3": [], "CANDIDATE-4": [], "CANDIDATE-5": [],
    }
    current_transport_by_source: Dict[str, Mapping[str, object]] = {}
    current_asset_by_source: Dict[str, Mapping[str, object]] = {}
    current_task_totals: Dict[str, List[int]] = {}
    for source in sources:
        source_path = repo_root / str(source["source_repo_relative_path"])
        html_bytes = source_path.read_bytes()
        source_baselines = []
        for task_id in TASK_IDS:
            storage_source_id = (
                "lodging_kpi_table:{}".format(task_id)
                if source["source_id"] == "marriott-development"
                else "{}:{}".format(source["source_id"], task_id)
            )
            asset = build_table_grid(
                html_bytes=html_bytes,
                parent_raw_asset_ids=["sha256:" +
                                      str(source["source_sha256"])],
                storage_uri=(
                    "artifacts/vnext/table_qualification_freeze/"
                    "{}.json".format(storage_source_id)
                ),
            )
            manifest = build_reader_input_manifest(
                derived_asset=asset,
                source_reference_ids=["source:" +
                                      str(source["source_sha256"])],
            )
            current = build_reader_payload(
                manifest=manifest,
                derived_asset=asset,
                task_contract=tasks[task_id],
            )
            provider, schema = build_provider_request_body(
                policy=policy,
                reader_request_bytes=current["request_bytes"],
            )
            baseline = _result_row(
                source=source,
                task_id=task_id,
                reader_body=current["body"],
                provider_envelope=provider,
                transport=current["table_transport"],
                expanded_equal=(
                    decode_compact_table_payload(
                        transport=current["table_transport"],
                    ) == asset["tables"]
                ),
                semantic_equal=True,
            )
            baseline["provider_layer_decomposition"] = (
                _provider_layer_decomposition(
                    provider_envelope=provider,
                    reader_body=current["body"],
                    output_schema_bytes=schema,
                )
            )
            baseline_rows.append(baseline)
            source_baselines.append(baseline)
            if task_id == TASK_IDS[0]:
                current_transport_by_source[
                    str(source["source_id"])
                ] = current["table_transport"]
                current_asset_by_source[str(source["source_id"])] = asset
                decompositions.append({
                    "source_id": source["source_id"],
                    "source_sha256": source["source_sha256"],
                    "compact_payload": _compact_payload_decomposition(
                        transport=current["table_transport"],
                    ),
                    "text_and_repetition": _text_and_repetition_census(
                        tables=asset["tables"],
                    ),
                })
            for candidate_id, encoder in (
                ("CANDIDATE-1", _candidate_one),
                ("CANDIDATE-2", _candidate_two),
                ("CANDIDATE-3", _candidate_three),
                ("CANDIDATE-4", _candidate_four),
            ):
                candidate = encoder(asset=asset)
                decoded = _decode_candidate(candidate=candidate)
                semantic_equal = (
                    _semantic_projection(tables=decoded)
                    == _semantic_projection(tables=asset["tables"])
                )
                body = _request_body(
                    manifest=manifest,
                    task=tasks[task_id],
                    transport=candidate,
                )
                envelope, _schema = build_provider_request_body(
                    policy=policy,
                    reader_request_bytes=canonical_json_bytes(value=body),
                )
                candidate_rows[candidate_id].append(_result_row(
                    source=source,
                    task_id=task_id,
                    reader_body=body,
                    provider_envelope=envelope,
                    transport=candidate,
                    expanded_equal=(decoded == asset["tables"]),
                    semantic_equal=semantic_equal,
                ))
        current_task_totals[str(source["source_id"])] = [
            int(row["exact_provider_envelope_bytes"])
            for row in source_baselines
        ]
        # CANDIDATE-5 changes only the research task contract; production-v2
        # transport remains byte-identical and the catalog stays untouched.
        merged_asset = current_asset_by_source[str(source["source_id"])]
        merged_transport = current_transport_by_source[str(
            source["source_id"])]
        merged_manifest = build_reader_input_manifest(
            derived_asset=merged_asset,
            source_reference_ids=["source:" + str(source["source_sha256"])],
        )
        merged_body = _request_body(
            manifest=merged_manifest,
            task=combined_task,
            transport=merged_transport,
        )
        merged_envelope, _schema = build_provider_request_body(
            policy=policy,
            reader_request_bytes=canonical_json_bytes(value=merged_body),
        )
        merged_row = _result_row(
            source=source,
            task_id=combined_task["task_contract_id"],
            reader_body=merged_body,
            provider_envelope=merged_envelope,
            transport=merged_transport,
            expanded_equal=(
                decode_compact_table_payload(transport=merged_transport)
                == merged_asset["tables"]
            ),
            semantic_equal=True,
        )
        merged_row["current_two_task_provider_envelope_bytes"] = sum(
            current_task_totals[str(source["source_id"])]
        )
        merged_row["estimated_batch_tokens_saved"] = (
            merged_row["current_two_task_provider_envelope_bytes"]
            - merged_row["exact_provider_envelope_bytes"]
        )
        candidate_rows["CANDIDATE-5"].append(merged_row)

    candidate_policy = {
        "CANDIDATE-1": {
            "machine_reversible": True,
            "model_final_visible_semantic_text_byte_equal": False,
            "model_visibility_note": (
                "Machine decoding restores exact semantic text, but "
                "normalized "
                "text is not directly present in the provider token stream."
            ),
            "required_serialization_or_schema_changes": [
                "new research serialization version",
                "bind fixed text_transform_version",
                (
                    "Reader/model contract must explain deterministic "
                    "normalization"
                ),
            ],
            "model_readability_risk": "MEDIUM_REQUIRES_REAL_QUALIFICATION",
        },
        "CANDIDATE-2": {
            "machine_reversible": True,
            "model_final_visible_semantic_text_byte_equal": True,
            "model_visibility_note": (
                "Every normalized semantic string remains directly present; "
                "raw source text becomes an optional override."
            ),
            "required_serialization_or_schema_changes": [
                "new research serialization version",
                "optional raw override field/position",
            ],
            "model_readability_risk": "LOW_TO_MEDIUM_REQUIRES_QUALIFICATION",
        },
        "CANDIDATE-3": {
            "machine_reversible": True,
            "model_final_visible_semantic_text_byte_equal": False,
            "model_visibility_note": (
                "Machine decoding is exact, but per-cell strings are "
                "dictionary references and therefore require real "
                "qualification validation "
                "of model readability."
            ),
            "required_serialization_or_schema_changes": [
                "new research serialization version",
                "string dictionary and integer reference schema",
            ],
            "model_readability_risk": "HIGH_REQUIRES_REAL_QUALIFICATION",
        },
        "CANDIDATE-4": {
            "machine_reversible": True,
            "model_final_visible_semantic_text_byte_equal": True,
            "model_visibility_note": (
                "Semantic strings remain direct, but locator coordinates "
                "become "
                "stateful deltas and need qualification for model use."
            ),
            "required_serialization_or_schema_changes": [
                "new research serialization version",
                "stateful delta-coordinate decoder and locator instructions",
            ],
            "model_readability_risk": "MEDIUM_REQUIRES_REAL_QUALIFICATION",
        },
        "CANDIDATE-5": {
            "machine_reversible": True,
            "model_final_visible_semantic_text_byte_equal": True,
            "model_visibility_note": (
                "Production-v2 table transport is unchanged; only a "
                "research-only "
                "two-role task estimate is formed after existing co-table "
                "proof."
            ),
            "required_serialization_or_schema_changes": [
                "no serializer change",
                (
                    "new combined task contract and qualification evidence "
                    "required"
                ),
            ],
            "model_readability_risk": (
                "ROLE_INTERFERENCE_REQUIRES_QUALIFICATION"
            ),
        },
    }
    candidates = []
    for candidate_id in sorted(candidate_rows):
        rows = candidate_rows[candidate_id]
        maximum = max(int(row["estimated_input_tokens"]) for row in rows)
        candidate = {
            "candidate_id": candidate_id,
            **candidate_policy[candidate_id],
            "decode_candidate_field_equal_current_expanded_authority": all(
                row["decode_candidate_field_equal_current_expanded_authority"]
                for row in rows
            ),
            "machine_decoded_semantic_text_byte_equal": all(
                row["machine_decoded_semantic_text_byte_equal"] for row in rows
            ),
            "per_source_task_measurements": rows,
            "maximum_estimated_input_tokens": maximum,
            "maximum_below_or_equal_200000": maximum <= THRESHOLD,
            "invalidated_qualification_family_ids_if_adopted": [
                "lodging_kpi_table"
            ],
            "contains_selector": False,
            "contains_filter": False,
            "contains_semantic_decision": False,
            "production_enabled": False,
        }
        if candidate_id == "CANDIDATE-5":
            candidate["co_table_evidence"] = co_table
            candidate["estimated_total_batch_tokens_saved"] = sum(
                int(row["estimated_batch_tokens_saved"]) for row in rows
            )
        candidates.append(candidate)

    after_root = _root_state(repo_root=repo_root)
    body = {
        "schema_version": 1,
        "record_type": "TABLE_STAGE_B_CONTEXT_MINIMIZATION_RECEIPT",
        "status": "DECISION_NEUTRAL_OFFLINE_EVIDENCE",
        "scope": {
            "reader_table_set": "ALL_DOCUMENT_TABLE_GRIDS_IN_DOCUMENT_ORDER",
            "semantic_prefilter": False,
            "selector_authorized": False,
            "production_serializer_changed": False,
            "production_task_contract_changed": False,
            "provider_or_sec_egress_authorized": False,
        },
        "authority": {
            "requirement_closure_hash": requirement[
                "requirement_closure_hash"
            ],
            "effective_d07_record_hash": content_hash(
                value=requirement["effective_decisions"]["D-07"],
            ),
            "matrix_sha256": sha256_file(path=repo_root / MATRIX_PATH),
            "task_catalog_sha256": sha256_file(path=repo_root / CATALOG_PATH),
            "provider_runtime_sha256": sha256_file(
                path=repo_root / PROVIDER_RUNTIME_PATH,
            ),
            "production_serializer_sha256": sha256_file(
                path=repo_root / PRODUCTION_SERIALIZER_PATH,
            ),
            "research_tool_sha256": sha256_file(
                path=repo_root / RESEARCH_TOOL_PATH,
            ),
            "estimator_id": "utf8_byte_upper_bound",
            "estimator_version": "1",
            "inclusive_threshold": THRESHOLD,
        },
        "source_set": sources,
        "source_set_hash": content_hash(value=sources),
        "task_contract_ids": list(TASK_IDS),
        "baseline_current_v2": {
            "per_source_task_measurements": baseline_rows,
            "maximum_estimated_input_tokens": max(
                int(row["estimated_input_tokens"]) for row in baseline_rows
            ),
            "marriott_measurements": [
                row for row in baseline_rows
                if row["source_id"] == "marriott-development"
            ],
            "two_tasks_repeat_complete_table_set": {
                source_id: {
                    "occupancy_and_revpar_total_provider_envelope_bytes": sum(
                        values
                    ),
                    "complete_table_set_send_count": 2,
                }
                for source_id, values in sorted(current_task_totals.items())
            },
        },
        "decomposition_by_source": decompositions,
        "candidates": candidates,
        "candidate_comparison_table": [{
            "candidate_id": candidate["candidate_id"],
            "maximum_estimated_input_tokens": candidate[
                "maximum_estimated_input_tokens"
            ],
            "maximum_below_or_equal_200000": candidate[
                "maximum_below_or_equal_200000"
            ],
            "machine_reversible": candidate["machine_reversible"],
            "model_final_visible_semantic_text_byte_equal": candidate[
                "model_final_visible_semantic_text_byte_equal"
            ],
            "model_readability_risk": candidate["model_readability_risk"],
        } for candidate in candidates],
        "interpretation_boundary": (
            "Machine round-trip proves information preservation only. It does "
            "not prove unchanged model extraction accuracy or readability."
        ),
        "root_business_artifacts_before": before_root,
        "root_business_artifacts_after": after_root,
        "root_business_artifacts_byte_equal": before_root == after_root,
        "egress_counts": {
            "real_model_provider_egress_count": 0,
            "paid_model_provider_call_count": 0,
            "real_sec_egress_count": 0,
        },
        "actual_prompt_tokens": "NOT_RUN",
    }
    if body["authority"]["production_serializer_sha256"] != (
        CURRENT_SERIALIZER_SHA256
    ):
        raise ContextInvestigationError("Production serializer bytes changed")
    if not body["root_business_artifacts_byte_equal"]:
        raise ContextInvestigationError(
            "Context research changed root artifacts")
    receipt_id = content_hash(value=body)
    return {"receipt_id": receipt_id, **body}


def write_context_minimization_receipt(
    *, repo_root: Path = REPO_ROOT,
) -> Dict[str, object]:
    """Write the deterministic receipt under its content-addressed ID."""
    receipt = build_context_minimization_receipt(repo_root=repo_root)
    digest = str(receipt["receipt_id"]).split(":", maxsplit=1)[1]
    relative = OUTPUT_ROOT / (digest + ".json")
    atomic_write_json(path=repo_root / relative, value=receipt)
    return {**receipt, "receipt_path": relative.as_posix()}


def main(*, argv: Sequence[str]) -> int:
    """Run the offline investigation and print its stable identity."""
    parser = argparse.ArgumentParser()
    parser.parse_args(list(argv))
    try:
        receipt = write_context_minimization_receipt(repo_root=REPO_ROOT)
    except (ContextInvestigationError, OSError, ValueError) as error:
        print(json.dumps({
            "status": "FAILED",
            "error_code": type(error).__name__,
            "message": str(error),
        }, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({
        "status": receipt["status"],
        "receipt_id": receipt["receipt_id"],
        "receipt_path": receipt["receipt_path"],
        "candidate_comparison_table": receipt["candidate_comparison_table"],
        "egress_counts": receipt["egress_counts"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
