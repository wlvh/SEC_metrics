"""Prepare a C02 development input with every block and table's visible grid.

Reuses the existing authenticated historical sources and table-grid parser.
This changes representation only: no selector, fact extraction, provider call,
Review or Result. Raw cells and their complete provenance remain in the local
derived asset; the model view keeps expanded text, headers and nonempty spans.
Empty unheaded cells decode to empty strings at their original coordinates.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from vnext.canonical import content_hash
from vnext.resource_limits import RESOURCE_LIMITS
from vnext.table_payload import encode_compact_table_payload


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def _need(ok, reason):
    if not ok:
        raise ValueError("C02_TABLE_CONTEXT_" + reason)


def expanded_view(view):
    """Recover all block texts and every expanded table text/header cell."""
    _need(set(view) == {"strings", "block_count", "geometry", "tables"}, "FIELDS")
    strings = view["strings"]
    _need(type(strings) is list and all(type(s) is str for s in strings), "STRINGS")

    def text(index):
        _need(type(index) is int and 0 <= index < len(strings), "STRING_REFERENCE")
        return strings[index]

    count = view["block_count"]
    _need(type(count) is int and 0 <= count <= len(strings), "BLOCK_COUNT")
    blocks = strings[:count]
    geometries = view["geometry"]

    def geometry(index):
        _need(type(index) is int and 0 <= index < len(geometries), "GEOMETRY_REFERENCE")
        g = geometries[index]
        _need(type(g) is list and len(g) == 3
              and type(g[0]) is int and type(g[1]) is int and type(g[2]) is bool,
              "GEOMETRY_FIELDS")
        return g

    tables, total = [], 0
    for order, t in enumerate(view["tables"]):
        _need(set(t) == {"i", "s", "c", "g", "x"}
              and t["i"] == "table_{:06d}".format(order + 1), "TABLE_ORDER")
        _need(type(t["s"]) is list and len(t["s"]) == 2, "TABLE_SIZE")
        rows, cols = t["s"]
        _need(type(rows) is int and type(cols) is int
              and 0 <= rows <= RESOURCE_LIMITS.max_rows_per_table
              and 0 <= cols <= RESOURCE_LIMITS.max_columns_per_table, "TABLE_SIZE")
        total += rows * cols
        _need(rows * cols <= RESOURCE_LIMITS.max_cells_per_table
              and total <= RESOURCE_LIMITS.max_total_cells, "CELL_LIMIT")
        cells = [[("", False) for _ in range(cols)] for _ in range(rows)]
        occupied = set()
        geometry(t["g"])
        for x in t["x"]:
            _need(type(x) is list and len(x) in (3, 4), "CELL_FIELDS")
            r, c, sid = x[:3]
            rs, cs, header = geometry(x[3] if len(x) == 4 else t["g"])
            _need(all(type(n) is int for n in (r, c, rs, cs))
                  and type(header) is bool and rs > 0 and cs > 0
                  and 0 <= r < r + rs <= rows and 0 <= c < c + cs <= cols, "CELL_SPAN")
            value = text(sid)
            _need(value != "" or header, "REDUNDANT_EMPTY_CELL")
            for rr in range(r, r + rs):
                for cc in range(c, c + cs):
                    _need((rr, cc) not in occupied, "OVERLAPPING_SPANS")
                    occupied.add((rr, cc))
                    cells[rr][cc] = (value, header)
        tables.append({"table_id": t["i"], "caption": text(t["c"]), "cells": cells})
    return blocks, tables


def assert_matches(view, document, derived):
    """Compare against the original blocks and public parser's full grid."""
    blocks, tables = expanded_view(view)
    _need(blocks == [b["text"] for b in document["blocks"]], "BLOCK_TEXT_OR_ORDER_CHANGED")
    expected = [{"table_id": t["table_id"], "caption": t["caption"],
                 "cells": [[(c["text"], c["header"]) for c in r["cells"]] for r in t["rows"]]}
                for t in derived["tables"]]
    _need(tables == expected, "EXPANDED_GRID_CHANGED")


def model_view(document, derived):
    # Validate the complete original asset using its existing reversible codec.
    encode_compact_table_payload(derived_asset=derived)
    _need(derived["parent_raw_asset_ids"] == [document["raw_asset_id"]], "RAW_PARENT_CHANGED")
    _need(all(b["block_index"] == i for i, b in enumerate(document["blocks"])), "BLOCK_ORDER")
    # The first entries are exactly B0..B<n>, including repeated block text.
    # A source-block id never becomes an unrelated string-dictionary id.
    strings = [b["text"] for b in document["blocks"]]
    indices = {}
    for i, text in enumerate(strings):
        indices.setdefault(text, i)
    geometries, geometry_ids = [[1, 1, False]], {(1, 1, False): 0}

    def intern(text):
        if text not in indices:
            indices[text] = len(strings)
            strings.append(text)
        return indices[text]

    def intern_geometry(cell):
        key = (cell["rowspan"], cell["colspan"], cell["header"])
        if key not in geometry_ids:
            geometry_ids[key] = len(geometries)
            geometries.append(list(key))
        return geometry_ids[key]

    tables = []
    for t in derived["tables"]:
        origins = [(c["row_index"], c["column_index"], intern_geometry(c), intern(c["text"]))
                   for r in t["rows"] for c in r["cells"]
                 if c["is_origin"] and (c["text"] or c["header"])]
        counts = Counter(g for _, _, g, _ in origins)
        default = min(counts, key=lambda g: (-counts[g], g)) if counts else 0
        cells = [[r, c, sid, *([g] if g != default else [])] for r, c, g, sid in origins]
        tables.append({"i": t["table_id"], "s": [t["row_count"], t["column_count"]],
                       "c": intern(t["caption"]), "g": default, "x": cells})
    view = {"strings": strings, "block_count": len(document["blocks"]),
            "geometry": geometries, "tables": tables}
    assert_matches(view, document, derived)
    return view


