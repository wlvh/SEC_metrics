"""D03 must pass the authenticated original bytes to common note navigation."""
import unittest
from unittest.mock import patch
from tests.vnext.test_text_business_candidates import annual, BODY, source_arguments
from vnext import regulatory_investigation_candidates as source


class D03RawNavigationTest(unittest.TestCase):
    def test_full_source_preparation_passes_the_exact_authenticated_bytes(self):
        raw=annual(BODY)
        with patch.object(source,'legal_risk_candidates',wraps=source.legal_risk_candidates) as navigation:
            result=source.prepare_regulatory_investigation_candidates(**source_arguments(raw))
        self.assertIs(navigation.call_args.kwargs.get('raw_bytes'),raw)
        self.assertTrue(result)

    def test_changed_original_bytes_fail_before_navigation(self):
        args=source_arguments(annual(BODY));args['raw_bytes']+=b'<!-- changed -->'
        with patch.object(source,'legal_risk_candidates',side_effect=AssertionError('No navigation of wrong bytes')):
            with self.assertRaises(ValueError):source.prepare_regulatory_investigation_candidates(**args)


if __name__=='__main__':unittest.main()
