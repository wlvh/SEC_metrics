"""Replay completed ordinary repair batches and inspect their actual rows."""
import csv
import io
import json
import os
from pathlib import Path
import unittest

from vnext.ordinary_projection import render_ordinary_run


@unittest.skipUnless(os.environ.get('ORDINARY_REPAIR_MANIFEST'),'Requires real completed repair batches')
class OrdinaryRepairProjectionMaterialTest(unittest.TestCase):
    def test_actual_repaired_rows_and_specific_source_failures(self):
        batches=json.loads(Path(os.environ['ORDINARY_REPAIR_MANIFEST']).read_text())
        expected_nonmeaningful={('marriott_international','B06'),('ford_motor_company','B07'),
            ('lumen_technologies','B06'),('lumen_technologies','B07')}
        checked=set()
        for kind,count in [('amendment',14),('denominator',6),('selection',2)]:
            root=Path(batches[kind]);summary=json.loads((root/'summary.json').read_text())
            self.assertEqual(count,len(summary['coordinates']))
            self.assertFalse(summary['production_authorized'])
            self.assertEqual({'provider':0,'paid':0,'sec':0},summary['new_calls'])
            for coordinate in summary['coordinates']:
                company,metric=coordinate['company_id'],coordinate['metric_id']
                self.assertEqual('CANDIDATE_ROW_PREPARED',coordinate['public_row_status'])
                rendered=render_ordinary_run(data_root=root/coordinate['data_path'],run_dir=root/coordinate['run_path'])
                self.assertEqual('OPEN',rendered['receipt']['run_status'])
                for filename,raw in rendered['files'].items():
                    self.assertEqual(raw,(root/'rows'/company/metric/filename).read_bytes())
                row=next(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
                evidence=list(csv.DictReader(io.StringIO(rendered['files']['metric_evidence.csv'].decode())))
                context=json.loads(row['context_or_dimension'])
                if kind=='amendment':
                    self.assertEqual('OPEN_CANDIDATE',coordinate['status'])
                    self.assertNotEqual('',row['value'])
                if kind=='denominator' and (company,metric) in expected_nonmeaningful:
                    self.assertEqual('NOT_MEANINGFUL',row['status'])
                    self.assertEqual('',row['value'])
                    self.assertTrue(evidence)
                    checked.add((company,metric))
                if kind=='selection':
                    selection=json.loads((root/coordinate['selection_path']).read_text())
                    self.assertEqual(selection,context['selection'])
                    if metric=='A05':
                        self.assertEqual('WITHHELD',row['status'])
                        self.assertEqual('NORMAL_COMPANYFACTS_PRIOR_HISTORY_SNAPSHOT_CONFLICT',selection['reason'])
                    else:
                        self.assertEqual('SOURCE_SCOPE_PROVEN',selection['status'])
                        self.assertEqual('0.155',row['value'])
        self.assertEqual(expected_nonmeaningful,checked)


if __name__=='__main__':
    unittest.main()
