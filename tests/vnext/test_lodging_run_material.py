"""Source-replayed native lodging records, with no invented AI approval."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import unittest

from vnext import run_store
from vnext.calculator import calculate_observation_metric
from vnext.canonical import content_hash,sha256_file
from vnext.observations import structured_observation
from vnext.specs import compile_spec_file
from vnext.traits import repository_company_traits


@unittest.skipUnless(os.environ.get('LODGING_NATIVE_BATCH'),'Requires completed actual lodging Runs')
class LodgingNativeMaterialTest(unittest.TestCase):
    def test_source_derived_records_and_resigned_wrong_value_are_checked(self):
        root=Path(os.environ['LODGING_NATIVE_BATCH']);output=Path(os.environ['LODGING_ATTACK_ROOT'])
        self.assertFalse(output.exists());output.mkdir(parents=True)
        summary=json.loads((root/'summary.json').read_text())
        self.assertEqual('OPEN_CANDIDATES_READY',summary['status'])
        targets={row['metric_id']:row for row in summary['coordinates'] if row['company_id']=='marriott_international'}
        self.assertEqual({'B10','B11'},set(targets))
        for metric,coordinate in targets.items():
            data,run=root/coordinate['data_path'],root/coordinate['run_path']
            manifest,records,decisions=run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
            self.assertEqual('OPEN',manifest['status']);self.assertEqual([],decisions)
            self.assertFalse(any(r['record_type'] in {'AI_ATTEMPT','CANDIDATE','REVIEW_UNIT'} for r in records))
            observation=next(r for r in records if r['record_type']=='VERIFIED_OBSERVATION')
            self.assertEqual('',observation['approval_effect_hash'])
            self.assertTrue(any(r['record_type']=='DERIVED_ASSET' and len(r['tables'])==68 for r in records))
            with (root/'rows/marriott_international'/metric/'metrics_matrix.csv').open() as stream:
                public=next(csv.DictReader(stream))
            self.assertEqual(('69.3','percent') if metric=='B10' else ('128.8','USD'),(public['value'],public['unit']))
            if metric!='B10':continue
            spec_path=next(iter(manifest['spec_file_hashes']));spec=compile_spec_file(path=data/spec_path,dependency_specs={})
            trace=next(r for r in records if r['record_type']=='EXECUTION_TRACE')
            target=trace['calculation_target'];target={k:target[k] for k in ['company_id','period_start','period_end','scope','scope_key']}
            changed_observation=structured_observation(metric_id='B10',semantic_role=observation['semantic_role'],company_id=observation['company_id'],
                period_start=observation['period_start'],period_end=observation['period_end'],scope=observation['scope'],value='0.995',
                unit=observation['unit'],quality=observation['quality'],source_binding=observation['source_binding'])
            result,new_trace=calculate_observation_metric(compiled_spec=spec,target=target,
                company_traits=repository_company_traits(repo_root=data,company_id=observation['company_id']),observation=changed_observation)
            attack=output/'resigned-wrong-occupancy';shutil.copytree(run,attack)
            changed=[r for r in records if r['record_type'] not in {'VERIFIED_OBSERVATION','EXECUTION_TRACE','METRIC_RESULT'}]
            changed.extend([changed_observation,new_trace,result])
            (attack/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in changed))
            with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
            attack=output/'missing-grid';shutil.copytree(run,attack)
            (attack/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in records if r['record_type']!='DERIVED_ASSET'))
            with self.assertRaises((ValueError,run_store.RunStoreError)):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
            attack=output/'old-ai-spec';shutil.copytree(run,attack);old=copy.deepcopy(manifest)
            path='catalog/metrics/B10_occupancy.md';old['spec_file_hashes']={path:sha256_file(path=data/path)}
            (attack/'manifest.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
            with self.assertRaisesRegex(ValueError,'SOURCE_SPEC_OR_PERIOD_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
        (output/'summary.json').write_text(json.dumps({'status':'PASS','actual_baselines':2,'attacks':3,
            'cases':['resigned-wrong-occupancy','missing-grid','old-ai-spec'],'model_calls':0,'fake_review_created':False},indent=2))


if __name__=='__main__':unittest.main()
