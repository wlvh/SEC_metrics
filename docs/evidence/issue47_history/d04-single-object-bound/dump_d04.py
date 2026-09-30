import json, sys
from pathlib import Path
root = Path(sys.argv[1]); out = sys.argv[2]
sys.path.insert(0, str(root / "scripts"))
from vnext.historical_semantic_results import pinned_native_source, pinned_requests
from vnext.normal_period_selection import resolve_period_selection
sel = resolve_period_selection(repo_root=root, company_id="marriott_international", report_end="2023-12-31")
src = pinned_native_source(repo_root=root, company_id="marriott_international", metric_id="D04", period_selection=sel)
reqs = pinned_requests(src)
strip = lambda d: {k: v for k, v in d.items() if k not in ("units",)}
record = {"selection": sel, "source": {**strip(src), "unit_ids": [u["unit_id"] for u in src["units"]]},
          "requests": [{**strip(r), "unit_ids": [u["unit_id"] for u in r["units"]]} for r in reqs]}
Path(out).write_text(json.dumps(record, indent=1, sort_keys=True, default=str))
