"""D03 genuine-source protocol and existing provider/WB-3 bridge, offline only."""
import copy
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext import ai_adapter as adapter, invocation_control as control
from vnext.canonical import canonical_json_bytes
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_semantic_calls import prepare_requests,build_plan,execute_feasibility,validate_semantic_rule_bindings
from vnext.r6_regulatory_semantics import validate_response
from vnext.r6_semantic_review import _source_items


class RegulatorySemanticTest(unittest.TestCase):
    def test_original_source_binding_and_offline_provider_bridge(self):
        location=os.environ.get('REGULATORY_WIRING_MATERIAL_ROOT')
        if location:
            directory=Path(location).resolve();self.assertFalse(directory.exists());directory.mkdir(parents=True)
        else:
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);directory=Path(temporary.name).resolve()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')), \
             patch.object(control,'effective_invocation_policy',side_effect=AssertionError('LEGACY_DEFAULT_FORBIDDEN')):
            candidates=prepare_requests(company_id='pfizer',metric_id='D03')
            source=json.loads(candidates[0].source_bytes)
            self.assertEqual(source['metric_id'],'D03')
            self.assertEqual(source['required_unit_ids'],[json.loads(p.request_bytes)['units'][0]['unit_id'] for p in candidates])
            self.assertEqual(3254,sum(len(u['payload']['facts']) for u in source['units'] if u['kind']=='NATIVE_FACTS'))
            prepared=next(p for p in candidates if any(x['source_index']==3928 and x['kind']=='VISIBLE_BLOCK'
                for x in json.loads(p.request_bytes)['required_candidate_assessments']))
            request=json.loads(prepared.request_bytes);unit=request['units'][0];kind,items=_source_items(unit)
            self.assertIn('In October 2018',items[3928]['text']);self.assertIn('in June 2025',items[3928]['text'])
            self.assertIn('relator is pursuing',items[3928]['text'])
            policy,plan=build_plan(prepared);envelope=json.loads(prepared.provider_request_body_bytes)
            self.assertEqual(envelope['thinking'],{'type':'disabled'});self.assertEqual(envelope['max_tokens'],4096)
            # The fixture leaves unknown meanings unresolved. It is not a
            # semantic benchmark answer or a declaration about actual cases.
            findings=[{'kind':'UNRESOLVED','subject':'UNRESOLVED','event_dates':[],'reported_status':'UNRESOLVED',
                'evidence':[{'kind':kind,'source_index':x['source_index']}],
                'reason':'Offline transport fixture; no semantic interpretation claimed.'}
                for x in request['required_candidate_assessments']]
            response={'request_id':request['request_id'],'units':[{'unit_id':unit['unit_id'],'reviewed':True,'findings':findings,'context_only_source_indices':[],'unresolved':['Fixture only.']}]}
            raw=canonical_json_bytes(value=response)
            checked=validate_response(request=request,raw_response=raw)
            self.assertFalse(checked['semantic_correctness_verified'])
            self.assertEqual(checked['provider_response'],response)
            self.assertEqual(checked['response_origin'],'HOST_MATERIALIZED_COMPLETE_SOURCE_ITEMS')
            context_only=copy.deepcopy(response)
            context_only['units'][0]['findings']=[f for f in findings if f['evidence'][0]['source_index']!=3923]
            context_only['units'][0]['context_only_source_indices']=[3923]
            context_checked=validate_response(request=request,raw_response=canonical_json_bytes(value=context_only))
            context_proposals=context_checked['source_selection_proposal']['units'][0]['findings']
            self.assertTrue(any(f['kind']=='OTHER_MEANING' and f['evidence'][0]['source_index']==3923 for f in context_proposals))
            overlap=copy.deepcopy(response);overlap['units'][0]['context_only_source_indices']=[3923]
            with self.assertRaisesRegex(ValueError,'D03_CONTEXT_AND_FINDING_OVERLAP'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=overlap))
            for finding in checked['findings']:
                for evidence in finding['evidence']:
                    self.assertEqual(evidence['text'],items[evidence['source_index']]['text'])
            schema=request['response_protocol']['json_schema']
            self.assertEqual(schema['properties']['units']['items']['properties']['unresolved']['items']['type'],'string')
            bad=copy.deepcopy(response);bad['units'][0]['unresolved']=[findings[0]]
            with self.assertRaisesRegex(ValueError,'D03_UNRESOLVED_FIELDS'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            bad=copy.deepcopy(response);bad['units'][0]['findings']=[f for f in findings if f['evidence'][0]['source_index']!=3928]
            with self.assertRaisesRegex(ValueError,'D03_KNOWN_SOURCE_CANDIDATE_NOT_ASSESSED'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            bad=copy.deepcopy(response);bad['units'][0]['findings'][0]['evidence'][0]['text']='An invented government investigation.'
            with self.assertRaisesRegex(ValueError,'D03_REFERENCE_OUTSIDE_SUPPLIED_SOURCE'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            for changes in [{'source_index':999999},{'kind':'NATIVE_FACT'},{'source_index':True}]:
                bad=copy.deepcopy(response);bad['units'][0]['findings'][0]['evidence'][0].update(changes)
                with self.assertRaisesRegex(ValueError,'D03_REFERENCE_OUTSIDE_SUPPLIED_SOURCE'):
                    validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            bad=copy.deepcopy(response);bad['units'][0]['findings'][0].update(kind='CURRENT_REGULATORY_ACTION',subject='TARGET_REGISTRANT',reported_status='NOT_STATED')
            with self.assertRaisesRegex(ValueError,'D03_CURRENT_ACTION_STATUS_CONFLICT'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=bad))
            temporal=copy.deepcopy(response)
            relator=next(f for f in temporal['units'][0]['findings'] if f['evidence'][0]['source_index']==3928)
            relator.update(kind='PRIVATE_OR_INTERNAL_ACTION',reported_status='ONGOING_AS_REPORTED',event_dates=[])
            temporal_checked=validate_response(request=request,raw_response=canonical_json_bytes(value=temporal))
            relator_checked=next(f for f in temporal_checked['findings'] if f['evidence'][0]['source_index']==3928)
            self.assertEqual(relator_checked['reported_status'],'ONGOING_AS_REPORTED')
            self.assertEqual(relator_checked['event_dates'],[])
            self.assertEqual(relator_checked['timing'],'CURRENT_REPORT')
            relator['event_dates']=['December 2099']
            with self.assertRaisesRegex(ValueError,'D03_EVENT_DATE_NOT_IN_SELECTED_SOURCE'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=temporal))
            relator.update(kind='REPORTED_REGULATORY_PROCESS',reported_status='NOT_STATED',event_dates=['2018-10'])
            dates_checked=validate_response(request=request,raw_response=canonical_json_bytes(value=temporal))
            dated=next(f for f in dates_checked['findings'] if f['evidence'][0]['source_index']==3928)
            self.assertEqual(dated['resolved_date_evidence'][0]['source_literal'],'October 2018')
            self.assertEqual(dated['resolved_date_evidence'][0]['canonical_date'],'2018-10')
            relator['event_dates']=['2018']
            with self.assertRaisesRegex(ValueError,'D03_EVENT_DATE_NOT_IN_SELECTED_SOURCE'):
                validate_response(request=request,raw_response=canonical_json_bytes(value=temporal))
            altered=copy.deepcopy(prepared.requirement);del altered['execution_authority']['files']['scripts/vnext/r6_semantic_source.py']
            with self.assertRaisesRegex(ValueError,'CONTINUOUS_SEMANTIC_RULE_NOT_BOUND'):
                validate_semantic_rule_bindings(altered)
            wire=canonical_json_bytes(value={'id':'d03-offline-only','model':'deepseek-flash','choices':[{
                'message':{'role':'assistant','content':raw.decode()},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1000,'completion_tokens':1000,'total_tokens':2000,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}})
            seen=[]
            class FakeResponse(io.BytesIO):headers={'x-request-id':'d03-offline-only'}
            def opener(*,fullurl,timeout):
                self.assertEqual(fullurl.full_url,'https://api.deepseek.com/chat/completions')
                self.assertEqual(fullurl.data,prepared.provider_request_body_bytes);self.assertEqual(timeout,120)
                seen.append(fullurl.data);return FakeResponse(wire)
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-not-a-secret'}),patch.object(adapter._DEEPSEEK_OPENER,'open',side_effect=opener):
                observed=adapter._build_repository_transport(policy=policy).complete(prepared_request=prepared,
                    egress_capability=adapter._RESERVATION_OWNER_EGRESS_CAPABILITY)
                self.assertEqual(observed.raw_response_bytes,wire)
            self.assertEqual(len(seen),1)
            ledger=recorded_ledger(root=directory/'recorded-ledger')
            path,outcome=execute_feasibility(prepared=prepared,ledger=ledger,recorded_wire=wire)
            self.assertIn('response_check',outcome);self.assertFalse(outcome['native_result_created'])
            with ledger.locked():self.assertEqual(ledger.snapshot()['counts'],[1,1,0])
            summary={'status':'D03_OFFLINE_WIRING_PASS','closure':prepared.requirement['requirement_closure_hash'],
                'source_units':len(candidates),'source_units_preserved':True,'native_facts':3254,
                'selected_request_id':request['request_id'],'required_candidate_indices':[x['source_index'] for x in request['required_candidate_assessments']],
                'request_bytes':len(prepared.provider_request_body_bytes),'estimated_tokens':plan['observability']['estimated_context_tokens'],
                'source_binding_gap_rejected':True,'network_disabled':True,'real_request_factory_to_controller_verified':True,
                'calls':[0,0,0],'native_mock_path':str(path),'native_result_created':False,'semantic_correctness_verified':False}
            (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':unittest.main()
