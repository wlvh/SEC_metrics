"""Real recorded HTTP persistence on a tiny legacy-shaped ledger."""
import json
import shutil
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from tests.vnext import test_existing_historical_sec_state as fixture_module
from vnext import company_online as online
from vnext.existing_historical_sec_state import inspect_existing_historical_sec


class HistoricalSecCaptureAdapterTest(TestCase):
    def setUp(self):
        fixture=fixture_module.ExistingHistoricalSecStateTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root
        self.context={'company_id':'marriott_international','metric_ids':['B01'],
            'ledger_root':str(self.root),'maximum_counts':[0,0,4],
            'execution_mode':'RECORDED_TEST_ONLY','purpose':'ISSUE47_HISTORICAL_SOURCE_DEPENDENCY',
            'requirement_id':'issue_47_v1','requirement_closure_hash':'test-only',
            'recorded_http_root':str(self.root.parent/'replies')}
        self.url='https://data.sec.gov/submissions/CIK0001048286-attachments-001.json'
        self.ledger=online._ledger(self.context,'marriott_international',['B01'])
        self.source=self.root/'source-inputs'
        from tests.vnext.common import REPO_ROOT
        (self.source/'config').mkdir()
        shutil.copyfile(REPO_ROOT/'config/company_registry.csv',self.source/'config/company_registry.csv')

    def capture(self):return online.Capture(self.source,self.ledger,self.context,1)

    def test_recorded_capture_preserves_prior_rows_and_uses_next_old_format_slot(self):
        before=(self.root/'claims.jsonl').read_bytes()
        log_before=(self.source/'evidence/requests_log.csv').read_bytes()
        capture=self.capture()
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',return_value=(200,b'{"saved":true}',{},'')) as transport:
            result=capture.get(self.url)
            self.assertTrue(result['raw'])
        self.assertEqual(transport.call_count,1)
        state=inspect_existing_historical_sec(self.root)
        self.assertEqual(state['counts'],[0,0,4]);self.assertEqual(state['limits'],[0,0,4])
        self.assertFalse(state['blocked']);self.assertTrue((self.root/'claims.jsonl').read_bytes().startswith(before))
        intent=json.loads((self.root/'calls/0002/intent.json').read_text())
        self.assertEqual(intent['allowance_binding_id'],'fixture-binding')
        self.assertEqual(intent['previous_intent_id'],'fixture-intent')
        plan=json.loads((self.root/'calls/0002/sec-plan.json').read_text())
        self.assertEqual(plan['request']['url'],self.url)
        self.assertEqual(json.loads((self.root/'binding.json').read_text())['limits'],[0,0,2])
        # The actual old checkpoint reader accepts the appended records. The
        # tiny baseline is a recorded test prefix, not an acquisition grant.
        from vnext.continuous_sec_acquisition import validate_acquisition_checkpoint, ROOT, MANIFEST_PATH
        from vnext.normal_source_authority import _git_blob_id
        from vnext.canonical import content_hash,sha256_file,sha256_bytes
        registry=(self.source/'config/company_registry.csv').read_bytes()
        baseline={'files':{'config/company_registry.csv':{'size':len(registry),'git_blob_id':_git_blob_id(registry)},
                          'evidence/requests_log.csv':{'size':len(log_before),'git_blob_id':_git_blob_id(log_before)}}}
        slot=self.root/'calls/0002'
        captured={name:json.loads((slot/(file+'.json')).read_text())
                  for name,file in [('intent','intent'),('receipt','sec-receipt'),('terminal','terminal')]}
        body={'record_type':'ORDINARY_SEC_ACQUISITION_CHECKPOINT','schema_version':1,
              'execution_mode':'RECORDED_TEST_ONLY','real_sec_credit':False,'production_authorized':False,
              'source_credit':'RECORDED_TEST_ONLY','baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH),
              'ledger_sha256':sha256_file(path=self.source/'evidence/requests_log.csv'),'captures':[captured]}
        checkpoint={**body,'checkpoint_id':content_hash(value=body)}
        _,_,admitted=validate_acquisition_checkpoint(self.source,checkpoint,baseline)
        self.assertEqual(len(admitted),1)
        self.assertEqual(sha256_bytes(content=(slot/'sec-wire/body.bin').read_bytes()),captured['receipt']['wire']['body']['sha256'])
        other=self.capture()
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=AssertionError('No redraw')):
            other.get(self.url)
        self.assertEqual(inspect_existing_historical_sec(self.root)['counts'],[0,0,4])

    def test_wrong_url_root_refresh_and_limit_refuse_before_transport(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=AssertionError('No transport')):
            with self.assertRaisesRegex(ValueError,'OUTSIDE_BOUNDED_PURPOSE'):self.capture().get(self.url+'x')
            with self.assertRaisesRegex(ValueError,'OUTSIDE_BOUNDED_PURPOSE'):self.capture().get(self.url,refresh=True)
            with self.assertRaisesRegex(ValueError,'SOURCE_ROOT_CHANGED'):
                online.Capture(self.root.parent/'different',self.ledger,self.context,1)
        with self.assertRaisesRegex(ValueError,'CONTEXT_SCOPE_DIFFERS'):
            online._ledger({**self.context,'maximum_counts':[0,0,5]},'marriott_international',['B01'])
        self.assertEqual(inspect_existing_historical_sec(self.root)['counts'],[0,0,3])

    def test_plan_interrupt_consumes_opportunity_without_http_or_fake_terminal(self):
        capture=self.capture()
        with patch('vnext.company_online._atomic_json',side_effect=RuntimeError('interrupted plan')), \
             patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=AssertionError('No HTTP')):
            with self.assertRaises(RuntimeError):capture.get(self.url)
        state=inspect_existing_historical_sec(self.root)
        self.assertEqual(state['counts'],[0,0,4]);self.assertTrue(state['blocked'])
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_ATTEMPT'):self.capture().get(self.url)

    def test_unknown_and_new_rate_refusal_remain_charged_and_stopped(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',side_effect=OSError('recorded unknown')):
            with self.assertRaises(ValueError):self.capture().get(self.url)
        state=inspect_existing_historical_sec(self.root)
        self.assertEqual(state['counts'],[0,0,4]);self.assertTrue(state['blocked'])
        terminal=json.loads((self.root/'calls/0002/terminal.json').read_text())
        self.assertEqual(terminal['status'],'UNKNOWN_REMOTE_OUTCOME')
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_ATTEMPT'):self.capture().get(self.url)

    def test_new_403_is_persisted_as_a_stop(self):
        with patch('vnext.recorded_sec_http.RecordedSecHttpClient.reply',return_value=(403,b'recorded denial',{},'')):
            with self.assertRaises(ValueError):self.capture().get(self.url)
        state=inspect_existing_historical_sec(self.root)
        self.assertEqual(state['counts'],[0,0,4]);self.assertEqual(state['blocked'][0]['reason'],'HTTP_403')
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_ATTEMPT'):self.capture().get(self.url)

    def test_unclaimed_new_log_row_is_not_treated_as_old_imported_history(self):
        from sec_http import parse_request_log_rows,request_log_csv_bytes,refresh_request_log_manifest
        log=self.source/'evidence/requests_log.csv';rows=parse_request_log_rows(text=log.read_text())
        rows.append({**rows[-1],'status_code':'0','error':'unattributed interruption'})
        log.write_bytes(request_log_csv_bytes(rows=rows));refresh_request_log_manifest(workdir=self.source,log_path=log)
        with self.assertRaisesRegex(ValueError,'UNOWNED_LOG_TAIL'):self.capture().get(self.url)
