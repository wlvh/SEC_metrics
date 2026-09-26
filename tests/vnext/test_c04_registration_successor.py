"""Explicit four-form C04 route leaves the ordinary two-form default intact."""
import socket
import unittest
from unittest.mock import patch

from vnext.c04_registration_successor import EVENT_FORMS, prepare_c04_registration_case
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


if __name__ == '__main__':
    unittest.main()
