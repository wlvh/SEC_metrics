"""Largest D04 native supplement in every saved inline document, and its reference tokens. Zero calls.

Usage: python3 scan.py <restored source root> <out.json>

For each saved ``.htm`` that carries inline XBRL (restored root and the
checkout's evidence), this runs the frozen D04 native-object parser and
supplement compaction exactly as ``r6_semantic_source._native_units`` does,
and measures each compacted supplement's encoded size the way the frozen
grouping compares it with ``max_single_object_payload_bytes``. For objects
over the bound it also counts reference tokens of the encoded unit payload
(the pinned DeepSeek tokenizer; this is the payload alone, not a full request
with prompt and schema, so it is a lower bound on the request's input).
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))

from vnext import r6_semantic_source as frozen  # noqa: E402
from vnext.continuous_request_context import _load_tokenizer  # noqa: E402

BOUND = frozen.POLICY["max_single_object_payload_bytes"]
NEAR = frozen.POLICY["max_unit_payload_bytes"]


def supplements(raw):
    parser = frozen._NativeObjects(raw)
    parser.feed(raw.decode("utf-8-sig"))
    parser.close()
    objects = []
    for item in sorted(parser.objects, key=lambda x: (x["start_character"], x["end_character"])):
        if item["local_name"] in {"context", "unit"}:
            continue
        obj = {k: item[k] for k in ("namespace", "local_name", "attributes", "raw_xml", "namespaces",
                                    "start_character", "end_character")}
        obj["namespace_environment_id"] = frozen.content_hash(value=obj["namespaces"])
        obj["raw_xml_sha256"] = frozen.sha256_bytes(content=obj["raw_xml"].encode("utf-8"))
        objects.append(obj)
    return frozen._compact_supplements(objects)


def main(root, out):
    tokenizer, fallback = _load_tokenizer()
    paths = sorted({p.resolve() for base in (Path(root) / "evidence", REPO / "evidence")
                    for p in base.rglob("*.htm") if p.is_file()})
    documents, over, near, failed = 0, [], [], []
    for path in paths:
        raw = path.read_bytes()
        if b"<ix:" not in raw.lower():
            continue
        documents += 1
        try:
            compact = supplements(raw)
        except Exception as error:  # recorded, not hidden
            failed.append({"path": path.name, "error": type(error).__name__ + ":" + str(error)[:200]})
            continue
        if not compact:
            continue
        sizes = [len(frozen._bytes({"objects": [row]})) for row in compact]
        top = max(range(len(sizes)), key=sizes.__getitem__)
        entry = {"document": path.name, "sha256": frozen.sha256_bytes(content=raw),
                 "largest_supplement_bytes": sizes[top],
                 "local_name": compact[top]["local_name"],
                 "raw_xml_characters": len(compact[top]["raw_xml"]),
                 "over_bound": sum(s > BOUND for s in sizes)}
        if sizes[top] > BOUND:
            payload = frozen._bytes({"objects": [compact[top]]}).decode("utf-8")
            entry["payload_reference_tokens"] = (len(tokenizer.encode(payload, add_special_tokens=False).ids)
                                                 if tokenizer else None)
            over.append(entry)
        elif sizes[top] > NEAR:
            near.append(entry)
        print(path.name, sizes[top], flush=True)
    record = {"single_object_bound_bytes": BOUND, "unit_limit_bytes": NEAR,
              "tokenizer_fallback": fallback, "inline_documents": documents,
              "over_bound": sorted(over, key=lambda e: -e["largest_supplement_bytes"]),
              "between_unit_limit_and_bound": sorted(near, key=lambda e: -e["largest_supplement_bytes"]),
              "failed": failed, "calls": [0, 0, 0]}
    Path(out).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
