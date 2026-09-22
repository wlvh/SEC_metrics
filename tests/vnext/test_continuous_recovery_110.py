"""One authorized replay slot, native history unchanged, no provider sockets."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import json,os,subprocess,sys,unittest
from tests.vnext import test_continuous_call_ledger as helpers
REQ = helpers.REQ
from vnext.canonical import canonical_json_bytes,content_hash
from vnext.continuous_call_ledger import recorded_ledger
from vnext.continuous_recovery_110 import recorded_authorization,RECORD_PATH,read_authorization,authorization
from vnext.invocation_control import _exclusive_write_json


class Recovery110Test(unittest.TestCase):
    setUp = helpers.ContinuousCallLedgerTest.setUp
    claim = helpers.ContinuousCallLedgerTest.claim
    terminal = helpers.ContinuousCallLedgerTest.terminal
    def failed(self,error='HTTP_402',name='original'):
        ledger=recorded_ledger(root=self.root)
        with ledger.locked():
            path,intent=self.claim(ledger,name)
            _exclusive_write_json(path=path/'semantic-request.json',value={'request':'unchanged business input'})
            _exclusive_write_json(path=path/'source.json',value={'source':'original complete source'})
            self.terminal(ledger,path,intent,error)
        return ledger,path,intent

    def allow(self,ledger):
        with ledger.locked():return recorded_authorization(ledger=ledger,original_ordinal=1)

    def test_only_original_request_can_claim_once_and_old_history_stays(self):
        ledger,path,intent=self.failed();old={p:p.read_bytes() for p in path.rglob('*') if p.is_file()}
        binding=(self.root/'binding.json').read_bytes();anchor=(self.root.parent/('.'+self.root.name+'.initialized.json')).read_bytes();claims=(self.root/'claims.jsonl').read_bytes()
        auth=self.allow(ledger)
        with ledger.locked():
            self.assertEqual(ledger.snapshot()['stopped_channels'],['PROVIDER'])
            with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.claim(ledger,'unrelated')
            new,new_intent=self.claim(ledger,'original')
            self.assertEqual(new.name,'0002');self.assertEqual(new_intent['recovery_authorization_id'],auth['authorization_id'])
            self.terminal(ledger,new,new_intent)
            self.assertEqual(ledger.snapshot()['counts'],[2,2,0]);self.assertEqual(ledger.snapshot()['stopped_channels'],[])
            with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):self.claim(ledger,'original')
            self.claim(ledger,'next genuine task')
        self.assertEqual(old,{p:p.read_bytes() for p in old});self.assertEqual((self.root/'binding.json').read_bytes(),binding)
        self.assertEqual((self.root.parent/('.'+self.root.name+'.initialized.json')).read_bytes(),anchor)
        self.assertTrue((self.root/'claims.jsonl').read_bytes().startswith(claims))
        with recorded_ledger(root=self.root).locked() as again:self.assertEqual(again.snapshot()['counts'],[3,3,0])

    def test_claim_consumes_before_terminal_and_restart_cannot_repeat(self):
        ledger,_,_=self.failed();self.allow(ledger)
        with ledger.locked():self.claim(ledger,'original')
        with recorded_ledger(root=self.root).locked() as again:
            self.assertEqual(again.snapshot()['counts'],[2,2,0])
            self.assertEqual(again.snapshot()['stopped_channels'],['PROVIDER'])
            with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.claim(again,'original')

    def test_new_stops_are_not_removed_by_old_authorization(self):
        for error in ['HTTP_402','UNKNOWN_REMOTE_OUTCOME','SOURCE_AUTHENTICITY_FAILED','USAGE_UNKNOWN','CONTEXT_REFERENCE_MISMATCH']:
            with self.subTest(error=error):
                self.root=self.root/error
                ledger,_,_=self.failed();self.allow(ledger)
                with ledger.locked():
                    p,i=self.claim(ledger,'original');self.terminal(ledger,p,i,error)
                    self.assertEqual(ledger.snapshot()['stopped_channels'],['PROVIDER'])
                    with self.assertRaisesRegex(ValueError,'CHANNEL_STOPPED'):self.claim(ledger,'next')

    def test_other_original_failures_and_existing_output_cannot_get_recovery(self):
        for error in ['','UNKNOWN_REMOTE_OUTCOME','SOURCE_AUTHENTICITY_FAILED','USAGE_UNKNOWN']:
            with self.subTest(error=error):
                self.root=self.root/(error or 'content')
                ledger,_,_=self.failed(error)
                with self.assertRaisesRegex(ValueError,'ORIGINAL_FAILURE_CHANGED'):self.allow(ledger)
        self.root=self.root/'usable-output';ledger,path,_=self.failed()
        (path/'wire/assistant-output.bin').write_bytes(b'usable output must not be repeated')
        with self.assertRaisesRegex(ValueError,'USABLE_OUTPUT'):self.allow(ledger)

    def test_resealed_wrong_binding_terminal_digest_and_mode_are_rejected(self):
        ledger,_,_=self.failed();auth=self.allow(ledger)
        for field,value in [('binding_id',content_hash(value='another')),('original_terminal_id',content_hash(value='wrong terminal')),
                            ('request_digest','wrong'),('original_ordinal',2),('execution_mode','LIVE'),('maximum_new_executions',2)]:
            bad=deepcopy(auth);bad[field]=value;bad['authorization_id']=content_hash(value={k:v for k,v in bad.items() if k!='authorization_id'})
            (self.root/RECORD_PATH).write_bytes(canonical_json_bytes(value=bad))
            with self.subTest(field=field),ledger.locked(),self.assertRaises(ValueError):ledger.snapshot()
        (self.root/RECORD_PATH).write_bytes(canonical_json_bytes(value=auth))

    def test_concurrent_processes_cannot_consume_twice(self):
        ledger,_,_=self.failed();self.allow(ledger)
        script='''import sys
from pathlib import Path
from vnext.continuous_call_ledger import recorded_ledger
from tests.vnext.test_continuous_call_ledger import REQ
from vnext.canonical import content_hash
with recorded_ledger(root=Path(sys.argv[1])).locked() as ledger:
 try:
  p,i=ledger.claim(channel='PROVIDER',request_digest=content_hash(value='original'),requirement=REQ,plan_id=content_hash(value='plan'),purpose='remaining_development_feasibility')
  print('CLAIMED')
 except ValueError as e:
  assert 'CHANNEL_STOPPED' in str(e),str(e)
  print('BLOCKED')
'''
        env={**os.environ,'PYTHONPATH':'scripts:.','PYTHONDONTWRITEBYTECODE':'1'}
        processes=[subprocess.Popen([sys.executable,'-c',script,str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env) for _ in range(2)]
        outputs=[]
        for proc in processes:
            stdout,stderr=proc.communicate(timeout=15);self.assertEqual(proc.returncode,0,stderr);outputs.append(stdout.strip())
        self.assertEqual(sorted(outputs),['BLOCKED','CLAIMED'])
        with ledger.locked():self.assertEqual(ledger.snapshot()['counts'],[2,2,0])

    def test_interrupted_claim_append_stays_consumed_and_blocks_restart(self):
        ledger,_,_=self.failed();self.allow(ledger)
        with ledger.locked(),patch('vnext.continuous_call_ledger._exclusive_write_json',side_effect=OSError('after durable claim append')):
            with self.assertRaises(OSError):self.claim(ledger,'original')
        with recorded_ledger(root=self.root).locked() as again:
            with self.assertRaisesRegex(ValueError,'CLAIM_SET_CHANGED'):self.claim(again,'original')

    def test_duplicate_recovery_marker_or_unmarked_duplicate_rejected_on_read(self):
        ledger,_,_=self.failed();self.allow(ledger)
        with ledger.locked():
            p,i=self.claim(ledger,'original');self.terminal(ledger,p,i)
        bad=deepcopy(i);bad.pop('recovery_authorization_id');bad['intent_id']=content_hash(value={k:v for k,v in bad.items() if k!='intent_id'})
        (p/'intent.json').write_bytes(canonical_json_bytes(value=bad))
        claims=(self.root/'claims.jsonl').read_text().splitlines();claims[-1]=canonical_json_bytes(value=bad).decode().strip();(self.root/'claims.jsonl').write_text('\n'.join(claims)+'\n')
        with ledger.locked(),self.assertRaisesRegex(ValueError,'DUPLICATE_REQUEST'):ledger.snapshot()

    def test_live_authorization_requires_original_root_and_real_pinned_comment(self):
        ledger,_,_=self.failed()
        # A test-mode record and a locally changed mode cannot become live permission.
        self.allow(ledger);ledger.live=True
        with self.assertRaises(ValueError):read_authorization(ledger)
        with self.assertRaises(ValueError):authorization(ledger=ledger)
        ledger.live=False

    def test_second_marked_recovery_and_removed_authorization_rejected(self):
        ledger,_,_=self.failed();auth=self.allow(ledger)
        with ledger.locked():
            p,i=self.claim(ledger,'original');self.terminal(ledger,p,i)
            third,body=self.claim(ledger,'next')
        changed=deepcopy(body);changed.update(request_digest=auth['request_digest'],recovery_authorization_id=auth['authorization_id'])
        changed['intent_id']=content_hash(value={k:v for k,v in changed.items() if k!='intent_id'})
        (third/'intent.json').write_bytes(canonical_json_bytes(value=changed))
        claims=(self.root/'claims.jsonl').read_text().splitlines();claims[-1]=canonical_json_bytes(value=changed).decode().strip();(self.root/'claims.jsonl').write_text('\n'.join(claims)+'\n')
        with ledger.locked(),self.assertRaisesRegex(ValueError,'RECOVERY_CLAIM_NOT_AUTHORIZED'):ledger.snapshot()
        (self.root/RECORD_PATH).unlink()
        with ledger.locked(),self.assertRaisesRegex(ValueError,'RECOVERY_CLAIM_NOT_AUTHORIZED'):ledger.snapshot()

    def test_live_owner_comment_is_pinned_and_not_caller_approved_boolean(self):
        from types import SimpleNamespace
        from vnext.normal_source_authority import ROOT
        config=json.loads((ROOT/'config/issue28_recovery_110_v1.json').read_text())
        comment=json.loads((ROOT/config['delegation_record_path']).read_text());body=json.loads(comment['body'])
        ledger=SimpleNamespace(root=Path(body['budget_root']),binding={'binding_id':body['original_binding_id'],'limits':[240,240,80]},live=True)
        with patch('vnext.annual_candidate._github',return_value=comment):
            self.assertEqual(authorization(ledger=ledger,online=True)['original_ordinal'],110)
        for field in ['user','updated_at','body']:
            bad=deepcopy(comment)
            if field=='user':bad['user']['login']='not-the-owner'
            elif field=='updated_at':bad['updated_at']='2026-09-23T00:00:00Z'
            else:bad['body']=json.dumps({**body,'maximum_new_executions_of_original_request':2})
            with self.subTest(field=field),patch('vnext.annual_candidate._github',return_value=bad),self.assertRaises(ValueError):
                authorization(ledger=ledger,online=True)

    def test_recovered_history_is_separate_and_cold_reader_rejects_rebinding(self):
        from vnext.continuous_recovery_110 import history_for_success,validate_history
        ledger,_,_=self.failed();self.allow(ledger)
        with ledger.locked():
            _,intent=self.claim(ledger,'original')
            # Synthetic successful terminal only for this pure history-reader contract test.
            terminal={'intent_id':intent['intent_id'],'status':'SUCCEEDED','stop_reason':''}
            history=history_for_success(ledger=ledger,intent=intent,terminal=terminal)
        self.assertEqual(history['original_terminal']['status'],'FAILED_TERMINAL')
        validate_history(history=history,intent=intent,terminal=terminal,mode='RECORDED_TEST_ONLY')
        for change in ['original_status','original_wire','new_ordinal','intent_authorization','mode']:
            bad=deepcopy(history);new_intent=deepcopy(intent);mode='RECORDED_TEST_ONLY'
            if change=='original_status':bad['original_terminal']['status']='SUCCEEDED'
            elif change=='original_wire':bad['original_wire']['error_class']='UNKNOWN_REMOTE_OUTCOME'
            elif change=='new_ordinal':bad['recovered_ordinal']=3
            elif change=='intent_authorization':new_intent['recovery_authorization_id']='unapproved'
            else:mode='LIVE'
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_history(history=bad,intent=new_intent,terminal=terminal,mode=mode)
