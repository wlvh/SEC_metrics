"""Updated-source native financial, governance, text and equity-guard routes."""
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
from vnext import normal_run_v3 as normal,run_store
from vnext.normal_run_v2 import _prepare_case as frozen_case
from vnext.ordinary_source_session import recorded_source_session
from vnext.ordinary_source_authority import register_recorded_session
from vnext.ordinary_projection import render_ordinary_run
from vnext.calculator import calculate_observation_metric
from vnext.observations import structured_observation

CASES={'marriott_international':['B06','C02','D01','D02','C03','C04'],
       'jpmorgan_chase':['A03','A04','A09','A11','A12','A13']}


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def build(root,cases):
    start=time.monotonic();rows=[]
    for company,metrics in cases.items():
        source,data=root/company/'source',root/company/'data'
        for metric in metrics:normal.install_normal_inputs(data_root=source,company_id=company,metric_id=metric)
        session=recorded_source_session(data_root=source,journal_root=root/company/'execution',company_id=company,max_responses=3)
        prepared=session.prepare_annual_input()['prepared_input']
        for proof in prepared['source_proofs']:session.record_saved_response(url=proof['source_url'],accession=proof['accession'])
        register_recorded_session(session=session)
        for metric in metrics:
            normal.install_normal_inputs(data_root=data,source_root=source,company_id=company,metric_id=metric)
            run=root/company/'runs'/metric
            created=normal.create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id=metric)
            rendered=render_ordinary_run(data_root=data,run_dir=run)
            target=root/company/'rows'/metric;target.mkdir(parents=True)
            for name,raw in rendered['files'].items():(target/name).write_bytes(raw)
            row={'company_id':company,'metric_id':metric,'result':created['result'],'run_status':created['manifest']['status'],
                 'source_credit':created['input_binding']['source_admission']['source_credit']}
            rows.append(row);save(root/'progress.json',rows)
    save(root/'summary.json',{'status':'PASS','rows':rows,'seconds':time.monotonic()-start,'source_responses':3*len(cases),
        'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False})


@unittest.skipUnless(os.environ.get('REMAINING_SOURCE_MATERIAL_ROOT') or os.environ.get('REMAINING_SOURCE_EXISTING_ROOT'),
                     'Requires a new or completed external material root')
class RemainingSourceMaterialTest(unittest.TestCase):
    def test_native_results_preserve_old_meanings_and_reject_bad_graph_or_missing_review(self):
        existing=os.environ.get('REMAINING_SOURCE_EXISTING_ROOT')
        root=Path(existing or os.environ['REMAINING_SOURCE_MATERIAL_ROOT']).resolve()
        company=os.environ.get('REMAINING_SOURCE_COMPANY');self.assertTrue(company is None or company in CASES)
        cases={company:CASES[company]} if company else CASES
        prepare=normal.prepare_case
        def guarded(**kwargs):
            with original_sources_only():return prepare(**kwargs)
        with patch.object(normal,'prepare_case',side_effect=guarded), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('No network')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('No DNS')), \
             patch('sec_http.urlopen',side_effect=AssertionError('No HTTP')), \
             patch.dict(os.environ,{'SEC_CONTACT_EMAIL':'sec-tests@wlvh.com'}):
            if not existing:
                self.assertFalse(root.exists());root.mkdir(parents=True);build(root,cases)
            summary=json.loads((root/'summary.json').read_text());self.assertEqual('PASS',summary['status'])
            self.assertEqual({(c,m) for c,ms in cases.items() for m in ms},
                             {(r['company_id'],r['metric_id']) for r in summary['rows']})
            attacks=Path(os.environ['REMAINING_SOURCE_ATTACK_ROOT']).resolve() if os.environ.get('REMAINING_SOURCE_ATTACK_ROOT') else root/'verified-attacks'
            self.assertFalse(attacks.exists());attacks.mkdir(parents=True)
            observed=[]
            for row in summary['rows']:
                c,m=row['company_id'],row['metric_id'];data=root/c/'data';run=root/c/'runs'/m
                manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
                self.assertEqual('OPEN',manifest['status']);case=normal.replay_case(data_root=data,manifest=manifest)
                self.assertEqual('RECORDED_TEST_ONLY',case['admission']['source_credit'])
                self.assertFalse(case['admission']['real_sec_credit'])
                result=next(r for r in records if r['record_type']=='METRIC_RESULT')
                with original_sources_only():old=frozen_case(data_root=ROOT,company_id=c,metric_id=m)
                if old['kind']=='STRUCTURED':
                    keys=['quality','value','unit','period_start','period_end']
                    self.assertEqual(tuple(old['result'][k] for k in keys),tuple(result[k] for k in keys))
                else:
                    self.assertEqual(['SYSTEM'],[d['reviewer_type'] for d in decisions])
                    self.assertTrue(result['text_payload']['items'])
                if m=='B06':
                    self.assertEqual(('NOT_MEANINGFUL',None),(result['quality'],result['value']))
                    with patch('vnext.normal_note_debt_results.prepare_note_debt_case',side_effect=AssertionError('Guard precedes debt')):
                        normal.replay_case(data_root=data,manifest=manifest)
                if m=='A03':
                    obs=next(r for r in records if r['record_type']=='VERIFIED_OBSERVATION')
                    fake=structured_observation(metric_id=m,semantic_role=obs['semantic_role'],company_id=c,
                        period_start=obs['period_start'],period_end=obs['period_end'],scope=obs['scope'],
                        value='9',unit=obs['unit'],quality=obs['quality'],source_binding=obs['source_binding'])
                    target={k:case['traces'][m]['calculation_target'][k] for k in
                            ['company_id','period_start','period_end','scope','scope_key']}
                    bad,bad_trace=calculate_observation_metric(compiled_spec=case['compiled_specs'][m],target=target,
                        company_traits=manifest['company_traits'],observation=fake)
                    self.assertEqual('EXACT',bad['quality']);self.assertNotEqual(result['value'],bad['value'])
                    attack=attacks/'false-lcr';shutil.copytree(run,attack)
                    changed=[r for r in records if r['record_type'] not in {'VERIFIED_OBSERVATION','METRIC_RESULT','EXECUTION_TRACE'}]
                    changed.extend([fake,bad_trace,bad]);(attack/'records.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in changed))
                    with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                        run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
                    observed.append('false-lcr-graph')
                if m=='D01':
                    attack=attacks/'missing-review';shutil.copytree(run,attack);(attack/'review_decisions.jsonl').write_text('')
                    with self.assertRaisesRegex((ValueError,run_store.RunStoreError),'Review unit has no effective decision'):
                        run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
                    observed.append('missing-text-review')
            save(attacks/'summary.json',{'status':'PASS','cases':len(summary['rows']),'attacks':observed,
                'source_credit':'RECORDED_TEST_ONLY','calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False})


if __name__=='__main__':unittest.main()
