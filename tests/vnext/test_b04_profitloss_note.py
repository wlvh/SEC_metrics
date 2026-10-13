"""Selected fact notes do not reinterpret quantities or unrelated candidates."""
from copy import deepcopy
import unittest
from vnext import ordinary_projection as projection


class ProfitLossNoteTest(unittest.TestCase):
    def setUp(self):
        self.result={'metric_id':'B04','publication':'PUBLISHED','value':'-8162000000'}
        self.claims={'chosen':{'claim_kind':'COMPANYFACTS_NUMERIC_FACT','locator':{'concept':'ProfitLoss'}},
                     'other':{'claim_kind':'COMPANYFACTS_NUMERIC_FACT','locator':{'concept':'NetIncomeLoss'}}}
        self.ordered=[{'source_binding':{'verified_claim_ids':['chosen']}}]

    def note(self):return projection._b04_profitloss_note(self.result,self.ordered,self.claims)

    def test_actual_selected_profitloss_gets_the_approved_scope_note(self):
        before=deepcopy((self.result,self.ordered,self.claims))
        self.assertEqual('ProfitLoss may include non-controlling interest.',self.note())
        self.assertEqual(before,(self.result,self.ordered,self.claims))

    def test_unselected_profitloss_does_not_annotate_another_selected_fact(self):
        self.ordered[0]['source_binding']['verified_claim_ids']=['other']
        self.assertEqual('',self.note())
        self.claims['other']['locator']['concept']='NetIncomeLossAvailableToCommonStockholdersBasic'
        self.assertEqual('',self.note())

    def test_withheld_null_structural_and_other_metrics_do_not_get_a_fake_scope_note(self):
        for change in ({'publication':'WITHHELD'},{'value':None},{'metric_id':'B07'}):
            with self.subTest(change=change):
                original=self.result;self.result={**original,**change}
                self.assertEqual('',self.note());self.result=original

    def test_missing_or_different_kind_and_prefixed_custom_concept_are_not_profitloss(self):
        for locator,kind in (({},'COMPANYFACTS_NUMERIC_FACT'),
                             ({'concept':'company:ProfitLoss'},'COMPANYFACTS_NUMERIC_FACT'),
                             ({'concept':'ProfitLoss'},'OTHER_REPORTED_TEXT')):
            with self.subTest(locator=locator,kind=kind):
                self.claims['chosen']={'locator':locator,'claim_kind':kind}
                self.assertEqual('',self.note())
        self.ordered=[];self.assertEqual('',self.note())

    def test_matched_verified_ids_remain_supported_without_scanning_all_claims(self):
        self.ordered[0]['source_binding']={'matched_verified_claim_ids':['chosen']}
        self.assertTrue(self.note())
        self.ordered[0]['source_binding']={'matched_verified_claim_ids':['other']}
        self.assertEqual('',self.note())


if __name__=='__main__':unittest.main()
