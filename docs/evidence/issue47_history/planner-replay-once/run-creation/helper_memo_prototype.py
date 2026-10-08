"""Prototype: the frozen checkpoint replay with its pure log helpers memoized."""
import contextlib, sys, time, json, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))
import sec_http
from vnext import ordinary_source_authority as authority
from vnext.canonical import strict_json_file, canonical_json_bytes
from vnext.normal_source_authority import MANIFEST_PATH, ROOT

FROZEN = {name: getattr(sec_http, name) for name in
          ("parse_request_log_rows", "request_log_attempt_id", "request_log_prefix_bytes")}


def _memos():
    parsed, ids, prefixes = {}, {}, {}
    def parse_request_log_rows(*, text):
        if type(text) is not str:
            return FROZEN["parse_request_log_rows"](text=text)
        rows = parsed.get(text)
        if rows is None:
            rows = FROZEN["parse_request_log_rows"](text=text)
            parsed[text] = [dict(row) for row in rows]
            return rows
        return [dict(row) for row in rows]
    def request_log_attempt_id(*, row_index, row):
        if not (type(row_index) is int and type(row) is dict
                and all(type(key) is str and type(value) is str for key, value in row.items())):
            return FROZEN["request_log_attempt_id"](row_index=row_index, row=row)
        key = (row_index, tuple(row.items()))
        found = ids.get(key)
        if found is None:
            found = FROZEN["request_log_attempt_id"](row_index=row_index, row=row)
            ids[key] = found
        return found
    def request_log_prefix_bytes(*, text, row_count):
        if not (type(text) is str and type(row_count) is int):
            return FROZEN["request_log_prefix_bytes"](text=text, row_count=row_count)
        key = (text, row_count)
        found = prefixes.get(key)
        if found is None:
            found = FROZEN["request_log_prefix_bytes"](text=text, row_count=row_count)
            prefixes[key] = found
        return found
    return {"parse_request_log_rows": parse_request_log_rows,
            "request_log_attempt_id": request_log_attempt_id,
            "request_log_prefix_bytes": request_log_prefix_bytes}


@contextlib.contextmanager
def log_helpers_memoized():
    memos = _memos()
    swapped = []
    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if not (name == "sec_http" or name.startswith("vnext.")):
            continue
        namespace = vars(module)
        for helper, frozen in FROZEN.items():
            if namespace.get(helper) is frozen:
                namespace[helper] = memos[helper]
                swapped.append((namespace, helper))
    try:
        yield len(swapped)
    finally:
        for namespace, helper in swapped:
            if namespace.get(helper) is memos[helper]:
                namespace[helper] = FROZEN[helper]


def digest(answer):
    raw, old_ids, admitted = answer
    return hashlib.sha256(raw).hexdigest(), hashlib.sha256(
        canonical_json_bytes(value={"old_ids": sorted(old_ids), "admitted": admitted})).hexdigest()


root = Path(sys.argv[1])
checkpoint = authority._trusted_checkpoint(root)
baseline = strict_json_file(path=ROOT / MANIFEST_PATH)
started = time.time()
with log_helpers_memoized() as count:
    memo_answer = authority._validate_checkpoint(root, checkpoint, baseline)
memo_seconds = round(time.time() - started, 1)
print("swapped", count, "memo seconds", memo_seconds, flush=True)
started = time.time()
frozen_answer = authority._validate_checkpoint(root, checkpoint, baseline)
frozen_seconds = round(time.time() - started, 1)
print("frozen seconds", frozen_seconds, flush=True)
print(json.dumps({"captures": len(checkpoint["captures"]), "memo_seconds": memo_seconds,
                  "frozen_seconds": frozen_seconds, "same_answer": memo_answer == frozen_answer,
                  "memo_digest": digest(memo_answer), "frozen_digest": digest(frozen_answer)}))
