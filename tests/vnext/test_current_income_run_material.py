"""Real reported stub amounts cannot be accepted as comparable annual income."""
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import unittest

from vnext.calculator import _result_and_trace
from vnext.specs import compile_spec_file
from vnext.records import validate_record
from vnext.run_store import _mechanically_replay_open_run


@unittest.skipUnless(os.environ.get('CURRENT_INCOME_NATIVE_BATCH'), 'Requires current income material')
class CurrentIncomeRunMaterialTest(unittest.TestCase):
    def test_reported_stub_and_combined_amounts_cannot_replace_the_annual_guard(self):
        base=Path(os.environ['CURRENT_INCOME_NATIVE_BATCH']).resolve()
        out=Path(os.environ['CURRENT_INCOME_ATTACK_ROOT']).resolve()
        self.assertFalse(out.exists());out.mkdir()
        summary=json.loads((base/'summary.json').read_text());self.assertEqual(len(summary['coordinates']),2)
        for c in summary['coordinates']:
            self.assertEqual(c['status'],'OPEN_CANDIDATE')
            self.assertEqual(c['public_row_status'],'CANDIDATE_ROW_PREPARED')
            self.assertEqual(c['result']['quality'],'NOT_MEANINGFUL')
            self.assertEqual(c['result']['reason_code'],'ANNUAL_DURATION_OUT_OF_RANGE')
            self.assertIsNone(c['result']['value'])
            self.assertEqual(c['target_period'],{'fiscal_year':2025,'period_start':'2025-08-08','period_end':'2025-12-31'})
        c=next(c for c in summary['coordinates'] if c['metric_id']=='B01')
        data=base/c['data_path'];run=base/c['run_path']
        original=[json.loads(line) for line in (run/'records.jsonl').read_text().splitlines()]
        trace=next(r for r in original if r['record_type']=='EXECUTION_TRACE')
        spec=compile_spec_file(path=data/'catalog/metrics/B01_revenue.md',dependency_specs={})
        checks=[]
        for name,amount in [('reported_stub_as_annual','12269000000'),('combined_predecessor_and_successor','28891000000')]:
            dest=out/name;shutil.copytree(run,dest)
            result,new_trace=_result_and_trace(compiled_spec=spec,target=trace['calculation_target'],
                applicability='APPLICABLE',quality='EXACT',publication='PUBLISHED',reason_code='PASS',
                value=Decimal(amount),result_unit='USD',trace_steps=trace['steps'],input_ids=trace['input_observation_ids'])
            records=[r for r in original if r['record_type'] not in {'METRIC_RESULT','EXECUTION_TRACE'}]+[new_trace,result]
            for r in records:validate_record(record=r)
            (dest/'records.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records))
            with self.assertRaisesRegex(ValueError,'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                _mechanically_replay_open_run(run_dir=dest,repo_root=data,require_complete_results=True)
            checks.append({'case':name,'records_reidentified_and_valid':True,'same_real_input_observations':True,'result':'REJECTED'})
        (out/'summary.json').write_text(json.dumps({'status':'PASS','checks':checks,'new_calls':[0,0,0]},indent=2)+'\n')


if __name__=='__main__':unittest.main()
