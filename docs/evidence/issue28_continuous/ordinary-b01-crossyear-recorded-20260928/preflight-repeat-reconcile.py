"""Read-only correction of the repeat test's whole-pointer assumption."""
import json
from pathlib import Path

ROOT = Path('/private/tmp/issue28-b01-crossyear-preflight-20260928')
HISTORY = ROOT/'state/marriott_international/metrics/B01'
advance = json.loads((ROOT/'advance-result.json').read_text())
repeat = json.loads((ROOT/'repeat-result.json').read_text())
before = advance['current_pointer']
after = json.loads((HISTORY/'current.json').read_text())
new_attempt = after['latest_attempt']
terminal = json.loads((HISTORY/'attempts'/new_attempt/'terminal.json').read_text())
intent = json.loads((HISTORY/'attempts'/new_attempt/'intent.json').read_text())
valid = (repeat['metric_status'] == 'NO_SOURCE_CONTENT_CHANGE'
    and repeat['new_candidate_created'] is False
    and repeat['old_success_package_unchanged']
    and repeat['new_success_package_unchanged']
    and repeat['ledger_counts_before_after'] == [[0,0,2],[0,0,2]]
    and before['configuration_id'] == after['configuration_id']
    and before['successful_attempt'] == after['successful_attempt']
    and before['latest_attempt'] != after['latest_attempt']
    and terminal['status'] == 'NO_SOURCE_CONTENT_CHANGE'
    and terminal['attempt_id'] == new_attempt
    and intent['previous_successful_attempt'] == before['successful_attempt'])
result = {'record_type':'ISSUE28_B01_RECORDED_CROSS_YEAR_REPEAT_RECONCILIATION',
    'status':'PASS' if valid else 'FAILED',
    'original_test_exit':1,
    'original_test_wrong_assumption':'whole current.json pointer is unchanged',
    'before_pointer':before,'after_pointer':after,
    'repeat_terminal_status':terminal['status'],
    'successful_attempt_unchanged':before['successful_attempt']==after['successful_attempt'],
    'latest_attempt_advanced':before['latest_attempt']!=after['latest_attempt'],
    'old_success_package_unchanged':repeat['old_success_package_unchanged'],
    'new_success_package_unchanged':repeat['new_success_package_unchanged'],
    'recorded_ledger_counts_unchanged':repeat['ledger_counts_before_after'],
    'real_calls':[0,0,0]}
(ROOT/'repeat-reconciliation.json').write_text(json.dumps(result,
    ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','repeat_terminal_status',
    'successful_attempt_unchanged','latest_attempt_advanced',
    'original_test_exit')},ensure_ascii=False))
assert valid
