"""Tiny existing-ledger fixtures; no capture or private ledger mutation."""
import json
from pathlib import Path
import tempfile
import unittest
from sec_http import REQUEST_LOG_FIELDNAMES, request_log_csv_bytes, refresh_request_log_manifest
from scripts.vnext.canonical import sha256_bytes
from scripts.vnext.existing_historical_sec_state import inspect_existing_historical_sec


class ExistingHistoricalSecStateTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = (Path(temp.name)/'existing').resolve(); self.root.mkdir()
        binding = {'record_type':'ISSUE_47_HISTORICAL_CALL_ALLOWANCE','binding_id':'fixture-binding',
                   'requirement_id':'issue_47_v1','execution_mode':'RECORDED_TEST_ONLY','limits':[0,0,2],
                   'purposes':['ISSUE47_HISTORICAL_SOURCE_DEPENDENCY']}
        self.write(self.root/'binding.json', binding)
        self.intent = {'record_type':'ISSUE_47_HISTORICAL_CALL_INTENT','intent_id':'fixture-intent',
            'allowance_binding_id':'fixture-binding','requirement_id':'issue_47_v1',
            'execution_mode':'RECORDED_TEST_ONLY','channel':'SEC','ordinal':1,
            'previous_intent_id':None,'request_digest':'fixture-request'}
        self.claims = (json.dumps(self.intent)+'\n').encode()
        (self.root/'claims.jsonl').write_bytes(self.claims)
        (self.root.parent/('.'+self.root.name+'.claims.jsonl')).write_bytes(self.claims)
        self.slot = self.root/'calls/0001'; self.slot.mkdir(parents=True)
        self.write(self.slot/'intent.json', self.intent)
        self.row = {key:'' for key in REQUEST_LOG_FIELDNAMES}
        self.row.update(method='GET', status_code='200', source_url='https://data.sec.gov/submissions/CIK0001048286.json',
                        document_name='CIK0001048286.json')
        log = self.root/'source-inputs/evidence/requests_log.csv'; log.parent.mkdir(parents=True)
        log.write_bytes(request_log_csv_bytes(rows=[self.row])); refresh_request_log_manifest(workdir=self.root/'source-inputs',log_path=log)
        self.receipt = {'receipt_id':'fixture-receipt','intent_id':'fixture-intent','execution_mode':'RECORDED_TEST_ONLY',
                        'status':'SUCCEEDED','ledger_row_index':0,'ledger_row':self.row}
        self.terminal = {'intent_id':'fixture-intent','sec_receipt_id':'fixture-receipt',
                        'execution_mode':'RECORDED_TEST_ONLY','status':'SUCCEEDED','stop_reason':''}
        self.write(self.slot/'sec-receipt.json',self.receipt);self.write(self.slot/'terminal.json',self.terminal)
        self.extension = self.root.parent/('.'+self.root.name+'.extension-1.json')
        self.write(self.extension,{'extension_ordinal':1,'maximum_additional_provider_paid_sec_calls':[0,0,2],
            'ledger_state':{'claims':{'size':len(self.claims),'sha256':sha256_bytes(content=self.claims)},'claim_count':1}})
        self.resume = self.root.parent/('.'+self.root.name+'.resumes.jsonl')
        self.resume.write_text(json.dumps({'record_type':'ISSUE_47_SEC_LEDGER_RESUME','budget_root':str(self.root),
            'lost_segment':{'reserve_sec_calls':2},'bounded_capture':{'maximum_counts':[0,0,4],
                'counts_before':[0,0,3],'maximum_additional_sec_calls':1,'retry_count':0,
                'company_id':'marriott_international',
                'source_url':'https://data.sec.gov/submissions/CIK0001048286-attachments-001.json'}})+'\n')

    def write(self,path,value):path.write_text(json.dumps(value))

    def read(self):return inspect_existing_historical_sec(self.root)

    def test_additive_limit_and_conservative_count_are_separate_from_binding(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.read()
        self.assertEqual(result['counts'],[0,0,3]);self.assertEqual(result['limits'],[0,0,4])
        self.assertEqual(result['binding']['limits'],[0,0,2]);self.assertFalse(result['capture_authorized_by_this_view'])
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_missing_terminal_is_counted_and_blocks(self):
        (self.slot/'terminal.json').unlink();result=self.read()
        self.assertEqual(result['counts'],[0,0,3]);self.assertEqual(result['blocked'][0]['reason'],'INCOMPLETE_ATTEMPT')

    def test_unknown_outcome_is_not_free_or_resolved(self):
        self.terminal.update(status='UNKNOWN_REMOTE_OUTCOME',stop_reason='UNKNOWN_REMOTE_OUTCOME')
        self.write(self.slot/'terminal.json',self.terminal);result=self.read()
        self.assertEqual(result['counts'],[0,0,3]);self.assertTrue(result['blocked'])

    def test_wrong_intent_binding_or_extension_prefix_is_rejected(self):
        self.intent['allowance_binding_id']='other';self.write(self.slot/'intent.json',self.intent)
        with self.assertRaisesRegex(ValueError,'INTENT_RELATION_DIFFERS'):self.read()
        self.intent['allowance_binding_id']='fixture-binding';self.write(self.slot/'intent.json',self.intent)
        self.write(self.extension,{'extension_ordinal':1,'maximum_additional_provider_paid_sec_calls':[0,0,2],
            'ledger_state':{'claims':{'size':len(self.claims),'sha256':'wrong'},'claim_count':1}})
        with self.assertRaisesRegex(ValueError,'EXTENSION_PREFIX_DIFFERS'):self.read()

    def test_known_failure_is_charged_and_wrong_logged_row_is_rejected(self):
        self.receipt['ledger_row']={**self.row,'status_code':'503'};self.receipt['status']='FAILED_TERMINAL'
        self.terminal['status']='FAILED_TERMINAL'
        self.write(self.slot/'sec-receipt.json',self.receipt);self.write(self.slot/'terminal.json',self.terminal)
        with self.assertRaisesRegex(ValueError,'RECEIPT_LOG_ROW_DIFFERS'):self.read()


if __name__=='__main__':unittest.main()
