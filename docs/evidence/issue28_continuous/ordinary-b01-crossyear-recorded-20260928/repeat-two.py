"""Recorded Marriott B01 same-current-input repeat after cross-year advance."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO/'scripts'),
                str(REPO/'docs/evidence/issue28_continuous/c04-adjacent-year-rehearsal-20260927')]
from rehearse import saved_response
from sec_urls import submissions_url
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext import ordinary_refresh_cycle as refresh

ROOT = Path('/private/tmp/issue28-b01-crossyear-auto-two-20260928')
STATE = ROOT/'state'
HISTORY = STATE/'marriott_international/metrics/B01'
before_pointer = json.loads((HISTORY/'current.json').read_text())
old_id = next(p.name for p in (HISTORY/'attempts').iterdir()
              if p.name != before_pointer['successful_attempt'])
current_id = before_pointer['successful_attempt']

def tree(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}

old_before = tree(HISTORY/'attempts'/old_id)
current_before = tree(HISTORY/'attempts'/current_id)
current,_ = saved_response(submissions_url(cik=1048286))
session = recorded_sec_session(root=ROOT/'ledger', response=current)
with session.ledger.locked():
    counts_before = session.ledger.snapshot()['counts']
started = time.monotonic()

def no_network(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')

with patch.object(socket.socket, 'connect', side_effect=no_network), \
     patch.object(socket, 'getaddrinfo', side_effect=no_network), \
     patch('sec_http.urlopen', side_effect=no_network):
    report = refresh.refresh_and_process(session=session,
        state_root=STATE, company_ids=['marriott_international'],
        metric_ids=['B01'], max_sec_requests=0)
company, = report['companies']
metric, = company['updates']['metrics']
with session.ledger.locked():
    counts_after = session.ledger.snapshot()['counts']
after_pointer = json.loads((HISTORY/'current.json').read_text())
out = {'record_type':'ISSUE28_MARRIOTT_B01_CROSS_YEAR_REPEAT',
    'report_status':report['status'], 'metric_status':metric['status'],
    'old_success_package_unchanged':tree(HISTORY/'attempts'/old_id)==old_before,
    'new_success_package_unchanged':tree(HISTORY/'attempts'/current_id)==current_before,
    'successful_attempt_unchanged':after_pointer['successful_attempt']==before_pointer['successful_attempt'],
    'latest_attempt_advanced':after_pointer['latest_attempt']!=before_pointer['latest_attempt'],
    'ledger_counts_before_after':[counts_before,counts_after],
    'new_candidate_created':metric.get('new_candidate_created'),
    'seconds':round(time.monotonic()-started,3),
    'real_calls':[0,0,0],'production_authorized':False}
(ROOT/'repeat-result.json').write_text(json.dumps(out,ensure_ascii=False,
    indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False),flush=True)
assert metric['status']=='NO_SOURCE_CONTENT_CHANGE'
assert out['old_success_package_unchanged']
assert out['new_success_package_unchanged']
assert out['successful_attempt_unchanged'] and out['latest_attempt_advanced']
assert counts_before==counts_after==[0,0,3]
assert json.loads((HISTORY/'attempts'/after_pointer['latest_attempt']/'terminal.json').read_text())['status']=='NO_SOURCE_CONTENT_CHANGE'
