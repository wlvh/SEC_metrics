"""Real candidate idempotency, input failures and interrupted pointer recovery."""
import json
import csv
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch
from uuid import uuid4

from vnext import normal_run_v3 as normal,ordinary_update_cycle as cycle
from vnext.ordinary_source_session import recorded_source_session
from vnext.ordinary_source_authority import register_recorded_session


@unittest.skipUnless(os.environ.get('ORDINARY_UPDATE_MATERIAL_ROOT'),'Requires a fresh external material root')
class OrdinaryUpdateCycleTest(unittest.TestCase):
    def test_real_history_idempotency_failure_and_recovery(self):
        root=Path(os.environ['ORDINARY_UPDATE_MATERIAL_ROOT']).resolve();self.assertFalse(root.exists());root.mkdir(parents=True)
        company='marriott_international';source=root/'source';state=root/'state'
        def check(where=state):return cycle.run_once(state_root=where,source_root=source,company_id=company,metric_ids=['B01'])
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
             patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')), \
             patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}):
            normal.install_normal_inputs(data_root=source,company_id=company,metric_id='B01')
            session=recorded_source_session(data_root=source,journal_root=root/'source-execution',company_id=company,max_responses=3)
            original=session.prepare_annual_input()['prepared_input']
            inventory=original['source_proofs'][0]
            historical='request:attempt:2d141ff33cfa770ab8a490d98a7f79d8fde3f1d3b25a2ea404553b56d6e405b3'
            session.record_saved_response(url=inventory['source_url'],historical_test_attempt_id=historical)
            register_recorded_session(session=session)
            first=check();self.assertEqual('CANDIDATE_READY',first['status']);success=first['successful_attempt']
            self.assertTrue(first['new_candidate_created'])
            session.record_saved_response(url=inventory['source_url'],historical_test_attempt_id=historical)
            register_recorded_session(session=session)
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Unchanged content must reuse its candidate')):
                second=check();self.assertEqual('NO_SOURCE_CONTENT_CHANGE',second['status'])
                self.assertEqual(success,second['successful_attempt']);self.assertFalse(second['new_candidate_created'])
            session.record_saved_response(url=inventory['source_url']);register_recorded_session(session=session)
            changed=check();self.assertEqual('CANDIDATE_READY',changed['status'])
            self.assertNotEqual(success,changed['successful_attempt'])
            self.assertEqual(success,changed['previous_successful_attempt']);success=changed['successful_attempt']
            values=[]
            for identity in [first['successful_attempt'],success]:
                with (state/'attempts'/identity/'rows/B01/metrics_matrix.csv').open() as stream:
                    values.append(next(csv.DictReader(stream))['value'])
            self.assertEqual(['26186000000','26186000000'],values)
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Failed or restored input must not replace its success')):
                primary=source/original['table_input']['source_repo_relative_path'];raw=primary.read_bytes();primary.write_bytes(raw+b' ')
                failed=check();self.assertEqual('INPUT_FAILED',failed['status']);self.assertEqual(success,failed['successful_attempt'])
                self.assertTrue(failed['terminal']['error'])
                primary.write_bytes(raw)
                restored=check();self.assertEqual('NO_SOURCE_CONTENT_CHANGE',restored['status']);self.assertEqual(success,restored['successful_attempt'])
            # Reconcile a terminal written just before a failed reference write.
            interrupted=root/'pointer-crash';atomic=cycle.atomic_write_json
            def fail_reference(*,path,value):
                if path.name=='current.json' and value['successful_attempt'] is not None:raise OSError('test interruption after ready terminal')
                return atomic(path=path,value=value)
            with patch.object(cycle,'atomic_write_json',side_effect=fail_reference):
                with self.assertRaisesRegex(OSError,'test interruption'):check(interrupted)
            ready=[cycle._read(p) for p in (interrupted/'attempts').glob('*/terminal.json')]
            self.assertEqual(1,len(ready));self.assertEqual('CANDIDATE_READY',ready[0]['status'])
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Recovery must reuse completed Run')):
                recovered=check(interrupted)
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE',recovered['status'])
            self.assertEqual(ready[0]['attempt_id'],recovered['successful_attempt'])
            # An unfinished zero-egress intent is retained as interrupted; it
            # does not erase the prior successful candidate or reset history.
            current=json.loads((state/'current.json').read_text());configuration=cycle._read(state/'configuration.json');identity=uuid4().hex
            cycle._record(state/'attempts'/identity/'intent.json',{'record_type':'ORDINARY_UPDATE_INTENT','attempt_id':identity,
                'configuration_id':configuration['record_id'],'started_at':cycle._now(),
                'previous_attempt':current['latest_attempt'],'previous_successful_attempt':current['successful_attempt']})
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Recovery with unchanged successful input must not rebuild')):
                after_interrupt=check()
            self.assertEqual('INTERRUPTED',cycle._read(state/'attempts'/identity/'terminal.json')['status'])
            self.assertEqual(success,after_interrupt['successful_attempt'])
            with cycle._locked(state):
                with self.assertRaisesRegex(cycle.OrdinaryUpdateError,'UPDATE_ALREADY_RUNNING'):check()
            pointer=state/'current.json';saved=pointer.read_bytes();changed_pointer=json.loads(saved)
            changed_pointer['latest_attempt']='0'*32;pointer.write_text(json.dumps(changed_pointer))
            with self.assertRaisesRegex(cycle.OrdinaryUpdateError,'UPDATE_STATE_REFERENCE_MISSING'):check()
            pointer.write_bytes(saved)
            # A reference is revalidated from actual sources and Run records,
            # not accepted merely because current.json names a success.
            row=state/'attempts'/success/'rows/B01/metrics_matrix.csv';raw=row.read_bytes();row.write_bytes(raw.replace(b'26186000000',b'99999999999'))
            with self.assertRaisesRegex(cycle.OrdinaryUpdateError,'UPDATE_SUCCESS_ROW_CHANGED'):check()
            row.write_bytes(raw)
            withheld_root=root/'withheld'
            blocked=cycle.run_once(state_root=withheld_root,source_root=normal.ROOT,company_id='pfizer',metric_ids=['B06'])
            self.assertEqual('CANDIDATE_WITHHELD',blocked['status']);self.assertIsNone(blocked['successful_attempt'])
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Identical withheld input must not generate another Run')):
                for _ in range(2):
                    repeated=cycle.run_once(state_root=withheld_root,source_root=normal.ROOT,company_id='pfizer',metric_ids=['B06'])
                    self.assertEqual('PREVIOUS_INPUT_WITHHELD',repeated['status']);self.assertFalse(repeated['new_candidate_created'])
            latest=json.loads((state/'current.json').read_text())['latest_attempt']
            first_work=state/'attempts'/first['successful_attempt']
            latest_terminal=state/'attempts'/latest/'terminal.json'
            metadata_attacks=[
                ('latest-terminal-id',latest_terminal,'attempt_id','0'*32,'UPDATE_TERMINAL_IDENTITY_CHANGED'),
                ('latest-terminal-type',latest_terminal,'record_type','UNRELATED_TERMINAL_TYPE','UPDATE_TERMINAL_IDENTITY_CHANGED'),
                ('older-terminal-id',first_work/'terminal.json','attempt_id','0'*32,'UPDATE_TERMINAL_IDENTITY_CHANGED'),
                ('older-terminal-type',first_work/'terminal.json','record_type','UNRELATED_TERMINAL_TYPE','UPDATE_TERMINAL_IDENTITY_CHANGED'),
                ('older-terminal-status',first_work/'terminal.json','status','UNRECOGNIZED','UPDATE_TERMINAL_STATUS_INVALID'),
                ('older-terminal-intent',first_work/'terminal.json','intent_id','sha256:'+'0'*64,'UPDATE_TERMINAL_INTENT_CHANGED'),
                ('older-terminal-configuration',first_work/'terminal.json','configuration_id','sha256:'+'0'*64,'UPDATE_TERMINAL_INTENT_CHANGED'),
                ('older-intent-type',first_work/'intent.json','record_type','UNRELATED_INTENT_TYPE','UPDATE_INTENT_IDENTITY_CHANGED'),
                ('older-success-predecessor',first_work/'intent.json','previous_successful_attempt',first['successful_attempt'],'UPDATE_INTENT_PREDECESSOR_CHANGED'),
                ('older-terminal-removed',first_work/'terminal.json',None,None,'UPDATE_HISTORICAL_TERMINAL_MISSING')]
            evidence=root/'metadata-rejections';evidence.mkdir()
            for name,path,field,value,reason in metadata_attacks:
                with self.subTest(metadata=name):
                    saved={path:path.read_bytes()}
                    try:
                        if field is None:path.unlink()
                        else:
                            changed=json.loads(saved[path]);changed[field]=value
                            changed['record_id']=cycle.content_hash(value={k:v for k,v in changed.items() if k!='record_id'})
                            path.write_text(json.dumps(changed,indent=2)+'\n')
                            if path.name=='intent.json':
                                terminal=path.parent/'terminal.json';saved[terminal]=terminal.read_bytes()
                                paired=json.loads(saved[terminal]);paired['intent_id']=changed['record_id']
                                paired['record_id']=cycle.content_hash(value={k:v for k,v in paired.items() if k!='record_id'})
                                terminal.write_text(json.dumps(paired,indent=2)+'\n')
                        (evidence/(name+'.json')).write_text(json.dumps({'expected_reason':reason,
                            'input_files':{str(p.relative_to(state)):p.read_text() if p.exists() else None for p in saved}},indent=2)+'\n')
                        with self.assertRaisesRegex(cycle.OrdinaryUpdateError,reason):check()
                    finally:
                        for p,raw in saved.items():p.write_bytes(raw)
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Restored history must reuse its original candidate')):
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',check()['status'])
        (root/'summary.json').write_text(json.dumps({'status':'PASS','first_candidate':first['successful_attempt'],
            'changed_content_candidate':success,'recovered_candidate':ready[0]['attempt_id'],
            'checks':['initial-candidate','request-only-change-no-new-run','two-actual-source-versions-new-candidate',
            'failed-source-preserves-success','restored-source-no-new-run','ready-terminal-pointer-recovery',
            'unfinished-intent-retained','concurrent-check-rejected','invented-latest-reference-rejected','changed-successful-row-rejected',
            'same-withheld-input-does-not-create-more-runs','terminal-and-intent-identities-and-ancestry-rejected'],
            'metadata_rejections':[name for name,*_ in metadata_attacks],
            'calls':{'provider':0,'paid':0,'sec':0},'real_new_filing_verified':False,'production_authorized':False},indent=2)+'\n')


