"""Actual ordinary debt Runs and counterfeit but fully recomputed graphs."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from contextlib import nullcontext

from vnext import run_store
from vnext.calculator import calculate_metric
from vnext.canonical import content_hash, sha256_file
from vnext.normal_run_v3 import replay_case


@unittest.skipUnless(os.environ.get('NOTE_DEBT_NATIVE_BATCH'),'Requires completed actual note-debt Runs')
class NoteDebtNativeMaterialTest(unittest.TestCase):
    def test_actual_debt_guard_and_counterfeit_graphs(self):
        root = Path(os.environ['NOTE_DEBT_NATIVE_BATCH']); out = Path(os.environ['NOTE_DEBT_ATTACK_ROOT'])
        self.assertFalse(out.exists()); out.mkdir(parents=True)
        summary = json.loads((root/'summary.json').read_text())
        self.assertEqual('OPEN_CANDIDATES_READY',summary['status'])
        rows = {r['company_id']:r for r in summary['coordinates']}
        self.assertEqual({'enphase_energy','marriott_international'},set(rows))
        for company,row in rows.items():
            data,run = root/row['data_path'],root/row['run_path']
            no_debt_needed = (patch('vnext.normal_note_debt_results.prepare_note_debt_case',
                side_effect=AssertionError('Nonpositive equity must not evaluate the new debt grammar'))
                if company == 'marriott_international' else nullcontext())
            with no_debt_needed:
                manifest,records,decisions = run_store._mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
            self.assertEqual('OPEN',manifest['status']); self.assertEqual([],decisions)
            result = next(r for r in records if r['record_type']=='METRIC_RESULT')
            if company == 'marriott_international':
                self.assertEqual(('NOT_MEANINGFUL','DENOMINATOR_NONPOSITIVE'),(result['quality'],result['reason_code']))
                continue
            self.assertEqual(('EXACT','1.107959077222837051285943352'),(result['quality'],result['value']))
            with (root/'rows'/company/'B06/metrics_matrix.csv').open() as stream:
                public = next(csv.DictReader(stream))
            self.assertEqual((result['value'],'ratio'),(public['value'],public['unit']))
            case = replay_case(data_root=data,manifest=manifest)
            proof = case['input_binding']['source_proof']
            self.assertEqual('1204377000',proof['composition']['balances']['total'])
            self.assertTrue(proof['dimension_reconciliations'])
            facts = copy.deepcopy(case['selection']['audit']['measurement_reconciliation']['calculation_facts'])
            chosen = next(f for f in facts if f['concept']=='us-gaap:LongTermDebtCurrent')
            chosen['value'] = '9000000000'
            chosen['fact_id'] = 'fact:'+content_hash(value={k:v for k,v in chosen.items() if k!='fact_id'})
            target = {k:v for k,v in case['traces']['B06']['calculation_target'].items() if k!='metric_id'}
            false_result,false_trace,observations = calculate_metric(compiled_spec=case['compiled_specs']['B06'],
                target=target,company_traits=manifest['company_traits'],structured_facts=facts,verified_observations=[])
            self.assertNotEqual(result['value'],false_result['value']); self.assertEqual('EXACT',false_result['quality'])
            attack = out/'resigned-false-current-debt'; shutil.copytree(run,attack)
            changed = [*case['source_records'],*observations,false_trace,false_result]
            (attack/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in changed))
            with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
            attack = out/'historical-spec-substitution'; shutil.copytree(run,attack)
            changed_manifest = copy.deepcopy(manifest); old_path = 'catalog/r5/B06_new_source_v2.md'
            changed_manifest['spec_file_hashes'] = {old_path:sha256_file(path=data/old_path)}
            (attack/'manifest.json').write_text(json.dumps(changed_manifest,ensure_ascii=False,indent=2)+'\n')
            with self.assertRaisesRegex(ValueError,'SOURCE_SPEC_OR_PERIOD_CHANGED'):
                run_store._mechanically_replay_open_run(run_dir=attack,repo_root=data,require_complete_results=True)
        (out/'summary.json').write_text(json.dumps({'status':'PASS','actual_baselines':2,'attacks':2,
            'cases':['resigned-false-current-debt','historical-spec-substitution'],
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False},indent=2)+'\n')


if __name__ == '__main__': unittest.main()
