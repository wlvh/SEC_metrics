"""Counter behavior and restart boundaries; no network or provider fixture."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from vnext.canonical import content_hash
from vnext.continuous_call_ledger import recorded_ledger
from vnext.invocation_control import _exclusive_write_json


REQ = {'requirement_id':'issue_28_v14','requirement_closure_hash':content_hash(value='test')}


class ContinuousCallLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'ledger'

    def claim(self, ledger, name='request', channel='PROVIDER'):
        return ledger.claim(channel=channel,request_digest=content_hash(value=name),requirement=REQ,
            plan_id=content_hash(value={'plan':name}),purpose='remaining_development_feasibility')

    def terminal(self, ledger, path, intent, error=''):
        """Native MOCK-shaped fixtures exercise ledger semantics only."""
        def seal(body,key):return {**body,key:content_hash(value=body)}
        eid=content_hash(value={'test':intent['ordinal']});name=eid.split(':')[1]
        receipt=seal({'execution_id':eid,'status':'FAILED_TERMINAL',
            'counters':{'mock_transport_invocation_count':1,'real_model_provider_egress_count':0,
                        'paid_model_provider_call_count':0}},'execution_receipt_id')
        marker=seal({'ai_invocation_plan_id':intent['plan_id'],'execution_id':eid,
            'attempt_ordinal':1,'transport_kind':'MOCK'},'egress_marker_id')
        wire={'error_class':error,'usage':{'input_tokens':None if error=='USAGE_UNKNOWN' else 10,'output_tokens':1}}
        for relative,value in [('invocation_control/executions/'+name+'.json',receipt),
            ('invocation_control/egress/'+name+'/01.json',marker),('wire/journal.json',wire)]:
            _exclusive_write_json(path=path/relative,value=value)
        return ledger.finish_provider(path=path,intent=intent,execution=receipt,wire=wire)

    def test_reopen_and_changed_phase_do_not_reset_exhausted_total(self):
        ledger=recorded_ledger(root=self.root,limits=(1,1,2))
        with ledger.locked():
            path,intent=self.claim(ledger);self.terminal(ledger,path,intent)
        other=recorded_ledger(root=self.root,limits=(1,1,2))
        with other.locked():
            self.assertEqual(other.snapshot()['counts'],[1,1,0])
            with self.assertRaisesRegex(ValueError,'COUNT_EXHAUSTED'):self.claim(other,'another')
            path,intent=self.claim(other,'SEC-metadata','SEC')
            self.assertEqual(other.snapshot()['counts'],[1,1,1])

    def test_raw_request_identity_blocks_redraw_despite_new_plan(self):
        ledger=recorded_ledger(root=self.root)
        with ledger.locked():
            path,intent=self.claim(ledger);self.terminal(ledger,path,intent)
            with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):self.claim(ledger)
            self.claim(ledger,'actually-repaired-request')

    def test_crashed_intent_charged_and_only_affected_channel_stopped(self):
        ledger=recorded_ledger(root=self.root)
        with ledger.locked():self.claim(ledger)
        with recorded_ledger(root=self.root).locked() as again:
            state=again.snapshot();self.assertEqual(state['counts'],[1,1,0]);self.assertEqual(state['stopped_channels'],['PROVIDER'])
            with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.claim(again,'next')
            self.claim(again,'SEC-original','SEC')

    def test_402_unknown_usage_and_unknown_outcome_are_permanent_stops(self):
        for error in ['HTTP_402','USAGE_UNKNOWN','UNKNOWN_REMOTE_OUTCOME','SOURCE_AUTHENTICITY_FAILED']:
            ledger=recorded_ledger(root=self.root/error)
            with ledger.locked():
                path,intent=self.claim(ledger);self.terminal(ledger,path,intent,error)
                self.assertEqual(ledger.snapshot()['counts'],[1,1,0])
                with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.claim(ledger,'new')

    def test_deleted_last_slot_or_deleted_root_cannot_restart_total(self):
        ledger=recorded_ledger(root=self.root)
        with ledger.locked():
            path,_=self.claim(ledger);shutil.rmtree(path)
            with self.assertRaisesRegex(ValueError,'CLAIM_SET_CHANGED'):ledger.snapshot()
        shutil.rmtree(self.root)
        with self.assertRaisesRegex(ValueError,'MISSING_OR_RESET'):
            with recorded_ledger(root=self.root).locked():pass

    def test_changed_bound_native_receipt_is_rejected(self):
        ledger=recorded_ledger(root=self.root)
        with ledger.locked():
            path,intent=self.claim(ledger);self.terminal(ledger,path,intent)
            p=next((path/'invocation_control/executions').glob('*.json'));p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'EVIDENCE_CHANGED'):ledger.snapshot()

    def test_test_mode_cannot_be_relabelled_live(self):
        ledger=recorded_ledger(root=self.root);ledger.live=True
        with self.assertRaisesRegex(ValueError,'MODE_CHANGED'):
            with ledger.locked():pass

    def test_competing_process_cannot_enter_held_directory_lock(self):
        ledger=recorded_ledger(root=self.root)
        script="""import sys
from pathlib import Path
from vnext.continuous_call_ledger import recorded_ledger
with recorded_ledger(root=Path(sys.argv[1])).locked():
 print('ENTERED',flush=True)
"""
        with ledger.locked():
            process=subprocess.Popen([sys.executable,'-c',script,str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'scripts')})
            try:
                with self.assertRaises(subprocess.TimeoutExpired):process.communicate(timeout=0.3)
            finally:
                # The process enters only after the owning context releases.
                pass
        out,err=process.communicate(timeout=10)
        self.assertEqual(process.returncode,0,err);self.assertEqual(out.strip(),'ENTERED')


if __name__=='__main__':unittest.main()
