"""Read the existing historical adapter against the fixed shared contract."""
import importlib.util, json, socket
from pathlib import Path
from unittest.mock import patch
from vnext import legal_review_contract as shared

path=Path('/Users/lyuhongwang/.codex/worktrees/issue47-history-continue/SEC_metrics/scripts/vnext/historical_legal_review.py')
spec=importlib.util.spec_from_file_location('vnext.issue47_historical_legal_consumer_receiving',path)
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
fixture=json.loads(Path('tests/fixtures/d02_saved_quote_failures.json').read_text());rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    for case in [*fixture['cases'],*fixture['contract_pass_cases']]:
        try:
            shared.validate_answer(request=case['request'],raw_output=case['raw_answer']);direct='CONTRACT_PASSED'
        except shared.LegalReviewContractError as error:
            direct=str(error)
        try:
            adapter.validate_answer(request=case['request'],raw_output=case['raw_answer']);consumer='CONTRACT_PASSED'
        except adapter.LegalReviewContractError as error:
            consumer=str(error)
        assert consumer==direct
        assert adapter.request_bytes(request=case['request'])==shared.request_bytes(request=case['request'])
        rows.append({'case':case['name'],'original_terminal':case['original_terminal_status'],
            'direct':direct,'historical_consumer':consumer,'request_bytes_equal':True})
result={'consumer_path':str(path),'same_shared_function':adapter.validate_answer is shared.validate_answer,
    'same_request_function':adapter.request_bytes is shared.request_bytes,'cases':rows,
    'registration_executed':False,'run_created':False,'business_acceptance_added':False,
    'new_calls':dict(provider=0,paid=0,sec=0)}
Path('work/historical-consumer-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print({'cases':len(rows),'successes':sum(r['direct']=='CONTRACT_PASSED' for r in rows),
       'failures':sum(r['direct']!='CONTRACT_PASSED' for r in rows),
       'same_shared_function':result['same_shared_function']})
