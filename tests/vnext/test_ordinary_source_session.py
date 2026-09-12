"""Native saved-input reads after explicit recorded source updates."""
import json
import copy
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_source_authority import verify_saved_source_proofs,NormalSourceAuthorityError
from vnext.ordinary_source_session import recorded_source_session,OrdinarySourceSessionError,compare_annual_inputs
from vnext.annual_update import AnnualUpdateError
from vnext.batch_workflow import BatchWorkflowError
from sec_http import request_log_csv_bytes,parse_request_log_rows,refresh_request_log_manifest


class OrdinarySourceSessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=prepare_saved_annual_input(repo_root=ROOT,company_id='marriott_international')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='recorded-ordinary-source-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.data=self.root/'data'
        self.addCleanup(patch.stopall)
        patch.object(socket.socket,'connect',side_effect=AssertionError('No network permitted')).start()
        patch('sec_http.urlopen',side_effect=AssertionError('Recorded session must not open HTTP')).start()
        patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}).start()
        paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for proof in self.original['source_proofs']:
            paths.update([proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']])
        for relative in paths:
            target=self.data/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
        self.session=recorded_source_session(data_root=self.data,journal_root=self.root/'journal',
            company_id=self.original['company_id'],max_responses=3)

    def test_three_recorded_responses_reach_the_unchanged_annual_input_reader(self):
        for proof in self.original['source_proofs']:
            terminal=self.session.record_saved_response(url=proof['source_url'],accession=proof['accession'])
            self.assertEqual('SUCCEEDED',terminal['status']);self.assertFalse(terminal['real_sec_credit'])
        updated=self.session.prepare_annual_input()
        self.assertEqual(self.original['filing'],updated['prepared_input']['filing'])
        self.assertEqual(self.original['table_input']['target_period'],updated['prepared_input']['table_input']['target_period'])
        self.assertNotEqual(self.original['input_id'],updated['prepared_input']['input_id'])
        self.assertEqual('RECORDED_TEST_ONLY',updated['source_admission']['source_credit'])
        self.assertEqual({'provider':0,'paid':0,'sec':0},updated['source_admission']['calls'])
        self.assertEqual(3,updated['source_admission']['recorded_responses'])
        change=compare_annual_inputs(previous=self.original,current=updated['prepared_input'])
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',change['status'])
        self.assertFalse(change['requires_candidate_processing'])
        # The unchanged real baseline does not turn these mock responses into
        # accepted real acquisitions merely because their bytes are valid.
        with self.assertRaises(NormalSourceAuthorityError):
            verify_saved_source_proofs(data_root=self.data,proofs=updated['prepared_input']['source_proofs'])

    def test_latest_failed_response_is_not_hidden_and_closes_further_test_attempts(self):
        proof=self.original['source_proofs'][0]
        self.session.record_saved_response(url=proof['source_url'])
        self.session.record_saved_response(url=proof['source_url'],status_code=500)
        with self.assertRaisesRegex(AnnualUpdateError,'LATEST_SOURCE_REQUEST_FAILED'):
            self.session.prepare_annual_input()
        with self.assertRaisesRegex(OrdinarySourceSessionError,'FAILED_TERMINAL_CLOSED'):
            self.session.record_saved_response(url=proof['source_url'])

    def test_consistent_unowned_ledger_append_cannot_self_enroll(self):
        path=self.data/'evidence/requests_log.csv';rows=parse_request_log_rows(text=path.read_text())
        rows.append(dict(rows[-1]));path.write_bytes(request_log_csv_bytes(rows=rows))
        refresh_request_log_manifest(workdir=self.data,log_path=path)
        with self.assertRaisesRegex(OrdinarySourceSessionError,'UNOWNED_LEDGER_APPEND'):
            self.session.prepare_annual_input()

    def test_unknown_terminal_and_budget_exhaustion_do_not_reopen_slots(self):
        proof=self.original['source_proofs'][0]
        for _ in range(3):self.session.record_saved_response(url=proof['source_url'])
        with self.assertRaisesRegex(OrdinarySourceSessionError,'RECORDED_BUDGET_EXHAUSTED'):
            self.session.record_saved_response(url=proof['source_url'])
        (self.root/'journal/terminals/000003.json').unlink()
        with self.assertRaisesRegex(OrdinarySourceSessionError,'OUTCOME_UNKNOWN'):
            self.session.prepare_annual_input()

    def test_changed_prefix_or_forged_terminal_is_not_trusted(self):
        proof=self.original['source_proofs'][0];self.session.record_saved_response(url=proof['source_url'])
        path=self.root/'journal/terminals/000001.json';record=json.loads(path.read_text());record['mode']='LIVE'
        from vnext.canonical import content_hash
        record['record_id']=content_hash(value={k:v for k,v in record.items() if k!='record_id'});path.write_text(json.dumps(record))
        with self.assertRaisesRegex(OrdinarySourceSessionError,'TERMINAL_NOT_OWNED'):
            self.session.prepare_annual_input()

    def test_rewritten_baseline_prefix_and_empty_proofs_are_rejected(self):
        with self.assertRaisesRegex(OrdinarySourceSessionError,'PROOFS_REQUIRED'):self.session.verify([])
        path=self.data/'evidence/requests_log.csv';rows=parse_request_log_rows(text=path.read_text())
        rows[0]['purpose']='rewritten-prefix';path.write_bytes(request_log_csv_bytes(rows=rows))
        refresh_request_log_manifest(workdir=self.data,log_path=path)
        with self.assertRaisesRegex(OrdinarySourceSessionError,'BASELINE_PREFIX_CHANGED'):
            self.session.prepare_annual_input()

    def test_changed_new_response_body_is_detected_and_persistence_failure_stays_unknown(self):
        proof=self.original['source_proofs'][0];terminal=self.session.record_saved_response(url=proof['source_url'])
        path=self.data/terminal['ledger_row']['repo_relative_path'];path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(BatchWorkflowError):self.session.prepare_annual_input()
        # Separate new session; this is a fixture failure, never a live retry.
        other=self.root/'other';other.mkdir()
        paths={'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
        for p in self.original['source_proofs']:
            paths.update([p['request_repo_relative_path'],p['request_headers_repo_relative_path']])
        for relative in paths:
            target=other/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
        session=recorded_source_session(data_root=other,journal_root=self.root/'other-journal',company_id=self.original['company_id'])
        from sec_http import SecHttpClient
        with patch.object(SecHttpClient,'_append_log_row',side_effect=OSError('recorded persistence failure')):
            with self.assertRaises(OSError):session.record_saved_response(url=proof['source_url'])
        with self.assertRaisesRegex(OrdinarySourceSessionError,'OUTCOME_UNKNOWN'):session.prepare_annual_input()

    def test_content_changes_and_regression_are_distinct_from_attempt_changes(self):
        # Pure comparison branches; these altered dictionaries are not admitted
        # source inputs and cannot be passed off as a new SEC acquisition.
        changed=copy.deepcopy(self.original);changed['source_proofs'][0]['content_sha256']='0'*64
        result=compare_annual_inputs(previous=self.original,current=changed)
        self.assertEqual('SOURCE_CONTENT_CHANGED',result['status']);self.assertTrue(result['requires_candidate_processing'])
        changed=copy.deepcopy(self.original);changed['filing']['reportDate']='2024-12-31'
        result=compare_annual_inputs(previous=self.original,current=changed)
        self.assertEqual('SOURCE_SELECTION_REGRESSED',result['status']);self.assertFalse(result['requires_candidate_processing'])
        self.assertFalse(result['input_authenticity_verified_by_comparison'])

    def test_replaced_data_root_and_journal_subdirectory_aliases_reject_before_write(self):
        moved=self.root/'moved-data';self.data.rename(moved);self.data.symlink_to(moved,target_is_directory=True)
        with self.assertRaisesRegex(OrdinarySourceSessionError,'PATH_ALIAS'):self.session.prepare_annual_input()
        self.data.unlink();moved.rename(self.data)
        elsewhere=self.root/'elsewhere';elsewhere.mkdir()
        (self.root/'journal/intents').symlink_to(elsewhere,target_is_directory=True)
        with self.assertRaisesRegex(OrdinarySourceSessionError,'RECORD_PATH_ALIAS'):
            self.session.record_saved_response(url=self.original['source_proofs'][0]['source_url'])
        self.assertEqual([],list(elsewhere.iterdir()))


if __name__=='__main__':unittest.main()
