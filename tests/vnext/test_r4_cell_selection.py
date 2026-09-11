"""Source choices, recovered evidence, normal controller/Run and cold replay."""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_r4_live_qualification import copy_r4_release_workspace
from tests.vnext.test_r4_reader_responsibilities import no_network
from tests.vnext.r4_cell_selection_samples import layered_audit, schema_check
from vnext.cell_selection import (REVISION, reference_map, model_input, output_schema,
    expand_response, CellSelectionError)
from vnext.canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_file
from vnext import ai_adapter
from vnext.r4_development import diagnostic_implementation, prepare_diagnostic_context, build_diagnostic_plan, execute_diagnostic
from vnext.r4_run_store import create_r4_scoped_run, finalize_r4_scoped_run

SAMPLES=REPO_ROOT/'tests/fixtures/r4_cell_selection'
CASES=[r['fixture_id'] for r in strict_json_file(path=SAMPLES/'provenance.json')['cases']]


def source_case(root,fixture):
    request=json.loads(strict_json_file(path=root/'tests/fixtures/r4_cell_selection'/(fixture+'.request.json'))['messages'][1]['content'])
    scope=strict_json_file(path=root/'docs/r4_v3/qualified_cases'/fixture/'source_scope.json')
    return request,scope


def ref_at(request,row,column):
    return next(ref for ref,c in reference_map(request).items() if c['locator']['row_index']==row and c['locator']['column_index']==column)


def synthetic_response(request,scope,others=None):
    """New-request TEST DATA, never a modified paid response or live credit."""
    refs=reference_map(request)
    def ref(locator): return next(k for k,v in refs.items() if v['locator']==locator)
    selected=next(iter(scope['synthetic_candidate']['selected'].values()))
    response={'selected_cell':ref(scope['target_locator']),'selected_value_text':selected['claimed_raw_value'],
        'scope_evidence_cells':[ref(x['locator']) for x in selected['scope_evidence_locators']],
        'other_candidate_cells':others or [],'unresolved':[]}
    return response