FORMAT = """\nSource representation (zero-based indices): strings is a shared text dictionary.
strings[0:block_count] are exactly the original visible blocks B0..B<block_count-1>.
Entries after block_count are extra cell/caption strings, never new source blocks.
Every HTML table appears in source order, including tables unrelated to this task.
Table i is its source table id; s=[row_count,column_count]; c indexes its caption.
geometry[g]=[rowspan,colspan,header]; each table's g is its default geometry index.
Each x cell is [row,column,string_index] using that default, or
[row,column,string_index,g] with an explicit geometry override. A cell's text and
header apply to every coordinate its span covers. All other coordinates are blank
and unheaded. Blank cells' original HTML spans, entity spelling, styles and images
are not rendered here; source images have not been interpreted. Table strings use
the existing parser's decoded whitespace-normalized text, not exact raw HTML.
Use this layout to interpret the supplied block text. Output source_blocks using
the original B indices, never dictionary indices or table coordinates. Dictionary
reuse is a spelling reference, not an assertion that two sources are one fact.
If a relation cannot be supported by the supplied blocks and layout, retain it
as unresolved. The extraction task and output contract above still apply.
"""


def prepare(source_root, company, end, out):
    from vnext.historical_text_input import prepare_historical_business_text_input
    from vnext.historical_text_results import prepare_business_text_sources
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    from vnext.table_grid import build_table_grid
    from vnext.continuous_request_context import measure_request
    from vnext.historical_xbrl_parse import xbrl_parsed_once

    with checkpoint_replayed_once(), xbrl_parsed_once():
        selection = resolve_period_selection(repo_root=source_root, company_id=company, report_end=end)
        prepared = prepare_historical_business_text_input(
            repo_root=source_root, company_id=company, metric_id="C02", period_selection=selection)
        _need(prepared["text_arguments"] is not None, "SOURCE_NOT_PREPARED")
        built = prepare_business_text_sources(metric_id="C02", **prepared["text_arguments"])
    # The preparation also retains the annual report used to locate the proxy.
    # C02's proposals name its actual governance source, as in the existing reader.
    document, = [built["documents"][sid] for sid in built["proposals"]]
    _need(document["source_state"] == "COMPLETE_LOCAL_DOCUMENT", "DOCUMENT_INCOMPLETE")
    raw = prepared["text_arguments"]["raw_bytes_by_id"][document["raw_asset_id"]]
    _need("sha256:" + hashlib.sha256(raw).hexdigest() == document["raw_asset_id"], "RAW_BYTES_CHANGED")
    derived = build_table_grid(html_bytes=raw, parent_raw_asset_ids=[document["raw_asset_id"]],
                               storage_uri="evidence/c02-development-table-context.json")
    view = model_view(document, derived)
    start = prepared["text_arguments"]["target"]["period_start"]
    _need(start.endswith("-01-01") and end.endswith("-12-31") and start[:4] == end[:4],
          "CALENDAR_FISCAL_LABEL_REQUIRED")
    filing = document["source_filing"]
    template = (REPO / "docs/evidence/issue28_continuous/c02-model-input-pilot-20261003/prompt.txt").read_text()
    task = template[template.index("Extract the registrant"):]
    prompt = (f"You receive all visible blocks and all HTML tables of {document['registrant_names'][0]}, "
              f"{filing['form']} filed {filing['filingDate']}, accession {filing['accessionNumber']}. "
              f"The annual reporting container is FY{end[:4]}, not a board measurement at {end}.\n\n"
              + task + FORMAT)
    request = {"model": "deepseek-flash", "messages": [
        {"role": "system", "content": prompt}, {"role": "user", "content": wire(view).decode()}],
        "response_format": {"type": "json_object"}, "temperature": 0, "max_tokens": 4096,
        "stream": False, "thinking": {"type": "disabled"}}
    measurement = measure_request(wire(request), require_reference=True)
    destination = out / (company + "-" + end)
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in (("view.json", view), ("table-grid.json", derived),
                        ("document.json", document), ("request-body.json", request),
                        ("context-measurement.json", measurement)):
        (destination / name).write_bytes(wire(value))
    (destination / "prompt.txt").write_text(prompt)
    metadata = {"record_type": "ISSUE_47_C02_TABLE_CONTEXT_DEVELOPMENT", "position": company + ":" + end,
                "source_reference_id": document["source_reference_id"], "raw_asset_id": document["raw_asset_id"],
                "document_id": document["text_document_id"], "filing": filing,
                "representation": "C02_BLOCKS_AND_TABLE_TEXT_HEADER_GRID_V2",
                "blocks": view["block_count"], "tables": len(view["tables"]),
                "expanded_cells": sum(t["row_count"] * t["column_count"] for t in derived["tables"]),
                "block_text_and_expanded_text_header_grids_identical": True,
                "full_raw_grid_round_trip_claimed": False,
                "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
                "artifacts": {n: hashlib.sha256((destination / n).read_bytes()).hexdigest()
                              for n in ("view.json", "table-grid.json", "document.json", "prompt.txt", "request-body.json")},
                "input_tokens": measurement["input_tokens"], "fits": measurement["fits"],
                "calls": [0, 0, 0], "model_answer_tested": False, "production_authorized": False}
    (destination / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: metadata[k] for k in ("position", "blocks", "tables", "input_tokens", "fits")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--position", action="append", required=True)
    args = parser.parse_args()
    for position in args.position:
        company, end = position.rsplit(":", 1)
        prepare(args.source_root.resolve(), company, end, args.out.resolve())


if __name__ == "__main__":
    main()
