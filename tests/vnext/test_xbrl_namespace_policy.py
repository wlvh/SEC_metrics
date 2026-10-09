"""Current defaults stay fixed; dated FASB releases need an explicit consumer policy."""
import unittest
from vnext.xbrl_namespace_policy import is_fasb_namespace, YEAR_OR_DATE_RELEASE
from vnext.ordinary_b03_input_scope import inspect_depreciation_input
from tests.vnext.test_b03_current_input_scope import original,observation,PERIOD


class NamespacePolicyTest(unittest.TestCase):
    def test_default_year_only_and_explicit_date_release(self):
        for uri in ('http://fasb.org/us-gaap/2021','https://fasb.org/us-gaap/2025'):
            self.assertTrue(is_fasb_namespace(uri))
        uri='http://fasb.org/us-gaap/2021-01-31'
        self.assertFalse(is_fasb_namespace(uri))
        self.assertTrue(is_fasb_namespace(uri,namespace_policy=YEAR_OR_DATE_RELEASE))
        for uri in ('https://example.invalid/us-gaap/2021-01-31','http://fasb.org/us-gaap/2021q4','http://fasb.org/us-gaap/2021-01-31/extra'):
            self.assertFalse(is_fasb_namespace(uri,namespace_policy=YEAR_OR_DATE_RELEASE))
        with self.assertRaisesRegex(ValueError,'POLICY_UNSUPPORTED'):
            is_fasb_namespace('http://fasb.org/us-gaap/2025',namespace_policy='.*')

    def test_direct_scope_requires_explicit_release_policy(self):
        raw=original([('DepreciationDepletionAndAmortization','20','INF')]).replace(b'http://fasb.org/us-gaap/2025',b'http://fasb.org/us-gaap/2021-01-31')
        args=dict(raw_bytes=raw,entity='195',period=PERIOD,observations=[observation('DepreciationDepletionAndAmortization','20')])
        self.assertEqual(inspect_depreciation_input(**args)['status'],'WITHHOLD')
        self.assertEqual(inspect_depreciation_input(**args,namespace_policy=YEAR_OR_DATE_RELEASE)['status'],'KEEP')

    def test_composition_passes_same_explicit_policy_to_original_component_lookup(self):
        raw=original([('Depreciation','7','INF'),('AmortizationOfIntangibleAssets','13','INF')]).replace(b'http://fasb.org/us-gaap/2025',b'http://fasb.org/us-gaap/2021-01-31')
        observations=[{'semantic_role':role,'value':value,'source_binding':{'concept':'us-gaap:'+concept}} for role,concept,value in [('depreciation','Depreciation','7'),('amortization','AmortizationOfIntangibleAssets','13')]]
        args=dict(raw_bytes=raw,entity='195',period=PERIOD,observations=observations)
        with self.assertRaisesRegex(ValueError,'SELECTED_COMPONENT_NOT_IN_ORIGINAL'):
            inspect_depreciation_input(**args)
        answer=inspect_depreciation_input(**args,namespace_policy=YEAR_OR_DATE_RELEASE)
        self.assertEqual(answer['status'],'KEEP');self.assertEqual(answer['chain_input']['value'],'20')

if __name__=='__main__':unittest.main()
