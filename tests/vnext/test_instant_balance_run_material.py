"""Actual current-balance Runs retain amendments and reject false cash graphs."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import unittest

from vnext import run_store
from vnext.calculator import calculate_observation_metric
from vnext.batch_workflow import BatchWorkflowError
from vnext.canonical import content_hash
from vnext.deterministic_router import validate_verified_claim
from vnext.normal_run_v3 import replay_case
from vnext.observations import structured_observation
from vnext.specs import compile_spec_file


@unittest.skipUnless(os.environ.get('INSTANT_BALANCE_NATIVE_BATCH'),'Requires completed actual current-balance Runs')
class InstantBalanceNativeMaterialTest(unittest.TestCase):
    def test_actual_current_balances_and_rejected_changed_computation_or_missing_amendment(self):
        root=Path(os.environ['INSTANT_BALANCE_NATIVE_BATCH']);out=Path(os.environ['INSTANT_BALANCE_ATTACK_ROOT'])
        self.assertFalse(out.exists());out.mkdir(parents=True)
        summary=json.loads((root/'summary.json').read_text())
        self.assertEqual('OPEN_CANDIDATES_READY',summary['status'])
        coordinates={r['metric_id']:r for r in summary['coordinates']}
        self.assertEqual({'B08','B09'},set(coordinates))
        for metric,row in coordinates.items():
            data,run=root/row['data_path'],root/row['run_path']
            manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
            self.assertEqual('OPEN',manifest['status']);self.assertEqual([],decisions)
            result=next(r for r in records if r['record_type']=='METRIC_RESULT')
            self.assertEqual('EXACT',result['quality'])
            self.assertEqual(('2025-12-31','2025-12-31'),(result['period_start'],result['period_end']))
            claims=[r for r in records if r['record_type']=='DETERMINISTIC_VERIFIED_CLAIM']
            self.assertTrue(claims)
            self.assertEqual({'2041610'},{r['attributes']['entity'] for r in claims})
            with (root/'rows'/row['company_id']/metric/'metrics_matrix.csv').open() as stream:
                public=next(csv.DictReader(stream))
            self.assertEqual(('3274000000','USD') if metric=='B09' else
                             ('1.256722332295499575431644495','ratio'),(public['value'],public['unit']))
            case=replay_case(data_root=data,manifest=manifest)
            component=case['input_binding']['component']
            self.assertEqual('WITHHELD',component['amendment_input']['decision'])
            self.assertEqual('INPUT_PROPERTY_PROVEN',component['instant_amendment_input']['decision'])
            self.assertFalse(component['instant_amendment_input']['annual_continuity_proven'])
            if metric!='B09':continue
            observation=next(r for r in records if r['record_type']=='VERIFIED_OBSERVATION')
            claim=next(r for r in records if r['record_type']=='DETERMINISTIC_VERIFIED_CLAIM')
            fake=copy.deepcopy(claim);fake['value']='9000000000'
            fake['verified_claim_id']=content_hash(value={k:v for k,v in fake.items() if k!='verified_claim_id'})
            validate_verified_claim(claim=fake)
            binding={**observation['source_binding'],'verified_claim_ids':[fake['verified_claim_id']]}
            false_observation=structured_observation(metric_id=metric,semantic_role=observation['semantic_role'],
                company_id=observation['company_id'],period_start=observation['period_start'],period_end=observation['period_end'],
                scope=observation['scope'],value=fake['value'],unit=observation['unit'],quality=observation['quality'],source_binding=binding)
            trace=next(r for r in records if r['record_type']=='EXECUTION_TRACE')
            target={k:trace['calculation_target'][k] for k in ['company_id','period_start','period_end','scope','scope_key']}
            spec=compile_spec_file(path=data/next(iter(manifest['spec_file_hashes'])),dependency_specs={})
            false_result,false_trace=calculate_observation_metric(compiled_spec=spec,target=target,
                company_traits=manifest['company_traits'],observation=false_observation)
            self.assertEqual('9000000000',false_result['value'])
            attack=out/'resigned-false-cash';shutil.copytree(run,attack)
            changed=[r for r in records if r['record_type'] not in {'DETERMINISTIC_VERIFIED_CLAIM','VERIFIED_OBSERVATION','EXECUTION_TRACE','METRIC_RESULT'}]
            changed.extend([fake,false_observation,false_trace,false_result])
            (attack/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in changed))
            with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
            copied_data,copied_run=out/'missing-amendment/data',out/'missing-amendment/run'
            shutil.copytree(data,copied_data);shutil.copytree(run,copied_run)
            amendment=component['prepared_input']['amendments'][0]['accessionNumber']
            proof=next(p for p in component['source_proofs'] if p['accession']==amendment)
            (copied_data/proof['request_repo_relative_path']).unlink()
            with self.assertRaises((ValueError,run_store.RunStoreError,BatchWorkflowError)):
                run_store._mechanically_replay_open_run(run_dir=copied_run,repo_root=copied_data,require_complete_results=True)
        (out/'summary.json').write_text(json.dumps({'status':'PASS','actual_baselines':2,'attacks':2,
            'cases':['resigned-false-cash','missing-amendment'],'calls':{'provider':0,'paid':0,'sec':0},
            'annual_continuity_proven':False,'production_authorized':False},indent=2)+'\n')


if __name__=='__main__':unittest.main()
