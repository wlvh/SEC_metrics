"""Pinned C02 text/header-grid representation received from Issue #47.

Source: 417ccfb788f39f53e5ef2b2d825a3fa46efc11bf
Original: tools/prepare_c02_table_context.py, pure representation functions only.
No historical preparation, selector, model invocation or acceptance is imported.
The provider retains implementation ownership; this receiving version is fixed.
"""
from collections import Counter
import json
from .resource_limits import RESOURCE_LIMITS
from .table_payload import encode_compact_table_payload

PROVIDER_COMMIT = '417ccfb788f39f53e5ef2b2d825a3fa46efc11bf'
PROVIDER_PATH = 'tools/prepare_c02_table_context.py'

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


