"""A coincidentally equal zero cannot hide a missing registered predecessor."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from vnext import traits
from vnext import normal_run_v3 as normal
from vnext.run_store import _mechanically_replay_open_run
from vnext.records import validate_record, validate_run_coordinates, RecordError


@unittest.skipUnless(os.environ.get('REGISTERED_EVENT_NATIVE_BATCH'), 'Requires actual registered-scope material')
class RegisteredEventRunMaterialTest(unittest.TestCase):
    def test_complete_scope_and_a_valid_current_only_zero(self):
        base=Path(os.environ['REGISTERED_EVENT_NATIVE_BATCH']).resolve()
        source=Path(os.environ['REGISTERED_EVENT_SOURCE_ROOT']).resolve()
        out=Path(os.environ['REGISTERED_EVENT_ATTACK_ROOT']).resolve()
        self.assertFalse(out.exists());out.mkdir()
        summary=json.loads((base/'summary.json').read_text());self.assertEqual(len(summary['coordinates']),6)
        expected={'C01':'12','E01':'5','E02':'0','E03':'12','E04':'0','E05':'4'}
        with self.assertRaisesRegex(RecordError,'exceeds 53 weeks'):
            validate_run_coordinates(target_period={'fiscal_year':2025,'period_start':'2024-01-01',
                'period_end':'2025-12-31'},company_traits=[])
        for item in summary['coordinates']:
            self.assertEqual(item['status'],'OPEN_CANDIDATE')
            self.assertEqual(item['public_row_status'],'CANDIDATE_ROW_PREPARED')
            self.assertEqual(item['result']['value'],expected[item['metric_id']])
            self.assertEqual(item['result']['period_start'],'2024-01-01')
            self.assertEqual(item['result']['period_end'],'2025-12-31')
            self.assertEqual(item['target_period'],{'fiscal_year':2025,'period_start':'2025-01-01','period_end':'2025-12-31'})
        company=summary['coordinates'][0]['company_id']
        ciks=traits.repository_company_ciks(repo_root=source,company_id=company)
        self.assertEqual(len(ciks),2)
        # Create a structurally legitimate graph while simulating the exact
        # implementation mistake: the registered predecessor is omitted.
        with patch.object(traits,'repository_company_ciks',return_value=ciks[:1]):
            data=out/'reduced-data';run=out/'reduced-run'
            normal.install_normal_inputs(data_root=data,company_id=company,metric_id='E02',source_root=source)
            reduced=normal.create_normal_run(data_root=data,run_dir=run,company_id=company,metric_id='E02')
            self.assertEqual(reduced['result']['quality'],'EXACT')
            self.assertEqual(reduced['result']['value'],'0')
            self.assertEqual(reduced['manifest']['status'],'OPEN')
        for line in (run/'records.jsonl').read_text().splitlines():
            validate_record(record=json.loads(line))
        with self.assertRaisesRegex(ValueError,'ORDINARY_INTEGRATED_INPUT_BINDING_CHANGED') as error:
            _mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
        (out/'summary.json').write_text(json.dumps({'status':'PASS','baseline_six_coordinates':True,
            'reduced_zero_was_structurally_valid':True,'reduced_zero_equal_to_correct_value':True,
            'cold_replay_after_restoring_registry':'REJECTED','reason':str(error.exception),
            'new_calls':[0,0,0]},indent=2)+'\n')


if __name__=='__main__':unittest.main()
