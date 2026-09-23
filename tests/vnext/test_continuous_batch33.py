"""One approved original-ledger batch; every test uses a recorded test ledger."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vnext.canonical import content_hash
from vnext.continuous_batch33 import (authorization, group_id,
    historical_successor_allowed, history_for_current, install_live_authorization,
    recorded_authorization,
    validate_history)
from vnext.continuous_call_ledger import recorded_ledger
from vnext.invocation_control import _exclusive_write_json

from tests.vnext.test_continuous_call_ledger import REQ


def group(metric, company, index, digest, original=None):
    return {'metric_id':metric,'company_id':company,'group_index':index,
            'initial_request_digest':digest,'source_id':content_hash(value=[metric,company]),
            'historical_ordinal':original}


class Batch33LedgerTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'ledger'
        self.ledger=recorded_ledger(root=self.root)

    def claim(self, name, *, batch_group=None):
        return self.ledger.claim(channel='PROVIDER', request_digest=content_hash(value=name),
            requirement=REQ, plan_id=content_hash(value=['plan',name]),
            purpose='remaining_development_feasibility', batch_group_id=batch_group)

    def finish(self, path, intent, *, status='SUCCEEDED', error=''):
        def seal(body, key):
            return {**body,key:content_hash(value=body)}
        identity=content_hash(value=['execution',intent['ordinal']]);name=identity.split(':')[1]
        execution=seal({'execution_id':identity,'status':status,
            'counters':{'mock_transport_invocation_count':1,'real_model_provider_egress_count':0,
                        'paid_model_provider_call_count':0}},'execution_receipt_id')
        marker=seal({'ai_invocation_plan_id':intent['plan_id'],'execution_id':identity,
            'attempt_ordinal':1,'transport_kind':'MOCK'},'egress_marker_id')
        wire={'error_class':error,'usage':{'input_tokens':10,'output_tokens':1}}
        for relative,value in [('invocation_control/executions/'+name+'.json',execution),
                               ('invocation_control/egress/'+name+'/01.json',marker),
                               ('wire/journal.json',wire)]:
            _exclusive_write_json(path=path/relative,value=value)
        return self.ledger.finish_provider(path=path,intent=intent,execution=execution,wire=wire)

    def stopped(self, name='ford171'):
        with self.ledger.locked():
            path,intent=self.claim(name)
            terminal=self.finish(path,intent,status='FAILED_TERMINAL',error='HTTP_402')
        return path,intent,terminal

    def test_exact_first_group_resumes_only_original_stop_and_restarts_cleanly(self):
        old,intent,terminal=self.stopped()
        original={p:p.read_bytes() for p in old.rglob('*') if p.is_file()}
        groups=[group('D04','enphase_energy',0,content_hash(value='enphase0')),
                group('D04','enphase_energy',1,content_hash(value='enphase1'))]
        with self.ledger.locked():
            auth=recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
            self.assertEqual(self.ledger.snapshot()['stopped_channels'],['PROVIDER'])
            with self.assertRaisesRegex(ValueError,'BATCH33_FIRST_D04_CLAIM_REQUIRED'):
                self.ledger.claim(channel='SEC',request_digest=content_hash(value='unapproved SEC'),
                    requirement=REQ,plan_id=content_hash(value='SEC plan'),
                    purpose='remaining_development_feasibility')
            with self.assertRaisesRegex(ValueError,'BATCH33_GROUP_REQUIRED'):self.claim('enphase0')
            with self.assertRaisesRegex(ValueError,'BATCH33_FIRST_CLAIM_CHANGED'):
                self.claim('enphase1',batch_group=group_id(groups[1]))
            path,claim=self.claim('enphase0',batch_group=group_id(groups[0]))
            self.assertEqual(claim['batch_authorization_id'],auth['authorization_id'])
            self.assertTrue(claim['batch_resume_171'])
            self.finish(path,claim)
            self.assertEqual(self.ledger.snapshot()['stopped_channels'],[])
            with self.assertRaisesRegex(ValueError,'BATCH33_REPAIR_NOT_ELIGIBLE'):
                self.claim('enphase0',batch_group=group_id(groups[0]))
            with self.assertRaisesRegex(ValueError,'BATCH33_BASE_GROUP_OR_ORDER_CHANGED'):
                self.claim('unapproved-digest',batch_group=group_id(groups[1]))
            second,second_intent=self.claim('enphase1',batch_group=group_id(groups[1]))
            self.finish(second,second_intent)
        self.assertEqual(original,{p:p.read_bytes() for p in old.rglob('*') if p.is_file()})
        with recorded_ledger(root=self.root).locked() as reopened:
            self.assertEqual(reopened.snapshot()['counts'],[3,3,0])
            self.assertEqual(reopened.snapshot()['stopped_channels'],[])
        (self.root/'batch33-authorization.json').unlink()
        with recorded_ledger(root=self.root).locked() as reopened, \
             self.assertRaisesRegex(ValueError,'BATCH33_AUTHORIZATION_MISSING'):
            reopened.snapshot()

    def test_two_specific_old_failed_digests_get_one_new_claim_each(self):
        with self.ledger.locked():
            for name,error in [('enphase0',''),('paramount0',''),('ford171','HTTP_402')]:
                path,intent=self.claim(name)
                self.finish(path,intent,status='FAILED_TERMINAL',error=error)
            groups=[group('D04','enphase_energy',0,content_hash(value='enphase0'),1),
                    group('D04','paramount_skydance_paramount_global',0,
                          content_hash(value='paramount0'),2)]
            recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=3)
            first,first_intent=self.claim('enphase0',batch_group=group_id(groups[0]))
            self.finish(first,first_intent)
            second,second_intent=self.claim('paramount0',batch_group=group_id(groups[1]))
            self.finish(second,second_intent)
            self.assertEqual(self.ledger.snapshot()['counts'],[5,5,0])
            with self.assertRaisesRegex(ValueError,'BATCH33_REPAIR_NOT_ELIGIBLE'):
                self.claim('paramount0',batch_group=group_id(groups[1]))
        with recorded_ledger(root=self.root).locked() as reopened:
            self.assertEqual(reopened.snapshot()['stopped_channels'],[])

    def test_separate_original_sec_claim_after_first_d04_does_not_spend_batch_slot(self):
        self.stopped()
        groups=[group('D04','enphase_energy',0,content_hash(value='enphase0')),
                group('D04','enphase_energy',1,content_hash(value='enphase1'))]
        with self.ledger.locked():
            auth=recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
            first,intent=self.claim('enphase0',batch_group=group_id(groups[0]))
            first_terminal=self.finish(first,intent)
            sec_path,sec_intent=self.ledger.claim(channel='SEC',
                request_digest=content_hash(value='separate C04 original-source fetch'),
                requirement=REQ,plan_id=content_hash(value='separate SEC plan'),
                purpose='remaining_development_feasibility')
            self.assertNotIn('batch_authorization_id',sec_intent)
            self.assertEqual(sec_path.name,'0003')
            self.assertEqual(self.ledger.snapshot()['stopped_channels'],['SEC'])
            second,second_intent=self.claim('enphase1',batch_group=group_id(groups[1]))
            second_terminal=self.finish(second,second_intent)
            self.assertEqual(second_intent['batch_attempt_index'],0)
            self.assertEqual(self.ledger.snapshot()['counts'],[3,3,1])
            history=history_for_current(ledger=self.ledger)
        rows=[{'ordinal':2,'intent':intent,'terminal':first_terminal},
              {'ordinal':4,'intent':second_intent,'terminal':second_terminal}]
        digests={row['ordinal']:row['intent']['request_digest'] for row in rows}
        self.assertTrue(validate_history(history=history,mode='RECORDED_TEST_ONLY',
            native_rows=rows,request_digests=digests,recovered_failed_ordinals=[]))
        self.assertEqual(history['authorization']['authorization_id'],auth['authorization_id'])
        altered=deepcopy(history)
        altered['claims'][1]['intent']['batch_authorization_id']=auth['authorization_id']
        altered['history_id']=content_hash(value={k:v for k,v in altered.items() if k!='history_id'})
        with self.assertRaises(ValueError):
            validate_history(history=altered,mode='RECORDED_TEST_ONLY',
                native_rows=rows,request_digests=digests,recovered_failed_ordinals=[])

    def test_new_provider_402_does_not_stop_separate_sec_channel(self):
        self.stopped()
        groups=[group('D04','enphase_energy',0,content_hash(value='enphase0'))]
        with self.ledger.locked():
            recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
            first,intent=self.claim('enphase0',batch_group=group_id(groups[0]))
            self.finish(first,intent,status='FAILED_TERMINAL',error='HTTP_402')
            self.assertEqual(self.ledger.snapshot()['stopped_channels'],['PROVIDER'])
            sec,sec_intent=self.ledger.claim(channel='SEC',
                request_digest=content_hash(value='independent source request'),
                requirement=REQ,plan_id=content_hash(value='independent source plan'),
                purpose='remaining_development_feasibility')
            self.assertEqual(sec.name,'0003')
            self.assertNotIn('batch_authorization_id',sec_intent)
            self.assertEqual(self.ledger.snapshot()['counts'],[2,2,1])

    def test_new_402_and_interrupted_claim_remain_stopped(self):
        for kind in ('HTTP_402','INTERRUPTED'):
            with self.subTest(kind=kind):
                self.root=self.root/kind
                self.ledger=recorded_ledger(root=self.root)
                self.stopped()
                groups=[group('D04','enphase_energy',0,content_hash(value='enphase0')),
                        group('D04','enphase_energy',1,content_hash(value='enphase1'))]
                with self.ledger.locked():
                    recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
                    path,intent=self.claim('enphase0',batch_group=group_id(groups[0]))
                    if kind=='HTTP_402':self.finish(path,intent,status='FAILED_TERMINAL',error='HTTP_402')
                with recorded_ledger(root=self.root).locked() as again:
                    self.ledger=again
                    self.assertEqual(again.snapshot()['counts'],[2,2,0])
                    self.assertEqual(again.snapshot()['stopped_channels'],['PROVIDER'])
                    with self.assertRaisesRegex(ValueError,'BATCH33_NEW_STOP_REMAINS'):
                        self.claim('enphase1',batch_group=group_id(groups[1]))

    def test_local_content_failure_blocks_only_its_company_and_no_free_retry(self):
        self.stopped()
        groups=[group('D04','enphase_energy',0,content_hash(value='enphase0')),
                group('D04','enphase_energy',1,content_hash(value='enphase1')),
                group('D04','paramount_skydance_paramount_global',0,content_hash(value='paramount0')),
                group('B13','enphase_energy',0,content_hash(value='b13-enphase0'))]
        with self.ledger.locked():
            recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
            first,intent=self.claim('enphase0',batch_group=group_id(groups[0]))
            self.finish(first,intent,status='FAILED_TERMINAL')
            self.assertEqual(self.ledger.snapshot()['stopped_channels'],[])
            with self.assertRaisesRegex(ValueError,'BATCH33_BASE_GROUP_OR_ORDER_CHANGED'):
                self.claim('enphase1',batch_group=group_id(groups[1]))
            with self.assertRaisesRegex(ValueError,'BATCH33_REPAIR_NOT_ELIGIBLE'):
                self.claim('enphase0',batch_group=group_id(groups[0]))
            with self.assertRaisesRegex(ValueError,'BATCH33_REPAIR_PROOF_NOT_YET_IMPLEMENTED'):
                self.ledger.claim(channel='PROVIDER',request_digest=content_hash(value='enphase0'),
                    requirement=REQ,plan_id=content_hash(value='repair plan'),
                    purpose='verification_after_engineering_repair',
                    batch_group_id=group_id(groups[0]),batch_repair_receipt={'unverified':True})
            other,other_intent=self.claim('paramount0',batch_group=group_id(groups[2]))
            self.finish(other,other_intent)
            b13,b13_intent=self.claim('b13-enphase0',batch_group=group_id(groups[3]))
            self.finish(b13,b13_intent)
            self.assertEqual(self.ledger.snapshot()['counts'],[4,4,0])

    def test_competing_processes_cannot_consume_the_first_group_twice(self):
        self.stopped();groups=[group('D04','enphase_energy',0,content_hash(value='enphase0'))]
        with self.ledger.locked():recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
        script='''import sys
from pathlib import Path
from vnext.continuous_call_ledger import recorded_ledger
from vnext.canonical import content_hash
from tests.vnext.test_continuous_call_ledger import REQ
with recorded_ledger(root=Path(sys.argv[1])).locked() as ledger:
 try:
  ledger.claim(channel='PROVIDER',request_digest=content_hash(value='enphase0'),
   requirement=REQ,plan_id=content_hash(value=['plan','enphase0']),
   purpose='remaining_development_feasibility',batch_group_id='D04:enphase_energy:0')
  print('CLAIMED')
 except ValueError:
  print('BLOCKED')
'''
        env={**os.environ,'PYTHONPATH':'scripts:.','PYTHONDONTWRITEBYTECODE':'1'}
        processes=[subprocess.Popen([sys.executable,'-c',script,str(self.root)],stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,text=True,env=env) for _ in range(2)]
        outputs=[]
        for process in processes:
            stdout,stderr=process.communicate(timeout=15)
            self.assertEqual(process.returncode,0,stderr)
            outputs.append(stdout.strip())
        self.assertEqual(sorted(outputs),['BLOCKED','CLAIMED'])
        with self.ledger.locked():self.assertEqual(self.ledger.snapshot()['counts'],[2,2,0])

    def test_cold_history_rechecks_claim_consumption_and_rejects_rebinding(self):
        self.stopped()
        groups=[group('D04','enphase_energy',0,content_hash(value='enphase0'))]
        with self.ledger.locked():
            recorded_authorization(ledger=self.ledger,groups=groups,original_stop_ordinal=1)
            path,intent=self.claim('enphase0',batch_group=group_id(groups[0]))
            terminal=self.finish(path,intent)
            history=history_for_current(ledger=self.ledger)
        rows=[{'ordinal':2,'intent':intent,'terminal':terminal}]
        digests={2:intent['request_digest']}
        self.assertTrue(validate_history(history=history,mode='RECORDED_TEST_ONLY',
            native_rows=rows,request_digests=digests,recovered_failed_ordinals=[]))
        for change in ('stop','claim','duplicate','digest'):
            bad=deepcopy(history)
            if change=='stop':bad['original_stop']['terminal']['stop_reason']=''
            elif change=='claim':bad['claims'][0]['intent']['batch_group_id']='D04:other:0'
            elif change=='duplicate':bad['claims'].append(deepcopy(bad['claims'][0]))
            else:bad_digests={2:content_hash(value='wrong digest')}
            bad['history_id']=content_hash(value={k:v for k,v in bad.items() if k!='history_id'})
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_history(history=bad,mode='RECORDED_TEST_ONLY',native_rows=rows,
                    request_digests=bad_digests if change=='digest' else digests,
                    recovered_failed_ordinals=[])


class Batch33ServerAuthorityTest(unittest.TestCase):
    def test_existing_approved_install_survives_the_first_counted_call(self):
        from contextlib import nullcontext
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'batch33-authorization.json').write_text('{}')
            approved={'authorization_id':content_hash(value='approved exact batch')}
            ledger=SimpleNamespace(root=root,locked=nullcontext,
                snapshot=lambda:{'counts':[123,123,50],'rows':[None]*173,
                                 'stopped_channels':[]})
            with patch('vnext.continuous_batch33._BOUND_PATHS',()), \
                 patch('vnext.continuous_batch33._config',return_value={'record_path':'batch33-authorization.json'}), \
                 patch('vnext.continuous_batch33.authorization',return_value=approved), \
                 patch('vnext.continuous_batch33.read_authorization',return_value=approved), \
                 patch('vnext.invocation_control._exclusive_write_json',
                       side_effect=AssertionError('MUST_NOT_REINSTALL')):
                self.assertEqual(install_live_authorization(ledger=ledger,
                    requirement={'execution_authority':{'files':{}}}),approved)

    def test_pinned_executor_transcription_is_not_a_local_boolean(self):
        from vnext.normal_source_authority import ROOT
        config=json.loads((ROOT/'config/issue28_batch33_v1.json').read_text())
        comment=json.loads((ROOT/config['delegation_record_path']).read_text())
        ledger=SimpleNamespace(root=Path(config['budget_root']),live=True,
            binding={'binding_id':config['binding_id'],'limits':[240,240,80]})
        with patch('vnext.continuous_batch33._originals'):
            offline=authorization(ledger=ledger)
            with patch('vnext.annual_candidate._github',return_value=comment):
                self.assertEqual(authorization(ledger=ledger,online=True),offline)
            for change in ('author','body','updated_at'):
                altered=deepcopy(comment)
                if change=='author':altered['user']['login']='other-user'
                elif change=='body':altered['body']=altered['body'].replace('66', '67', 1)
                else:altered['updated_at']='2026-09-24T00:00:00Z'
                with self.subTest(change=change), \
                     patch('vnext.annual_candidate._github',return_value=altered), \
                     self.assertRaises(ValueError):
                    authorization(ledger=ledger,online=True)

    def test_only_exact_111_successor_may_skip_current_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            path=root/'calls/0111/semantic-request.json';path.parent.mkdir(parents=True)
            source=content_hash(value='saved source')
            saved={'metric_id':'B13','company_id':'enphase_energy','source_id':source}
            _exclusive_write_json(path=path,value=saved)
            digest=content_hash(value='approved successor').split(':',1)[1]
            approved_group=group('B13','enphase_energy',0,digest,111)
            approved_group['source_id']=source
            approved={'execution_mode':'RECORDED_TEST_ONLY',
                      'test_groups':[approved_group]}
            replacement={'metric_id':'B13','company_id':'enphase_energy','source_id':source}
            self.assertTrue(historical_successor_allowed(authorization=approved,
                ledger=SimpleNamespace(root=root),ordinal=111,saved_request=saved,
                replacement_request=replacement,replacement_digest=digest))
            self.assertFalse(historical_successor_allowed(authorization=approved,
                ledger=SimpleNamespace(root=root),ordinal=112,saved_request=saved,
                replacement_request=replacement,replacement_digest=digest))
            for bad in ({**replacement,'source_id':content_hash(value='different')},
                        {**replacement,'metric_id':'D04'}):
                with self.assertRaisesRegex(ValueError,'BATCH33_111_SOURCE_GROUP_CHANGED'):
                    historical_successor_allowed(authorization=approved,
                        ledger=SimpleNamespace(root=root),ordinal=111,saved_request=saved,
                        replacement_request=bad,replacement_digest=digest)


if __name__ == '__main__':
    unittest.main()
