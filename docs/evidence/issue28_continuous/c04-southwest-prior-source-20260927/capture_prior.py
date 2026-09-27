"""One authorized #28 SEC acquisition for declared Southwest C04 prior annual."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.continuous_sec_acquisition import live_sec_session

COMPANY = 'southwest_airlines'
URL = ('https://www.sec.gov/Archives/edgar/data/92380/'
       '000009238025000024/luv-20241231.htm')

session = live_sec_session()
session._check()
with session.ledger.locked():
    before = session.ledger.snapshot()
assert before['counts'] == [143, 143, 51]
assert before['rows'][-1]['ordinal'] == 194
assert before['rows'][-1]['status'] == 'SUCCEEDED'
result = session.capture(company_id=COMPANY, url=URL,
                         refresh_metadata=False, source_only_c04=True)
with session.ledger.locked():
    snapshot = session.ledger.snapshot()
print(json.dumps({'company_id': COMPANY, 'source_url': URL,
    'status': result['status'], 'calls': result['calls'],
    'last_ordinal': snapshot['rows'][-1]['ordinal'],
    'last_status': snapshot['rows'][-1]['status'],
    'cumulative_counts': snapshot['counts'],
    'receipt_id': result.get('receipt', {}).get('receipt_id'),
    'terminal_id': result.get('terminal', {}).get('terminal_id'),
    'checkpoint_id': result.get('checkpoint_id'),
    'production_authorized': False}, sort_keys=True))
raise SystemExit(0 if result['status'] in {
    'SUCCEEDED', 'EXISTING_VERIFIED_SOURCE_REUSED'} else 2)
