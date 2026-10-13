"""Actual saved-source cases; direct preparation is not company acceptance."""
from contextlib import ExitStack
import json
from pathlib import Path
import socket
import subprocess
import time
from unittest.mock import patch

from vnext.current_statement_metric_case import prepare_current_statement_metric_case
from vnext.normal_companyfacts_results import resolve_ordinary_companyfacts_metrics

source=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
fields=('value','unit','quality','reason_code','period_start','period_end','result_id')
records=[]
with ExitStack() as stack:
    stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
    stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
    stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
    for company in ('salesforce','paramount_skydance_paramount_global'):
        # Compute the retained adapter once per company, not once per metric.
        baseline=resolve_ordinary_companyfacts_metrics(repo_root=source,company_id=company)
        for metric in ('B04','B07'):
            started=time.perf_counter()
            case=prepare_current_statement_metric_case(source_root=source,company_id=company,metric_id=metric)
            current=case['results'][metric]
            old=baseline['metrics'][metric]['result']
            selected={field:current.get(field) for field in fields}
            expected={field:old.get(field) for field in fields}
            assert selected==expected,(company,metric,selected,expected)
            row={'company':company,'metric':metric,'current':selected,'baseline':expected,
                'same_result_id':current['result_id']==old['result_id'],
                'target_period':case['target_period'],
                'actual_selection':case['input_assessments']['current_statement_selection'],
                'current_seconds':time.perf_counter()-started}
            records.append(row)
            print(json.dumps({k:v for k,v in row.items() if k!='actual_selection'}),flush=True)
receipt={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'working_tree_test':True,'source_root':str(source),'results':records,'new_calls':[0,0,0],
    'scope':'DIRECT_CASE_COMPARISON_NOT_COMPANY_PERSISTENCE'}
Path(__file__).with_name('current-boundaries.json').write_text(json.dumps(receipt,indent=2)+'\n')
