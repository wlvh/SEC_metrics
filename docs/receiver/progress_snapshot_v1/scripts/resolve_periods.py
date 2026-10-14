#!/usr/bin/env python3
"""Step 1 of the receiver snapshot: issuer fiscal-year label -> selected annual report.

usage: resolve_periods.py <code_root> <source_root> <out.json> [company ...]
For each registered company tries labels 2020..2027 through the production
period selection on saved sources only and keeps every outcome (resolved or the
exact error). The latest five resolved labels form the company's window.
"""
import json, sys
from pathlib import Path
code, source, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_snapshot as b
b.load_code(code)
companies = sys.argv[4:] or [r['company_id'] for r in b.registry(code)]
result = b.windows(code, source, companies, years=range(2020, 2028))
out.write_text(json.dumps({'code_root': str(code), 'source_root': str(source), 'years': [2020, 2027],
                           'companies': result}, indent=1, sort_keys=True))
print({c: v['window'] for c, v in result.items()})