@unittest.skipUnless(os.environ.get('ORDINARY_UPDATE_COMPANY_MATERIAL_ROOT'),'Requires a fresh external company material root')
class OrdinaryCompanyUpdateTest(unittest.TestCase):
    def test_successful_metrics_survive_withheld_and_failed_neighbours(self):
        root=Path(os.environ['ORDINARY_UPDATE_COMPANY_MATERIAL_ROOT']).resolve();self.assertFalse(root.exists())
        def check():return cycle.run_company(state_root=root,source_root=normal.ROOT,
            company_id='pfizer',metric_ids=['B01','B06','B08'])
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
             patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')):
            first=check();self.assertEqual('UPDATES_PARTIAL',first['status'])
            metrics={m['metric_id']:m for m in first['metrics']}
            self.assertEqual('CANDIDATE_READY',metrics['B01']['status'])
            self.assertEqual('CANDIDATE_WITHHELD',metrics['B06']['status'])
            self.assertEqual('CANDIDATE_READY',metrics['B08']['status'])
            self.assertIsNone(metrics['B06']['last_verified_candidate'])
            revenue=metrics['B01']['last_verified_candidate']
            with (Path(revenue['rows_root'])/'B01/metrics_matrix.csv').open() as stream:
                self.assertEqual('62579000000',next(csv.DictReader(stream))['value'])
            self.assertEqual('2025-12-31',revenue['targets']['B01']['period_end'])
            successful={m:metrics[m]['successful_attempt'] for m in ['B01','B08']}
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Repeated input must not create any Run')):
                repeat=check();repeated={m['metric_id']:m for m in repeat['metrics']}
                self.assertEqual('UPDATES_PARTIAL',repeat['status'])
                self.assertEqual('PREVIOUS_INPUT_WITHHELD',repeated['B06']['status'])
                for metric in successful:
                    self.assertEqual('NO_SOURCE_CONTENT_CHANGE',repeated[metric]['status'])
                    self.assertEqual(successful[metric],repeated[metric]['successful_attempt'])
                    self.assertTrue(repeated[metric]['last_verified_candidate']['current_input_matches'])
                original=normal.prepare_case
                def fail_revenue_input(**kwargs):
                    if kwargs['data_root']==normal.ROOT and kwargs['metric_id']=='B01':
                        raise ValueError('Injected current revenue input failure')
                    return original(**kwargs)
                with patch.object(normal,'prepare_case',side_effect=fail_revenue_input):
                    failed=check()
                failed_metrics={m['metric_id']:m for m in failed['metrics']}
                self.assertEqual('INPUT_FAILED',failed_metrics['B01']['status'])
                self.assertEqual(successful['B01'],failed_metrics['B01']['successful_attempt'])
                self.assertFalse(failed_metrics['B01']['last_verified_candidate']['current_input_matches'])
                self.assertEqual(revenue['targets'],failed_metrics['B01']['last_verified_candidate']['targets'])
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',failed_metrics['B08']['status'])
                self.assertEqual(successful['B08'],failed_metrics['B08']['successful_attempt'])
                restored=check()
                self.assertEqual('NO_SOURCE_CONTENT_CHANGE',restored['metrics'][0]['status'])
            # Re-signed company summaries cannot replace the per-metric source
            # and native-Run verification performed by the controller.
            row=Path(revenue['rows_root'])/'B01/metrics_matrix.csv';raw=row.read_bytes()
            row.write_bytes(raw.replace(b'62579000000',b'99999999999'))
            with patch.object(normal,'create_normal_run',side_effect=AssertionError('Other unchanged metrics still reuse Runs')):
                tampered=check()
            row.write_bytes(raw);tampered_metrics={m['metric_id']:m for m in tampered['metrics']}
            self.assertEqual('UPDATE_BLOCKED',tampered_metrics['B01']['status'])
            self.assertIsNone(tampered_metrics['B01']['last_verified_candidate'])
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE',tampered_metrics['B08']['status'])
            with self.assertRaisesRegex(cycle.OrdinaryUpdateError,'UPDATE_GROUP_HISTORY_REQUIRES_PINNED_RUNTIME'):
                cycle.run_company(state_root=root/'metrics/B01',source_root=normal.ROOT,
                    company_id='pfizer',metric_ids=['B01'])
        (root/'summary.json').write_text(json.dumps({'status':'PASS','successful_attempts':successful,
            'checks':['independent-success-with-withheld','no-duplicate-runs','earlier-input-failure-does-not-stop-later-success',
                      'historical-period-and-current-status-separated','restored-source-reuses-success',
                      'changed-success-row-blocks-only-affected-metric','existing-group-history-not-silently-reset'],
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False},indent=2)+'\n')


if __name__=='__main__':unittest.main()
