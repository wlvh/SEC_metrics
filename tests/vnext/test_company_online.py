"""Small count/failure checks; real HTTP-boundary CLI evidence is separate."""
import io,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from tests.vnext.common import REPO_ROOT
from vnext import company_online as online
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash


class Response(io.BytesIO):
    status=200
    headers={'Content-Type':'application/json'}


class CompanyOnlineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.ledger=recorded_ledger(root=self.root/'ledger',limits=(0,0,10))
        with self.ledger.locked():self.ledger.snapshot()
        self.context={'company_id':'marriott_international','metric_ids':['B01','B02'],
            'ledger_root':str(self.ledger.root),'maximum_counts':[0,0,10],
            'execution_mode':'RECORDED_TEST_ONLY','purpose':'remaining_development_feasibility',
            'requirement_id':'ordinary-company-capture-v1','requirement_closure_hash':content_hash(value={'recorded':True})}
        self.url='https://data.sec.gov/submissions/CIK0001048286.json'
        self.capture=online.Capture(self.root/'source',self.ledger,self.context,5)

    def test_one_native_http_attempt_uses_existing_count_and_no_retry(self):
        with patch('sec_http.urlopen',side_effect=lambda **kw:Response(b'{"cik":1048286}')) as transport:
            self.capture.get(self.url)
            self.capture.get(self.url)
        self.assertEqual(transport.call_count,1)
        self.assertEqual(self.capture.client.config['max_retries'],0)
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,1])
        self.assertEqual(len(self.capture.captures),1)
        self.assertTrue((self.root/'source/evidence/requests_log_manifest.json').is_file())

    def test_unknown_remote_blocks_next_claim_and_is_not_zero(self):
        with patch('sec_http.urlopen',side_effect=OSError('unknown remote')) as transport:
            with self.assertRaises(ValueError):self.capture.get(self.url)
        self.assertEqual(transport.call_count,1)
        with self.ledger.locked():
            state=self.ledger.snapshot();self.assertEqual(state['counts'],[0,0,1]);self.assertIn('SEC',state['stopped_channels'])
        self.assertEqual(self.capture.stop,'UNKNOWN_REMOTE_OUTCOME')
        with self.assertRaises(ValueError):self.capture.get(self.url)

    def test_persistence_interrupt_leaves_counted_pending_no_second_transport(self):
        with patch('sec_http.urlopen',side_effect=lambda **kw:Response(b'{}')) as transport, \
             patch('vnext.company_online._atomic_json',side_effect=RuntimeError('interrupted plan')):
            with self.assertRaises(RuntimeError):self.capture.get(self.url)
        self.assertEqual(transport.call_count,0)
        with self.ledger.locked():self.assertIn('SEC',self.ledger.snapshot()['stopped_channels'])

    def test_scope_or_limits_cannot_be_changed_by_call_context(self):
        for updated in [{'company_id':'ford_motor'}, {'maximum_counts':[0,0,11]}, {'execution_mode':'LIVE'}]:
            with self.assertRaises(ValueError):online._ledger({**self.context,**updated},'marriott_international',['B01'])

    def test_existing_real_ledger_never_created(self):
        with self.assertRaises(ValueError):online._ledger({**self.context,'ledger_root':str(self.root/'missing')},'marriott_international',['B01'])
        self.assertFalse((self.root/'missing').exists())

    def test_unsupported_metric_rejected_before_sources_or_claim(self):
        with self.assertRaisesRegex(ValueError,'METRIC_NOT_CONNECTED'):
            online.run_online_company(company_id='marriott_international',work_dir=self.root/'task',output_dir=self.root/'out',call_context=self.root/'missing-context',metric_ids=['D03'])
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[0,0,0])
