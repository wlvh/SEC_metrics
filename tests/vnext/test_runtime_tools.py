"""Small business/format checks for tools used by the ordinary path."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.vnext.csv_output import METRIC_FIELDS, EVIDENCE_FIELDS, PublicationError, _csv_bytes
from scripts.vnext.deterministic_catalog import (
    ZeroAiReleaseError, _load_deterministic_catalog, _compiled_deterministic_spec,
    _validate_deterministic_component, _validate_deterministic_branch)

ROOT = Path(__file__).resolve().parents[2]


class RuntimeToolsTest(unittest.TestCase):
    def test_csv_columns_quotes_newlines_and_unicode_are_preserved(self):
        row = dict.fromkeys(METRIC_FIELDS, '')
        row.update(company='ACME', metric_id='D01', value='"Risk", one\nNext \u037e',
                   period_start='2025-01-01', period_end='2025-12-31', unit='text', status='TEXT_QUAL')
        raw = _csv_bytes(rows=[row], fieldnames=METRIC_FIELDS)
        import csv, io
        self.assertEqual(list(csv.DictReader(io.StringIO(raw.decode()))), [row])
        self.assertIn('\u037e'.encode(), raw)
        self.assertNotIn(b'\r\n', raw)
        self.assertEqual(raw.splitlines()[0].decode(), ','.join(METRIC_FIELDS))
        self.assertEqual(len(EVIDENCE_FIELDS), 18)

    def test_missing_or_extra_csv_field_is_a_real_failure(self):
        exact = dict.fromkeys(METRIC_FIELDS, '')
        for row in ({**exact, 'unknown': 'x'}, {k:v for k,v in exact.items() if k!='unit'}):
            with self.assertRaisesRegex(PublicationError, 'schema differs'):
                _csv_bytes(rows=[row], fieldnames=METRIC_FIELDS)

    def test_catalog_compile_keeps_metric_formula_unit_and_dimension_rules(self):
        catalog = _load_deterministic_catalog(repo_root=ROOT)
        self.assertEqual(len(catalog['metrics']), 14)
        for metric, route in catalog['metrics'].items():
            spec = _compiled_deterministic_spec(metric_id=metric, route=route)
            self.assertEqual(spec['compiled']['metric_id'], metric)
            self.assertEqual(spec['compiled']['canonical_unit'], route['canonical_unit'])
            self.assertEqual(spec['compiled']['applicability'], route['applicability'])
            for branch in route['branches']:
                self.assertEqual(_validate_deterministic_branch(branch=branch), branch)

    def test_invalid_formula_arity_unit_and_dimensions_not_silently_accepted(self):
        catalog = _load_deterministic_catalog(repo_root=ROOT)
        branch = copy.deepcopy(next(iter(catalog['metrics'].values()))['branches'][0])
        branch['components'] = []
        with self.assertRaisesRegex(ZeroAiReleaseError, 'arity'):
            _validate_deterministic_branch(branch=branch)
        component = copy.deepcopy(next(iter(catalog['metrics'].values()))['branches'][0]['components'][0])
        for update in ({'unit': ''}, {'dimension_policy': 'NONE', 'required_dimensions': {'Axis':'Member'}},
                       {'approved_concepts': []}, {'period_role': 'arbitrary'}):
            with self.subTest(update=update), self.assertRaises(ZeroAiReleaseError):
                _validate_deterministic_component(component={**component, **update})

    def test_small_source_and_spec_tools_do_not_import_release_workflows(self):
        code = """import sys,json
sys.path.insert(0,'scripts')
from vnext.csv_output import METRIC_FIELDS,_csv_bytes
from vnext.normal_run_specs import installed_ordinary_spec_documents
from vnext.normal_annual_input import prepare_saved_annual_input
assert len(installed_ordinary_spec_documents())==22
for name in ('vnext.publication','vnext.cutover','vnext.qualification','vnext.zero_ai_release','vnext.zero_ai_r2'):
 assert name not in sys.modules,name
print('LIGHT_ORDINARY_TOOLS_OK')
"""
        child = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                               capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(child.stdout.strip(), 'LIGHT_ORDINARY_TOOLS_OK')


if __name__ == '__main__': unittest.main()
