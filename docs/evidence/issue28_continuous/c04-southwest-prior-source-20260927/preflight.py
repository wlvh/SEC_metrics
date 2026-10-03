"""Read-only authorization, dependency and ledger preflight for one URL."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.continuous_sec_acquisition import live_sec_session

plan = json.loads((HERE/'plan.json').read_text())
expected = ('https://www.sec.gov/Archives/edgar/data/92380/'
            '000009238025000024/luv-20241231.htm')
assert plan['status'] == 'OFFLINE_SOURCE_PLAN'
assert plan['dependency']['source_url'] == expected
assert plan['dependency']['roles'] == ['prior_annual_primary']
assert plan['dependency']['saved_status'] == 'MISSING_SAVED_SOURCE'
assert plan['calls'] == [0, 0, 0]
session = live_sec_session()
session._check()
with session.ledger.locked():
    snapshot = session.ledger.snapshot()
assert snapshot['counts'] == [143, 143, 51]
assert snapshot['rows'][-1]['ordinal'] == 194
assert snapshot['rows'][-1]['status'] == 'SUCCEEDED'
policy = json.loads((ROOT/'config/issue28_continuous_calls_v1.json').read_text())
assert snapshot['counts'][2] < policy['maximum_additional_provider_paid_sec_calls'][2]
print(json.dumps({'record_type': 'ISSUE28_C04_ONE_SEC_SOURCE_PREFLIGHT',
    'company_id': 'southwest_airlines', 'source_url': expected,
    'declared_role': plan['dependency']['roles'][0],
    'saved_status': plan['dependency']['saved_status'],
    'requirement_id': session.requirement['requirement_id'],
    'requirement_closure': session.requirement['requirement_closure_hash'],
    'source_only_c04': True, 'automatic_retry_count': 0,
    'counts_before': snapshot['counts'],
    'last_ordinal_before': snapshot['rows'][-1]['ordinal'],
    'sec_cap': policy['maximum_additional_provider_paid_sec_calls'][2],
    'calls': [0, 0, 0]}, sort_keys=True))
