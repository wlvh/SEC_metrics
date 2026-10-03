import json, sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT))
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext import going_concern_source as gcs, r6_semantic_source as r6, historical_annual_input as hai
from vnext.normal_period_selection import resolve_period_selection
def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append((path + "/" + k, "only in " + ("pinned" if k in a else "ordinary")))
            else:
                out.extend(diff(a[k], b[k], path + "/" + k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff(x, y, path + "[%d]" % i))
    elif a != b:
        out.append((path, "differs"))
    return out
with original_sources_only():
    sel = resolve_period_selection(repo_root=ROOT, company_id="marriott_international", report_end="2025-12-31")
    v1 = hai.prepare_original_historical_input(repo_root=ROOT, company_id="marriott_international", period_selection=sel)
    v2 = hai.prepare_historical_annual_input(repo_root=ROOT, company_id="marriott_international", period_selection=sel)
    with patch.object(gcs, "prepare_saved_annual_input", lambda **_: v1), patch.object(r6, "prepare_saved_annual_input", lambda **_: v2):
        pinned = r6.prepare_d04_semantic_source(repo_root=ROOT, company_id="marriott_international")
    ordinary = r6.prepare_d04_semantic_source(repo_root=ROOT, company_id="marriott_international")
d = diff(pinned, ordinary)
print(len(d)); 
import collections
print(collections.Counter(p.split("/")[1] if p.count("/")>=1 else p for p, _ in d))
for p, why in d[:40]: print(p, why)
print("units equal:", pinned["units"] == ordinary["units"])
print("pinned filing keys:", sorted(pinned["prepared_annual_input"]["filing"]))
