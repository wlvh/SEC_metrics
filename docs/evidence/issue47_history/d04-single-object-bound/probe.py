"""Which source object puts a pinned D04 source over the single-object bound? Zero calls.

Usage: python3 probe.py <restored source root> <out.json> company@report_end ...

Runs the historical D04 source preparation unchanged on a root restored from
the acquisition's export. Only the frozen grouping function is observed: for
every call it records the unit kind and, per row, the encoded size of that row
alone - the quantity the frozen bound compares with
``max_single_object_payload_bytes``. Rows over the bound are described (kind,
block index or fact concept, size, a text prefix). The grouping itself runs
unchanged, so a position that failed in the batch fails here the same way.
"""
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import r6_semantic_source as frozen  # noqa: E402
from vnext.historical_semantic_source import prepare_historical_d04_semantic_source  # noqa: E402
from vnext.normal_history_plan import checkpoint_replayed_once  # noqa: E402
from vnext.normal_period_selection import resolve_period_selection  # noqa: E402

BOUND = frozen.POLICY["max_single_object_payload_bytes"]
UNIT_LIMIT = frozen.POLICY["max_unit_payload_bytes"]


def describe(kind, row, size):
    if kind == "VISIBLE_TEXT":
        return {"kind": kind, "bytes": size, "block_index": row["block_index"],
                "text_characters": len(row["text"]), "raw_bytes": row["raw_end_byte"] - row["raw_start_byte"],
                "text_prefix": row["text"][:240]}
    if isinstance(row, dict) and "fact" in row:
        fact = row["fact"]
        return {"kind": kind, "bytes": size, "concept": fact.get("concept"),
                "context_ref": fact.get("context_ref"), "ordinal": fact.get("ordinal"),
                "value_characters": len(str(fact.get("value") or "")),
                "value_prefix": str(fact.get("value") or "")[:240]}
    if isinstance(row, dict) and "raw_xml" in row:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row["raw_xml"])).strip()
        return {"kind": kind, "bytes": size, "namespace": row["namespace"],
                "local_name": row["local_name"], "attributes": row["attributes"],
                "raw_xml_characters": len(row["raw_xml"]), "visible_characters": len(text),
                "nested_objects": len(row.get("nested_objects", [])),
                "nested_local_names": sorted({o["local_name"] for o in row.get("nested_objects", [])}),
                "start_character": row["start_character"], "end_character": row["end_character"],
                "text_prefix": text[:240]}
    return {"kind": kind, "bytes": size, "row_keys": sorted(row)[:20] if isinstance(row, dict) else None}


def main(root, out, positions):
    root, results = Path(root), {}
    original = frozen._group
    with checkpoint_replayed_once():
        for position in positions:
            company, end = position.split("@")
            seen = {"largest": {}, "over": [], "rows": {}}

            def observed(rows, render, document_id, kind):
                sizes = [len(frozen._bytes(render(rows[i:i + 1]))) for i in range(len(rows))]
                seen["rows"][kind] = seen["rows"].get(kind, 0) + len(rows)
                if sizes:
                    top = max(range(len(sizes)), key=sizes.__getitem__)
                    if sizes[top] > seen["largest"].get(kind, {}).get("bytes", -1):
                        seen["largest"][kind] = describe(kind, rows[top], sizes[top])
                seen["over"].extend(describe(kind, rows[i], s) for i, s in enumerate(sizes) if s > BOUND)
                return original(rows, render, document_id, kind)

            frozen._group = observed
            started = time.time()
            try:
                selection = resolve_period_selection(repo_root=root, company_id=company, report_end=end)
                source = prepare_historical_d04_semantic_source(repo_root=root, company_id=company,
                                                                period_selection=selection)
                outcome = {"units": len(source["units"])}
            except Exception as error:  # recorded, not hidden
                outcome = {"error": type(error).__name__ + ":" + str(error)[:300]}
            finally:
                frozen._group = original
            results[position] = {**outcome, **seen, "seconds": int(time.time() - started)}
            print(position, outcome, [(o["kind"], o["bytes"]) for o in seen["over"]],
                  {k: v["bytes"] for k, v in seen["largest"].items()}, flush=True)
    record = {"single_object_bound_bytes": BOUND, "unit_limit_bytes": UNIT_LIMIT,
              "root_note": "restored from the committed export; not a data root the Runs use",
              "positions": results, "calls": [0, 0, 0]}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
