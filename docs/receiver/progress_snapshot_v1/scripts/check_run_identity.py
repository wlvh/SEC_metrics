#!/usr/bin/env python3
"""Check that every per-cell history record was produced by the given code checkout with no new calls.

usage: check_run_identity.py <code_root> <history_root> <out.json>
For each work/updates/<metric>/periods/<FY>/latest-check.json: the SHA-256 of every
declared processing file must equal the file in <code_root>, and new_calls must be
provider/paid/SEC = 0/0/0. Records without declared files (failed before configuration)
are counted separately, never treated as matching.
"""
import collections, glob, hashlib, json, os, sys

code, hist, out = sys.argv[1], sys.argv[2], sys.argv[3]
cache = {}


def sha(rel):
    if rel not in cache:
        path = os.path.join(code, rel)
        cache[rel] = hashlib.sha256(open(path, 'rb').read()).hexdigest() if os.path.isfile(path) else None
    return cache[rel]


result = collections.defaultdict(collections.Counter)
mismatched, calls = collections.Counter(), collections.Counter()
for f in sorted(glob.glob(os.path.join(hist, '*', 'work', 'updates', '*', 'periods', '*', 'latest-check.json'))):
    company = os.path.relpath(f, hist).split(os.sep)[0]
    record = json.load(open(f))
    calls[json.dumps(record.get('new_calls'), sort_keys=True)] += 1
    files = ((record.get('completed_check') or {}).get('configuration') or {}).get('declared_processing_files') or {}
    if not files:
        result[company]['NO_DECLARED_FILES'] += 1
        continue
    bad = [p for p, digest in files.items() if sha(p) != digest]
    result[company]['MATCH' if not bad else 'MISMATCH'] += 1
    mismatched.update(bad)
report = {'code_root': code, 'history_root': hist, 'by_company': {k: dict(v) for k, v in sorted(result.items())},
          'mismatched_files': dict(mismatched), 'new_calls': dict(calls),
          'records': sum(sum(v.values()) for v in result.values())}
json.dump(report, open(out, 'w'), indent=1, sort_keys=True)
print(json.dumps(report, sort_keys=True))
