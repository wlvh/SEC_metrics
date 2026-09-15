"""Normal selection cannot hide an ambiguous new source using an older value."""
import unittest

from tests.vnext.common import REPO_ROOT
from tests.vnext.test_governance_compensation_table import arguments, source, PERSON, SPEC_PATH
from vnext.normal_candidates import _governance_resolution


def preparation(raw_sources):
    items = []
    for raw in raw_sources:
        args = arguments(raw)
        args.pop('compiled_spec')
        items.append({'arguments': args, 'filing': {'form': '10-K/A'}, 'spec_path': SPEC_PATH})
    return {'input_binding': {'company_id': items[0]['arguments']['expected_company_id'],
            'prepared_annual_input': {'table_input': {'target_period': {
                'period_start': '2025-01-01', 'period_end': '2025-12-31'}}},
            'metric_input_status': {'C03': 'READY'}},
            'resolver_inputs': {'c03_sct_candidates': items}}


class NormalCandidateSemanticsTest(unittest.TestCase):
    def test_ambiguous_current_compensation_cannot_fall_back_to_old_scalar(self):
        newest = source(rows=[PERSON, ['Second Person Former Chief Executive Officer', '2025', '20', '75,000']])
        _, resolution = _governance_resolution(data_root=REPO_ROOT,
            preparation=preparation([newest, source()]), metric_id='C03')
        self.assertEqual('WITHHELD', resolution['result']['publication'])
        self.assertEqual('C03_REPORTED_TABLE_UNRESOLVED', resolution['result']['reason_code'])
        self.assertEqual(2, len(resolution['selection']['details'][0]['candidates']))

    def test_absent_table_may_continue_to_its_explicit_original(self):
        absent = source().replace(b'Name and Principal Position', b'Unrelated column')
        _, resolution = _governance_resolution(data_root=REPO_ROOT,
            preparation=preparation([absent, source()]), metric_id='C03')
        self.assertEqual('125000', resolution['result']['value'])


if __name__ == '__main__':
    unittest.main()
