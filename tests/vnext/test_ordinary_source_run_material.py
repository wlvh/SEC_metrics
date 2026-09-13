"""Actual ordinary Runs after owned recorded updates, with data/graph attacks."""
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import time
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only
from tests.vnext import test_normal_run_v3_material as graph_tests
from vnext import normal_run_v3 as normal,run_store
from vnext.canonical import content_hash
from vnext.ordinary_projection import render_ordinary_run
from vnext.ordinary_source_authority import register_recorded_session,OrdinarySourceAuthorityError,EXPORT_PATH
from vnext.ordinary_source_session import recorded_source_session,compare_annual_inputs
from sec_http import parse_request_log_rows,request_log_csv_bytes,refresh_request_log_manifest


@unittest.skipUnless(os.environ.get('ORDINARY_SOURCE_MATERIAL_ROOT'),'Requires a fresh external material root')
class OrdinarySourceRunMaterialTest(unittest.TestCase):
    def test_owned_updates_reach_three_adapters_and_reject_untrusted_changes(self):
        root=Path(os.environ['ORDINARY_SOURCE_MATERIAL_ROOT']).resolve()
        self.assertFalse(root.exists());root.mkdir(parents=True);started=time.monotonic()
        source,data=root/'source',root/'candidate-data';company='marriott_international'
        metrics=['B03','B08','B09','B10','B11'];prepare=normal.prepare_case
        def guarded(**kwargs):
            with original_sources_only():return prepare(**kwargs)
        with patch.object(normal,'prepare_case',side_effect=guarded), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
             patch('sec_http.urlopen',side_effect=AssertionError('Recorded input must not use HTTP')), \
             patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}):
            expected={m:normal.prepare_case(data_root=ROOT,company_id=company,metric_id=m)['results'][m] for m in metrics}
            normal.install_normal_inputs(data_root=source,company_id=company,metric_id='B03')
            session=recorded_source_session(data_root=source,journal_root=root/'execution',company_id=company,max_responses=3)
            before=session.prepare_annual_input()['prepared_input']
            for proof in before['source_proofs']:session.record_saved_response(url=proof['source_url'],accession=proof['accession'])
            after=session.prepare_annual_input()['prepared_input']
            with self.assertRaisesRegex(OrdinarySourceAuthorityError,'UNREGISTERED_LEDGER'):
                normal.prepare_case(data_root=source,company_id=company,metric_id='B03')
            checkpoint=register_recorded_session(session=session)
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE',compare_annual_inputs(previous=before,current=after)['status'])
            rows={};manifests={}
            for metric in metrics:
                normal.install_normal_inputs(data_root=data,source_root=source,company_id=company,metric_id=metric)
                run=root/'runs'/metric
                created=normal.create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id=metric)
                self.assertEqual('OPEN',created['manifest']['status'])
                self.assertEqual('RECORDED_TEST_ONLY',created['input_binding']['source_admission']['source_credit'])
                self.assertFalse(created['input_binding']['source_admission']['real_sec_credit'])
                self.assertEqual(tuple(expected[metric][k] for k in ['quality','value','unit','period_start','period_end']),
                                 tuple(created['result'][k] for k in ['quality','value','unit','period_start','period_end']))
                rendered=render_ordinary_run(data_root=data,run_dir=run)
                self.assertEqual('RECORDED_TEST_ONLY',rendered['receipt']['source_credit'])
                self.assertIn('no new SEC acquisition',rendered['row']['notes'])
                target=root/'rows'/metric;target.mkdir(parents=True)
                for name,raw in rendered['files'].items():(target/name).write_bytes(raw)
                graph_tests.save(target/'receipt.json',rendered['receipt'])
                rows[metric]=created['result'];manifests[metric]=created['manifest']
            base=root/'runs/B03';manifest=manifests['B03']
            case=normal.replay_case(data_root=data,manifest=manifest)
            self.assertEqual({'B01','B03'},set(case['results']))
            self.assertEqual('26186000000',case['results']['B01']['value'])
            for name,mutate in [('false-revenue',graph_tests.OrdinaryIntegratedMaterialTest.false_revenue),
                                ('missing-dependency',graph_tests.OrdinaryIntegratedMaterialTest.remove_dependency)]:
                attack=root/'attacks'/name;shutil.copytree(base,attack)
                mutate(copy.deepcopy(manifest),data,attack)
                with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                    run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
            for name in ['missing-checkpoint','resigned-credit-upgrade','unowned-append']:
                copied=root/'attacks'/name;shutil.copytree(data,copied/'data');shutil.copytree(base,copied/'run')
                changed_data=copied/'data';changed_run=copied/'run'
                if name=='missing-checkpoint':
                    (changed_data/EXPORT_PATH).unlink();reason='CHECKPOINT_NOT_INSTALLED'
                elif name=='resigned-credit-upgrade':
                    fake=copy.deepcopy(checkpoint);fake.update(real_sec_credit=True,source_credit='LIVE_SEC')
                    fake['checkpoint_id']=content_hash(value={k:v for k,v in fake.items() if k!='checkpoint_id'})
                    graph_tests.save(changed_data/EXPORT_PATH,fake)
                    changed=copy.deepcopy(manifest);key=changed['run_id'][len(normal.PREFIX):]
                    binding=json.loads((changed_data/normal.BINDING_DIRECTORY/(key+'.json')).read_text())
                    binding['source_admission'].update(source_credit='LIVE_SEC',real_sec_credit=True,checkpoint_id=fake['checkpoint_id'])
                    key=content_hash(value=binding)[7:];graph_tests.save(changed_data/normal.BINDING_DIRECTORY/(key+'.json'),binding)
                    changed['run_id']=normal.PREFIX+key;graph_tests.save(changed_run/'manifest.json',changed)
                    reason='IMPORTED_CHECKPOINT_CHANGED'
                else:
                    log=changed_data/'evidence/requests_log.csv';entries=parse_request_log_rows(text=log.read_text())
                    entries.append(dict(entries[-1]));log.write_bytes(request_log_csv_bytes(rows=entries))
                    refresh_request_log_manifest(workdir=changed_data,log_path=log);reason='UNREGISTERED_LEDGER'
                with self.assertRaisesRegex(OrdinarySourceAuthorityError,reason):
                    run_store._mechanically_replay_open_run(run_dir=changed_run,repo_root=changed_data,require_complete_results=True)
        graph_tests.save(root/'summary.json',{'status':'PASS','native_runs':5,'metric_results':6,'source_responses':3,
            'checkpoint_id':checkpoint['checkpoint_id'],'results':rows,'attacks':5,'seconds':time.monotonic()-started,
            'source_credit':'RECORDED_TEST_ONLY','real_sec_credit':False,'source_content_changed':False,
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False})


if __name__=='__main__':unittest.main()
