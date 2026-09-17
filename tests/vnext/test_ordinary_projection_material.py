"""Inspect real CLI graphs/CSV outputs from an explicit integrated batch root."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import unittest

from vnext.ordinary_projection import render_ordinary_run
from vnext.publication import METRIC_FIELDS,EVIDENCE_FIELDS


@unittest.skipUnless(os.environ.get('ORDINARY_PROJECTION_MATERIAL_ROOT'),'Requires a completed ordinary CLI batch')
class OrdinaryProjectionMaterialTest(unittest.TestCase):
    def test_primary_results_and_source_component_evidence_are_replayed_and_not_dependencies(self):
        root=Path(os.environ['ORDINARY_PROJECTION_MATERIAL_ROOT'])
        summary=json.loads((root/'summary.json').read_text())
        self.assertEqual('OPEN_CANDIDATES_READY',summary['status'])
        observations={}
        for coordinate in summary['coordinates']:
            metric=coordinate['metric_id'];company=coordinate['company_id']
            data,run=root/coordinate['data_path'],root/coordinate['run_path']
            rendered=render_ordinary_run(data_root=data,run_dir=run)
            self.assertEqual('VERIFIED_OPEN_PREVIEW',rendered['receipt']['status'])
            self.assertEqual('OPEN',rendered['receipt']['run_status'])
            self.assertFalse(rendered['receipt']['production_authorized'])
            rows=list(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode())))
            evidence=list(csv.DictReader(io.StringIO(rendered['files']['metric_evidence.csv'].decode())))
            self.assertEqual(1,len(rows));self.assertEqual(metric,rows[0]['metric_id'])
            self.assertEqual(set(METRIC_FIELDS),set(rows[0]))
            self.assertTrue(all(set(row)==set(EVIDENCE_FIELDS) for row in evidence))
            for filename,raw in rendered['files'].items():
                self.assertEqual(raw,(root/'rows'/company/metric/filename).read_bytes())
            for entry in evidence:
                self.assertEqual(metric,entry['metric_id'])
                self.assertEqual(entry['content_sha256'],hashlib.sha256((data/entry['repo_relative_path']).read_bytes()).hexdigest())
            if metric=='D01':
                self.assertEqual(34,len(evidence))
                self.assertEqual(rows[0]['value'],'\n'.join(e['evidence_quote'] for e in evidence))
            observations[metric]=(rows[0],evidence)
        if 'B03' in observations:
            row,evidence=observations['B03']
            self.assertEqual('0.1756281982738868097456656229',row['value'])
            self.assertEqual({'26186000000','4141000000','145000000','313000000'},{e['value_normalized'] for e in evidence})
        if 'B05' in observations:
            row,evidence=observations['B05'];self.assertEqual('2608000000',row['value'])
            self.assertEqual({'3212000000','604000000'},{e['value_normalized'] for e in evidence})
            self.assertTrue(all(e['evidence_quote'].startswith('Parsed source fact:') for e in evidence))
        if 'E03' in observations:
            row,evidence=observations['E03'];self.assertEqual('3',row['value'])
            self.assertEqual(3,len(evidence));self.assertEqual({'1'},{e['value_normalized'] for e in evidence})
            self.assertEqual({'Item 5.02'},{e['concept_or_section'] for e in evidence})
        if 'B12' in observations:
            row,evidence=observations['B12'];self.assertEqual('2026',row['fiscal_year'])
            self.assertEqual(('2026-01-31','2026-01-31'),(row['period_start'],row['period_end']))
            self.assertEqual('72400000000',row['value']);self.assertIn('RPO substitute',row['metric_name'])
        if 'C03' in observations:
            row,evidence=observations['C03'];self.assertEqual('2026',row['fiscal_year'])
            self.assertEqual('49379252',row['value'])


if __name__=='__main__':unittest.main()
