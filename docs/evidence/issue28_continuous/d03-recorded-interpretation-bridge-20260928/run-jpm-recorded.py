"""One complete JPM D03 synthetic-recorded packet through current bridge."""
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode=True
REPO=Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import strict_json_file
from vnext.continuous_call_ledger import CallLedger,_FACTORY
from vnext.d03_native_preparation import prepare_native_input
from vnext.d03_recorded_response_set import record_offline_set
from vnext.d03_complete_interpretation import replay_recorded_complete_interpretation
from vnext.r6_regulatory_semantics import requests_from_source

ROOT=Path('/private/tmp/issue28-d03-jpm-recorded-bridge-20260928')
assert not ROOT.exists(), 'PACKET_ROOT_ALREADY_EXISTS'
LEDGER=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
ledger=CallLedger(factory=_FACTORY,root=LEDGER,
    binding=strict_json_file(path=LEDGER/'binding.json'),live=True)
with ledger.locked():before=ledger.snapshot()

def no_network(*a,**kw):raise AssertionError('NETWORK_FORBIDDEN')

started=time.monotonic()
with original_sources_only(), \
     patch.object(socket.socket,'connect',side_effect=no_network), \
     patch.object(socket,'getaddrinfo',side_effect=no_network), \
     patch('sec_http.urlopen',side_effect=no_network):
    prepared=prepare_native_input(company_id='jpmorgan_chase')
    originals=requests_from_source(prepared['source'])
    assert len(originals)==len(prepared['groups'])==38
    responses={}
    successor=0
    for original,group in zip(originals,prepared['groups']):
        assert original['request_id']==group['original_request_id']
        effective=group['effective_request']
        anchors=effective.get('source_fact_candidates',[])
        successor+=bool(anchors)
        units=[];reviews=[]
        for unit in effective['units']:
            owned=[anchor for anchor in anchors if anchor['unit_id']==unit['unit_id']]
            indices={row['source_index'] for row in effective[
                'required_candidate_assessments'] if row['unit_id']==unit['unit_id']}
            anchor_indices={anchor['block_index'] for anchor in owned}
            findings=[]
            for anchor in owned:
                index=len(findings)
                findings.append({'kind':'UNRESOLVED','subject':'UNRESOLVED',
                    'event_dates':[],'reported_status':'UNRESOLVED',
                    'evidence':[{'kind':'VISIBLE_BLOCK',
                                 'source_index':anchor['block_index']}],
                    'reason':'Synthetic recorded proposal; context remains unresolved.'})
                reviews.append({'candidate_id':anchor['candidate_id'],
                    'unit_id':unit['unit_id'],'finding_indices':[index]})
            units.append({'unit_id':unit['unit_id'],'reviewed':True,
                'findings':findings,
                'context_only_source_indices':sorted(indices-anchor_indices),
                'unresolved':['Synthetic recorded proposal, not a business conclusion.']})
        body={'request_id':effective['request_id'],'units':units}
        if anchors:body['candidate_reviews']=reviews
        responses[original['request_id']]=(json.dumps(body,
            ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    assert successor==1
    saved=record_offline_set(output_root=ROOT,source=prepared['source'],
        responses_by_original_id=responses)
    bridged=replay_recorded_complete_interpretation(packet_root=ROOT,
        expected_packet_id=saved['packet_id'],company_id='jpmorgan_chase')
with ledger.locked():after=ledger.snapshot()
assert before['counts']==after['counts']==[143,143,52]
assert len(before['rows'])==len(after['rows'])==195
assert bridged['group_count']==38 and len(bridged['request_mapping'])==38
assert sum(row['source_anchor_successor'] for row in bridged['request_mapping'])==1
assert bridged['proposed_branch']=='UNRESOLVED_REQUIRES_REVIEW'
assert bridged['provider_execution_identity_verified'] is False
assert bridged['native_result_or_run_created'] is False
summary={'record_type':'ISSUE28_JPM_D03_COMPLETE_SYNTHETIC_RECORDED_BRIDGE',
    'packet_id':saved['packet_id'], 'record_id':bridged['record_id'],
    'source_id':bridged['source_id'],'input_id':bridged['prepared_input_id'],
    'group_count':bridged['group_count'],
    'source_anchor_successor_group_count':1,
    'successor_mapping':[row for row in bridged['request_mapping']
        if row['source_anchor_successor']],
    'unresolved_group_count':len(bridged['unresolved_group_indices']),
    'proposed_branch':bridged['proposed_branch'],
    'recorded_response_only':True,
    'provider_execution_identity_verified':False,
    'native_result_or_run_created':False,
    'real_ledger_counts_before_after':[before['counts'],after['counts']],
    'real_calls':[0,0,0],
    'seconds':round(time.monotonic()-started,3)}
Path('/private/tmp/issue28-d03-jpm-recorded-bridge-summary-20260928.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
