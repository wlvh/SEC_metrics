"""Read-only check whether current V15 closure can reuse native B13 success190."""
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import (prepare_requests,
    select_native_request_variants)
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


evidence = Path(__file__).resolve().parent
requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
ledger = live_ledger(requirement=requirement)
with ledger.locked():
    before = ledger.snapshot()
assert before['counts'] == [143,143,49] and len(before['rows']) == 192
reason = None
selected = None
report = None
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')), \
     patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')), \
     patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')), \
     patch.object(control,'effective_invocation_policy',
                  side_effect=AssertionError('NO_LEGACY')), \
     request_construction_session(requirement):
    prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                reference_context=True, program_quantity_roles=True)
    try:
        selected, report = select_native_request_variants(
            prepared_requests=prepared, ledger=ledger,
            source_references=True, compact_references=True,
            semantic_role_labels=True, relevance_repair_group_index=2)
    except Exception as error:
        reason = {'type':type(error).__name__, 'message':str(error)}
with ledger.locked():
    after = ledger.snapshot()
assert after['counts'] == before['counts'] and len(after['rows']) == 192
summary = {'record_type':'ISSUE28_B13_190_CURRENT_CLOSURE_NO_CALL_REUSE_CHECK',
    'requirement_closure_hash':requirement['requirement_closure_hash'],
    'old_190_status':'SUCCEEDED_IN_ORIGINAL_LEDGER',
    'current_selection_status':'REUSED' if reason is None else 'BLOCKED',
    'current_selection_error':reason,
    'selected_190_ordinal':report[0]['original_ordinal'] if report else None,
    'ledger_counts_unchanged':after['counts'],
    'new_real_calls':[0,0,0],
    'complete_B13_company_result':False}
(evidence/'no-call-reuse-190.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary))
