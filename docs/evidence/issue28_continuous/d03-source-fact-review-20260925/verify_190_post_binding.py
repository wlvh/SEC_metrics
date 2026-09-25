"""Read-only old B13 success reuse after D03 changed the current V15 closure."""
import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch

from vnext import invocation_control as control
from vnext.continuous_call_ledger import live_ledger
from vnext.continuous_semantic_calls import prepare_requests, select_native_request_variants
from vnext.native_request_construction import request_construction_session
from vnext.normal_source_authority import ROOT
from vnext.requirements import load_requirement_snapshot


def run():
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
    ledger = live_ledger(requirement=requirement)
    with ledger.locked():
        before = ledger.snapshot()
    assert before['counts'] == [143, 143, 49] and len(before['rows']) == 192
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')), \
         patch.object(socket, 'getaddrinfo', side_effect=AssertionError('NO_DNS')), \
         patch('sec_http.urlopen', side_effect=AssertionError('NO_SEC')), \
         patch.object(control, 'effective_invocation_policy',
                      side_effect=AssertionError('NO_LEGACY')), \
         request_construction_session(requirement):
        prepared = prepare_requests(company_id='enphase_energy', metric_id='B13',
                                    reference_context=True, program_quantity_roles=True)
        selected, report = select_native_request_variants(
            prepared_requests=prepared, ledger=ledger, source_references=True,
            compact_references=True, semantic_role_labels=True,
            relevance_repair_group_index=2)
    assert len(selected) == len(report) == 6 and report[0]['original_ordinal'] == 190
    with ledger.locked():
        after = ledger.snapshot()
    assert after['counts'] == before['counts'] and len(after['rows']) == len(before['rows'])
    return {'record_type':'ISSUE28_B13_190_POST_D03_BINDING_REUSE',
            'requirement_closure_hash':requirement['requirement_closure_hash'],
            'reused_ordinal':report[0]['original_ordinal'],
            'revalidated_request_id':report[0]['request_id'],
            'request_count':len(selected), 'new_calls':[0,0,0],
            'ledger_counts':after['counts'], 'complete_b13_company_result':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('b13-190-post-binding.json'))
    output = parser.parse_args().output
    result = run()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result))