class CellSelectionBoundaryTest(unittest.TestCase):
    def test_original_nine_layered_failures_are_read_only(self):
        audit=layered_audit(REPO_ROOT);cases={c['fixture_id']:c for c in audit['cases']}
        self.assertEqual(sum(c['syntax']=='FAIL' for c in cases.values()),3)
        self.assertEqual(sum(c['saved_json_schema']=='PASS' for c in cases.values()),6)
        self.assertTrue(all(c['channel']=={'response_format':{'type':'json_object'},'stream':False,
            'temperature':0,'thinking':{'type':'disabled'}} for c in cases.values()))
        bac=cases['r4_a12_alternate'];self.assertEqual(bac['selection']['declared_value'],'78')
        self.assertEqual(bac['selection']['source_text'],'$');self.assertEqual(bac['certified_target_source_cell']['text'],'34')
        self.assertFalse(cases['r4_a04_alternate']['scope_labels'][0]['source_checks'][0]['literal_present'])
        self.assertEqual(cases['r4_a11_alternate']['competitors'][-1]['source_text'],'1,882,211')
        self.assertEqual(cases['r4_a11_alternate']['competitors'][-1]['status'],'FAIL')
        self.assertIsNone(cases['r4_a11_alternate']['scope_labels'][0]['exact_alias'])
        self.assertFalse(cases['r4_a03_alternate']['competitors'][0]['period']['consistent'])
        self.assertFalse(cases['r4_a09_production']['competitors'][0]['unit']['consistent'])

    def test_nine_short_inputs_preserve_all_cells_without_identity_or_answers(self):
        for fixture in CASES:
            request,scope=source_case(REPO_ROOT,fixture);shown=model_input(request)
            self.assertEqual(sum(len(t['x']) for t in request['untrusted_scoped_table_data']['tables']),
                sum(len(t['cells']) for t in shown['tables']))
            text=canonical_json_bytes(value=shown).decode()
            self.assertNotIn('sha256:',text)
            for original,rendered in zip(request['untrusted_scoped_table_data']['tables'],shown['tables']):
                for cell,view in zip(original['x'],rendered['cells']):
                    _namespace,table,row,column=view[0].split('/')
                    self.assertEqual((table,int(row),int(column)),('t'+str(int(original['i'].split('_')[1])),cell[0],cell[1]))
                    self.assertEqual(view[1:],[cell[2],cell[3],cell[6]])
            for key in ('selected_cell','selected_value_text','target_locator','reference','synthetic_candidate'):
                self.assertNotIn('"'+key+'":',text)
            response=synthetic_response(request,scope)
            self.assertTrue(schema_check(response,output_schema()))
            native,receipt=expand_response(request=request,response_text=json.dumps(response),scope=scope)
            self.assertEqual(json.loads(native)['candidates'][0]['locator'],scope['target_locator'])
            self.assertEqual(receipt['original_response_sha256'],sha256_bytes(content=json.dumps(response).encode()))

    def test_period_percent_and_confidence_exclusion_are_source_derived(self):
        request,scope=source_case(REPO_ROOT,'r4_a03_alternate')
        response=synthetic_response(request,scope,[ref_at(request,4,6)])
        native,receipt=expand_response(request=request,response_text=json.dumps(response),scope=scope)
        comp=json.loads(native)['candidates'][0]['competing_candidates'][0]
        self.assertEqual(comp['claimed_period'],'2025-09-30')
        self.assertEqual(receipt['competitor_dispositions'][0]['period']['kind'],'COLUMN_DATE')
        self.assertEqual(comp['rejection_reason_claim'],'DIFFERENT_SOURCE_PERIOD')
        request,scope=source_case(REPO_ROOT,'r4_a09_production')
        native,receipt=expand_response(request=request,response_text=json.dumps(synthetic_response(request,scope,[ref_at(request,4,9)])),scope=scope)
        self.assertEqual(json.loads(native)['candidates'][0]['competing_candidates'][0]['claimed_reported_unit'],'percent')
        self.assertEqual(receipt['competitor_dispositions'][0]['unit']['normalized_value'],'0.0066')
        request,scope=source_case(REPO_ROOT,'r4_a12_alternate')
        native,receipt=expand_response(request=request,response_text=json.dumps(synthetic_response(request,scope,[ref_at(request,23,10)])),scope=scope)
        self.assertEqual(receipt['competitor_dispositions'][0]['exclusion'],'DIFFERENT_SOURCE_SCOPE:confidence_level')
        self.assertEqual(receipt['selected_unit_evidence']['normalized_value'],'34000000')
        request,scope=source_case(REPO_ROOT,'r4_a11_production')
        _,receipt=expand_response(request=request,response_text=json.dumps(synthetic_response(request,scope,[ref_at(request,2,3)])),scope=scope)
        self.assertEqual(receipt['competitor_dispositions'][0]['unit']['unit'],'UNKNOWN')
        self.assertEqual(receipt['competitor_dispositions'][0]['exclusion'],'UNRESOLVED')

    def test_wrong_cells_labels_and_unresolved_are_not_repaired(self):
        request,scope=source_case(REPO_ROOT,'r4_a12_alternate');good=synthetic_response(request,scope)
        changes=[{'selected_value_text':'78'}, {'selected_cell':ref_at(request,23,15),'selected_value_text':'78'},
            {'selected_cell':ref_at(request,23,10),'selected_value_text':'78'},
            {'scope_evidence_cells':[ref_at(request,7,9)]}, {'selected_cell':'other-request/t147/23/16'},
            {'scope_evidence_cells':[]}, {'scope_label_text':'95 percent'}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(CellSelectionError):
                expand_response(request=request,response_text=json.dumps({**good,**change}),scope=scope)
        req,s=source_case(REPO_ROOT,'r4_a04_alternate');bad=synthetic_response(req,s)
        bad['scope_evidence_cells']=[ref_at(req,7,0)]
        with self.assertRaisesRegex(CellSelectionError,'MISSING_SOURCE_SCOPE_LABEL'):
            expand_response(request=req,response_text=json.dumps(bad),scope=s)
        req,s=source_case(REPO_ROOT,'r4_a03_alternate');bad=synthetic_response(req,s)
        bad.update(selected_cell=ref_at(req,4,6),selected_value_text='115')
        with self.assertRaisesRegex(CellSelectionError,'SELECTED_PERIOD_NOT_PROVEN'):
            expand_response(request=req,response_text=json.dumps(bad),scope=s)
        # An unexplained other row is not silently dismissed, even at the same value.
        req,s=source_case(REPO_ROOT,'r4_a11_alternate');response=synthetic_response(req,s,[ref_at(req,21,16)])
        native,receipt=expand_response(request=req,response_text=json.dumps(response),scope=s)
        self.assertEqual(receipt['competitor_dispositions'][0]['exclusion'],'UNRESOLVED')
        self.assertTrue(json.loads(native)['unresolved_competing_claims'])
        response=synthetic_response(req,s);response['unresolved']=['real same-period conflict']
        native,_=expand_response(request=req,response_text=json.dumps(response),scope=s)
        self.assertEqual(json.loads(native)['unresolved_competing_claims'],[{'description':'real same-period conflict'}])
        # A supplied cell from a second window still cannot supply this table's scope.
        req,s=source_case(REPO_ROOT,'r4_a04_alternate');multi=copy.deepcopy(req)
        other=copy.deepcopy(multi['untrusted_scoped_table_data']['tables'][0]);other['i']='table_000999'
        multi['untrusted_scoped_table_data']['tables'].append(other)
        response=synthetic_response(req,s)
        response['scope_evidence_cells']=[next(k for k,c in reference_map(multi).items()
            if c['locator']['table_id']=='table_000999' and c['locator']['row_index']==4 and c['locator']['column_index']==0)]
        with self.assertRaisesRegex(CellSelectionError,'CROSS_TABLE'):
            expand_response(request=multi,response_text=json.dumps(response),scope=s)
        # SourceScope's old DIFFERENT_SCOPE label alone cannot justify exclusion.
        req,s=source_case(REPO_ROOT,'r4_a03_production')
        response=synthetic_response(req,s,[ref_at(req,29,6)])
        native,receipt=expand_response(request=req,response_text=json.dumps(response),scope=s)
        self.assertEqual(receipt['competitor_dispositions'][0]['exclusion'],'UNRESOLVED')
        self.assertTrue(json.loads(native)['unresolved_competing_claims'])

    def test_beginning_balance_is_reread_and_excluded_by_source_label(self):
        request,scope=source_case(REPO_ROOT,'r4_a11_alternate')
        response=synthetic_response(request,scope,[ref_at(request,30,16)])
        native,receipt=expand_response(request=request,response_text=json.dumps(response),scope=scope)
        comp=json.loads(native)['candidates'][0]['competing_candidates'][0]
        self.assertEqual(comp['claimed_raw_value'],'1,882,211')
        self.assertEqual(comp['rejection_reason_claim'],'DIFFERENT_SOURCE_STATISTIC')
        self.assertEqual(receipt['competitor_dispositions'][0]['unit']['normalized_value'],'1882211000000')


class CellSelectionRunIntegrationTest(unittest.TestCase):
    def test_normal_nine_acceptance_run_freeze_and_fresh_process_replay(self):
        with ExitStack() as stack:
            directory=Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='r4-short-current-')))
            root=directory/'current';copy_r4_release_workspace(root);guards=no_network(stack)
            with diagnostic_implementation(root,offline_interface_revision=REVISION):
                context=prepare_diagnostic_context(root);plan=build_diagnostic_plan(context,mode='RECORDED_TEST')
                with self.assertRaises(ValueError): build_diagnostic_plan(context,mode='LIVE')
                transports={};captured={};review=[]
                for entry in plan['entries']:
                    request=context._requests[entry['fixture_id']]
                    body=json.loads(request.request_bytes);scope=context._session._fixture(entry['fixture_id'])[-2]
                    other=[]
                    if entry['fixture_id']=='r4_a03_alternate':other=[ref_at(body,4,6)]
                    if entry['fixture_id']=='r4_a09_production':other=[ref_at(body,4,9)]
                    if entry['fixture_id']=='r4_a11_alternate':other=[ref_at(body,30,16)]
                    if entry['fixture_id']=='r4_a12_alternate':other=[ref_at(body,23,10)]
                    response=synthetic_response(body,scope,other)
                    wire={'id':'synthetic-short-'+str(entry['ordinal']),'model':'deepseek-v4-flash',
                        'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(response)}}],
                        'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                            'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':1000}}
                    transports[entry['entry_id']]=ai_adapter.build_recorded_scoped_transport(raw_response_bytes=canonical_json_bytes(value=wire),
                        expected_provider_request_body_sha256=request.identity['provider_request_body_sha256'])
                    review.append({'fixture_id':entry['fixture_id'],'period':body['task_period'],
                        'source_scope_manifest_id':body['source_scope_manifest_id'],
                        'request_sha256':request.identity['provider_request_body_sha256'],
                        'request_bytes':len(request.provider_request_body_bytes),
                        'output_schema_sha256':request.identity['provider_output_schema_sha256']})
                original=ai_adapter.run_scoped_ai_attempt
                def observe(**kwargs):
                    result=original(**kwargs)
                    if kwargs['prepared_request'].identity['fixture_id']=='r4_a12_alternate':
                        captured.update(result=result,context=kwargs['acceptance_context'])
                    return result
                with mock.patch.object(ai_adapter,'run_scoped_ai_attempt',side_effect=observe):
                    result=execute_diagnostic(context=context,plan=plan,recorded_transports=transports)
                self.assertEqual([e['status'] for e in result['entries']],['ACCEPTED']*9)
                self.assertEqual(result['counters']['real_model_provider_egress_count'],0)
                attempt=captured['result'];acceptance=captured['context']
                self.assertEqual(attempt.candidate_record['assistant_output_sha256'],sha256_bytes(content=attempt.payloads.assistant_output_bytes))
                trace=attempt.evidence_record['checks'][-1]['details']
                self.assertEqual(trace['revision'],REVISION)
                self.assertNotEqual(trace['original_response_sha256'],trace['native_projection_sha256'])
                run=root/'offline-short-run'
                create_r4_scoped_run(repo_root=root,run_dir=run,attempt_result=attempt,acceptance_context=acceptance)
                frozen=finalize_r4_scoped_run(repo_root=root,run_dir=run,acceptance_context=acceptance)
                self.assertEqual(frozen['status'],'FROZEN')
                print('SHORT_CELL: nine native acceptances; BAC A12 Run FROZEN / 34000000 USD',flush=True)
                (root/'selection-plan.json').write_bytes(canonical_json_bytes(value=plan))
            env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET'))}
            env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(root/'scripts')+os.pathsep+str(root))
            child=subprocess.run([sys.executable,'-c',
                'from pathlib import Path; from contextlib import ExitStack; import json; '
                'from tests.vnext.test_r4_reader_responsibilities import no_network; '
                'from vnext.r4_development import diagnostic_implementation; '
                'from vnext.r4_run_store import replay_r4_scoped_run; '
                's=ExitStack(); no_network(s); root=Path.cwd(); run=root/"offline-short-run"; '
                'm=json.loads((run/"manifest.json").read_text()); '
                'q=json.loads((run/m["r4_execution_binding"]["artifact_files"]["request_record"]["path"]).read_text()); '
                's.enter_context(diagnostic_implementation(root,offline_interface_revision=q["request_interface_revision"])); '
                'r=replay_r4_scoped_run(repo_root=root,run_dir=root/"offline-short-run"); '
                'print(json.dumps(r,ensure_ascii=False)); s.close()'],cwd=root,env=env,capture_output=True,text=True,timeout=300)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)
            print('SHORT_CELL_INDEPENDENT_REPLAY',child.stdout.strip(),flush=True)
            if os.environ.get('R4_SELECTION_EVIDENCE_DIR'):
                out=Path(os.environ['R4_SELECTION_EVIDENCE_DIR']);out.mkdir(parents=True,exist_ok=True)
                (out/'replay.json').write_text(child.stdout)
                (out/'next-nine-request-review.json').write_bytes(canonical_json_bytes(value={
                    'classification':'PENDING_NEW_AUTHORIZATION','interface_revision':REVISION,
                    'source_set':'EXISTING_NINE_BASE_ONLY','maximum_calls_proposed':9,'retry':0,'reuse':False,
                    'SEC':False,'publication':False,'qualification_credit':'NONE','new_real_calls':0,
                    'request_set_id':content_hash(value=review),'entries':review}))
                for entry in plan['entries']:
                    (out/(entry['fixture_id']+'.request.json')).write_bytes(context._requests[entry['fixture_id']].provider_request_body_bytes)
            for guard in guards:guard.assert_not_called()


if __name__=='__main__':unittest.main()
