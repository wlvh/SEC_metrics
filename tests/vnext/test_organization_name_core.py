"""Small shared-name regressions; no filing identity acceptance inferred."""
import subprocess
import sys
from unittest import TestCase

from vnext.organization_name_core import _LEGAL_SUFFIX, _name_core


class OrganizationNameCoreTest(TestCase):
    def test_actual_conformed_names_retain_the_existing_words(self):
        self.assertEqual(('marriott','international'),_name_core('MARRIOTT INTERNATIONAL INC /MD/'))
        self.assertEqual(_name_core('MARRIOTT INTERNATIONAL INC /MD/'),_name_core('Marriott International, Inc.'))
        self.assertEqual(('ford','motor'),_name_core('FORD MOTOR CO'))
        self.assertEqual(("macy's",),_name_core('Macy’s, Inc.'))

    def test_different_substantive_words_and_original_marker_bounds_remain(self):
        self.assertNotEqual(_name_core('Example Holdings LLC'),_name_core('Example Manufacturing LLC'))
        self.assertEqual(('example','md'),_name_core('Example /md/'))
        self.assertEqual(('acme','2022'),_name_core('ACME 2022 PLC'))
        self.assertEqual((),_name_core('The Company Inc.'))

    def test_existing_c02_module_reexports_one_callable_and_same_policy(self):
        from vnext import historical_board_composition_v2 as original
        self.assertIs(_name_core,original._name_core)
        self.assertIs(_LEGAL_SUFFIX,original._LEGAL_SUFFIX)
        self.assertEqual('sha256:5284d56d9d3b3f0cf48fa5801ffbe25fcdb7a60e7a0cfc418847277b5b240473',
                         original._policy_identity())
        self.assertTrue(original._is_registrant('Ford Motor Company',{('ford','motor')}))
        self.assertFalse(original._is_registrant('Different Holdings',{('ford','motor')}))

    def test_lightweight_import_does_not_load_board_selector_or_terms(self):
        # Process needed: prior tests legitimately import the original module.
        code="from vnext.organization_name_core import _name_core; import sys; assert _name_core('Example Inc.')==('example',); assert not any('historical_board_composition' in n for n in sys.modules)"
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_small_c02_proposal_keeps_original_candidate_and_policy_identity(self):
        from tests.vnext.test_text_coverage import annual
        from tests.vnext.test_text_business_candidates import source_arguments
        from vnext.text_business_candidates import governance_source_document
        from vnext.historical_board_composition_v2 import board_composition_facts
        raw=annual('<p>Our Board has nine directors.</p>'
            '<p>Jane Smith is Chair of the Example Company Board.</p>'
            '<p>Jane Smith is Chair of the Different Holdings Board.</p>'
            '<h2>Audit Committee</h2>'
            '<p>The Audit Committee consists of Jane Smith and Alex Jones.</p>',form='DEF 14A')
        document=governance_source_document(**source_arguments(raw,'DEF 14A'))
        proposal=board_composition_facts(document=document,period_start='2025-01-01')
        self.assertEqual(2,len(proposal['candidates']))
        self.assertEqual('sha256:5284d56d9d3b3f0cf48fa5801ffbe25fcdb7a60e7a0cfc418847277b5b240473',
                         proposal['policy_hash'])
        self.assertFalse(proposal['numeric_board_counts_asserted'])
        self.assertFalse(proposal['board_measurement_date_assigned'])
