"""Explicit four-form C04 route leaves the ordinary two-form default intact."""
import socket
import unittest
from unittest.mock import patch

from vnext.c04_registration_successor import (EVENT_FORMS,
    _checked_inventory_rows, prepare_c04_registration_case)
from vnext.normal_governance_input import _filings, history_body_alignment
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT


class C04RegistrationSuccessorTest(unittest.TestCase):
    def test_saved_marriott_default_identity_and_explicit_successor(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK_FORBIDDEN')):
            ordinary = prepare_case(data_root=ROOT,
                company_id='marriott_international', metric_id='C04')
            successor = prepare_case(data_root=ROOT,
                company_id='marriott_international', metric_id='C04',
                c04_event_forms=EVENT_FORMS)
        self.assertEqual('catalog/r5/C04_auditor_changes_v2.md',
                         ordinary['spec_paths']['C04'])
        self.assertNotIn('c04_registration_successor', ordinary['input_binding'])
        self.assertEqual('catalog/r5/C04_auditor_changes_v3.md',
                         successor['spec_paths']['C04'])
        self.assertEqual(ordinary['results']['C04']['value'],
                         successor['results']['C04']['value'])
        self.assertEqual(0, len(successor['input_binding'][
            'c04_registration_successor']['registration_accessions']))
        self.assertEqual(EVENT_FORMS, successor['input_binding'][
            'c04_registration_successor']['event_forms'])
        self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0},
                         successor['admission']['new_business_calls'])

    def test_rejects_unapproved_form_subset_and_wrong_metric(self):
        with self.assertRaisesRegex(ValueError,
                                    'C04_REGISTRATION_EVENT_FORM_SCOPE_REQUIRED'):
            prepare_c04_registration_case(repo_root=ROOT,
                company_id='marriott_international',
                event_forms=['8-K12B'])
        with self.assertRaisesRegex(ValueError,
                                    'ORDINARY_C04_EVENT_FORM_SCOPE_WRONG_METRIC'):
            prepare_case(data_root=ROOT, company_id='marriott_international',
                metric_id='B06', c04_event_forms=EVENT_FORMS)

    def test_registration_event_outside_history_index_cannot_be_omitted_before_zero(self):
        payload = {'form': ['8-K12B'], 'reportDate': ['2025-06-01'],
                   'filingDate': ['2025-06-01'],
                   'accessionNumber': ['0000012345-25-000007'],
                   'primaryDocument': ['event.htm']}
        name = 'CIK0000012345-submissions-001.json'
        shard = {'name': name, 'filingFrom': '2024-01-01',
                 'filingTo': '2024-12-31'}
        self.assertEqual([], _filings(payload, inventory_name=name))
        self.assertIsNone(history_body_alignment(shard=shard, rows=[]))
        with self.assertRaisesRegex(ValueError,
                                    'C04_REGISTRATION_HISTORY_BODY_ALIGNMENT_CONFLICT'):
            _checked_inventory_rows(payload, inventory_name=name, shard=shard)
        shard['filingFrom'], shard['filingTo'] = '2025-01-01', '2025-12-31'
        rows = _checked_inventory_rows(payload, inventory_name=name, shard=shard)
        self.assertEqual(['8-K12B'], [row['form'] for row in rows])


if __name__ == '__main__':
    unittest.main()
