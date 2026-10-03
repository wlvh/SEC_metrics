"""Read-only comparison of four declared C04 sources in the installed ledger copy."""
import json
from pathlib import Path

from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import CallLedger, _FACTORY
from vnext.normal_source_requirements import discover_saved_source_requirements


root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
evidence = Path(__file__).resolve().parent
plan = json.loads((evidence / 'four-url-plan.json').read_text())
expected = {row['source_url']: row for row in plan['requirements']}
ledger = CallLedger(factory=_FACTORY, root=root,
                    binding=strict_json_file(path=root/'binding.json'), live=True)
with ledger.locked():
    before = ledger.snapshot()
discovery = discover_saved_source_requirements(
    repo_root=root/'source-inputs', company_id='paramount_skydance_paramount_global')
selected = {row['source_url']: row for row in discovery['requirements']
            if row['source_url'] in expected}
assert set(selected) == set(expected)
rows = []
for url, original in expected.items():
    row = selected[url]
    assert row['roles'] == original['roles']
    result = {'url':url, 'form':original['filing_form'],
              'role':original['roles'][0], 'baseline_status':original['saved_status'],
              'installed_status':row['saved_status'],
              'request_attempt_id':row.get('proof',{}).get('request_attempt_id'),
              'source_reference_id':row.get('source_reference',{}).get('source_reference_id')}
    if row['saved_status'] == 'VERIFIED_SAVED_SOURCE':
        assert result['request_attempt_id'] and result['source_reference_id']
    rows.append(result)
with ledger.locked():
    after = ledger.snapshot()
assert before['counts'] == after['counts'] and len(before['rows']) == len(after['rows'])
summary = {'record_type':'ISSUE28_PARAMOUNT_C04_INSTALLED_FOUR_SOURCE_AUDIT',
           'discovery_id':discovery['requirements_id'],
           'four_exact_urls':rows,
           'verified_count':sum(row['installed_status']=='VERIFIED_SAVED_SOURCE' for row in rows),
           'missing_count':sum(row['installed_status']=='MISSING_SAVED_SOURCE' for row in rows),
           'ledger_counts_unchanged':before['counts'],
           'new_real_calls':[0,0,0], 'C04_result_created':False}
(evidence/'installed-four-status.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verified':summary['verified_count'],
                  'missing':summary['missing_count'],
                  'statuses':[(row['form'],row['role'],row['installed_status']) for row in rows],
                  'new_real_calls':summary['new_real_calls']}))
